---
description: Scan YAGNI Decision Ladder sull'intero code_path (o sottoinsieme). Full-repo counterpart di /ponytail-review. Produce report in code_quality/reports/ letto da /ponytail-gain. Opt-in ponytail.enabled.
argument-hint: "[<path-glob>]"
allowed-tools: Read, Bash, Glob, Write
---

Sintassi:

```
/ponytail-audit                  → scan dell'intero code_path (da factory.config.yaml)
/ponytail-audit src/components/  → scan di un sottoinsieme
/ponytail-audit "**/*.tsx"       → scan via glob
```

## Comportamento

1. **Gate**: se `ponytail.enabled != true` → STOP con istruzioni di attivazione.
2. Invoca la skill `ponytail-audit` (Decision Ladder full-repo, cap 200 file/batch, campionamento
   file >50 righe / <90 giorni, rispetta `ponytail.audit.exclude_patterns`).
3. Output: report `code_quality/reports/ponytail-audit-<YYYY-MM-DD>.md` (sommario per livello +
   dettaglio + Top 5 quick wins) + riepilogo in chat.

## Vincoli

- **Read-only sul codice**: cataloga i candidati, non applica mai le semplificazioni.
- **Invariante R.PY1**: mai valuta/sopprime findings di security/a11y/trust-boundary.
- **No verdict**: è un catalogo advisory, non un gate.

## Cross-link

- Skill: `.claude/skills/ponytail-audit.md`
- Comando affine: `/ponytail-review` (diff), `/ponytail-gain` (impatto aggregato)
- Concetto: `wiki/concepts/decision-ladder.md`
