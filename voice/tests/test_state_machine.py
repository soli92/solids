"""voice/tests/test_state_machine.py — Test logica FSM handsfree (US-143..US-159).

Scenari testati (nessun hardware, nessun LLM):
  SM-1: stato iniziale IDLE + proprietà `state` come stringa
  SM-2: _transition() aggiorna lo stato e logga
  SM-3: _detect_voice_command() — keyword handsfree on/off, case-insensitive
  SM-4: _handle_voice_command() — aggiorna _handsfree_mode / _continuous_mode + TTS locale
  SM-5: _drain_queue() — conversione float32→PCM int16, mono, clip, empty queue
  TSK-396: FSM pickup post-shutdown consumer
    SC1: consumer morto durante CATTURA (PTT) → FSM ritorna a IDLE
    SC2: consumer morto durante CATTURA (continuous) → _continuous_mode resettato
    SC3: run_loop() recupera da eccezione in run_once() — reset a IDLE + continua

Framework: pytest + asyncio.run(). Nessun pytest-asyncio richiesto.
"""
from __future__ import annotations

import asyncio
import logging
import queue as _queue_module
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

import voice.core.state_machine as _sm_mod
from voice.config import VoiceConfig
from voice.core.state_machine import VoiceState, VoiceStateMachine, _drain_queue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    wake_word_enabled: bool = False,
    barge_in_enabled: bool = False,
) -> VoiceConfig:
    cfg = VoiceConfig()
    cfg.wake_word.enabled = wake_word_enabled
    cfg.wake_word.keyword = "prometeus"
    cfg.barge_in.enabled = barge_in_enabled
    return cfg


def _build_fsm(
    wake_word_enabled: bool = False,
    barge_in_enabled: bool = False,
) -> VoiceStateMachine:
    cfg = _make_config(wake_word_enabled=wake_word_enabled, barge_in_enabled=barge_in_enabled)
    capture = MagicMock()
    capture.queue = _queue_module.Queue()
    vad = MagicMock()
    vad.feed_frame.return_value = True
    stt = AsyncMock()
    tts = MagicMock()
    playback = MagicMock()
    runtime = MagicMock()
    router = MagicMock()
    router.route = AsyncMock(return_value=False)
    return VoiceStateMachine(
        config=cfg,
        capture=capture,
        vad=vad,
        stt=stt,
        tts=tts,
        playback=playback,
        runtime=runtime,
        router=router,
    )


# ===========================================================================
# SM-1: initial state
# ===========================================================================


class TestInitialState:
    def test_initial_state_is_idle(self):
        fsm = _build_fsm()
        assert fsm.state == "IDLE"

    def test_state_property_returns_string(self):
        fsm = _build_fsm()
        assert isinstance(fsm.state, str)

    def test_handsfree_mode_off_by_default(self):
        fsm = _build_fsm()
        assert fsm._handsfree_mode is False

    def test_continuous_mode_off_by_default(self):
        fsm = _build_fsm()
        assert fsm._continuous_mode is False

    def test_skip_next_utterance_false_by_default(self):
        fsm = _build_fsm()
        assert fsm._skip_next_utterance is False


# ===========================================================================
# SM-2: _transition
# ===========================================================================


class TestTransition:
    def test_transition_changes_state(self):
        fsm = _build_fsm()
        fsm._transition(VoiceState.CATTURA, trigger="test")
        assert fsm.state == "CATTURA"

    def test_transition_through_all_states(self):
        fsm = _build_fsm()
        for target, trigger in [
            (VoiceState.CATTURA, "start"),
            (VoiceState.TRASCRIZIONE, "vad"),
            (VoiceState.ELABORAZIONE, "stt"),
            (VoiceState.PARLATO, "llm"),
            (VoiceState.IDLE, "done"),
        ]:
            fsm._transition(target, trigger=trigger)
            assert fsm.state == target.value

    def test_transition_logs_info(self, caplog):
        fsm = _build_fsm()
        with caplog.at_level(logging.INFO, logger="voice.core.state_machine"):
            fsm._transition(VoiceState.CATTURA, trigger="test_trigger")
        assert any("IDLE" in r.message and "CATTURA" in r.message for r in caplog.records)


# ===========================================================================
# SM-3: _detect_voice_command — keyword matching
# ===========================================================================


class TestDetectVoiceCommand:
    def test_handsfree_keyword_detected(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("handsfree") == "handsfree_on"

    def test_mani_libere_keyword_detected(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("attiva mani libere ora") == "handsfree_on"

    def test_disattiva_handsfree_detected(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("disattiva handsfree") == "handsfree_off"

    def test_modalita_normale_detected(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("torna in modalità normale") == "handsfree_off"

    def test_handsfree_on_case_insensitive(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("HANDSFREE") == "handsfree_on"

    def test_no_keyword_returns_none(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("apri il kanban sprint 47") is None

    def test_partial_match_inside_sentence(self):
        fsm = _build_fsm()
        result = fsm._detect_voice_command("per favore attiva il modo handsfree adesso")
        assert result == "handsfree_on"

    def test_empty_string_returns_none(self):
        fsm = _build_fsm()
        assert fsm._detect_voice_command("") is None


# ===========================================================================
# SM-4: _handle_voice_command — updates mode + local TTS
# ===========================================================================


def _run(coro):
    return asyncio.run(coro)


class TestHandleVoiceCommand:
    def test_handsfree_on_sets_flags(self):
        fsm = _build_fsm()
        fsm._tts.synthesize.return_value = np.zeros(100, dtype=np.float32)
        _run(fsm._handle_voice_command("handsfree_on", tts_sr=22050))
        assert fsm._handsfree_mode is True
        assert fsm._continuous_mode is True

    def test_handsfree_off_clears_flag(self):
        fsm = _build_fsm()
        fsm._handsfree_mode = True
        fsm._continuous_mode = True
        fsm._tts.synthesize.return_value = np.zeros(100, dtype=np.float32)
        _run(fsm._handle_voice_command("handsfree_off", tts_sr=22050))
        assert fsm._handsfree_mode is False

    def test_handsfree_on_calls_tts_synthesize(self):
        fsm = _build_fsm()
        fsm._tts.synthesize.return_value = np.zeros(100, dtype=np.float32)
        _run(fsm._handle_voice_command("handsfree_on", tts_sr=22050))
        fsm._tts.synthesize.assert_called_once()
        call_text = fsm._tts.synthesize.call_args[0][0]
        assert "handsfree" in call_text.lower() or "mani libere" in call_text.lower()

    def test_unknown_command_is_no_op(self):
        fsm = _build_fsm()
        _run(fsm._handle_voice_command("comando_sconosciuto", tts_sr=22050))
        fsm._tts.synthesize.assert_not_called()

    def test_tts_exception_does_not_propagate(self):
        """Errore TTS in handle_voice_command non deve far esplodere la FSM."""
        fsm = _build_fsm()
        fsm._tts.synthesize.side_effect = RuntimeError("piper not found")
        _run(fsm._handle_voice_command("handsfree_on", tts_sr=22050))
        # Must not raise — FSM remains stable
        assert fsm._handsfree_mode is True


# ===========================================================================
# SM-5: _drain_queue — conversione float32→PCM int16
# ===========================================================================


class TestDrainQueue:
    def test_empty_queue_returns_empty_bytes(self):
        q = _queue_module.Queue()
        result = _drain_queue(q)
        assert result == b""

    def test_single_frame_produces_pcm_bytes(self):
        q = _queue_module.Queue()
        frame = np.zeros((160, 1), dtype=np.float32)
        frame[0, 0] = 0.5
        q.put(frame)
        result = _drain_queue(q)
        assert len(result) > 0
        assert len(result) % 2 == 0  # PCM int16: 2 bytes per sample

    def test_multiple_frames_concatenated(self):
        q = _queue_module.Queue()
        for _ in range(3):
            q.put(np.zeros((160, 1), dtype=np.float32))
        result = _drain_queue(q)
        # 3 frame × 160 campioni × 2 byte = 960 byte
        assert len(result) == 3 * 160 * 2

    def test_multichannel_frame_converted_to_mono(self):
        """2-channel frame → only channel 0 is used."""
        q = _queue_module.Queue()
        frame = np.zeros((160, 2), dtype=np.float32)
        frame[:, 0] = 0.5   # channel 0: signal
        frame[:, 1] = -1.0  # channel 1: anti-signal (if not discarded, alters sum)
        q.put(frame)
        result = _drain_queue(q)
        samples = np.frombuffer(result, dtype=np.int16)
        # All samples > 0 (channel 0 = 0.5 > 0; if channel 1 used they would be < 0)
        assert np.all(samples > 0)

    def test_clipping_at_plus_one(self):
        """Valori float32 > 1.0 vengono clippati a int16 max (32767)."""
        q = _queue_module.Queue()
        frame = np.full((1, 1), 2.0, dtype=np.float32)  # out of range
        q.put(frame)
        result = _drain_queue(q)
        sample = np.frombuffer(result, dtype=np.int16)[0]
        assert sample == 32767

    def test_clipping_at_minus_one(self):
        """Valori float32 < -1.0 vengono clippati a int16 min (-32767)."""
        q = _queue_module.Queue()
        frame = np.full((1, 1), -2.0, dtype=np.float32)
        q.put(frame)
        result = _drain_queue(q)
        sample = np.frombuffer(result, dtype=np.int16)[0]
        assert sample == -32767

    def test_silence_frame_produces_zero_pcm(self):
        """Silent frame → all PCM samples = 0."""
        q = _queue_module.Queue()
        q.put(np.zeros((256, 1), dtype=np.float32))
        result = _drain_queue(q)
        samples = np.frombuffer(result, dtype=np.int16)
        assert np.all(samples == 0)

    def test_queue_drained_completely(self):
        """After _drain_queue the queue must be empty."""
        q = _queue_module.Queue()
        for _ in range(5):
            q.put(np.zeros((160, 1), dtype=np.float32))
        _drain_queue(q)
        assert q.empty()


# ===========================================================================
# TSK-396: FSM liveness check in CATTURA + reset continuous mode post-shutdown
# ===========================================================================


def _build_fsm_with_dead_consumer(
    continuous_mode: bool = False,
) -> VoiceStateMachine:
    """Helper: FSM con consumer morto (is_consumer_alive=False)."""
    cfg = _make_config(wake_word_enabled=False, barge_in_enabled=False)
    capture = MagicMock()
    capture.queue = _queue_module.Queue()  # empty queue, no frames needed
    vad = MagicMock()
    vad.reset.return_value = None
    vad.feed_frame.return_value = True
    vad.speech_started = True
    stt = AsyncMock()
    stt.transcribe.return_value = "test utterance"
    tts = MagicMock()
    tts.synthesize.return_value = np.zeros(1, dtype=np.float32)
    playback = MagicMock()
    runtime = MagicMock()
    runtime.is_consumer_alive.return_value = False  # consumer morto
    runtime.aclose = AsyncMock()
    router = MagicMock()
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
    fsm._continuous_mode = continuous_mode
    return fsm


class TestTSK396LivenessFix:
    """TSK-396 — Fix FSM pickup post-shutdown consumer.

    Verifica i tre change implementati in state_machine.py:
      SC1: liveness check periodico in CATTURA → FSM ritorna a IDLE (DoD).
      SC2: consumer morto in CATTURA con continuous mode → _continuous_mode reset.
      SC3: eccezione in run_once() → run_loop() recupera, resetta IDLE, continua.
    """

    def test_sc1_cattura_dead_consumer_returns_idle(self, monkeypatch):
        """SC1 (DoD): consumer termina durante CATTURA → FSM ritorna a IDLE.

        Con _CATTURA_LIVENESS_INTERVAL_S=0.0 il check scatta al primo ciclo
        del loop CATTURA (prima ancora di invocare queue.get o VAD).
        Risultato atteso: FSM transita a IDLE senza completare STT.
        """
        monkeypatch.setattr(_sm_mod, "_CATTURA_LIVENESS_INTERVAL_S", 0.0)

        async def _run():
            fsm = _build_fsm_with_dead_consumer(continuous_mode=False)
            # PTT: mock input() to exit wait immediately
            with patch("builtins.input", return_value=""), \
                 patch.object(fsm, "_speak_feedback", AsyncMock()):
                await fsm.run_once()
            return fsm.state, fsm._runtime.is_consumer_alive.called

        state, alive_called = asyncio.run(_run())

        assert state == "IDLE", (
            f"SC1 FAIL: atteso stato IDLE dopo consumer morto in CATTURA, "
            f"trovato {state!r}"
        )
        assert alive_called, (
            "SC1 FAIL: is_consumer_alive() non è stato invocato durante CATTURA"
        )

    def test_sc2_cattura_dead_consumer_resets_continuous_mode(self, monkeypatch):
        """SC2: consumer morto durante CATTURA in continuous mode → _continuous_mode=False.

        Fix del busy-loop post-shutdown (TSK-396): senza reset, il prossimo
        run_once() rientra immediatamente in CATTURA → loop infinito «Nessuna sessione».
        """
        monkeypatch.setattr(_sm_mod, "_CATTURA_LIVENESS_INTERVAL_S", 0.0)

        async def _run():
            fsm = _build_fsm_with_dead_consumer(continuous_mode=True)
            # Continuous mode: asyncio.sleep(1.0) e _speak_feedback vengono
            # patched to avoid blocking the test.
            with patch("asyncio.sleep", AsyncMock()), \
                 patch.object(fsm, "_speak_feedback", AsyncMock()):
                await fsm.run_once()
            return fsm.state, fsm._continuous_mode

        state, cont_mode = asyncio.run(_run())

        assert state == "IDLE", (
            f"SC2 FAIL: atteso IDLE, trovato {state!r}"
        )
        assert cont_mode is False, (
            "SC2 FAIL: _continuous_mode deve essere False dopo consumer morto in CATTURA "
            "(fix busy-loop TSK-396); ancora True — il pickup post-shutdown è ancora attivo"
        )

    def test_sc3_run_loop_recovers_from_exception(self):
        """SC3: eccezione inattesa in run_once() → run_loop() resetta IDLE e continua.

        Simula: primo run_once() lancia RuntimeError (es. OSError audio),
        secondo run_once() lancia KeyboardInterrupt (shutdown nominale).
        Atteso: stato IDLE dopo il recovery, run_loop() termina senza propagare errori.
        """
        async def _run():
            fsm = _build_fsm_with_dead_consumer(continuous_mode=False)

            call_count = [0]

            async def _mock_run_once():
                call_count[0] += 1
                if call_count[0] == 1:
                    # Simulate exception in CATTURA path (e.g. OSError on AudioCapture)
                    fsm._state = VoiceState.ELABORAZIONE  # stuck non-IDLE pre-fix
                    raise RuntimeError("simulated audio hardware error")
                # Secondo giro: shutdown nominale
                raise KeyboardInterrupt

            with patch.object(fsm, "run_once", side_effect=_mock_run_once):
                await fsm.run_loop()

            return fsm.state, call_count[0]

        state, calls = asyncio.run(_run())

        assert state == "IDLE", (
            f"SC3 FAIL: atteso IDLE dopo exception recovery in run_loop(), "
            f"trovato {state!r} — la FSM è rimasta bloccata in stato non-IDLE"
        )
        assert calls == 2, (
            f"SC3 FAIL: attesi 2 call a run_once() (1 eccezione + 1 KeyboardInterrupt), "
            f"trovati {calls} — il loop non ha ripreso dopo l'eccezione"
        )
