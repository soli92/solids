"""voice/vad/silero_vad.py — Silero VAD wrapper (PyTorch-based).

Importable without torch installed: torch and model import
is lazy (happens on first use via load_model / is_speech).

To install dependencies:
    pip install -e ".[voice]"

Dependency: torch, torchaudio (included in silero-vad)
Model:       snakers4/silero-vad (Torch Hub)
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from voice.vad.base import VADBase

if TYPE_CHECKING:
    # Import for type checking only — not executed at runtime if torch is absent.
    import torch


class SileroVAD(VADBase):
    """VAD based on Silero (snakers4/silero-vad) via PyTorch.

    The model is loaded once on first use (lazy init).
    On environments without torch / silero-vad installed the constructor does not fail;
    failure occurs only on the first call to is_speech() or load_model().

    Args:
        threshold:   VAD confidence threshold (0.0-1.0, default 0.5).
        sample_rate: Expected sample rate (default 16000 Hz).
                     Silero supports 8000 and 16000 Hz.
    """

    SUPPORTED_SAMPLE_RATES = (8000, 16000)

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16000,
    ) -> None:
        if sample_rate not in self.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"SileroVAD supporta solo sample_rate in {self.SUPPORTED_SAMPLE_RATES}, "
                f"ricevuto: {sample_rate}"
            )
        self.threshold = threshold
        self.sample_rate = sample_rate

        # Lazy init — set by load_model()
        self._model = None
        self._get_speech_ts = None
        self._torch = None

    # ------------------------------------------------------------------
    # Explicit load method (usable before is_speech)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset Silero model internal state between turns."""
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception:  # noqa: BLE001
                pass

    def load_model(self, repo: str = "snakers4/silero-vad") -> None:
        """Load Silero VAD model from Torch Hub.

        Called automatically by is_speech() on first use.
        Can be invoked explicitly to anticipate warm-up.

        Args:
            repo: Torch Hub model identifier (default 'snakers4/silero-vad').

        Raises:
            ImportError: If torch is not installed.
        """
        if self._model is not None:
            return  # already loaded

        try:
            import torch  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "torch non e' installato. Per abilitare SileroVAD esegui:\n"
                "    pip install -e '.[voice]'\n"
                "oppure installa torch separatamente: pip install torch"
            ) from exc

        self._torch = torch

        # Path 1: local cache (git clone in torch hub dir) — no network.
        # Path 2: remote torch.hub with SSL bypass (macOS Python 3.12).
        import os as _os, ssl as _ssl  # noqa: PLC0415
        _hub_dir = torch.hub.get_dir()
        _local_candidates = [
            _os.path.join(_hub_dir, "snakers4_silero-vad_main"),
            _os.path.join(_hub_dir, "snakers4_silero-vad_master"),
        ]
        _local_path = next((p for p in _local_candidates if _os.path.isdir(p)), None)

        try:
            if _local_path:
                model, utils = torch.hub.load(
                    repo_or_dir=_local_path,
                    model="silero_vad",
                    source="local",
                    force_reload=False,
                    onnx=False,
                )
            else:
                # Network fallback with SSL bypass
                _orig_ctx = _ssl._create_default_https_context
                _ssl._create_default_https_context = _ssl._create_unverified_context
                try:
                    model, utils = torch.hub.load(
                        repo_or_dir=repo,
                        model="silero_vad",
                        force_reload=False,
                        onnx=False,
                        trust_repo=True,
                    )
                finally:
                    _ssl._create_default_https_context = _orig_ctx
        except Exception as exc:
            raise RuntimeError(
                f"Impossibile caricare il modello Silero VAD da '{repo}'. "
                "Verifica la connessione a internet o usa il path locale. "
                f"Errore originale: {exc}"
            ) from exc

        self._model = model
        # utils[0] = get_speech_timestamps, utils[2] = VADIterator, etc.
        self._get_speech_ts = utils[0]

    # ------------------------------------------------------------------
    # VADBase interface
    # ------------------------------------------------------------------

    def is_speech(self, frame: bytes, samplerate: int) -> bool:
        """Classify audio frame via Silero VAD.

        Args:
            frame:      Raw PCM 16-bit little-endian audio chunk.
            samplerate: Sample rate in Hz (must match constructor value).

        Returns:
            True if VAD confidence exceeds configured threshold.

        Raises:
            ImportError: If torch is not installed (on first use).
            ValueError:  If samplerate does not match configured value.
        """
        if samplerate != self.sample_rate:
            raise ValueError(
                f"SileroVAD configurato per {self.sample_rate} Hz, "
                f"ricevuto frame a {samplerate} Hz."
            )

        # Lazy model load on first use
        if self._model is None:
            self.load_model()

        torch = self._torch  # already imported by load_model()

        # Convert PCM 16-bit bytes → float32 tensor in [-1.0, 1.0]
        num_samples = len(frame) // 2
        samples_i16 = struct.unpack(f"<{num_samples}h", frame)
        audio_tensor = torch.tensor(samples_i16, dtype=torch.float32) / 32768.0

        # Silero requires EXACTLY sr/31.25 samples (512 @ 16kHz, 256 @ 8kHz).
        # Pad or truncate if frame does not have exact size.
        exact_samples = int(samplerate / 31.25)
        n = audio_tensor.shape[0]
        if n < exact_samples:
            audio_tensor = torch.cat([audio_tensor, torch.zeros(exact_samples - n)])
        elif n > exact_samples:
            audio_tensor = audio_tensor[:exact_samples]

        # Inference: confidence for single frame
        with torch.no_grad():
            confidence = self._model(audio_tensor, self.sample_rate).item()

        return confidence >= self.threshold
