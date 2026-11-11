"""Tests for Endpointer debounce logic — TSK-334 (US-155).

Covers 3 acceptance criteria:
  AC2 — debounce active (200ms < 500ms): second endpoint suppressed (False)
  AC3 — debounce inactive (600ms >= 500ms): second endpoint accepted (True)
  AC5 — nominal path: first endpoint (_last_endpoint_ts == 0.0) returned True
        without debounce overhead (branch skipped via short-circuit)

No hardware required: the VAD dependency is replaced with a MagicMock and
time.monotonic is patched at the module level to control elapsed time exactly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from voice.vad.endpointing import Endpointer


# ---------------------------------------------------------------------------
# Constants for a deterministic, hardware-free 10 ms frame
# ---------------------------------------------------------------------------

_SAMPLERATE = 16_000
# 160 samples × 2 bytes/sample (PCM 16-bit) = 320 bytes → 10 ms at 16 kHz
_FRAME_10MS: bytes = b"\x00\x00" * 160


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_endpointer(
    debounce_ms: int = 500,
    silence_threshold_ms: int = 100,
) -> Endpointer:
    """Return an Endpointer backed by a silent-only mock VAD.

    The mock VAD always returns False from is_speech(), so every frame fed
    to the Endpointer is treated as silence.  Internal state is then
    manipulated directly via _prime_for_endpoint() to trigger endpoints
    without going through real VAD processing.
    """
    vad = MagicMock()
    vad.is_speech.return_value = False  # always silence
    return Endpointer(
        vad=vad,
        silence_threshold_ms=silence_threshold_ms,
        debounce_ms=debounce_ms,
    )


def _prime_for_endpoint(endpointer: Endpointer) -> None:
    """Inject minimal internal state so the next feed_frame() fires an endpoint.

    Sets _speech_started = True and _silence_ms to the threshold value.
    When feed_frame() is then called with a silence frame (is_speech=False),
    _silence_ms grows by one frame_ms (10 ms), satisfying
    _silence_ms >= _silence_threshold_ms, and the endpoint check runs.
    """
    endpointer._speech_started = True
    endpointer._silence_ms = endpointer._silence_threshold_ms


# ---------------------------------------------------------------------------
# AC2 — Debounce active: second endpoint within 200 ms < 500 ms → suppressed
# ---------------------------------------------------------------------------


def test_debounce_suppresses_endpoint_within_window() -> None:
    """AC2: a second endpoint arriving 200 ms after the first (200 ms < debounce_ms=500 ms)
    must be silently suppressed — feed_frame() returns False."""
    endpointer = _make_endpointer(debounce_ms=500)
    t0 = 1_000.0  # arbitrary reference monotonic timestamp (seconds)

    with patch("voice.vad.endpointing.time") as mock_time:
        # --- First endpoint at T0 ---
        mock_time.monotonic.return_value = t0
        _prime_for_endpoint(endpointer)
        result_first = endpointer.feed_frame(_FRAME_10MS, _SAMPLERATE)
        assert result_first is True, "Il primo endpoint deve essere accettato"

        # --- Second endpoint at T0 + 200 ms (inside the debounce window) ---
        mock_time.monotonic.return_value = t0 + 0.200
        _prime_for_endpoint(endpointer)
        result_second = endpointer.feed_frame(_FRAME_10MS, _SAMPLERATE)
        assert result_second is False, (
            "Il secondo endpoint a 200 ms < 500 ms deve essere soppresso dal debounce"
        )


# ---------------------------------------------------------------------------
# AC3 — Debounce inactive: second endpoint after 600 ms >= 500 ms → accepted
# ---------------------------------------------------------------------------


def test_debounce_accepts_endpoint_after_window() -> None:
    """AC3: a second endpoint arriving 600 ms after the first (600 ms >= debounce_ms=500 ms)
    must be accepted — feed_frame() returns True."""
    endpointer = _make_endpointer(debounce_ms=500)
    t0 = 1_000.0

    with patch("voice.vad.endpointing.time") as mock_time:
        # --- First endpoint at T0 ---
        mock_time.monotonic.return_value = t0
        _prime_for_endpoint(endpointer)
        result_first = endpointer.feed_frame(_FRAME_10MS, _SAMPLERATE)
        assert result_first is True, "Il primo endpoint deve essere accettato"

        # --- Second endpoint at T0 + 600 ms (outside the debounce window) ---
        mock_time.monotonic.return_value = t0 + 0.600
        _prime_for_endpoint(endpointer)
        result_second = endpointer.feed_frame(_FRAME_10MS, _SAMPLERATE)
        assert result_second is True, (
            "Il secondo endpoint a 600 ms >= 500 ms deve essere accettato"
        )


# ---------------------------------------------------------------------------
# AC5 — Nominal path: first endpoint with _last_endpoint_ts == 0.0 → True
# ---------------------------------------------------------------------------


def test_first_endpoint_accepted_without_debounce_check() -> None:
    """AC5: at startup _last_endpoint_ts == 0.0, so the debounce branch
    (`_last_endpoint_ts > 0.0 and ...`) is short-circuited and skipped entirely.
    feed_frame() returns True on the very first endpoint with zero overhead."""
    endpointer = _make_endpointer(debounce_ms=500)

    # Verify initial state: the debounce branch condition must be bypassed
    assert endpointer._last_endpoint_ts == 0.0, (
        "Lo stato iniziale deve avere _last_endpoint_ts == 0.0 (AC5)"
    )

    with patch("voice.vad.endpointing.time") as mock_time:
        mock_time.monotonic.return_value = 1_000.0

        _prime_for_endpoint(endpointer)
        result = endpointer.feed_frame(_FRAME_10MS, _SAMPLERATE)

    assert result is True, (
        "Il primo endpoint deve essere sempre accettato senza check di debounce"
    )
    # After a successful endpoint, _last_endpoint_ts must have been updated
    assert endpointer._last_endpoint_ts == 1_000.0, (
        "_last_endpoint_ts deve essere aggiornato al valore di time.monotonic() "
        "dopo l'endpoint accettato"
    )
