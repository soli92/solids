---
name: vcs-handoff
description: Coordina il commit del codice prodotto da un dev-agent con la topologia VCS dichiarata in factory.config.yaml.vcs (PATTERN §15). Gate umano obbligatorio per scritture VCS.
---
# Procedura — VCS handoff a chiusura di un TSK

Invocata dal `dev-protocol` (Fase 5), DOPO `dev-handoff` (entry su `wiki/log.md`).
Branch logico per `vcs.mode` letto da `factory.config.yaml`.

## Fase 0 — Pre-condizioni

1. Leggi `factory.config.yaml`. Estrai `vcs.mode`, `vcs.submodule_path` (se applicabile),
   `vcs.remote_url`, `vcs.branch_strategy` (default `shared`), `vcs.commit_coupling` (default `float`).
2. Verifica che `code_path` sia coerente con `vcs.mode`:
   - `mode: monorepo` → `code_path` deve essere relativo (`./...`) e dentro al repo.
   - `mode: submodule` → `vcs.submodule_path` valorizzato e presente in `.gitmodules`.
   - `mode: sibling` → `code_path` deve essere assoluto o relativo fuori dal repo.
   - `mode: external` → nessuna verifica, qualsiasi path ammesso.
   - `mode: none` → STOP, non c'è L5 da coordinare (errore di config se siamo qui).
3. Se incoerenza → STOP e segnala in chat.

## Fase 1 — Branch (solo `submodule` e `sibling`)

Determina il branch target invocando la skill **`branch-resolver`** (single source of truth
dell'expected branch, EP-034 R.B9). Passa `resolved_vcs`, `resolved_target_name` e il TSK
corrente; ricevi `expected_branch` + `source`. Questo garantisce che il naming usato al commit
sia **identico** a quello mostrato dal preflight (`/vcs-status`) — nessuna logica divergente.

Regola risolta da `branch-resolver` (riepilogo; dettaglio + manifest override in quella skill):
- **`shared`**: `base_branch` se valorizzato, altrimenti il branch corrente. Se HEAD detached → STOP, segnala.
- **`per-tsk`**: nome branch `tsk-<id-lowercase>-<slug-from-tsk-title>` (es. `tsk-042-add-login-endpoint`).
- **`per-sprint`**: nome `sprint-<NN>` (NN da frontmatter TSK `sprint:`).

Applicazione dell'`expected_branch`:
- Se non esiste, propone `git checkout -b <expected_branch>` → **gate umano** → esegui.
- Se esiste e siamo già su quello → OK.
- Se esiste ma siamo altrove → STOP, segnala potenziale conflitto (comando di allineamento
  suggerito: `git checkout <expected_branch>`; l'umano decide, mai auto-checkout — R.B8).

**Consiglio**: se `branch_awareness.dispatch_gate` è attivo, questa condizione è già stata
verificata a monte in `dev-protocol` Fase 0 (Step 2-ter). Qui resta come rete di sicurezza.

### Drift check parent-ref vs submodule-HEAD (opt-in, solo `submodule`)

Se `resolved_vcs.branch_awareness.drift_check: true`, prima dello staging del bump (Fase 2
mode submodule) confronta il commit registrato dal parent (`git -C <factory-root> ls-tree HEAD
<submodule_path>`) con l'HEAD reale del submodule (`git -C <submodule_path> rev-parse HEAD`).
Se divergono in modo inatteso (es. il submodule è indietro rispetto al parent), **segnala** e
chiedi conferma umana prima di procedere col bump. Read-only fino alla conferma (R.B7).

## Fase 2 — Procedura per mode

### Mode: `monorepo`

1. `git status` nel factory repo.
2. Se nessun cambiamento in `code_path` → STOP, segnala "develop senza modifiche" (rare ma possibili).
3. Stagea solo i file sotto `code_path`: `git add <code_path>`.
4. Propone messaggio di commit:
   ```
   feat(<layer>): <TSK title sintetizzato>

   TSK-ZZZ: <link relativo al TSK>
   <eventuale DoD partial note>
   ```
5. **Gate umano** → mostra il diff staged + il messaggio proposto, chiedi OK.
6. Su OK: `git commit -m <messaggio>`. Nessun push automatico.

### Mode: `submodule`

1. `cd <submodule_path> && git status`.
2. Se HEAD detached nel submodule → STOP, segnala (richiede checkout su un branch prima di committare).
3. Stagea + propone commit nel submodule:
   ```
   feat(<layer>): <TSK title sintetizzato>

   TSK-ZZZ (factory: <factory-repo-name>)
   ```
4. **Gate umano** → conferma commit nel submodule.
5. Opzionale: chiedi se vuoi pushare il submodule (`git push origin <branch>`). Solo se utente conferma esplicitamente.
6. `cd <factory-repo-root> && git add <submodule_path>` → stagea il bump del ref nel factory repo.
7. Propone commit nel factory repo:
   ```
   chore(<layer>): bump <submodule_path> for TSK-ZZZ

   Submodule commit: <hash-short>
   ```
8. **Gate umano** → conferma commit factory.
9. Se `commit_coupling: pin` → aggiorna `.factory-lock` (vedi Fase 3).

### Mode: `sibling`

1. `cd <code_path> && git status`.
2. Stessa procedura del submodule **MA**:
   - Niente bump nel factory repo (sono due repo indipendenti).
   - Stampa avviso: "Ricorda di aprire PR su <vcs.remote_url> se vuoi mergeare su main."
3. **Gate umano** per ogni commit.
4. Se `commit_coupling: pin` → aggiorna `.factory-lock`.

### Mode: `external`

1. Tenta `cd <code_path> && git rev-parse HEAD` (test best-effort).
2. Se è un git repo → cattura il commit hash corrente per il log.
3. Se non lo è → solo annota `commit: n/a` nel log.
4. **Nessuna operazione VCS**. La factory non sa cosa coordinare.

## Pre-push: verifica commit kanban (obbligatorio)

Prima di qualsiasi `git push` (bump di un submodule incluso):

```bash
git status --porcelain management/kanban/
```

Se produce output (file modificati o non tracciati in `management/kanban/`), prima il commit
atomico del kanban, poi il push:

```bash
git add management/kanban/
git commit -m "chore(kanban): wave-close atomic commit — <EP-ID>"
```

**Motivazione**: con il kanban non committato il DAG del run successivo, ricostruito dal
filesystem (R.S6), ripropone lavoro fatto o ignora dipendenze risolte. Procedura completa e gate
umano: `.claude/skills/tpm-wave-close.md` Check (d).

## Fase 3 — `.factory-lock` (solo se `commit_coupling: pin`)

File al root del factory repo. Append-only.

Formato (YAML list):

```yaml
# .factory-lock — generato da vcs-handoff (PATTERN §15)
# Mappa ogni Develop chiuso al commit hash del codice corrispondente.
# Reproducibilità: `git checkout <factory-commit>` → so quale commit di L5 corrispondeva.

- tsk: TSK-042
  layer: be
  vcs_mode: submodule
  submodule_path: ./code/
  commit: a1b2c3d4
  date: 2026-05-20T14:32:00Z
- tsk: TSK-043
  layer: fe
  vcs_mode: sibling
  code_path: /Users/me/Repos/customer-portal/
  commit: e5f6g7h8
  date: 2026-05-20T15:10:00Z
```

Append-only: mai editare entry passate. Se serve correzione, append nuova entry
con marker `correction: true`.

## Fase 4 — Log entry (estensione di `dev-handoff`)

Append a `wiki/log.md` (la stessa entry di `dev-handoff`, ma estesa con info VCS):

```markdown
## YYYY-MM-DD HH:MM — develop TSK-ZZZ
**Agente:** <be-dev|fe-dev|db-dev|qa-dev>
**TSK:** [[../management/kanban/.../TSK-ZZZ]]
**Layer:** <be|fe|db|qa|infra>
**Code path:** <code_path>
**VCS mode:** <monorepo|submodule|sibling|external>
**Branch:** <nome-branch o "shared">
**Commit (L5):** <hash-short o "n/a">
**Commit (factory):** <hash-short se monorepo o submodule bump; "n/a" altrimenti>
**Files touched:** <count>
**DoD:** <pass | partial>
**Note:** <free-form>
```

## Vincoli inviolabili (PATTERN §7 r.14)

- **Mai `git push`** senza conferma esplicita dell'utente, mai automatico.
- **Mai `git submodule add|update --remote`** automatico. Bootstrap stampa il comando, utente lo lancia.
- **Mai `git clone`** automatico per `sibling`: stampa istruzioni.
- **Mai `--force`**, `--no-verify`, `--amend` (preferisci nuovi commit).
- **Mai modificare `.gitmodules`** fuori da questa skill.
- **Mai modificare `.factory-lock`** fuori da questa skill.
- **Mai cambiare branch** nel factory repo (`git checkout <other-branch>`): l'utente decide su quale branch del factory si trova prima di invocare il dev-agent.
- **Mai cambiare branch** in `code_path` per modi `sibling`/`external`: l'utente è responsabile dello stato del repo esterno.
- **Push su branch protetti**: se il branch corrente è `main`/`master` (o coincide con il default branch rilevato da `git remote show origin | grep "HEAD branch"`) E la factory usa `vcs.branch_strategy: per-tsk` o `per-sprint`, stampare avviso: «Branch protetto rilevato — preferire branch feature + PR invece di push diretto per evitare CI bypass». Non bloccare, ma richiedere conferma esplicita dell'utente prima del push.

## Errori comuni

- **HEAD detached** in submodule o sibling → STOP, l'utente deve fare checkout di un branch prima.
- **`.gitmodules` non trovato** in mode `submodule` → STOP, configurazione incoerente.
- **`code_path` non esiste** in mode `monorepo`/`sibling` → STOP, segnala.
- **`code_path` esiste ma non è un git repo** in mode `submodule`/`sibling` → STOP, segnala.
- **Conflitti staged** nel factory repo → STOP, non si committa sopra conflitti aperti.

---

## Decision Anchor Propagation (opt-in v2.19, EP-015)

> **Gated**: `factory.config.yaml.compression.output.decision_anchor.enabled: true`.
> A flag spento questa sezione è no-op, comportamento identico v2.18 (R.P3).

### Step pre-handoff (DA ESEGUIRE PRIMA DI EMETTERE L'HANDOFF)

1. **Controlla presenza**: l'input del dev-agent include `decision_anchor` nel task package?
   - Se NO e `enabled: true` → ERROR `[anchor-stripped]` in `wiki/log.md` + blocco handoff.
   - Se NO e `enabled: false` → no-op.
2. **Controlla checksum**: il campo `decision_anchor.checksum` nel task package ricevuto corrisponde
   all'hash di `canonical_json(decision_anchor.decisions[])`?
   - Se NO → ERROR `[anchor-tampered]` in `wiki/log.md` + blocco handoff.
3. **Copia invariata**: includi il campo `decision_anchor` nell'output del handoff senza modifiche.
   Il dev-agent è **read-only** sull'anchor.

### Struttura handoff arricchita (gated)

```yaml
# vcs-handoff output — sezione aggiunta v2.19
decision_anchor: <<anchor copiato invariato dall'input>>
# Nota: <<...>> = marcatore template cross-adapter (non stampare letteralmente)
```

### Nota VCS

Il campo `decision_anchor` viene incluso nel **bundle metadata** del VCS handoff, non nel
commit message body. Se il provider non supporta extended metadata, il campo viene incluso
nel task package file (.md) allegato al commit.

### Errori

| Codice | Condizione | Severity | Azione |
|--------|-----------|----------|--------|
| `anchor-stripped` | Anchor atteso ma assente | ERROR | Blocco handoff, log `[anchor-stripped]` |
| `anchor-tampered` | Checksum mismatch | ERROR | Blocco handoff, log `[anchor-tampered]` |

### Cross-link

- Schema anchor: `wiki/runbooks/decision-anchor-runbook.md` (TSK-115)
- PATTERN §20.4 R.C7 (TSK-119)
- Skill parallela: `dev-handoff.md` (stessa logica)

---

## Temporal Handoff Block (opt-in v2.18+, gated da `temporal.handoff_protocol.enabled`)

Quando `factory.config.yaml.temporal.handoff_protocol.enabled: true`, ogni handoff
`develop → vcs-handler` include un blocco YAML strutturato `temporal_handoff:`
con **5 campi obbligatori** (contratto invariante cross-skill, identico a `dev-handoff.md`,
ADR-031 §A):

### Schema canonico

```yaml
temporal_handoff:
  handoff_id: "HO-<timestamp-utc>-<random-4char>"   # es. "HO-2026-06-04T14:32:00Z-a1b2"
  elapsed_ms: <integer ≥ 0>                          # wall-clock: epoch_ms(now()) - epoch_ms(task_started_at)
  estimated_remaining_ms: <integer | null>           # best-effort agente uscente; null se non stimabile
  completed_steps:                                   # append-only
    - step_id: "<id>"
      name: "<descrizione breve>"
      started_at: "<UTC ISO-8601 Z>"
      completed_at: "<UTC ISO-8601 Z>"
      agent: "<slug>"                                # es. "be-dev", "vcs-handler"
  pending_steps:                                     # dichiarati nel piano TSK, NON stimati a runtime
    - step_id: "<id>"
      name: "<descrizione breve>"
      agent: "<slug previsto>"
  context_summary: |
    <testo multi-riga — mai vuoto; per VCS include convenzioni commit, stato PR,
    branch target, convention di merge. Aggiunge informazioni di CONTENUTO
    non replicate da completed_steps.>
```

### Punto di iniezione

- **Develop → vcs-handler**: tra il dev-agent (Fase 5 di `dev-protocol`) e il VCS
  handler (questa skill, Fase 0). Il blocco viene incluso nel task package passato
  al VCS handler prima che inizi le operazioni di staging/commit.

### `context_summary` per VCS (esempi obbligatori ≥ 2 elementi)

```yaml
context_summary: |
  Branch: tsk-084-temporal-handoff-block, strategy: per-tsk.
  Nessuna PR aperta su questo branch. Commit convention: feat(docs): <titolo TSK>.
  File modificati sotto .claude/skills/: no impatto su codice applicativo.
```

### Calcolo dei campi (ADR-030)

- `elapsed_ms`: `epoch_ms(now()) - epoch_ms(task_started_at)`. Wall-clock (include attese tool/API/gating). Granularità millisecondi. Fail-loud se negativo.
- Tutti i timestamp UTC ISO-8601 con `Z` (helper `tools/temporal/utc-now.sh`). Vedi ADR-030 §A.
- `estimated_remaining_ms`: best-effort. `null` accettato + nota in `context_summary`.
  Se `temporal.handoff_protocol.use_reference_class: true` AND EP-009 attiva: campo additivo
  `estimated_remaining_ms_from_history` da `analyze_timeline` (ADR-030 §C).

### Proiezione da State Machine (se US-047 attiva)

Se `temporal.state_machine.enabled: true` AND TSK con State Machine attiva (ADR-029):
- `completed_steps[]` = proiezione di `history[]` filtrata per `status: completed`.
- `pending_steps[]` = proiezione di `history[]` filtrata per `status: pending`.
- Single source of truth = state file `management/state/<TSK-id>.json` (ADR-028 §B).

### Vincoli enforced

- **5 campi obbligatori quando flag attivo**: assenza → STOP «missing required field in Temporal Handoff Block: <field>».
- **`context_summary` mai vuoto**: `null` o `""` → STOP «context_summary cannot be empty».
- **Append-only su `completed_steps[]`**: ogni handoff aggiunge, mai modifica retroattivamente.
- **No future prediction su `pending_steps[]`**: dichiarati nel piano TSK, non stimati a runtime.
- **UTC ISO-8601 con Z** su tutti i timestamp (ADR-030 §A).

### Backward compat

- `temporal.enabled: false` (default) O `temporal.handoff_protocol.enabled: false`: skill
  si comporta identica a v2.8. Nessun nuovo ERROR/WARNING. R.P3.
- `temporal.handoff_protocol.enabled: true` AND `temporal.enabled: false`: fail-loud al boot
  «`temporal.handoff_protocol.enabled` richiede `temporal.enabled: true`. Vedi ADR-031 §B».

**Nota scope v2.18** (ADR-031 §D): skill cross-cutting come `code-review-protocol` e
`visual-oracle-protocol` NON sono modificate in v2.18 (scope EP-011 = `dev-handoff` +
`vcs-handoff`). Porting v2.19+ candidate.

Cross-link: [[temporal-awareness-multiagent-patterns]] §Pattern 4 | ADR-031 §A (backward compat) |
ADR-030 (time semantics) | ADR-028 (state file integration) | ADR-029 (state machine activation).
Skill parallela: `dev-handoff.md` (contratto identico, contesto diverso).
