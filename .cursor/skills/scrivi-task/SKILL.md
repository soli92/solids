# Skill: Scrivi Task

> Adapter Cursor della skill `scrivi-task` definita in PATTERN.md.

# Procedura per scrivere un task

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (cascade: il task cita US/ADR/design).

## Path

`management/kanban/EP-XXX-<slug>/US-YYY-<slug>/TSK-ZZZ.md`

## Frontmatter (minimal, v2.11)

```yaml
---
id: TSK-ZZZ
sprint: NN
layer: be | fe | db | qa | infra
consumer: agent | human
priority: P0 | P1 | P2
estimate: XS | S | M | L
status: todo | in-progress | done
depends_on: []           # v2.11: lista TSK prerequisiti (es. [TSK-007, TSK-012]) — hard block
blocked_by: []           # v2.11: lista Q_NNN hard aperte che bloccano il TSK
code_path: []            # v2.11: lista path/glob L5 toccati (es. ["src/auth/**", "src/api/v1/login.py"])
# Campi EP-018 (Functional Oracle) — opzionali/additivi; assenza = 0 ERROR di lint (no-op se fe_correctness.functional_oracle.enabled: false)
functional_status: pass | conditional | reject | skip | pending  # EP-018 opt-in; single-writer: skill functional-oracle-protocol (qa-dev)
functional_acceptance_spec: <path>  # EP-018 opt-in; path acceptance-spec YAML; scritto dal TPM/progetto al momento della tasking
# Campi EP-029 (Test Failure Taxonomy) — opzionali; solo per TSK layer: qa.
# Campo assente = nessun effetto sul routing (backward compat totale, US-102).
# Valori ammessi: APPLICATION_BUG | SSR_BUG | TEST_BUG | INFRASTRUCTURE | FLAKY
# Impostabile da qa-dev (auto) o da umano (override manuale).
failure_classification:   # opzionale — omettere se non applicabile
---
```

Note:
- `story` ed `epic` deducibili dal path.
- `layer` sostituisce il vecchio `team` (deprecato in v2.7).
- `consumer` = default da `factory.config.yaml.routing.<layer>`. Override esplicito ammesso.
- Se la topologia non include un dev-agent per `<layer>` ma `consumer: agent`,
  il [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) segnalerà incoerenza.

Se aggiungi `risk_classification:`, vedi PATTERN §5 per lo schema completo (opt-in v2.16). Non duplicare qui.

### Campi v2.11 — input per il parallel scheduler (PATTERN §18)

- **`depends_on: [TSK-XXX, ...]`** — TSK che DEVONO essere `status: done` prima
  che questo possa partire. Hard dependency. Lo scheduler usa questa lista per
  costruire il DAG (toposort + level grouping). **Sezione `## Dependencies` del
  body è ora derivata da questo campo, non canonica.** Se entrambi presenti,
  vince il frontmatter; [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) segnala drift.
- **`blocked_by: [Q_NNN, ...]`** — `Q_NNN` con `Bloccante: hard` aperte che
  toccano il TSK. Equivalente al campo omonimo su US (vedi [scrivi-user-story](mdc:.cursor/skills/scrivi-user-story/SKILL.md)).
  Risolta la Q (gap chiuso da [propagate-resolution](mdc:.cursor/skills/propagate-resolution/SKILL.md)), va rimossa.
- **`code_path: ["<glob>", ...]`** — path/glob in `<code_path>/**` che questo TSK
  prevede di toccare in scrittura. Lo scheduler li confronta fra TSK candidate
  allo stesso level: overlap di glob ≠ ∅ → non parallelizzabili (race su file).
  Lista vuota = "scope sconosciuto" → lo scheduler tratta il TSK come
  serializzante (conservativo). Esempi: `["src/auth/**"]`, `["db/migrations/0042_*.sql"]`,
  `["tests/e2e/login.spec.ts"]`. Usa glob, non path assoluti.

## Corpo

```markdown
# TSK-ZZZ — <Titolo conciso>

## Context
<US riferita, perché serve questo task>
[^src: management/kanban/EP-XXX-<slug>/US-YYY-<slug>/US-YYY.md §AC]

## Technical Specs
- **BE:** endpoint OpenAPI specifico → `POST /api/v1/foo` ([openapi_schema.yaml §paths./foo](../../../../design_&_architecture/api_specs/openapi_schema.yaml))
- **FE:** pagina/componente → `LoginPage` consuma `POST /api/v1/auth/login`
- **DB:** tabelle impattate
- **Auth:** ruoli abilitati

## Implementation Steps
1. <step 1>
2. <step 2>
3. <step 3>

## Definition of Done
- [ ] Test unitario passa
- [ ] Test integrazione passa
- [ ] Documentazione aggiornata
- [ ] Code review approvata

## Dependencies
<!-- v2.11: lista derivata dal frontmatter `depends_on:` + `blocked_by:`.
     Questa sezione è OPZIONALE e serve solo a esporre rationale umano-leggibile
     (es. "TSK-007 deve girare prima perché definisce lo schema DB").
     La verità per lo scheduler è il frontmatter. -->
- TSK-XXX — <rationale opzionale>
```

## Layer FE — State Matrix nel DoD

> Sezione opt-in (US-021, Leva 4). Contromisura strutturale al failure mode §2
> «esplosione combinatoria degli stati UI» di [[fe-agent-failure-modes]].

**Trigger.** Si applica solo a TSK con `layer: fe` **e** `factory.config.yaml.fe_correctness.state_matrix_inject: true`.
Quando entrambe le condizioni sono vere, il task scritto include — oltre agli `## Acceptance Criteria`
standard — il block «DoD FE — stati obbligatori» qui sotto.

**Gate esplicito.** A flag `state_matrix_inject: false` (default) lo skill **non inietta nulla**:
comportamento identico a oggi. Nessun block, nessuna riga aggiunta. L'opt-in è totale (coerente con
ADR-012 §E, tutti i flag `fe_correctness` default `false`).

**Block template (VERBATIM).** Inserire le seguenti 10 righe in una sezione `## DoD FE — stati obbligatori`:

```
## DoD FE — stati obbligatori (selezionare quelli applicabili)
- [ ] loading state
- [ ] empty state
- [ ] error state
- [ ] success state (happy path)
- [ ] responsive: mobile (≤ 768px)
- [ ] responsive: desktop (≥ 1280px)
- [ ] dark mode / tema alternativo
- [ ] accessibilità da tastiera (tab order, focus visible)
- [ ] contenuti di lunghezza variabile (testo corto / lunghissimo / overflow)
- [ ] stato disabled / read-only (se form o interazione)
```

**`## DoD FE — stati obbligatori` ≠ `## Acceptance Criteria`.** Sono due sezioni distinte e ortogonali:

- gli **Acceptance Criteria** descrivono *comportamenti misurabili end-to-end* (cosa deve fare il
  sistema, verificabile con un test);
- gli **stati FE obbligatori** descrivono *dimensioni di completezza UI ortogonali* — ciascun stato è
  una faccia della matrice combinatoria che la stessa AC deve coprire (loading, empty, error,
  responsive, tema, a11y, ...).

Tenerle separate evita di confondere «il login funziona» (AC) con «il login è completo in tutti i suoi
stati visivi» (DoD FE). Una AC può essere verde mentre metà degli stati è ancora l'angolo in alto a
sinistra (success + default + desktop + light).

**Regola di selezione (per il TPM).** Il TPM **deve** selezionare gli stati applicabili al singolo TSK:
rimuovere le righe non pertinenti o marcarle `n/a` (es. un componente non interattivo non ha lo stato
`disabled / read-only`; un endpoint-driven widget senza vuoto possibile non ha `empty state`).
**Lasciare il block intatto (10 righe non triage-ate) è un anti-pattern** — segnala che la matrice non è
stata ragionata sul task reale. È l'oggetto del lint di US-022 (granularity / triage del block).

**Motivazione.** I tre failure modes di [[fe-agent-failure-modes]]
spiegano perché serve rendere gli stati criteri *espliciti* nel DoD:

1. **Falso segnale di completamento** (§1) — il FE renderizza «qualcosa» quasi sempre; build verde non
   significa task finito.
2. **Esplosione combinatoria degli stati UI** (§2) — senza checklist esplicita l'agente implementa solo
   `success + default + desktop + light + testo breve` e considera chiuso il task.
3. **Specifica sotto-determinata** (§3) — in assenza di criteri misurabili l'agente inventa le intenzioni
   di design e diverge.

Come recita la contromisura §2: **finché questi non sono criteri espliciti, l'agente tratterà l'happy
path come fine del lavoro.** Il block li rende espliciti e contrattuali.

**Cross-link al visual oracle (EP-005).** La State Matrix è input naturale del visual oracle di EP-005:
**ogni stato selezionato → uno screenshot da verificare** con `visual-oracle-protocol`.
Gli stati spuntati definiscono la matrice di rendering (viewport × tema × stato dati) che la skill
cattura e critica. State Matrix (cosa coprire) e visual oracle (verifica del coperto) sono i due lati
dello stesso ciclo di chiusura del loop FE.

**Backward compat.** Un TSK FE **senza** la sezione `## DoD FE — stati obbligatori` resta pienamente
valido: **0 ERROR di lint**. Il block è additivo e opt-in; la sua assenza non è mai un errore (il triage
mancante quando il block *è* presente è invece materia di lint US-022, WARNING-only).

## Layer FE — Granularity Rule

> Sezione opt-in (US-022, Leva 5). Prompt preventivo di scomposizione per TSK FE troppo grossi
> o con troppe varianti UI. Complementare alla State Matrix qui sopra: quella rende espliciti
> gli stati, questa evita che un singolo TSK ne accumuli troppi.

**Regola (forma OR, VERBATIM).**

> Un TSK con `layer: fe` deve avere `estimate ≤ max_estimate_hours` OPPURE coprire al massimo
> `max_states` stati selezionati. Se ENTRAMBE violate, scomporre.

In altre parole: in fase di scrittura, se anche **solo una** delle due dimensioni è alta
(`estimate > max_estimate_hours` **OPPURE** `states > max_states`), il TPM deve fermarsi e
chiedersi se il TSK vada scomposto. L'OR è volutamente educativo: un TSK da 16h che copre 1 solo
stato è comunque sospetto (perché è così grosso? è davvero uno stato solo?), così come un TSK da
4h che copre 6 stati lo è.

**Soglie default e configurabilità.** I default sono `{max_estimate_hours: 8, max_states: 3}` e
sono configurabili in `factory.config.yaml.fe_correctness.granularity.{max_estimate_hours, max_states}`.
Un progetto con scope atipico (dashboard analytics complessa vs app marketing con tante landing
piccole) può alzare o abbassare le soglie senza toccare lo skill.

**Pattern di scomposizione.** Quando la regola scatta, scomporre seguendo uno di questi pattern:

1. **Un componente per TSK** — se il TSK copre più componenti, splittare un TSK per componente.
2. **Stati uno per volta (o per gruppo coeso)** — se il TSK accumula troppi stati della State
   Matrix, verificare gli stati uno alla volta o a gruppi coesi (es. tutti i `responsive` insieme,
   tutti gli stati-dati insieme), un TSK per gruppo.
3. **Integrazione come TSK separato** — isolare l'integrazione (wiring API, orchestrazione di
   componenti già pronti) in un TSK dedicato, distinto dai TSK di costruzione dei singoli pezzi.

**Motivazione.** Unità più piccole = loop di verifica più stretti = convergenza più affidabile. È il
principio del [[feedback-loop-gate]] applicato alla granularità del task: ogni scomposizione accorcia
il ciclo write → verify → fix, e riduce la superficie su cui l'agente FE può divergere. Deriva
direttamente dalla sintesi `fe-agent-correctness-strategy` §Leva 5.

**Nota sulla divergenza OR (prompt) / AND (lint) — intenzionale.** Il prompt qui sopra usa **OR**
(preventivo, fase di scrittura): il TPM deve essere spinto a riflettere se anche solo una dimensione
è alta. Il lint **Check 4n** (US-022, in [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md)) usa invece **AND** (conservativo, fase di
review): segnala solo se ENTRAMBE le dimensioni sono alte, per non generare rumore su TSK legittimi
a singola dimensione (es. integrazione API pesante con 1 stato, o wizard piccolo con molti step). La
divergenza è intenzionale — «scrittura strict (OR), lint forgiving (AND)» riduce i falsi positivi a
runtime preservando l'educazione preventiva. Riferimento: ADR-011 §Rationale punto 3.

## Layer FE — UX/UI Design Spec (EP-008, ADR-020)

> Sezione opt-in (US-032, capability EP-008). Procedura per il **TPM** per allegare al frontmatter di
> un TSK FE il campo `ui_design_spec: <path>` quando esiste un deliverable di Design per il componente.
> Analoga alla `## Layer FE — Interaction Test Spec` di EP-005 (ADR-012): il deliverable è una specifica
> esterna che il TPM allega al TSK, non un output di runtime.

**Quando suggerirlo.** Se per il componente target del TSK FE esiste un deliverable di Design prodotto
da `/ux-ui-design` (agente `ui-designer`, US-029/030) — tipicamente in
`code_quality/reports/<TSK-id>-uxui-design.json` (+ `.md`), oppure in `code_quality/reports/_adhoc/uxui-design-<...>`
per invocazioni standalone — la skill suggerisce di valorizzare il frontmatter:

```yaml
ui_design_spec: code_quality/reports/<TSK-id>-uxui-design.json
```

**Single-writer: il TPM (ADR-020 §A/§F).** Il `ui-designer` **suggerisce** il path nel proprio output
(logging), ma NON modifica il frontmatter né il corpo del TSK: il TPM **committa** il campo in fase di
scrittura/aggiornamento del TSK. Pattern simmetrico a come il `code-reviewer` suggerisce ma il TPM
committa i campi strutturali. Evita race condition e mantiene il TPM come owner del TSK schema.

**Procedura.**
1. Verifica se esiste un deliverable Design per il componente (path `<TSK-id>-uxui-design.json` o adhoc).
2. Se sì, aggiungi `ui_design_spec: <path>` al frontmatter del TSK FE.
3. Se il deliverable è adhoc e copre più componenti/TSK, scelta del TPM: può citarlo in più TSK.
4. Opzionalmente aggiungi una sezione `## Design Reference` nel corpo del TSK con bullet al wireframe/spec.

**Cosa ne fa il fe-dev.** In Fase 4 (Develop) il fe-dev legge `ui_design_spec:` come specifica visiva di
prima classe (wireframe + `component_spec` + rationale del designer); le `assumptions[]`/`open_questions[]`
non risolte del deliverable possono diventare `open_questions` del TSK. Vedi
`fe-dev` §UX/UI Design spec input.

**Schema deliverable single-shot.** Il deliverable Design è **single-shot** per TSK (no iter-N, distinto
dal report Review iterativo `uxui-review-iter-<N>`): eventuali ridisegni sovrascrivono il file, il
versioning vive in git. Il path resta quindi stabile nel frontmatter.

**Backward compat.** Un TSK FE **senza** `ui_design_spec:` resta pienamente valido: **0 ERROR di lint**.
Il campo è additivo e opt-in; la sua assenza non è mai un errore (il fe-dev sviluppa dalle specifiche
esistenti — corpo TSK, State Matrix, eventuale `visual_reference:`).

## Layer FE — Functional Oracle (EP-018, ADR-065/ADR-067)

> Sezione opt-in (US-071, EP-018). Procedura per il **TPM** per allegare al frontmatter di un TSK
> il campo `functional_acceptance_spec: <path>` quando esiste un'`acceptance-spec` YAML per il
> componente/app target. Analoga a `## Layer FE — UX/UI Design Spec` (EP-008): il deliverable è una
> specifica esterna che il TPM allega al TSK al momento della tasking, non un output di runtime.

**Quando suggerirlo.** Se per il TSK esiste (o si intende creare) un'`acceptance-spec` YAML che
descrive fixture + scenario Playwright + asserzioni per verificare che l'app funzioni come atteso
(ADR-065 §B), la skill suggerisce di valorizzare il frontmatter:

```yaml
functional_acceptance_spec: code_quality/acceptance/<TSK-id>.acceptance.yaml
```

Il path può puntare a una spec per-TSK (`<TSK-id>.acceptance.yaml`) o per-app
(`<app-slug>.acceptance.yaml`) all'interno del glob configurato in
`fe_correctness.functional_oracle.acceptance_spec_glob` (default `code_quality/acceptance/*.acceptance.yaml`).

**Single-writer per campo.**

- `functional_acceptance_spec:` — **single-writer: TPM/progetto** (ADR-065 §Storage, ADR-067 §Config).
  Il TPM scrive questo campo al momento della creazione/aggiornamento del TSK, prima dell'esecuzione
  del functional oracle. Nessun agente lo sovrascrive automaticamente.
- `functional_status:` — **single-writer: `functional-oracle-protocol`** (sub-skill di `qa-dev`,
  ADR-067 §A). Solo la skill di esecuzione scrive questo campo (`pass | conditional | reject | skip |
  pending`). Il TPM non lo valorizza al momento della tasking (lasciare assente o `pending`). Mai
  sovrascritto da altri agenti (dev-agent, reviewer, TPM post-esecuzione).

**Procedura (TPM).**
1. Verifica se esiste (o si intende produrre) un'`acceptance-spec` YAML per il componente/app.
2. Se sì, aggiungi `functional_acceptance_spec: <path>` al frontmatter del TSK.
3. Lascia `functional_status:` assente o a `pending` — lo aggiornerà la skill dopo l'esecuzione.
4. Opzionalmente aggiungi una sezione `## Acceptance Spec` nel corpo del TSK con il path e una
   descrizione breve dello scenario (es. «verifica che il gioco parta e il canvas avanzi»).

**Cosa ne fa `qa-dev` (functional oracle).** In modalità functional-oracle, `qa-dev` legge
`functional_acceptance_spec:` come contratto di verifica: carica le fixture, esegue lo scenario
Playwright, valuta le asserzioni binarie (ADR-065 §C/§D) e aggiorna `functional_status:` con il
verdict. Il critic LLM (se `functional_oracle.critic: advisory`) ispeziona il trace solo come
osservazione aggiuntiva — mai nel path pass/fail (ADR-067 §B). Vedi
`functional-oracle-protocol`.

**Opzionalità e no-op a flag spento.**

- Se `fe_correctness.functional_oracle.enabled: false` (default) → i due campi sono **completamente
  no-op**: nessun agente li legge, nessun lint genera ERROR o WARNING per la loro assenza.
- La loro **assenza** non genera mai ERROR di lint, indipendentemente dal flag (ADR-065 §E).
- Se `enabled: true` **e** `functional_acceptance_spec:` valorizzato ma il file non esiste →
  ERROR (spec referenziata assente; ADR-065 §E + Lint Check 4z.1).

**Backward compat.** Un TSK **senza** `functional_status:` e senza `functional_acceptance_spec:`
resta pienamente valido: **0 ERROR di lint**. Entrambi i campi sono additivi e opt-in; la loro assenza
non è mai un errore (R.P3 opt-in totale, backward compat totale con factory v2.19).

## Regole

- **Atomicità:** un task = una unità testabile. Mai "Crea modulo Login" → spezza
  in "Crea endpoint POST /auth/login" + "Crea LoginPage React".
- Cita endpoint OpenAPI o pagina FE specifica, non astratti.
- Estimate: XS=<2h, S=mezza giornata, M=1 giorno, L=2+ giorni.
- Citazioni: vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (cascade L4 → US/ADR).
