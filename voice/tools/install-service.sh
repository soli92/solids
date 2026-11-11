#!/usr/bin/env bash
# voice/tools/install-service.sh — Install voice channel as macOS LaunchAgent.
#
# Service starts automatically at login and restarts on crash.
# API key saved in ~/.config/soli-voice/env (permissions 600, never in plist).
#
# Uso:
#   bash voice/tools/install-service.sh
#   # or with API key already in environment:
#   ANTHROPIC_API_KEY=sk-... bash voice/tools/install-service.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAUNCH_SCRIPT="$REPO_DIR/voice/tools/launch-voice.sh"
PLIST_LABEL="com.soli.voice-factory"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
ENV_DIR="$HOME/.config/soli-voice"
ENV_FILE="$ENV_DIR/env"
LOG_DIR="$HOME/Library/Logs/soli-voice"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Soli Voice Factory — Installazione servizio   ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Repo:   $REPO_DIR"
echo "Plist:  $PLIST_PATH"
echo "Logs:   $LOG_DIR/"
echo ""

# --- Verify macOS ---
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERRORE: questo script supporta solo macOS (launchd)."
    echo "Su Linux usa systemd: crea /etc/systemd/user/voice-factory.service"
    exit 1
fi

# --- Find Python3 with voice installed ---
PYTHON3="$(command -v python3)"
echo "Python: $PYTHON3 ($(python3 --version 2>&1))"

# Test that voice package is importable
if ! "$PYTHON3" -c "import voice" 2>/dev/null; then
    echo ""
    echo "ATTENZIONE: il pacchetto 'voice' non è importabile."
    echo "Installa le dipendenze con:"
    echo "  cd $REPO_DIR && pip install -e '.[voice]'"
    echo ""
fi

# --- ANTHROPIC_API_KEY (optional if runtime provider = ollama) ---
# Check if already saved in env file (previous installation)
existing_key=""
if [[ -f "$ENV_FILE" ]]; then
    existing_key=$(grep -m1 '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
fi

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    api_key="$ANTHROPIC_API_KEY"
    echo "✓ API key letta dall'ambiente"
elif [[ -n "$existing_key" ]]; then
    api_key="$existing_key"
    echo "✓ API key letta dal file precedente ($ENV_FILE)"
else
    api_key=""
    echo "⚠  ANTHROPIC_API_KEY non impostata — ok se runtime provider = ollama"
fi

# --- Create protected env file ---
mkdir -p "$ENV_DIR"
cat > "$ENV_FILE" <<EOF
# Soli Voice Factory — environment variables for launchd
# Generato da install-service.sh il $(date '+%Y-%m-%d %H:%M:%S')
ANTHROPIC_API_KEY=${api_key}
PIPER_MODEL_DIR=${HOME}/.local/share/piper/voices
PYTHON3=${PYTHON3}
EOF
chmod 600 "$ENV_FILE"
echo "✓ Env salvato in $ENV_FILE (permessi 600)"

# --- Create log dir ---
mkdir -p "$LOG_DIR"

# --- Make launch script executable ---
chmod +x "$LAUNCH_SCRIPT"

# --- Unload any previous instance ---
if launchctl list 2>/dev/null | grep -q "$PLIST_LABEL"; then
    echo "Servizio già presente — reload in corso..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# --- Generate plist ---
# Call Python directly (no shell wrapper) to avoid macOS TCC blocks
# on scripts in ~/Documents. Env vars are inline in plist.
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>-m</string>
        <string>voice.app</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PIPER_MODEL_DIR</key>
        <string>${HOME}/.local/share/piper/voices</string>
        <key>ANTHROPIC_API_KEY</key>
        <string>${api_key}</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${REPO_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/voice-factory.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/voice-factory.error.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
PLIST

echo "✓ Plist generato in $PLIST_PATH"

# --- Load service ---
launchctl load "$PLIST_PATH"
echo "✓ Servizio avviato"
echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│  Canale vocale installato come LaunchAgent      │"
echo "│  Si avvia automaticamente ad ogni login         │"
echo "├─────────────────────────────────────────────────┤"
echo "│  Stato:    launchctl list | grep soli           │"
echo "│  Log:      tail -f $LOG_DIR/voice-factory.log"
echo "│  Stop:     launchctl unload $PLIST_PATH"
echo "│  Rimuovi:  bash voice/tools/uninstall-service.sh│"
echo "└─────────────────────────────────────────────────┘"
