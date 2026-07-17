---
description: Promuove una pagina wiki (draft → review → approved). Invoca orchestrator.
---

Argomenti: `<path-pagina> [<new-status>]`.

Esempi:
- `/promote wiki/concepts/event-sourcing.md` → next state dal corrente
- `/promote wiki/concepts/event-sourcing.md approved` → target esplicito

Invoca l'agente [orchestrator](mdc:.cursor/rules/orchestrator.mdc) via `Agent` (è l'unico autorizzato a editare `status:` frontmatter di pagine wiki — vedi PATTERN.md §10 + orchestrator agent prompt).

L'orchestrator:
1. Legge la pagina target.
2. Calcola transizione legale: `draft → review → approved`, mai salti.
3. Edita **solo** `status:` e `updated:` nel frontmatter YAML. Mai il corpo.
4. Append a `wiki/log.md` la riga di promotion.

Se la transizione è illegale → orchestrator rifiuta e suggerisce il passo intermedio. Niente auto-fix.
