---
name: voice-channel-install-protocol
description: Procedura di installazione e configurazione del Voice Channel (EP-041, PATTERN §30). Guida l'agente voice-channel-installer attraverso 5 fasi sequenziali per attivare l'interazione vocale con la factory.
---
# Skill — Voice Channel Install Protocol (EP-041)

Skill invocata dall'agente `voice-channel-installer` per installare e configurare
il canale vocale end-to-end. Ogni fase emette un verdict (`OK | WARN | ERROR`) e
log leggibile in chat.

## Invarianti

- **INV-VC-1**: mai leggere o stampare credenziali (`ANTHROPIC_API_KEY`, chiavi piper). Solo verificare che esistano nell'env.
- **INV-VC-2**: ogni passo bash che modifica il sistema (install pip, LaunchAgent) richiede gate umano esplicito prima dell'esecuzione.
- **INV-VC-3**: `factory.config.yaml` è scritto SOLO dopo conferma esplicita dell'utente sui valori.
- **INV-VC-4**: il canale vocale è opt-in. Se l'utente sceglie `voice_channel.enabled: false`, la skill si ferma con `SKIP` senza modifiche.

## Output schema

```yaml
phase_results:
  - phase: 1..5
    verdict: OK | WARN | ERROR | SKIP
    notes: <stringa>
factory_config_patch:     # blocco YAML pronto per injection in factory.config.yaml
  voice_channel: { ... }
service_installed: bool   # true se LaunchAgent installato
```

---

## Fase 1 — Prerequisiti Python + dipendenze

Verifica la catena di dipendenze necessarie.

### Step 1.1 — Versione Python
```bash
python3 --version
```
Richiede Python 3.9+. Se inferiore → ERROR + STOP.

### Step 1.2 — Pacchetto `voice` installabile
```bash
python3 -c "import voice" 2>/dev/null && echo "OK" || echo "MISSING"
```
Se MISSING: mostra il comando di installazione e chiedi conferma:
```bash
cd <factory_path>
pip install -e ".[voice]"
```
Dipendenze chiave incluse: `faster-whisper`, `piper-tts>=1.4`, `sounddevice`, `torch`, `openWakeWord>=0.6.0`, `anthropic`.

### Step 1.3 — Modello TTS italiano
Verifica che la voce configurata (`tts.voice`) sia presente nella `PIPER_MODEL_DIR`:
```bash
ls "${PIPER_MODEL_DIR:-$HOME/.local/share/piper/voices}" 2>/dev/null | grep -i "it_IT" || echo "MISSING"
```
Se MISSING: mostra il comando di download e chiedi conferma:
```bash
export PIPER_MODEL_DIR="$HOME/.local/share/piper/voices"
mkdir -p "$PIPER_MODEL_DIR"
python3 -c "
from piper.download import ensure_voice_exists, find_voice, get_voices
data_dir = '$PIPER_MODEL_DIR'
voices_info = get_voices(data_dir, update_voices=True)
key = 'it_IT-paola-medium'
*voice_name_parts, quality = key.split('-')
voice_name = '-'.join(voice_name_parts)
ensure_voice_exists(voice_name, [data_dir], data_dir, voices_info)
"
```

### Step 1.4 — Modello Silero VAD locale
Verifica il clone locale:
```bash
ls "$HOME/.cache/torch/hub/snakers4_silero-vad_main" 2>/dev/null && echo "OK" || echo "MISSING"
```
Se MISSING: mostra il comando e chiedi conferma:
```bash
mkdir -p "$HOME/.cache/torch/hub"
GIT_SSL_NO_VERIFY=true git clone https://github.com/snakers4/silero-vad \
  "$HOME/.cache/torch/hub/snakers4_silero-vad_main"
```

### Step 1.5 — ANTHROPIC_API_KEY
```bash
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "SET" || echo "MISSING"
```
Se MISSING: WARN (non blocca). La chiave può essere fornita all'installazione del servizio (Fase 4).

### Step 1.6 — PIPER_MODEL_DIR
Verifica che sia esportata o aggiunta al profilo shell. Se assente: WARN + mostra:
```bash
echo 'export PIPER_MODEL_DIR="$HOME/.local/share/piper/voices"' >> ~/.zshrc
source ~/.zshrc
```

**Verdict Fase 1**: OK se tutti gli step critici (1.1, 1.2, 1.3, 1.4) passano. WARN se 1.5/1.6 mancano.

---

## Fase 2 — Configurazione factory.config.yaml

Raccoglie le opzioni utente e prepara la patch per `voice_channel:`.

### Domande da porre all'utente (usa AskUserQuestion o chat):

| Campo | Descrizione | Default |
|---|---|---|
| `enabled` | Abilitare il canale vocale? | `true` |
| `stt.model` | Modello Whisper STT | `small` (tiny/base/small/medium/large) |
| `tts.voice` | Voce piper italiana | `it_IT-paola-medium` |
| `runtime.provider` | Provider LLM | `anthropic` (anthropic/ollama/mock) |
| `runtime.llm_model` | Modello LLM | `claude-sonnet-5-5` |
| `wake_word.enabled` | Attivare wake word "Prometeus"? | `true` |
| `wake_word.keyword` | Parola chiave | `prometeus` |
| `wake_word.sensitivity` | Soglia similarity (0.0–1.0) | `0.75` |

### Mostra il blocco YAML finale all'utente per conferma prima di scrivere.

### Scrivi `voice_channel:` in factory.config.yaml:
- Se il blocco esiste già: aggiorna solo i campi modificati (non distruggere commenti).
- Se non esiste: appendi alla fine del file.
- Invariante INV-VC-3: non scrivere senza conferma utente.

---

## Fase 3 — Registrazione campioni wake word (se wake_word.enabled)

### Step 3.1 — Verifica campioni esistenti
```bash
ls voice/wake_word_samples/prometeus/*.wav 2>/dev/null | wc -l
```
Se ≥ 5 campioni già presenti → SKIP Fase 3 (chiedi conferma per ri-registrare).

### Step 3.2 — Guida alla registrazione
Mostra le istruzioni in chat:
```
Pronti a registrare 5 campioni della parola chiave.
Avrai ~2 secondi per pronunciare il wake word dopo il prompt "Registrando...".
Pronuncia il wake word in modo naturale, con leggere variazioni di tono.
```
Chiedi conferma, poi esegui:
```bash
cd <factory_path>
python3 voice/tools/record_samples.py
```

### Step 3.3 — Verifica campioni registrati
```bash
ls voice/wake_word_samples/prometeus/*.wav | wc -l
```
Se < 5: WARN (il rilevatore funziona con meno campioni ma con accuracy ridotta).

---

## Fase 4 — Installazione LaunchAgent (macOS, opt-in)

Chiedi all'utente se vuole installare il canale vocale come servizio macOS (auto-start al login).

Se sì:
1. Verifica che `ANTHROPIC_API_KEY` sia nell'env (o chiedi di inserirla).
2. Chiedi conferma prima di eseguire lo script.
3. Esegui:
```bash
ANTHROPIC_API_KEY="<key>" bash voice/tools/install-service.sh
```
Se no: mostra il comando manuale per avviare il canale:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export PIPER_MODEL_DIR="$HOME/.local/share/piper/voices"
python3 -m voice.app
```

---

## Fase 5 — Validazione (smoke test)

### Step 5.1 — Import check
```bash
python3 -c "
import voice.config, voice.audio.capture, voice.stt.faster_whisper_stt
import voice.tts.piper_tts, voice.vad.silero_vad
print('Import OK')
"
```
Se fallisce: mostra il traceback e ferma con ERROR.

### Step 5.2 — Config check
```bash
python3 -c "
from voice.config import load_config
cfg = load_config()
print('Config OK — voice_channel.enabled:', cfg.enabled)
print('STT model:', cfg.stt.model)
print('TTS voice:', cfg.tts.voice)
print('Wake word:', cfg.wake_word.enabled, '/', cfg.wake_word.keyword)
"
```

### Step 5.3 — Riepilogo installazione
Mostra in chat:
```
╔══════════════════════════════════════════╗
║   Voice Channel — Installazione completa ║
╚══════════════════════════════════════════╝
✓ Dipendenze Python installate
✓ Modello TTS: it_IT-paola-medium
✓ Modello VAD: silero-vad (locale)
✓ Campioni wake word: N campioni
✓ factory.config.yaml aggiornato
[✓ LaunchAgent installato] (se applicabile)

Per avviare manualmente:
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 -m voice.app

Per i log del servizio:
  tail -f ~/Library/Logs/soli-voice/voice-factory.log

Comandi vocali disponibili:
  "Prometeus"           → attiva wake word
  "handsfree"           → modalità handsfree (no wake word)
  "disattiva handsfree" → torna a modalità normale
```
