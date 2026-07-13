# Skill: Wiki Keeper Worker Protocol

> Adapter Cursor della skill `wiki-keeper-worker-protocol` definita in PATTERN.md.

**Versione:** v2.27 | **Invocata da:** [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) (sub-agent parallelo)
**Scope:** read-only — questa skill non scrive su disco (invariante del worker)

Protocollo operativo del `wiki-keeper-worker`. Descrive input, output, vincoli e
gestione degli errori per l'analisi di un singolo raw file nell'ambito dell'ingest
parallelo ([ingest-protocol](mdc:.cursor/skills/ingest-protocol/SKILL.md) Fase 1, ramo N ≥ 3 file).

Analogia strutturale con le skill di altri sync sub-agent:
- [repo-extraction-protocol](mdc:.cursor/skills/repo-extraction-protocol/SKILL.md) — parser di repo locale
- [figma-extraction-protocol](mdc:.cursor/skills/figma-extraction-protocol/SKILL.md) — parser di file Figma
- [graphify-extraction-protocol](mdc:.cursor/skills/graphify-extraction-protocol/SKILL.md) — parser di knowledge graph

---

## Fase 1 — Ricezione input

L'agente riceve dal `wiki-keeper` i seguenti campi (tutti obbligatori):

| Campo | Tipo | Descrizione |
|---|---|---|
| `txt_path` | string (path) | Path al singolo `raw/<data>-<nome>.*` da analizzare |
| `tech_stack` | string | Contenuto di `raw/tech_stack.md` (context stack tecnico) |
| `open_gaps` | string (markdown) | Lista gap aperti da `wiki/gaps.md` |
| `existing_slugs` | list[string] | Path-slug di pagine già presenti in `wiki/` |

**Precondizione:** il `wiki-keeper` valida che `txt_path` esista prima di invocare il worker.
Il worker non re-valida — tratta input invalido secondo Fase 5 (gestione errori).

---

## Fase 2 — Lettura e segmentazione

1. Leggere `txt_path` per intero via `Read`.
2. Identificare le **sezioni tematiche principali** del documento (heading di primo o
   secondo livello se markdown, sezioni tipografiche se testo libero).
3. Per ogni sezione valutare:
   - È già coperta da `existing_slugs`? → proposta di **aggiornamento** (non creazione).
   - Apre un gap già in `open_gaps`? → segnalare la chiusura potenziale.
   - Introduce concetti non in wiki? → proposta di **nuova pagina**.
4. Applicare `tech_stack` come filtro di rilevanza: contenuti ortogonali allo stack
   sono segnalati come `low_relevance: true` nella pagina proposta.

**Vincolo sectioning-bound:** il worker analizza **solo** `txt_path`. Non legge altri
`.txt` del manifest anche se `txt_path` li referenzia.

---

## Fase 3 — Costruzione output JSON

Produrre **un solo blocco JSON** conforme allo schema `ingest-protocol` Fase 1:

```json
{
  "source_txt": "<txt_path>",
  "proposed_pages": [
    {
      "slug": "<namespace>/<slug>",
      "namespace": "sources|concepts|entities|syntheses|runbooks|guides",
      "title": "<titolo pagina>",
      "status": "draft",
      "cite": ["<txt_path>#<sezione>"],
      "low_relevance": false,
      "action": "create|update",
      "target_path": "wiki/<namespace>/<slug>.md"
    }
  ],
  "gaps_opened": [
    {
      "slug": "<gap-slug>",
      "reason": "<perché non è trattabile con i dati disponibili>",
      "blocking": true|false
    }
  ],
  "contradictions_flagged": [
    {
      "existing_slug": "<wiki/path/esistente>",
      "claim": "<affermazione in txt_path che contraddice>",
      "cite": "<txt_path>#<sezione>"
    }
  ]
}
```

**Nessun testo libero fuori dal JSON.** L'output è consumato machine-readable dal
`wiki-keeper` nell'aggregazione parallela.

---

## Fase 4 — Vincoli di qualità

- **Zero invenzione** (§7 r.2): ogni `proposed_pages[i]` DEVE avere almeno un
  elemento in `cite[]` che punta a `txt_path`. Pagine senza citazione → scartate.
- **Naming slug**: snake_case, unico per namespace, ≤ 60 caratteri. Verificare
  contro `existing_slugs` per evitare collisioni.
- **Frontmatter karpathy-style**: `title`, `status: draft`, `sources: [<cite>]`.
  Vedi [scrivi-wiki-page](mdc:.cursor/skills/scrivi-wiki-page/SKILL.md) per il template completo.
- **Citazioni**: seguire [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) per il formato `[fonte](#sezione)`.
- **Namespace assignment**:
  - `sources/` — un documento per raw elaborato (sempre 1:1 con `txt_path`)
  - `concepts/` — concetti astratti e pattern
  - `entities/` — persone, tool, standard con identità propria
  - `syntheses/` — comparazioni, risposte precompilate, articoli
  - `runbooks/` — playbook operativi step-by-step
  - `guides/` — guide narrative di più ampio respiro

---

## Fase 5 — Gestione errori

| Condizione | Comportamento |
|---|---|
| `txt_path` vuoto o illeggibile | `proposed_pages: []`, `gaps_opened: [{slug:"raw-unreadable-<basename>", reason:"File non leggibile o vuoto", blocking:true}]` |
| Nessuna sezione tematica identificabile | `proposed_pages: []`, `gaps_opened: [{slug:"raw-unstructured-<basename>", reason:"Documento non segmentabile", blocking:false}]` |
| Tutti i concetti già coperti da `existing_slugs` | `proposed_pages: []` con array vuoto — output valido, nessun errore |
| JSON malformato in output | NON accettabile — riformattare prima di terminare |

---

## Cross-link

- [ingest-protocol](mdc:.cursor/skills/ingest-protocol/SKILL.md) — protocollo del `wiki-keeper` che invoca questo worker
- [wiki-keeper-worker](mdc:.cursor/rules/wiki-keeper-worker.mdc) — agente che esegue questa skill
- [scrivi-wiki-page](mdc:.cursor/skills/scrivi-wiki-page/SKILL.md) — template frontmatter per le pagine proposte
- [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) — grammatica citazioni e wikilink
- `wiki-gap-protocol` — procedura per i gap segnalati
