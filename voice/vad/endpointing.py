"""voice/vad/endpointing.py — Turn-end detection (endpointing) via VAD.

Accumulates audio frames classified by VAD and signals when an utterance
is complete (prolonged silence beyond the configured threshold).

In Phase 1 (sequential push-to-talk) Endpointer is not on the active path:
the turn ends on key release. The module exists and must be importable
(US-143 AC1) for Phase 2 (automatic endpointing, US-144).

No external dependencies: stdlib only.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice.vad.base import VADBase


class Endpointer:
    """Accumulates VAD frames and signals when an utterance is complete.

    Turn-end logic: after receiving at least one speech frame,
    continuous silence >= silence_threshold_ms ms is interpreted as
    end of utterance. Internal state is reset after each turn-end.

    Args:
        vad:                  Concrete VADBase instance (SileroVAD / WebRTCVAD).
        silence_threshold_ms: Minimum silence duration to declare turn-end
                              in milliseconds (default 700 ms; suggested range
                              500-800 ms for a natural experience).
        debounce_ms:          Debounce window in milliseconds: a second
                              endpoint within this interval from the previous one is
                              silently suppressed (US-155; default 500 ms).
                              On the first turn (_last_endpoint_ts == 0.0) the
                              condition is always false — zero nominal overhead.
    """

    def __init__(
        self,
        vad: "VADBase",
        silence_threshold_ms: int = 700,
        debounce_ms: int = 500,
    ) -> None:
        if silence_threshold_ms <= 0:
            raise ValueError(
                f"silence_threshold_ms deve essere positivo, "
                f"ricevuto: {silence_threshold_ms}"
            )
        self._vad = vad
        self._silence_threshold_ms = silence_threshold_ms
        self._debounce_ms = debounce_ms

        # Internal state
        self._accumulated: list[bytes] = []
        self._speech_started: bool = False
        self._silence_ms: int = 0
        # Timestamp of last accepted endpoint (monotonic, seconds).
        # Initialized to 0.0: debounce condition is false on first turn (AC5).
        self._last_endpoint_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def speech_started(self) -> bool:
        """True if VAD detected speech onset in the current turn.
        Read-only — does not alter feed_frame() or reset() behavior.
        """
        return self._speech_started

    def feed_frame(self, frame: bytes, samplerate: int) -> bool:
        """Process an audio frame and update internal state.

        Each call accumulates the frame and updates the silence counter.
        When silence exceeds the threshold and an utterance was in progress,
        internal state is reset and the method returns True.

        Args:
            frame:      Raw PCM 16-bit little-endian audio chunk.
            samplerate: Sample rate in Hz.

        Returns:
            True if the utterance ended (turn-end detected),
            False otherwise.
        """
        # Frame duration in ms (PCM 16-bit = 2 bytes/sample)
        num_samples = len(frame) // 2
        frame_ms = num_samples * 1000 // samplerate if samplerate > 0 else 0

        is_speech = self._vad.is_speech(frame, samplerate)

        if is_speech:
            # Speech detected: reset silence counter, accumulate frame
            self._speech_started = True
            self._silence_ms = 0
            self._accumulated.append(frame)
        else:
            # Silence: still accumulate frame (for context), update counter
            self._accumulated.append(frame)
            if self._speech_started:
                self._silence_ms += frame_ms

        # Check turn-end: prolonged silence after at least one speech frame
        if self._speech_started and self._silence_ms >= self._silence_threshold_ms:
            now = time.monotonic()
            if (self._last_endpoint_ts > 0.0 and
                    (now - self._last_endpoint_ts) * 1000 < self._debounce_ms):
                # Spurious endpoint: arrives within debounce window from previous.
                # Silently suppressed to avoid double turn-end (US-155 P1).
                self._reset()
                return False
            # Accepted endpoint: update timestamp and signal turn-end.
            self._last_endpoint_ts = now
            self._reset()
            return True

        return False

    def get_accumulated(self) -> list[bytes]:
        """Return frames accumulated since last reset.

        Returns:
            List of accumulated audio frames (defensive copy).
        """
        return list(self._accumulated)

    def reset(self) -> None:
        """Reset accumulation state (e.g. on key release in F1 or at start of CATTURA).

        Resets: _accumulated, _speech_started, _silence_ms.
        Does NOT reset _last_endpoint_ts: clearing it would remove debounce protection
        between turn N (end of PARLATO) and start of CATTURA turn N+1, where the
        audio/echo queue generates the spurious endpoint that is the root cause of US-155 P1.
        """
        self._reset()

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Reset internal state after turn-end or on explicit request."""
        self._accumulated = []
        self._speech_started = False
        self._silence_ms = 0
        # Reset underlying VAD model state (e.g. Silero hidden state).
        # Optional: called only if VAD exposes reset().
        if hasattr(self._vad, "reset"):
            self._vad.reset()  # type: ignore[union-attr]
