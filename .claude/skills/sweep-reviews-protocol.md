---
name: sweep-reviews-protocol
description: Loop evaluator-optimizer SEMANTICO per la qualità di wiki/. Rileva e (con gate umano bulk) risolve claim non supportati, wikilink dangling e deriva terminologica. Opt-in, bounded, gated. Skill del wiki-keeper (EP-056 US-203).
---
# Protocollo sweep-reviews (semantico)

Riferimenti: `lint-checks` (segnale detection), `heal-protocol` (analogia strutturale,
natura opposta), `citation-rules`, `wiki-gap-protocol`, `wiki-log-entry`, `wiki/purpose.md`
(EP-055), `PATTERN.md §35` (Wiki Keeper 2.0) + `§7 r.7` (Aggiornamenti semantici) + `§7 r.12`
(single-committer) + `§10` (contradictions non-distruttive).

## Natura e distinzione (Accordo Round 2 TR-llmwiki-20260824)

sweep-reviews è la controparte **semantica** di `heal-protocol`. Stessa struttura (loop
bounded + gate bulk), natura opposta:

| | Dominio | Natura | Inferenza di intento | Applicazione | Gate | Opt-in |
|---|---|---|---|---|---|---|
| `heal-protocol` | `wiki/` | **meccanico** (whitelist deterministica) | **vietata** | in-place puro | bulk | always-on |
| CQRL (`code-review`) | codice | idiomaticità/design/robustezza | — | task_package a dev | severity-tiered | `code_quality.enabled` |
| **sweep-reviews** | `wiki/` | **semantico** (claim/link/terminologia) | **ammessa, ma gated** | `## Aggiornamenti` (§7 r.7) | bulk stretto + confidence | `wiki_sweep.enabled` |

sweep-reviews è l'unico che fa inferenza semantica → gate più stretto di heal (mostra
`confidence` per item) e **opt-in totale** (default off, R.P3).

## Chi può eseguirla

**Solo il `wiki-keeper`** (Accordo Round 2: nessun agente separato), su invocazione via
`/sweep-reviews` o come pass finale opzionale post-ingest. Single-committer preservato.

## Gate di attivazione

`wiki_sweep.enabled: true` in `factory.config.yaml`. Se `false` → STOP esplicito (mai
silenzioso): «sweep-reviews non abilitato. Aggiungi `wiki_sweep.enabled: true` in
factory.config.yaml». A flag spento la factory è identica a prima (backward-compat totale).

## Categorie di review item (whitelist semantica)

L'optimizer propone risoluzioni SOLO per queste tre categorie. Ogni altra osservazione
semantica è lasciata all'umano.

| Categoria | Detection | Risoluzione proposta |
|---|---|---|
| `unsupported-claim` | claim > 20 parole senza `[^src:]` (riusa segnale Check 2 `unsourced-claim`) | individua fonte in `raw/` che supporta il claim → aggiungi `[^src:]`; se assente → converti in gap (`wiki-gap-protocol`) |
| `dangling-concept` | `[[X]]` verso pagina inesistente **e** non presente in `wiki/gaps.md` (previa **normalizzazione**, vedi sotto) | crea stub minimo `wiki/<kind>/X.md` (se il concetto è supportato da ≥1 fonte) **oppure** apri gap |
| `terminology-drift` | termini incoerenti per lo stesso concetto, giudicati contro `wiki/purpose.md` (`priority_entity_types` + `domain`) | normalizza al termine canonico dedotto da `purpose.md`; se `purpose.md` assente → item **skippato** (nessuna base di giudizio) |

### Normalizzazione wikilink per `dangling-concept` (detection hardening, battle-test v2.38.0)

Il battle-test v2.38.0 (detection su 3 factory: meta 231p, soli-boy 58p, wise-planeswalker
437p) ha rivelato che una detection ingenua produce falsi positivi massivi (202 su
wise-planeswalker). Prima di classificare un `[[X]]` come dangling, applica **in ordine**:

1. **Escludi code**: ignora i wikilink dentro fenced code block (```` ``` ````) e inline code (`` ` ``).
2. **Strip anchor/alias + pipe escaped**: prendi solo il segmento prima di `|` **o `\|`** e `#`,
   poi rimuovi eventuali `\` finali. In tabella markdown il pipe è escaped (`[[innistrad\|Innistrad]]`):
   senza questa regola il target diventa `innistrad\` (falso positivo). Battle-test v2.38.0:
   su wise-planeswalker questo solo fix ha ridotto i dangling da 25 a 5 (20 falsi positivi da `\|`).
3. **Strip `.md`** e **risolvi path relativi** al basename (`../../concepts/commander.md` → `commander`).
4. **Escludi placeholder/generici**: `<...>`, `X`/`Y`/`Z`, `foo`/`bar`, `pagina`/`slug`/`name`/
   `link`/`wikilink`/`wiki-page`/`skill-name`/`...`, stringhe ≤ 2 char, stringhe con `<>*$"`.
5. **Risoluzione cross-namespace**: `ADR-*` → `design_&_architecture/decisions/`; `EP-*`/`US-*`/
   `TSK-*` → `management/kanban/`; nomi di agente/skill (`wiki-keeper`, `repo-sync`, …) →
   `.claude/agents/` o `.claude/skills/`. Se risolvono lì, **non sono dangling wiki** — sono
   cross-reference legittime (semmai un WARNING soft "wikilink cross-namespace", non un item).
6. **Risolvi anche verso i side-channel esistenti**: le pagine in `wiki/lint/`, `wiki/query/`,
   `wiki/decisions/` NON si scansionano come *sorgenti* di wikilink, ma **esistono su disco e sono
   linkabili validamente**. Includile nel set di *risoluzione*: un `[[report-lint-2026-06-25]]`
   verso un report reale in `wiki/lint/` NON è dangling. (Battle-test v2.38.0 su soli-projects:
   7 su 10 "dangling" erano falsi positivi = ref a report `wiki/lint/` esistenti esclusi dal set
   di risoluzione.)
7. Solo ciò che resta non risolto contro **nessuna** pagina esistente in `wiki/**` è un vero
   `dangling-concept`.

Con questa normalizzazione, sul meta-framework i candidati scendono da 34 (ingenui) a 16
(reali: agent/skill privi di pagina-concetto wiki + ref a `management/`). Sui campioni derivati:
soli-projects 10→3, wise-planeswalker 25→3 (dopo escaped-pipe + side-channel).

**Finding sistematico di flotta (battle-test v2.38.0)**: il runbook `content-share-setup.md`
(scaffolded da EP-048) referenzia `[[content-share-hub-pattern]]` / `[[soli-frames]]` /
`[[soli-frames-integration]]` — pagine vive solo nella wiki del meta-framework, mai ingestate
nelle factory derivate. Risultano dangling in **tutte** le factory con EP-048 scaffoldato.
Candidato fix upstream: il template runbook non dovrebbe emettere wikilink verso pagine
non-portabili (usare link esterni o note), oppure lo scaffolding EP-048 dovrebbe ingestare
gli stub. Tracciato come gap in ogni factory, non fabbricato.

**Esclusi categoricamente** (mai auto-risolti — surface all'umano):
- `## Contradictions` (§10 invariante — mai risoluzione silenziosa)
- `## Storie collegate` (proprietà PM, §2)
- riscritture di intere pagine (fuori scope: è ingest, non sweep)
- gap già aperti (li gestisce l'ingest, non lo sweep)

## Input

- Scope: `wiki/**` (escluso `log.md`, `query/`, `lint/`, `decisions/`).
- `wiki/purpose.md` se presente (EP-055) — riferimento di dominio per `terminology-drift`.
- Config: `wiki_sweep.max_iterations` (default 3), `wiki_sweep.confidence_min` (default 0.7),
  `wiki_sweep.categories`, `wiki_sweep.use_purpose_md`.

## Procedura (loop fino a max_iterations)

### Iter 0 — Detection (Bootstrap)

1. Scansiona `wiki/**` per le categorie abilitate in `wiki_sweep.categories`.
2. Costruisci la coda dei review item: `{id, categoria, target_page, descrizione,
   risoluzione_proposta, confidence}`.
3. Se coda vuota → STOP `no-items`. Inizializza `iter_count = 0`, `prev_item_count = +∞`.

### Per ogni iterazione N ∈ {1..max_iterations}

**A. Produzione proposte (read + analyze, no write)**

1. Per ogni review item: deriva la `risoluzione_proposta` secondo la whitelist semantica.
   Scarta gli item con `confidence < confidence_min` (restano nella coda, non risolti).
2. Per `terminology-drift`: se `use_purpose_md: true` e `purpose.md` assente → skip item.
3. Costruisci un **diff semantico aggregato** (proposta di `## Aggiornamenti` per pagina
   impattata, oppure stub/gap da creare). Niente scrittura su disco.
4. Se il diff è vuoto (nessuna risoluzione ≥ confidence_min) → STOP `empty-diff`.

**B. Gate umano bulk (STOP — più stretto di heal)**

Mostra in chat:

```
SWEEP-REVIEWS — Iter <N> / <max>
================================
unsupported-claim: K1 | dangling-concept: K2 | terminology-drift: K3
Confidence media: <c> (min applicata: <confidence_min>)
Pagine impattate: <M>

Proposte (per item, con confidence):
[<conf>] <categoria> <target_page>: <descrizione> → <risoluzione>
...

Diff semantico aggregato:
<preview delle sezioni ## Aggiornamenti / stub / gap>

Confermi l'applicazione? [yes/no]
```

**Attendi risposta esplicita.** `no` → STOP `user-rejected`. `yes` → procedi.
Gate **bulk** (un solo yes/no). Per escludere item singoli: rispondi `no`, restringi
`categories`/alza `confidence_min`, ri-esegui.

**C. Applicazione (semantica, NON in-place)**

- Claim/terminologia su pagine `review`/`approved` → sezione `## Aggiornamenti (vYYYY-MM-DD)`
  (§7 r.7 — la modifica È semantica, a differenza di heal che è meccanico in-place).
- `dangling-concept` → crea stub `status: draft` con `scrivi-wiki-page`, oppure gap.
- `unsupported-claim` senza fonte → gap via `wiki-gap-protocol`.
- Mai toccare `## Contradictions` / `## Storie collegate`.

**D. Re-evaluator**

Ri-scansiona le pagine impattate per le stesse categorie. Attendi la nuova coda.

**E. Terminazione** (identica a heal §E, su `item_count` invece di `error_count`)

| Condizione | Azione |
|---|---|
| `new_item_count == 0` | STOP **closed**. |
| `new_item_count >= prev_item_count` | STOP **stuck** (no-progress). |
| Nuovi item non presenti in N-1 | STOP **regression**. No rollback; segnala. |
| `N == max_iterations` | STOP **max-iterations**. |
| Altrimenti | `iter_count += 1`, `prev_item_count = new_item_count`, vai ad A. |

## Log entry (template `sweep`)

Append a `wiki/log.md` **una sola entry per ciclo** (vedi `wiki-log-entry` template `sweep`):

```
## [YYYY-MM-DD] sweep | esito=<closed|stuck|regression|max-iterations|user-rejected|no-items|empty-diff>
Categorie: unsupported-claim=<N>, dangling-concept=<N>, terminology-drift=<N>
Iter <k>: applied=<A>, residual=<R> | Files touched: <M>
```

## Foundation read-only (stability window — Accordo Round 2)

sweep-reviews usa EP-042 (wiki-search) ed EP-054 (code intelligence) come foundation
**read-only**: può consultarli per detection ma NON li modifica. Non introduce nuovi layer
su di essi (retrieval 4-fase e KG 4-segnali restano backlog EP-042.1 / spike).

## Anti-pattern (vietati)

| Anti-pattern | Perché vietato | Correzione |
|---|---|---|
| Auto-apply senza gate | Inferenza semantica non supervisionata | STOP obbligatorio prima di ogni iter |
| Risolvere `## Contradictions` | §10 invariante non-distruttivo | Surface all'umano, mai silenzioso |
| In-place edit senza `## Aggiornamenti` | Perde tracciabilità della modifica semantica (§7 r.7) | Sempre sezione datata su review/approved |
| `terminology-drift` senza `purpose.md` | Nessuna base di giudizio del termine canonico | Skip item |
| Loop > max_iterations | Bounded per costruzione | Termina con `max-iterations` |
| Toccare `## Storie collegate` | Proprietà PM (§2) | Mai |
| Nuovo agente per sweep | Accordo Round 2 (capability del keeper) | Skill del wiki-keeper |

## Cross-link

- `heal-protocol.md` — controparte meccanica (natura opposta)
- `lint-checks.md` — Check 2 (unsourced-claim), Check 1 (broken-wikilink) come segnali di detection
- `wiki/purpose.md` — riferimento di dominio (EP-055) per terminology-drift
- `wiki-gap-protocol.md` — destinazione di claim/concept non risolvibili
- `PATTERN.md §35` — Wiki Keeper 2.0
