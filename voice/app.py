"""
Voice Channel Factory — entry point.

Usage:
    python -m voice.app                    # usa factory.config.yaml in cwd o parent
    python -m voice.app --config path.yaml # config esplicita
    python -m voice.app --dry-run          # verify dependencies without starting
    python -m voice.app --list-devices     # list audio devices
    python -m voice.app --handsfree        # start directly in handsfree mode
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path


# Default PID file path (consistent with _PIPE_DIR in voice/runtime/).
DEFAULT_PID_PATH = Path.home() / ".local/share/soli-voice/voice.pid"


@contextmanager
def pid_lock(path: Path):
    """Context manager that serializes voice/app.py startup via PID file.

    Acquisition (synchronous, before event loop):
      - Create directory if missing (AC6).
      - If file exists, read PID and verify with os.kill(pid, 0):
          * no exception → process alive → print error to stderr + sys.exit(1) (AC2)
          * ProcessLookupError → stale lock → silent overwrite (AC3)
          * PermissionError → conservative, treated as alive → exit(1)
          * non-int value / corrupt file → stale → silent overwrite
      - Write str(os.getpid()) to file (AC1).

    Release (finally — guaranteed even on SystemExit / KeyboardInterrupt):
      - Remove file only if PID in file matches own (anti-race guard, AC4).

    No external dependencies: stdlib only (os, pathlib, contextlib).
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            pid_text = path.read_text(encoding="utf-8").strip()
            pid = int(pid_text)
            try:
                os.kill(pid, 0)
                # Process alive: clean exit with diagnostic message.
                print(
                    f"voice/app.py gia' in esecuzione (PID {pid}). "
                    f"Usa `kill {pid}` per terminarlo.",
                    file=sys.stderr,
                )
                sys.exit(1)
            except ProcessLookupError:
                # Stale lock: process no longer exists, overwrite.
                pass
            except PermissionError:
                # Conservative: treat as alive (e.g. another user's process).
                print(
                    f"voice/app.py gia' in esecuzione (PID {pid}). "
                    f"Usa `kill {pid}` per terminarlo.",
                    file=sys.stderr,
                )
                sys.exit(1)
        except (ValueError, OSError):
            # Non-int value or read failed → stale lock, overwrite.
            pass

    own_pid = os.getpid()
    path.write_text(str(own_pid), encoding="utf-8")
    try:
        yield
    finally:
        # Anti-race guard: remove file only if PID in file is still own.
        try:
            if path.exists() and path.read_text(encoding="utf-8").strip() == str(own_pid):
                path.unlink()
        except OSError:
            pass


async def main(
    config_path: str | None = None,
    dry_run: bool = False,
    list_devices: bool = False,
    handsfree: bool = False,
) -> None:
    """
    Async entry point: load config, assemble Phase 1 chain,
    start the state machine push-to-talk cycle.

    Args:
        config_path:  Explicit path to factory.config.yaml. If None, walk up
                      the filesystem from cwd (default behavior).
        dry_run:      If True, instantiate components to verify dependencies
                      but do not start the push-to-talk cycle.
        list_devices: If True, print available audio devices and return.
        handsfree:    If True, start state machine directly in
                      handsfree mode (equivalent to saying "mani libere" after startup).
    """
    # 1. Load config from voice_channel: section of factory.config.yaml
    from voice.config import load_config

    config = load_config(config_path)

    if not config.enabled:
        print("voice_channel.enabled: false — imposta enabled: true in factory.config.yaml")
        sys.exit(0)

    # 2. --list-devices: list PortAudio audio devices and return
    if list_devices:
        from voice.audio.devices import list_devices as _list_devices

        for d in _list_devices():
            print(
                f"  [{d['index']}] {d['name']}"
                f" (in:{d['channels_in']} out:{d['channels_out']})"
            )
        return

    # 3. PID lock — prevents multiple instance startup (US-159 AC1, AC4, AC6).
    #    Path resolved here (after load_config) but before audio assembly.
    pid_path = (
        Path(config.pid_file_path).expanduser()
        if config.pid_file_path
        else DEFAULT_PID_PATH
    )

    with pid_lock(pid_path):
        from voice.core.side_channel import reset_state_file
        reset_state_file()  # AC4: atomic reset — first operation inside pid_lock
        # 4. Configure logging at level declared in config
        logging.basicConfig(level=config.log_level)

        # Lazy component imports: none imported at module level
        # to respect no-op principle when voice_channel.enabled: false.
        from voice.audio.aec import NoOpProcessor, create_aec_processor
        from voice.audio.capture import AudioCapture
        from voice.audio.playback import AudioPlayback, PlaybackFarEndSink
        from voice.core.router import EventRouter
        from voice.core.state_machine import VoiceStateMachine
        from voice.runtime.claude_code_adapter import ClaudeCodeAdapter
        from voice.runtime.cursor_adapter import CursorAdapter
        from voice.runtime.custom_loop_adapter import CustomLoopAdapter
        from voice.runtime.mock_adapter import MockAdapter
        from voice.runtime.ollama_adapter import OllamaAdapter
        from voice.stt.faster_whisper_stt import FasterWhisperSTT
        from voice.tts.piper_tts import PiperTTS
        from voice.vad.endpointing import Endpointer
        from voice.vad.silero_vad import SileroVAD
        from voice.vad.wake_word import WakeWordDetector

        # --- Assemble Phase 1 chain ---

        # AudioPlayback: synchronous TTS playback via PortAudio.
        # Created before AudioCapture: PlaybackFarEndSink (AEC) is
        # connected here and passed to capture as far-end reference.
        playback = AudioPlayback(config)

        # Optional AEC pre-filter (US-147 AC3, AC4, AC5): capture → AEC → VAD.
        # If aec.enabled=False: NoOpProcessor (no WebRTC APM binding import, AC3).
        # If aec.enabled=True: graceful fallback cascade webrtc-apm→speexdsp→
        # noisereduce→NoOp+WARNING (AC4); PlaybackFarEndSink connected to playback
        # for far-end reference (TTS signal during playback).
        if config.aec.enabled:
            aec_processor = create_aec_processor(config.aec)
            far_end_sink: PlaybackFarEndSink | None = PlaybackFarEndSink()
            playback.set_far_end_sink(far_end_sink)
        else:
            # aec.enabled=False: explicit NoOpProcessor (AC3 — zero overhead, no WebRTC import)
            aec_processor = NoOpProcessor()
            far_end_sink = None

        # AudioCapture: capture PCM from microphone via PortAudio (real-time callback).
        # Pipeline: capture → AEC (pre-filter, US-147 AC5) → queue → VAD → STT.
        capture = AudioCapture(config, aec_processor=aec_processor, far_end_sink=far_end_sink)

        # VAD + Endpointer (off active path in F1; instantiated for AC1 completeness)
        # NOTE: endpoint_silence_ms is the correct field in VADConfig (not min_silence_ms).
        # debounce_ms: use getattr as safety net — TSK-333 adds the field
        # to VADConfig; if absent Endpointer constructor uses default 500 ms.
        vad = Endpointer(
            SileroVAD(threshold=config.vad.threshold),
            silence_threshold_ms=config.vad.endpoint_silence_ms,
            debounce_ms=getattr(config.vad, "debounce_ms", 700),
        )

        # STT: faster-whisper (lazy model load on first transcribe)
        stt = FasterWhisperSTT(
            model_size=config.stt.model,
            language=config.stt.language,
            no_speech_prob_threshold=config.stt.no_speech_prob_threshold,    # US-169
            compression_ratio_threshold=config.stt.compression_ratio_threshold,  # US-169
        )

        # TTS: piper-tts (loads .onnx model in constructor; PiperTTS has no speed)
        tts = PiperTTS(voice=config.tts.voice, model_dir=config.tts.model_dir)

        # Runtime: dispatch based on voice_channel.runtime.provider
        _provider = config.runtime.provider
        if _provider == "mock":
            runtime = MockAdapter(config)
            print("[MOCK] Runtime in modalità echo — nessuna API key richiesta.")
        elif _provider == "ollama":
            runtime = OllamaAdapter(config)
            print(f"[OLLAMA] Runtime locale: {config.runtime.ollama_base_url} model={config.runtime.ollama_model}")
        elif _provider == "claude-code":
            runtime = ClaudeCodeAdapter(config)
            _tools = config.runtime.claude_code_allowed_tools
            print(f"[CLAUDE CODE] Runtime factory — tool: {_tools}")
            print("  Comandi vocali: query wiki, stato progetto, git log, diff, etc.")
        elif _provider == "file-pipe":
            from voice.runtime.file_pipe_adapter import FilePipeAdapter
            runtime = FilePipeAdapter(config)
            print("[FILE-PIPE] Runtime in-session — relay alla chat Claude Code attiva.")
            print("  Avvia il monitor nella sessione Claude Code per ricevere i comandi vocali.")
        elif _provider == "cursor":
            runtime = CursorAdapter(config)
            print(f"[CURSOR] Runtime factory Cursor — regole da {config.runtime.cursor_rules_dir}")
            print("  Anthropic API con system prompt costruito dai file .cursor/rules/*.mdc")
        else:
            runtime = CustomLoopAdapter(config)

        # EventRouter: asyncio queue for TTS (sole choke point, US-143 AC6)
        tts_queue: asyncio.Queue[str] = asyncio.Queue()
        router = EventRouter(tts_queue)

        # Wake word detector (opt-in; no-op if wake_word.enabled=false)
        wake_word_detector = None
        if config.wake_word.enabled:
            wake_word_detector = WakeWordDetector(
                samples_dir=config.wake_word.samples_dir,
                keyword=config.wake_word.keyword,
                sensitivity=config.wake_word.sensitivity,
                min_detections=config.wake_word.min_detections,
            )
            try:
                wake_word_detector.load()
                print(f"[WAKE WORD] Keyword '{config.wake_word.keyword}' caricata — dì la parola per iniziare.")
            except (ImportError, FileNotFoundError) as exc:
                print(f"[WAKE WORD] WARN: {exc}")
                print("[WAKE WORD] Fallback a push-to-talk (INVIO).")
                wake_word_detector = None

        if dry_run:
            print("Dipendenze caricate. --dry-run: nessuna sessione avviata.")
            return

        # 5. Build state machine with injected dependencies
        fsm = VoiceStateMachine(
            config=config,
            capture=capture,
            vad=vad,
            stt=stt,
            tts=tts,
            playback=playback,
            runtime=runtime,
            router=router,
            wake_word_detector=wake_word_detector,
        )

        if handsfree:
            fsm._handsfree_mode = True
            fsm._continuous_mode = True
            print("[HANDSFREE] Modalità handsfree attivata all'avvio — nessun INVIO richiesto.")

        print(
            f"Voice Channel Factory avviato"
            f" (modello STT: {config.stt.model}, voce TTS: {config.tts.voice})"
        )
        if config.wake_word.enabled and wake_word_detector is not None:
            print(f"Pronuncia '{config.wake_word.keyword}' per iniziare — poi parla liberamente.")
            print("La conversazione continua automaticamente dopo ogni risposta.")
        else:
            print("Premi INVIO per parlare — VAD rileva automaticamente la fine della frase.")
        print("Ctrl+C per uscire.")

        # 6. Start push-to-talk loop; run_loop() handles KeyboardInterrupt
        #    internally and calls runtime.aclose().
        #    Inner finally ensures capture.stop() in all cases;
        #    outer pid_lock context manager removes PID file on exit (AC4).
        try:
            await fsm.run_loop()
        finally:
            reset_state_file()  # AC5: IDLE rewrite on orderly shutdown
            capture.stop()


def cli() -> None:
    """Synchronous entry point: parse CLI arguments + asyncio.run(main(...))."""
    parser = argparse.ArgumentParser(
        description="Voice Channel Factory — canale vocale push-to-talk EP-041."
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Explicit path to factory.config.yaml"
        " (default: automatic search from cwd).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify dependencies are installed without starting the voice cycle.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available PortAudio audio devices and exit.",
    )
    parser.add_argument(
        "--handsfree",
        action="store_true",
        help="Start directly in handsfree mode (equivalent to saying 'mani libere' after startup).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                config_path=args.config,
                dry_run=args.dry_run,
                list_devices=args.list_devices,
                handsfree=args.handsfree,
            )
        )
    except KeyboardInterrupt:
        # Ctrl+C outside asyncio loop (e.g. during startup): clean exit.
        pass


if __name__ == "__main__":
    cli()
