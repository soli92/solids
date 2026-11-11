"""
voice/audio/devices.py — Enumerazione e selezione dei device audio PortAudio.

Tutte le funzioni importano `sounddevice` lazily: il modulo puo' essere
importato senza sounddevice installato; l'ImportError viene sollevato
solo al momento della chiamata effettiva.

Uso tipico:
    from voice.audio.devices import list_devices, get_default_input

    devices = list_devices()
    for d in devices:
        print(d["index"], d["name"], d["channels_in"], d["channels_out"])

    default_mic = get_default_input()
"""
from __future__ import annotations

from typing import Optional


def _import_sd():
    """Import sounddevice lazily con messaggio esplicito se assente."""
    try:
        import sounddevice as sd  # noqa: PLC0415
        return sd
    except ImportError as exc:
        raise ImportError(
            "sounddevice non trovato. "
            "Installa le dipendenze vocali: pip install '.[voice]'"
        ) from exc


def list_devices() -> list[dict]:
    """
    Restituisce la lista di tutti i device audio disponibili via PortAudio.

    Returns:
        Lista di dizionari con le chiavi:
            - index (int)          : indice PortAudio del device
            - name (str)           : nome del device
            - channels_in (int)    : numero di canali di input (0 se solo output)
            - channels_out (int)   : numero di canali di output (0 se solo input)
            - default_samplerate (float): sample rate di default del device
            - hostapi (int)        : indice host API (ALSA, CoreAudio, WASAPI, ecc.)

    Raises:
        ImportError: se sounddevice non e' installato.
    """
    sd = _import_sd()
    raw = sd.query_devices()
    # query_devices() restituisce un DeviceList (list-like di dizionari)
    result: list[dict] = []
    for idx, dev in enumerate(raw):
        result.append(
            {
                "index": idx,
                "name": dev.get("name", ""),
                "channels_in": dev.get("max_input_channels", 0),
                "channels_out": dev.get("max_output_channels", 0),
                "default_samplerate": dev.get("default_samplerate", 0.0),
                "hostapi": dev.get("hostapi", -1),
            }
        )
    return result


def get_default_input() -> Optional[int]:
    """
    Restituisce l'indice del device di input (microfono) di default.

    Returns:
        Indice intero del device di default oppure None se non disponibile.

    Raises:
        ImportError: se sounddevice non e' installato.
    """
    sd = _import_sd()
    try:
        dev = sd.query_devices(kind="input")
        # L'indice e' recuperato interrogando l'intera lista per trovare la corrispondenza
        all_devices = sd.query_devices()
        for idx, d in enumerate(all_devices):
            if d.get("name") == dev.get("name") and d.get("hostapi") == dev.get("hostapi"):
                return idx
    except Exception:  # noqa: BLE001
        pass
    return None


def get_default_output() -> Optional[int]:
    """
    Restituisce l'indice del device di output (speaker/cuffie) di default.

    Returns:
        Indice intero del device di default oppure None se non disponibile.

    Raises:
        ImportError: se sounddevice non e' installato.
    """
    sd = _import_sd()
    try:
        dev = sd.query_devices(kind="output")
        all_devices = sd.query_devices()
        for idx, d in enumerate(all_devices):
            if d.get("name") == dev.get("name") and d.get("hostapi") == dev.get("hostapi"):
                return idx
    except Exception:  # noqa: BLE001
        pass
    return None
