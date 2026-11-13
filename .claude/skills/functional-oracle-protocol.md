---
name: functional-oracle-protocol
description: >-
  Skill 5-fasi per il functional oracle. Esercita l'app reale: Serve → Load Fixture → Drive Scenario → Assert Outcomes → Diff+Loop. Riusa interaction-drive-protocol, screenshot-capture-protocol, app-lifecycle serve. Eseguita da qa-dev in modalita' functional-oracle.
---
# Protocollo Functional Oracle — verifica funzionale end-to-end dell'app reale

Skill procedurale a 5 fasi per l'oracolo funzionale (EP-018): esercita l'app reale con
input reali, esegue lo scenario dichiarato, asserisce gli esiti funzionali osservabili ed
emette un verdict `pass|conditional|reject` con evidenza. È la risposta al failure mode
«sembra finito ma non lo è» al livello funzionale (comportamento, non aspetto grafico).

Eseguita da **`qa-dev` in modalità functional-oracle** (sub-skill, ADR-067 §A): nessun
nuovo sub-agent; `qa-dev` è la sede naturale dell'accettazione funzionale. Fallback se
`qa-dev` non in topologia: la skill gira via `fe-dev` (precedenza analoga ad ADR-014 per
a11y, ADR-067 §A).

**Scope di questo documento (TSK-141 + TSK-142 + TSK-143)**: tutte e 5 le fasi.
Fase 1 (Serve) + Fase 2 (Load Fixture) + Fase 3 (Drive Scenario) + Fase 4 (Assert Outcomes) +
Fase 5 (Diff+Loop bounded).

Riferimenti ADR:
`ADR-064` (app-lifecycle serve +
tool callability binding),
`ADR-065` (acceptance-spec: schema
framework, contenuto progetto, fail-loud §E),
`ADR-066` (delega interazione a
`interaction-drive-protocol`, runtime condiviso),
`ADR-067` (esecutore = `qa-dev`,
verdict deterministico, critic LLM advisory).

Sub-skill / cross-link: invocata dal comando standalone `/functional-oracle <TSK-id|app>`
(US-018a) e da `dev-protocol` quando `fe_correctness.functional_oracle.enabled: true`.
Ordering nel cascade (ADR-066 §Conseguenze): `develop → visual-oracle → functional-oracle → review`.

[^src: design_&_architecture/decisions/ADR-067.md §A]
[^src: design_&_architecture/decisions/ADR-065.md §E]
[^src: design_&_architecture/decisions/ADR-066.md §B §C]

## Prerequisiti

- `fe_correctness.functional_oracle.enabled: true` (master gate — STOP no-op altrimenti,
  R.P3). A flag spento la skill è un no-op dichiarato (backward compat totale).
- `qa-dev` con `Bash` nel frontmatter (ADR-064 §A): il binding callable è obbligatorio
  per servire l'app ed eseguire Playwright.
- Playwright disponibile nel project host: verificato alla Fase 1 (fail-loud altrimenti).
- `code_path` del TSK risolvibile (frontmatter `code_path:` o `target:` → entry in
  `code_paths`).
- `acceptance-spec` presente e valida se `enabled: true` (ADR-065 §E).

### Skill complementare — `deep-functional-probe`

Per scenari funzionali **complessi** (stati multi-livello, flussi asincroni profondi,
side-effect su storage persistente), la skill `deep-functional-probe` può essere invocata
**prima** del functional oracle come sondaggio avanzato dello stato funzionale dell'app.

Quando usarla:
- Il TSK presenta acceptance-spec con `>5` asserzioni `blocking` interdipendenti.
- Lo scenario coinvolge flussi asincroni con race-condition note (es. IndexedDB write
  prima di canvas render).
- Iterazioni precedenti del functional oracle hanno prodotto `conditional` per ragioni
  non diagnosticabili dal trace standard.

Invocazione (opzionale, non sostituisce questa skill):
```
deep-functional-probe(<TSK-id>) → probe_report: { findings, suggested_assertions }
```

Il `probe_report` arricchisce l'acceptance-spec con asserzioni supplementari prima
dell'esecuzione delle 5 fasi. La skill è **sempre opt-in** (backward compat totale).

[^src: `.claude/skills/deep-functional-probe.md`]
[^src: design_&_architecture/decisions/ADR-064.md §C §D]
[^src: design_&_architecture/decisions/ADR-065.md §E]

## Costanti

```
MAX_ITERATIONS    = fe_correctness.functional_oracle.max_iterations  # default 3 (ADR-067 §C / R.Q4)
REPORTS_DIR       = "code_quality/reports"                           # side-channel riusato (ADR-065 §Storage)
ACCEPTANCE_GLOB   = "code_quality/acceptance/<app|tsk>.acceptance.yaml"
SCHEMA_PATH       = ".claude/schemas/acceptance-spec.schema.yaml"    # schema authoritative (US-069)
RUNNER_DIR        = ".factory-runners"                               # script Bash, gitignored (ADR-008 §Rationale 2)
```

---

## Fase 1 — Serve

**Input atteso**: `TSK-id`, `factory.config.yaml`, `code_path` risolto.

**Principio — single source**: questa fase **non reimplementa** il serve. Delega
interamente ad **ADR-064 Step 1.0** (app-lifecycle serve) come unico punto di verità
per il ciclo di vita del server. Nessuna logica di serve inline in questa skill.

**Criterio di completamento**: `server_url` raggiungibile HTTP 200 **AND** `npx
playwright --version` exit 0 **AND** cartella artefatti
`code_quality/reports/<TSK-id>-functional-iter-<N>/` creata.

**Output prodotto**: `server_url`, `server_pid`, `server_port`, `current_iter`,
`code_path` risolto, cartella artefatti creata.

> **Trigger vincolante** — Passi 1-8, CWD, readiness fail-loud verbatim, Playwright
> check fail-loud verbatim, teardown garantito: leggere obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/fase1-serve-detail.md`
> prima di eseguire la fase. File assente → STOP fail-closed.

---

## Fase 2 — Load Fixture

**Input atteso**: frontmatter TSK (`functional_acceptance_spec:`, `id`), `code_path`
risolto (Fase 1), `server_url` (Fase 1).

### 2.2 — Gate `enabled`

`functional_oracle.enabled: false` (default, R.P3) → **no-op** dichiarato. Log a chat:
«Functional oracle disabilitato per questo TSK; abilitare con
`fe_correctness.functional_oracle.enabled: true`». Backward compat totale: la skill è
inerte a flag spento.

[^src: design_&_architecture/decisions/ADR-065.md §E «functional_oracle.enabled: false → no-op»]

### 2.3 — Fail-loud su `enabled: true` + spec assente

Se `enabled: true` **e** la spec non è trovata/leggibile → **fail-loud** (config
incoerente: l'utente ha optato nel functional oracle senza fornire il contratto).
Messaggio canonico **verbatim** (ADR-065 §E):

> Functional oracle abilitato (`enabled: true`) ma acceptance-spec non trovata.
> Path cercati: (1) frontmatter `functional_acceptance_spec: <path>` — assente o
> non risolto; (2) `code_quality/acceptance/<TSK-id>.acceptance.yaml` — non trovato;
> (3) `code_quality/acceptance/<app-slug>.acceptance.yaml` — non trovato.
> Creare il file acceptance-spec seguendo lo schema
> `.claude/schemas/acceptance-spec.schema.yaml`. Non è possibile procedere senza il
> contratto di accettazione (anti-fabbricazione ADR-065 §E).

STOP: non procedere alle fasi successive. MAI un pass silenzioso su spec assente
(ADR-063/ADR-064 anti-fabbricazione).

[^src: design_&_architecture/decisions/ADR-065.md §E «enabled: true + spec assente → fail-loud»]
[^src: design_&_architecture/decisions/ADR-063.md §A «fail-loud su evidenza mancante»]

### 2.5 — Verdict `skip` su `scenario: []`

Se la spec è valida ma `scenario` è un array vuoto (`[]`) → **verdict `skip`
dichiarato**, non `pass` silenzioso (ADR-065 §E). Log a chat:

> Acceptance-spec `<path>` presente e valida ma `scenario: []` — nessuno scenario
> da eseguire. Verdict: `skip` (dichiarato). Il functional oracle non può produrre
> un `pass` su scenario vuoto (anti-fabbricazione).

Aggiorna `functional_status: skip` nel frontmatter TSK (single-writer). Non procedere.

[^src: design_&_architecture/decisions/ADR-065.md §E «scenario vuoto → skip dichiarato, non pass»]

**Criterio di completamento**: spec valida (4 sezioni presenti), tutti i fixture
dichiarati esistono sul filesystem, `scenario` non vuoto.

**Output prodotto**: `spec_path` risolto, `spec` parsed (YAML), `fixture_paths` verificati.

> **Trigger vincolante** — Risoluzione path spec (§2.1), validazione schema 4 sezioni
> obbligatorie (§2.4), verifica existence fixture (§2.6): leggere obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/fase2-fixture-schema-detail.md`
> prima di eseguire. File assente → STOP fail-closed.

---

## Fase 3 — Drive Scenario

**Input atteso**: `spec` (oggetto YAML parsato in Fase 2), `server_url` (Fase 1),
`current_iter` (Fase 1), `code_path` risolto, cartella artefatti (creata in Fase 1).

**Principio**: questa fase **non contiene logica Playwright inline**. Delega l'intera
esecuzione dello scenario a `interaction-drive-protocol` (ADR-066 §B — single source of
truth per l'interazione Playwright scriptata). Aggiunge solo responsabilità orchestrative:
aprire browser, intercettare log, chiudere browser.

**Criterio di completamento**: `trace` disponibile (anche parziale su errore fatale);
`console_log_path` e `network_log_path` scritti; browser chiuso.

**Output prodotto** (`scenario_evidence`): `trace`, `screenshots`, `console_log`,
`network_log`, `console_log_path`, `network_log_path`.

> **Trigger vincolante** — §3.1 verifica prerequisito `interaction-drive-protocol`,
> §3.2 apertura browser+log, §3.3 esecuzione scenario via `interaction-drive-protocol`,
> §3.4 screenshot via `screenshot-capture-protocol`, §3.5 chiusura log: leggere
> obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/fase3-drive-scenario-detail.md`.
> File assente → STOP fail-closed.

---

## Fase 4 — Assert Outcomes

**Input atteso**: `spec` (oggetto YAML, Fase 2), `scenario_evidence` (Fase 3),
`factory.config.yaml` (per `fe_correctness.functional_oracle.critic`).

**Principio**: il verdict nasce **esclusivamente** da asserzioni binarie deterministiche
(ADR-067 §B). Nessun LLM nel path di `pass`/`fail`. Il critic LLM è invocato dopo la
determinazione del verdict e può solo aggiungere osservazioni advisory — mai alterare
il verdict positivamente (ADR-067 §B).

### 4.2 — Verdict deterministico (ADR-065 §D)

| Condizione | Verdict |
|---|---|
| Tutte le asserzioni `blocking` passano **E** advisory fallite `<=` `advisory_max` | **`pass`** |
| Tutte le asserzioni `blocking` passano **MA** advisory fallite `>` `advisory_max` | **`conditional`** |
| Almeno una asserzione `blocking` fallisce | **`reject`** |

```
verdict_summary:
  blocking_total:   int
  blocking_pass:    int
  blocking_fail:    int
  advisory_total:   int
  advisory_fail:    int
  advisory_max:     int     # da spec.thresholds.advisory_max
  verdict:          "pass" | "conditional" | "reject"
```

**Il verdict è definitivo dopo questo calcolo.** Il critic LLM (§4.4) può aggiungere
osservazioni ma **non modifica** `verdict_summary.verdict`.

### 4.4 — Critic LLM: invarianti (ADR-067 §B)

Condizionale: SOLO se `critic == "advisory"`. Se `critic: "off"` → salta interamente.

**Invarianti (non violabili)**:
1. Il critic **non modifica** `verdict_summary.verdict`.
2. Il critic **non può promuovere** a `pass` un verdict `reject` o `conditional`.
3. Il critic **può abbassare** il verdict aggiungendo `open_questions` advisory (il
   campo `verdict` resta immutato).
4. Ogni osservazione del critic **deve citare un artefatto reale del trace**
   (evidence-provenance ADR-063 §B). Finding senza artefatto reale → scartato.

**Criterio di completamento**: 8 primitive dispatchate su ogni asserzione; `verdict_summary`
calcolato; critic invocato (o skippato); `open_questions` filtrati per evidence-provenance.

**Output prodotto** (`assertion_results`): `results`, `verdict_summary`, `open_questions`.

> **Trigger vincolante** — 8 primitive dispatch (§4.1+§4.1.1), tabulazione (§4.3),
> invocazione critic LLM e schema `CriticFinding` (§4.4): leggere obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/fase4-assert-primitives.md`.
> File assente → STOP fail-closed.

---

## Fase 5 — Diff+Loop bounded

**Input atteso**: `assertion_results` (Fase 4: `results`, `verdict_summary`,
`open_questions`), `current_iter`/`MAX_ITERATIONS` (Fase 1), `TSK-id`, `server_pid`
(per teardown garantito).

**Principio**: diff azionabile → `feedback-router` (ADR-009) → dev-agent (`qa-dev`
fallback `fe-dev`). Loop bounded da `max_iterations` (default 3, ADR-067 §C / R.Q4).

### 5.3 — Routing verdict → azione

| `verdict` | `functional_status` scritto | `next_action` | Comportamento |
|---|---|---|---|
| `pass` | `pass` | `done` | Aggiorna frontmatter TSK; pronto per review (ordering ADR-066 §B). |
| `conditional` | `conditional` | `loop` | Diff → feedback-router → dev-agent; bounded da `MAX_ITERATIONS`. |
| `reject` | `reject` | `escalate-human` | Gate umano (PATTERN §7 r.16); TSK resta in-progress. |
| `skip` | `skip` | `done` | Già impostato in Fase 2 §2.5; nessuna ulteriore azione. |

### 5.6 — Aggiornamento frontmatter TSK (single-writer)

Scrive **solo** il campo `functional_status:` nel frontmatter TSK (MAI sovrascrivere
altri campi — R.Q2 / ADR-065 §Storage):

| Valore | Quando scritto |
|---|---|
| `pass` | verdict `pass` §5.3 |
| `conditional` | verdict `conditional` §5.3 (loop in corso) |
| `reject` | verdict `reject` §5.3, oppure loop esaurito §5.5 |
| `skip` | scenario vuoto (Fase 2 §2.5); questa skill non lo ri-scrive se già `skip` |

**Criterio di completamento**: report JSON+MD scritti, `functional_status` aggiornato,
server teardown eseguito, `next_action` determinato e azione avviata.

**Output prodotto**: report JSON+MD, `functional_status` aggiornato, `wiki/log.md`
aggiornato; su `conditional`: diff §5.4 a `feedback-router`; su `reject`/loop esaurito:
blocco chat §5.7.

> **Trigger vincolante** — §5.1 teardown server, §5.2 schema report JSON+MD, §5.4 diff
> azionabile, §5.5 loop bound, §5.7 blocco chat escalation, §5.8 log append: leggere
> obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/fase5-report-loop-escalation.md`.
> File assente → STOP fail-closed.

---

## Nota single-writer su `functional_status` (ADR-065 §Storage)

**SOLO questa skill** (`functional-oracle-protocol`, eseguita da `qa-dev`) scrive il
campo `functional_status:` nel frontmatter del TSK. È il **single-writer** del campo
(analogo a `visual_status` per EP-005, `review_status` per CQRL, R.Q2). Dev-agent, PM,
TPM, orchestrator **NON** lo scrivono a runtime: lo leggono soltanto. Enum del campo:
`pending | pass | conditional | reject | skip`. Questo evita race condition e drift.

[^src: design_&_architecture/decisions/ADR-065.md §Storage/frontmatter]
[^src: design_&_architecture/decisions/ADR-067.md §B]

---

## Fixture del caso peggiore (opzionale, `ui_craft`)

Attiva **solo** con `ui_craft.enabled: true` e `ui_craft.worst_case_data: true`; a flag spento nulla cambia e questa
sezione si ignora. Il caso peggiore è una **fixture in più** (Fase 2) su cui girano le stesse asserzioni della Fase 4,
con stato asserito via engine/DOM e primo run validato per evitare falsi reject. Il report delle rotture precede ogni
correzione. Metodo, catalogo e formato dell'esito: `.claude/skills/kowalski-worst-case-data.md` (comando `/worst-case`).

---

## SSR Context Extension (EP-030, v2.22)

> **Precondizione**: questa sezione è attiva SOLO quando `fe_correctness.ssr_aware.enabled: true`
> AND `ssr_context.framework != 'none'` (framework rilevato da `stack-detector` SSR section,
> TSK-200). A flag spento o con `framework: none` → nessun campo `ssr_context:` aggiunto,
> nessuno scenario SSR generato, comportamento identico a v2.21 (backward compat totale, R.P3).

Il campo `ssr_context:` è un'estensione **opzionale additiva** all'acceptance-spec
(backward-compatible, 0 ERROR lint su spec esistenti). `qa-dev` genera scenari nelle
categorie (critical path SSR / ISR revalidation / hydration check) SOLO se entrambe le
precondizioni sono soddisfatte.

> **Trigger vincolante** — Schema `ssr_context:` YAML, semantica sotto-campi, regola
> guardia `qa-dev`, tabella categorie SSR, invarianti: leggere obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/ssr-context-extension.md`.
> File assente → STOP fail-closed.

---

## Pattern / ADR di riferimento

Questa skill istanzia il pattern **evaluator-optimizer** (producer deterministico + critic
advisory). Verdict fail-closed su asserzioni binarie (ADR-065 §C). Single-source per ogni
componente runtime (ADR-064/ADR-066/ADR-017). Side-channel CQRL riusato (ADR-065 §Storage).
Ordering nel cascade: `develop → visual-oracle → functional-oracle → review`.

> **Trigger vincolante** — Pattern evaluator-optimizer, fail-closed, single-source,
> side-channel, tabella ADR vincolanti: leggere obbligatoriamente
> `.claude/skills/references/functional-oracle-protocol/pattern-adr-reference.md`.
> File assente → STOP fail-closed.

[^src: design_&_architecture/decisions/ADR-067.md §Rationale «anti-fabbricazione strutturale»]
[^src: design_&_architecture/decisions/ADR-066.md §Rationale «single-source per riga di runtime»]
[^src: design_&_architecture/decisions/ADR-065.md §Storage «side-channel report»]
[^src: design_&_architecture/decisions/ADR-008.md §Decisione «Playwright via Bash»]
[^src: design_&_architecture/decisions/ADR-017.md §Decisione «screenshot-capture-protocol»]
