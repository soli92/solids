---
description: Estrae KB JSON da un file Figma e la scrive in raw/ (sub-agent Sync v2.9, PATTERN §16).
---

Argomento richiesto: `<figma-url>` oppure `<file_key>` (alfanumerico). Esempi:

```
/figma-sync https://www.figma.com/design/ABC123/customer-portal
/figma-sync ABC123
```

Invoca l'agente [figma-sync](mdc:.cursor/rules/figma-sync.mdc). L'agente:

1. Verifica `ANTHROPIC_API_KEY` in env (ABORT se assente).
2. Mostra in chat il piano di estrazione (file_key, manifest key, output path)
   e attende conferma.
3. Esegue **Discovery** (singola chiamata Anthropic + Figma MCP) per mappare i
   frame e i token globali. Mostra riepilogo e attende conferma per Fase 3.
4. Esegue **Chunked Extraction** parallela (max 3 chunk concorrenti, retry
   esponenziale su 429/5xx) — vedi [[chunked-extraction-pipeline]] e
   [[worker-pool-concurrency-limiter]].
5. Propone la KB finale e attende conferma esplicita prima di scrivere.
6. Scrive `raw/<data>-figma-<file_key>.kb.json` + companion stub per ogni frame
   significativo in `raw/images/` + entry in `raw/.extraction-manifest.json`.
7. Suggerisce di invocare [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) per l'ingest L1→L2 (mai automatico).

Prerequisito: l'utente deve aver configurato l'accesso Figma MCP (auth lato
server `https://mcp.figma.com/mcp`) prima di invocare il comando.

Vedi la skill [figma-extraction-protocol](mdc:.cursor/skills/figma-extraction-protocol/SKILL.md) per la procedura completa, PATTERN §16 per il
contratto «sync adapters».
