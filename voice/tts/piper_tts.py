"""voice/tts/piper_tts.py — piper-tts wrapper (local Italian neural voices).

The module is importable without piper-tts installed: the package is
imported lazily inside __init__ to avoid ImportError on environments
without extras[voice].

Recommended async usage (from state_machine / router):
    audio: np.ndarray = await asyncio.to_thread(tts.synthesize, text)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np

from voice.tts.base import TTSBase


_DOWNLOAD_HINT = (
    "Scarica il modello piper-tts italiano da:\n"
    "  https://huggingface.co/rhasspy/piper-voices/tree/main/it/it_IT\n"
    "Esempio (modello riccardo medium):\n"
    "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "it/it_IT/riccardo/medium/it_IT-riccardo-medium.onnx\n"
    "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "it/it_IT/riccardo/medium/it_IT-riccardo-medium.onnx.json\n"
    "Poi instanzia:\n"
    "  PiperTTS(voice='it_IT-riccardo-medium', model_dir='<directory>')\n"
    "oppure imposta la variabile d'ambiente PIPER_MODEL_DIR."
)


class PiperTTS(TTSBase):
    """Local Italian TTS via piper-tts (neural ONNX models).

    Implements TTSBase returning normalized mono PCM float32 audio.
    piper-tts generates PCM int16 internally; conversion to float32 happens
    in synthesize().

    Args:
        voice: Voice model name (without '.onnx' extension).
               Default: 'it_IT-riccardo-medium'.
        model_dir: Directory containing <voice>.onnx (and <voice>.onnx.json).
                   If None, uses the PIPER_MODEL_DIR environment variable;
                   if that is also unset, uses the current directory.

    Raises:
        ImportError: if the piper-tts package is not installed.
        FileNotFoundError: if the .onnx file is not found in model_dir.

    Recommended async usage:
        audio: np.ndarray = await asyncio.to_thread(tts.synthesize, text)
    """

    def __init__(
        self,
        voice: str = "it_IT-riccardo-medium",
        model_dir: Optional[str] = None,
    ) -> None:
        # Lazy import — not at module level to avoid ImportError on environments
        # without extras[voice]. Raised with a clear message if missing.
        try:
            import piper  # noqa: F401 — verify package presence
        except ImportError as exc:
            raise ImportError(
                "Il pacchetto piper-tts non e' installato.\n"
                "Installa con: pip install 'soli-multi-agents-factory[voice]'\n"
                "o direttamente: pip install piper-tts"
            ) from exc

        self._voice_name = voice
        self._model_dir = Path(
            model_dir or os.environ.get("PIPER_MODEL_DIR", ".")
        ).expanduser()
        self._piper_voice = self._load_voice()

    def _load_voice(self):
        """Load the model from disk via piper.PiperVoice.load().

        Raises:
            FileNotFoundError: with download hint if the .onnx file is missing.
        """
        import piper

        model_path = self._model_dir / f"{self._voice_name}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modello piper-tts non trovato: {model_path}\n"
                f"{_DOWNLOAD_HINT}"
            )
        return piper.PiperVoice.load(str(model_path))

    def synthesize(self, text: str) -> np.ndarray:
        """Synthesize *text* into normalized mono PCM float32 audio.

        Synchronous CPU-bound method. Always call from a separate thread:
            audio = await asyncio.to_thread(tts.synthesize, text)

        To reduce perceived latency, pass individual sentences extracted with
        voice.tts.sentence_splitter.split_into_sentences(full_text).

        Args:
            text: Text to synthesize (ideally a single sentence).

        Returns:
            np.ndarray float32 mono normalized to [-1.0, 1.0].
            Empty array (shape (0,)) if synthesis produces no output.
        """
        # piper >= 1.4: PiperVoice.synthesize() → Iterable[AudioChunk]
        # AudioChunk.audio_int16_bytes = PCM int16 LE mono
        # AudioChunk.sample_rate = actual rate (typically 22050 Hz)
        raw_chunks: list[bytes] = []
        for chunk in self._piper_voice.synthesize(text):
            raw_chunks.append(chunk.audio_int16_bytes)
            self._sample_rate = chunk.sample_rate  # exposed as attribute

        raw_bytes = b"".join(raw_chunks)
        if not raw_bytes:
            return np.array([], dtype=np.float32)

        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        return audio_int16.astype(np.float32) / 32768.0

    @property
    def sample_rate(self) -> int:
        """Effective model sample rate (set after first synthesize)."""
        return getattr(self, "_sample_rate", 22050)
