# Comando: /voice-install

> Equivalente Cursor del comando Claude Code `/voice-install` (`.claude/commands/voice-install.md`).
> Installa e configura il Voice Channel (EP-041) come capability opt-in della factory. Guida attraverso prerequisiti pip, modelli STT/TTS/VAD, campioni wake word, configurazione factory.config.yaml e…

> Procedura: [voice-channel-install-protocol](mdc:.cursor/rules/skills/voice-channel-install-protocol.mdc)

> **Gate**: `factory.config.yaml.voice_channel.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

## Limitazioni Cursor

- I tool deterministici sotto `tools/` sono invocati da terminale e si comportano in modo identico: la differenza sta solo nell'agente che li chiama.
