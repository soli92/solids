---
description: Health check di wiki/ e management/kanban/. Solo report, mai auto-fix.
---

Invoca l'agente [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) via `Agent`.

Argomenti opzionali:
- nessun argomento → lint completo (i 4 check di [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md))
- nome namespace (es. `concepts`, `kanban`) → lint scoped
- `citation-audit` → audit completo delle citazioni (verifica che ogni `[^src: ...]` punti a file e sezione esistenti)

Output: `wiki/lint/YYYY-MM-DD-lint-report.md` (o `-citation-audit.md` per la variante). L'agente NON modifica mai gli artefatti — solo report con severità ERROR/WARNING e fix suggeriti. Append a `wiki/log.md` con una riga di riepilogo.
