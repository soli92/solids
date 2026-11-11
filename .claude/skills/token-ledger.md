---
id: token-ledger
version: v2.21
capability: EP-022
opt_in: analytics.token_ledger.enabled
depends_on_skill: cost-and-time-analytics
pattern_refs: [temporal-budget-governor, task-analytics-cost-estimation-capability]
description: Mostra il ledger token della sessione corrente con costo stimato dopo ogni operazione (EP-022) per fornire visibilità economica inline. Display puro di dati reali dal transcript; non prende decisioni.
---

# Skill: token-ledger

> **Visibilità economica inline** — mostra il costo cumulativo della sessione corrente
> dopo ogni operazione. Complementa `cost-and-time-analytics` (reportistica batch EP-009)
> con un readout immediato leggibile senza aprire report.

A differenza del `temporal-budget-governor` (che monitora il *ratio* budget/consumo per
i loop evaluator-optimizer), il token-ledger è **display puro**: mostra dati reali dal
transcript Claude Code, non stime. Non prende decisioni.

Riferimenti: `harvest-session-tokens.py` (batch harvest EP-013), `show-session-tokens.py`
(display real-time — tool implementativo di questa skill), settings.json hook `Stop`
(trigger automatico), ADR-022 (pricing.yaml resolution), [[task-analytics-cost-estimation-capability]].

## Architettura

```
Claude Code finisce una risposta
        │
        ▼  (hook Stop — settings.json)
show-session-tokens.py --from-hook
        │
        ├─ legge il transcript JSONL (~/.claude/projects/<cwd>/<sessione>.jsonl)
        │   e i suoi subagents/agent-*.jsonl
        │   → token reali da message.usage, una risposta API per message.id
        │     (Claude Code scrive una riga per content block con lo stesso usage)
        ├─ risolve il pricing di ogni modello da analytics/pricing.yaml (ADR-022)
        │   → fallback prefix-based se modello, yaml o PyYAML mancano
        ├─ calcola, per modello: input·in + output·out + cache_read·cr
        │     + (cache_write − cache_write_1h)·cw + cache_write_1h·cw1h
        │   (cache a TTL 1h prezzata a parte; senza il campo nel listino, a 5m)
        └─ stampa one-liner ◉ TOKENS ... (il risparmio da cache è mostrato, non sommato)
```

Il transcript è **la sorgente di verità** per i token reali (campo `message.usage` per ogni
risposta assistant, contata una volta per `message.id`, subagenti compresi: stessa regola di
`harvest-session-tokens.py`). Granularità: aggregato **per sessione** (dalla prima risposta della
sessione al momento dell'hook). Per confrontare il costo con soglie e abbonamento: `/cost-alert`. Distinto dalla granularità per-wave EP-013 che il
`harvest-session-tokens.py` produce a SessionEnd.

## Display format

**Compatto (default, hook Stop):**
```
◉ TOKENS  in:42.3k  out:8.1k  💾 -$0.0031  │  sessione: ~$0.1527
```

**Completo (flag `--full` o comando `/token-ledger --full`):**
```
╭────────────────────────────────────────────────────╮
│  TOKEN LEDGER — sessione corrente                  │
│  Modelli: claude-sonnet-4-6                        │
├────────────────────────────────────────────────────┤
│  Input:           42.3k  tokens                    │
│  Output:           8.1k  tokens                    │
│  Cache read:      31.2k  tokens                    │
│  Risparmio:      $0.0031                           │
├────────────────────────────────────────────────────┤
│  Costo sessione:  ~$0.1527                         │
╰────────────────────────────────────────────────────╯
```

## Prerequisiti

- Hook `Stop` configurato in `.claude/settings.json` (aggiunto automaticamente v2.21).
- Python 3.8+ (presente in qualunque Mac con Claude Code).
- `analytics/pricing.yaml` presente per costi precisi; assente → fallback prefix-based
  (Sonnet $3/$15, Opus $5/$25, Haiku $1/$5).
- PyYAML (`pip install pyyaml`) per la lettura del pricing; assente → fallback silente.

## Vincoli

- **Display-only**: non scrive nel JSONL store (`harvest-session-tokens.py` è il writer
  canonico a SessionEnd per EP-013). Nessuna duplicazione eventi.
- **Fail-open**: qualunque errore (transcript non trovato, parsing fallito, timeout) →
  skip silente. Mai interrompere il workflow Claude per mancanza di metriche.
- **Timeout 5s**: il hook ha `timeout: 5` — il parsing deve completare in meno di 5 secondi
  anche su transcript grandi. Il loop su JSONL è O(linee) e tipicamente < 1s.
- **Self-observation**: il display dell'hook è parte della sessione, quindi i token del
  messaggio che ha triggato l'hook sono inclusi nel conteggio. Effetto: il costo mostrato
  è leggermente inferiore al reale perché i token dell'hook stesso non sono ancora nel
  transcript al momento del parsing. Accettabile (differenza < 0.5%).

## Integrazione con parallel-scheduling

Quando `analytics.token_ledger.auto_call_on_wave_close: true`, l'orchestrator invoca
lo script con `--full` al termine di ogni wave (wave_close). Questo fornisce visibilità
sul costo di ogni wave individuale oltre al totale sessione dell'hook Stop.

Invocazione wave_close (da aggiungere in `parallel-scheduling.md` Fase 5 — Dispatch):
```
python3 "$CLAUDE_PROJECT_DIR/tools/analytics/show-session-tokens.py" --full
```

## Aggiornamento pricing

I prezzi vengono da `analytics/pricing.yaml` (single-writer umano, ADR-022). Se il modello
usato non è nella tabella → fallback prefix-based con nota `[pricing fallback]`. Per
aggiornare i prezzi: aggiungere nuova entry con `valid_from:` in `pricing.yaml` (mai editare
entry esistenti — no-retroactive ADR-022 §E).

## Display per adapter (agent-agnostic)

La capability è **adapter-agnostic** ma il meccanismo di display varia per adapter:

| Adapter | Meccanismo | Note |
|---|---|---|
| `.claude/` Claude Code | Claude chiama script esplicitamente + hook Stop (backup) | Chat VS Code non mostra stdout hook; Claude include output inline |
| `.cursor/` Cursor | Rule in `adapters/cursor/` che invoca lo script equivalente | Richiede script adapter-specifico |
| `.aider/` Aider | Hook `after-send` in aider config | Richiede port dello script |
| Altri | Hook stop/session-end del tool | Adattare path transcript per il tool specifico |

Il path `~/.claude/projects/<cwd>/*.jsonl` è Claude Code-specifico. Per altri adapter
lo script va adattato al percorso del transcript del tool specifico (il formato JSONL
con `message.usage` è Claude Code; altri tool usano formati diversi).

### Alternativa compatta — `statusline-ledger.py`

Per ambienti dove la statusbar VS Code è il canale di display preferito (es. estensione
Claude Code con statusbar custom), `tools/analytics/statusline-ledger.py` è uno script
**stdin-based** complementare a `show-session-tokens.py`.

Differenze chiave:

| Caratteristica | `show-session-tokens.py` | `statusline-ledger.py` |
|---|---|---|
| Input | Legge transcript JSONL dal filesystem | Legge da stdin (stream-friendly) |
| Output | One-liner `◉ TOKENS ...` in chat | Stringa compatta per statusline |
| Uso tipico | Hook Stop + output inline Claude | VS Code `statusLine` setting |

Integrazione in `.vscode/settings.json` (o equivalente estensione):
```json
{
  "statusLine": "python3 tools/analytics/statusline-ledger.py"
}
```

A flag `analytics.token_ledger.enabled: false` → entrambi gli script sono no-op
(fail-open). `statusline-ledger.py` non introduce nuove dipendenze rispetto a
`show-session-tokens.py`.

## Backward compat

`analytics.token_ledger.enabled: false` (default factory derivate) → skip display.
Comportamento identico a v2.20.
