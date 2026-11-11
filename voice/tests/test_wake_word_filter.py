"""voice/tests/test_wake_word_filter.py — Test filtro wake-word post-attivazione (TSK-338).

Scenari:
  1. Trascritto simile alla wake word → scartato (AC2)
  2. Trascritto comando reale → inoltrato a runtime.submit (AC3)
  3. Log DEBUG contiene testo scartato e distanza Levenshtein (AC4)
  4. Correttezza di levenshtein() su tre casi limite (AC - funzione)
  5. No-op quando _skip_next_utterance=False → inoltro normale (AC6)

Framework: pytest + unittest.mock.AsyncMock / MagicMock.
Non avvia hardware audio: test unitari sulla logica FSM in isolamento.
Le dipendenze I/O (input da stdin, playback HW) vengono patched via asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import logging
import queue as _queue_module
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from voice.config import VoiceConfig
from voice.core.state_machine import VoiceStateMachine
from voice.vad.wake_word import levenshtein


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(keyword: str = "prometeus", filter_threshold: int = 3) -> VoiceConfig:
    """Config minimale PTT (no wake-word hardware, no barge-in) per i test."""
    cfg = VoiceConfig()
    cfg.wake_word.keyword = keyword
    cfg.wake_word.filter_threshold = filter_threshold
    cfg.wake_word.enabled = False  # PTT: salta il detector hardware in IDLE
    cfg.barge_in.enabled = False
    return cfg


def _build_fsm(
    keyword: str = "prometeus",
    filter_threshold: int = 3,
) -> tuple[VoiceStateMachine, MagicMock, AsyncMock, MagicMock]:
    """
    Istanzia VoiceStateMachine con tutte le dipendenze iniettate come mock.

    Returns:
        (fsm, capture, stt, runtime)
    """
    cfg = _make_config(keyword=keyword, filter_threshold=filter_threshold)

    capture = MagicMock()
    capture.queue = _queue_module.Queue()

    vad = MagicMock()
    # feed_frame returns True on first frame: immediate VAD endpoint,
    # CATTURA loop exits after single frame without waiting for real silence.
    vad.feed_frame.return_value = True

    stt: AsyncMock = AsyncMock()
    tts = MagicMock()
    playback = MagicMock()
    runtime = MagicMock()

    router = MagicMock()
    # route returns False → runtime event-loop exits immediately (Done semantics)
    router.route = AsyncMock(return_value=False)

    fsm = VoiceStateMachine(
        config=cfg,
        capture=capture,
        vad=vad,
        stt=stt,
        tts=tts,
        playback=playback,
        runtime=runtime,
        router=router,
    )
    return fsm, capture, stt, runtime


async def _empty_async_gen(*args, **kwargs):
    """Async generator vuoto: simula runtime.submit senza eventi TTS prodotti."""
    return
    yield  # pragma: no cover — rende la funzione un async generator


def _put_audio_frame(q: _queue_module.Queue) -> None:
    """Inserisce un frame audio sintetico nella queue (evita ramo 'nessun audio').

    Shape (512, 1) float32, energia non-zero perché il VAD RMS gate
    richiede un segnale > 0.
    """
    frame = np.zeros((512, 1), dtype=np.float32)
    frame[0, 0] = 0.1
    q.put(frame)


async def _run_once_patched(fsm: VoiceStateMachine, transcript: str) -> None:
    """
    Esegue run_once() con patch minimali per evitare I/O bloccante e hardware.

    Patch:
      - asyncio.to_thread → no-op async (bypassa input() da stdin e playback HW)
      - stt.transcribe → AsyncMock che restituisce `transcript`

    Il frame audio sintetico inserito nella queue prima della chiamata garantisce
    che captured_frames non sia vuota e audio_bytes sia non-empty.

    Il runtime.submit deve essere configurato prima di chiamare questa funzione.
    """
    _put_audio_frame(fsm._capture.queue)
    fsm._stt.transcribe.return_value = transcript

    async def _noop_to_thread(func, *args, **kwargs):
        """Sostituisce asyncio.to_thread: ritorna None senza eseguire il callable."""
        return None

    with patch("asyncio.to_thread", new=_noop_to_thread):
        await fsm.run_once()


# ---------------------------------------------------------------------------
# Test 1 — Trascritto wake-word scartato (AC2)
# ---------------------------------------------------------------------------


def test_wake_word_utterance_scartata():
    """
    AC2: con _skip_next_utterance=True e trascritto == wake word (distanza 0 < threshold 3),
    runtime.submit NON viene chiamato e il flag viene resettato a False.
    """
    fsm, _capture, _stt, runtime = _build_fsm()

    # Simulate moment right after wake_word_detected (TSK-335)
    fsm._skip_next_utterance = True

    runtime.submit = MagicMock(side_effect=lambda *a, **kw: _empty_async_gen())

    asyncio.run(_run_once_patched(fsm, "prometeus"))

    runtime.submit.assert_not_called()
    assert fsm._skip_next_utterance is False, (
        "_skip_next_utterance deve essere resettato a False dopo il filtro"
    )


# ---------------------------------------------------------------------------
# Test 2 — Trascritto comando reale inoltrato (AC3)
# ---------------------------------------------------------------------------


def test_comando_reale_inoltrato():
    """
    AC3: con _skip_next_utterance=True ma trascritto distante (distanza >> threshold),
    runtime.submit VIENE chiamato con il testo trascritto e il flag viene resettato.
    """
    fsm, _capture, _stt, runtime = _build_fsm()
    fsm._skip_next_utterance = True

    submit_calls: list[tuple[str, str]] = []

    async def _tracking_gen(text: str, session_id: str):
        submit_calls.append((text, session_id))
        return
        yield  # pragma: no cover

    runtime.submit = MagicMock(side_effect=lambda *a, **kw: _tracking_gen(*a, **kw))

    asyncio.run(_run_once_patched(fsm, "apri il kanban"))

    assert len(submit_calls) == 1, (
        "runtime.submit deve essere chiamato esattamente una volta"
    )
    assert submit_calls[0][0] == "apri il kanban", (
        "runtime.submit deve ricevere il testo trascritto originale"
    )
    assert fsm._skip_next_utterance is False, (
        "_skip_next_utterance deve essere resettato anche quando il testo è inoltrato"
    )


# ---------------------------------------------------------------------------
# Test 3 — DEBUG log with discarded text and distance (AC4)
# ---------------------------------------------------------------------------


def test_log_debug_distanza(caplog: pytest.LogCaptureFixture):
    """
    AC4: quando il trascritto viene scartato, il log DEBUG riporta il testo
    scartato e il valore di distanza Levenshtein calcolato.

    Il logger atteso è 'voice.core.state_machine' (log = logging.getLogger(__name__)).
    Il messaggio atteso è: "Wake-word utterance scartata: 'prometeus' (distanza Levenshtein=0)"
    """
    fsm, _capture, _stt, runtime = _build_fsm()
    fsm._skip_next_utterance = True
    runtime.submit = MagicMock(side_effect=lambda *a, **kw: _empty_async_gen())

    with caplog.at_level(logging.DEBUG, logger="voice.core.state_machine"):
        asyncio.run(_run_once_patched(fsm, "prometeus"))

    assert "prometeus" in caplog.text, (
        "Il log DEBUG deve contenere il testo scartato ('prometeus')"
    )
    assert "Levenshtein=0" in caplog.text, (
        "Il log DEBUG deve contenere la distanza calcolata (0 per stringa identica)"
    )


# ---------------------------------------------------------------------------
# Test 4 — Correttezza levenshtein()
# ---------------------------------------------------------------------------


def test_levenshtein_correttezza():
    """
    Verifica la correttezza di levenshtein() per i tre casi documentati nel DoD di TSK-336:
      - stringa identica → distanza 0
      - un carattere aggiunto ('prometheus' vs 'prometeus') → distanza 1
      - testo completamente diverso → distanza > threshold (3)
    """
    assert levenshtein("prometeus", "prometeus") == 0
    assert levenshtein("prometeus", "prometheus") == 1
    assert levenshtein("apri il kanban", "prometeus") > 3


# ---------------------------------------------------------------------------
# Test 5 — No-op senza wake word (AC6)
# ---------------------------------------------------------------------------


def test_no_op_senza_wake_word():
    """
    AC6: quando _skip_next_utterance=False (default, nessuna attivazione wake word),
    il filtro è un no-op trasparente: runtime.submit viene chiamato normalmente
    per qualsiasi testo, indipendentemente dalla distanza dalla wake word.
    """
    fsm, _capture, _stt, runtime = _build_fsm()

    # Verify flag is False by default (never activated)
    assert fsm._skip_next_utterance is False

    submit_calls: list[tuple[str, str]] = []

    async def _tracking_gen(text: str, session_id: str):
        submit_calls.append((text, session_id))
        return
        yield  # pragma: no cover

    runtime.submit = MagicMock(side_effect=lambda *a, **kw: _tracking_gen(*a, **kw))

    asyncio.run(_run_once_patched(fsm, "qualsiasi comando"))

    assert len(submit_calls) == 1, (
        "runtime.submit deve essere chiamato anche senza attivazione wake word"
    )
    assert submit_calls[0][0] == "qualsiasi comando"
