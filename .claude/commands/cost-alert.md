---
description: Controlla i costi in token dell'operatore (sessione, giorno, settimana, mese) contro le regole di analytics/alert-rules.yaml; mostra e prende in carico gli alert pendenti.
argument-hint: "[--period=session|daily|weekly|monthly|all] [--breakdown] [--pending] [--ack=<id>|--ack-all] [--json]"
---

# /cost-alert — Controllo dei costi in token

Argomenti utente: `$ARGUMENTS`

Esegue la skill `cost-alert-protocol` (`.claude/skills/cost-alert-protocol.md`): leggila
prima di procedere. Il comando non ha logica propria: ogni numero viene da
`tools/analytics/cost_alert.py`.

## Procedura

### Step 1 — Parse argomenti

| Flag | Azione |
|---|---|
| (nessuno) | `check --period all` |
| `--period=<p>` | `check --period <p>` (`session`, `daily`, `weekly`, `monthly`, `all`) |
| `--breakdown` | `breakdown --period <p>` (default `daily`): costo per scope, modello e sessioni più costose |
| `--pending` | `pending`: alert dell'operatore non ancora presi in carico |
| `--ack=<id>` / `--ack-all` | `ack --id <id>` / `ack --all` |
| `--json` | passa `--json` al tool |

Flag non riconosciuti: ignorali con un avviso in chat.

### Step 2 — Esecuzione

```bash
python3 tools/analytics/cost_alert.py <sottocomando> [opzioni]
```

Riporta l'output integralmente, note comprese (skill §Step 2).

### Step 3 — Escalation

Solo per `check`: se il verdetto ha regole `escalate` superate, segui la skill §Step 3
(agente `cost-alert` se `agent_enabled: true`, altrimenti valgono come `warn`). Con `--json`
leggi il campo `escalations`.

## Esempi

```bash
/cost-alert                      # tutte le regole
/cost-alert --period=daily       # solo la giornata
/cost-alert --breakdown --period=weekly
/cost-alert --pending
/cost-alert --ack-all
```

## Configurazione

- Interruttori: `factory.config.yaml → analytics.cost_alert.enabled` / `.agent`.
- Soglie: `analytics/alert-rules.yaml` (modifica solo via PR).
- A flag spento il tool risponde «nessun controllo» e il comando si limita a riportarlo.
