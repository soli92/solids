#!/usr/bin/env bash
# voice/tools/voice-pipe-watcher.sh — Voice channel visibility watcher (provider-agnostic).
#
# Monitors voice-in.json (utterance) and voice-state.json (FSM states) and prints
# readable events to stdout, ready for Claude Code Monitor tool ingestion.
#
# Works with ANY runtime provider (claude-code, file-pipe, mock):
#   - voice-in.json   — written by FSM after each confirmed transcription
#   - voice-state.json — written by FSM on each state transition
#
# Never writes anything: read-only access (observer pattern).
#
# Fix race condition (feedback #10 E2E 2026-07-10): 50ms delay after inbox touch.
#
# State emoji → readable chat label:
#   IDLE          → 🔇 In attesa
#   CATTURA       → 🎙️  Ascolto...
#   TRASCRIZIONE  → ✍️  Trascrivo...
#   ELABORAZIONE  → ⚙️  Elaboro... [testo]
#   PARLATO       → 🔊 Rispondo...
#
# Usage (via Monitor tool in Claude Code):
#   command: bash voice/tools/voice-pipe-watcher.sh

INBOX="$HOME/.local/share/soli-voice/voice-in.json"
STATE="$HOME/.local/share/soli-voice/voice-state.json"

# Initialize CURRENT mtimes (ignore files present at boot — avoid immediate fire)
last_inbox_mtime=$(stat -f "%m" "$INBOX" 2>/dev/null || echo "0")
last_state_mtime=$(stat -f "%m" "$STATE" 2>/dev/null || echo "0")

_state_emoji() {
    case "$1" in
        IDLE)          echo "🔇 In attesa" ;;
        CATTURA)       echo "🎙️  Ascolto..." ;;
        TRASCRIZIONE)  echo "✍️  Trascrivo..." ;;
        ELABORAZIONE)  echo "⚙️  Elaboro..." ;;
        PARLATO)       echo "🔊 Rispondo..." ;;
        *)             echo "❓ $1" ;;
    esac
}

while true; do
    # --- New transcribed utterance ---
    if [ -f "$INBOX" ]; then
        cur_inbox=$(stat -f "%m" "$INBOX" 2>/dev/null || echo "0")
        if [ "$cur_inbox" != "$last_inbox_mtime" ]; then
            sleep 0.05  # Fix race: wait for write completion
            if [ -f "$INBOX" ]; then
                text=$(python3 -c "import json,sys; d=json.load(open('$INBOX')); print(d.get('text',''))" 2>/dev/null)
                if [ -n "$text" ]; then
                    echo "🎤 Tu: $text"
                fi
            fi
            last_inbox_mtime="$cur_inbox"
        fi
    fi

    # --- FSM transition ---
    if [ -f "$STATE" ]; then
        cur_state=$(stat -f "%m" "$STATE" 2>/dev/null || echo "0")
        if [ "$cur_state" != "$last_state_mtime" ]; then
            state=$(python3 -c "import json,sys; d=json.load(open('$STATE')); print(d.get('state',''))" 2>/dev/null)
            if [ -n "$state" ] && [ "$state" != "IDLE" ]; then
                echo "$(_state_emoji "$state")"
            fi
            last_state_mtime="$cur_state"
        fi
    fi

    sleep 0.3
done
