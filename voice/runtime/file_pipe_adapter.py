"""
voice/runtime/file_pipe_adapter.py — File-pipe adapter for in-session Claude Code.

Instead of launching `claude -p` as a subprocess, writes the voice transcription
to an inbox file that the current Claude Code session monitors. The response
is written by the current session to an outbox file that this adapter reads.

This allows the voice channel to integrate with the active Claude Code chat,
making voice interactions appear directly in the current conversation.

File protocol:
  inbox:  ~/.local/share/soli-voice/voice-in.json   {"id": str, "text": str, "ts": float}
  outbox: ~/.local/share/soli-voice/voice-out.json  {"id": str, "response": str}
  ready:  ~/.local/share/soli-voice/voice-ready     touch file — signals new input

Config (voice_channel.runtime):
  provider: file-pipe
  pipe_timeout: 180     # max seconds waiting for session response
  pipe_poll_ms: 100     # outbox polling interval in milliseconds (watchdog fallback)

Outbox notification:
  - Primary path  (watchdog available): FSEvents on macOS, inotify on Linux.
    Typical latency < 10ms. No active polling.
  - Fallback path  (watchdog absent):     polling every pipe_poll_ms (default 100ms).
    Fallback is announced with a single INFO log at initialization.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

# ---------------------------------------------------------------------------
# watchdog import guard — optional; no ImportError if absent (AC4)
# ---------------------------------------------------------------------------
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False

from voice.runtime.factory_runtime import (
    Acknowledgment,
    Done,
    Error,
    FactoryRuntime,
    RuntimeEvent,
    SpokenSummary,
    Artifact,
)
from voice.core.side_channel import (
    CONSUMER_ALIVE,
    INBOX,
    atomic_write_json,
    SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from voice.config import VoiceConfig

logger = logging.getLogger(__name__)

_PIPE_DIR = Path.home() / ".local/share/soli-voice"
# _INBOX removed: replaced by INBOX (voice.core.side_channel) — TSK-370
_OUTBOX  = _PIPE_DIR / "voice-out.json"
_READY   = _PIPE_DIR / "voice-ready"


class FilePipeAdapter(FactoryRuntime):
    """
    Adapter that relays each voice utterance to the active Claude Code session
    via a bidirectional file-pipe.

    Waits for the session response via watchdog (FSEvents/inotify) when
    available; falls back to polling every ``_poll_ms`` otherwise.
    """

    def __init__(self, config: "VoiceConfig") -> None:
        self._config = config
        rt = config.runtime
        self._timeout: int   = getattr(rt, "pipe_timeout", 180)
        # default 100ms (polling fallback); TSK-344 formalizes pipe_poll_ms in RuntimeConfig
        self._poll_ms: float = getattr(rt, "pipe_poll_ms", 100) / 1000.0
        _PIPE_DIR.mkdir(parents=True, exist_ok=True)
        # Clean up residual outbox from previous sessions
        _OUTBOX.unlink(missing_ok=True)
        # Log once if watchdog is unavailable (AC3)
        if not _WATCHDOG_AVAILABLE:
            logger.info(
                "watchdog non disponibile: file-pipe usa polling a %dms",
                int(self._poll_ms * 1000),
            )

    def is_consumer_alive(self) -> bool:
        """True if CONSUMER_ALIVE exists and mtime <= consumer_alive_ttl_s seconds.
        False if the file does not exist. Default True if liveness_check disabled in config.

        Uses defensive getattr on self._config.runtime until TSK-371
        (RuntimeConfig) formalizes liveness_check and consumer_alive_ttl_s fields.
        """
        liveness_check = getattr(getattr(self._config, "runtime", None), "liveness_check", True)
        if not liveness_check:
            return True
        consumer_alive_ttl_s = getattr(
            getattr(self._config, "runtime", None), "consumer_alive_ttl_s", 10
        )
        if not CONSUMER_ALIVE.exists():
            return False
        age = time.monotonic() - CONSUMER_ALIVE.stat().st_mtime
        return age <= consumer_alive_ttl_s

    # ------------------------------------------------------------------
    # FactoryRuntime interface (AC5: signature unchanged)
    # ------------------------------------------------------------------

    async def submit(
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        turn_id = str(uuid.uuid4())[:8]

        # Write inbox atomically (US-165 F5)
        atomic_write_json(INBOX, {
            "id": turn_id,
            "text": text,
            "ts": time.time(),
            "schema_version": SCHEMA_VERSION,
        })
        # Touch ready file — signals the Claude Code session that input is available
        _READY.touch()

        yield Acknowledgment("in attesa della sessione Claude Code...")

        # Wait for response: event-driven path or polling fallback
        if _WATCHDOG_AVAILABLE:
            data = await self._await_watchdog(turn_id)
        else:
            data = await self._await_polling(turn_id)

        if data is None:
            yield Error(
                f"Timeout: la sessione Claude Code non ha risposto in {self._timeout}s."
            )
            return

        # Response received — clean up protocol files
        _OUTBOX.unlink(missing_ok=True)
        INBOX.unlink(missing_ok=True)
        _READY.unlink(missing_ok=True)

        response = data.get("response", "")
        if not response:
            yield Error("Risposta vuota dalla sessione.")
            return

        yield SpokenSummary(response[:500])
        yield Artifact(kind="text", content=response)
        yield Done()

    async def cancel(self, session_id: str) -> None:
        _OUTBOX.unlink(missing_ok=True)
        INBOX.unlink(missing_ok=True)
        _READY.unlink(missing_ok=True)

    async def aclose(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Event-driven path (AC1)
    # ------------------------------------------------------------------

    async def _await_watchdog(self, turn_id: str) -> dict | None:
        """
        Wait for ``voice-out.json`` via watchdog (FSEvents on macOS / inotify on Linux).
        Typical latency < 10ms. Returns the outbox dict if id matches, None on timeout.
        """
        loop = asyncio.get_running_loop()
        event = asyncio.Event()

        class _OutboxHandler(FileSystemEventHandler):  # type: ignore[misc]
            def on_modified(self_h, fs_event) -> None:  # noqa: N805
                if Path(fs_event.src_path).name == _OUTBOX.name:
                    loop.call_soon_threadsafe(event.set)

            def on_created(self_h, fs_event) -> None:  # noqa: N805
                if Path(fs_event.src_path).name == _OUTBOX.name:
                    loop.call_soon_threadsafe(event.set)

        observer = Observer()
        observer.schedule(_OutboxHandler(), str(_PIPE_DIR), recursive=False)
        observer.start()
        try:
            # Race check: file may already be present before observer starts
            if _OUTBOX.exists():
                event.set()
            await asyncio.wait_for(event.wait(), timeout=self._timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            observer.stop()
            observer.join()

        return self._read_outbox(turn_id)

    # ------------------------------------------------------------------
    # Polling fallback path (AC3)
    # ------------------------------------------------------------------

    async def _await_polling(self, turn_id: str) -> dict | None:
        """
        Wait for ``voice-out.json`` via polling every ``_poll_ms`` (default 100ms).
        Used when watchdog is unavailable.
        """
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll_ms)
            data = self._read_outbox(turn_id)
            if data is not None:
                return data
        return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _read_outbox(self, turn_id: str) -> dict | None:
        """
        Read and validate ``voice-out.json``.
        Returns the dict if the ``id`` field matches ``turn_id``, None otherwise.
        """
        if not _OUTBOX.exists():
            return None
        try:
            data = json.loads(_OUTBOX.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("id") != turn_id:
            return None
        return data
