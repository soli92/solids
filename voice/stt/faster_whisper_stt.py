"""FasterWhisperSTT — STT implementation via faster-whisper (CTranslate2).

Recommended usage from the state machine (asyncio.to_thread NOT required: transcribe
is already async and internally delegates the blocking call):

    stt = FasterWhisperSTT(model_size="base", language="it")
    text = await stt.transcribe(audio_bytes, sample_rate=16000)

The `faster-whisper` dependency is optional: imported lazily on first transcribe.
If missing, ImportError is raised with installation instructions.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import numpy as np

from voice.stt.base import BaseSTT

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FasterWhisperSTT(BaseSTT):
    """STT based on faster-whisper (Whisper quantized via CTranslate2).

    The model is loaded lazily on the first ``transcribe`` call to honor
    the no-op principle when ``voice_channel.enabled: false`` in factory config.

    Attributes:
        model_size: Whisper model size (tiny | base | small | medium | large).
        language: ISO 639-1 language code passed to the model (default "it").

    Model selection:
        Selected from ``config.stt.model``, passed as ``model_size=`` to the constructor.
        The ``model_size`` parameter must NOT be renamed: it is a stable interface.

    Performance notes (CPU M1, int8):
        medium: STT latency ~2s median; ~0.8s on GPU float16
        small:  STT latency ~1s median; ~0.3s on GPU float16

    Tradeoff:
        ``medium`` significantly reduces WER on factory technical vocabulary
        (artifact names, kanban commands). ``small`` preferable on CPU-only hardware
        with RAM < 8GB.

    Download on-demand:
        If the model is not in the local faster-whisper cache it is downloaded
        automatically on the first ``transcribe``. No action required.

    Reference: ``wiki/runbooks/voice-channel.md`` — "Model selection" section.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "it",
        no_speech_prob_threshold: float = 0.6,
        compression_ratio_threshold: float = 2.4,
    ) -> None:
        self._model_size = model_size
        self._language = language
        self._no_speech_threshold = no_speech_prob_threshold
        self._compression_ratio_threshold = compression_ratio_threshold
        # _model is None until the first transcribe is invoked (lazy load).
        self._model = None

    # ------------------------------------------------------------------
    # Private methods (run in thread via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _ensure_model_loaded(self) -> None:
        """Load WhisperModel if not already loaded.

        Raises explicit ImportError if faster-whisper is not installed.
        This method is called inside _transcribe_sync, which runs on a
        separate thread, so blocking I/O here is safe.
        """
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415 (intentional lazy import)
        except ImportError as exc:
            raise ImportError(
                "faster-whisper non e' installato. "
                "Installa i voice extras con: pip install 'soli-voice[voice]' "
                "oppure: pip install faster-whisper"
            ) from exc

        logger.info(
            "Caricamento modello faster-whisper '%s' (device=cpu, compute_type=int8) ...",
            self._model_size,
        )
        self._model = WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Modello faster-whisper '%s' caricato.", self._model_size)

    def _transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> str:  # noqa: ARG002
        """Run synchronous transcription (invoke via asyncio.to_thread).

        Args:
            audio: Mono float32 numpy array, values in [-1.0, 1.0].
            sample_rate: Sample rate (kept for signature compatibility; faster-whisper
                         assumes 16 kHz internally, but the parameter is retained for
                         future calls that might resample).

        Returns:
            Transcribed text with segments concatenated and separated by a single space.
        """
        self._ensure_model_loaded()
        segments, _info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            condition_on_previous_text=False,  # prevents repetition loops on silence
            no_speech_threshold=0.6,           # internal Whisper threshold (complements primary gate)
        )
        # Primary per-segment gate: discard if no_speech_prob >= threshold OR compression_ratio >= threshold (US-169).
        # Mandatory WARNING log per segment — builds the C6 calibration sample.
        parts = []
        for seg in segments:
            is_speech = (
                getattr(seg, "no_speech_prob", 0.0) < self._no_speech_threshold
                and getattr(seg, "compression_ratio", 0.0) < self._compression_ratio_threshold
            )
            logger.warning(
                "STT segment gate: is_speech=%s no_speech_prob=%.3f compression_ratio=%.3f text=%r",
                is_speech,
                getattr(seg, "no_speech_prob", 0.0),
                getattr(seg, "compression_ratio", 0.0),
                seg.text,
            )
            if not is_speech:
                continue
            if seg.text.strip():
                parts.append(seg.text.strip())
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Public interface (BaseSTT)
    # ------------------------------------------------------------------

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio to text asynchronously.

        Converts PCM int16 bytes to normalized float32 numpy, then delegates the
        blocking faster-whisper call to a separate thread via ``asyncio.to_thread``,
        without blocking the main event loop.

        Args:
            audio_bytes: Raw audio in PCM int16 little-endian format.
                         If empty (b""), returns an empty string immediately.
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            Transcribed text. Empty string if ``audio_bytes`` is empty.

        Raises:
            ImportError: If faster-whisper is not installed (install voice extras).
        """
        if not audio_bytes:
            return ""

        # Convert PCM int16 → normalized float32 numpy in [-1.0, 1.0].
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # Pre-Whisper RMS gate: discard silent audio before invoking the model.
        # Whisper hallucinates text like "Sottotitoli a cura di..." on silence with
        # high confidence (low no_speech_prob), so the energy gate is essential.
        rms = float(np.sqrt(np.mean(audio_float32 ** 2)))
        if rms < 0.008:
            logger.debug("STT: audio scartato — RMS troppo basso (%.4f < 0.008)", rms)
            return ""

        result = await asyncio.to_thread(self._transcribe_sync, audio_float32, sample_rate)

        # Blocklist of known Whisper hallucination patterns (subtitle-style).
        _hallucination_tokens = ("sottotitoli", "iscriviti al canale", "grazie per l'attenzione", "qtss")
        result_lower = result.lower()
        if any(tok in result_lower for tok in _hallucination_tokens):
            logger.debug("STT: testo scartato — hallucination pattern %r", result[:40])
            return ""

        # Post-STT correction dictionary (factory domain terms).
        from voice.stt.corrections import apply_corrections  # noqa: PLC0415
        corrected = apply_corrections(result)
        if corrected != result:
            logger.debug("STT: correzione applicata %r → %r", result[:50], corrected[:50])

        return corrected
