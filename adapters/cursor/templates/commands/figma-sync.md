# Comando: /figma-sync

> Equivalente Cursor del comando Claude Code `/figma-sync` (`.claude/commands/figma-sync.md`).
> Procedura: vedi [figma-extraction-protocol](mdc:.cursor/rules/skills/figma-extraction-protocol.mdc).

**Sintassi**: `/figma-sync <figma-url|file_key>`

**Esempi**:
```
/figma-sync https://www.figma.com/design/ABC123/customer-portal
/figma-sync ABC123
```

## Comportamento

Estrae KB JSON da un file Figma e la scrive in `raw/`. Procedura:

1. Verifica `ANTHROPIC_API_KEY` in env (ABORT se assente).
2. Mostra piano di estrazione (file_key, manifest key, output path) e attende conferma.
3. Discovery (singola chiamata Figma MCP) — mappa frame + token globali. Mostra riepilogo, attende conferma per Fase 3.
4. Chunked Extraction — max 3 chunk concorrenti, retry esponenziale su 429/5xx.
5. Propone KB finale e attende conferma esplicita prima di scrivere.
6. Scrive `raw/<data>-figma-<file_key>.kb.json` + companion stub per frame in `raw/images/` + entry in `raw/.extraction-manifest.json`.
7. Suggerisce di invocare `wiki-keeper` per ingest L1→L2 (mai automatico).

## Prerequisiti

- Accesso Figma MCP configurato (auth lato server `https://mcp.figma.com/mcp`).
- `ANTHROPIC_API_KEY` in env.

## Limitazioni Cursor

- In Cursor il Figma MCP deve essere configurato come tool MCP esterno.
- Le fasi di estrazione vanno eseguite sequenzialmente (no parallel chunk concorrenti).
- Se il MCP Figma non è disponibile → l'estrazione non è fattibile in Cursor senza setup aggiuntivo.
