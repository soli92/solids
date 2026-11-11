#!/usr/bin/env bash
# voice/tools/uninstall-service.sh — Rimuove il LaunchAgent canale vocale.
#
# Uso: bash voice/tools/uninstall-service.sh

set -euo pipefail

PLIST_LABEL="com.soli.voice-factory"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo "=== Disinstallazione Canale Vocale Factory ==="

if launchctl list 2>/dev/null | grep -q "$PLIST_LABEL"; then
    launchctl unload "$PLIST_PATH" 2>/dev/null && echo "✓ Servizio fermato"
fi

if [[ -f "$PLIST_PATH" ]]; then
    rm "$PLIST_PATH"
    echo "✓ Plist rimosso: $PLIST_PATH"
else
    echo "Plist non trovato (già rimosso?)"
fi

echo ""
echo "Il file ~/.config/soli-voice/env non è stato rimosso."
echo "Per rimuovere anche le credenziali: rm -rf ~/.config/soli-voice"
