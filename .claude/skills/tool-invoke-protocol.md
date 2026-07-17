# Skill: Tool Invoke Protocol

> Adapter Cursor della skill `tool-invoke-protocol` definita in PATTERN.md.

**Scopo:** Standardizza la risoluzione del path di invocazione di uno strumento della factory indipendentemente dall'adapter.

## Regole

**R.TI.1** — Tutti i tool della factory vivono in `tools/` alla root del repo. I path `.claude/tools/` sono shim backward-compat.

**R.TI.2** — Il path root è risolto tramite:
- (a) `$CLAUDE_PROJECT_DIR` per Claude Code
- (b) Path relativo `./tools/` da CWD per lancio manuale
- (c) Adapter-specific binding per Cursor/Aider (vedi binding table)

**R.TI.3** — I path `.claude/tools/` sono shim backward-compat e **non devono essere usati in nuovo codice**. Usa sempre `tools/<subfolder>/` nei nuovi skill/agent.

## Binding table

| Adapter | Risoluzione root |
|---|---|
| Claude Code | `$CLAUDE_PROJECT_DIR` |
| Cursor | `${workspaceFolder}` (VS Code env) |
| Aider | CWD al lancio (assumono root repo) |
| Lancio manuale | CWD = root repo |

## Esempio invocazione da skill/agent

```bash
# Claude Code
bash "$CLAUDE_PROJECT_DIR/tools/a11y/a11y-scan.sh" --target <url>

# Lancio manuale (dalla root del repo)
bash tools/a11y/a11y-scan.sh --target <url>

# Python tool
python3 "$CLAUDE_PROJECT_DIR/tools/analytics/show-session-tokens.py" --full
```
