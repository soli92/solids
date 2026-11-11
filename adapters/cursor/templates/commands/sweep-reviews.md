# Comando: /sweep-reviews

> Equivalente Cursor del comando Claude Code `/sweep-reviews` (`.claude/commands/sweep-reviews.md`).
> Pass di qualità SEMANTICA su wiki/ — risolve (con gate) claim non supportati, wikilink dangling e deriva terminologica. Loop bounded, gated, opt-in. EP-056.

> Procedura: [sweep-reviews-protocol](mdc:.cursor/rules/skills/sweep-reviews-protocol.mdc)

> **Gate**: `factory.config.yaml.wiki_sweep.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

## Limitazioni Cursor

- Nessun fan-out nativo di sub-agenti (`profile: sequential`): dove la fonte dispatcha in parallelo, esegui in sequenza e aggrega a mano.
