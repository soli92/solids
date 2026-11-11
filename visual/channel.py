"""Il canale visivo del contratto `FactoryRuntime` (US-280).

`wiki/concepts/voice-channel-factory.md` §Principio cardine elenca *Visivo
(schermo/editor/terminale)* come canale di pari rango, e l'invariante su `Artifact`
in §Interfaccia FactoryRuntime dichiara che il contenuto «raggiunga esclusivamente il
canale visivo (stdout strutturato in MVP)». Questo modulo sostituisce quella
parentesi: il canale smette di essere un segnaposto.

Il contratto NON si modifica. Qui si importa e si consuma; `git diff voice/` deve
restare vuoto in ogni TSK di questa epica.

INVARIANTE EREDITATA, nella direzione opposta: `Artifact.content` non esce mai da
qui verso un componente di sintesi vocale. Il canale audio ha un router che lo
impedisce a monte; questo canale non offre un percorso di ritorno. `tts_payload()`
esiste apposta per rendere la regola eseguibile invece che sperata, ed e' verificata
da un test di regressione.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from voice.runtime.factory_runtime import (
    Acknowledgment, Artifact, Done, Error, Progress, Question, SpokenSummary,
)

MAX_TIMELINE = 200

#: Tipi che il contratto instrada al canale visivo in modo esclusivo.
VISUAL_ONLY = (Artifact,)

#: Tipi che il contratto instrada (anche) al TTS.
SPEAKABLE = (Acknowledgment, SpokenSummary, Question, Error)


def kind_of(event: Any) -> str:
    return type(event).__name__.lower()


def tts_payload(event: Any) -> str | None:
    """Cosa di questo evento puo' essere pronunciato. `None` = nulla.

    Unico punto in cui il canale visivo decide cosa sarebbe legittimo passare al TTS.
    Per `Artifact` la risposta e' `None` **sempre**, e il test di regressione di
    US-280 fallisce se questa funzione ne restituisce il contenuto.
    """
    if isinstance(event, Artifact):
        return None
    if isinstance(event, SPEAKABLE):
        return getattr(event, "text", None) or getattr(event, "message", None)
    return None


@dataclass
class TurnState:
    """Stato osservabile di un turno, cosi' come lo vede lo schermo."""

    acknowledged_at: float | None = None
    acknowledgment: str | None = None
    progress: dict | None = None
    summary: str | None = None
    artifacts: list[dict] = field(default_factory=list)
    question: str | None = None
    error: str | None = None
    done: bool = False
    started_at: float = field(default_factory=time.time)

    @property
    def ack_latency_ms(self) -> float | None:
        if self.acknowledged_at is None:
            return None
        return round((self.acknowledged_at - self.started_at) * 1000, 1)

    @property
    def phase(self) -> str:
        if self.error:
            return "errore"
        if self.question:
            return "attesa-risposta"     # il gate umano: lo stato piu' importante
        if self.done:
            return "concluso"
        if self.progress or self.acknowledgment:
            return "in-lavorazione"
        return "inattivo"


class VisualChannel:
    """Consumatore dei sette `RuntimeEvent`. Thread-safe, senza I/O su disco."""

    def __init__(self, max_timeline: int = MAX_TIMELINE) -> None:
        self._lock = threading.Lock()
        self._turn = TurnState()
        self._timeline: deque[dict] = deque(maxlen=max_timeline)
        self._ultimo_a: float | None = None

    # -- ingestione -----------------------------------------------------------
    def consume(self, event: Any) -> dict:
        """Assorbe un evento e ne restituisce la resa visiva."""
        now = time.time()
        rendered: dict = {"kind": kind_of(event), "at": now, "speakable": tts_payload(event)}

        with self._lock:
            turn = self._turn
            if isinstance(event, Acknowledgment):
                turn.acknowledged_at = now
                turn.acknowledgment = event.text
                rendered["text"] = event.text

            elif isinstance(event, Progress):
                # pct=None -> avanzamento INDETERMINATO. Una barra ferma a zero direbbe
                # «nessun avanzamento», che e' un'altra cosa.
                turn.progress = {"text": event.text, "pct": event.pct,
                                 "indeterminate": event.pct is None}
                rendered.update(turn.progress)

            elif isinstance(event, SpokenSummary):
                turn.summary = event.text
                rendered["text"] = event.text

            elif isinstance(event, Artifact):
                item = {"kind": event.kind, "content": event.content, "at": now}
                turn.artifacts.append(item)
                rendered.update({"artifact_kind": event.kind, "content": event.content})
                rendered["speakable"] = None   # esplicito: non pronunciabile, mai

            elif isinstance(event, Question):
                turn.question = event.text
                rendered["text"] = event.text

            elif isinstance(event, Error):
                turn.error = event.message
                rendered["text"] = event.message

            elif isinstance(event, Done):
                turn.done = True

            else:
                rendered["kind"] = "sconosciuto"
                rendered["text"] = repr(event)

            self._timeline.append(rendered)
            self._ultimo_a = now
        return rendered

    def begin_turn(self) -> None:
        with self._lock:
            self._turn = TurnState()

    def answer_question(self) -> None:
        """Il gate e' stato sciolto. Wave C lo colleghera' a una `submit()`."""
        with self._lock:
            self._turn.question = None

    # -- osservazione ---------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            turn = self._turn
            return {
                "phase": turn.phase,
                "acknowledgment": turn.acknowledgment,
                "ack_latency_ms": turn.ack_latency_ms,
                "progress": turn.progress,
                "summary": turn.summary,
                "question": turn.question,
                "error": turn.error,
                "done": turn.done,
                "artifacts": list(turn.artifacts),
                "artifact_count": len(turn.artifacts),
                # Ritardo dichiarato: un canale indietro rispetto all'altro lo dice,
                # invece di mostrarsi aggiornato (US-295).
                "ritardo_s": None if self._ultimo_a is None else round(time.time() - self._ultimo_a, 2),
                "timeline": list(self._timeline)[-40:][::-1],
            }
