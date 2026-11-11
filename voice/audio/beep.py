"""voice/audio/beep.py — Beep di conferma wake word e ricezione messaggio.

Genera toni sinusoidali float32 per due eventi distinti:
  - generate_ready_beep(): 880 Hz singolo — "pronto ad ascoltare" (wake word)
  - generate_ack_beep():   440→660 Hz doppio — "messaggio ricevuto" (dopo endpointing)

Riproduzione:
  - play_beep(audio, sr): usa afplay (macOS) → CoreAudio gestisce BT warmup;
    fallback sounddevice su piattaforme non-macOS.

Nessuna dipendenza esterna: solo numpy (+ stdlib wave/tempfile/asyncio).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import wave
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


async def play_beep(audio: np.ndarray, samplerate: int = 22050) -> None:
    """Riproduce un beep audio.

    Su macOS usa afplay (CoreAudio) che gestisce la latenza di startup
    Bluetooth (Jabra, AirPods, ecc.) meglio di PortAudio/sounddevice.
    Su altre piattaforme usa sounddevice come fallback.

    Args:
        audio:      Array float32 mono (shape N,) con il segnale del beep.
        samplerate: Sample rate Hz (default 22050).
    """
    if sys.platform == "darwin":
        await _play_via_afplay(audio, samplerate)
    else:
        await _play_via_sounddevice(audio, samplerate)


async def _play_via_afplay(audio: np.ndarray, samplerate: int) -> None:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        fname = f.name
    try:
        with wave.open(fname, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(pcm.tobytes())
        proc = await asyncio.create_subprocess_exec(
            "afplay", fname,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("play_beep: afplay fallito: %s", exc)
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass


async def _play_via_sounddevice(audio: np.ndarray, samplerate: int) -> None:
    try:
        import sounddevice as sd  # noqa: PLC0415
        await asyncio.to_thread(sd.play, audio, samplerate)
        await asyncio.to_thread(sd.wait)
    except Exception as exc:  # noqa: BLE001
        log.warning("play_beep: sounddevice fallito: %s", exc)


_BT_PREAMBLE_MS = 700  # Silenzio iniziale per svegliare driver Bluetooth (Jabra Evolve 65: ~500ms)


def generate_ack_beep(
    sample_rate: int = 22050,
) -> np.ndarray:
    """Doppio-bip (440 Hz + 660 Hz) per confermare la ricezione del messaggio.

    Suona subito dopo l'endpointing VAD, mentre STT e LLM elaborano.
    Il tono ascendente (440→660) distingue questo evento dal ready_beep (880 Hz).
    Include preamble silenzioso per device Bluetooth (Jabra, AirPods, ecc.).
    """
    def _tone(freq: float, ms: int, vol: float = 0.65) -> np.ndarray:
        n = int(sample_rate * ms / 1000)
        t = np.linspace(0.0, ms / 1000.0, n, endpoint=False)
        tone = (vol * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)
        fade = min(int(sample_rate * 0.008), n // 4)
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        tone[:fade] *= ramp
        tone[-fade:] *= ramp[::-1]
        return tone

    preamble = np.zeros(int(sample_rate * _BT_PREAMBLE_MS / 1000), dtype=np.float32)
    gap = np.zeros(int(sample_rate * 0.04), dtype=np.float32)
    return np.concatenate([preamble, _tone(440, 80), gap, _tone(660, 80)])


def generate_ready_beep(
    freq: float = 880.0,
    duration_ms: int = 180,
    volume: float = 0.75,
    sample_rate: int = 22050,
) -> np.ndarray:
    """Genera un tono sinusoidale float32 normalizzato.

    Args:
        freq:        Frequenza in Hz (default 880 = La5, tono "ready" naturale).
        duration_ms: Durata in ms (default 180 ms).
        volume:      Ampiezza [0.0–1.0] (default 0.75, con preamble BT).
        sample_rate: Sample rate Hz (default 22050, compatibile con piper-tts output).

    Returns:
        np.ndarray float32 mono normalizzato, shape (N,).
    """
    n_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0.0, duration_ms / 1000.0, n_samples, endpoint=False)
    tone = volume * np.sin(2.0 * np.pi * freq * t).astype(np.float32)

    # Fade-in e fade-out 15 ms per evitare click
    fade_n = int(sample_rate * 0.015)
    fade_n = min(fade_n, n_samples // 4)
    ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
    tone[:fade_n] *= ramp
    tone[-fade_n:] *= ramp[::-1]

    # Preamble silenzioso per device Bluetooth (Jabra, AirPods, ecc.)
    preamble = np.zeros(int(sample_rate * _BT_PREAMBLE_MS / 1000), dtype=np.float32)
    return np.concatenate([preamble, tone])


def generate_error_beep(
    sample_rate: int = 22050,
) -> np.ndarray:
    """Tono discendente (330→220 Hz) per segnalare errore TTS/playback.

    Suona quando piper-tts o il dispositivo audio fallisce, per evitare
    silenzio non comunicativo (feedback #15 sessione E2E 2026-07-10).
    """
    def _tone(freq: float, ms: int, vol: float = 0.60) -> np.ndarray:
        n = int(sample_rate * ms / 1000)
        t = np.linspace(0.0, ms / 1000.0, n, endpoint=False)
        tone = (vol * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)
        fade = min(int(sample_rate * 0.010), n // 4)
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        tone[:fade] *= ramp
        tone[-fade:] *= ramp[::-1]
        return tone

    preamble = np.zeros(int(sample_rate * _BT_PREAMBLE_MS / 1000), dtype=np.float32)
    gap = np.zeros(int(sample_rate * 0.05), dtype=np.float32)
    return np.concatenate([preamble, _tone(330, 120), gap, _tone(220, 180)])
