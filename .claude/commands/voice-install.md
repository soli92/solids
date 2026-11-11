---
description: >-
  Installa e configura il Voice Channel come capability opt-in della factory. Guida attraverso prerequisiti pip, modelli STT/TTS/VAD, campioni wake word, configurazione factory.config.yaml e LaunchAgent macOS. Supporta sub-comandi: diagnose, status, restart, uninstall.
argument-hint: "[diagnose|status|restart|uninstall]"
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /voice-install — Voice Channel Installer

Argomenti: `$ARGUMENTS`

Dispatcha l'agente `voice-channel-installer` con il sub-comando appropriato.

## Risoluzione sub-comando

Parse `$ARGUMENTS`:

- **nessun argomento** → modalità `install` (installazione guidata completa)
- **`diagnose`** → diagnostica prerequisiti + config, senza modifiche
- **`status`** → stato servizio LaunchAgent + ultimi log
- **`restart`** → restart servizio (con gate umano)
- **`uninstall`** → rimozione servizio LaunchAgent (con gate umano)

## Dispatch agente

Avvia l'agente `voice-channel-installer` con il sub-comando risolto.

L'agente:
1. Legge `factory.config.yaml` per lo stato corrente di `voice_channel:`.
2. Segue la skill `voice-channel-install-protocol` per le 5 fasi di installazione.
3. Richiede gate umano esplicito prima di ogni operazione bash che modifica il sistema.
4. Emette un riepilogo finale con lo stato di ogni fase.

## Note

- Backward compat: se `voice_channel.enabled: false` (default), il comando guida
  l'attivazione opt-in senza modificare il comportamento corrente della factory.
- macOS only per il LaunchAgent; su altri OS fornisce il comando manuale.
- La ANTHROPIC_API_KEY non viene mai letta o stampata dall'agente (INV-VC-1).
