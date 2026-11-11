# Comando: /tavola-rotonda

> Equivalente Cursor del comando Claude Code `/tavola-rotonda` (`.claude/commands/tavola-rotonda.md`).
> Procedura: vedi [tavola-rotonda-protocol](mdc:.cursor/rules/skills/tavola-rotonda-protocol.mdc).

**Sintassi**:
```
/tavola-rotonda <topic>
/tavola-rotonda <topic> --partecipanti=<agent1>,<agent2>,...
/tavola-rotonda <topic> --max-round=<N>
/tavola-rotonda <topic> --partecipanti=<a>,<b> --max-round=<N> --budget=<USD>
```

> **Gate**: `factory.config.yaml.tavola_rotonda.enabled: true`. Se `false` → STOP esplicito con istruzioni.

## Procedura

1. **Gate**: verifica `tavola_rotonda.enabled`. STOP esplicito se `false`.
2. **Parse argomenti**: topic (obbligatorio, max 120 char), `--partecipanti`, `--max-round`, `--budget`.
3. **Risoluzione parametri** (precedenza: flag > config > default): `partecipanti` (min 2), `max_round` (default 4), `budget_max_cost_usd` (obbligatorio — STOP se assente).
4. **Validazione agenti**: verifica esistenza `.claude/agents/<slug>.md` per ogni partecipante.
5. **Esecuzione** [tavola-rotonda-protocol](mdc:.cursor/rules/skills/tavola-rotonda-protocol.mdc) 5 fasi: Setup → Posizioni → Confronto → Convergenza → Sintesi.
6. **Output**: registro decisioni in `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` + append `wiki/log.md`.

## Vincoli

- Budget obbligatorio (INV-TR-3): nessuna sessione parte senza `budget.max_cost_usd`.
- Almeno 2 partecipanti (diversita' strutturale minima).
- Override `--partecipanti/--max-round/--budget` sono one-shot: non modificano `factory.config.yaml`.

## Config minima

```yaml
tavola_rotonda:
  enabled: true
  partecipanti: [be-dev, lead-architect]
  max_round: 4
  budget:
    max_cost_usd: 2.00
```

## Limitazioni Cursor

- Le fasi di [tavola-rotonda-protocol](mdc:.cursor/rules/skills/tavola-rotonda-protocol.mdc) vanno eseguite sequenzialmente (no parallel fan-out in Cursor).
- I partecipanti sono ruoli dichiarati nella stessa sessione Chat, non sub-agent separati.
