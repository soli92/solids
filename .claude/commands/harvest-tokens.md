---
description: Registra manualmente il token-usage della sessione corrente nell'event store analytics (workaround VS Code hook non eseguiti).
argument-hint: "[--dry-run] [--session-id=<uuid>]"
---

# /harvest-tokens — Harvest token-usage sessione corrente

> v1.0 — US-309 / TSK-712 (EP-069): porting da factory derivata con path dinamici
> (nessun percorso cablato; discovery identica a `token-ledger` e `show-session-tokens.py`).

Argomenti utente: `$ARGUMENTS`

Raccoglie i token della sessione corrente (o di una sessione indicata) dal transcript JSONL
di Claude Code e li scrive nell'event store `analytics/events/YYYY-MM.jsonl` via
`tools/analytics/harvest-session-tokens.py`. Idempotente: ri-eseguire non duplica.
Conta una risposta API per `message.id`, raccoglie anche i `subagents/` della sessione e porta
nell'evento la quota di scritture in cache a TTL 1h (`cache_write_1h`). `/session-close` lo
esegue da sé (Fase 1h): a mano serve solo fuori da quel flusso.

## Quando serve

L'estensione VS Code di Claude Code **non esegue** gli hook `Stop`/`SessionEnd` di
`settings.json`. Il ledger in-sessione (statusLine) funziona normalmente, ma l'event
store persistente `analytics/events/` non viene popolato. Usa questo comando a fine
sessione prima di `/session-close` o di qualsiasi report analytics multi-sessione.

L'hook `SessionEnd` in `settings.json` gestisce lo stesso compito in modo automatico
quando funziona (es. CLI, terminale nativo). Questo comando e' il ripiego manuale.

## Procedura

### Step 1 — Individua il transcript

La directory dei transcript viene derivata dalla `$CLAUDE_PROJECT_DIR` (o `$PWD` come
fallback) con il medesimo path-mangling usato da `show-session-tokens.py` e
`harvest-session-tokens.py`: ogni `/` e ogni `.` diventano `-`.

```bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
MANGLED=$(echo "$PROJECT_DIR" | sed 's|[/.]|-|g')
TRANSCRIPTS_DIR="$HOME/.claude/projects/$MANGLED"

# Se --session-id=<uuid> e' stato fornito, usa quel file; altrimenti il piu' recente
if [[ "$ARGUMENTS" =~ --session-id=([a-f0-9-]+) ]]; then
  TRANSCRIPT="$TRANSCRIPTS_DIR/${BASH_REMATCH[1]}.jsonl"
else
  TRANSCRIPT="$(ls -t "$TRANSCRIPTS_DIR"/*.jsonl 2>/dev/null | head -1)"
fi

if [[ ! -f "$TRANSCRIPT" ]]; then
  echo "ERRORE: transcript non trovato in $TRANSCRIPTS_DIR"
  exit 1
fi

echo "Transcript: $TRANSCRIPT"
echo "Dimensione: $(wc -l < "$TRANSCRIPT") righe"
```

### Step 2 — Esegui il harvest

```bash
DRY_RUN_FLAG=""
if [[ "$ARGUMENTS" =~ --dry-run ]]; then
  DRY_RUN_FLAG="--dry-run"
fi

python3 "${CLAUDE_PROJECT_DIR}/tools/analytics/harvest-session-tokens.py" \
  "$TRANSCRIPT" $DRY_RUN_FLAG
```

Il flag `--project` non viene passato: lo script ricava il `project_id` da
`os.path.basename(os.getcwd())`, che e' il nome corretto per qualunque factory della
flotta (nessuna costante da aggiornare nelle derivate).

### Step 3 — Verifica evento scritto

Dopo il harvest, stampa il riepilogo degli eventi e il costo cumulato aggiornato:

```bash
OUT="${TMPDIR:-/tmp}/agentic-cost-$$.json"
python3 "${CLAUDE_PROJECT_DIR}/tools/analytics/compute-agentic-cost.py" > "$OUT"
python3 - "$OUT" <<'PY'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read().strip()
if not raw:
    # lo script ha gia' detto perche' su stderr (es. analytics.measurement.enabled non attivo)
    print("(nessun riepilogo di costo: compute-agentic-cost non ha prodotto JSON, motivo qui sopra)")
    sys.exit(0)
d = json.loads(raw)
print(f"Events totali: {d['events_considered']}")
print(f"Costo totale: ${d['cost']:.2f} {d['currency']}")
for mid, cost in sorted(d["breakdown"]["per_model"].items(), key=lambda x: -x[1]):
    print(f"  {mid}: ${cost:.2f}")
PY
rm -f "$OUT"
```

Lo stderr dello script **non** si sopprime: se il riepilogo manca, il motivo deve restare
visibile (in passato l'errore spariva in `2>/dev/null`). Lo script e' Python (US-327) e gira
anche su Windows senza bash; `compute-agentic-cost.sh` resta come rimando per i chiamanti storici.

### Output atteso

Conferma JSON che l'evento e' stato registrato. Se il transcript non contiene sessioni
nuove non ancora nel JSONL, lo script lo segnala (idempotente via sha256 dedup).

## Note tecniche

- **Nessun path cablato**: la directory transcript e' derivata a runtime dalla CWD.
  Stesso algoritmo di `show-session-tokens.py:find_transcript()` e di
  `harvest-session-tokens.py` in modalita' `--from-hook` (sorgente autorevole: le due
  funzioni Python; questo comando non le duplica, le rispecchia in bash).
- **`--all-sessions`**: `harvest-session-tokens.py` non supporta questo flag (elabora
  un transcript alla volta). Per backfill di piu' sessioni, chiamare il comando piu'
  volte passando `--session-id=<uuid>` per ciascuna.
- **Idempotenza**: il dedup avviene via sha256 sul campo `task_id` (sessione + scope +
  model). Ri-eseguire sullo stesso transcript non duplica gli eventi.
