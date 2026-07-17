# Skill: Figma Extraction Protocol

> Adapter Cursor della skill `figma-extraction-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: figma-extraction-protocol
description: Protocollo di estrazione Figma per il figma-sync. 5 fasi (Bootstrap → Discovery → Chunked Extraction → Proposta → Scrittura). Implementa il pattern chunked-extraction-pipeline.
```

Riferimenti: PATTERN §16 (sync adapters), §6 (citazioni JSON), §7 r.1 (L1
read-only), [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md), `wiki-log-entry`. Implementa in headless il pattern
documentato in [[chunked-extraction-pipeline]] (concept derivato da `raw/figma-extraction-agent.jsx`).

## Prerequisiti

- **`ANTHROPIC_API_KEY`** in env (o `.env` non committato). La skill verifica la
  presenza e ABORTISCE se assente.
- **Accesso Figma MCP** (`https://mcp.figma.com/mcp`). Header beta
  `anthropic-beta: mcp-client-2025-04-04`. Richiede che il file Figma sia visibile
  alle credenziali del MCP server (l'utente deve aver configurato l'auth Figma in
  precedenza, fuori dallo scope di questa skill).
- **(Opzionale)** `FIGMA_TOKEN` se si vogliono scaricare anche i thumbnail dei
  frame via Figma REST (`/v1/images/:key`).

## Schema KB (single source of truth)

```json
{
  "project": {
    "name": "string",
    "description": "string",
    "domain": "string",
    "pages_count": "integer",
    "screens_count": "integer"
  },
  "screens": [
    { "id": "string", "name": "string", "type": "dashboard|list|detail|form|modal|auth|settings|other",
      "description": "string", "components": ["string"], "actions": ["string"],
      "data": ["string"], "links_to": ["string"] }
  ],
  "components": [
    { "name": "string", "category": "layout|navigation|form|display|feedback|other",
      "description": "string", "props": ["string"], "screens": ["string"] }
  ],
  "flows": [
    { "name": "string", "description": "string", "trigger": "string",
      "steps": ["string"], "screens": ["string"] }
  ],
  "features": [
    { "name": "string", "description": "string", "priority": "high|medium|low",
      "screens": ["string"], "stories": ["string"] }
  ],
  "tokens": {
    "colors":     [{ "name": "string", "value": "string" }],
    "typography": [{ "name": "string", "value": "string" }],
    "spacing":    [{ "name": "string", "value": "string" }]
  }
}
```

Costanti (allineate al pattern [[chunked-extraction-pipeline]]):

```
MODEL            = "claude-sonnet-4-6"        # o successivo, parametrizzabile
MAX_CONCURRENCY  = 3                          # chunk in parallelo
MAX_RETRIES      = 2                          # tentativi per chunk in errore
RETRY_BASE_DELAY = 1500 ms                    # base exponential backoff
FRAMES_PER_CHUNK = 3                          # frame per gruppo
```

## Fase 0 — Bootstrap

- Verifica `ANTHROPIC_API_KEY` in env. Assente → ABORT con messaggio chiaro.
- Parsing input: estrai `file_key` da URL Figma. Pattern supportati:
  `/file/KEY/`, `/design/KEY/`, `/proto/KEY/`. Se l'utente passa già il `file_key`
  alfanumerico, accettalo direttamente.
- Read `raw/.extraction-manifest.json`. Genera chiave manifest: `<data>-figma-<file_key>`.
  - Se la chiave esiste già con `status: success` → mostra in chat l'entry
    esistente e chiedi: «Re-extract (overwrite con `## Aggiornamenti` semantics
    nella Fase 5)? [y/N]».
  - Se esiste con `status: partial` o `error` → procedi (retry trasparente).
- Read `raw/tech_stack.md` (se esiste) per contesto eventuale (non altera il
  prompt, ma viene incluso come hint nel `DISCOVERY_PROMPT`).

## Fase 1 — Piano di estrazione (STOP iniziale)

Mostra in chat:

```
PIANO ESTRAZIONE FIGMA
======================
File: <url o file_key>
Output primario: raw/YYYY-MM-DD-figma-<file_key>.kb.json
Manifest key:    <data>-figma-<file_key>
Costo stimato:   1 chiamata Discovery + N chiamate chunk (stima da affinare in Fase 2)
Thumbnail:       <on|off in base a FIGMA_TOKEN>
Procedo con Discovery?
```

**Attendi conferma esplicita.** Se l'utente nega → ABORT pulito (nessuno scrittura).

## Fase 2 — Discovery (singola chiamata)

Prompt `DISCOVERY_PROMPT` (testo guida, citazione `[[chunked-extraction-pipeline]]`):

> Tu sei un knowledge extractor su un file Figma. Usa i tool MCP `get_metadata` e
> `get_variable_defs` per mappare la struttura del file. Restituisci JSON con:
> - `project`: name, description, domain, pages_count, screens_count
> - `frames`: lista di `{id, name, page}` (TUTTI i frame del file, anche se molti)
> - `tokens`: colors / typography / spacing globali
> **DO NOT extract details yet — only discover.** Niente componenti, niente flussi.

Chiamata Anthropic API con `mcp_servers` payload registrato verso
`https://mcp.figma.com/mcp` + header `anthropic-beta: mcp-client-2025-04-04`.

Output atteso: blocco JSON valido contro lo schema (sezione `project` + `frames[]` +
`tokens`). Se il modello produce JSON malformato → 1 retry con prompt rinforzato
(«Output deve essere SOLO JSON valido, niente prosa»). Secondo fallimento → ABORT,
manifest entry `status: error`, log a chat.

Mostra in chat:

```
DISCOVERY COMPLETED
===================
Project:  <name> (domain: <domain>)
Pages:    <pages_count>
Frames:   <N> totali
Tokens:   <C> colors, <T> typography, <S> spacing
Chunks da estrarre: ceil(N / FRAMES_PER_CHUNK) = <C>
Procedo con extraction parallela? (worker pool max 3)
```

**Attendi conferma.** Se l'utente vuole filtrare frame (es. «solo le pagine
Mobile»), accetta una lista di id da escludere prima di procedere.

## Fase 3 — Chunked extraction (parallela)

- Chunk = `frames[]` partizionato in gruppi di `FRAMES_PER_CHUNK = 3`.
- Per ogni chunk, lancia un task asincrono. Limite globale `MAX_CONCURRENCY = 3`
  (worker pool). Vedi [[worker-pool-concurrency-limiter]].
- Prompt `CHUNK_PROMPT_TEMPLATE`: enumera esplicitamente gli id dei frame del
  chunk e chiede al modello di chiamare `get_design_context` su ciascuno;
  restituire JSON con `screens[]`, `components[]`, `flows[]`, `features[]`
  popolati **solo dai frame elencati** (mai inventare frame non in lista).
- Retry: ogni chunk usa [[exponential-backoff-retry]] (`MAX_RETRIES = 2`, base
  `RETRY_BASE_DELAY = 1500 ms`). Errori 429/5xx → retry; errori 4xx (≠429) → no
  retry, marca chunk `status: error`.
- Aggiornamento progressivo: dopo ogni chunk concluso, aggiorna in memoria la KB
  con `mergeKB(discovery, chunkResults)`. Non scrivere ancora su disco.

Durante l'esecuzione, log a chat ogni 5 secondi (o per evento):

```
[14:32:01] chunk 1/8 done    (3 screens, 5 components extracted)
[14:32:03] chunk 2/8 done    (2 screens, 1 component extracted)
[14:32:05] chunk 3/8 retry   (HTTP 429, backoff 1500ms)
...
```

Al termine: stampa riepilogo (chunk done / retry / error).

## Fase 4 — Proposta (STOP, PATTERN §7 r.6)

Mostra in chat la sintesi della KB:

```
KB FIGMA PRONTA
===============
project:    <name>
screens:    <N>  (tipi: dashboard×2, form×3, modal×1, ...)
components: <M>  (categorie: layout×3, form×4, ...)
flows:      <F>  (priority high: P, medium: M)
features:   <K>
tokens:     <C> colors, <T> typography, <S> spacing
chunk falliti dopo retry: <X>  (lista se >0)
Procedo a scrivere raw/<data>-figma-<file_key>.kb.json?
```

**Attendi conferma esplicita.**

Se chunk falliti > 0 → mostra quali frame mancano. L'utente decide:
- procedere comunque (manifest `status: partial`, lista frame mancanti in `extraction_metadata`)
- ritentare solo i chunk falliti (nuova Fase 3 limitata)

## Fase 5 — Scrittura

1. **Write** `raw/YYYY-MM-DD-figma-<file_key>.kb.json` con la KB completa.
2. Per ogni screen significativo (criterio: `type ∈ {dashboard, form, list, detail}`
   o se referenziato da ≥ 1 flow), **Write** un companion stub `raw/images/YYYY-MM-DD-figma-<file_key>-frame-NN.md`:

   ```markdown
   ---
   source_figma: <file_key>
   frame_id: <id>
   frame_name: <name>
   frame_index: NN
   type: figma-frame
   thumbnail: <path .png se presente, altrimenti "" >
   ---
   # Frame NN — <name>

   Tipo: <type>. Companion stub generato da figma-sync. Vedi descrizione strutturata
   in `raw/YYYY-MM-DD-figma-<file_key>.kb.json §screens[id=<id>]`.
   ```

3. **(Opzionale, se `FIGMA_TOKEN` env)** scarica i thumbnail PNG via Figma REST
   `/v1/images/<file_key>?ids=<frame_id>&format=png&scale=2` → salva accanto al
   companion stub con stesso slug.
4. **Edit** `raw/.extraction-manifest.json`: appendi (o aggiorna in-place per
   re-extract) la entry:

   ```json
   {
     "<data>-figma-<file_key>": {
       "source": "figma",
       "extracted_at": "<ISO-8601>",
       "primary_artifact": "raw/<data>-figma-<file_key>.kb.json",
       "secondary_artifacts": ["raw/images/<data>-figma-<file_key>-frame-NN.md", "..."],
       "extractor_version": "figma-sync@2.9.0",
       "extraction_metadata": {
         "file_key": "<key>",
         "project_name": "<name>",
         "screens_count": <N>,
         "chunks_total": <C>,
         "chunks_failed": <X>,
         "frames_missing": [<id>, ...],
         "status": "success | partial | error"
       }
     }
   }
   ```

5. **Suggerisci esplicitamente** in chat: «Estrazione completata. Invoca
   [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) per l'ingest L1→L2.» Mai chiamare wiki-keeper automaticamente
   (orchestrazione cross-ruolo è responsabilità dell'utente o dell'orchestrator,
   §7 r.12).

## Regole anti-corner-case

- **Frame senza id**: scartabili. Annota in `extraction_metadata.frames_skipped`.
- **File Figma protetto / 403**: ABORT Fase 1 con istruzione: «Configura
  l'accesso Figma MCP per il file <url> e riprova».
- **Rate limit globale Anthropic**: backoff esponenziale; se 3+ retry consecutivi
  falliscono → ABORT con messaggio chiaro («Riprova fra 5 min»).
- **File enorme (>200 frame)**: avvisa in Fase 2 e chiedi conferma esplicita
  («Estrazione stimata in ~M chunk, ~Y minuti, ~Z chiamate API. Procedo?»).
- **Re-extract**: il file `.kb.json` viene riscritto in toto (no merge
  incrementale a livello di file; il merge progressivo vive solo in memoria
  durante una singola estrazione). La storia delle estrazioni vive nel
  manifest (`extracted_at` aggiornato) e in `wiki/log.md` (entry future del
  wiki-keeper).

## Non in scope per figma-sync

- Scrivere in `wiki/`, `management/`, `design_&_architecture/` (scope di altri ruoli).
- Decidere quali screen/component diventano pagine wiki: questo è giudizio
  dell'*Analyst* (wiki-keeper) in `ingest-protocol` Fase 1.
- Generare wikilink `[[...]]` nel companion stub: il companion è solo metadati
  L1; i wikilink vivono in L2.
- Aprire gap o storie: la skill è puramente L1.
