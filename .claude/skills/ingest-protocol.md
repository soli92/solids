# Skill: Ingest Protocol

> Adapter Cursor della skill `ingest-protocol` definita in PATTERN.md.

# Protocollo di Ingest

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md), [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md), [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md), [scrivi-wiki-page](mdc:.cursor/skills/scrivi-wiki-page/SKILL.md),
PATTERN §16 (sync adapters multi-sorgente, v2.9).

**Shape dei raw (v2.9)**: il manifest può contenere entries con `source: pdf` (artefatto
`.txt` + figure `.md`) o `source: figma` (artefatto `.kb.json` + companion stub `.md`).
Il wiki-keeper sceglie il ramo di analisi in Fase 1 in base al campo `source` del
manifest (assenza → `pdf` per retrocompatibilità).

**Branch parallelo**: se al termine di Fase 0 il manifest ha **N ≥ 3** nuovi artefatti
da ingerire (qualunque source), l'analisi (Fase 1) si esegue in modalità **parallela**
delegando a worker subordinati ([wiki-keeper-worker](mdc:.cursor/rules/wiki-keeper-worker.mdc)); altrimenti seriale. La fase di
merge (1.bis) è eseguita solo nel ramo parallelo. Scrittura, indice e log restano
serializzati in entrambi i rami.

**Coerenza con scheduler v2.11** (PATTERN §18): l'ingest parallelo è l'istanza canonica
del dominio `ingest` (§18.3). Vincoli inviolabili dello scheduler che si applicano qui:
**R.S1** (single-committer su `wiki/log.md` preservato: una sola entry per ingest, mai
una per worker — vedi Fase 5), **R.S3** (cap di fan-out: rispetta `scheduler.max_parallel`
di `factory.config.yaml` — se `N > max_parallel`, il `wiki-keeper` partiziona i raw in
chunk seriali di `max_parallel` worker ciascuno), **R.S7** (worker fallito = un solo
retry, poi report; gli altri worker proseguono). `parallel_gate_threshold` non si applica
qui perché la conferma esplicita arriva comunque alla Fase 2 (proposta).

## Fase 0 — Bootstrap

- `Glob raw/**/*.{txt,md,kb.json}` + Read `raw/.extraction-manifest.json`
- `Glob wiki/**/*.md` per sapere cosa c'è già
- Read ultimo `memory/episodic/*.md` per continuità con run precedente
- **Read `wiki/gaps.md`** (vedi [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md)): se ci sono gap aperti, mostra
  in chat la lista e proponi di colmarli prima o insieme al nuovo ingest. Attendi
  conferma esplicita su quali gap affrontare.
- Per ogni entry del manifest, determina lo `source` (`pdf` se mancante).
- Conta `N` = nuovi artefatti non ancora rappresentati in `wiki/sources/`
  (chiave manifest non corrispondente a `wiki/sources/<key>.md`).
- **Se N ≥ 3 → Fase 1 (parallela)**, altrimenti Fase 1 (seriale).
- Decidi: ingest nuovo, update, gap-pickup, o no-op?

## Fase 1 — Analisi (seriale, N < 3)

Per ogni entry `<key>` nel manifest, applica il ramo corrispondente al `source`:

### Ramo `source: pdf` (testuale)

- Read `raw/<key>.txt`
- `Glob raw/images/<key>-fig-*.md`
- Mappa sezioni → pagine candidate karpathy-style (source / concept / entity /
  synthesis / runbook / incident).

### Ramo `source: figma` (strutturato, v2.9)

- Read `raw/<key>.kb.json` (artefatto primario).
- `Glob raw/images/<key>-frame-*.md` (companion stub).
- Mappatura **schema-driven** (lo schema KB Figma dicta la classificazione):
  - `project` → una sola pagina `wiki/sources/<key>.md` (entry-point della
    sorgente Figma, raccoglie metadati + indice degli oggetti estratti).
  - Ogni `screens[i]` significativo → `wiki/entities/screen-<slug>.md`
    (`kind: screen`).
  - Ogni `components[i]` → `wiki/entities/component-<slug>.md`
    (`kind: ui-component`).
  - Ogni `flows[i]` → `wiki/concepts/flow-<slug>.md` (descrive l'user flow).
  - Ogni `features[i]` → `wiki/concepts/feature-<slug>.md` (mappabile a future
    user story dal PM tramite `## Storie collegate`).
  - `tokens` → consolidati in `wiki/concepts/design-tokens-<key>.md` (oppure
    appesi a una pagina `design-tokens.md` esistente, se applicabile).
- **Soglia di significatività**: scarta screen/component senza descrizione e con
  meno di 2 cross-reference (riducono rumore). Annota quelli scartati nella
  sezione `## Estratto non promosso a pagina` della source page.
- **Citazione**: ogni claim deriva da `[^src: raw/<key>.kb.json §<dotted-path>]`
  (vedi PATTERN §6, grammatica JSON v2.9). Esempi:
  - `[^src: raw/2026-05-21-figma-ABC123.kb.json §project.name]`
  - `[^src: raw/2026-05-21-figma-ABC123.kb.json §screens[0]]`
  - `[^src: raw/2026-05-21-figma-ABC123.kb.json §components[name=Button]]`

Vai a **Fase 2**.

## Fase 1 (parallela, N ≥ 3) — Analisi delegata

Invoca **in parallelo** `min(N, scheduler.max_parallel)` sub-agent [wiki-keeper-worker](mdc:.cursor/rules/wiki-keeper-worker.mdc)
(adapter Cursor: invocazione dell'agente worker per ciascun raw). Se
`N > scheduler.max_parallel`, processa i raw in **chunk seriali** di `max_parallel`
worker ciascuno (rispetto R.S3 di §18); fra un chunk e il successivo non c'è merge
intermedio — il merge (Fase 1.bis) avviene su tutto l'insieme dei JSON ritornati.
Ogni worker riceve:

- `source`: `pdf` | `figma` | … (dal manifest; default `pdf` se assente)
- `primary_path`: `raw/<key>.txt` (se `pdf`) o `raw/<key>.kb.json` (se `figma`)
- `tech_stack`: contenuto di `raw/tech_stack.md`
- `open_gaps`: stralcio di `wiki/gaps.md` (gap aperti)
- `existing_slugs`: lista dei file `.md` già presenti in `wiki/{sources,concepts,entities,syntheses,runbooks,incidents}/`

Ogni worker DEVE rispondere **un solo blocco JSON** (schema):

```json
{
  "source_txt": "raw/<file>.txt",
  "proposed_pages": [
    { "path": "wiki/<kind>/<slug>.md", "type": "concept|entity|source|synthesis|runbook|incident",
      "status": "draft", "title": "...", "sources": ["raw/<file>.txt"],
      "summary_3lines": "...", "claims": [{"text": "...", "cite": "[^src: ...]"}],
      "wikilinks_out": ["<slug>", ...], "figures_referenced": ["raw/images/<file>-fig-NN.md"] }
  ],
  "gaps_opened":           [{"slug": "...", "reason": "...", "blocking": false}],
  "contradictions_flagged":[{"target_page": "wiki/...", "summary": "..."}]
}
```

Vincoli del worker: legge solo `primary_path` + `tech_stack` + `open_gaps` + slug
esistenti; non scrive file (output = solo il JSON); applica [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) su ogni
`claim` (per `source: figma` usa la grammatica JSON v2.9, vedi PATTERN §6); su slug
esistente ambiguo lascia il proprio e segnala in `wikilinks_out`. Per `source: figma`
il worker segue la mappatura schema-driven definita sopra (Fase 1 seriale, ramo Figma)
e applica la soglia di significatività.

Terminazione: tutti i worker rispondono entro timeout. Worker falliti/vuoti → un solo
retry; al secondo fallimento "raw non ingerito" + report in Fase 2.

## Fase 1.bis — Merge (solo ramo parallelo)

Il [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) principale riceve gli N JSON e produce un piano unificato:

1. **Slug collision**: se due worker propongono lo stesso `path` con `type` compatibile →
   fonde le `proposed_pages` in una sola: `sources[]` = unione, `claims[]` = unione
   deduplicata, `summary_3lines` riscritto. Se `type` incompatibile (uno `concept`,
   uno `entity`) → conserva entrambi rinominando uno con suffisso semantico
   (`-concept` / `-entity`) e segnala in report.
2. **Wikilink cross-worker**: per ogni `wikilinks_out[]` non risolto verso una pagina
   esistente o proposta, verifica se compare in altri JSON; se sì, lega; se no, lo
   lascia come placeholder (regola §6 invariata).
3. **Citazioni alla fonte L1**: ogni `sources[]` (sia `raw/*.txt` che `raw/*.kb.json`) viene promosso a `wiki/sources/<slug>.md` se non esiste già (aggiunto al piano di scrittura come `proposed_page` virtuale). Per `source: figma`, la source page riassume il `project` block del KB JSON e linka gli screen/component/flow/feature promossi a pagine.
4. **Gap conflitti**: se due worker aprono lo stesso gap-slug → consolida in una sola
   entry con `**Sospetta fonte:**` che cita entrambe. Se due worker **chiudono** lo
   stesso gap con fonti diverse → la pagina target cita **entrambe** le fonti; se i
   contenuti contraddicono, applica regola §10 (sezione `## Contradictions` non-distruttiva).
5. **Contradictions flagged**: ogni entry → append `## Contradictions` alla pagina target (mai overwrite).

## Fase 2 — Proposta (STOP)

Mostra in chat:

```
INGEST PROPOSTO (ramo: parallel|seriale, N=<n>)
================
Documenti: <lista>
Pagine da creare: M (lista path)
Pagine da aggiornare: K
Figure referenziate: F
Gap identificati (prima passata): G
Slug collisions risolte: C (lista)
Contradictions flagged: X (lista)
Worker falliti dopo retry: W (lista, se ramo parallel)
Procedo?
```

**Attendi conferma esplicita.**

## Fase 3 — Scrittura

- Per ogni pagina nel piano: usa [scrivi-wiki-page](mdc:.cursor/skills/scrivi-wiki-page/SKILL.md). **Una alla volta**, sul [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) principale.
- Per ogni claim senza fonte robusta: apri un gap secondo [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md).
- Citazioni e wikilink: secondo [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md).
- **Touch many small files**: un ingest sano produce 5–15 piccole pagine, non
  una mega-pagina.

## Fase 4 — Indice

Regenera `wiki/index.md` da `Glob wiki/**/*.md` (escludi `log.md`, `query/`, `lint/`).

## Fase 5 — Log entry (OBBLIGATORIA)

Append **una sola** entry a `wiki/log.md` secondo [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template `ingest`).
Se ramo parallel: l'entry include il campo `parallel_workers: N` e la lista delle slug
collisions risolte. Per ogni gap chiuso, applica il template `gap-closed`. **Mai una
entry per worker.**

## Fase 6 — VCS handoff (OBBLIGATORIA, ACC-05 TR-20260714-14)

Al termine della Fase 5, verifica lo stato del repository:

```
git status --short wiki/ raw/
```

Se risultano file modified o untracked nelle directory `wiki/` e `raw/`:
1. Proponi in chat il commit con il messaggio pre-compilato:
   ```
   docs(ingest): <key> — <N> pagine wiki aggiornate/create
   ```
2. Attendi conferma esplicita o esegui il commit se il contesto è autonomo
   (flag `auto_commit: true` o sessione scheduler).
3. Se il commit ha successo, segnala in chat: `VCS: commit effettuato — wiki/ e raw/ puliti.`

**Motivazione**: ogni ingest deve chiudersi con un repository in stato committato.
Modifiche non committate a `wiki/` e `raw/` rischiano di essere sovrascritte o di
creare conflitti in sessioni successive. (ACC-05 TR-20260714-14)

## Regola di concorrenza

Se durante l'ingest trovi una pagina con `## Storie collegate` non vuota → non
toccare quella sezione, è del PM.

## Contraddizioni

Se un raw contraddice una wiki page esistente → **non risolvere silenziosamente**.
Aggiungi una sezione `## Contradictions` alla pagina impattata; surface al
chiamante.
