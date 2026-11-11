# Comando: /visual-oracle

> Equivalente Cursor del comando Claude Code `/visual-oracle` (`.claude/commands/visual-oracle.md`).
> Invoca il visual oracle su un TSK FE (EP-005, ADR-012). Esegue visual-oracle-protocol (render headless + screenshot multi-viewport/tema + critica visiva) e ritorna verdict pass | conditional |…

> Procedura: [visual-oracle-protocol](mdc:.cursor/rules/skills/visual-oracle-protocol.mdc) + [oracle-precheck](mdc:.cursor/rules/skills/oracle-precheck.mdc)

> **Gate**: `factory.config.yaml.fe_correctness.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/visual-oracle <TSK-id>            → visual oracle standard (aggiorna visual_status nel frontmatter TSK)
/visual-oracle <TSK-id> --dry-run  → esegue la skill ma NON aggiorna il frontmatter (solo logging)
```

## Limitazioni Cursor

- Playwright gira da terminale: identico. Cambia solo chi lo lancia.
- Nessuna auto-valutazione: chi produce l'artefatto non lo giudica. La separazione e' strutturale e vale su ogni adapter.
