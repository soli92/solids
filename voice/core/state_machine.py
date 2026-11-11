"""
voice/core/state_machine.py — Main FSM: Phase 1/3 push-to-talk cycle.

5 states: IDLE → CATTURA → TRASCRIZIONE → ELABORAZIONE → PARLATO → IDLE
         (Phase 3, US-144 AC2d) PARLATO → CATTURA on confirmed barge-in.
Every transition is logged (US-143 AC2).

In Phase 1 capture ends on INVIO key release (sequential,
no automatic endpointing and no barge-in — deferred to US-144).

In Phase 3 (barge_in.enabled = true) the PARLATO state launches two
concurrent asyncio tasks: playback_task (TTS) and detector_task (BargeinDetector).
On barge-in confirmation: cancel_turn() + PARLATO → CATTURA transition.

Type hierarchy:
  VoiceState          — enum of the 5 states
  VoiceStateMachine   — FSM with constructor dependency injection
  VoiceFSM            — alias (orchestrator spec compatibility)
"""
from __future__ import annotations

import asyncio
import logging
import queue as _queue_module
import time
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

from voice.core.session import VoiceSessionManager
from voice.core.side_channel import atomic_write_json, STATE_FILE, INBOX, SCHEMA_VERSION
from voice.runtime.factory_runtime import Acknowledgment, Done, Error, SpokenSummary

# levenshtein: imported from voice.vad.wake_word (TSK-336).
# If the symbol is not yet available (TSK-336 not yet executed),
# use the inline fallback implementation.
try:
    from voice.vad.wake_word import levenshtein  # type: ignore[attr-defined]
except ImportError:

    def levenshtein(s1: str, s2: str) -> int:  # type: ignore[misc]
        """Levenshtein distance (inline fallback — replaced by TSK-336)."""
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        if not s2:
            return len(s1)
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
            prev = curr
        return prev[-1]


if TYPE_CHECKING:
    from voice.audio.capture import AudioCapture
    from voice.audio.playback import AudioPlayback
    from voice.config import VoiceConfig
    from voice.core.router import EventRouter
    from voice.runtime.factory_runtime import FactoryRuntime
    from voice.stt.base import BaseSTT
    from voice.tts.base import TTSBase
    from voice.vad.endpointing import Endpointer
    from voice.vad.wake_word import WakeWordDetector

log = logging.getLogger(__name__)

# Interval (seconds) for liveness check during the CATTURA loop (TSK-396).
# Conservative value: ensures detection within consumer_alive_ttl_s (10s) + 5s
# in the worst case, without significant overhead on the VAD loop.
_CATTURA_LIVENESS_INTERVAL_S: float = 5.0


# ---------------------------------------------------------------------------
# FSM state enum (US-143 AC2)
# ---------------------------------------------------------------------------

class VoiceState(Enum):
    """Five states of the push-to-talk cycle (US-143 AC2)."""
    IDLE = "IDLE"
    CATTURA = "CATTURA"
    TRASCRIZIONE = "TRASCRIZIONE"
    ELABORAZIONE = "ELABORAZIONE"
    PARLATO = "PARLATO"


# ---------------------------------------------------------------------------
# Helper: drain audio frame queue and return PCM int16 bytes
# ---------------------------------------------------------------------------

def _drain_queue(q: "_queue_module.Queue") -> bytes:
    """Drain all float32 frames from AudioCapture.queue.

    Each frame in the queue is a numpy float32 array of shape (blocksize, channels).
    Concatenates along axis 0, takes the first channel (mono) and converts to
    PCM int16 little-endian — format expected by BaseSTT.transcribe.

    Returns:
        PCM int16 audio bytes. Empty bytes if the queue is already empty.
    """
    frames = []
    while True:
        try:
            frame = q.get_nowait()
            frames.append(frame)
        except _queue_module.Empty:
            break

    if not frames:
        return b""

    audio = np.concatenate(frames, axis=0)
    # Flatten to mono: take the first channel if multi-channel
    if audio.ndim > 1:
        audio = audio[:, 0]
    # float32 [-1.0, 1.0] → int16 [-32768, 32767]
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    return audio_int16.tobytes()


# ---------------------------------------------------------------------------
# VoiceStateMachine
# ---------------------------------------------------------------------------

class VoiceStateMachine:
    """
    Phase 1 push-to-talk FSM: sequential cycle
    IDLE → CATTURA → TRASCRIZIONE → ELABORAZIONE → PARLATO → IDLE.

    All dependencies are injected in the constructor; run_once() runs
    one full turn using stored components. run_loop() calls
    run_once() in a loop until KeyboardInterrupt.

    DoD compatibility (US-143 AC2):
      - ``state`` attribute of type str: returns the string name of the
        current state ('IDLE', 'CATTURA', 'TRASCRIZIONE', 'ELABORAZIONE', 'PARLATO').
      - run_turn(capture, stt, runtime, router, tts, playback, config) — DoD
        signature; wrapper that temporarily overrides dependencies and calls
        run_once().

    Barge-in note (Phase 3, TSK-300):
      _cancellation_requested is an asyncio.Event settable from outside to
      signal barge-in. In Phase 1 it is never set (CancelToken no-op).
    """

    def __init__(
        self,
        config: "VoiceConfig",
        capture: "AudioCapture",
        vad: "Endpointer",
        stt: "BaseSTT",
        tts: "TTSBase",
        playback: "AudioPlayback",
        runtime: "FactoryRuntime",
        router: "EventRouter",
        wake_word_detector: "WakeWordDetector | None" = None,
    ) -> None:
        self._config = config
        self._capture = capture
        self._vad = vad
        self._stt = stt
        self._tts = tts
        self._playback = playback
        self._runtime = runtime
        self._router = router
        self._wake_word_detector = wake_word_detector
        self._state: VoiceState = VoiceState.IDLE
        # True after first wake word activation: automatically listens again
        # after each TTS response (continuous conversation), no wake word required.
        self._continuous_mode: bool = False
        # True when activated by voice ("handsfree"): no wake word for
        # the entire session; _continuous_mode is never reset to False.
        self._handsfree_mode: bool = False
        # Length in characters of the last spoken TTS text.
        # Used to compute dynamic post-TTS cooldown (speaker echo).
        self._last_tts_chars: int = 0
        # Set to True in the wake_word_detected branch: filters the first transcript
        # that resembles the wake word (US-156, TSK-335). Always False in PTT/continuous
        # without wake word — the check in the TRASCRIZIONE branch is a transparent no-op (AC6).
        self._skip_next_utterance: bool = False
        # Set from outside for barge-in (Phase 3, TSK-300). No-op in Phase 1.
        self._cancellation_requested: asyncio.Event = asyncio.Event()
        # US-166 invariant flag (TSK-368): True during tts_chunks playback.
        # Blocks transition to CATTURA until TTS completes (AC3).
        # _speak_feedback() is NOT covered by this flag (constraint D4).
        self._tts_playing: bool = False
        self._tts_playing_since: float = 0.0
        # CATTURA entry timestamp and speech-onset flag (US-168, TSK-376).
        # _cattura_start: re-initialized on CATTURA entry (including via barge-in).
        # _speech_onset:  True when VAD has detected at least one speech frame;
        #                 disables onset_timeout check for the rest of the turn.
        self._cattura_start: float = 0.0
        self._speech_onset: bool = False
        # Session-owner seam (US-170 EP-046): no-op in the current implementation.
        self._session_manager = VoiceSessionManager()

    # ------------------------------------------------------------------
    # Voice feedback TTS (replaces beep — US-160 revision)
    # ------------------------------------------------------------------

    async def _speak_feedback(self, text: str, sr: int = 22050) -> None:
        """Synthesize and play a status phrase via TTS + afplay.

        Replaces sinusoidal beeps with spoken phrases (e.g. 'Sono in ascolto',
        'Ok, elaboro') to avoid Bluetooth startup latency issues:
        a TTS phrase is long enough to survive BT warmup (~300ms).
        Uses afplay (CoreAudio) on macOS for wireless headset compatibility.
        """
        try:
            synth = await asyncio.to_thread(self._tts.synthesize, text)
            from voice.audio.beep import play_beep as _pb  # noqa: PLC0415
            await _pb(synth, sr)
        except Exception as exc:  # noqa: BLE001
            log.warning("FSM: feedback vocale %r non riprodotto: %s", text, exc)

    # ------------------------------------------------------------------
    # Public property: state as string (DoD US-143 AC2)
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        """Current state as string ('IDLE', 'CATTURA', ...)."""
        return self._state.value

    # ------------------------------------------------------------------
    # Internal transition with logging
    # ------------------------------------------------------------------

    def _transition(self, new_state: VoiceState, trigger: str) -> None:
        """Perform a state transition and log (US-143 AC2).

        Formato log: ``FSM: {from} → {to} (trigger: {trigger})``
        Also writes to voice-state.json for visual feedback in file-pipe sessions.
        """
        log.info(
            "FSM: %s → %s (trigger: %s)",
            self._state.value,
            new_state.value,
            trigger,
        )
        self._state = new_state
        self._write_state_update(trigger)

    def _write_state_update(self, trigger: str, context: "dict | None" = None) -> None:
        # write-only — voice-state.json is external observability. NEVER re-read
        # to restore FSM state on restart. Init always forces IDLE (invariant C1).
        import time as _time  # noqa: PLC0415
        payload: dict = {"state": self._state.value, "trigger": trigger, "ts": _time.time()}
        if context:
            payload.update(context)
        try:
            atomic_write_json(STATE_FILE, payload)
        except Exception as exc:  # noqa: BLE001
            log.debug("FSM: voice-state.json write failed: %s", exc)

    def _write_utterance_log(self, text: str) -> None:
        """Write the transcribed utterance to voice-in.json for chat visibility."""
        import time as _time  # noqa: PLC0415
        import uuid as _uuid  # noqa: PLC0415
        try:
            atomic_write_json(INBOX, {
                "id": str(_uuid.uuid4())[:8],
                "text": text,
                "ts": _time.time(),
                "schema_version": SCHEMA_VERSION,
            })
        except Exception as exc:  # noqa: BLE001
            log.debug("FSM: voice-in.json write failed: %s", exc)

    # ------------------------------------------------------------------
    # run_once: one full IDLE→IDLE cycle
    # ------------------------------------------------------------------

    async def run_once(self) -> None:
        """Run ONE full cycle IDLE→CATTURA→TRASCRIZIONE→ELABORAZIONE→PARLATO→IDLE.

        Phase 1 (sequential push-to-talk):
          1. IDLE: wait for INVIO key press
          2. CATTURA: start capture; wait for INVIO release
          3. TRASCRIZIONE: stop capture; drain queue; transcribe via STT
          4. ELABORAZIONE: consume runtime event stream; accumulate TTS text
          5. PARLATO: synthesize and play each accumulated TTS chunk
          6. IDLE: turn completed

        Empty turns (no audio or empty transcription) are skipped with
        warning log and direct return to IDLE.
        """
        from voice.core.session import new_session  # lazy import (avoids circular)

        session = new_session()
        sr: int = 16000                        # samplerate Fase 1 (fixed)
        tts_sr: int = 22050                    # samplerate output piper-tts
        self._last_tts_chars = 0               # reset for this turn (correct cooldown)

        # Ensure start from IDLE (defensive guard)
        if self._state != VoiceState.IDLE:
            log.warning(
                "FSM: run_once invocato in stato %s; reset forzato a IDLE",
                self._state.value,
            )
            self._state = VoiceState.IDLE

        # ---------------------------------------------------------------
        # Watchdog tts_playing (US-166, TSK-368): reset flag if TTS remained
        # stuck beyond safety threshold (config.tts.playing_watchdog_s).
        # Prevents permanent starvation of the IDLE→CATTURA cycle in case of
        # unhandled exception in the PARLATO path.
        # ---------------------------------------------------------------
        if (self._tts_playing and
                time.monotonic() - self._tts_playing_since > self._config.tts.playing_watchdog_s):
            log.warning(
                "watchdog tts_playing scattato dopo %ds — reset flag",
                self._config.tts.playing_watchdog_s,
            )
            self._tts_playing = False

        # ---------------------------------------------------------------
        # [1] IDLE — wait: continuous conversation | wake word | PTT
        # ---------------------------------------------------------------
        if self._continuous_mode:
            # US-166 invariant gate (TSK-368, AC5): block CATTURA if TTS in progress.
            if self._tts_playing:
                log.warning("transizione a CATTURA bloccata: TTS in riproduzione")
                return
            await asyncio.sleep(1.0)              # fixed post-TTS cooldown (device-name heuristic removed AC5)
            _drain_queue(self._capture.queue)     # flush residual echo
            await self._speak_feedback("Sono in ascolto.", tts_sr)
            if self._handsfree_mode:
                print("\r🔊 Handsfree — parla pure")
            else:
                print("\r💬 Pronti — parla pure")
            self._transition(
                VoiceState.CATTURA,
                trigger="handsfree" if self._handsfree_mode else "conversazione_continua",
            )

        elif self._config.wake_word.enabled and self._wake_word_detector is not None:
            log.info(
                "FSM: in attesa (pronuncia '%s' per iniziare)...",
                self._config.wake_word.keyword,
            )
            self._capture.start()
            # Drain PortAudio startup buffer and wait 800ms before listening:
            # the first frames after start() often contain click/echo artifacts
            # that exceed the RMS gate and trigger a spurious wake-word match.
            _drain_queue(self._capture.queue)
            await asyncio.sleep(0.8)
            _drain_queue(self._capture.queue)
            try:
                await self._wake_word_detector.wait_for_wake_word(self._capture)
            finally:
                self._capture.stop()
                _drain_queue(self._capture.queue)

            print("\r🎤 Sto ascoltando...")
            await self._speak_feedback("Sono in ascolto.", tts_sr)

            # ---------------------------------------------------------------
            # [2] IDLE → CATTURA (wake word)
            # ---------------------------------------------------------------
            # US-166 invariant gate (TSK-368): block CATTURA if TTS in progress.
            if self._tts_playing:
                log.warning("transizione a CATTURA bloccata: TTS in riproduzione")
                return
            self._transition(VoiceState.CATTURA, trigger="wake_word_detected")
            # First turn after wake word: filter the wake word itself if captured
            # as utterance (US-156, TSK-335). Automatic reset in TRASCRIZIONE branch.
            self._skip_next_utterance = True
            self._continuous_mode = True  # continuous conversation mode active

        else:
            log.info("FSM: in attesa (premi INVIO per iniziare a parlare)...")
            try:
                await asyncio.to_thread(input, "")
            except EOFError:
                pass
            # ---------------------------------------------------------------
            # [2] IDLE → CATTURA (PTT)
            # ---------------------------------------------------------------
            # US-166 invariant gate (TSK-368): block CATTURA if TTS in progress.
            if self._tts_playing:
                log.warning("transizione a CATTURA bloccata: TTS in riproduzione")
                return
            self._transition(VoiceState.CATTURA, trigger="INVIO_premuto")

        # ---------------------------------------------------------------
        # CATTURA: automatic VAD endpointing
        # ---------------------------------------------------------------
        self._capture.start()
        log.info("FSM: cattura in corso (VAD endpointing)...")
        print("\r🔴 Registro — parla ora...", flush=True)

        captured_frames: list[bytes] = []
        vad_loop = asyncio.get_running_loop()
        self._vad.reset()
        # Config-driven CATTURA timer initialization (US-168, TSK-376).
        # Re-run here: works for both nominal path and barge-in
        # (PARLATO → CATTURA), resetting timers on each new state entry.
        self._cattura_start = time.monotonic()
        self._speech_onset = False

        # ------------------------------------------------------------------
        # Periodic liveness check in CATTURA (TSK-396 — fix FSM pickup post-shutdown)
        #
        # Failure scenario (documented root cause):
        #   1. FSM in CATTURA; consumer (file-pipe) exits due to crash or SIGTERM.
        #   2. CONSUMER_ALIVE becomes stale after consumer_alive_ttl_s (default 10s).
        #   3. Without this check, the FSM keeps capturing audio until VAD
        #      endpoint (onset_timeout_s=5s) or max_duration_s (30s), then runs STT,
        #      and only in step [4] detects the dead consumer. Recovery time
        #      can reach 30s + STT latency.
        #   4. In continuous/handsfree mode, the next run_once() re-enters
        #      CATTURA immediately (because _continuous_mode=True and is not
        #      reset), creating a busy-loop: capture → consumer_non_connesso
        #      → IDLE → cattura → ...
        #
        # Fix: check liveness every _CATTURA_LIVENESS_INTERVAL_S (5s). If the
        # consumer is dead → stop capture, reset _continuous_mode, return to IDLE.
        # For non-file-pipe adapters (mock, anthropic, ollama, etc.) is_consumer_alive()
        # always returns True → this path is a transparent no-op (AC5 unchanged).
        # ------------------------------------------------------------------
        _cattura_liveness_last: float = self._cattura_start

        while True:
            # ------------------------------------------------------------------
            # Onset and max-duration timers (US-168 AC1/AC2) — evaluated each frame,
            # regardless of queue.get/Empty branch. Replace the old
            # hardcoded 8s deadline (removed, TSK-376).
            # ------------------------------------------------------------------
            _now = time.monotonic()
            _elapsed = _now - self._cattura_start

            # ------------------------------------------------------------------
            # Periodic liveness check (TSK-396): every _CATTURA_LIVENESS_INTERVAL_S
            # seconds verify that the consumer is still connected.
            # Avoid completing capture + STT before discovering the dead consumer.
            # ------------------------------------------------------------------
            if _now - _cattura_liveness_last >= _CATTURA_LIVENESS_INTERVAL_S:
                _cattura_liveness_last = _now
                if not self._runtime.is_consumer_alive():
                    log.warning(
                        "FSM CATTURA: consumer non connesso (liveness check periodico) "
                        "— abort capture, torno a IDLE"
                    )
                    self._capture.stop()
                    # Reset _continuous_mode: prevents immediate re-entry into CATTURA
                    # on next run_once() (TSK-396 fix busy-loop post-shutdown).
                    if self._continuous_mode:
                        log.info(
                            "FSM: _continuous_mode reset — consumer morto rilevato in CATTURA"
                        )
                        self._continuous_mode = False
                    self._transition(VoiceState.IDLE, trigger="consumer_morto_in_cattura")
                    return

            if not self._speech_onset and _elapsed > self._config.capture.onset_timeout_s:
                log.info(
                    "FSM: onset_timeout (%ds): nessun onset VAD — torno a IDLE",
                    self._config.capture.onset_timeout_s,
                )
                self._capture.stop()
                if self._continuous_mode and not self._handsfree_mode:
                    self._continuous_mode = False
                self._transition(VoiceState.IDLE, trigger="onset_timeout")
                return

            if _elapsed > self._config.capture.max_duration_s:
                log.warning(
                    "FSM: max_capture_duration (%ds) superato — torno a IDLE senza STT",
                    self._config.capture.max_duration_s,
                )
                self._capture.stop()
                if self._continuous_mode and not self._handsfree_mode:
                    self._continuous_mode = False
                self._transition(VoiceState.IDLE, trigger="max_capture_timeout")
                return

            try:
                frame_float: "np.ndarray" = await vad_loop.run_in_executor(
                    None, lambda: self._capture.queue.get(timeout=0.5)
                )
            except _queue_module.Empty:
                # Timers are checked at the top of the loop: no additional check
                # on time in the Empty branch (old deadline removed, TSK-376).
                continue

            # float32 → PCM int16 bytes for Endpointer/SileroVAD
            _mono = frame_float[:, 0] if frame_float.ndim > 1 else frame_float.ravel()
            _frame_bytes = (
                np.clip(_mono, -1.0, 1.0) * 32767.0
            ).astype(np.int16).tobytes()
            captured_frames.append(_frame_bytes)

            if self._vad.feed_frame(_frame_bytes, sr):
                log.info("FSM: fine-turno VAD rilevato")
                break

            # Update onset (US-168 AC1): speech_started becomes True after
            # feed_frame has processed a speech frame. Once set,
            # disables onset_timeout check for the rest of the turn.
            if not self._speech_onset and self._vad.speech_started:
                self._speech_onset = True

        # Close microphone BEFORE beep: avoid PortAudio input/output conflict
        # on the same physical device (PaErrorCode -9986 paInvalidDevice on macOS).
        self._capture.stop()

        # Voice feedback for message received
        await self._speak_feedback("Ok, elaboro.", tts_sr)
        print("\r✍️  Trascrivo...", flush=True)

        # ---------------------------------------------------------------
        # [3] CATTURA → TRASCRIZIONE
        # ---------------------------------------------------------------
        self._transition(VoiceState.TRASCRIZIONE, trigger="VAD_endpoint")
        # capture.stop() already called before beep

        audio_bytes = b"".join(captured_frames) if captured_frames else _drain_queue(self._capture.queue)
        if not audio_bytes:
            log.warning("FSM: nessun audio catturato; turno saltato → IDLE")
            self._state = VoiceState.IDLE
            log.info("FSM: IDLE → IDLE (trigger: audio_vuoto)")
            return

        text: str = await self._stt.transcribe(audio_bytes, sr)
        if not text or not text.strip():
            log.warning("FSM: trascrizione vuota; turno saltato → IDLE")
            self._state = VoiceState.IDLE
            log.info("FSM: TRASCRIZIONE → IDLE (trigger: testo_vuoto)")
            return

        # --- Wake-word first-turn filter (US-156, TSK-335) ---
        # _skip_next_utterance is True ONLY after wake_word_detected (AC6: no-op in PTT).
        # filter_threshold: use getattr for backward compat with TSK-337 not yet executed.
        if self._skip_next_utterance:
            self._skip_next_utterance = False  # reset: applies only on first turn
            keyword = self._config.wake_word.keyword
            dist = levenshtein(text.lower().strip(), keyword.lower())
            if dist < getattr(self._config.wake_word, "filter_threshold", 3):
                log.debug(
                    "Wake-word utterance scartata: %r (distanza Levenshtein=%d)",
                    text,
                    dist,
                )
                # Transition to IDLE: mirrors "empty text" behavior (AC4)
                self._state = VoiceState.IDLE
                log.info(
                    "FSM: TRASCRIZIONE → IDLE (trigger: wake_word_utterance_scartata)"
                )
                return
            # otherwise: first turn was already a real command, continue normally

        log.info("FSM: testo trascritto → %r", text)
        print(f"\n👤 Tu: {text}", flush=True)
        self._write_utterance_log(text)  # chat visibility independent of provider

        # --- Local voice commands (no LLM call) ---
        voice_cmd = self._detect_voice_command(text)
        if voice_cmd:
            await self._handle_voice_command(voice_cmd, tts_sr)
            self._transition(VoiceState.IDLE, trigger="voice_command")
            return

        # ---------------------------------------------------------------
        # [4] TRASCRIZIONE → ELABORAZIONE (with pre-flight liveness US-167)
        # ---------------------------------------------------------------
        # Pre-flight liveness check (US-167 C3 AC1/AC2): if the consumer
        # (file-pipe adapter) is not connected, emit TTS feedback and return to
        # IDLE without waiting for the 180s timeout. For all non-
        # file-pipe adapters is_consumer_alive() always returns True → nominal path
        # unchanged (AC5). Check is one-shot synchronous (TTL file lookup).
        if not self._runtime.is_consumer_alive():
            log.warning(
                "consumer non connesso (liveness check fallito) — feedback + torno a IDLE"
            )
            # TSK-396: reset _continuous_mode to prevent post-shutdown busy-loop.
            # Root cause: without reset, run_loop() immediately calls run_once() which, with
            # _continuous_mode=True, skips INVIO/wake-word wait and re-enters CATTURA,
            # ritrovando il consumer morto e ripetendo all'infinito la sequenza
            # «cattura → liveness fail → "Nessuna sessione" TTS → IDLE → cattura».
            if self._continuous_mode:
                log.info(
                    "FSM: _continuous_mode reset — consumer non connesso pre-ELABORAZIONE"
                )
                self._continuous_mode = False
            await self._speak_feedback(self._config.runtime.not_connected_message)
            self._transition(VoiceState.IDLE, trigger="consumer_non_connesso")
            return

        print(f"\r⚙️  Elaboro...", flush=True)
        self._transition(VoiceState.ELABORAZIONE, trigger="testo_pronto")

        tts_chunks: list[str] = []
        async for event in self._runtime.submit(text, session.session_id):
            continue_turn: bool = await self._router.route(event)
            if isinstance(event, Acknowledgment):
                # Acknowledgment → print only (no TTS): Acknowledgment is emitted
                # before the LLM starts, so synthesizing it creates silence
                # post-ack worse than not doing it. Audio feedback is already ack_beep.
                print(f"  💭 {event.text}", flush=True)
            elif isinstance(event, SpokenSummary):
                tts_chunks.append(event.text)
            if not continue_turn:
                # Done or Error: end processing
                break

        if tts_chunks:
            print(f"\n🤖 Risposta: {' '.join(tts_chunks)}", flush=True)
            self._last_tts_chars = sum(len(c) for c in tts_chunks)

        # ---------------------------------------------------------------
        # [5] ELABORAZIONE → PARLATO (only if there are chunks to speak)
        # ---------------------------------------------------------------
        if tts_chunks:
            self._transition(VoiceState.PARLATO, trigger="elaborazione_completata")

            if self._config.barge_in.enabled:
                # ----------------------------------------------------------
                # Phase 3: TTS playback with concurrent barge-in detection
                # (US-144 AC2 — TSK-301)
                # ----------------------------------------------------------
                # US-166 flag (TSK-368): set before playback, clear in finally.
                self._tts_playing = True
                self._tts_playing_since = time.monotonic()
                try:
                    barge_in_occurred = await self._run_parlato_barge_in(
                        tts_chunks, session.session_id, tts_sr
                    )
                finally:
                    # Clear BEFORE potential re-entry to CATTURA (constraint D5).
                    self._tts_playing = False

                if barge_in_occurred:
                    # PARLATO → CATTURA (not IDLE) — US-144 AC2d
                    self._transition(VoiceState.CATTURA, trigger="barge-in")
                    # turn interrupted; next run_loop cycle will restart from IDLE
                    return
                # No barge-in: fall-through to IDLE transition

            else:
                # ----------------------------------------------------------
                # Phase 1/2: sequential, no barge-in (backward compat)
                # ----------------------------------------------------------
                # US-166 flag (TSK-368): set before TTS loop, clear in finally.
                self._tts_playing = True
                self._tts_playing_since = time.monotonic()
                try:
                    for chunk in tts_chunks:
                        if self._cancellation_requested.is_set():
                            log.info("FSM: barge-in rilevato; sintesi interrotta")
                            break
                        try:
                            synth: "np.ndarray" = await asyncio.to_thread(
                                self._tts.synthesize, chunk
                            )
                            await asyncio.to_thread(self._playback.play, synth, tts_sr)
                        except Exception as exc:  # noqa: BLE001
                            log.error("FSM: errore sintesi/playback (%r): %s", chunk[:30], exc)
                            print(f"\r❌ Errore TTS: {exc}", flush=True)
                            try:
                                from voice.audio.beep import generate_error_beep  # noqa: PLC0415
                                _err_beep = generate_error_beep(tts_sr)
                                await asyncio.to_thread(self._playback.play, _err_beep, tts_sr)
                            except Exception:  # noqa: BLE001
                                pass  # if beep also fails, do nothing else
                finally:
                    self._tts_playing = False
        else:
            # No spoken text produced: direct transition to IDLE
            log.info(
                "FSM: %s → IDLE (trigger: nessun_testo_parlato)",
                self._state.value,
            )
            self._state = VoiceState.IDLE
            return

        # ---------------------------------------------------------------
        # [6] PARLATO → IDLE
        # ---------------------------------------------------------------
        _should_reset = self._session_manager.should_reset()
        log.debug("session_manager.should_reset() = %s (no-op)", _should_reset)
        self._transition(VoiceState.IDLE, trigger="turno_completato")

    # ------------------------------------------------------------------
    # _run_parlato_barge_in: Phase 3 — concurrent playback + detector
    # ------------------------------------------------------------------

    async def _run_parlato_barge_in(
        self,
        tts_chunks: "list[str]",
        session_id: str,
        tts_sr: int,
    ) -> bool:
        """Phase 3: TTS playback with concurrent barge-in detection (US-144 AC2).

        Launches two asyncio tasks in parallel:
          - playback_task: reads chunks from TTS queue, synthesizes and plays.
          - detector_task: monitors incoming audio frames via BargeinDetector
            and cancels playback_task if voice detected (RMS pre-gate + VAD debounce).

        On barge-in confirmation:
          1. BargeinDetector.monitor() has already called playback_task.cancel()
             and playback.abort() for immediate stop (US-144 AC2a).
          2. cancel_turn() flushes TTS queue and propagates cancel to LLM runtime
             (US-144 AC2b/AC2c).
        Teardown awaits asyncio.gather(..., return_exceptions=True) ensuring
        both tasks have finished before transition (US-144 AC2c).

        Args:
            tts_chunks: list of text chunks to synthesize and play.
            session_id: current turn identifier (passed to cancel_turn).
            tts_sr:     TTS sample rate in Hz (typically 22050 for piper-tts).

        Returns:
            True  — barge-in detected and confirmed (playback interrupted).
            False — playback finished naturally, no barge-in.

        Note:
            Barge-in VAD uses the threshold configured in
            config.barge_in.vad_threshold (default 0.7, higher than
            CATTURA 0.5) to reduce false triggers from noise or TTS audio captured
            by speakers (US-144 AC5/AC6).

            self._vad is an Endpointer; the underlying VADBase (self._vad._vad)
            is passed directly to BargeinDetector (already pre-configured
            by Endpointer — see BargeinDetector.__init__ docstring).
            # pending_clarification: if Endpointer exposes VADBase
            # as a public property in the future, update this private access.
        """
        # Lazy import: does not import torch/webrtcvad at module level (DoD TSK-300)
        from voice.core.cancellation import BargeinDetector, cancel_turn  # noqa: PLC0415

        # TTS queue: holds chunks not yet spoken (flushed in cancel_turn)
        tts_queue: asyncio.Queue = asyncio.Queue()
        for chunk in tts_chunks:
            tts_queue.put_nowait(chunk)

        # Playback task: synthesizes and plays chunks from TTS queue
        async def _playback_worker() -> None:
            while not tts_queue.empty():
                chunk: str = tts_queue.get_nowait()
                synth: "np.ndarray" = await asyncio.to_thread(
                    self._tts.synthesize, chunk
                )
                await asyncio.to_thread(self._playback.play, synth, tts_sr)

        playback_task: asyncio.Task = asyncio.create_task(_playback_worker())

        # BargeinDetector: VADBase extracted from Endpointer (self._vad._vad)
        # vad_threshold configures the documented threshold in the detector;
        # VAD is already pre-instantiated by Endpointer with its parameters.
        detector = BargeinDetector(
            vad=self._vad._vad,  # type: ignore[union-attr]  # Endpointer._vad = VADBase
            capture=self._capture,
            vad_threshold=self._config.barge_in.vad_threshold,  # 0.7 PARLATO (AC5)
        )
        detector_task: asyncio.Task = asyncio.create_task(
            detector.monitor(playback_task, self._playback)
        )

        # Teardown: wait for both tasks to finish (US-144 AC2c)
        results = await asyncio.gather(playback_task, detector_task, return_exceptions=True)

        # results[1]: True (barge-in detected) | False | Exception
        barge_in_detected: bool = results[1] is True

        if barge_in_detected:
            log.info(
                "FSM: barge-in confermato in PARLATO; "
                "avvio sequenza cancel_turn (session_id=%s)",
                session_id,
            )
            # Steps 2-3 of cancel sequence: flush TTS queue + cancel runtime
            # (Step 1 — stop TTS — already done by BargeinDetector.monitor())
            await cancel_turn(
                playback_task,
                tts_queue,
                self._playback,
                self._runtime,
                session_id,
            )

        return barge_in_detected

    # ------------------------------------------------------------------
    # run_turn: DoD signature (US-143 AC2) — wrapper over run_once()
    # ------------------------------------------------------------------

    async def run_turn(
        self,
        capture: "AudioCapture",
        stt: "BaseSTT",
        runtime: "FactoryRuntime",
        router: "EventRouter",
        tts: "TTSBase",
        playback: "AudioPlayback",
        config: "VoiceConfig",
    ) -> None:
        """Run a full turn with explicitly passed dependencies.

        Signature compatible with DoD US-143 AC2. Temporarily overrides
        instance dependencies and calls run_once(); restores them in finally.

        Args:
            capture:  AudioCapture to acquire audio frames.
            stt:      BaseSTT for transcription.
            runtime:  FactoryRuntime for LLM processing.
            router:   EventRouter to route runtime events.
            tts:      TTSBase for speech synthesis.
            playback: AudioPlayback for playback.
            config:   VoiceConfig with parameters (samplerate, language, etc.).
        """
        # Save original dependencies
        _orig = (
            self._capture,
            self._stt,
            self._runtime,
            self._router,
            self._tts,
            self._playback,
            self._config,
        )
        # Override for this turn
        self._capture = capture
        self._stt = stt
        self._runtime = runtime
        self._router = router
        self._tts = tts
        self._playback = playback
        self._config = config
        try:
            await self.run_once()
        finally:
            # Restore original dependencies
            (
                self._capture,
                self._stt,
                self._runtime,
                self._router,
                self._tts,
                self._playback,
                self._config,
            ) = _orig

    # ------------------------------------------------------------------
    # run_loop: infinite loop (main entry point)
    # ------------------------------------------------------------------

    async def run_loop(self) -> None:
        """Infinite loop: calls run_once() in cycle until Ctrl+C.

        On KeyboardInterrupt performs clean shutdown:
        calls runtime.aclose() and logs shutdown.

        TSK-396: unexpected exceptions in run_once() (e.g. audio OSError, network
        error, exception in CATTURA/ELABORAZIONE path) are caught to
        prevent the FSM from getting stuck in a non-IDLE state. State is
        reset to IDLE and the loop continues, ensuring voice channel resilience
        against transient errors.
        """
        log.info("FSM: avvio loop push-to-talk (Ctrl+C per uscire)")
        try:
            while True:
                self._cancellation_requested.clear()
                try:
                    await self.run_once()
                except KeyboardInterrupt:
                    raise  # propagate to outer except block
                except Exception as exc:
                    # TSK-396: recovery from unexpected exception in run_once.
                    # Root cause: an exception during CATTURA or ELABORAZIONE can
                    # leave the FSM in non-IDLE state and/or capture open.
                    # Fix: log error, reset to IDLE, attempt capture stop,
                    # continue loop (no voice process crash).
                    log.error(
                        "FSM: eccezione non attesa in run_once [stato=%s]: %s "
                        "— reset a IDLE e riprendo il loop",
                        self._state.value,
                        exc,
                        exc_info=True,
                    )
                    self._state = VoiceState.IDLE
                    try:
                        self._capture.stop()
                    except Exception:  # noqa: BLE001
                        pass  # capture already stopped or unavailable — do not block recovery
        except KeyboardInterrupt:
            log.info("FSM: interruzione richiesta da Ctrl+C")
        finally:
            await self._runtime.aclose()
            log.info("FSM: loop terminato, risorse rilasciate")


    # ------------------------------------------------------------------
    # Local voice commands (handsfree toggle)
    # ------------------------------------------------------------------

    # Keywords detected in transcription to enable/disable handsfree.
    # Lowercase comparison, case-insensitive, substring match.
    _HANDSFREE_ON_KEYWORDS = ("handsfree", "hands-free", "hands free", "mani libere")
    _HANDSFREE_OFF_KEYWORDS = ("disattiva handsfree", "disattiva hands-free", "modalità normale")

    def _detect_voice_command(self, text: str) -> "str | None":
        """Return command name if text contains a keyword, otherwise None.

        OFF-keywords are checked first because they include ON-keywords as
        substrings ("disattiva handsfree" contains "handsfree"): without this order
        an OFF command would be incorrectly recognized as ON.
        """
        lower = text.lower().strip()
        for kw in self._HANDSFREE_OFF_KEYWORDS:
            if kw in lower:
                return "handsfree_off"
        for kw in self._HANDSFREE_ON_KEYWORDS:
            if kw in lower:
                return "handsfree_on"
        return None

    async def _handle_voice_command(self, command: str, tts_sr: int) -> None:
        """Execute voice command: update state and respond with local TTS (no LLM)."""
        if command == "handsfree_on":
            self._handsfree_mode = True
            self._continuous_mode = True
            msg = "Modalità handsfree attivata, posso ascoltarti senza bisogno di dire Prometeus."
            print("\r🔊 Handsfree ON")
            log.info("FSM: handsfree_mode attivata")
        elif command == "handsfree_off":
            self._handsfree_mode = False
            msg = "Modalità handsfree disattivata, dì Prometeus per ricominciare."
            print("\r🎤 Handsfree OFF")
            log.info("FSM: handsfree_mode disattivata")
        else:
            return

        try:
            synth = await asyncio.to_thread(self._tts.synthesize, msg)
            await asyncio.to_thread(self._playback.play, synth, tts_sr)
        except Exception as exc:  # noqa: BLE001
            log.error("FSM: errore TTS comando vocale (%r): %s", command, exc)


# ---------------------------------------------------------------------------
# Compatibility alias (orchestrator spec uses VoiceFSM)
# ---------------------------------------------------------------------------

VoiceFSM = VoiceStateMachine
