---
description: Analizza un diff con la YAGNI Decision Ladder (Pass 4 advisory, EP-057). Wrapper standalone di code-review-protocol §Passata 5. Non produce verdict. Opt-in ponytail.enabled.
argument-hint: <TSK-id | branch | file | --staged> [--save]
allowed-tools: Read, Bash, Glob, Write
---

Sintassi:

```
/ponytail-review TSK-<id>        → Decision Ladder sul diff del TSK (code_path da kanban)
/ponytail-review <branch>        → diff vs default-branch
/ponytail-review <file-path>     → diff del singolo file
/ponytail-review --staged        → diff staged corrente
/ponytail-review <target> --save → salva report in code_quality/reports/ (alimenta /ponytail-gain)
```

## Comportamento

1. **Gate**: se `ponytail.enabled != true` in `factory.config.yaml` → STOP con istruzioni di
   attivazione. Esecuzione esplicita = volontà esplicita (non richiede `passes.yagni_ladder`).
2. Invoca la skill `ponytail-review` (che esegue `code-review-protocol` §Passata 5 sul diff).
3. Output: tabella `File | Costrutto | Livello Decision Ladder suggerito | Note` in chat.
   Con `--save`, scrive anche il report su disco.

## Vincoli

- **Non produce verdict**: è advisory puro. Diversamente da `/review` (che esegue Passate 1-3 +
  eventuale Passata 5 e calcola pass/conditional/reject), `/ponytail-review` esegue **solo** la
  Passata 5.
- **Invariante R.PY1**: mai valuta/sopprime findings di security/a11y/trust-boundary.
- **Read-only sul codice**: non applica mai le semplificazioni suggerite (le propone soltanto).

## Cross-link

- Skill: `.claude/skills/ponytail-review.md`
- Procedura canonica: `.claude/skills/code-review-protocol.md §Passata 5`
- Comando affine: `/ponytail-audit` (scan full-repo), `/review` (CQRL completo)
- Concetto: `wiki/concepts/decision-ladder.md`
