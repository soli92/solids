# Comando: /share

> Equivalente Cursor del comando Claude Code `/share` (`.claude/commands/share.md`).
> Pubblica un artefatto HTML su soli-frames tramite GitHub repository_dispatch. Invoca content-share-protocol (5 fasi). Gated su content_share.enabled (R.CS2 default off). Supporta --dry-run (Fasi 0-3…

> Procedura: [content-share-protocol](mdc:.cursor/rules/skills/content-share-protocol.mdc)

> **Gate**: `factory.config.yaml.content_share.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/share <html-path> [--slug=<slug>] [--title=<titolo>] [--dry-run]
/share output/prototype-sprint-5.html --slug=sprint-5-prototype --title="Sprint 5 Prototype"
/share output/cost-report.html --dry-run
/share reports/2026-07-17-analytics.html --title="Analytics Report 2026-07-17"
/share <html-path> — completato
/share <html-path> --dry-run — completato
```

## Limitazioni Cursor

- Pubblica verso l'esterno: gate umano obbligatorio.
- `--dry-run` per fermarsi prima della pubblicazione.
