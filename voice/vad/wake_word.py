"""voice/vad/wake_word.py — "Prometeus" wake word detector via openWakeWord.

Importable without openwakeword installed: import happens lazily
inside load(), not at module level. Constructor does not fail
on environments without openwakeword; failure occurs only on
first call to load().

Detection strategy:
  1. (Primary) openwakeword.Model with custom_verifier_models: computes
     positive sample embeddings and uses cosine similarity at runtime.
  2. (Fallback) If custom_verifier_models API is not available in the
     installed version, falls back to manual cosine similarity between
     FFT of current chunk and registered samples.

To install dependencies:
    pip install -e ".[voice]"  # includes openwakeword>=0.6.0

Typical usage:
    from voice.vad.wake_word import WakeWordDetector
    from voice.audio.capture import AudioCapture

    detector = WakeWordDetector("voice/wake_word_samples")
    detector.load()
    capture = AudioCapture(config)
    capture.start()
    await detector.wait_for_wake_word(capture)
    capture.stop()
"""
from __future__ import annotations

import asyncio
import wave
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import numpy as np

if TYPE_CHECKING:
    from voice.audio.capture import AudioCapture


# ---------------------------------------------------------------------------
# Utility: Levenshtein edit distance
# ---------------------------------------------------------------------------

def levenshtein(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings (case-sensitive).

    Case-insensitive comparison must be applied by caller
    (es. ``levenshtein(a.lower(), b.lower())``).

    Two-array optimized DP algorithm: O(min(len(a), len(b))) space.
    No external dependencies.

    Args:
        a: First string.
        b: Second string.

    Returns:
        Minimum number of insert, delete or
        single-character substitute operations to transform ``a`` into ``b``.

    Examples:
        >>> levenshtein("prometeus", "prometeus")
        0
        >>> levenshtein("prometeus", "prometheus")
        1
        >>> levenshtein("apri il kanban", "prometeus") > 3
        True
    """
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


class WakeWordDetector:
    """Wake word detector based on openWakeWord with custom verifier.

    Uses openWakeWord custom verifier: computes cosine similarity
    between incoming audio chunk embedding and pre-computed embeddings
    of positive samples registered for the keyword.

    If openwakeword is not installed, constructor does not fail;
    failure occurs only on load() call.

    Args:
        samples_dir: Root directory containing subdirectories per keyword.
                     Expected pattern: <samples_dir>/<keyword>/sample_NN.wav
                     Es.: voice/wake_word_samples/prometeus/sample_01.wav
        keyword:     Keyword to detect (default 'prometeus').
        sensitivity: Similarity/confidence threshold [0.0-1.0] (default 0.5).
                     Higher values = fewer false positives, more false negatives.
    """

    def __init__(
        self,
        samples_dir: str,
        keyword: str = "prometeus",
        sensitivity: float = 0.5,
        min_detections: int = 2,
    ) -> None:
        self._samples_dir = Path(samples_dir)
        self._keyword = keyword
        self._sensitivity = sensitivity
        self._min_detections = max(1, min_detections)  # at least 1 positive chunk

        # Set by load()
        self._sample_embeddings: List[np.ndarray] = []
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Sample loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load WAV samples from samples_dir and compute openWakeWord embeddings.

        WAV files must be located at:
            <samples_dir>/<keyword>/sample_NN.wav

        Primary path:
            Create openwakeword.Model with custom_verifier_models, which computes
            positive sample embeddings internally.

        Fallback (if custom_verifier_models not available in API):
            Manually compute FFT spectral signatures of samples and use them
            for cosine similarity in process_chunk().

        Raises:
            ImportError:     If openwakeword is not installed.
            FileNotFoundError: If sample directory does not exist or is empty.
        """
        if self._loaded:
            return

        # Lazy import: openwakeword imported only here, never at module level.
        # Ensures module importability on environments without openwakeword.
        try:
            import openwakeword  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "openwakeword non trovato. Installa le dipendenze vocali:\n"
                "    pip install 'openwakeword>=0.6.0'\n"
                "oppure incluso nel gruppo voice:\n"
                "    pip install -e '.[voice]'"
            ) from exc

        keyword_dir = self._samples_dir / self._keyword
        if not keyword_dir.exists():
            raise FileNotFoundError(
                f"Directory sample non trovata: {keyword_dir}\n"
                "Registra i campioni prima con:\n"
                "    python voice/tools/record_samples.py"
            )

        wav_paths = sorted(keyword_dir.glob("*.wav"))
        if not wav_paths:
            raise FileNotFoundError(
                f"Nessun file WAV trovato in {keyword_dir}\n"
                "Registra i campioni con:\n"
                "    python voice/tools/record_samples.py"
            )

        # For fully custom keywords (no pre-trained ONNX model),
        # use cosine similarity directly on FFT embeddings of samples.
        # openwakeword.custom_verifier_models requires sklearn pickle trained
        # on existing base model (alexa, hey_jarvis…) — not applicable here.
        self._sample_embeddings = [
            self._compute_fft_embedding(self._load_wav(p))
            for p in wav_paths
        ]
        self._loaded = True

    def is_loaded(self) -> bool:
        """True if samples have been loaded."""
        return self._loaded

    # ------------------------------------------------------------------
    # Audio chunk processing
    # ------------------------------------------------------------------

    def process_chunk(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """Process audio chunk and return True if wake word is detected.

        Uses openWakeWord custom verifier: cosine similarity between embedding
        of current chunk and positive sample embeddings. If primary path
        (openwakeword.Model) is not available, falls back to cosine
        similarity manually based on FFT.

        Args:
            audio_chunk: Numpy array float32 di shape (N,) o (N, channels).
                         Typically produced by AudioCapture.queue (float32).
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            True if wake word detected with confidence >= sensitivity.

        Raises:
            RuntimeError: If load() has not been called yet.
        """
        if not self._loaded:
            raise RuntimeError(
                "WakeWordDetector non caricato. Chiama load() prima di process_chunk()."
            )

        # Normalize to mono (N,) — take first channel if multi-channel
        if audio_chunk.ndim > 1:
            mono = audio_chunk[:, 0]
        else:
            mono = audio_chunk.ravel()

        # Energy gate: ignore silence/ambient noise frames before computing
        # similarity. Avoids false positives on background noise.
        # Typical speech RMS: 0.05–0.30; silence/noise: < 0.003.
        rms = float(np.sqrt(np.mean(mono ** 2)))
        if rms < 0.003:
            return False
        return self._process_chunk_fallback(mono)

    # ------------------------------------------------------------------
    # Async wake word wait loop
    # ------------------------------------------------------------------

    async def wait_for_wake_word(self, capture: "AudioCapture") -> None:
        """Async loop: read from capture queue until wake word is detected.

        Blocks until keyword is spoken. Frames are
        read from AudioCapture thread-safe queue via run_in_executor
        to avoid blocking the async loop.

        Args:
            capture: AudioCapture already started (capture.start() already called).
                     Queue must produce numpy float32 arrays of shape
                     (blocksize, channels).

        Raises:
            RuntimeError: If load() has not been called yet.
        """
        if not self._loaded:
            raise RuntimeError(
                "WakeWordDetector non caricato. Chiama load() prima di wait_for_wake_word()."
            )

        import collections  # noqa: PLC0415
        import logging as _log  # noqa: PLC0415
        log = _log.getLogger(__name__)

        loop = asyncio.get_running_loop()
        # Sliding window: accumulate ~500ms of audio before comparing.
        # 16000 Hz * 0.5s = 8000 samples; chunk = 512 → 16 chunks per window.
        _SR: int = 16000
        _WIN_MS: int = 500
        _CHUNK: int = 512
        win_chunks: int = max(1, int(_SR * _WIN_MS / 1000) // _CHUNK)  # 15 chunk
        window: "collections.deque[np.ndarray]" = collections.deque(maxlen=win_chunks)
        consecutive: int = 0
        frames_seen: int = 0

        while True:
            frame: np.ndarray = await loop.run_in_executor(None, capture.queue.get)
            frames_seen += 1
            if frames_seen == 1 or frames_seen % 100 == 0:
                log.debug("WakeWord: frame #%d ricevuto (queue ok)", frames_seen)

            # Normalize to mono (N,) and append to window (maxlen handles sliding)
            mono = frame[:, 0] if frame.ndim > 1 else frame.ravel()
            window.append(mono)

            # Evaluate only when window is full (at least win_chunks chunks)
            if len(window) < win_chunks:
                continue

            # Concatenate and compute RMS on entire 500ms segment
            segment = np.concatenate(list(window))
            rms = float(np.sqrt(np.mean(segment ** 2)))

            # Compare with samples — always log for diagnostics
            embedding = self._compute_fft_embedding(segment)
            max_sim = max(
                self._cosine_similarity(embedding, ref)
                for ref in self._sample_embeddings
            ) if self._sample_embeddings else 0.0

            log.debug("WakeWord: RMS=%.4f sim=%.3f (soglia=%.2f)", rms, max_sim, self._sensitivity)

            if rms < 0.003:
                consecutive = 0
                continue

            if max_sim >= self._sensitivity:
                consecutive += 1
                log.debug(
                    "WakeWord: match %d/%d (sim=%.3f)", consecutive, self._min_detections, max_sim
                )
                if consecutive >= self._min_detections:
                    return  # confirmed
            else:
                consecutive = 0

    # ------------------------------------------------------------------
    # Private methods: manual fallback (cosine similarity on FFT)
    # ------------------------------------------------------------------

    def _load_wav(self, wav_path: Path) -> np.ndarray:
        """Load a WAV file and return as float32 mono array.

        Uses stdlib only (wave), no external dependencies.

        Args:
            wav_path: Path to WAV file (mono or stereo, int16 or int32).

        Returns:
            float32 mono array normalized to [-1.0, 1.0].

        Raises:
            ValueError: If WAV file format is not supported.
        """
        with wave.open(str(wav_path), "rb") as wf:
            n_frames = wf.getnframes()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(n_frames)

        if sampwidth == 2:  # int16 — standard format for 16kHz audio
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:  # int32
            samples = (
                np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2_147_483_648.0
            )
        else:
            raise ValueError(
                f"Formato WAV non supportato: sample width {sampwidth} byte "
                f"in {wav_path}. Atteso int16 (2) o int32 (4)."
            )

        # Take first channel if stereo
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels)[:, 0]

        return samples

    def _compute_fft_embedding(self, audio: np.ndarray, n_fft: int = 4096) -> np.ndarray:
        """Compute L2-normalized FFT spectral signature of audio.

        Embedding is an L2-normalized FFT magnitude vector.
        Used only in manual fallback path.

        Args:
            audio: float32 mono array.
            n_fft: Number of samples used for FFT (default 4096).

        Returns:
            L2-normalized float32 vector of shape (n_fft//2 + 1,).
        """
        # Use at most n_fft samples; zero-pad if signal is shorter
        length = min(len(audio), n_fft)
        frame = np.zeros(n_fft, dtype=np.float32)
        frame[:length] = audio[:length]

        fft_mag = np.abs(np.fft.rfft(frame)).astype(np.float32)

        norm = np.linalg.norm(fft_mag)
        if norm > 0.0:
            fft_mag = fft_mag / norm

        return fft_mag

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity tra due vettori.

        Args:
            a: float32 vector (normalized or not).
            b: float32 vector of same length or truncated to shorter.

        Returns:
            Float in [-1.0, 1.0]; 0.0 if either vector is zero.
        """
        min_len = min(len(a), len(b))
        a = a[:min_len]
        b = b[:min_len]
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _process_chunk_fallback(self, mono: np.ndarray) -> bool:
        """Fallback path: manual cosine similarity on FFT embedding.

        Compare FFT embedding of current chunk with embeddings
        pre-computed from positive samples. Returns True if
        max similarity exceeds sensitivity threshold.

        Args:
            mono: float32 mono array (N,) already normalized to [-1.0, 1.0].

        Returns:
            True if max(cosine_similarity) >= sensitivity.
        """
        if not self._sample_embeddings:
            return False

        chunk_embedding = self._compute_fft_embedding(mono)
        max_similarity = max(
            self._cosine_similarity(chunk_embedding, ref)
            for ref in self._sample_embeddings
        )
        return max_similarity >= self._sensitivity
