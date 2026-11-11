"""
voice/tests/test_liveness_check.py — Test liveness check US-167 (TSK-373).

Scenari (5 AC):
  TC1: is_consumer_alive() → False se CONSUMER_ALIVE non esiste (AC1).
  TC2: is_consumer_alive() → True se CONSUMER_ALIVE ha mtime recente (AC2).
  TC3: Payload scritto su INBOX contiene schema_version='1' (AC3).
  TC4: Con liveness_check=False, is_consumer_alive() → True anche senza file (AC4).
  TC5: Adapter non-FilePipeAdapter eredita default True da FactoryRuntime (AC5).

Framework: pytest + tmp_path. Nessun hardware audio, nessun LLM.
Isolamento: i path di protocollo vengono reindirizzati a tmp_path via monkeypatch.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import voice.runtime.file_pipe_adapter as fp_mod
import voice.core.side_channel as sc_mod
from voice.config import VoiceConfig
from voice.runtime.factory_runtime import Acknowledgment, FactoryRuntime
from voice.runtime.file_pipe_adapter import FilePipeAdapter


# ---------------------------------------------------------------------------
# Helper: build minimal VoiceConfig with liveness and pipe fields
# ---------------------------------------------------------------------------

def _make_config(
    liveness_check: bool = True,
    consumer_alive_ttl_s: int = 10,
    pipe_timeout: int = 1,
    pipe_poll_ms: int = 100,
) -> VoiceConfig:
    """VoiceConfig con timeout breve; adatto a test senza runtime LLM."""
    cfg = VoiceConfig()
    cfg.runtime.liveness_check = liveness_check
    cfg.runtime.consumer_alive_ttl_s = consumer_alive_ttl_s
    cfg.runtime.pipe_timeout = pipe_timeout
    cfg.runtime.pipe_poll_ms = pipe_poll_ms
    return cfg


# ---------------------------------------------------------------------------
# Helper: redirect module global paths to tmp_path
# ---------------------------------------------------------------------------

def _redirect_pipe_paths(monkeypatch, tmp_path):
    """Redirige _PIPE_DIR, INBOX, _OUTBOX, _READY, CONSUMER_ALIVE a tmp_path."""
    monkeypatch.setattr(fp_mod, "_PIPE_DIR", tmp_path)
    monkeypatch.setattr(fp_mod, "_OUTBOX",  tmp_path / "voice-out.json")
    monkeypatch.setattr(fp_mod, "_READY",   tmp_path / "voice-ready")
    # INBOX imported from side_channel; patch both module and origin
    monkeypatch.setattr(fp_mod, "INBOX",    tmp_path / "voice-in.json")
    monkeypatch.setattr(sc_mod, "INBOX",    tmp_path / "voice-in.json")


# ---------------------------------------------------------------------------
# TC1 — Consumer absent → is_consumer_alive() == False (AC1)
# ---------------------------------------------------------------------------

def test_consumer_absent_returns_false(tmp_path, monkeypatch):
    """AC1: is_consumer_alive() → False se CONSUMER_ALIVE non esiste.

    Il file heartbeat viene puntato a un percorso inesistente: l'adapter
    deve rilevare l'assenza e restituire False senza eccezioni.
    """
    nonexistent = tmp_path / "nonexistent.alive"

    monkeypatch.setattr(sc_mod, "CONSUMER_ALIVE", nonexistent)
    monkeypatch.setattr(fp_mod, "CONSUMER_ALIVE", nonexistent)
    _redirect_pipe_paths(monkeypatch, tmp_path)

    config = _make_config(liveness_check=True, consumer_alive_ttl_s=10)
    adapter = FilePipeAdapter(config)

    result = adapter.is_consumer_alive()

    assert result is False, (
        f"is_consumer_alive() deve restituire False con CONSUMER_ALIVE assente, "
        f"ha restituito: {result!r}"
    )


# ---------------------------------------------------------------------------
# TC2 — Consumer with fresh alive-file → is_consumer_alive() == True (AC2)
# ---------------------------------------------------------------------------

def test_consumer_alive_fresh_file(tmp_path, monkeypatch):
    """AC2: is_consumer_alive() → True se CONSUMER_ALIVE ha mtime recente.

    Il file heartbeat viene creato con mtime corrente; con TTL=10s il file
    è fresco e l'adapter deve restituire True.
    """
    alive_file = tmp_path / "voice-consumer.alive"
    alive_file.touch()  # mtime = adesso

    monkeypatch.setattr(sc_mod, "CONSUMER_ALIVE", alive_file)
    monkeypatch.setattr(fp_mod, "CONSUMER_ALIVE", alive_file)
    _redirect_pipe_paths(monkeypatch, tmp_path)

    config = _make_config(liveness_check=True, consumer_alive_ttl_s=10)
    adapter = FilePipeAdapter(config)

    result = adapter.is_consumer_alive()

    assert result is True, (
        f"is_consumer_alive() deve restituire True con CONSUMER_ALIVE fresco, "
        f"ha restituito: {result!r}"
    )


# ---------------------------------------------------------------------------
# TC3 — Payload inbox contiene schema_version='1' (AC3)
# ---------------------------------------------------------------------------

def test_submit_payload_has_schema_version(tmp_path, monkeypatch):
    """AC3: il payload scritto su INBOX da submit() contiene schema_version='1'.

    Strategia: eseguiamo submit() e consmiamo solo il primo evento (Acknowledgment),
    che viene emesso dopo che INBOX è già stato scritto atomicamente.
    Chiudiamo il generator prima del polling/watchdog per non attendere il timeout.
    Verifichiamo il contenuto di INBOX.
    """
    inbox_path = tmp_path / "voice-in.json"

    monkeypatch.setattr(fp_mod, "INBOX",   inbox_path)
    monkeypatch.setattr(sc_mod, "INBOX",   inbox_path)
    _redirect_pipe_paths(monkeypatch, tmp_path)

    config = _make_config(pipe_timeout=1, pipe_poll_ms=100)
    adapter = FilePipeAdapter(config)

    async def _consume_first_event():
        gen = adapter.submit("test utterance", "sess-001")
        # INBOX written before first yield (Acknowledgment).
        # Use generator context manager to ensure aclose().
        async for _event in gen:
            # First event: Acknowledgment — INBOX already written at this point.
            break  # aclose() called automatically by async for

    try:
        asyncio.run(asyncio.wait_for(_consume_first_event(), timeout=3.0))
    except asyncio.TimeoutError:
        pass  # Safety: wait_for should not trigger (INBOX written before yield)
    except Exception:
        pass  # Ignora errori del generator post-Acknowledgment

    assert inbox_path.exists(), (
        "voice-in.json non trovato: atomic_write_json non ha scritto INBOX prima del "
        "primo yield. Verificare che submit() chiami atomic_write_json(INBOX, ...) "
        "prima di 'yield Acknowledgment(...)'."
    )
    data = json.loads(inbox_path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == "1", (
        f"schema_version atteso '1', trovato: {data.get('schema_version')!r}\n"
        f"Payload INBOX completo: {data}\n"
        f"Verificare che SCHEMA_VERSION (voice.core.side_channel) sia '1' e che "
        f"submit() lo includa nel payload."
    )


# ---------------------------------------------------------------------------
# TC4 — liveness_check=False → is_consumer_alive() == True always (AC4)
# ---------------------------------------------------------------------------

def test_liveness_check_false_always_returns_true(tmp_path, monkeypatch):
    """AC4: con liveness_check=False, is_consumer_alive() → True anche senza file.

    Backward-compat EP-044: disabilitando il check il comportamento è identico
    agli adapter EP-044 che non hanno il pre-flight gate.
    """
    nonexistent = tmp_path / "nonexistent.alive"

    monkeypatch.setattr(sc_mod, "CONSUMER_ALIVE", nonexistent)
    monkeypatch.setattr(fp_mod, "CONSUMER_ALIVE", nonexistent)
    _redirect_pipe_paths(monkeypatch, tmp_path)

    config = _make_config(liveness_check=False)
    adapter = FilePipeAdapter(config)

    result = adapter.is_consumer_alive()

    assert result is True, (
        f"Con liveness_check=False, is_consumer_alive() deve restituire True "
        f"indipendentemente dalla presenza di CONSUMER_ALIVE, ha restituito: {result!r}"
    )


# ---------------------------------------------------------------------------
# TC5 — Mock adapter → is_consumer_alive() == True (default ABC) (AC5)
# ---------------------------------------------------------------------------

def test_non_file_pipe_adapter_always_alive():
    """AC5: adapter non-FilePipeAdapter ereditano il default True da FactoryRuntime.

    Verifica non-regressione D2: tutti gli adapter esistenti (mock, ollama,
    claude-code, cursor, anthropic, custom-loop) che non sovrascrivono
    is_consumer_alive() devono restituire True.
    """

    class _MockRuntime(FactoryRuntime):
        """Implementazione minima per testare il default ABC."""

        async def submit(self, text: str, session_id: str):  # type: ignore[override]
            # Empty async generator — satisfies AbstractMethod contract.
            return
            yield  # noqa: unreachable — required to make this an async generator

        async def cancel(self, session_id: str) -> None:
            pass

        async def aclose(self) -> None:
            pass

    runtime = _MockRuntime()
    result = runtime.is_consumer_alive()

    assert result is True, (
        f"FactoryRuntime.is_consumer_alive() deve restituire True per default "
        f"(nessun override), ha restituito: {result!r}"
    )
