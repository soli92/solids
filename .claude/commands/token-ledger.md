---
description: Mostra il token ledger della sessione corrente (token reali + costo stimato). Flag --full per il display box.
argument-hint: "[--full] [--transcript <path>]"
allowed-tools: Bash
---

Comando della capability [[token-ledger]] (EP-022, v2.21). Legge il transcript JSONL
della sessione corrente (e dei suoi subagenti, una risposta per `message.id`) e mostra token
consumati + costo stimato a listino.

Complementa l'hook `Stop` automatico (che mostra il one-liner dopo ogni risposta) con
un readout on-demand e il display completo via `--full`.

Il ledger mostra il costo, non lo giudica: per confrontarlo con le soglie di sessione, giorno
e settimana usa `/cost-alert` (skill `cost-alert-protocol`).

## Sintassi

```
/token-ledger [--full] [--transcript <path>]
```

## Flag

- `--full` — box completo con breakdown input/output/cache invece del one-liner
- `--transcript <path>` — path esplicito al transcript JSONL (override auto-discovery)

## Comportamento

1. Legge `factory.config.yaml`. Se `analytics.token_ledger.enabled: false` → mostra nota
   ma esegue comunque (il comando è sempre disponibile anche con capability off).
2. Individua il transcript JSONL più recente per la CWD (`~/.claude/projects/<cwd>/*.jsonl`).
3. Aggrega tutti i token `message.usage` dai messaggi assistant del transcript.
4. Risolve il pricing da `analytics/pricing.yaml` (fallback prefix-based se file assente).
5. Mostra il display (compatto o box).

## Invocazione

```bash
python3 "$CLAUDE_PROJECT_DIR/tools/analytics/show-session-tokens.py" $ARGS
```

dove `$ARGS` = `--full` se il flag è passato.

## Note

- I token mostrati sono **reali** (dal transcript API, campo `message.usage`), non stime.
- La granularità è **per sessione** (dal primo messaggio al momento dell'invocazione).
- Il costo include risparmio cache (`cache_read_input_tokens`).
- Per reportistica per-TSK/wave usa `/analytics` (EP-009 `cost-and-time-analytics`).
