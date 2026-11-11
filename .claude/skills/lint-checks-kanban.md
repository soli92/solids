---
skill: lint-checks-kanban
part_of: lint-checks (modular)
family: kanban
parent: lint-checks
description: "Check lint su EP/US/TSK frontmatter e struttura kanban — check-family kanban"
---

# Lint Checks — Kanban

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 3 (integrità frontmatter EP/US/TSK), Check 4g (coerenza scheduler/depends_on), Check 4b (coerenza Q ↔ kanban), Check 4m (coerenza risk_classification ↔ Risk Registry), Check 4as (coerenza `assignee:` ↔ stato del TSK), Check 4be (date di lavoro), Check 4bh (evidenza di test dei TSK be), Check 4j (repository risolvibile)

Check ordinati per severità: ERROR → WARNING → INFO.

---

## Check 3 — Integrità kanban

**Eseguibile** (anche 4as e 4b): `python3 tools/lint/check-kanban-integrity.py`, dentro
`tools/lint/run-deterministic.py`. Si riportano le righe, non si stimano. Popolazione: ogni
`<ID>.md` del kanban, archivio incluso; ID con prefisso opzionale e cartelle con slug.

Per ogni `management/kanban/EP-*/EP-*.md`:
- Frontmatter ha `id`, `title`, `status`, `priority`, `confidence`? Altrimenti **ERROR**.
- `id` matcha il pattern `EP-XXX` con XXX = nome cartella? Altrimenti **ERROR**.

Per ogni `US-*.md`:
- Frontmatter ha `id`, `title`, `role`, `priority`, `status`, `wiki_page`?
- `wiki_page` punta a file esistente? Altrimenti **ERROR**.

Per ogni `TSK-*.md` (v2.7, aggiornato v2.43):
- Frontmatter ha `id`, `layer`, `consumer`, `priority`, `estimate`, `status`?
  (`sprint` è **facoltativo** — v2.43: rimosso dai campi obbligatori).
- `id` univoco globalmente (cross-cartelle)?
- `layer` ∈ chiavi di `routing:` in `factory.config.yaml` della factory analizzata;
  se `routing:` manca → fallback `{be, fe, db, qa, infra, docs}` → altrimenti **ERROR invalid-layer**.
  _Motivazione_: `docs` è layer legittimo dalla v2.19 (agente `docs-dev`); una lista hard-coded
  nella norma divergerebbe al primo adapter o factory nuova. Il config è la SSOT.
- `consumer` ∈ `{agent, human}` → altrimenti **ERROR invalid-consumer**.
- Campo legacy `team:` ancora presente → **WARNING deprecated-field** (v2.7,
  migrazione manuale a `layer:`).
- Se `status` in `{in_progress, review}` e `sprint:` assente → **WARNING in-progress-senza-sprint**.

**Campi obbligatori e artefatti chiusi** (v2.43): la popolazione include archivio.
Su artefatti con `status` ∈ `{done, completed, superseded, cancelled, renamed, wontfix}`:
- Solo `id` e `status` (campi d'identità, PATTERN §8) mancanti → **ERROR**.
- Tutti gli altri campi mancanti → **una riga INFO aggregata** per `(tipo, campo)` con
  conteggio e 3 esempi (es. `TSK: 457 artefatti chiusi senza priority (esempi: ...)`).
  _Motivazione_: un check che segnala centinaia di difetti storici non correggibili viene
  ignorato e nasconde quelli nuovi. La storia non si riscrive per soddisfare il lint.
  I campi d'identità restano ERROR perché servono alla derivazione dello stato a runtime.

**Frontmatter non valido come YAML** (`yaml-invalid`, EP-072), su tutti gli artefatti: **ERROR**
se aperto, **WARNING** se chiuso. Il resto del check legge il frontmatter a righe e tollera uno
YAML rotto; chi lo legge con un parser vero (report PM, `tests/test_frontmatter_leggibile.py`)
scarta il file, che diventa invisibile. Controllo a righe, senza PyYAML: riga senza chiave,
valore non quotato che contiene `: ` (anche nelle voci di lista; i commenti in linea `#` sono
esclusi), blockquote `>` dentro il frontmatter — le forme trovate su una derivata (10 file).
Correzione: quotare il valore o usare `>-`, senza cambiarne il testo.

### 4g — Coerenza scheduler/depends_on (v2.11, PATTERN §18)

Solo se almeno un EP/US/TSK in `management/kanban/**` ha frontmatter `depends_on:` valorizzato:

- Per ogni artefatto con `depends_on: [...]`:
  - Ogni `<id>` nella lista deve avere lo stesso prefisso dell'artefatto host (EP→EP, US→US, TSK→TSK). Cross-tipo (es. TSK in `depends_on` di US) → **ERROR `invalid-depends-on-type`**.
  - Ogni `<id>` deve essere file esistente in `management/kanban/**/<id>.md`. Assente → **WARNING `orphan-depends-on`** (referenza a artefatto eliminato o rinominato).
  - Auto-riferimento (`depends_on` contiene il proprio `id`) → **ERROR `self-depends-on`**.
- **Cycle detection**: costruisci DAG `E_dep` sull'insieme {EP, US, TSK} e applica toposort (algoritmo di Kahn). Se rimangono nodi con `in_degree > 0` a fine algoritmo → ciclo presente → **ERROR `depends-on-cycle`** con lista dei nodi nel ciclo. Non `heal-eligible` (richiede giudizio semantico).
- **Drift body ↔ frontmatter** (solo TSK): se il body contiene `## Dependencies\n- TSK-XXX` ma `TSK-XXX` non è in `depends_on:` frontmatter (o viceversa) → **WARNING `dependencies-drift`** (frontmatter prevale per lo scheduler; rinconciliare a mano).
- **`code_path` validation** (solo TSK con `code_path:` valorizzato):
  - Ogni glob deve essere stringa non vuota. Glob vuoto → **WARNING `empty-code-path-glob`**.
  - Se `factory.config.yaml.scheduler.code_path_conflict: strict` e ≥ 2 TSK al "level 0" (depends_on vuoto o tutti soddisfatti) condividono lo stesso glob esatto → **INFO `code-path-overlap`** (non error; informativo per chi pianifica lo sprint, segnala che i due TSK saranno serializzati dal partition step).
- **`blocked_by` su TSK** (v2.11, esteso da US):
  - Ogni `Q_NNN` referenziato deve esistere in `management/questions.md`. Assente → **WARNING `orphan-blocked-by-q`**.
  - Q in `[RISOLTE]` ancora in `blocked_by` di un TSK → **WARNING `stale-blocked-by-tsk`** (simmetrico al check 4b su US; genera `reconcile-needed`).
- **`scheduler:` block coerenza** (solo se `factory.config.yaml.scheduler` esiste):
  - `enabled` ∈ `{true, false}`. Altrimenti → **ERROR `invalid-scheduler-enabled`**.
  - `max_parallel` intero ≥ 1. Altrimenti → **WARNING `invalid-max-parallel`** (applica default 4).
  - `parallel_gate_threshold` intero ≥ 1 e ≤ `max_parallel`. Altrimenti → **WARNING `invalid-gate-threshold`** (applica default 3).
  - `code_path_conflict` ∈ `{strict, warn, off}`. Altrimenti → **ERROR `invalid-conflict-mode`**.
  - `empty_code_path_policy` ∈ `{serial, parallel}`. Altrimenti → **ERROR `invalid-empty-policy`**.

### 4b — Coerenza Q ↔ kanban (v2.6, gate L4 graduato)

- Per ogni `Q_NNN` in `management/questions.md` `[APERTE]`: verifica presenza
  campo `**Bloccante:** hard | soft`. Assenza → **WARNING missing-blocking-level**
  (non ERROR, per compatibilità retroattiva pre-v2.6; default = `hard`).
- Per ogni `Q_NNN` in `[RISOLTE]`: cerca US con `blocked_by:.*Q_NNN` o
  `pending_clarification:.*Q_NNN`. Match → **WARNING stale-blocked-by**:
  la US referenzia una Q già chiusa. Suggerisce: invocare `product-manager`
  o riconciliare manualmente. (Vedi marker `reconcile-needed` in `wiki/log.md`
  generati da `propagate-resolution`.)
- Per ogni US con `pending_clarification:` non vuota: verifica che almeno
  un ADR la citi nel proprio `pending_clarification:` frontmatter. Mismatch →
  **WARNING orphan-pending-clarification**.

### 4m — Coerenza `risk_classification` ↔ Risk Registry (v2.16 opt-in, PATTERN §3/§5)

**WARNING-only — nessun ERROR meccanico** (R.P3 opt-in totale). Il check non blocca
mai `/lint`. Eventuale promozione a ERROR è candidato v2.17+ post-evidenza.

**Pre-condizioni di silenzio** (no-op se):
- l'artefatto EP/US/TSK **non** ha il blocco `risk_classification:` nel frontmatter → no-op totale;
- `management/risk-registry.md` **non** esiste → 4m.1 e 4m.2 si skippano (il Registry è opt-in); solo 4m.3 (broken ref) può ancora scattare.

Tre sotto-check (per ogni artefatto con `risk_classification:` valorizzato):

- **4m.1 — Drift tier**: se `tier` MATCHES `/^tiger-/` e una sezione del Registry per quel target esiste, ma il tier nel Registry ≠ tier nel frontmatter → **WARNING `drift_tier`**.
- **4m.2 — Missing Registry row**: se `tier` MATCHES `/^tiger-/`, il Registry esiste, ma non c'è alcuna sezione/riga per quel target → **WARNING `missing_registry_row`** (suggerimento: esegui `/premortem <target>`).
- **4m.3 — Broken premortem_ref**: se `premortem_ref` è valorizzato e `(path, anchor)` non è risolvibile (file inesistente o anchor assente) → **WARNING `broken_premortem_ref`**.

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][risk_classification][4m.1] EP-042: drift_tier — frontmatter=tiger-launch-blocking, registry=tiger-fast-follow (suggerimento: riconciliare)
- [WARNING][risk_classification][4m.2] US-017: missing_registry_row — esegui /premortem US-017
- [WARNING][risk_classification][4m.3] TSK-103: broken_premortem_ref — management/risk-registry.md#pm-inesistente
```

**Numerazione**: «4m» è il check del pattern Premortem (v2.16). La lettera segue la
serie OCL/CCL prevista in v2.14 (4k/4l); non collide con alcun check esistente in
questo file (4b–4g). Mai `heal-eligible` (WARNING-only, giudizio semantico).

### 4as — Coerenza `assignee:` ↔ stato del TSK (v2.43-candidate, EP-064 / US-253, FM-NEW-4)

**WARNING-only — nessun ERROR meccanico.** Il campo `assignee:` è **advisory**: un check
ERROR trasformerebbe l'igiene di pianificazione in un blocco. Il check non fa mai fallire
`/lint`. Eventuale promozione a ERROR: non prevista (il campo è opzionale per contratto).

**Pre-condizione di silenzio** (no-op totale se):
- il TSK **non ha** `assignee:` nel frontmatter, oppure il valore è vuoto → **nessun
  output di nessun tipo**. L'assenza del campo non è mai un errore né un WARNING: il campo
  è opzionale e additivo (vedi `.claude/skills/scrivi-task.md` §«Campo `assignee:` —
  opzionale, additivo, advisory»).

**Cosa intercetta.** La forma **osservabile** di **FM-NEW-4 — riallocazione non
tracciata** (scambio informale, frontmatter non aggiornato, divergenza silenziosa fra il
campo e la realtà): un campo di assegnazione valorizzato su un TSK in uno stato in cui
l'assegnazione **non ha significato**.

Due sotto-check (solo per TSK con `assignee:` valorizzato):

- **4as.1 — assegnazione su TSK chiuso**: `status: done` (o qualunque stato di chiusura in
  uso nella factory, es. `cancelled`) e `assignee:` ancora valorizzato → **WARNING
  `stale-assignee-on-closed`**. Un task chiuso non ha un proprietario di lavoro: il campo
  residuo è la traccia tipica di una riallocazione mai riconciliata, e alimenta la falsa
  lettura del board.
- **4as.2 — assegnazione su TSK a consumo agentico**: `consumer: agent` e `assignee:`
  valorizzato con un'identità umana → **WARNING `assignee-on-agent-consumer`**. Il campo
  copre il **lavoro umano pianificato**: sul traffico di claim agentico la sua copertura è
  **0%**, perché il dispatch non legge il campo (e non deve iniziare a farlo — US-253 BR1).
  Un'assegnazione nominativa su un TSK che verrà dispacciato da uno scheduler è quindi
  un'annotazione senza effetto, e in genere il residuo di un cambio di `consumer:`.

**Output format** (sezione `## WARNING (igiene)` del report):

```
- [WARNING][assignee][4as.1] TSK-410: stale-assignee-on-closed — `assignee: anna` su status: done (FM-NEW-4 riallocazione non tracciata: rimuovere il campo alla chiusura o riconciliarlo)
- [WARNING][assignee][4as.2] TSK-411: assignee-on-agent-consumer — `assignee: anna` su consumer: agent (il campo copre il lavoro umano pianificato; copertura 0% sul traffico di claim agentico)
```

**Cosa il check NON rileva — dichiarato, non sottinteso.** La **forma centrale** di
FM-NEW-4 — lo scambio informale fra due attori **entrambi presenti** — non lascia alcuna
traccia: il frontmatter resta sintatticamente coerente e il check **tace**. Il presidio è
quindi **parziale per costruzione**: nessuno strumento della factory può confrontare il
campo con la realtà, perché la realtà non è in un file. Presentare 4as come «FM-NEW-4
presidiata» è l'errore che questa nota impedisce.

**Rumore dichiarato su 4as.2.** Se il team adotta la semantica «`assignee:` = supervisore
umano di una sessione agentica», 4as.2 diventa **rumore sistematico** e va declassato a
INFO con un TSK dedicato. La scelta è dichiarata qui invece di essere lasciata al caso:
oggi la semantica normativa del campo è una sola — **lavoro umano pianificato**
(`scrivi-task` §«Campo `assignee:` — advisory, mai vincolante sul dispatch» punto 4).

**Complementarità con `tpm-reconcile` §3.4.** I due presidi coprono i due fallimenti
silenziosi dichiarati e non si sovrappongono: 4as guarda i TSK **chiusi o agentici**
(FM-NEW-4), `tpm-reconcile` §3.4 (`assegnazione-ferma`) guarda i TSK **aperti e immobili**
(FM-NEW-1). Nessuno dei due copre il proprio failure mode per intero.

**Numerazione**: «4as» è la prima lettera libera della serie al 2026-09-18 (fino a «4ar» —
annotazioni SUNSET scadute, `lint-checks-governance.md` — sono occupate). Mai
`heal-eligible`: rimuovere o riconciliare un'assegnazione è una decisione di pianificazione
(giudizio semantico), non una correzione meccanica.

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/US-253.md §AC4 + §AC6]
[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/TSK-589.md §Deliverable]

## Check 4be — date di lavoro dei TSK (ERROR, EP-079)

`python3 tools/lint/check-date-lavoro.py` (dentro `run-deterministic.py`, logica in
`tools/kanban/date_lavoro_check.py`). Vale per i TSK che sono passati a `in-progress` o `done` in un
commit con data `>= kanban_dates.required_from` di `factory.config.yaml`, piu' i cambi di stato non
ancora committati; lo storico e `management/kanban/archive/` sono esenti, a chiave assente il check
tace. `in-progress` richiede `started_at`; `done` richiede `started_at` e `closed_at`, in formato
AAAA-MM-GG, con `closed_at >= started_at`. Sono le date del lavoro, non della registrazione.
Non controlla chi ha lavorato ne' i commit.

- [ERROR][date-lavoro][4be] TSK-N (done): mancano started_at, closed_at — <percorso>

## Check 4bh — evidenza di test sui TSK `layer: be` chiusi (default off)

`python3 tools/lint/check_evidenza_test_be.py --root .` (dentro `run-deterministic.py`). Un TSK `be`
`done` richiede un TSK `qa` `done` che lo cita in `depends_on`, con `## Esito` completo (comando, codice
di uscita, saltati a zero, report, SHA). Regole `lint.kanban.be_test_evidence`, `_consumers`, `_since`;
a regola spenta il check tace. Dettaglio, codici ed esenzione `be_test_evidence: na`:
`references/lint-checks-kanban/check-4bh.md`.

## Check 4j — repository risolvibile sui TSK aperti degli agenti (default off)

`python3 tools/lint/check_target_tsk.py --root .` (dentro `run-deterministic.py`). Per i TSK aperti con
`consumer: agent` il repository si risolve da `target:`, `code_path:` o dal layer in `code_paths`
(Step 2-bis del dev-protocol). Regole `lint.kanban.tsk_target` e `tsk_target_gitmodules` (risoluzione via
`.gitmodules`, opzionale). Dettaglio e codici: `references/lint-checks-kanban/check-4j.md`.

