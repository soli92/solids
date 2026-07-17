---
description: Meta-comando release validation gate (EP-012, v2.19+). Wrapper ergonomico della skill release-validation-gate. Verifica che ≥N RUN-REPORT validi esistano prima del tag di release. Default safe --dry-run. Mai auto-tag (R.P1). Meta-comando parallelo a /factory-bootstrap e /factory-upgrade, NON scaffoldato in factory derivate. Opt-in via release_governance.battle_test_gate.enabled.
argument-hint: <version> [--dry-run|--apply] [--bypass-validation-gate --reason="<msg>"]
allowed-tools: Read, Write, Edit, Bash, Glob, TodoWrite
---

# /release — Meta-comando release validation gate (EP-012, v2.19+)

> Parte di EP-012 (Battle-test forcing function). Meta-comando parallelo a `/factory-bootstrap`
> e `/factory-upgrade`. Invoca la skill `release-validation-gate` per verificare che
> ≥N RUN-REPORT validi esistano prima del tag di release. Mai auto-tag (R.P1).
> **Non scaffoldato in factory derivate** (meta-comando, PATTERN §0 + ADR-033 §C).
> Opt-in via `release_governance.battle_test_gate.enabled: true` (default true nel repo framework).

> **Sede e installazione.** Come `/factory-bootstrap` e `/factory-upgrade`, questo è un
> **meta-comando**: opera sul meta-framework dall'esterno e **non** viene scaffoldato nelle
> factory derivate. Source-of-truth versionata qui in `.claude/commands/`; per usarlo come
> slash command installalo user-level:
> ```bash
> cp <your-clone>/.claude/commands/release.md ~/.claude/commands/
> cp <your-clone>/.claude/skills/release-validation-gate.md ~/.claude/skills/
> ```

Argomenti utente: `$ARGUMENTS`

## Sintassi

```
/release <version> [--dry-run | --apply] [--bypass-validation-gate --reason="<msg>"]
```

## Parametri

| Parametro | Tipo | Default | Descrizione |
|---|---|---|---|
| `<version>` | string vX.Y.Z | obbligatorio | Versione target del tag (es. v2.19.0) |
| `--dry-run` | flag | **true (default safe)** | Esegue il gate, produce GATE-REPORT, NON propone azioni |
| `--apply` | flag | false | Esegue il gate; se `pass` propone all'utente i comandi git per il tag (mai esegue tag automaticamente, R.P1); se `fail` STOP |
| `--bypass-validation-gate` | flag | false | Skip del gate (richiede `--reason`). Produce BYPASS.md + marker CHANGELOG |
| `--reason="<msg>"` | string | obbligatorio se bypass | Rationale del bypass (es. "hotfix CVE-2026-1234") |

## Esempi

```bash
# Verifica safe (default dry-run): simula il gate, mostra GATE-REPORT, nessun side effect
/release v2.19.0

# Equivalente esplicito
/release v2.19.0 --dry-run

# Esegue il gate; se pass propone git commands per il tag (mai esegue automaticamente)
/release v2.19.0 --apply

# Bypass tracciato per hotfix (SLA: colmare entro release successiva)
/release v2.19.1 --apply --bypass-validation-gate --reason="hotfix CVE-2026-1234"
```

## Comportamento

1. Carica la skill `release-validation-gate` (`.claude/skills/release-validation-gate.md`).
2. Propaga i parametri alla skill (version, dry-run, apply, bypass, reason).
3. In modalità `--apply` con verdict `pass`: **propone** all'utente una lista di comandi git
   da eseguire manualmente (mai esegue `git tag` direttamente — R.P1).
4. Produce sempre:
   - `validation/release-gates/<version>/GATE-REPORT.md`
   - `validation/release-gates/<version>/<timestamp>-<verdict>.log` (audit)
   - (se bypass) `validation/release-gates/<version>/BYPASS.md`

## Quando invocare

- Prima di ogni `git tag vX.Y.Z` sul repo del meta-framework.
- In modalità `--dry-run` per verificare lo stato corrente senza impegnarsi.
- Con `--apply` solo quando si è pronti al tag effettivo.

## Note architetturali

- **Meta-comando**: non appare in factory derivate (non scaffoldato da `/factory-bootstrap`
  o `/factory-upgrade`). Le factory derivate non rilasciano versioni del meta-framework.
- **Responsabilità Single**: `/factory-upgrade` aggiorna factory esistenti; `/factory-bootstrap`
  crea factory nuove; `/release` valida pre-tag del meta-framework. Triade coerente (ADR-033 §A).
- **Mai auto-tag** (R.P1 + R.P3): la skill produce GATE-REPORT + verdict; il maintainer
  esegue `git tag` a mano dopo aver letto il report.

## Relazione con altri comandi

| Comando | Scopo |
|---|---|
| `/factory-bootstrap` | **Crea** una factory nuova (greenfield scaffolder). |
| `/factory-upgrade` | **Aggiorna** una factory esistente (delta incrementale non distruttivo). |
| `/release` | **Valida** pre-tag una release del meta-framework (battle-test gate). |

Cross-reference: ADR-033 §A (scelta (b) `/release` standalone) §B (contratto comando) §C
(posizione meta-comando). Skill consumata: [`release-validation-gate`](../skills/release-validation-gate.md) (TSK-097).
