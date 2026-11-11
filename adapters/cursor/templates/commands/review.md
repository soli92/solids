# Comando: /review

> Equivalente Cursor del comando Claude Code `/review` (`.claude/commands/review.md`).
> Procedura: vedi [code-review-protocol](mdc:.cursor/rules/skills/code-review-protocol.mdc) + [feedback-router](mdc:.cursor/rules/skills/feedback-router.mdc).

**Sintassi**:
```
/review <TSK-id>                  → review standard
/review <TSK-id> --strategy=<...> → override una-tantum router.strategy
/review <TSK-id> --force          → forza review anche se review_status non è pending/conditional
/review show <TSK-id>             → mostra ultimo report senza re-revieware
/review summary                   → riepilogo pass_rate, false_positive, escalation rate
```

> **Gate**: `factory.config.yaml.code_quality.enabled: true`. Se `false` → ABORT e suggerisci di abilitare.

## Comportamento

### `/review <TSK-id>`

1. Legge `factory.config.yaml.code_quality`.
2. Trova TSK via glob. Se `status ≠ done` → ABORT. Se `review_status ∈ {passed, rejected}` → chiede `--force`.
3. Esegue [code-review-protocol](mdc:.cursor/rules/skills/code-review-protocol.mdc) 5 fasi (3 pass paralleli: idiomaticity/design/robustness + aggregatore + verdict).
4. Aggiorna frontmatter TSK: `review_status:` / `review_iter:` / `review_report:`.
5. Applica [feedback-router](mdc:.cursor/rules/skills/feedback-router.mdc): verdict `pass` → chiusura; `conditional` → dispatch dev-agent (loop max 3); `reject` → gate umano.

### `/review show <TSK-id>`

Read-only: legge `code_quality/reports/<TSK-id>-iter-*.md` (ultimo). Nessuna scrittura.

### `/review summary`

Aggregato analytics: pass_rate, false_positive, top 5 rule_id violati, escalation rate. Read-only.

## Vincoli (PATTERN §7 r.16 + §19.6)

- Mai auto-revert codice (verdict reject = gate umano).
- Mai modificare il corpo del TSK (solo frontmatter).
- Mai bypassare `max_iterations` (default 3).
- Mai applicare regole `emergent` con `status: candidate`.

## Limitazioni Cursor

- I 3 pass (idiomaticity/design/robustness) vanno eseguiti sequenzialmente in Cursor.
- L'aggregatore è inline nella stessa sessione Chat.
- Aggiornare `review_status:` manualmente nel frontmatter TSK dopo il verdict.
