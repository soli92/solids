# Comando: /compression

> Equivalente Cursor del comando Claude Code `/compression` (`.claude/commands/compression.md`).
> Procedura: vedi [caveman-protocol](mdc:.cursor/rules/skills/caveman-protocol.mdc).

**Sintassi**:
```
/compression                          → equivalente a `/compression show`
/compression show                     → mostra config corrente + ultime stats
/compression set <key> <value>        → modifica un campo
/compression policy <profile>         → shortcut: cambia policy_profile
/compression dry-run --payload="<t>"  → comprimi payload di test (no side effects)
```

## Comportamento

### `show`

Mostra `factory.config.yaml.compression.output`: Provider, Enabled, Policy profile, canali attivi con livelli, invarianti R.C1 non overridabili, stats ultima sessione. Read-only.

### `set <key> <value>`

Esempi: `/compression set enabled true`, `/compression set policy_profile aggressive`.

Gate:
- `enabled: true` → verifica `caveman --version`. Se assente → mostra install command, attendi conferma.
- `policy_profile: custom` → chiede in chat `channels` block completo.
- `cross_factory: on` → warning R.C4 + doppia conferma.
- Modifica `invariants.*` → **RIFIUTATO** (R.C1 non overridabile).

### `policy <profile>`

Shortcut per `/compression set policy_profile <profile>`. Profili: `conservative` (default), `aggressive`, `custom`.

### `dry-run`

Invoca [caveman-protocol](mdc:.cursor/rules/skills/caveman-protocol.mdc) §Fase 2-3 senza side-effects. Mostra: Channel, Profile, Effective level, Tokens in/out, Ratio, INPUT→OUTPUT esempio.

## Vincoli (PATTERN §20 R.C1–R.C6)

- Mai abilitare compressione su `to_user`, `to_artifact`, `propagate_resolution` (R.C1).
- Mai modifica automatica `policy_profile` a runtime.
- Mai `cross_factory: on` senza doppia conferma (R.C4).

## Limitazioni Cursor

- La compression layer opera a livello di sessione Chat; in Cursor non c'è intercept automatico inline.
- Usare `/compression set enabled true` per documentare la policy, poi applicare manualmente [caveman-protocol](mdc:.cursor/rules/skills/caveman-protocol.mdc) nei canali agent-to-agent.
