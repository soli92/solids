"""
voice/core/side_channel.py — Lifecycle owner per i file di protocollo del canale vocale.

Centralizza:
- Costanti path del side-channel (~/.local/share/soli-voice/)
- SCHEMA_VERSION per evoluzione formato senza rottura
- atomic_write_json: scrittura atomica POSIX (tmp+os.replace)
- reset_state_file: helper per reset a stato IDLE

Vincoli EP-041: solo stdlib (pathlib, os, json, typing).
Il modulo e' importabile anche con voice_channel.enabled: false
senza effetti collaterali (nessun import audio/STT/TTS/hardware).

Prerequisito di TSK-364, TSK-365, TSK-370, TSK-371.
[^src: management/kanban/EP-046-voice-hardening/US-165-lifecycle-owner-side-channel/TSK-363.md]
"""

from pathlib import Path
import os
import json
from typing import Any

# ---------------------------------------------------------------------------
# Costanti path — root unico per tutti i file di protocollo voice
# ---------------------------------------------------------------------------

SOLI_VOICE_DIR: Path = Path.home() / ".local" / "share" / "soli-voice"
"""Directory radice del side-channel vocale. Creata on-demand da atomic_write_json."""

STATE_FILE: Path = SOLI_VOICE_DIR / "voice-state.json"
"""Stato corrente della FSM vocale (es. {"state": "IDLE"})."""

INBOX: Path = SOLI_VOICE_DIR / "voice-in.json"
"""File-pipe in ingresso: comando scritto dal LLM verso il modulo voice."""

READY: Path = SOLI_VOICE_DIR / "voice-ready"
"""Sentinel file: presenza indica che il consumer voice e' pronto ad accettare input."""

PID_FILE: Path = SOLI_VOICE_DIR / "voice.pid"
"""PID del processo voice principale (singola istanza, EP-044 US-159)."""

CONSUMER_ALIVE: Path = SOLI_VOICE_DIR / "voice-consumer.alive"
"""Liveness marker del consumer; aggiornato periodicamente dal loop voice."""

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1"
"""
Versione del formato dei file di protocollo voice-state.json e voice-in.json.
Incrementare quando cambia la struttura in modo non retro-compatibile.
Permite ai lettori di rilevare file scritti da versioni incompatibili.
"""

# ---------------------------------------------------------------------------
# I/O atomico
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, data: dict) -> None:
    """Scrive *data* su *path* tramite pattern tmp+os.replace (atomico POSIX).

    Il file temporaneo e' creato nella stessa directory di *path*
    (path.with_suffix(path.suffix + ".tmp")), garantendo che tmp e target
    risiedano sullo stesso filesystem. os.replace e' quindi atomico su POSIX:
    nessun lettore vedra' mai un file parzialmente scritto.

    La directory parent viene creata automaticamente se assente.

    Parametri
    ---------
    path : Path
        Percorso del file destinazione.
    data : dict
        Dati da serializzare in JSON (encoding UTF-8, indent=2).

    Raises
    ------
    OSError
        Propagato senza intercettazione silente se la scrittura o il replace
        falliscono (es. permessi, filesystem read-only).
    """
    # Assicura che la directory esista prima di aprire il file tmp.
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp: Path = path.with_suffix(path.suffix + ".tmp")
    # Scrivi sul file temporaneo nella stessa directory del target.
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    # Sostituisce atomicamente tmp -> path (POSIX: rename(2) e' atomico).
    os.replace(tmp, path)


def reset_state_file() -> None:
    """Scrive atomicamente {"state": "IDLE"} su STATE_FILE.

    Chiamata tipicamente all'avvio del modulo voice o dopo un errore
    per garantire uno stato FSM noto e coerente.

    Raises
    ------
    OSError
        Propagato se la scrittura su STATE_FILE fallisce.
    """
    atomic_write_json(STATE_FILE, {"state": "IDLE"})


# ---------------------------------------------------------------------------
# Esportazioni pubbliche
# ---------------------------------------------------------------------------

__all__ = [
    "SOLI_VOICE_DIR",
    "STATE_FILE",
    "INBOX",
    "READY",
    "PID_FILE",
    "CONSUMER_ALIVE",
    "SCHEMA_VERSION",
    "atomic_write_json",
    "reset_state_file",
]
