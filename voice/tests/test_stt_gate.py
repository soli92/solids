"""Test gate STT strutturale US-169 EP-046.

Verifica:
  TC1 — AC1: gate primario scarta segmento ad alta no_speech_prob e compression_ratio
  TC2 — AC2: segmento parlato reale accettato
  TC3 — AC3: metadati OK ma testo in blacklist → scartato dalla blacklist secondaria
  TC4 — AC4: log WARNING con metadati per ogni segmento (scartato e accettato)
  TC5 — AC5: override soglie via config
  TC6 — AC6: commento calibrazione presente nel sorgente voice/config.py

Nessun hardware audio, nessun modello STT reale — segmenti mock via SimpleNamespace.
"""
import logging
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice.stt.faster_whisper_stt import FasterWhisperSTT


# ---------------------------------------------------------------------------
# faster-whisper segment mock fixture
# ---------------------------------------------------------------------------

def make_segment(no_speech_prob: float, compression_ratio: float, text: str):
    return SimpleNamespace(
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
        text=text,
    )


def _make_stt_with_segments(segments, threshold_nsp=0.6, threshold_cr=2.4):
    """Crea FasterWhisperSTT con modello mock che restituisce i segmenti dati."""
    stt = FasterWhisperSTT(
        model_size="tiny",
        language="it",
        no_speech_prob_threshold=threshold_nsp,
        compression_ratio_threshold=threshold_cr,
    )
    model_mock = MagicMock()
    model_mock.transcribe.return_value = (segments, MagicMock())
    stt._model = model_mock
    return stt


# ---------------------------------------------------------------------------
# TC1 — AC1: primary gate discards segment (high no_speech_prob AND high compression_ratio)
# ---------------------------------------------------------------------------

def test_tc1_gate_primario_scarta_segmento():
    """Segmento no_speech_prob=0.85, compression_ratio=7.7 → scartato prima della blacklist."""
    seg = make_segment(no_speech_prob=0.85, compression_ratio=7.7, text="Qualcosa di silenzioso")
    stt = _make_stt_with_segments([seg])

    audio = np.zeros(16000, dtype=np.float32)
    result = stt._transcribe_sync(audio, 16000)

    assert result == "", f"Atteso stringa vuota, ottenuto: {result!r}"


# ---------------------------------------------------------------------------
# TC2 — AC2: segmento parlato reale accettato
# ---------------------------------------------------------------------------

def test_tc2_segmento_parlato_accettato():
    """Segmento no_speech_prob=0.1, compression_ratio=1.5 → accettato."""
    seg = make_segment(no_speech_prob=0.1, compression_ratio=1.5, text="Ciao come stai")
    stt = _make_stt_with_segments([seg])

    audio = np.zeros(16000, dtype=np.float32)
    result = stt._transcribe_sync(audio, 16000)

    assert "Ciao come stai" in result


# ---------------------------------------------------------------------------
# TC3 — AC3: metadati OK ma testo in blacklist → scartato dalla blacklist secondaria
# ---------------------------------------------------------------------------

def test_tc3_blacklist_secondaria():
    """Segmento con metadati OK ma testo hallucination → scartato dalla blacklist in transcribe()."""
    seg = make_segment(
        no_speech_prob=0.1,
        compression_ratio=1.5,
        text="Sottotitoli a cura di QTSS Prometeus",
    )
    stt = _make_stt_with_segments([seg])

    # _transcribe_sync does not apply blacklist (secondary layer in transcribe())
    raw = stt._transcribe_sync(np.zeros(16000, dtype=np.float32), 16000)
    assert "Sottotitoli" in raw, "Gate primario non deve scartare questo segmento"

    # Verify blacklist in transcribe() discards it (simulates full path)
    audio_bytes = (np.zeros(16000, dtype=np.float32) * 32767).astype(np.int16).tobytes()
    import asyncio

    # Patch _transcribe_sync to return hallucination text
    with patch.object(stt, "_transcribe_sync", return_value="Sottotitoli a cura di qtss"):
        final = asyncio.run(stt.transcribe(
            (np.ones(16000, dtype=np.float32) * 0.1 * 32767).astype(np.int16).tobytes(),
            sample_rate=16000,
        ))
    assert final == "", f"La blacklist secondaria doveva scartare il testo, ottenuto: {final!r}"


# ---------------------------------------------------------------------------
# TC4 — AC4: log WARNING with metadata per segment (discarded and accepted)
# ---------------------------------------------------------------------------

def test_tc4_log_warning_per_segmento(caplog):
    """Ogni segmento (scartato e accettato) deve produrre un log WARNING con metadati."""
    segments = [
        make_segment(no_speech_prob=0.85, compression_ratio=7.7, text="silenzio"),
        make_segment(no_speech_prob=0.1, compression_ratio=1.5, text="parola"),
    ]
    stt = _make_stt_with_segments(segments)

    with caplog.at_level(logging.WARNING, logger="voice.stt.faster_whisper_stt"):
        stt._transcribe_sync(np.zeros(16000, dtype=np.float32), 16000)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 2, f"Attesi 2 WARNING, ottenuti {len(warning_records)}"

    for record in warning_records:
        assert "no_speech_prob" in record.message
        assert "compression_ratio" in record.message
        assert "is_speech" in record.message


# ---------------------------------------------------------------------------
# TC5 — AC5: threshold override via config
# ---------------------------------------------------------------------------

def test_tc5_override_soglie_custom():
    """Soglie custom no_speech_prob=0.5, compression_ratio=2.0 — segmento borderline scartato."""
    # no_speech_prob=0.55 is above custom threshold 0.5 but below default 0.6 → discarded
    seg = make_segment(no_speech_prob=0.55, compression_ratio=1.5, text="borderline")
    stt = _make_stt_with_segments([seg], threshold_nsp=0.5, threshold_cr=2.0)

    result = stt._transcribe_sync(np.zeros(16000, dtype=np.float32), 16000)
    assert result == "", f"Con soglia custom 0.5 il segmento doveva essere scartato, ottenuto: {result!r}"

    # With default thresholds (0.6) same segment would be accepted
    stt_default = _make_stt_with_segments([seg])
    result_default = stt_default._transcribe_sync(np.zeros(16000, dtype=np.float32), 16000)
    assert "borderline" in result_default


# ---------------------------------------------------------------------------
# TC6 — AC6: calibration comment present in voice/config.py source
# ---------------------------------------------------------------------------

def test_tc6_commento_calibrazione_in_config():
    """Il sorgente voice/config.py deve contenere 'NON calibrato' vicino a compression_ratio_threshold."""
    config_path = pathlib.Path(__file__).parent.parent / "config.py"
    content = config_path.read_text(encoding="utf-8")
    assert "NON calibrato" in content, (
        "Il commento di calibrazione obbligatorio manca in voice/config.py "
        "(C6 ADR-EP046-001)"
    )
