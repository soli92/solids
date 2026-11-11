"""
voice/audio/playback.py — Synchronous audio playback via sounddevice (PortAudio).

Design:
- `play()` is synchronous: blocks until data has been played.
  In Phase 1 sequentiality is intentional (US-143 Technical Notes).
  For use inside `asyncio`, wrap with `asyncio.to_thread(playback.play, ...)`.
- `abort()` stops playback immediately (barge-in Phase 3, US-144).
  In Phase 1 used for flush on error.
- `stop()` performs an orderly drain then closes the device.
- `sounddevice` is imported lazily inside each method that needs it.
- `PlaybackFarEndSink` (US-147 Phase 4): thread-safe circular buffer that receives
  each TTS frame during playback, exposed to AECProcessor as far-end reference
  for echo cancellation (capture → AEC → VAD → STT).

Typical usage (Phase 1, sequential):
    playback = AudioPlayback(config)
    playback.play(audio_array, samplerate=22050)
    # blocks until audio finishes

    # Emergency interrupt (e.g. barge-in Phase 3):
    playback.abort()
"""
from __future__ import annotations

import collections
import logging
import threading
from typing import TYPE_CHECKING, Optional

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    import numpy as np


# ---------------------------------------------------------------------------
# PlaybackFarEndSink — thread-safe circular buffer for far-end signal
# ---------------------------------------------------------------------------

class PlaybackFarEndSink:
    """
    Thread-safe circular buffer for TTS audio frames during playback.

    Provides far-end reference to AECProcessor: AudioPlayback notifies each
    TTS frame played via `push()`; AudioCapture reads the most recent frame
    via `get_latest()` in the real-time callback for use as AEC reference signal
    (US-147 Phase 4).

    Thread-safety: push() and get_latest() are protected by threading.Lock.
    The buffer is a deque with fixed maxlen (circular): oldest frames are
    discarded automatically when the buffer is full.

    Args:
        maxlen: maximum circular buffer capacity (default 32 frames).
                At 30 ms/frame @ 16kHz, 32 frames = ~960 ms of history.
    """

    def __init__(self, maxlen: int = 32) -> None:
        self._buffer: collections.deque = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def push(self, frame: "np.ndarray") -> None:
        """Add an audio frame to the circular buffer (thread-safe).

        Args:
            frame: PCM float32, shape (N,) mono — TTS frame being played.
        """
        with self._lock:
            self._buffer.append(frame)

    def get_latest(self) -> "Optional[np.ndarray]":
        """Return the most recent frame, or None if the buffer is empty.

        Thread-safe: callable from the PortAudio callback real-time thread.
        """
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
            return None


class AudioPlayback:
    """
    Synchronous numpy audio playback via sounddevice.

    Thread-safety: `abort()` is designed to be called from a thread
    different from `play()`. Internal state is protected by `threading.Event`.
    """

    def __init__(self, config: "VoiceConfig") -> None:  # noqa: F821
        """
        Initialize AudioPlayback with voice config.

        Args:
            config: VoiceConfig from `voice.config`. In Phase 1 config is
                    used for potential future overrides (output device, etc.).
        """
        self._config = config
        # Output device: device name string or None (system default)
        self._output_device = config.audio.output_device  # type: ignore[attr-defined]
        self._abort_event = threading.Event()
        # Far-end sink for AEC (Phase 4, US-147): None by default (no AEC active).
        # Set via set_far_end_sink() by the assembler (voice/app.py) when
        # config.aec.enabled=True.
        self._far_end_sink: Optional["PlaybackFarEndSink"] = None

    def set_far_end_sink(self, sink: "PlaybackFarEndSink") -> None:
        """Set the far-end sink for AEC (US-147 Phase 4).

        Each TTS audio frame during playback is sent to the sink via push()
        before playback starts. AudioCapture reads the most recent frame
        from the sink as far-end reference for AECProcessor in its callback.

        Args:
            sink: PlaybackFarEndSink instance shared with AudioCapture.
        """
        self._far_end_sink = sink

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, audio_data: "np.ndarray", samplerate: int = 22050) -> None:
        """
        Play a numpy array synchronously (blocking).

        Clears the abort flag before starting playback so a previous call to
        `abort()` does not contaminate the next playback.

        Args:
            audio_data:  float32 numpy array with audio samples. Shape
                         `(n_samples,)` mono or `(n_samples, channels)` stereo.
            samplerate:  sample rate in Hz (default 22050,
                         typical piper TTS output).

        Raises:
            ImportError: if sounddevice is not installed.
        """
        try:
            import sounddevice as sd  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "sounddevice non trovato. "
                "Installa le dipendenze vocali: pip install '.[voice]'"
            ) from exc

        # Reset flag: abort() called before play() must not stop current play.
        self._abort_event.clear()

        # Far-end sink (AEC Phase 4, US-147): notify TTS frame as reference
        # far-end before playback starts. AudioCapture reads the most recent
        # frame from the sink during the AEC callback. Normalized to mono (N,) float32.
        if self._far_end_sink is not None:
            import numpy as _np  # noqa: PLC0415  # lazy: avoided when AEC disabled
            _ref = _np.asarray(audio_data, dtype=_np.float32)
            if _ref.ndim > 1:
                _ref = _ref[:, 0]
            self._far_end_sink.push(_ref)

        # sounddevice.play() is non-blocking; sounddevice.wait() blocks
        # until playback finishes (or until abort() calls stop()).
        sd.play(audio_data, samplerate=samplerate)
        try:
            # Polling loop to honor abort event without busy-wait.
            # sounddevice.wait() blocks without timeout; use get_stream to
            # check abort flag with 50 ms granularity.
            import time as _time  # noqa: PLC0415

            while sd.get_stream().active:
                if self._abort_event.is_set():
                    sd.stop()
                    break
                _time.sleep(0.05)
        except Exception as _poll_exc:  # noqa: BLE001
            # Stream already closed or other non-critical error — do not propagate.
            # WARNING log makes PaErrorCode -9986 and similar visible.
            log.warning("AudioPlayback: errore polling stream: %s", _poll_exc)

    def abort(self) -> None:
        """
        Stop playback in progress immediately (buffer drop).

        Thread-safe: can be called from any thread.
        If no playback is in progress, this is a no-op.
        """
        try:
            import sounddevice as sd  # noqa: PLC0415
        except ImportError:
            return

        self._abort_event.set()
        try:
            sd.stop()
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        """
        Wait for current playback to finish (orderly drain) then close.

        Unlike `abort()`, does not interrupt buffers already started.
        Used for clean module shutdown.
        """
        try:
            import sounddevice as sd  # noqa: PLC0415
        except ImportError:
            return

        try:
            sd.wait()
        except Exception:  # noqa: BLE001
            pass
