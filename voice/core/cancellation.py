"""
voice/core/cancellation.py — Cancellation and barge-in (Phase 3, TSK-300).

Implements the two-stage RMS+VAD detector for barge-in during TTS playback
and the async propagated cancel sequence.

Architecture:
  BargeinDetector.process_frame()  — frame-by-frame detector (RMS pre-gate + VAD)
  BargeinDetector.monitor()        — async loop reading from audio queue
  cancel_turn()                    — cancel sequence: playback + TTS queue + runtime

Lazy import (DoD TSK-300):
  The module does not import torch, webrtcvad or sounddevice at module level.
  VADBase comes from voice.vad.base which has only stdlib; the concrete instance
  (SileroVAD or WebRTCVAD) is injected via constructor.
  numpy is the only heavy dependency at module level; it is accepted
  because it is already used throughout the voice/ layer and does not require device specifics.

Backward-compat gate (AC6/US-144):
  When voice_channel.barge_in.enabled: false BargeinDetector is not
  instantiated by the state machine (TSK-301); this module remains importable
  without side effects.

Main exports:
    CancelToken      — synchronous cancellation flag (DoD US-143 AC2)
    BargeinDetector  — two-stage RMS+VAD detector (DoD TSK-300)
    cancel_turn      — async cancel sequence (playback + TTS + runtime)
"""
from __future__ import annotations

import asyncio
import logging
import queue as _queue_module
from typing import TYPE_CHECKING, Optional

import numpy as np

from voice.vad.base import VADBase

if TYPE_CHECKING:
    from voice.audio.capture import AudioCapture
    from voice.audio.playback import AudioPlayback
    from voice.runtime.factory_runtime import FactoryRuntime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CancelToken (DoD US-143 AC2)
# ---------------------------------------------------------------------------

class CancelToken:
    """Synchronous cancellation token for a voice turn.

    In Phase 1 it is never set (no barge-in). Passed to the state machine
    which checks it before each TTS chunk in PARLATO.

    Usage:
        token = CancelToken()
        # from another thread/task (Phase 3):
        token.cancel()
        # in the state machine:
        if token.is_cancelled:
            break
    """

    def __init__(self) -> None:
        self.is_cancelled: bool = False

    def cancel(self) -> None:
        """Set the cancellation flag.

        Idempotent: calling multiple times has no side effects.
        Thread-safe for reads; atomic write on CPython (GIL).
        """
        self.is_cancelled = True

    def reset(self) -> None:
        """Clear the flag (new turn)."""
        self.is_cancelled = False

    def __repr__(self) -> str:  # pragma: no cover
        return f"CancelToken(is_cancelled={self.is_cancelled})"


# ---------------------------------------------------------------------------
# BargeinDetector (TSK-300 — Phase 3)
# ---------------------------------------------------------------------------

class BargeinDetector:
    """
    Detects voice activity during TTS playback and cancels the current task.

    Phase 3: two-stage detection
    1. RMS pre-gate (fast, no model) — computes rms = sqrt(mean(frame**2));
       frames below threshold are discarded without invoking VAD.
    2. VAD confirmation (with debounce) — only frames above RMS pre-gate pass to
       VAD; barge-in triggers when VAD confirms voice for N consecutive frames
       (avoids triggers on single spikes).

    VAD is received via constructor (injection): the detector does not import
    torch or webrtcvad at module level (DoD TSK-300, backward-compat).

    In PARLATO state VAD should already be configured with a higher threshold
    than CATTURA (config.barge_in.vad_threshold = 0.7, AC5/AC6):
    responsibility lies with the caller that instantiates VAD with the correct threshold.
    The vad_threshold parameter in the constructor documents the expected value but
    does not override the injected VAD internal configuration.

    Args:
        vad:             VADBase instance already configured with the correct threshold
                         for PARLATO state (typically threshold=0.7).
        capture:         AudioCapture listening during PARLATO; monitor() reads
                         from its thread-safe queue.
        rms_threshold:   RMS energy pre-gate (normalized float32 [-1,1]).
                         Frames with RMS < threshold are discarded without invoking VAD.
                         Default 0.01 (~ -40 dBFS).
        vad_threshold:   Expected VAD threshold (documentation; VAD already configured).
                         Default 0.7 for PARLATO state (vs 0.5 in CATTURA, AC5).
        debounce_frames: Number of consecutive VAD frames required to confirm
                         barge-in. Default 3 (~ 90 ms at 30 ms/frame).
        sample_rate:     Expected sample rate in Hz. Default 16000.
    """

    def __init__(
        self,
        vad: VADBase,
        capture: "AudioCapture",
        rms_threshold: float = 0.01,
        vad_threshold: float = 0.7,
        debounce_frames: int = 3,
        sample_rate: int = 16000,
    ) -> None:
        self._vad = vad
        self._capture = capture
        self._rms_threshold = rms_threshold
        self._vad_threshold = vad_threshold  # documentation; VAD already pre-configured
        self._debounce_frames = debounce_frames
        self._sample_rate = sample_rate
        # Internal consecutive VAD frame counter above threshold
        self._consecutive_vad_frames: int = 0

    # ------------------------------------------------------------------
    # process_frame — two-stage detection on single frame
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> bool:
        """Two-stage detection on a single audio frame.

        Stage 1 — RMS pre-gate:
            Computes rms = sqrt(mean(frame**2)). If rms < rms_threshold the frame
            is discarded (resets consecutive VAD counter) without invoking
            the VAD model: pure numpy operation, no ML overhead.

        Stage 2 — VAD confirmation:
            Frame that passes RMS pre-gate is converted from float32 to
            PCM int16 bytes and passed to VADBase.is_speech(). If VAD confirms
            speech, consecutive frame counter is incremented; when debounce_frames
            is reached the method returns True.
            If VAD denies speech, counter is reset.

        Args:
            frame: float32 numpy array of shape (blocksize,) mono or
                   (blocksize, channels); first channel is used for computation.

        Returns:
            True if barge-in is confirmed (N consecutive VAD frames above
            threshold after RMS pre-gate). False otherwise.
        """
        # Flatten to mono: use first channel if multi-channel
        audio: np.ndarray = frame[:, 0] if frame.ndim > 1 else frame

        # Stage 1: RMS pre-gate — cheap, no ML
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < self._rms_threshold:
            # Below threshold: no speech expected, reset debounce
            self._consecutive_vad_frames = 0
            return False

        # Stage 2: VAD confirmation
        # Convert float32 [-1.0, 1.0] → PCM int16 little-endian (VADBase format)
        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
        frame_bytes: bytes = audio_int16.tobytes()

        try:
            is_speech: bool = self._vad.is_speech(frame_bytes, self._sample_rate)
        except Exception as exc:  # noqa: BLE001
            # VAD error (e.g. wrong frame length for WebRTCVAD):
            # do not trigger barge-in, reset counter for safety.
            logger.debug(
                "BargeinDetector: errore VAD su frame (%s); frame scartato", exc
            )
            self._consecutive_vad_frames = 0
            return False

        if is_speech:
            self._consecutive_vad_frames += 1
        else:
            self._consecutive_vad_frames = 0

        return self._consecutive_vad_frames >= self._debounce_frames

    # ------------------------------------------------------------------
    # reset — clear internal state (new turn)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear consecutive VAD frame counter.

        Call before each new turn (or at the start of each monitor())
        to avoid residual state from the previous turn triggering a false
        barge-in at the start of the next one.
        """
        self._consecutive_vad_frames = 0

    # ------------------------------------------------------------------
    # monitor — async detection loop during playback
    # ------------------------------------------------------------------

    async def monitor(
        self,
        playback_task: asyncio.Task,
        playback: Optional["AudioPlayback"] = None,
    ) -> bool:
        """Monitor audio capture while playback_task is active.

        Reads frames from AudioCapture queue without blocking the event loop
        (non-blocking polling with get_nowait() + asyncio.sleep(0.005)).
        For each frame calls process_frame() which runs two-stage detection
        (RMS pre-gate → VAD debounce).

        On barge-in confirmation:
          1. Cancel playback_task (injects CancelledError into the asyncio task
             running asyncio.to_thread(playback.play, ...)).
          2. If playback is provided, call playback.abort() for immediate
             sounddevice buffer drop (without waiting for thread drain).
          3. Return True.

        If playback_task finishes naturally before barge-in, return False.

        Args:
            playback_task: Asyncio task managing TTS playback.
                           Cancelled on barge-in detection.
            playback:      Optional AudioPlayback. If provided, .abort() is
                           called immediately for instant audio stop
                           (recommended for AC4 latency < 300 ms).
                           If None, only the task is cancelled: audio stop
                           happens via cancel_turn() in the state machine.

        Returns:
            True  — barge-in detected (playback_task cancelled).
            False — playback finished naturally without barge-in.

        Raises:
            asyncio.CancelledError: if the calling task is itself
                                    cancelled (propagated correctly).
        """
        self.reset()

        # Drain residual frames in queue (produced during CATTURA/TRASCRIZIONE)
        # to avoid false triggers from pre-playback audio at monitor start.
        _drained = 0
        while True:
            try:
                self._capture.queue.get_nowait()
                _drained += 1
            except _queue_module.Empty:
                break
        if _drained:
            logger.debug(
                "BargeinDetector: scaricati %d frame residui prima del monitor",
                _drained,
            )

        try:
            while not playback_task.done():
                # Non-blocking poll: avoid blocking the asyncio event loop
                try:
                    frame: np.ndarray = self._capture.queue.get_nowait()
                except _queue_module.Empty:
                    # No frame available: yield control for ~5 ms
                    # (interval smaller than ~30 ms audio frame to avoid dropping frames)
                    await asyncio.sleep(0.005)
                    continue

                # Empty or invalid frame: skip without calling process_frame
                if frame is None or frame.size == 0:
                    continue

                # Two-stage detection: RMS pre-gate + VAD debounce
                if self.process_frame(frame):
                    logger.info(
                        "BargeinDetector: barge-in confermato"
                        " (%d frame VAD consecutivi, RMS pre-gate attivo);"
                        " cancello playback_task",
                        self._consecutive_vad_frames,
                    )
                    # Stop TTS task
                    playback_task.cancel()
                    # Immediate sounddevice stop (drop buffer, not drain)
                    if playback is not None:
                        playback.abort()
                    return True

            # Playback finished naturally before barge-in
            logger.debug("BargeinDetector: playback terminato senza barge-in")
            return False

        except asyncio.CancelledError:
            # Calling task (e.g. state machine) was cancelled:
            # propagate without suppressing to avoid blocking shutdown chain.
            logger.debug("BargeinDetector.monitor: CancelledError ricevuto, propagato")
            raise
        finally:
            # Cleanup always runs: clear internal state.
            # Caller (state machine TSK-301) is responsible for stopping
            # AudioCapture if needed.
            self.reset()


# ---------------------------------------------------------------------------
# cancel_turn — async propagated cancel sequence
# ---------------------------------------------------------------------------

async def cancel_turn(
    playback_task: asyncio.Task,
    tts_queue: "asyncio.Queue[object]",
    playback: "AudioPlayback",
    runtime: "FactoryRuntime",
    session_id: str,
) -> bool:
    """Barge-in cancel sequence: stop TTS + flush queue + cancel runtime.

    Executes the three cancel sequence steps (US-144 Technical Notes §Cancel mechanism
    via asyncio.Task) respecting the ~500 ms tolerance (AC2):

    1. Immediate TTS stop:
       - playback_task.cancel() — injects CancelledError into asyncio task.
       - playback.abort()       — immediate sounddevice buffer drop
                                  (abort != stop: no drain, instant).
         Note: AudioPlayback.abort() is synchronous; does not use await.

    2. Flush TTS queue:
       Drain tts_queue of sentences not yet spoken (and artifacts
       discarded by US-145): remove them without enqueueing elsewhere.

    3. Propagate cancel to LLM runtime:
       runtime.cancel(session_id) cleanly closes the LLM stream and any
       in-progress tools; idempotent (can be called multiple times).

    The entire sequence must complete within ~500 ms to respect AC2 tolerance
    (US-144). Steps 1 and 2 are synchronous and sub-millisecond; step 3
    (await runtime.cancel) completes within runtime timeout.

    Args:
        playback_task: Asyncio task running TTS playback.
        tts_queue:     Async queue with TTS sentences not yet spoken.
        playback:      AudioPlayback for immediate audio buffer drop.
        runtime:       FactoryRuntime from which to interrupt LLM processing.
        session_id:    Current turn identifier to cancel.

    Returns:
        True when the sequence is complete.
    """
    # Step 1: Immediate TTS stop
    # cancel() on asyncio task + abort() on sounddevice device (drop, not drain)
    playback_task.cancel()
    # abort() is synchronous (threading.Event.set() + sd.stop()); does not use await.
    playback.abort()

    # Step 2: Flush TTS queue — discard sentences not yet spoken
    flushed = 0
    while not tts_queue.empty():
        try:
            tts_queue.get_nowait()
            flushed += 1
        except Exception:  # noqa: BLE001
            # Queue empty or closed in the meantime: exit loop
            break
    if flushed:
        logger.debug("cancel_turn: %d chunk TTS scartati dalla coda", flushed)

    # Step 3: Propagate cancel to LLM runtime
    await runtime.cancel(session_id)

    logger.info(
        "cancel_turn: sequenza completata (session_id=%s, tts_flushed=%d)",
        session_id,
        flushed,
    )
    return True
