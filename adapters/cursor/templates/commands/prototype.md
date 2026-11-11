# Comando: /prototype

> Equivalente Cursor del comando Claude Code `/prototype` (`.claude/commands/prototype.md`).
> Procedura: vedi [prototype-generation-protocol](mdc:.cursor/rules/skills/prototype-generation-protocol.mdc) + [backend-resolver](mdc:.cursor/rules/skills/backend-resolver.mdc).

**Sintassi**:
```
/prototype <US-id|TSK-id|"intent"> [--backend=html|react|figma|penpot] [--fidelity=static|interactive|animated] [--dry-run]
```

> **Gate**: `factory.config.yaml.prototyping.enabled: true`. Se `false` → STOP esplicito con istruzioni.

## Procedura

1. **Gate**: verifica `prototyping.enabled`. STOP esplicito se `false`.
2. **Parse**: estrae `raw_input` (US-id / TSK-id / stringa libera), `override_backend`, `override_fidelity`, `dry_run`.
3. **Validazione input**: US-id → glob `management/kanban/**/US-<NNN>.md`; TSK-id → glob `management/kanban/**/TSK-<NNN>.md`; stringa libera → nessuna ricerca.
4. **Override one-shot**: `--backend` e `--fidelity` non modificano `factory.config.yaml`.
5. **Dry-run**: se `--dry-run` → invoca [backend-resolver](mdc:.cursor/rules/skills/backend-resolver.mdc) only, mostra risoluzione senza generare artefatti. STOP.
6. **Generazione**: esegue [prototype-generation-protocol](mdc:.cursor/rules/skills/prototype-generation-protocol.mdc) 5 fasi (Backend Resolve → Intent & Source → Generate → Self-contain check → Handoff).

## Suggerimenti post-generazione

| Backend | Suggerimenti downstream |
|---|---|
| `html` | `/visual-oracle`, `/functional-oracle`, `/ux-ui-review`, `/a11y` |
| `react` | `/visual-oracle`, `/functional-oracle`, `/review` (CQRL), `/a11y` |
| `figma` | `/ux-ui-review`, round-trip `/figma-sync` |
| `penpot` | `/ux-ui-review` |

## Vincoli

- Gate `prototyping.enabled` (INV-5, R.P3): mai STOP silenzioso.
- Read-only verso spec sorgente (INV-3).
- No auto-eval (INV-4).

## Limitazioni Cursor

- Le 5 fasi di [prototype-generation-protocol](mdc:.cursor/rules/skills/prototype-generation-protocol.mdc) vanno eseguite sequenzialmente.
- Per backend `html`: sempre disponibile (INV-1). Per `figma`/`penpot`: richiede MCP configurato.
