"""
voice/voice_consumer.py — Unsupervised STT→tutor→TTS bridge.

Monitors voice-out.json event-driven (watchdog primary, polling
fallback) and sends each LLM response to piper TTS (PiperTTS + AudioPlayback).

Closes the STT→tutor→TTS loop without manual intervention:
  1. The state machine (FSM) writes the transcription to voice-in.json.
  2. Claude Code reads voice-in.json, processes, writes voice-out.json:
         {"id": "<turn_id>", "response": "<LLM response text>"}
  3. VoiceConsumer reads voice-out.json → extracts "response" → TTS → audio.

Fundamental invariants (EP-046 C3, feedback_voice_pipe_response_field):
  - Field read: data.get("response", "") — NEVER "text" (silent TTS if "text").
  - Empty string guard: log WARNING + skip; no silent TTS.
  - Event-driven loop: FSEvents on macOS / inotify on Linux via watchdog
    if available; fallback to polling every pipe_poll_ms (default 100ms).
  - TTS errors not propagated: log ERROR + continue loop.
  - Compatible with EP-046 C7 (session-owner stub via VoiceSessionManager).

TTS parameters from config (voice_channel.tts.*):
  - tts.voice     — piper model name (default it_IT-riccardo-medium)
  - tts.model_dir — .onnx file directory (default: PIPER_MODEL_DIR or cwd)

Uso:
    from voice.voice_consumer import VoiceConsumer
    from voice.config import load_config

    cfg = load_config()
    consumer = VoiceConsumer(cfg)
    asyncio.run(consumer.run())

Or as standalone process:
    python -m voice.voice_consumer [--config path/factory.config.yaml]
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

# ---------------------------------------------------------------------------
# Watchdog import guard — optional (mirror of runtime/file_pipe_adapter.py)
# No ImportError if watchdog not installed: use fallback path.
# ---------------------------------------------------------------------------
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False

from voice.core.side_channel import SOLI_VOICE_DIR
from voice.core.session import VoiceSessionManager

if TYPE_CHECKING:
    from voice.config import VoiceConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constant paths — aligned with file_pipe_adapter.py and side_channel.py
# ---------------------------------------------------------------------------

_PIPE_DIR = SOLI_VOICE_DIR
_OUTBOX   = _PIPE_DIR / "voice-out.json"


# ---------------------------------------------------------------------------
# VoiceConsumer
# ---------------------------------------------------------------------------

class VoiceConsumer:
    """
    Unsupervised STT→tutor→TTS consumer bridge (EP-046).

    Monitors voice-out.json for new LLM responses and sends them to piper TTS
    via PiperTTS (synthesis) + AudioPlayback (playback).

    Invarianti:
      - Field read: data.get("response", "") — NEVER "text".
      - Empty string guard → log WARNING + skip.
      - Event-driven loop (watchdog primary, polling fallback).
      - TTS errors → log ERROR, loop continues.
      - EP-046 C7: VoiceSessionManager stub no-op instantiated.

    Args:
        config: VoiceConfig loaded from factory.config.yaml.
    """

    def __init__(self, config: "VoiceConfig") -> None:
        self._config = config
        rt = config.runtime
        # Fallback polling interval in seconds (from pipe_poll_ms in config)
        self._poll_ms: float = getattr(rt, "pipe_poll_ms", 100) / 1000.0
        # piper-tts output sample rate — aligned with state_machine.py (tts_sr)
        self._tts_sr: int = 22050
        # Last processed turn ID — filters duplicates on fast loop
        self._last_id: Optional[str] = None
        # Session-owner stub (EP-046 C7, US-170): no-op in current implementation
        self._session_manager = VoiceSessionManager()

        _PIPE_DIR.mkdir(parents=True, exist_ok=True)

        if not _WATCHDOG_AVAILABLE:
            logger.info(
                "watchdog non disponibile: VoiceConsumer usa polling a %dms",
                int(self._poll_ms * 1000),
            )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main event-driven loop. Blocks until Ctrl+C.

        Initialize TTS and Playback (lazy — no piper/sounddevice import
        at module level), then enters wait cycle on voice-out.json.

        For each new response:
          1. Read data.get("response", "")
          2. Empty guard → skip (no silent TTS)
          3. Synthesize via PiperTTS
          4. Play via AudioPlayback
          5. TTS errors → log ERROR + continue

        Raises:
            ImportError: if piper-tts or sounddevice are not installed.
        """
        logger.info("VoiceConsumer: avvio — attesa risposte su %s", _OUTBOX)

        try:
            tts = self._build_tts()
            playback = self._build_playback()
        except ImportError as exc:
            logger.error("VoiceConsumer: dipendenze TTS non disponibili: %s", exc)
            raise

        logger.info(
            "VoiceConsumer: TTS inizializzato (voice=%r, sr=%d Hz)",
            self._config.tts.voice,
            self._tts_sr,
        )

        try:
            while True:
                data = await self._wait_for_response()
                await self._handle_response(data, tts, playback)
        except KeyboardInterrupt:
            logger.info("VoiceConsumer: interruzione da Ctrl+C — loop terminato")

    # ------------------------------------------------------------------
    # Lazy build TTS and Playback dependencies
    # ------------------------------------------------------------------

    def _build_tts(self):
        """Instantiate PiperTTS with parameters from voice_channel.tts.* in config.

        Lazy import: no piper-tts import at module level (backward compat
        with environments without extras[voice]).
        """
        from voice.tts.piper_tts import PiperTTS  # noqa: PLC0415
        return PiperTTS(
            voice=self._config.tts.voice,
            model_dir=self._config.tts.model_dir,
        )

    def _build_playback(self):
        """Instantiate AudioPlayback with current VoiceConfig.

        Lazy import: no sounddevice import at module level.
        """
        from voice.audio.playback import AudioPlayback  # noqa: PLC0415
        return AudioPlayback(self._config)

    # ------------------------------------------------------------------
    # Event-driven or polling wait
    # ------------------------------------------------------------------

    async def _wait_for_response(self) -> dict:
        """Wait for next valid, non-duplicate voice-out.json.

        Uses watchdog (FSEvents on macOS / inotify on Linux) if available;
        polling fallback every pipe_poll_ms otherwise.

        Never returns None: blocks until valid new data.
        """
        if _WATCHDOG_AVAILABLE:
            return await self._wait_watchdog()
        return await self._wait_polling()

    async def _wait_watchdog(self) -> dict:
        """Wait for voice-out.json via watchdog (event-driven, latency < 10ms).

        Creates an Observer per wait; on event receive reads outbox.
        If ID already processed or file invalid, iterate with 100ms pause
        (avoids busy-loop on stale file edge case).

        Mirror pattern of file_pipe_adapter.py._await_watchdog().
        """
        while True:
            loop = asyncio.get_running_loop()
            ev = asyncio.Event()

            class _Handler(FileSystemEventHandler):  # type: ignore[misc]
                def on_modified(self_h, fs_ev) -> None:  # noqa: N805
                    if Path(fs_ev.src_path).name == _OUTBOX.name:
                        loop.call_soon_threadsafe(ev.set)

                def on_created(self_h, fs_ev) -> None:  # noqa: N805
                    if Path(fs_ev.src_path).name == _OUTBOX.name:
                        loop.call_soon_threadsafe(ev.set)

            observer = Observer()
            observer.schedule(_Handler(), str(_PIPE_DIR), recursive=False)
            observer.start()
            try:
                # Race-check: file may already be present before
                # observer starts — set event immediately.
                if _OUTBOX.exists():
                    ev.set()
                await ev.wait()
            finally:
                observer.stop()
                observer.join()

            data = self._read_outbox()
            if data is not None:
                return data
            # File present but ID already processed or invalid JSON — pause
            # briefly before re-entering loop to avoid busy-spin.
            await asyncio.sleep(0.1)

    async def _wait_polling(self) -> dict:
        """Wait for voice-out.json via polling every _poll_ms.

        Fallback path when watchdog is not available.
        Loop with sleep every pipe_poll_ms (default 100ms).
        """
        while True:
            data = self._read_outbox()
            if data is not None:
                return data
            await asyncio.sleep(self._poll_ms)

    # ------------------------------------------------------------------
    # Outbox read and validation
    # ------------------------------------------------------------------

    def _read_outbox(self) -> Optional[dict]:
        """Read voice-out.json and filter already-processed turns.

        Field invariant: reads "response" (not "text") — field is
        extracted in _handle_response; here only structure and ID are validated.

        Returns:
            dict with outbox content if:
              - file exists
              - JSON is valid
              - data["id"] differs from self._last_id (new turn)
            None otherwise (missing file / invalid JSON / duplicate ID).
        """
        if not _OUTBOX.exists():
            return None
        try:
            data = json.loads(_OUTBOX.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        # Filter already-processed IDs — avoid double TTS on file not yet removed
        turn_id = data.get("id")
        if turn_id is not None and turn_id == self._last_id:
            return None
        return data

    # ------------------------------------------------------------------
    # Response handling: TTS + playback
    # ------------------------------------------------------------------

    async def _handle_response(self, data: dict, tts, playback) -> None:
        """Extract "response", guard on empty, synthesize and play.

        Field invariant (feedback_voice_pipe_response_field):
            Reads data.get("response", "") — NEVER data.get("text", "").
            Field "text" is written to voice-in.json (STT transcription
            ); "response" is the LLM response on voice-out.json.
            Reading the wrong field produces silent TTS.

        Empty string guard: log WARNING + return (no silent TTS).

        TTS/Playback errors: log ERROR + return (not propagated — loop
        must continue even on piper or sounddevice error).

        Args:
            data:     dict read from voice-out.json.
            tts:      PiperTTS instance for speech synthesis.
            playback: AudioPlayback instance for audio playback.
        """
        turn_id = data.get("id")
        # Update last_id before TTS: if TTS crashes, do not reprocess
        # same turn on next iteration (duplicate guard).
        self._last_id = turn_id

        # Field invariant "response" (NOT "text") — feedback_voice_pipe_response_field
        response = data.get("response", "")

        # Empty string guard → no silent TTS (DoD invariant)
        if not response or not response.strip():
            logger.warning(
                "VoiceConsumer: risposta vuota per turno %r — skip TTS "
                "(nessun audio silenzioso)",
                turn_id,
            )
            return

        logger.info(
            "VoiceConsumer: turno %r — risposta %d caratteri → sintetizzo TTS",
            turn_id, len(response),
        )

        # Remove outbox after read (file-pipe protocol cleanup)
        try:
            _OUTBOX.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("VoiceConsumer: pulizia outbox fallita (non bloccante): %s", exc)

        # TTS synthesis + audio playback.
        # Errors not propagated: loop must continue on TTS errors (DoD).
        try:
            audio = await asyncio.to_thread(tts.synthesize, response)
            if audio is not None and len(audio) == 0:
                logger.warning(
                    "VoiceConsumer: sintesi TTS ha prodotto audio vuoto "
                    "per turno %r — skip playback",
                    turn_id,
                )
                return
            await asyncio.to_thread(playback.play, audio, self._tts_sr)
            logger.info(
                "VoiceConsumer: turno %r — riproduzione completata", turn_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "VoiceConsumer: errore TTS/playback per turno %r: %s", turn_id, exc
            )
            # Do not propagate: loop must continue on TTS errors (DoD)


# ---------------------------------------------------------------------------
# Entry point CLI standalone
# ---------------------------------------------------------------------------

def _cli_main() -> None:
    """Entry point for standalone execution: python -m voice.voice_consumer."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "VoiceConsumer — unsupervised STT→tutor→TTS bridge (EP-046).\n"
            "Monitors voice-out.json and sends each LLM response to piper TTS."
        )
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help=(
            "Explicit path to factory.config.yaml "
            "(default: walk up filesystem from cwd)"
        ),
    )
    parser.add_argument(
        "--log-level",
        default=None,
        metavar="LEVEL",
        help="Override log level: DEBUG | INFO | WARNING (default: from voice_channel.log_level)",
    )
    args = parser.parse_args()

    from voice.config import load_config  # noqa: PLC0415

    cfg = load_config(args.config)

    if not cfg.enabled:
        print(
            "voice_channel.enabled: false in factory.config.yaml — "
            "VoiceConsumer non avviato.\n"
            "Imposta voice_channel.enabled: true per abilitare il canale vocale.",
            file=sys.stderr,
        )
        sys.exit(1)

    log_level = (args.log_level or cfg.log_level or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    consumer = VoiceConsumer(cfg)
    asyncio.run(consumer.run())


if __name__ == "__main__":
    _cli_main()
