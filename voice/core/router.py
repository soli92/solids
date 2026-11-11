"""
voice/core/router.py — EventRouter: sole choke point between runtime and TTS queue.

Position in the event chain (US-145, contract §4.2):

    runtime.submit() ──stream events──▶ EventRouter ──┬──▶ tts_queue   (SpokenSummary, Acknowledgment, Question, Error)
                                                       └──▶ visual_sink (Artifact, Progress, Done)

Non-negotiable invariant (EP-041 §Artifacts never to TTS, US-145 AC3):
    Artifact.content has NO code path to the TTS queue.
    The router discards it (visual_sink) and logs WARNING if it reaches the TTS path
    due to a programming error (defense in depth, AC5).
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from typing import TextIO

from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    Error,
    Progress,
    Question,
    RuntimeEvent,
    SpokenSummary,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTS-safe allowlist (invariant §4.2, US-145 AC3)
# ---------------------------------------------------------------------------

# ONLY these types are enqueued to the speech synthesizer.
# Artifact and Done are not listed here: they have no path to tts_queue.
#: Ogni quanto, al massimo, un avanzamento puo' essere PRONUNCIATO.
#: Lo schermo li riceve tutti; la voce no, e non e' una limitazione tecnica ma il canale
#: asimmetrico di PATTERN §30.1: un turno produce decine di `tool_use`, e leggerli tutti ad
#: alta voce renderebbe il canale vocale inutilizzabile proprio per chi non ha lo schermo.
PROGRESS_TTS_INTERVALLO_S: float = 25.0

#: Dal nome dello strumento a un verbo. Si pronuncia COSA sta facendo, non SU COSA: un
#: percorso di file letto ad alta voce e' rumore, e cambia a ogni chiamata.
_VERBO_PER_STRUMENTO: dict[str, str] = {
    "Read": "sto leggendo", "Grep": "sto cercando", "Glob": "sto cercando",
    "Write": "sto scrivendo", "Edit": "sto scrivendo", "NotebookEdit": "sto scrivendo",
    "Bash": "sto eseguendo comandi", "Task": "ho delegato a un agente",
    "WebFetch": "sto consultando il web", "WebSearch": "sto consultando il web",
}


def annuncio_grossolano(testo_progress: str) -> str:
    """«Read visual/server.py» -> «sto leggendo».

    Il testo fine resta intatto per lo schermo: qui se ne ricava solo la classe di
    attivita'. Uno strumento sconosciuto non e' un errore — si dice che si sta lavorando.
    """
    strumento = (testo_progress or "").split(" ", 1)[0]
    return _VERBO_PER_STRUMENTO.get(strumento, "sto lavorando")


TTS_ALLOWED: frozenset[type] = frozenset(
    {SpokenSummary, Acknowledgment, Question, Error, Progress}
)

# ---------------------------------------------------------------------------
# Regex for spoken_summary_extractor (US-145 AC2)
# ---------------------------------------------------------------------------

# Any markdown fence: ```lang\n...\n```
# Fence content is artifact; text outside fences is spoken candidate.
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

# Spoken-specific fence: ```spoken\n...\n```
_SPOKEN_FENCE_RE = re.compile(r"```spoken\n(.*?)```", re.DOTALL)

# HTML spoken comment: <!-- spoken: <text> -->
_SPOKEN_COMMENT_RE = re.compile(r"<!--\s*spoken:\s*(.*?)\s*-->", re.DOTALL)


# ---------------------------------------------------------------------------
# Module-level extractor (US-145 AC2)
# ---------------------------------------------------------------------------

def spoken_summary_extractor(raw_text: str) -> tuple[list[str], list[str]]:
    """
    Separate free text from markdown fence blocks (```lang...```).

    Text outside fences is spoken candidate (SpokenSummary);
    fence content is artifact (code, diff, log, JSON...) — NEVER to TTS.
    Fallback: text without fences → all in parlato_list.

    This hook implements the syntactic separator contract (US-145 AC2, Option A):
    the fence pattern is what the LLM spontaneously produces for code/diff
    and does not collide with normal speech.

    Args:
        raw_text: raw text produced by the LLM (potentially mixed text + fence).

    Returns:
        (parlato_list, artefatto_list) where:
            parlato_list:   list of speakable text segments (outside fences).
            artefatto_list: list of fence contents (code, diff...) — NEVER sent to TTS.
    """
    if not raw_text or not raw_text.strip():
        return ([], [])

    artefatto_list: list[str] = []
    parlato_parts: list[str] = []

    last_end = 0
    for match in _FENCE_RE.finditer(raw_text):
        before = raw_text[last_end : match.start()].strip()
        if before:
            parlato_parts.append(before)
        fence_content = match.group(1).rstrip()
        if fence_content:
            artefatto_list.append(fence_content)
        last_end = match.end()

    after = raw_text[last_end:].strip()
    if after:
        parlato_parts.append(after)

    # Fallback: no fence found → entire text is spoken candidate
    if not artefatto_list and not parlato_parts and raw_text.strip():
        parlato_parts = [raw_text.strip()]

    return (parlato_parts, artefatto_list)


# ---------------------------------------------------------------------------
# EventRouter
# ---------------------------------------------------------------------------

class EventRouter:
    """
    EventRouter is the ONLY component authorized to write to the TTS queue;
    no other module (stt, runtime, state_machine) accesses it directly.

    Applies the TTS-safe allowlist (not denylist, EP-041 §Constraint): only types in
    TTS_ALLOWED can reach tts_queue. Artifact is routed exclusively
    to the visual channel (US-145 AC3). The defensive check in _to_tts ensures
    no non-spoken type reaches TTS even in case of a call error
    (AC5: WARNING + discard).
    """

    def __init__(
        self,
        tts_queue: asyncio.Queue,
        visual_sink: TextIO | None = None,
    ) -> None:
        """
        Args:
            tts_queue:   async queue toward the TTS synthesizer (piper_tts).
            visual_sink: text sink for the visual channel; default sys.stdout.
                         Accepts any object with a .write(str) method for testability.
        """
        self._tts_queue = tts_queue
        self._sink: TextIO = visual_sink if visual_sink is not None else sys.stdout
        #: Quando e' stato pronunciato l'ultimo avanzamento. `Acknowledgment` lo azzera,
        #: perche' la strozzatura e' per turno: un turno nuovo non deve ereditare il
        #: silenzio di quello prima.
        self._ultimo_progress_parlato: float = 0.0

    async def route(self, event: RuntimeEvent) -> bool:
        """
        Route a RuntimeEvent to the correct channel (TTS or visual_sink).

        Routing table (US-145 AC1):
            SpokenSummary  → tts_queue (event.text)
            Acknowledgment → tts_queue (event.text)
            Question       → tts_queue (event.text)
            Error          → tts_queue (brief) + visual_sink (detail); closes turn
            Progress       → visual_sink; optional TTS announcement if text present
            Artifact       → visual_sink ONLY; never to TTS (AC3)
            Done           → visual_sink; closes turn

        Args:
            event: typed event emitted by FactoryRuntime.submit().

        Returns:
            True  — turn continues (more events expected).
            False — turn ended (Done or Error received).

        Note (AC5): if _to_tts receives a type not in TTS_ALLOWED (due to an
        external call error), it discards with WARNING without enqueuing to TTS.
        """
        match event:
            case SpokenSummary():
                await self._to_tts(event, event.text)
                return True

            case Acknowledgment():
                self._ultimo_progress_parlato = 0.0
                await self._to_tts(event, event.text)
                return True

            case Question():
                await self._to_tts(event, event.text)
                return True

            case Error():
                # Error: visual channel (detail) + TTS (brief speakable version).
                # Runtime contract §7 and factory_runtime.py: TTS + visual destination.
                self._sink.write(f"[ERROR] {event.message}\n")
                await self._to_tts(event, f"Errore: {event.message}")
                return False

            case Progress():
                pct_str = f" {event.pct:.0%}" if event.pct is not None else ""
                # Lo schermo riceve l'avanzamento PIENO, sempre: e' la meta' fine del
                # canale asimmetrico, e la plancia ci costruisce sopra il dettaglio del turno.
                self._sink.write(f"[PROGRESS{pct_str}] {event.text}\n")
                # La voce riceve la meta' grossolana, e non piu' di una ogni
                # PROGRESS_TTS_INTERVALLO_S. Prima questa chiamata era commentata con
                # «default is visual only»: una scelta ragionevole finche' NESSUN adapter
                # emetteva `Progress` — cioe' finche' la domanda non si poneva. Ora che
                # arriva, tacere del tutto lascerebbe senza il segnale «sta ancora
                # lavorando» proprio chi non ha lo schermo.
                adesso = time.monotonic()
                if event.text and adesso - self._ultimo_progress_parlato >= PROGRESS_TTS_INTERVALLO_S:
                    self._ultimo_progress_parlato = adesso
                    await self._to_tts(event, annuncio_grossolano(event.text))
                return True

            case Artifact():
                # INVARIANT: Artifact goes ONLY to the visual channel. Never to TTS (AC3).
                # _to_tts is not called in this branch by design.
                self._sink.write(f"[ARTIFACT kind={event.kind}]\n{event.content}\n")
                return True

            case Done():
                self._sink.write("[DONE]\n")
                return False

            case _:
                # Unknown type (future extension): discard silently with WARNING.
                log.warning(
                    "EventRouter: unknown event discarded: %s",
                    type(event).__name__,
                )
                return True

    async def _to_tts(self, event: RuntimeEvent, text: str) -> None:
        """
        Enqueue text to TTS only if the type is in TTS_ALLOWED.

        Defense in depth (AC5): if called with a type not in TTS_ALLOWED
        (e.g. due to a refactoring error), log WARNING and discard without enqueuing.
        This is the only path to tts_queue in the entire module.
        """
        if type(event) not in TTS_ALLOWED:
            log.warning(
                "EventRouter: non-spoken type discarded: %s",
                type(event).__name__,
            )
            return
        await self._tts_queue.put(text)

    def extract_spoken_summary(self, artifact_text: str) -> str | None:
        """
        Extract spoken summary from a markdown block if present.

        Supported patterns (in priority order):
          1. ```spoken\\n<text>\\n```
          2. <!-- spoken: <text> -->

        Used as syntactic fallback when the runtime produces mixed text not
        yet structured into typed events (US-145 §Syntactic separator contract,
        complementary Option A).

        Args:
            artifact_text: raw markdown text (unstructured LLM output).

        Returns:
            Extracted spoken text (stripped), or None if no pattern found.
        """
        m = _SPOKEN_FENCE_RE.search(artifact_text)
        if m:
            return m.group(1).strip() or None

        m = _SPOKEN_COMMENT_RE.search(artifact_text)
        if m:
            return m.group(1).strip() or None

        return None
