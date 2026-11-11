"""voice/tools/record_samples.py — CLI to record wake word audio samples.

Records N samples of the keyword (default: "Prometeus") and saves them
in voice/wake_word_samples/<keyword>/sample_NN.wav, ready for use
by WakeWordDetector.

Usage:
    python voice/tools/record_samples.py
    python voice/tools/record_samples.py --keyword prometeus --n-samples 5 --duration 2
    python voice/tools/record_samples.py --output-dir /percorso/custom

Dependencies:
    sounddevice  — pip install -e ".[voice]"
    numpy        — included in the voice group

WAV files are saved as 16kHz, mono, int16, compatible with
openwakeword and WakeWordDetector.
"""
from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np

# Fixed audio parameters: compatible with openWakeWord and WakeWordDetector
_SAMPLERATE: int = 16000   # Hz
_CHANNELS: int = 1         # mono


def _record_single(duration: float, samplerate: int = _SAMPLERATE) -> np.ndarray:
    """Record for `duration` seconds and return a mono float32 array.

    Args:
        duration:   Recording duration in seconds.
        samplerate: Sample rate in Hz (default 16000).

    Returns:
        Mono float32 array of shape (N,) with N = duration * samplerate.

    Raises:
        ImportError: If sounddevice is not installed.
    """
    try:
        import sounddevice as sd  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "sounddevice non trovato. "
            "Installa le dipendenze vocali: pip install -e '.[voice]'"
        ) from exc

    n_frames = int(duration * samplerate)
    recording = sd.rec(
        n_frames,
        samplerate=samplerate,
        channels=_CHANNELS,
        dtype="float32",
    )
    sd.wait()  # blocks until recording completes

    # Shape: (n_frames, 1) → (n_frames,) mono
    return recording.ravel()


def _save_wav(audio: np.ndarray, path: Path, samplerate: int = _SAMPLERATE) -> None:
    """Save a mono float32 array as an int16 WAV file.

    Uses stdlib only (wave), no external dependencies.

    Args:
        audio:      Mono float32 array of shape (N,), normalized to [-1.0, 1.0].
        path:       Destination path (directory must exist).
        samplerate: Sample rate in Hz (default 16000).
    """
    audio_int16 = (audio * 32767.0).clip(-32768, 32767).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)        # mono
        wf.setsampwidth(2)        # int16 = 2 bytes per sample
        wf.setframerate(samplerate)
        wf.writeframes(audio_int16.tobytes())


def main() -> None:
    """Entry point for the record_samples CLI."""
    parser = argparse.ArgumentParser(
        description="Registra sample audio della wake word per WakeWordDetector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Esempio:\n"
            "  python voice/tools/record_samples.py\n"
            "  python voice/tools/record_samples.py --keyword prometeus --n-samples 5 --duration 2\n"
        ),
    )
    parser.add_argument(
        "--keyword",
        default="prometeus",
        help="Parola chiave da registrare (default: prometeus).",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=5,
        dest="n_samples",
        help="Numero di sample da registrare (default: 5).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Durata di ciascuna registrazione in secondi (default: 2.0).",
    )
    parser.add_argument(
        "--output-dir",
        default="voice/wake_word_samples",
        dest="output_dir",
        help="Directory radice dove salvare i sample (default: voice/wake_word_samples).",
    )
    args = parser.parse_args()

    keyword: str = args.keyword
    n_samples: int = args.n_samples
    duration: float = args.duration
    output_dir = Path(args.output_dir)

    # Create destination directory if it does not exist
    save_dir = output_dir / keyword
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nRegistreremo {n_samples} sample della parola '{keyword}'")
    print(f"Durata per sample: {duration}s — frequenza: {_SAMPLERATE} Hz, mono")
    print(f"Directory di salvataggio: {save_dir.resolve()}")
    print()

    for i in range(1, n_samples + 1):
        print(f"Sample {i}/{n_samples} — premi INVIO e pronuncia subito '{keyword}'", end="")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\nInterrotto dall'utente.")
            sys.exit(1)

        print(f"  Registrazione in corso ({duration}s)...", end=" ", flush=True)

        try:
            audio = _record_single(duration)
        except ImportError as exc:
            print(f"\nERRORE: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(f"\nERRORE durante la registrazione: {exc}", file=sys.stderr)
            sys.exit(1)

        filename = f"sample_{i:02d}.wav"
        save_path = save_dir / filename
        _save_wav(audio, save_path)

        actual_duration = len(audio) / _SAMPLERATE
        print(f"salvato (durata: {actual_duration:.1f}s)")

    print(f"\nCampioni salvati in {save_dir.resolve()}/")


if __name__ == "__main__":
    main()
