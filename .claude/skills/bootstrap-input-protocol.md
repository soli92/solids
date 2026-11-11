---
name: bootstrap-input-protocol
description: >-
  Skill di raccolta input per il meta-prompt factory-bootstrap v2.12 (PATTERN §13). Espone (a) un
  Quick path via archetipi predefiniti per scenari comuni e (b) un Linear path A→G per scenari
  custom. Output strutturato: dict di input da passare alle skill bootstrap-* successive.
---
# Skill — Bootstrap input collection

Riferimenti: PATTERN §13 (topology), §14 (stack modes), §16 (sync adapters incluso
existing-repo), §17 (publisher), §18 (parallel scheduler), §19 (code quality review).
Invocata dal meta-prompt `factory-bootstrap` come Fase 2.

## Output schema (return value)

```yaml
project_name: <string>
target_path: <abs-path>
language: it | en | <other>
owner: <string>
topology: knowledge-only | plan-only | full-stack-agents | hybrid-be-agents | hybrid-fe-agents | custom
custom_devs: [be|fe|db|qa]   # solo se topology=custom
stack_mode: manual | guided | auto
standards: [<verbatim>...]
wiki_feed_source: empty | pdf | figma | existing-repo
pdf_folder: <path>            # solo se pdf
figma_url: <url>              # solo se figma
existing_repos:               # solo se existing-repo (lista, vedi bootstrap-multirepo-protocol)
  - name, path, layers, tags, coupling
kanban_publish:
  provider: none | github | gitlab | jira | linear | custom
  target: <string>
  auth_env: <string>
scheduler:
  enabled: true | false
  # cap defaults applicati se enabled
code_quality:
  enabled: true | false
  # default ragionevoli applicati se enabled
stack:                         # solo se stack_mode=guided
  backend, frontend, database, qa, infra
```

## Path A — Quick path archetipi (decision tree, default)

Mostra all'utente i 5 archetipi più comuni. Ogni archetipo applica preset ragionevoli;
l'utente può override singole voci dopo.

```
SCEGLI UN ARCHETIPO O 'custom' PER FLUSSO COMPLETO:

1. knowledge-only      — solo wiki/ingest, no codice
2. greenfield-full     — nuovo progetto, full-stack agentico in monorepo
3. existing-monolith   — repo monolite esistente, retrofit con factory
4. microservices       — N microservizi BE + (opzionale) 1 FE
5. micro-frontend      — N FE indipendenti + 1+ BE shared
6. custom              — flusso completo A→G (sotto)
```

### Preset per archetipo (applicati prima del riepilogo)

| Archetipo | topology | wiki_feed_source | code_quality | kanban_publish | scheduler |
|---|---|---|---|---|---|
| `knowledge-only` | `knowledge-only` | chiedi (default `empty`) | off (no codice) | off | enabled (solo ingest/lint/query/sync) |
| `greenfield-full` | `full-stack-agents` | `empty` | chiedi (suggerito on) | chiedi (default off) | enabled tutti i domini |
| `existing-monolith` | chiedi (suggerito `full-stack-agents` o `hybrid-*`) | `existing-repo` (1 repo) | chiedi (suggerito on per codice esistente) | chiedi | enabled |
| `microservices` | `full-stack-agents` o `hybrid-be-agents` | `existing-repo` (N ≥ 2 repo, layers=[be] per ciascuno) | chiedi (suggerito on) | chiedi (suggerito on per coordinare release) | enabled (review parallelo molto utile) |
| `micro-frontend` | `full-stack-agents` o `hybrid-fe-agents` | `existing-repo` (N ≥ 2 FE + 1+ BE) | chiedi (on per coerenza UX) | chiedi | enabled |

Dopo selezione archetipo, chiedi **solo** le domande non pre-impostate (es. per
`microservices` chiedi N repo, path, name di ciascuno; per `greenfield-full` chiedi
stack_mode + stack). Riduce 12 domande → 3-5 per scenario standard.

## Path B — Linear path A→G (custom o override)

Quando l'utente sceglie `custom`, o vuole override dell'archetipo, sequenza canonica
con AskUserQuestion **una sola sequenza** dove possibile:

### A. Lingua del contenuto
Italiano (default) / Inglese / Altra

### B. Owner
Default: `soli92` (o quello dell'archetipo se settato).

### C. Topologia (PATTERN §13)
| Topologia | Descrizione |
|---|---|
| `knowledge-only` | Solo ingest + wiki. No planning, no execution. |
| `plan-only` | Fino a TSK; consumer umano (default v2.6). |
| `full-stack-agents` | Tutti i dev-agent (be/fe/db/qa). |
| `hybrid-be-agents` | BE/DB agentici, FE/QA umani. |
| `hybrid-fe-agents` | FE agentico, BE/DB/QA umani. |
| `custom` | Sub-set arbitrario (chiedi quali). |

### D. Code path (L5) — SKIP se G=`existing-repo` (derivato dal coupling, vedi `bootstrap-multirepo-protocol`)

Se topologia ammette dev-agent: `code_path` default `./src/` o assoluto.
Knowledge-only/plan-only: `code_path: ""`.

### D-bis. VCS mode (v2.8, PATTERN §15) — SKIP se G=`existing-repo`

`monorepo | submodule | sibling | external | none`. Coerente con `code_path`.
Follow-up condizionali (submodule_path, remote_url, branch_strategy, commit_coupling).

### D-ter. External task tracker / Kanban publish — opzionale (v2.10, §17)

**Opt-in**: pubblica EP/US/TSK su tool esterno come mirror push-only.

`provider`: `none` (default) | `github` | `gitlab` | `jira` | `linear` | `custom`.
Se ≠ none: chiedi `target`, env var token (default `GH_TOKEN` per github).

**Sinergia existing-repo**: se G=`existing-repo` + provider=`github` + repo già su
GitHub, suggerisci `target: <org>/<existing-repo>` (conferma esplicita).

### D-quater. Parallel scheduler (v2.11, §18)

Default raccomandato `enabled: true`. Defaults sicuri: `max_parallel: 4`,
`parallel_gate_threshold: 3`, `code_path_conflict: strict`,
`empty_code_path_policy: serial`. Domini default on: `ingest, develop, lint, query, sync, review`.

### D-quinquies. Code Quality Review Layer (v2.12, §19) — solo se topologia ha dev-agent

| Opzione | Comportamento |
|---|---|
| `enabled: false` (default) | Nessun review post-Develop. |
| `enabled: true` | 3 passate (idiomaticità + design + robustezza), max_iterations 3, reject = gate umano. |

Se on: ricorda «non sostituisce qa-dev, non copre security; popolare
`code_quality/rules/canonical/` con regole per lo stack prima del primo `/review`».

### E. Stack mode (PATTERN §14)
`manual` (default) | `guided` (mini-questionario stack §3 sotto) | `auto` (tech-scout).

### F. Standards / vincoli normativi noti
Lista libera (SPID, OIDC, FHIR, eIDAS, GDPR, …). Verbatim §11 in `raw/tech_stack.md`.

### G. Wiki feeding source (v2.12)

| Opzione | Comportamento |
|---|---|
| `empty` (default) | wiki vuota; utente popola `raw/` dopo. |
| `pdf` | Chiedi path cartella PDF (vedi G-bis). Suggerisci `/sync-docs` come next step. |
| `figma` | Chiedi URL/file_key (vedi G-ter). Suggerisci `/figma-sync <url>` next step. |
| `existing-repo` (v2.12) | Delega a `bootstrap-multirepo-protocol` (G-quater + G-quinquies multi-repo loop). |

**Ordering hint**: se l'utente sceglie `existing-repo`, **invoca `bootstrap-multirepo-protocol` prima** di D/D-bis (che vengono derivate dal coupling).

### G-bis/ter/quater — vedi bootstrap-multirepo-protocol per existing-repo

### Stack guided (se stack_mode == guided)

Per ciascun layer attivo, proponi 3 opzioni curate 2026 con 1 riga pro/contro:
- backend: FastAPI / Express / Spring Boot / NestJS
- frontend: React / Vue / SvelteKit / Solid / Angular
- database: PostgreSQL / MongoDB / SQLite / DynamoDB
- qa: Pytest+Playwright / Vitest+Cypress / JUnit+Selenium

**Mai inventare**: se utente sceglie "Altro" e non specifica, lascia `""` in config.

## Vincoli inviolabili

- **Mai bypassare domande pertinenti**: se l'archetipo non pre-imposta una voce
  rilevante per la topology scelta, chiedila esplicitamente.
- **Mai pre-impostare standards verbatim**: la sezione F è sempre input esplicito
  dell'utente (legale/compliance, mai inventato).
- **Mai chiedere domande irrilevanti**: es. D-quinquies (CQRL) se topology è
  knowledge-only — skip.
- **Auto-derive trasparente**: quando una domanda è skip per via dell'archetipo o
  del coupling, mostra in chat «<campo>: <valore-derivato> (auto da <archetipo|coupling>)».

## Return value

Restituisci al meta-prompt il dict completo definito sopra. Il meta-prompt lo passa
alle skill successive (`bootstrap-multirepo-protocol`, `bootstrap-scaffolding-protocol`, …).

### H. Capability opt-in — Voice Channel (v2.28+, EP-041, PATTERN §30)

**Opt-in**: il Voice Channel è disabilitato di default (R.P3). Chiedi all'utente:

> «Vuoi abilitare il canale vocale (interazione STT/TTS con la factory)?
> Richiede: Python .[voice], modello piper italiano, Anthropic API key.»

Se **sì**: aggiungi al config output:

```yaml
voice_channel:
  enabled: true
  stt:
    model: <chiedi: tiny|base|small|medium|large — default small>
  tts:
    voice: <chiedi: voce piper — default it_IT-paola-medium>
  runtime:
    provider: anthropic
    llm_model: <chiedi — default claude-sonnet-5-5>
  wake_word:
    enabled: <chiedi: true|false — default true>
    keyword: <chiedi se enabled — default prometeus>
```

**Poi**: dopo il bootstrap, ricorda all'utente di eseguire `/voice-install` per
l'installazione guidata (prerequisiti, campioni wake word, LaunchAgent).

Se **no**: ometti il blocco `voice_channel:` dal config output (la factory derivata
avrà lo stub con `enabled: false`, backward compat totale).
