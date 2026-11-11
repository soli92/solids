# Comando: /analytics

> Equivalente Cursor del comando Claude Code `/analytics` (`.claude/commands/analytics.md`).
> Invoca analytics-reporter su uno scope (project/sprint/period/TSK) per audit costi e ROI (EP-009 US-038). Misura il passato, NON stima il futuro. Flag --ephemeral per non salvare.

> Procedura: [cost-and-time-analytics](mdc:.cursor/rules/skills/cost-and-time-analytics.mdc)

> **Gate**: `factory.config.yaml.analytics.measurement.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/analytics <scope> [--audience=operativa|progetto|executive] [--format=md|json|pdf|html] [--ephemeral] [--compression-savings]
```

## Limitazioni Cursor

- I tool deterministici sotto `tools/` sono invocati da terminale e si comportano in modo identico: la differenza sta solo nell'agente che li chiama.
- Nessun hook `Stop`: cio' che su Claude Code compare in automatico a fine risposta va invocato a mano.
