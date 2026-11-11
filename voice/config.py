"""
voice/config.py — VoiceConfig: lazy read of the voice_channel: section from factory.config.yaml.

No audio/STT/TTS dependency imports at module level.
Dependencies sounddevice, faster_whisper, piper are imported lazily only
in submodules that use them (audio/, stt/, tts/).

Uso:
    from voice.config import load_config
    cfg = load_config()          # search for factory.config.yaml from cwd
    cfg = load_config("/path/factory.config.yaml")

Campi validati da from_factory_config:
    - enabled: bool
    - phase: int in {1, 2, 3, 4}
    - log_level: str in {'DEBUG', 'INFO', 'WARNING'}

No-op behavior (US-146 AC2):
    When enabled=False the function returns VoiceConfig with enabled=False.
    No voice/ module imports sounddevice, faster_whisper or piper —
    the factory works exactly as before EP-041.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allowed values for validated fields
_VALID_PHASES: frozenset[int] = frozenset({1, 2, 3, 4})
_VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING"})


# ---------------------------------------------------------------------------
# Sub-dataclass for each nested block of the voice_channel: schema
# ---------------------------------------------------------------------------

@dataclass
class STTConfig:
    """Speech-To-Text configuration (faster-whisper)."""
    provider: str = "faster-whisper"
    model: str = "medium"      # "tiny"|"base"|"small"|"medium"|"large" — default "medium" for production; use "small" on CPU-only hardware with RAM < 8GB
    language: str = "it"
    no_speech_prob_threshold: float = 0.6
    # compression_ratio_threshold: OpenAI Whisper threshold (upstream default).
    # Calibration 2026-07-10 on medium model, 5 real Italian speech samples:
    #   observed cr = 0.50–0.53 (avg 0.524) → 4.5x margin vs 2.4.
    # Repetitive hallucinated text produces cr >> 1.0 (typically 3–8+).
    # Threshold 2.4 is conservative and validated: no false positives expected on short speech.
    compression_ratio_threshold: float = 2.4

    @classmethod
    def from_dict(cls, d: dict) -> "STTConfig":
        return cls(
            provider=str(d.get("provider", "faster-whisper")),
            model=str(d.get("model", "medium")),
            language=str(d.get("language", "it")),
            no_speech_prob_threshold=float(d.get("no_speech_prob_threshold", 0.6)),
            compression_ratio_threshold=float(d.get("compression_ratio_threshold", 2.4)),
        )


@dataclass
class TTSConfig:
    """Text-To-Speech configuration (piper-tts)."""
    provider: str = "piper-tts"
    voice: str = "it_IT-riccardo-medium"
    model_dir: Optional[str] = None  # override PIPER_MODEL_DIR
    playing_watchdog_s: int = 10     # Timeout to reset tts_playing flag on TTS error (US-166 AC6)

    @classmethod
    def from_dict(cls, d: dict) -> "TTSConfig":
        return cls(
            provider=str(d.get("provider", "piper-tts")),
            voice=str(d.get("voice", "it_IT-riccardo-medium")),
            model_dir=d.get("model_dir") or None,
            playing_watchdog_s=int(d.get("playing_watchdog_s", 10)),
        )


@dataclass
class AudioConfig:
    """Hardware audio device selection (null = system default)."""
    input_device: Optional[str] = None
    output_device: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "AudioConfig":
        return cls(
            input_device=d.get("input_device", None),
            output_device=d.get("output_device", None),
        )


@dataclass
class VADConfig:
    """Voice Activity Detection — endpointing and hands-free (Phase 2+)."""
    provider: str = "silero-vad"
    threshold: float = 0.5          # base threshold in CATTURA state
    endpoint_silence_ms: int = 700  # silence (ms) for turn end (500-800 ms)
    debounce_ms: int = 700          # VAD debounce window (ms) — US-155; 700ms for slow pedagogical utterances (TSK-395)

    @classmethod
    def from_dict(cls, d: dict) -> "VADConfig":
        return cls(
            provider=str(d.get("provider", "silero-vad")),
            threshold=float(d.get("threshold", 0.5)),
            endpoint_silence_ms=int(d.get("endpoint_silence_ms", 700)),
            debounce_ms=int(d.get("debounce_ms", 700)),
        )


@dataclass
class BargeInConfig:
    """Barge-in (TTS interruptibility — Phase 3, US-144 AC6). Disabled in Phase 1/2."""
    enabled: bool = False
    vad_threshold: float = 0.7  # VAD threshold in PARLATO state (overrides VADConfig.threshold)

    @classmethod
    def from_dict(cls, d: dict) -> "BargeInConfig":
        return cls(
            enabled=bool(d.get("enabled", False)),
            vad_threshold=float(d.get("vad_threshold", 0.7)),
        )


@dataclass
class AECConfig:
    """Acoustic Echo Cancellation (Phase 4, US-147 AC2). Optional with headphones (AC4)."""
    enabled: bool = False
    provider: str = "webrtc-apm"  # webrtc-apm | speexdsp | noisereduce

    @classmethod
    def from_dict(cls, d: dict) -> "AECConfig":
        return cls(
            enabled=bool(d.get("enabled", False)),
            provider=str(d.get("provider", "webrtc-apm")),
        )


@dataclass
class WakeWordConfig:
    """Wake word detection (openWakeWord, opt-in). Falls back to PTT if disabled."""
    enabled: bool = False
    keyword: str = "prometeus"          # activation keyword
    sensitivity: float = 0.5           # cosine similarity threshold (0.0–1.0)
    samples_dir: str = "voice/wake_word_samples"  # WAV sample directory for each keyword
    listen_chunk_ms: int = 100         # audio chunk duration in continuous listen (ms)
    min_detections: int = 2            # consecutive positive chunks to confirm (debounce)
    filter_threshold: int = 3          # max Levenshtein distance for first-turn filter (US-156)

    @classmethod
    def from_dict(cls, d: dict) -> "WakeWordConfig":
        return cls(
            enabled=bool(d.get("enabled", False)),
            keyword=str(d.get("keyword", "prometeus")),
            sensitivity=float(d.get("sensitivity", 0.5)),
            samples_dir=str(d.get("samples_dir", "voice/wake_word_samples")),
            listen_chunk_ms=int(d.get("listen_chunk_ms", 100)),
            min_detections=int(d.get("min_detections", 2)),
            filter_threshold=int(d.get("filter_threshold", 3)),
        )


@dataclass
class CaptureConfig:
    """Safety timers for the CATTURA loop (US-168 C4)."""
    onset_timeout_s: int = 5    # Abort turn if no VAD onset within N s (evaluated each frame)
    max_duration_s: int = 30    # Hard capture cap → IDLE with WARNING (never TRASCRIZIONE)

    @classmethod
    def from_dict(cls, d: dict) -> "CaptureConfig":
        return cls(
            onset_timeout_s=int(d.get("onset_timeout_s", 5)),
            max_duration_s=int(d.get("max_duration_s", 30)),
        )


_VALID_RUNTIME_PROVIDERS: frozenset[str] = frozenset(
    {"anthropic", "ollama", "mock", "claude-code", "cursor", "file-pipe"}
)

_DEFAULT_CLAUDE_CODE_ALLOWED_TOOLS = (
    "Read,Glob,Bash(git log*),Bash(git status),Bash(git diff*)"
)


@dataclass
class RuntimeConfig:
    """LLM runtime configuration (provider + per-adapter parameters)."""
    provider: str = "anthropic"       # anthropic | ollama | mock | claude-code
    llm_model: str = "claude-sonnet-4-6"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # --- claude-code adapter fields ---
    claude_code_bin: str = ""         # explicit path (auto-detect if empty)
    claude_code_timeout: int = 120    # max seconds waiting for response
    claude_code_max_spoken: int = 500 # max characters synthesized via TTS
    claude_code_allowed_tools: str = _DEFAULT_CLAUDE_CODE_ALLOWED_TOOLS
    claude_code_model: str = ""       # "" = use Claude Code default
    # --- cursor adapter fields ---
    cursor_rules_dir: str = ".cursor/rules"   # path relative to factory root
    cursor_max_rules_chars: int = 8000        # character budget for rules in system prompt
    # --- file-pipe adapter fields (US-158) ---
    pipe_poll_ms: int = 100        # ms fallback polling interval (watchdog unavailable); nominal path: event-driven
    pipe_timeout: int = 180        # total submit() timeout in seconds
    # --- file-pipe liveness check fields (US-167) ---
    liveness_check: bool = True          # Fail-fast active for file-pipe (deliberate change D3)
    consumer_alive_path: Optional[str] = None  # None → CONSUMER_ALIVE da side_channel.py
    consumer_alive_ttl_s: int = 10       # Heartbeat freshness TTL window (seconds)
    not_connected_message: str = "Nessuna sessione connessa."  # TTS audio feedback AC4

    @classmethod
    def from_dict(cls, d: dict) -> "RuntimeConfig":
        provider = str(d.get("provider", "anthropic")).lower()
        if provider not in _VALID_RUNTIME_PROVIDERS:
            raise ValueError(
                f"voice_channel.runtime.provider deve essere in "
                f"{sorted(_VALID_RUNTIME_PROVIDERS)}, ricevuto: {provider!r}"
            )
        return cls(
            provider=provider,
            llm_model=str(d.get("llm_model", "claude-sonnet-4-6")),
            ollama_base_url=str(d.get("ollama_base_url", "http://localhost:11434")),
            ollama_model=str(d.get("ollama_model", "llama3.2")),
            claude_code_bin=str(d.get("claude_code_bin", "")),
            claude_code_timeout=int(d.get("claude_code_timeout", 120)),
            claude_code_max_spoken=int(d.get("claude_code_max_spoken", 500)),
            claude_code_allowed_tools=str(
                d.get("claude_code_allowed_tools", _DEFAULT_CLAUDE_CODE_ALLOWED_TOOLS)
            ),
            claude_code_model=str(d.get("claude_code_model", "")),
            cursor_rules_dir=str(d.get("cursor_rules_dir", ".cursor/rules")),
            cursor_max_rules_chars=int(d.get("cursor_max_rules_chars", 8000)),
            pipe_poll_ms=int(d.get("pipe_poll_ms", 100)),
            pipe_timeout=int(d.get("pipe_timeout", 180)),
            liveness_check=bool(d.get("liveness_check", True)),
            consumer_alive_path=d.get("consumer_alive_path", None),
            consumer_alive_ttl_s=int(d.get("consumer_alive_ttl_s", 10)),
            not_connected_message=str(d.get("not_connected_message", "Nessuna sessione connessa.")),
        )


# ---------------------------------------------------------------------------
# VoiceConfig — root dataclass
# ---------------------------------------------------------------------------

@dataclass
class VoiceConfig:
    """
    Complete voice channel configuration (EP-041).

    All fields have explicit defaults: a missing voice_channel: section
    in factory.config.yaml produces VoiceConfig() with enabled=False (no-op, AC2).

    Access: cfg.stt.model, cfg.tts.voice, cfg.vad.threshold, ...
    """
    enabled: bool = False
    phase: int = 1
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    barge_in: BargeInConfig = field(default_factory=BargeInConfig)
    aec: AECConfig = field(default_factory=AECConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    log_level: str = "INFO"
    # Optional PID file path (US-159 AC5).
    # None → DEFAULT_PID_PATH in voice/app.py (~/.local/share/soli-voice/voice.pid).
    pid_file_path: Optional[str] = None

    @classmethod
    def from_factory_config(cls, raw: dict) -> "VoiceConfig":
        """
        Build VoiceConfig from the voice_channel: section of the raw YAML dict.

        Validations:
          - enabled: must be bool; TypeError otherwise.
          - phase: int in {1, 2, 3, 4}; ValueError if out of range.
          - log_level: str in {'DEBUG', 'INFO', 'WARNING'} (case-insensitive); ValueError otherwise.

        All sub-section fields use from_dict with explicit defaults:
        a missing or partial section does not cause KeyError.

        When enabled=False the factory works identically to v2.27 (AC2).
        """
        vc = raw.get("voice_channel", {})

        # --- enabled validation ---
        enabled = vc.get("enabled", False)
        if not isinstance(enabled, bool):
            raise TypeError(
                f"voice_channel.enabled deve essere bool, ricevuto: {type(enabled).__name__!r}"
            )

        # --- phase validation ---
        phase_raw = vc.get("phase", 1)
        try:
            phase = int(phase_raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"voice_channel.phase deve essere intero in {sorted(_VALID_PHASES)}, "
                f"ricevuto: {phase_raw!r}"
            )
        if phase not in _VALID_PHASES:
            raise ValueError(
                f"voice_channel.phase deve essere in {sorted(_VALID_PHASES)}, "
                f"ricevuto: {phase}"
            )

        # --- log_level validation (case-insensitive) ---
        log_level = str(vc.get("log_level", "INFO")).upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"voice_channel.log_level deve essere in {sorted(_VALID_LOG_LEVELS)}, "
                f"ricevuto: {log_level!r}"
            )

        return cls(
            enabled=enabled,
            phase=phase,
            stt=STTConfig.from_dict(vc.get("stt") or {}),
            tts=TTSConfig.from_dict(vc.get("tts") or {}),
            audio=AudioConfig.from_dict(vc.get("audio") or {}),
            vad=VADConfig.from_dict(vc.get("vad") or {}),
            barge_in=BargeInConfig.from_dict(vc.get("barge_in") or {}),
            aec=AECConfig.from_dict(vc.get("aec") or {}),
            runtime=RuntimeConfig.from_dict(vc.get("runtime") or {}),
            wake_word=WakeWordConfig.from_dict(vc.get("wake_word") or {}),
            capture=CaptureConfig.from_dict(vc.get("capture") or {}),
            log_level=log_level,
            pid_file_path=vc.get("pid_file_path", None),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_factory_config(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up the filesystem from start directory looking for factory.config.yaml."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "factory.config.yaml"
        if candidate.exists():
            return candidate
    return None


def load_config(path: Optional[str] = None) -> VoiceConfig:
    """
    Read the voice_channel: section from factory.config.yaml and return VoiceConfig.

    Args:
        path: explicit path to factory.config.yaml. If None, walk up the filesystem
              from cwd looking for the file (default behavior).

    Returns:
        VoiceConfig with values from factory.config.yaml, or VoiceConfig() with
        all defaults if the file does not exist or voice_channel: section is absent.

    Note:
        When enabled=False no audio/STT/TTS dependency imports occur.
        Dependencies sounddevice, faster_whisper, piper are imported lazily
        only in submodules that use them (AC2).
    """
    # Import PyYAML lazily — present in base project, NOT a voice dependency.
    try:
        import yaml
    except ImportError:
        # Graceful degradation: without PyYAML returns default config (enabled=False).
        # Voice channel cannot be enabled but factory remains operational.
        return VoiceConfig()

    if path is not None:
        config_path = Path(path)
    else:
        config_path = _find_factory_config()

    if config_path is None or not config_path.exists():
        return VoiceConfig()

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return VoiceConfig.from_factory_config(raw)
