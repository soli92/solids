> Modulo di PATTERN.md (§24–§37) — indice e versione: [`PATTERN.md`](PATTERN.md).

## §24 — Design Intelligence Layer (v2.21, EP-019, opt-in)
<!-- profiles: full -->

> Capability opt-in che estende EP-008 (UX/UI Review & Design) con coordinamento tematico
> centralizzato (art-director), separazione LLM/generatore deterministico, gate reasoning-first,
> critica strutturata (Critic/Judge) e asse Intention Economy. Default off (R.P3): factory
> v2.20 identica a flag spenti. Dipendenza: `design_intelligence.enabled: true` richiede
> `ux_ui.enabled: true` (fail-loud al boot). **Sezione documentale + capability opt-in, nessuna
> nuova invariante §7** (resta 18, stessa natura di §20/§22/§23). Contabilizza +1 verso N:1
> (ADR-052/ADR-055 §Revisione, `N=5`).
> [^src: design_&_architecture/decisions/ADR-068.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-069.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-070.md §Decisione]
> [^src: design_&_architecture/decisions/ADR-071.md §A §B §C §D]

### §24.1 — Concetti e pipeline

Il Design Intelligence Layer introduce 5 concetti distinti nella factory:

| Concetto | Wiki | Skill |
|---|---|---|
| Art-Director Coordination | [[art-director-coordination]] | `art-director-coordination-protocol` |
| Design Rationale | [[design-rationale]] | gate inline in `ux-ui-design-protocol` Step 2-bis |
| LLM-Generator Separation | [[llm-generator-separation]] | `llm-generator-separation-protocol` + tool `run-generator.sh` |
| Critic/Judge Agent | [[critic-judge-agent]] | sub-passo Step 3-bis in `ux-ui-review-protocol` |
| Intention Economy | inline in Step 3-bis | sotto-dimensione del Critic/Judge |

**Pipeline a 4 fasi** (attiva solo con `design_intelligence.enabled: true`):

```
Fase 1 — Intent
  L'agente ui-designer riceve il brief.

Fase 2 — Art-Director (art-director-coordination-protocol)
  Produce DSL intermedia `art_director_spec` (colori, tipografia, spaziatura,
  gerarchia, varianti) — single-writer del tema. Il fe-dev è read-only sul tema (R.D1).
  Poi: design-rationale gate reasoning-first (art_director → rationale → deliverable, R.D2).

Fase 3 — Generatore deterministico (llm-generator-separation-protocol, condizionale)
  Se generator_tool != none: fe-dev produce spec parametrica → skill invoca
  .claude/tools/run-generator.sh → scaffold deterministico (token budget ~zero).
  Fuori-template → spec custom, generatore non invocato (ADR-069 §D).

Fase 4 — Critic/Judge (sub-passo Step 3-bis di ux-ui-review-protocol, condizionale)
  Se critic_enabled: true: valuta render su 6 principi visivi + asse Intention Economy
  (se rubric_intention_economy: true). Strumento di refinement, NON oracolo (R.D3).
```

### §24.2 — Configurazione (`design_intelligence:` block)

```yaml
design_intelligence:
  enabled: false                   # master switch; richiede ux_ui.enabled: true
  art_director: false              # gate art-director + design-rationale (ADR-068)
  generator_tool: none             # none | plop | yeoman (ADR-069)
  critic_enabled: false            # passo Critic/Judge 6 principi (ADR-070)
  rubric_intention_economy: false  # asse Intention Economy (ADR-070 §E)
```

Tutti i sotto-flag sono inerti se `enabled: false` (gating gerarchico). A tutti i flag
al default: factory identica a v2.20 (backward compat totale, R.P3).

**Validation fail-loud al boot**: se `design_intelligence.enabled: true` AND
`ux_ui.enabled: false` → messaggio canonico: «`design_intelligence` richiede
`ux_ui.enabled: true`» (ADR-071 §B).

### §24.3 — Confine con EP-005 e EP-008

| Capability | Scopo | Output | Sede |
|---|---|---|---|
| EP-005 Visual Oracle | Correttezza funzionale FE («il rendering aderisce alla spec») | Verdict **deterministico** pass/conditional/reject | `visual-oracle-protocol` (Fase 4-bis dev-protocol) |
| EP-008 UX/UI Review | Review euristica (Nielsen 10 + UI 6 + flusso 5) | Findings qualitativi + `rubric_ref` | `ux-ui-review-protocol` Step 3 |
| EP-019 Critic/Judge | Qualità visiva design («è UX-buono vs 6 principi») | Critiche di refinement qualitative (NON oracolo, R.D3) | `ux-ui-review-protocol` Step 3-bis |

Le tre capability sono **complementari nell'ordering** (`develop → visual-oracle → ux-ui-review
→ critic-judge`): nessuna sovrapposizione di scope, runtime cattura condiviso (ADR-017).

### §24.4 — Regole R.D1-R.D3

- **R.D1 — No bypass del canale DSL art-director**: la DSL prodotta da `art-director-coordination-protocol`
  è l'unico canale stilistico autorizzato tra art-director e fe-dev. Il tema non è comprimibile né
  bypassabile; il fe-dev è read-only sul tema. [ADR-068 §C]
  *Nota cross-link compression §20*: la DSL art-director è audit-trail, non comprimibile aggressivamente.

- **R.D2 — Ordine obbligatorio reasoning-first**: l'ordine è `art-director (tema/DSL) →
  design-rationale (reasoning) → produzione (deliverable/codice)`. L'LLM non produce prima
  di dichiarare il rationale strutturato (`decision`, `alternatives_considered`, `rationale`,
  `constraints_applied`, `consequences.resolution_velocity_impact`). [ADR-068 §B; US-074]

- **R.D3 — Il Critic/Judge non è oracolo**: il Critic/Judge Design è strumento di refinement
  qualitativo. Non emette verdict deterministico bloccante; correlazione con giudizio umano
  non garantita. Ancorare a checkpoint umani dove possibile. Ogni finding richiede
  `evidence_zone` (guard evidence-provenance, ADR-063 §B). [ADR-070 §C]

[^src: design_&_architecture/decisions/ADR-071.md §C]

---

## §25 — Semantic Drift Detection (v2.23, EP-031, opt-in L3 / always-on L1)
<!-- profiles: full -->

> Capability di monitoraggio della deriva semantica tra le pagine wiki e le sezioni PATTERN.md
> che referenziano tramite il campo frontmatter `pattern_section:`. Architettura a piramide a tre
> livelli (ADR-EP031-001, GO-MODIFIED, 2026-06-25): L1 staleness (always-on, age-based) →
> L2 LLM-judge (manuale, graceful degradation) → L3 embedding coseno (opt-in, API key richiesta).
> Check 4ag (L1) è **sempre attivo** in `/lint` indipendentemente dalla configurazione.
> Check 4af (L3) è **INFO-only, sperimentale**, non è mai un gate bloccante.
> **Nessuna nuova invariante §7** (resta 18). Complexity budget: §25 è +1 sezione; con N=5
> il ratio 1/1 = 1 ≤ 5 → pass.
> [^src: design_&_architecture/decisions/ADR-EP031-001-semantic-drift-embedding.md §Decisione]

### §25.1 — Architettura a piramide

La rilevazione di deriva semantica è organizzata in tre livelli crescenti di precisione e costo:

```
L1 — Staleness (Check 4ag)         [always-on, zero costo API]
  ▸ Misura: age in giorni dall'ultimo aggiornamento (campo updated_at nel frontmatter)
  ▸ Soglie: age > 180gg → INFO; age > 365gg → WARNING; MISSING-DATE → WARNING
  ▸ Attivazione: automatica nel ciclo /lint, nessuna configurazione richiesta
  ▸ Razionale: proxy oggettivo e a costo zero; una pagina non aggiornata da > 6 mesi
    rischia divergenza man mano che PATTERN.md evolve

L2 — LLM-judge (proxy qualitativo)  [manuale, zero costo API]
  ▸ Misura: score qualitativo [0.0–1.0] assegnato dal modello confrontando body della
    pagina wiki con estratto della sezione PATTERN.md referenziata
  ▸ Trigger: invocazione manuale del comando /semantic-drift-scan
  ▸ Graceful degradation: attivo anche quando l'API embedding è irraggiungibile
  ▸ Scope: corpus ≤ 50 pagine (costo lineare del modello)
  ▸ Razionale: nessun prerequisito di infrastruttura; adeguato per corpora piccoli

L3 — Embedding coseno              [manuale, costo API embedding, opt-in]
  ▸ Misura: similarità coseno tra embedding vettoriale della pagina e dell'estratto PATTERN
  ▸ Trigger: /semantic-drift-scan con wiki_lint.semantic_check.enabled: true + API key
  ▸ Scope: corpus > 50 pagine (costo sublineare grazie a batching API)
  ▸ Razionale: misura metrica riproducibile, indipendente dal modello di giudizio
```

**Decisione ADR-EP031-001 (GO-MODIFIED)**: la piramide è la struttura di riferimento.
L1 è l'unico livello con garanzia always-on. L2 e L3 si escludono per graceful degradation
(se L3 non disponibile → L2; se L2 non disponibile → L1 unico segnale). Il factory derivante
scegli il livello in base a disponibilità API e dimensione corpus; il framework non impone L3.

### §25.2 — Configurazione (`wiki_lint.semantic_check:` block)

```yaml
wiki_lint:
  semantic_check:
    enabled: false           # master switch L3 (R.P3 default off). L1 è SEMPRE attivo.
    similarity_threshold: 0.75  # soglia coseno (provvisoria — calibrazione empirica US-108)
    embedding_model: "voyage-3" # voyage-3 (Anthropic) | text-embedding-3-small (OpenAI)
    cost_warn_usd: 1.0          # gate di conferma esplicita (soglia costo stimato)
    output_report: true         # produce report YYYY-MM-DD in output_report_path
    output_report_path: "code_quality/reports/"
```

- `enabled: false` → L1 (Check 4ag) resta attivo; Check 4af e chiamate API embedding disabilitate.
- `enabled: true` → attiva L3 (Check 4af + chiamate API); L2 usato come fallback se API irraggiungibile.
- La soglia `0.75` è provvisoria: la baseline empirica 2026-06-25 (10 pagine, LLM-judge) mostra
  score medio 0.68 su corpus sotto-soglia; calibrazione su corpus più ampio è US-108 backlog.
- Il gate `cost_warn_usd` è una conferma esplicita analoga a `full_rebuild_cost_warn` di §20:
  nessuna chiamata API viene eseguita senza conferma se il costo stimato supera la soglia.

### §25.3 — Check 4ag e Check 4af (integrazione lint)

I due check si integrano nel ciclo `/lint` (skill `lint-checks`, vedi §10):

| Check | Livello | Severità | Trigger | Gate |
|---|---|---|---|---|
| **4ag** — Staleness threshold | L1 | INFO (>180gg) / WARNING (>365gg o MISSING-DATE) | Ogni `/lint` — always-on | Nessuna configurazione |
| **4af** — Embedding similarity | L3 | INFO-only (mai WARNING né ERROR) | `/lint` solo se `enabled: true` | `wiki_lint.semantic_check.enabled: true` |

Entrambi i check sono **non-bloccanti**: non impediscono la progressione di TSK, US, EP,
release gate o wave dispatch. Check 4af è classificato `sperimentale` fino alla calibrazione
empirica della soglia (US-108).

Il campo frontmatter rilevante per i check è `pattern_section: "§N"`: le pagine wiki senza
questo campo sono escluse silenziosamente dalla scansione e riportate nel report come
«non scansionate».

### §25.4 — Convenzione frontmatter `pattern_section:`

Le pagine wiki che documentano una specifica sezione PATTERN.md possono dichiarare la loro
intenzione tramite il campo opzionale `pattern_section:` nel frontmatter YAML:

```yaml
---
title: "Compressione output: approccio Caveman"
pattern_section: "§20"  # sezione PATTERN.md di riferimento
updated_at: "2026-06-20"
---
```

- **Obbligatorietà**: il campo è **opzionale**. La sua assenza non è un errore di lint.
- **Scope**: adatto a pagine `wiki/syntheses/`, `wiki/concepts/`, `wiki/runbooks/` che
  documentano o sintetizzano una sezione PATTERN.md specifica.
- **Esclusione esplicita**: `wiki/entities/` e `wiki/getting-started/` non sono mappate su
  sezioni PATTERN per design (scope diverso).
- **Falsi positivi**: il mapping errato (es. `pattern_section: "§18"` su una pagina che tratta §3)
  produce falsi positivi nelle scansioni. ADR-EP031-001 raccomanda di leggere il body prima
  dell'assegnazione — mai inferire dal titolo.

### §25.5 — Confine con §10 (wiki maintenance)

| Meccanismo | Sede | Segnale |
|---|---|---|
| §10 wiki feedback loop | `/lint` Check 1-4p (existing) | Orphan link, dangling wikilink, struttura mancante |
| §25 Staleness (L1) | `/lint` Check 4ag (always-on) | Pagine non aggiornate rispetto all'età |
| §25 LLM-judge (L2) | `/semantic-drift-scan` (manuale) | Deriva semantica qualitativa vs PATTERN |
| §25 Embedding (L3) | `/semantic-drift-scan` (manuale, opt-in) | Deriva semantica metrica vs PATTERN |

§25 **non sostituisce** §10: i check strutturali (orphan, dangling) restano in §10; §25 aggiunge
un livello semantico ortogonale. Il report `/semantic-drift-scan` è side-channel di
`code_quality/reports/` — analogo a §19 CQRL — e non modifica mai le pagine wiki direttamente
(rispetta §7 r.7: append-only, no auto-rewrite).

## §26 — Runtime Contextual Suggestions (v2.24, EP-033)

### §26.1 — Problema e motivazione

La factory è storicamente pull-based: l'utente chiede (`/help`, `/query`), la factory risponde.
EP-032 ha risolto la scopribilità intenzionale con `/help`. Rimane aperto il caso più frequente
in pratica: l'utente sta eseguendo un task e non sa che esiste una capability adiacente che
migliorerebbe il risultato o preverrebbe un problema.

Esempi di gap reali:
- Un dev-agent completa un TSK `layer=fe` senza che nessuno suggerisca `/a11y` o `/ux-ui-review`.
- `/lint` trova WARNING staleness senza suggerire `/semantic-drift-scan`.
- Si apre uno sprint con TSK FE senza segnalare che `fe_correctness.visual_oracle.enabled` è spento.

### §26.2 — Architettura a tre proposte

| Proposta | Punto di iniezione | Effort | Coverage |
|---|---|---|---|
| A — Orchestrator Fase 6 | `/run` (fine wave dispatch) | S | Sprint planning, tutti i TSK in coda |
| B — dev-handoff post-exec | Fine di ogni TSK | S | Post-esecuzione per layer fe/be/db/qa/docs |
| C — Hook Stop `suggest-next.py` | Dopo ogni comando configurato | M | Bypass `/run` e `/dev` |

A+B coprono il ciclo normale (90% dei casi) con effort S + S e rischio di regressione nullo
(modifica a file esistenti). C aggiunge copertura per utenti avanzati che bypassano il ciclo.

### §26.3 — Proposta A: Orchestrator Fase 6

`Fase 6 — Capability Relevance Check` aggiunta in fondo a `orchestrator.md`. Si attiva
al termine del wave dispatch; se non ci sono TSK `status: todo` → no-op silenzioso.

**6 regole di suggerimento:**

| Condizione rilevata | Suggerimento emesso |
|---|---|
| Sprint ha TSK `layer=fe` + `fe_correctness.visual_oracle.enabled: false` | Considera `/visual-oracle` |
| Sprint ha TSK `layer=fe` + `a11y.enabled: false` | Considera `/a11y` |
| ≥3 TSK done nella settimana + `analytics.measurement.enabled: true` | Considera `/analytics` |
| ≥1 epic `status: open` senza entry premortem in `wiki/log.md` | Considera `/premortem <epic-id>` |
| `wiki/log.md` ultima entry > 30 giorni fa | Considera `/semantic-drift-scan` o `/lint` |
| Sprint ha TSK `layer=fe/be` + `code_quality.enabled: false` | Considera `/review` |

Gate: prima di emettere un suggerimento, verificare che `.claude/commands/<comando>.md` esista.
Output condizionale: la sezione `## Suggerimenti contestuali` compare solo se ≥1 suggerimento supera il gate.

### §26.4 — Proposta B: dev-handoff post-esecuzione

Sezione `## Suggerimento post-esecuzione` aggiunta in fondo a `dev-handoff.md`. Condizionale:
compare nell'output dell'handoff solo se il layer del TSK ha capability adiacenti rilevanti
non ancora eseguite sulla US corrente (deduplication via `wiki/log.md`).

| Layer | Suggerimenti (se comando installato + non già eseguito per questa US) |
|---|---|
| fe | `/a11y`, `/ux-ui-review`, `/visual-oracle` (se rispettivi flag abilitati) |
| be | `/review` (focus robustezza) |
| db | `/review`, nota backup strategy se migration DDL |
| qa | `flakiness-detection-protocol` se test asincroni |
| docs | `/lint` per verifica integrazione wiki |

Max 3 suggerimenti per handoff. Gate installazione identico a Proposta A.

### §26.5 — Proposta C: Hook Stop `suggest-next.py`

Script Python (`~90 righe`, solo stdlib) invocato dall'hook Stop di Claude Code dopo i comandi
`/dev`, `/lint`, `/run`, `/review`. Opera fuori dal contesto LLM: regole statiche, deterministico.

```
matcher: /(dev|lint|run|review)
command: python3 "$CLAUDE_PROJECT_DIR/tools/runtime/suggest-next.py" --command="$CLAUDE_COMMAND"
timeout: 5
non-bloccante: 2>/dev/null || true
```

Path canonico: `tools/runtime/suggest-next.py`. Shim legacy: `.claude/tools/suggest-next.py`.
Flag `--dry-run` per debug. Il *binding* hook è adapter-specific (Claude Code Stop);
lo script è provider-agnostic (risolve la factory via `factory.config.yaml` / `tools/`).

### §26.6 — Invarianti (nessuna nuova rispetto a §7)

- **Suggerimenti non bloccanti**: non interrompono mai il flusso operativo. Sono informativi.
- **Gate installazione**: mai suggerire capability il cui comando non esiste nella factory.
- **Output condizionale**: nessuna sezione vuota o placeholder — o c'è almeno un suggerimento rilevante, o la sezione non compare.
- **Tono non imperativo**: "Considera", "Potresti valutare" — mai "Devi", mai imperativo.
- **Backward compat totale** (R.P3): factory derivate senza le capability suggerite → tutte le check falliscono silenziosamente → comportamento identico a v2.23.

### §26.7 — Artefatti scaffoldati in factory derivate

| Artefatto | Tipo | Note |
|---|---|---|
| `orchestrator.md` | modifica | Aggiunta Fase 6 in fondo |
| `dev-handoff.md` | modifica | Aggiunta sezione post-exec in fondo |
| `tools/runtime/suggest-next.py` | nuovo (canonico) | Script Python hook-based (Proposta C) |
| `.claude/tools/suggest-next.py` | shim | Thin wrapper → `tools/runtime/suggest-next.py` |
| `.claude/settings.json` | modifica | Hook Stop → path `tools/…` |

Nessun nuovo agente. Nessun nuovo campo `factory.config.yaml` per A e B (sempre attivi una
volta scaffoldati). Proposta C può essere gated da `runtime_suggestions.hook.enabled: false`
se la factory derivata vuole disabilitarla senza modificare `settings.json`.

Fonte: EP-033 | [[runtime-contextual-suggestions]] | [[runtime-suggestions-proposal-comparison]]

---

## §27 — Prototype Generation Layer (v2.26, EP-035)

### §27.1 — Problema e motivazione

La factory copre l'intero ciclo spec → codice → validazione per il design, ma si fermava
alle spec testuali: `ui-designer` (EP-008) produce wireframe/spec in Markdown, `figma-sync`
(v2.9) legge da Figma (solo read), `visual-oracle` (EP-017) e `functional-oracle` (EP-018)
verificano artefatti esistenti. Mancava il passo generativo: nessun agente produceva
l'artefatto grafico renderizzabile (prototipo cliccabile, file di design, componente reale)
che collega la spec testuale all'artefatto percepibile dall'utente.

EP-035 chiude questo gap introducendo un layer generativo adattivo: a partire da una spec
testuale (US, TSK o intent in linguaggio naturale), il **Prototype Generation Layer** produce
un prototipo nel backend disponibile piu' adatto, con cascata di fallback che garantisce sempre
almeno un artefatto self-contained (`html` T0 — INV-1).

**Estensione semantica di §24**: EP-035 non duplica il Design Intelligence Layer (§24/EP-019)
ma lo estende semanticamente aggiungendo il layer generativo. Se `design_intelligence.art_director`
e' attivo, il prototipo eredita il tema/tipografia/spacing coordinati dall'art-director DSL. Se
spento, la generazione procede in modo standalone. Il ruolo Prototyper e' distinto da
`ui-designer` (che produce spec testuali): il Prototyper consuma la spec e produce l'artefatto
renderizzabile, senza self-eval (INV-4) e senza riscrivere la spec sorgente (INV-3).

### §27.2 — Artefatti scaffoldati in factory derivate

| Artefatto | Tipo | Analogia con esistente |
|---|---|---|
| `agents/prototype-generator.md` | agente Prototyper (opt-in, gated) | `figma-sync`, `ui-designer` |
| `skills/prototype-generation-protocol.md` | skill 5 fasi, provider-agnostic | `publisher-protocol` (v2.10) |
| `skills/backend-resolver.md` | skill cascata detection + degradazione | `branch-resolver` (EP-034), `stack-detector` |
| `skills/html-prototype-mapping.md` | skill mapping provider-specific html (T0) | `github-mapping` (v2.10) |
| `skills/react-mapping.md` | skill mapping provider-specific React (T1) | `github-mapping` |
| `skills/figma-mapping.md` | skill mapping provider-specific Figma (T2) | `github-mapping` |
| `skills/penpot-mapping.md` | skill mapping provider-specific Penpot (T3) | `github-mapping` |
| `commands/prototype.md` | `/prototype <US-id\|TSK-id\|"intent">` | `/kanban-publish`, `/dev` |
| `commands/prototype-status.md` | `/prototype-status` — backend risolto + disponibilita' | `/vcs-status` (EP-034) |
| `factory.config.yaml` | blocco `prototyping:` (master switch + backends) | blocchi `compression:`, `code_quality:` |

Il pattern architetturale e' **provider-agnostic + provider-specific**: `prototype-generation-protocol`
non conosce Figma o Penpot; aggiungere un nuovo backend richiede solo una skill `*-mapping` +
una voce nel `fallback_chain`, senza modificare il protocollo core. Analogo al pattern
`publisher-protocol` / `github-mapping` (v2.10).

### §27.3 — Configurazione (blocco `prototyping:`)

Blocco verbatim da `factory.config.yaml` (righe 890–944):

```yaml
prototyping:
  enabled: false                    # master switch EP-035 (R.P3 default off)
  backend: auto                     # auto | html | react | figma | penpot
  fallback_chain: [figma, penpot, react, html]  # cascata di fallback (html = terminale garantito INV-1)
  degrade_policy: notify            # notify (default) | strict (STOP+gate umano se preferito UNAVAILABLE)
  fidelity: interactive             # static | interactive (default) | animated
  design_source: auto               # auto (cerca design-spec.md) | <path> | none
  art_director: inherit             # inherit | on | off (EP-019 DSL opt-in)
  output_path: "output/prototypes"  # directory root artefatti generati
  oracle_handoff: true              # Fase 4: suggerisce oracle/reviewer appropriato per backend
  scheduler_domain: prototype       # dominio scheduler (prototype, opt-in default false)
  backends:
    html:                           # T0 — fallback terminale garantito (INV-1), zero prerequisiti
      css_strategy: tailwind-cdn    # tailwind-cdn (default) | inline | vanilla
      single_file: true             # INVARIANTE INV-6 — non overridabile; un solo file HTML self-contained
    react:                          # T1 — production-ready (richiede code_path FE)
      component_lib: shadcn         # shadcn (default) | radix | mui | custom
      storybook: true               # true (default) → genera storie Storybook per ogni stato
      target: null                  # null = output_path; path = directory nel code_path target
    figma:                          # T2 — alta fedelta' (richiede MCP figma autenticato)
      mcp_server: "figma"           # nome MCP server Figma (deve essere installato e autenticato)
      file_key: ""                  # chiave file Figma target; "" → crea nuovo file
    penpot:                         # T3 — alta fedelta' open-source (richiede MCP penpot)
      mcp_server: "penpot"          # nome MCP server Penpot (deve essere installato e autenticato)
      instance_url: ""              # URL istanza Penpot (es. https://design.penpot.app)
```

Note di configurazione:

- `enabled: false` e' l'unico campo che attiva la capability (R.P3 opt-in). Tutti gli altri
  campi hanno default funzionanti — basta impostare `enabled: true` per il comportamento base.
- `backend: auto` attiva il `backend-resolver` che proba (ASSE 1: MCP figma/penpot;
  ASSE 2: stack-detector per react) e sceglie il backend piu' fedele disponibile.
- `degrade_policy: notify` (default) — il resolver degrada silenziosamente con marker
  `BACKEND_DEGRADED` in chat e log. `strict` => STOP + gate umano.
- `art_director: inherit` lega la capability a `design_intelligence.art_director` di §24;
  impostare `on`/`off` per override locale.
- `oracle_handoff: true` abilita la Fase 4 del protocollo: al termine della generazione,
  l'agente suggerisce il reviewer piu' adatto (visual-oracle, functional-oracle, ux-ui-review,
  a11y) in base al backend usato e alla fidelity prodotta.
- Per factory con `code_paths: []` vuoto (es. repo meta-framework reflexivo), il backend
  `react` (T1) risulta UNAVAILABLE (probe ASSE 2 senza target FE) e il resolver degrada a
  `html` (T0). Comportamento atteso e documentato.

### §27.4 — Invarianti locali (INV-1..INV-6)

Le seguenti invarianti si applicano alla capability EP-035 in tutte le factory derivate
che la attivano. Non fanno parte delle 18 invarianti globali §7 (invariate).

- **INV-1**: backend `html` sempre disponibile come fallback terminale — la capability non
  puo' hard-fail; se tutti i backend superiori falliscono, viene prodotto sempre un file
  HTML self-contained.
- **INV-2**: mai bloccare su MCP non autenticato — il resolver degrada con marker
  `BACKEND_DEGRADED` e prosegue (salvo `degrade_policy: strict` che chiede gate umano
  esplicito).
- **INV-3**: `prototype-generator` e' read-only verso la spec sorgente — non riscrive
  i file prodotti da `ui-designer` o da qualunque altro agente upstream.
- **INV-4**: no self-eval — il generatore non giudica il proprio output; la validazione
  e' delegata interamente agli agenti oracle/reviewer/a11y esistenti (analogo ad ADR-063
  anti-fabbricazione).
- **INV-5**: default off (R.P3) — a `prototyping.enabled: false` la factory v2.26 e'
  identica alla v2.25 (backward compat totale; nessun nuovo agente scaffoldato, nessun
  comando disponibile).
- **INV-6**: `single_file: true` per backend `html` e' un'invariante di self-containment
  non overridabile — un solo file HTML con tutto inline (unica eccezione ammessa:
  Tailwind CDN se `css_strategy: tailwind-cdn`), apribile offline senza server.

### §27.5 — ADR-EP035 accettati

Tutti i sei ADR EP-035 sono accettati (GO). ADR-EP035-001 (cascata backend adattiva) e'
l'ADR fondante: stabilisce che la capability e' multi-backend con fallback, non single-backend
hard-coded.

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP035-001** | Cascata backend adattiva vs singolo backend hard-coded | GO cascata adattiva — `backend-resolver` + `fallback_chain` configurable |
| ADR-EP035-002 | `html` single-file come fallback terminale garantito | GO — INV-1 + INV-6 |
| ADR-EP035-003 | Riuso pattern publisher (protocol agnostic + mapping specifico) | GO riuso — `prototype-generation-protocol` + `*-mapping` skills |
| ADR-EP035-004 | §27 nuova sezione PATTERN vs estendere §24 | GO sezione nuova — estende semanticamente §24 senza duplicarlo |
| ADR-EP035-005 | `degrade_policy` default `notify` vs `strict` | GO `notify` — minor friction, massima disponibilita' |
| ADR-EP035-006 | Figma vs Penpot primo nel `fallback_chain` di default | GO Figma prima (adozione maggiore); Penpot per ambienti self-contained-first |

### §27.6 — Integrazione con capability esistenti

EP-035 si integra con le capability esistenti senza duplicarle:

- **§24 Design Intelligence Layer (EP-019)**: se `design_intelligence.art_director: true`,
  il Prototyper eredita il tema/tipografia/spacing coordinati dall'art-director DSL (`art_director: inherit`).
  EP-035 e' l'estensione generativa di §24: §24 produce la spec di design, §27 produce
  l'artefatto renderizzabile da quella spec.
- **§26 Runtime Contextual Suggestions (EP-033)**: la Fase 6 dell'orchestrator include
  una regola push — "TSK layer=fe con spec testuale ma senza prototipo associato → considera
  `/prototype`". Handoff post-exec del dev-handoff segnala lo stesso.
- **visual-oracle (EP-017)**: backend `figma` e `penpot` (alta fedelta') suggeriscono in
  Fase 4 il visual-oracle come validatore naturale del prototipo prodotto.
- **functional-oracle (EP-018)**: backend `react` (T1) suggerisce in Fase 4 il
  functional-oracle per la validazione dell'interattivita' dei componenti generati.
- **a11y (EP-012/v2.18)**: `oracle_handoff: true` include sempre un suggerimento a11y
  in Fase 4 indipendentemente dal backend, in quanto il prototipo e' un artefatto UI
  consumabile dall'utente finale.
- **Scheduler (v2.11)**: nuovo dominio `prototype` configurabile in `scheduler.domains`
  (opt-in/out come tutti gli altri domini — `develop`, `lint`, `review`, ecc.). Default
  opt-in quando `prototyping.enabled: true`.
- **figma-sync (v2.9)**: a livello di sistema l'integrazione diventa bidirezionale —
  `figma-sync` legge da Figma (read), `prototype-generator` backend `figma` scrive su
  Figma (write via MCP) — round-trip design completo.

## §28 — Tavola Rotonda (modalita' multi-agente collaborativa)
<!-- profiles: full -->

### §28.1 — Scopo e quando usarla

La Tavola Rotonda e' una modalita' operativa **opt-in** (EP-039, v2.27) per la
risoluzione collaborativa di problemi **genuinamente complessi e multi-dominio** che
richiedono la sintesi di prospettive eterogenee — architettura, sicurezza, UX, delivery —
impossibile da ottenere con un singolo agente o con una pipeline a layer fissi.

**Usare la Tavola Rotonda quando:**

- Il problema e' multi-dominio e la soluzione richiede la sintesi di ≥2 aree di competenza
  (es. scelta architetturale con impatto su sicurezza + UX + costi operativi).
- Il rischio di anchoring e groupthink e' alto — una pipeline lineare non produce
  controllo incrociato, i rischi emergerebbero in produzione invece che prima.
- La decisione e' irreversibile o molto costosa da cambiare in seguito.
- Il problema ha ≥2 alternative concrete non ovviamente superiori l'una all'altra.

**Non usare la Tavola Rotonda quando:**

- La risposta e' lookup (wiki, ADR gia' accettato, regola codificata): usa `/query`.
- Il problema ha un solo esperto di dominio rilevante: usa il singolo dev-agent.
- Il costo di una sessione (5-15x un task normale) e' sproporzionato all'impatto della
  decisione.

Vedi il decision tree completo: [`wiki/runbooks/tavola-rotonda.md`](wiki/runbooks/tavola-rotonda.md).

### §28.2 — Componenti

| Componente | File | Responsabilita' |
|---|---|---|
| **Sessione principale** | `.claude/commands/tavola-rotonda.md` | Lancia i partecipanti con il tool Agent (Fase 1 isolata in parallelo, Fase 2 Critico per primo), li trascrive verbatim con l'agent id, registra i lanci nel frontmatter e verifica a fine sessione con `tools/tavola-rotonda/verifica-lanci.py --registro`. Non esprime opinioni di merito (ADR-EP073-001) |
| **Moderatore** | `.claude/agents/tavola-rotonda-moderatore.md` | Invocato come subagente nelle modalità `setup` (Fase 0), `convergenza` (Fase 3) e `sintesi` (Fase 4, aggregatore); non lancia altri agenti (da Claude Code 2.1.289 un subagente non può farlo); non esprime opinioni di merito in Fasi 1-3 |
| **Partecipanti** | qualunque agente in `.claude/agents/<slug>.md` | Producono posizioni indipendenti in Fase 1 e interventi argomentati in Fase 2; comunicano solo tramite la lavagna (no messaggi diretti) |
| **Critico** | un agente della lista partecipanti (obbligatorio, R.TR2) | Mandato esplicito di dissenso attivo: identifica assunzioni fragili, scenari di failure, domande dirompenti; ha priorita' di intervento in Fase 2; non convergere per default |
| **Blackboard** | `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` | File strutturato con sezioni `## Posizioni Fase 1` / `## Accordi (congelati)` / `## Punti Aperti` / `## Sintesi`; formato normativo ADR-EP039-001; un solo scrittore per volta (sessione principale o moderatore), partecipanti mai; ogni intervento porta l'agent id del lancio |
| **Registro decisioni** | blackboard completo di `## Sintesi` | Artefatto persistente della sessione in `wiki/decisions/`; sempre prodotto in Fase 4 (R.TR1 — non opt-in) |

### §28.3 — Protocollo a 5 fasi (sintesi normativa)

Il protocollo completo e' definito in `.claude/skills/tavola-rotonda-protocol.md`.
Le fasi sono sequenziali; il fallimento di un passo blocca la fase.

| Fase | Nome | Output chiave |
|---|---|---|
| **Fase 0** | Setup | Blackboard inizializzato, topic riformulato, criteri di successo, partecipanti verificati, Critico assegnato, budget confermato |
| **Fase 1** | Posizioni iniziali indipendenti | Ogni agente produce una posizione **in isolamento** (R.TR3) — nessun agente vede le posizioni degli altri prima che tutti abbiano risposto; posizioni trascritte verbatim nel blackboard |
| **Fase 2** | Confronto | Il Critico interviene per primo; gli altri agenti producono critiche, integrazioni, rischi sulle proposte altrui; tutto il traffico passa dalla lavagna |
| **Fase 3** | Convergenza | Sintesi progressiva: nuovi accordi congelati in `## Accordi (congelati)`; punti residui in `## Punti Aperti`; condizioni di stop valutate in ordine: consenso totale → max_round → budget esaurito → stallo (≥2 round senza nuovi accordi) |
| **Fase 4** | Sintesi | Aggregatore produce la sintesi: Soluzione + Motivazione + Dissensi registrati + Criteri di successo verificati; registro decisioni scritto nel blackboard; entry aggiunta a `wiki/log.md` |

**Condizioni di stop (Fase 3, ordine di priorita'):**

1. `## Punti Aperti` vuoto → convergenza completa
2. `round_corrente ≥ max_round` → stop forzato per tetto
3. Costo sessione > `budget.max_cost_usd` → stop forzato per budget
4. Stallo: 2 round consecutivi senza nuovi accordi → stop forzato con annotazione `[STALLO]`

In tutti i casi di stop forzato la Fase 4 produce comunque la `## Sintesi` (R.TR1).

### §28.4 — Invarianti R.TR1-R.TR4 (non overridabili)

Le seguenti quattro invarianti non possono essere modificate da alcun parametro,
prompt o istruzione runtime in nessuna factory che attivi la Tavola Rotonda.

**R.TR1 — Registro decisioni obbligatorio**
Nessuna sessione Tavola Rotonda termina senza il registro decisioni.
Il moderatore non puo' dichiarare `stato: terminata` senza aver scritto la sezione
`## Sintesi` nel file `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md`
e senza aver aggiunto la entry in `wiki/log.md`. Questo vale anche in caso di
stop forzato (budget esaurito, stallo, max_round raggiunto).

**R.TR2 — `budget.max_cost_usd` obbligatorio**
Nessuna sessione inizia senza un valore numerico esplicito per `budget.max_cost_usd`.
Assenza, valore nullo, `~`, `0` o stringa vuota → STOP immediato con messaggio esplicito
prima di qualsiasi fase. Nessun default silenzioso ammesso.
Fonte primaria: flag CLI `--budget=<USD>`; fonte secondaria: `tavola_rotonda.budget.max_cost_usd`
in `factory.config.yaml`. Costo tipico per sessione: 5-15x un task normale.

**R.TR3 — Fase 1 in isolamento**
Nessun agente vede le posizioni degli altri durante la Fase 1. Ogni agente riceve
esclusivamente: topic riformulato + criteri di successo + proprio ruolo. Il moderatore
NON condivide il blackboard ne' le posizioni parziali prima che tutti i partecipanti
abbiano risposto. Violazione → la sessione DEVE essere riavviata da Fase 0; non esiste
recupero parziale. Questo e' il meccanismo primario di prevenzione dell'anchoring e
del groupthink.

**R.TR4 — Il moderatore non decide nel merito nelle Fasi 1-3**
Nelle Fasi 1-3 il moderatore agisce esclusivamente su processo, turni e trascrizione
verbatim. Non filtra, non commenta, non valuta il merito delle posizioni. Il role switch
ad aggregatore avviene solo in Fase 4 (sintesi). La trascrizione verbatim degli
interventi nella lavagna e' parte di questa invariante: il riassunto introduce distorsione.

### §28.5 — Configurazione

La capability e' controllata dal blocco `tavola_rotonda:` in `factory.config.yaml` (§13).
Default `enabled: false` — backward compat totale con v2.26 (opt-in R.P3).

```yaml
# Tavola Rotonda — modalita' multi-agente collaborativa (EP-039, PATTERN §28)
tavola_rotonda:
  enabled: false                    # default off — backward compat totale

  partecipanti: []                  # es. [be-dev, lead-architect, qa-dev]

  critico:
    enabled: true                   # sempre on quando abilitata
    mode: dedicated                 # dedicated | rotation

  max_round: 4                      # obbligatorio — nessuna sessione illimitata

  stop_su_consenso: true
  definizione_consenso: unanimity   # unanimity | supermajority | no_blocking_objection

  meccanismo_decisione: ibrido      # sintesi_moderatore | voto | voto_pesato | consenso | ibrido

  budget:
    max_cost_usd: ~                 # OBBLIGATORIO se enabled: true — fail se assente (R.TR2)
    max_tokens: ~                   # opzionale
    max_latency_s: ~                # opzionale

  topologia: lavagna                # lavagna (default, hub-and-spoke) | grafo_completo (sconsigliato)
  sintesi_progressiva: true         # riassunto accordi/punti-aperti a ogni round
```

Note di configurazione:

- `enabled: false` e' l'unico campo che attiva la capability. A flag spento la factory
  v2.27 e' identica alla v2.26 (backward compat totale; agente e skill non invocabili
  dal runner automatico, comando `/tavola-rotonda` disponibile ma non auto-attivato).
- `budget.max_cost_usd: ~` e' il valore di configurazione permanente raccomandata.
  Se assente, va fornito obbligatoriamente a ogni sessione via `--budget=<USD>` (R.TR2).
- `partecipanti: []` — selezione esplicita v1 (MVP). La selezione automatica per dominio
  del topic (`partecipanti: auto`) e' esclusa dall'MVP di EP-039; prevista per v2.
- `critico.mode: rotation` — il ruolo Critico ruota tra i partecipanti nei round
  successivi al primo (utile per sessioni con ≥3 agenti, evita la stanchezza del Critico).
- `topologia: grafo_completo` e' sconsigliato in v1: la comunicazione diretta tra agenti
  (senza moderatore) produce contesti O(n×m) e bypassa le invarianti di trascrizione
  verbatim. Usare solo con piena consapevolezza delle implicazioni.

### §28.6 — File chiave

| Tipo | Path |
|---|---|
| **Agente moderatore** | `.claude/agents/tavola-rotonda-moderatore.md` |
| **Skill protocollo** | `.claude/skills/tavola-rotonda-protocol.md` |
| **Comando** | `.claude/commands/tavola-rotonda.md` |
| **Runbook** | `wiki/runbooks/tavola-rotonda.md` |
| **ADR normativo blackboard** | `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md` |
| **Concept tavola-rotonda** | `wiki/concepts/tavola-rotonda.md` |
| **Concept blackboard-architecture** | `wiki/concepts/blackboard-architecture.md` |
| **Concept multi-agent-debate** | `wiki/concepts/multi-agent-debate.md` |
| **Registro decisioni (runtime)** | `wiki/decisions/tavola-rotonda-<session-id>-<YYYY-MM-DD>.md` |

### §28.7 — Integrazione con capability esistenti

EP-039 si integra con le capability esistenti senza duplicarle:

- **§18 Parallel Scheduler (v2.11)**: la Tavola Rotonda non usa il DAG scheduler per le
  sessioni — la sessione principale che esegue `/tavola-rotonda` gestisce direttamente il
  lancio sequenziale/parallelo dei partecipanti con il tool Agent (Fase 1 parallelo, Fase 2
  Critico-prima poi parallelo; ADR-EP073-001: fino a Claude Code 2.1.270 lo faceva il moderatore).
  Il dominio `tavola-rotonda` e' escluso dallo scheduler automatico; la sessione e'
  invocata sempre esplicitamente.
- **§22 Release Governance (v2.19)**: la capability e' gated da benchmark pre-release
  (TSK-294, verdict `pass`) prima del bump di versione. Questo e' il modello di release
  validation applicato anche a §28: nessun rilascio senza evidenza empirica.
- **§24 Design Intelligence Layer (EP-019)**: la Tavola Rotonda puo' essere usata per
  le decisioni di design complesse che l'art-director non riesce a risolvere unilateralmente.
  Il registro decisioni `wiki/decisions/` diventa input per gli ADR successivi.
- **Token Ledger (EP-022)**: il costo di ogni sessione e' visibile inline via
  `show-session-tokens.py`. Il `budget.max_cost_usd` e' il guardrail di spesa; il Token
  Ledger e' lo strumento di osservabilita' del consumo reale durante la sessione.
- **wiki/decisions/ (R.TR1)**: il blackboard completato e' il registro decisioni naturale
  della factory — stesso layer `wiki/decisions/` usato da altri meccanismi di governance.
  La query `/query` lo indicizza automaticamente come fonte L2.

### §28.8 — ADR-EP039-001 accettato

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP039-001** | Formato normativo del blackboard | GO — file strutturato in `wiki/decisions/` con 9 campi frontmatter obbligatori + 3 sezioni (`## Posizioni Fase 1`, `## Accordi (congelati)`, `## Punti Aperti`) + `## Sintesi` aggiunta in Fase 4; single-writer (solo moderatore, R.TR4); UUID v4 come `session_id` |
| **ADR-EP073-001** | Tavola Rotonda: partecipanti lanciati dalla sessione principale | ACCEPTED (2026-10-08, dalla derivata portale-servizi-factory dove e' in uso dal 2026-10-07) — da Claude Code 2.1.289 un subagente non lancia altri agenti: la sessione principale lancia e trascrive i partecipanti con l'agent id, il moderatore resta per setup, convergenza e sintesi; verifica dei lanci dal registro con `tools/tavola-rotonda/verifica-lanci.py --registro` |

Fonte: EP-035 | [[prototype-generation-capability]] | [[ep-035-prototype-generation-integration]]

---

## §29 — Factory Scalability Patterns (v2.27, factory-optimization-2026-07-07)

Questa sezione documenta i pattern architetturali introdotti dalla sessione di ottimizzazione
della factory (2026-07-07) che risolvono tre problemi di scalabilità identificati:

1. **Orchestrator troppo grasso** — ogni nuova EP aggiungeva logica di dispatch inline.
2. **Routing hardcoded** — aggiungere un agente richiedeva modifiche in più file.
3. **Tracciabilità wave limitata** — WAVE_ID generato ma non propagato al log umano.

### §29.1 — Thin Orchestrator + Fat Dispatch Policy

**Pattern**: estrarre tutta la logica di dispatch condizionale dall'orchestrator in una
skill dedicata `dispatch-policy.md`. L'orchestrator diventa un thin dispatcher che
invoca la skill senza replicarne il contenuto.

**Benefici**:
- Aggiungere una nuova EP di routing richiede modificare **solo** `dispatch-policy.md`.
- L'orchestrator resta ≤ 100 righe — comprensibile a colpo d'occhio.
- Single-writer chiaro: ogni sezione di `dispatch-policy` è firmata dalla EP che la introduce.

**File chiave**:
- `.claude/skills/dispatch-policy.md` — 8 sezioni numerate, una per capability di dispatch
- `.claude/agents/orchestrator.md` — thin (< 100 righe), punta a `dispatch-policy` §1-§7

**Invariante**: ogni nuova EP che introduce logica di routing DEVE aggiungere una sezione
numerata a `dispatch-policy.md` e NON espandere `orchestrator.md`.

### §29.2 — Capability Advertisement

**Pattern**: ogni agente dichiara nel frontmatter YAML un blocco `capabilities: [...]`
con slug descrittivi. Il blocco è opzionale e additivo — backward compat totale.

```yaml
capabilities:
  - <capability-slug>   # commento opzionale
```

**Benefici**:
- Tool e check di lint possono derivare "chi fa cosa" da YAML senza leggere il body testuale.
- `lint-checks` Check 4ai usa la lista per validare tool/skill/command reference.
- Routing futuro può essere basato su capability match invece di agent-name hardcoding.
- Il registro slug in `dispatch-policy.md §8` è la single source of truth del vocabolario.

**File chiave**:
- `.claude/agents/*.md` — tutti i 27 agenti dichiarano `capabilities:`
- `.claude/skills/dispatch-policy.md §8` — registry completo degli slug per layer
- `.claude/skills/lint-checks.md Check 4ai` — validator che usa tool/skill/command reference

**Invariante**: `capabilities:` è documentativo, non autorizzativo. Non configura permessi
né sostituisce le regole di scope nei body degli agenti.

### §29.3 — WAVE_ID Log Propagation

**Pattern**: il WAVE_ID (già generato dal parallel scheduler negli analytics events) viene
propagato anche nel log umano `wiki/log.md` via il template `wave` di `wiki-log-entry.md`.

**Formato WAVE_ID**: `W-<sprint>-<level>-<YYYYMMDD-HHMMSS>`

**Benefici**:
- Correlazione retrospettiva costo/tempo per wave (join WAVE_ID tra log.md e analytics events).
- Auditabilità delle wave: ogni entry di log wave ha un ID univoco.
- Il template `develop` del dev-agent include `wave: <wave_id>` opzionale per tracciare
  il TSK alla wave che lo ha generato.

**File chiave**:
- `.claude/skills/wiki-log-entry.md` — template `wave` e `develop` con WAVE_ID
- `.claude/skills/parallel-scheduling.md` — già genera `wave_id` negli analytics events

### §29.4 — Agent Infrastructure Check (Check 4ai)

**Pattern**: il lint verifica che ogni agente referenzi solo skill/command/tool esistenti.
WARNING-only, always-on, zero API cost (pure file existence check).

**File chiave**:
- `.claude/skills/lint-checks.md Check 4ai` — tre sotto-check (tool whitelist, skill reference, command reference)

### §29.5 — Invarianti globali

Questi pattern rispettano e non violano nessuna invariante §7 preesistente:
- `capabilities:` è additive-only: zero rimozioni da agent body, zero nuovi ERROR lint.
- `dispatch-policy.md` è read-only per l'orchestrator: single-committer invariant preservata.
- WAVE_ID nel log è additivo: log.md rimane append-only (R.S1 preservata).
- Check 4ai è WARNING-only: non blocca `/lint`, non è `heal-eligible` (R.P3 preservata).

---

## §30 — Voice Channel Layer (EP-041, v2.28, opt-in)
<!-- profiles: full -->

> Canale di interazione vocale (STT/TTS) opt-in per la factory multi-agente.
> Il canale vocale non modifica la factory ma si mette **davanti al runtime**,
> trasformandosi in un nuovo front-end di I/O per un sistema gia' esistente.

### §30.1 — Principio cardine: canale asimmetrico

Il Voice Channel Layer introduce un principio architetturale che lo distingue da ogni
altra capability del framework: e' un **front-end di I/O**, non un layer della pipeline.

- La factory (orchestratore, agenti, skill, config) e' **invariata**: nessun file
  all'interno di `.claude/` viene modificato da EP-041.
- Il modulo `voice/` si posiziona **davanti** al runtime LLM esistente, avvolgendolo
  tramite un'interfaccia astratta (`FactoryRuntime`) senza conoscerne i dettagli.
- Il canale e' **asimmetrico**: l'input vocale viene trascritto in testo prima di
  entrare nel runtime; l'output del runtime viene filtrato prima di essere sintetizzato
  in voce. Non esiste un percorso di codice che colleghi direttamente l'audio I/O agli
  agenti.
- Il principio non negoziabile: **artefatti mai al TTS**. Solo i tipi `SpokenSummary`,
  `Acknowledgment` e `Question` raggiungono il sintetizzatore vocale. `Artifact.content`
  (codice, diff, log, tabelle) e' instradato esclusivamente al canale visivo (stdout
  strutturato in MVP). L'invariante e' realizzata con un unico choke point in
  `voice/core/router.py` (allowlist, non denylist) e coperta da test automatizzato.

### §30.2 — Architettura: modulo voice/ esterno al meta-framework

Il modulo `voice/` vive alla radice del repo, fuori da `.claude/`. Questa posizione
e' deliberata: il canale vocale e' un front-end applicativo, non un componente del
meta-framework di orchestrazione.

```
voice/
├── audio/          # I/O audio real-time (PortAudio)
│   ├── capture.py       stream input, callback → coda thread-safe
│   ├── playback.py      stream output, .abort()/.stop() per barge-in
│   ├── devices.py       enumerazione e selezione device audio
│   └── aec.py           AECProcessor (Fase 4) + fallback chain NoOp
├── vad/            # Voice Activity Detection + endpointing
│   ├── base.py          interfaccia astratta VAD
│   ├── webrtc_vad.py    VAD frame-based, leggero (webrtcvad)
│   ├── silero_vad.py    VAD neurale (silero-vad + torch)
│   └── endpointing.py   rilevamento fine-turno su silenzio 500–800 ms
├── stt/            # Speech-to-Text
│   ├── base.py          interfaccia astratta STT
│   └── faster_whisper_stt.py  motore STT locale (faster-whisper)
├── tts/            # Text-to-Speech
│   ├── base.py          interfaccia astratta TTS
│   ├── piper_tts.py     motore TTS neurale locale (piper-tts)
│   └── sentence_splitter.py  split frase-per-frase per latenza ridotta
├── runtime/        # Adattatori FactoryRuntime (unico contatto con il runtime LLM)
│   ├── base.py                interfaccia astratta + tassonomia eventi
│   └── custom_loop_adapter.py Opzione B — loop LLM+tool custom (ADR-EP041-001)
├── core/           # Orchestrazione voice pipeline
│   ├── state_machine.py   macchina a stati 5 stati + INTERRUZIONE (barge-in)
│   ├── router.py          choke point allowlist TTS-safe
│   ├── cancellation.py    token/segnali di cancel propagabili (barge-in Fase 3)
│   └── session.py         contesto turno: session_id, codice
├── app.py          # Entry point CLI (python -m voice.app)
└── config.py       # Lettura sezione voice_channel: da factory.config.yaml
```

### §30.3 — Componenti

| Componente | File | Ruolo |
|---|---|---|
| **VoiceConfig** | `voice/config.py` | Lettura e validazione `voice_channel:` da `factory.config.yaml` |
| **AudioCapture** | `voice/audio/capture.py` | Stream input PortAudio; callback → coda thread-safe; push-to-talk gate |
| **AudioPlayback** | `voice/audio/playback.py` | Stream output; `.abort()` per barge-in senza thread appesi |
| **VAD + Endpointer** | `voice/vad/` | Rilevamento voce (webrtcvad o silero) + fine-turno su silenzio |
| **STT** | `voice/stt/faster_whisper_stt.py` | Trascrizione audio→testo via faster-whisper (locale, CTranslate2) |
| **TTS** | `voice/tts/piper_tts.py` | Sintesi testo→audio via piper-tts (neurale locale, voci italiane) |
| **FactoryRuntime** | `voice/runtime/base.py` | Interfaccia astratta: `submit()` + `cancel()` + `aclose()` |
| **CustomLoopAdapter** | `voice/runtime/custom_loop_adapter.py` | Implementazione concreta Opzione B (loop LLM+tool custom) |
| **VoiceStateMachine** | `voice/core/state_machine.py` | FSM 5 stati; gestisce concorrenza callback real-time ↔ task asyncio |
| **EventRouter** | `voice/core/router.py` | Choke point allowlist TTS; `Artifact` mai alla coda TTS |
| **BargeinDetector** | `voice/core/cancellation.py` | Token cancel propagabili; `cancel()` idempotente (Fase 3) |
| **AECProcessor** | `voice/audio/aec.py` | Fallback chain WebRTCAPM → SpeexDSP → NoOp (Fase 4 opt-in) |
| **App** | `voice/app.py` | Entry point CLI; costruisce la pipeline e avvia il loop asyncio |

### §30.4 — Macchina a stati

```
  (push-to-talk / VAD trigger)        (rilascio tasto / endpointing silenzio)
             │                                       │
             ▼                                       ▼
  ┌──────────────┐    ┌──────────┐      ┌──────────────┐      ┌───────────────┐
  │ IDLE/ASCOLTO │──▶ │ CATTURA  │ ───▶ │ TRASCRIZIONE │ ───▶ │  ELABORAZIONE │
  └──────────────┘    │  (mic)   │      │    (STT)     │      │  (runtime LLM │
        ▲             └──────────┘      └──────────────┘      │    + tool)    │
        │                  ▲                                   └───────┬───────┘
        │ Done / Error     │                                          │ SpokenSummary
        │                  │ barge-in (Fase 3):                       │ (router → coda TTS)
        │                  │ cancel() + flush buffer TTS              │
        │             ┌──────────┐                                    │
        └─────────────┤ PARLATO  │◀───────────────────────────────────┘
                      │  (TTS)   │
                      └──────────┘
```

Transizioni chiave:

| Da → A | Trigger |
|---|---|
| IDLE → CATTURA | push-to-talk (Fase 1) oppure trigger VAD hands-free (Fase 2+) |
| CATTURA → TRASCRIZIONE | rilascio tasto (Fase 1) oppure endpointing su silenzio 500–800 ms (Fase 2+) |
| TRASCRIZIONE → ELABORAZIONE | STT restituisce testo → `FactoryRuntime.submit(text, session_id)` |
| ELABORAZIONE → PARLATO | runtime emette `SpokenSummary`; router → coda TTS |
| PARLATO → IDLE | evento `Done` / `Error` chiude il turno |
| PARLATO → CATTURA | **barge-in** (Fase 3 only): VAD rileva voce → `cancel()` + flush |

Concorrenza: i callback audio PortAudio girano su thread real-time e non bloccano mai;
STT, runtime LLM e TTS sono task `asyncio` o thread executor. La comunicazione
thread ↔ event loop usa `queue.Queue` o `loop.call_soon_threadsafe`.

### §30.5 — Invariante: artefatti mai al TTS

Il vincolo e' realizzato con una **allowlist** nel router (non una denylist):

1. Solo gli eventi `SpokenSummary`, `Acknowledgment` e `Question` hanno il campo
   `.text` accodato alla coda TTS.
2. `Artifact.content` e' instradato esclusivamente al canale visivo; non esiste percorso
   di codice che lo passi a `piper_tts`. **L'implementazione concreta di quel canale
   dipende dall'adapter** — nel MVP era `stdout` strutturato — e l'invariante vale su
   qualunque la realizzi: il filtro resta uno, mai una seconda copia della regola.
3. Se un tipo non-allowlist arriva per errore alla coda TTS, il router lo **scarta**
   e logga a livello WARNING — degradazione sicura, mai pronuncia dell'artefatto.
4. L'invariante e' coperta da test automatizzato: data una sequenza mista di eventi,
   la coda TTS contiene esattamente i soli testi parlati; il canale visivo i soli
   artefatti.

### §30.6 — Config gate

```yaml
# Voice Channel (EP-041, opt-in, PATTERN §30)
voice_channel:
  enabled: false                # opt-in esplicito obbligatorio
  phase: 1                      # fase roadmap attiva (1..4)
  log_level: INFO               # DEBUG|INFO|WARNING
  stt:
    provider: faster-whisper    # motore STT locale
    model: base                 # tiny|base|small|medium|large
    language: it
  tts:
    provider: piper-tts         # motore TTS locale
    voice: it_IT-riccardo-medium
  audio:
    input_device: null          # null = default di sistema
    output_device: null
  vad:                          # Fase 2+ (hands-free/endpointing)
    provider: silero-vad        # silero-vad | webrtcvad
    threshold: 0.5
    endpoint_silence_ms: 700
  barge_in:                     # Fase 3 (US-144) — opt-in separato
    enabled: false
    vad_threshold: 0.7
  aec:                          # Fase 4 (US-147) — opt-in separato
    enabled: false
    provider: webrtc-apm        # webrtc-apm | speexdsp | noisereduce
```

`voice_channel.enabled: false` (default) — factory identica a v2.27; nessun import
avviene, nessuna dipendenza audio/STT/TTS viene caricata (integrazione no-op US-146 AC2).

`voice_channel.enabled: true` — avvia la pipeline vocale con `python -m voice.app`.
Prerequisito: `pip install -e ".[voice]"` + voce piper scaricata (runbook §3).

### §30.7 — Fasi implementative (roadmap a 4 fasi)

| Fase | Sprint | Contenuto | Stato |
|---|---|---|---|
| **Fase 1** — Push-to-talk MVP | SP41 | Ciclo end-to-end: cattura PTT → STT → LLM → TTS. Nessun VAD attivo; sequenziale. | DONE (US-143, US-145, US-146) |
| **Fase 3** — Barge-in | SP42 | Full-duplex: RMS pre-gate + VAD debounce; `cancel()` propagato; latenza interruzione < 300 ms. | DONE (US-144) |
| **Fase 4** — AEC opzionale | SP42 | Cancellazione eco altoparlanti: fallback chain WebRTCAPM → SpeexDSP → NoOp. Cuffie raccomandati senza AEC. | DONE (US-147) |
| **Fase 2** — VAD hands-free | roadmap | Trigger automatico via VAD (senza tasto push-to-talk); endpointing su silenzio. | roadmap |

> Nota: le fasi sono state consegnate in ordine 1 → 3 → 4 (Fase 2 posticipata a roadmap
> perche' Fase 3 barge-in era prerequisito piu' critico per il test dell'architettura
> concorrente).

### §30.8 — Dipendenze Python (opt-in)

Le dipendenze vocali non vengono mai importate quando `voice_channel.enabled: false`.
Installazione tramite extra group: `pip install -e ".[voice]"`.

| Package | Ruolo | Fase |
|---|---|---|
| `sounddevice` (PortAudio) | cattura + playback audio real-time | F1 |
| `faster-whisper` | STT (Whisper via CTranslate2, locale) | F1 |
| `piper-tts` | TTS neurale locale, voci italiane | F1 |
| `numpy` | frame math, RMS, buffer | F1, F3 |
| `webrtcvad` / `silero-vad` | VAD + endpointing + barge-in | F2–F3 |
| `speexdsp` | AEC leggero (alternativa a WebRTC APM) | F4 |
| `asyncio`, `threading`, `queue` (stdlib) | concorrenza real-time ↔ task lenti | F1+ |

### §30.9 — ADR

| ADR | Titolo | Decisione |
|---|---|---|
| **ADR-EP041-001** | Runtime adapter: Opzione A (agent SDK) vs Opzione B (custom loop) | **GO Opzione B** — custom loop adapter (`voice/runtime/custom_loop_adapter.py`); massima aderenza alla filosofia agnostica; interfaccia astratta `FactoryRuntime` consente aggiunta futura di `agent_sdk_adapter.py` senza modificare il layer vocale |

### §30.10 — File chiave

| Tipo | Path |
|---|---|
| **Entry point** | `voice/app.py` |
| **Config** | `voice/config.py` + `factory.config.yaml :: voice_channel:` |
| **Interfaccia runtime** | `voice/runtime/base.py` (`FactoryRuntime` + tassonomia eventi) |
| **Adapter Opzione B** | `voice/runtime/custom_loop_adapter.py` |
| **FSM** | `voice/core/state_machine.py` |
| **Router (choke point TTS)** | `voice/core/router.py` |
| **Runbook installazione** | `wiki/runbooks/voice-channel-installation.md` |
| **Concept** | `wiki/concepts/voice-channel-factory.md` |
| **Design source** | `wiki/sources/sistema-vocale-factory.md` |

### §30.11 — Integrazione con capability esistenti

EP-041 si integra con il framework esistente senza modificarlo:

- **factory.config.yaml**: aggiunge il blocco `voice_channel:` (opt-in, default off)
  senza toccare nessuna chiave esistente. A `enabled: false` la factory e' identica a v2.27.
- **Token Ledger (EP-022)**: il consumo della sessione vocale e' visibile inline via
  `show-session-tokens.py`. Il CustomLoopAdapter genera eventi LLM le cui chiamate
  contribuiscono al conteggio di sessione.
- **§29 Scalability Patterns**: la `voice/` directory e' fuori scope del dispatch degli
  agenti — nessuna interazione con lo scheduler, nessun agente `.claude/` scaffoldato.
  EP-041 non aggiunge nessuna sezione a `dispatch-policy.md`.
- **Backward compat totale**: nessuna factory v2.27 preesistente e' impattata.
  Il blocco `voice_channel:` con `enabled: false` e' l'unico artefatto aggiunto
  a `factory.config.yaml`; tutti gli altri file sono invariati (R.P3).

Fonte: EP-041 | [[voice-channel-factory]] | [[sistema-vocale-factory]]

### §30.12 — Voice Handsfree Improvements (EP-044, v2.31, opt-in)

EP-044 estende il Voice Channel Layer (EP-041) con cinque miglioramenti hands-free
consegnati negli Sprint 45-46. Nessuna nuova invariante §7. Backward compat totale v2.30.

| US | Problema | Soluzione | Campo config aggiunto |
|---|---|---|---|
| **US-155** | P1: doppio endpoint — VAD produce due trigger per una singola utterance | Debounce 500 ms in `Endpointer.feed_frame()`; campo `VADConfig.debounce_ms: int = 500` | `vad.debounce_ms: 500` |
| **US-156** | P2: wake-word catturata come primo comando utente | Flag `_skip_next_utterance` + distanza di Levenshtein (`levenshtein()`) per rigettare utterance foneticamente prossime alla wake-word | `wake_word.filter_threshold: 3` |
| **US-157** | P3: WER elevato con modello `small` su termini tecnici (10.4%) | Default STT promosso a `model: "medium"` — WER 2.9%, latenza ~2 s su CPU accettabile per l'uso hands-free | `stt.model` default: `"base"` → `"medium"` |
| **US-158** | P4: latenza file-pipe con polling fisso 500 ms | `FilePipeAdapter` riscritta event-driven (FSEvents macOS / inotify Linux) via dipendenza opzionale `watchdog`; fallback polling 100 ms sempre garantito | `runtime.pipe_poll_ms: 100`, `runtime.pipe_timeout: 180` |
| **US-159** | P5: doppia istanza e processi zombie al riavvio | PID lock file atomico (`VoiceConfig.pid_file_path`); avvio fallisce con errore esplicito se lock esiste; lock rimosso a `finally` | `voice_channel.pid_file_path: ".voice.pid"` |

**Dipendenza opzionale**: `pip install watchdog` abilita la modalita' event-driven per
US-158. Senza il pacchetto, il fallback polling 100 ms e' sempre attivo (no-op silenzioso).

**Config delta** (aggiunta al blocco `voice_channel:` di §30.6):

```yaml
# Voice Handsfree Improvements (EP-044, v2.31 opt-in)
voice_channel:
  pid_file_path: ".voice.pid"      # US-159: PID lock — no doppia istanza
  vad:
    debounce_ms: 500               # US-155: debounce doppio endpoint VAD
  wake_word:
    filter_threshold: 3            # US-156: Levenshtein distance max per filtrare wake-word
  stt:
    model: medium                  # US-157: default upgrade (WER 2.9% vs 10.4% small)
  runtime:
    pipe_poll_ms: 100              # US-158: fallback polling interval (ms)
    pipe_timeout: 180              # US-158: timeout attesa risposta file-pipe (s)
```

**Backward compat**: a `voice_channel.enabled: false` (default EP-041) tutti i miglioramenti
EP-044 sono no-op. Nessun import aggiuntivo avviene. Gate v2.31.0 PENDING.

Fonte: EP-044 | [[voice-channel-factory]]

## §31 — Hybrid Wiki Search Layer (EP-042, v2.29, opt-in)
<!-- profiles: full -->

> Ricerca semantica ibrida (vector + FTS + metadata filter) sul wiki, con fallback
> trasparente alla scansione lineare esistente. Potenzia la capability `wiki-query`
> senza modificarla: quando l'indice e' disponibile le query beneficiano del ranking
> semantico; quando e' assente (o disabilitato) il comportamento e' identico a v2.28.

### §31.1 — Problema e soluzione

Il wiki di una factory attiva cresce rapidamente (centinaia di pagine). La scansione
lineare `Glob wiki/**/*.md` + lettura selettiva per pertinenza gia' in uso in `wiki-query`
scala male: latenza lineare, nessun ranking semantico, nessun supporto a query in lingua
naturale che non matchino lessicalmente i titoli.

EP-042 introduce un **layer di ricerca semantica ibrida** opt-in:
- **LanceDB embedded** (zero server aggiuntivo) come store vettoriale + FTS (tantivy).
- **sentence-transformers** (`paraphrase-multilingual-MiniLM-L12-v2`) per embedding
  multilingua (italiano + inglese) a ~120 MB offline.
- **Reciprocal Rank Fusion (RRF k=60)** per combinare score vettoriali e FTS in un unico
  ranking calibrato.
- **Chunk per H2-section** (cap 2000 chars), ID stabile `<path>#<section-slug>`.
- **Fallback obbligatorio** (R.WS1): se l'indice e' assente o corrotto, `wiki-query` ricade
  silenziosamente sulla scansione lineare pre-EP-042 — nessuna risposta bloccata.

### §31.2 — Architettura

```
wiki/**/*.md  →  indexer  →  .wiki-search/index.lance  →  HybridSearcher  →  wiki-query
                               (LanceDB embedded)          tools/wiki-search/   (agente)
```

Il layer ha due percorsi indipendenti:

**Percorso di indicizzazione (write, off-band):**
`build-index.py` / `update-index.py` → crawl `wiki/` → chunk per H2-section →
embed (`sentence-transformers`) → upsert in LanceDB → aggiorna `index_state.json`
(per differenziale incrementale). L'indicizzazione avviene fuori-band tramite
comando esplicito (`/wiki-search reindex`), mai automaticamente durante una query.

**Percorso di ricerca (read-only, on-demand):**
`HybridSearcher.search(query, mode, top_k, filters)` → vector search (embedding coseno)
+ FTS (tantivy / scan TF fallback) → RRF merge → metadata filter push-down → top-K risultati
ordinati per score decrescente. La skill `wiki-search-protocol` incapsula questo percorso
in 4 step (check → query → inject → fallback) ed e' invocata da `wiki-query` come
PRE-LLM context injection.

### §31.3 — Componenti

| Componente | File | Responsabilita' | US |
|---|---|---|---|
| **IndexerCore** | `tools/wiki-search/indexer.py` | crawl/chunk/embed/upsert condiviso (importabile) | US-148 |
| **IndexBuilder CLI** | `tools/wiki-search/build-index.py` | full build entry point; `--rebuild` = drop + re-index | US-148 |
| **IncrementalUpdater CLI** | `tools/wiki-search/update-index.py` | update solo file modificati via `index_state.json`; `--full`; `--stats` | US-150 |
| **HybridSearcher** | `tools/wiki-search/searcher.py` | vector + FTS + filter → RRF → top-K; `.is_available()` gateway; sceglie il backend (`wiki_search.backend`) | US-149 |
| **Backend fts5** | `tools/wiki-search/fts_index.py` | SQLite FTS5, solo stdlib: una riga per sezione H2, BM25, indice incrementale per hash; default di `backend: auto` quando `lancedb`/`sentence-transformers` mancano | EP-075 |
| **wiki-search-protocol** | `.claude/skills/wiki-search-protocol.md` | thin-skill 4-step: check → query → inject → fallback | US-151 |
| **wiki-query** (esteso) | `.claude/agents/wiki-query.md` | primo consumatore della skill; fallback scan lineare se indice assente | US-149 |
| **Comando** | `.claude/commands/wiki-search.md` | `/wiki-search <query>` + `reindex [--full]` + `status` | US-150 |
| **Config** | `factory.config.yaml :: wiki_search:` | parametri layer: embedding, mode, top_k, exclude_types | US-151 |

### §31.4 — Invarianti locali (R.WS1..R.WS3)

Queste invarianti sono **locali al layer EP-042** — non aggiungono ne' modificano le 18
invarianti globali §7.

| Invariante | Titolo | Regola |
|---|---|---|
| **R.WS1** | Fallback garantito | Indice assente / `enabled: false` / import fail → `{"results": [], "fallback": true}`. Mai bloccare una risposta per mancanza di indice. `wiki-query` ricade silenziosamente sulla scansione lineare pre-EP-042. |
| **R.WS2** | Opt-in obbligatorio | `wiki_search.enabled: false` di default. A flag spento: nessun import di `lancedb` o `sentence_transformers`, nessuna directory `.wiki-search/` creata, comportamento identico a v2.28. Vale anche per il backend `fts5`: `/query` lancia `fts_index.py` solo a flag acceso. |
| **R.WS3** | Read-only durante la query | Nessun write sull'indice durante `HybridSearcher.search()`. L'indice e' aperto in sola lettura; solo `build-index.py` e `update-index.py` eseguono scritture (su comando esplicito). **Deroga dichiarata per `fts5`:** se `.wiki-search/fts.sqlite` manca, la prima ricerca lo costruisce, e `search --refresh` reindicizza le pagine cambiate. L'indice LanceDB resta in sola lettura. |

### §31.5 — Config gate

```yaml
# Hybrid Wiki Search (EP-042, opt-in, PATTERN §31)
wiki_search:
  enabled: false                                           # opt-in esplicito (R.WS2)
  backend: auto                                            # auto | fts5 | hybrid (EP-075)
  fts_db: .wiki-search/fts.sqlite                          # indice del backend fts5
  embedding_provider: local                                # local | voyage-api | openai-api
  embedding_model: paraphrase-multilingual-MiniLM-L12-v2  # 384d, IT+multilingua, offline ~120MB
  embedding_dim: 384                                       # deve combaciare col modello (invariante schema)
  index_path: .wiki-search/index.lance                     # dataset LanceDB dentro .wiki-search/ (gitignored)
  index_table: pages                                       # nome tabella
  chunk_strategy: h2-section                               # h2-section (default) | whole-page
  mode: hybrid                                             # hybrid (default) | vector | fts — ignorato con backend fts5
  rrf_k: 60                                                # costante Reciprocal Rank Fusion
  candidate_k: 20                                          # candidati per ramo prima del merge RRF
  top_k: 5                                                 # risultati restituiti di default
  exclude_types: [meta]                                    # type esclusi di default (gaps/log)
```

`wiki_search.enabled: false` (default) — factory identica a v2.28; nessun import avviene,
nessuna dipendenza di ricerca viene caricata. Il blocco `wiki_search:` con `enabled: false`
e' l'unico artefatto aggiunto a `factory.config.yaml` dalle factory che aggiornano da v2.28.

`wiki_search.enabled: true` — attiva il layer. Con `backend: auto` e senza `lancedb` e
`sentence-transformers` il motore e' `fts5`: nessuna installazione, l'indice si costruisce alla
prima ricerca. Per il layer ibrido: `pip install lancedb sentence-transformers` + almeno un run
di `/wiki-search reindex` completato con successo.
Vedi `wiki/runbooks/wiki-search-installation.md`.

### §31.6 — Comandi

| Comando | Azione |
|---|---|
| `/wiki-search <query>` | Ricerca ibrida diretta nell'indice; bypassa `wiki-query` (utile per testing/debug) |
| `/wiki-search <query> --mode=fts\|vector` | Solo full-text o solo embedding |
| `/wiki-search reindex` | Aggiornamento incrementale dell'indice |
| `/wiki-search reindex --full` | Full rebuild (drop + re-index completo) |
| `/wiki-search status` | Stato indice: chunk count, last updated, modello |

### §31.7 — Dipendenze Python (opt-in)

Le dipendenze non vengono importate quando `wiki_search.enabled: false`, ne' con backend `fts5`
(solo `sqlite3` della libreria standard, piu' `pyyaml` per la config).

| Package | Ruolo |
|---|---|
| `lancedb` | Store vettoriale embedded + FTS (tantivy) |
| `sentence-transformers` | Modello embedding multilingua locale (~120 MB) |
| `numpy` | Calcoli vettoriali frame-level |
| `pyyaml` | Lettura `factory.config.yaml` |

### §31.8 — Integrazione con capability esistenti

EP-042 si integra con il framework esistente senza modificarlo:

- **wiki-query**: riceve context injection PRE-LLM dai risultati top-K quando l'indice e'
  disponibile; se no, comportamento invariato (scan lineare). Backward compat totale.
- **factory.config.yaml**: aggiunge il blocco `wiki_search:` (opt-in, default off) senza
  toccare nessuna chiave esistente. A `enabled: false` la factory e' identica a v2.28.
- **Dispatch policy §8**: `wiki_search` e' annunciato come capability opt-in nella tabella
  slug di `dispatch-policy.md §8` (Capability Advertisement, v2.27+).
- **Token Ledger (EP-022)**: le query di embedding e le ricerche FTS non generano chiamate
  LLM; il costo e' trascurabile e non registrato nel ledger (inferenza locale).
- **Backward compat totale**: nessuna factory v2.28 preesistente e' impattata. Il blocco
  `wiki_search:` con `enabled: false` e' l'unico artefatto aggiunto a `factory.config.yaml`
  (R.WS2). Tutti gli altri file sono invariati.

Fonte: EP-042 | [[hybrid-wiki-search-capability]] | `tools/wiki-search/` | `wiki/runbooks/wiki-search-installation.md`

Fonte: factory-optimization-2026-07-07 | `CLAUDE.md §Meta-prompt versioning`

---

## §32 — Content Share Consumer Layer (EP-048, v2.33, opt-in)

### §32.1 — Problema

Le factory producono artefatti HTML (prototipi EP-035, report analytics EP-009) che devono
raggiungere un viewer pubblico condiviso (soli-frames, https://soli-frames.vercel.app/viewer/).
Il canale diretto (commit nel repo viewer) e' impraticabile: richiede accesso cross-repo,
introduce accoppiamento strutturale e bypassa il gate di review del viewer.

Il pattern Content Share risolve questo disaccoppiando produzione e pubblicazione:
la factory invia un `repository_dispatch` a soli-frames; soli-frames crea una PR in
autonomia; la PR viene mergiata (draft → review → published). La factory non ha mai
write access al viewer: il dispatch e' fire-and-forget con gate umano obbligatorio (R.CS3).

### §32.2 — Architettura dispatch

```
factory (producer)                soli-frames (hub)
─────────────────                 ─────────────────
/share <html>                     POST /dispatches
  → content-share-protocol  ────▶   event_type: content-ingest
    Fase 0 Pre-flight              client_payload: { dispatch_secret, slug,
    Fase 1 Build Payload             title, html_b64, publish, source_repo }
    Fase 2 Validate                       │
    Fase 3 Gate umano ◀── STOP dry-run    ▼
    Fase 4 Dispatch ──────────▶  GHA workflow content-factory.yml
                                   resolve-dispatch-payload.py
                                   ingest-content-run.sh → node cli.js
                                   create-pull-request → merge → Vercel
```

Il payload DEVE essere annidato: `{"event_type": "...", "client_payload": {...}}`.
Un payload flat causa HTTP 422. La skill usa `gh api ... --input -` via heredoc.

Due segreti distinti (non intercambiabili):
- `CONTENT_DISPATCH_SECRET` — server-side su soli-frames, confrontato contro `dispatch_secret` nel payload
- `SOLI_FRAMES_DISPATCH_SECRET` — client-side in factory (env var), valore inviato come `dispatch_secret`

Due token distinti:
- `SOLI_FRAMES_PAT` — Bearer token per il POST GitHub API (fine-grained, Contents:write su soli-frames ONLY)
- `SOLI_FRAMES_DISPATCH_SECRET` — autenticazione payload (non usato come HTTP header)

### §32.3 — Slug convention (R.CS1)

Lo slug completo segue il pattern: `{source_repo_slug}-{content_slug}`.

- **Regex**: `^[a-z][a-z0-9-]{1,78}[a-z0-9]$` (2–80 caratteri, solo lowercase + cifre + trattino)
- **Auto-composizione**: se `--slug` omesso, `content_slug` e' il basename del file HTML in kebab-case
- **Override esplicito**: `--slug=my-report` → slug finale `soli-factory-my-report`
- **Vincolo unicita'**: soli-frames usa lo slug come filename (`content/<slug>.html`); un secondo dispatch
  con lo stesso slug aggiorna il file esistente (upsert)
- **source_repo_slug** e' dichiarato in `factory.config.yaml.content_share.source_repo_slug` —
  mai auto-derivato a runtime (R.CS1 side-effect: slug deterministici cross-sessione)

### §32.4 — Invarianti R.CS1..R.CS4

| ID | Invariante | Violazione → |
|---|---|---|
| R.CS1 | Slug conforme `^[a-z][a-z0-9-]{1,78}[a-z0-9]$`, prefissato con `source_repo_slug` | STOP in Fase 1 |
| R.CS2 | `content_share.enabled: false` di default — backward-compat totale v2.32 | STOP silenzioso con messaggio esplicito |
| R.CS3 | Gate umano obbligatorio prima di ogni dispatch (azione outward non reversibile) | `--dry-run` bypassa Fase 4, non Fase 3 |
| R.CS4 | Egress classification check: `analytics_report` con dati sensibili → EGRESS_BLOCK | STOP in Fase 0 |

Vincoli aggiuntivi (non invarianti §7 ma contratti locali EP-048):
- Dimensione HTML hard limit: 100 KB decoded (EGRESS_BLOCK); warning a 80 KB (EGRESS_WARN)
- `publish_default: draft` — mai publish automatico (viewer pubblico, no unpublish)
- Nessun agente lancia `/share` in autonomia (deliberazione TR A11)

### §32.5 — Configurazione

```yaml
content_share:
  enabled: false                              # R.CS2 opt-in — backward-compat totale v2.32
  target_repo: "soli92/soli-frames"          # hub destinazione
  source_repo_slug: ""                        # ESPLICITO obbligatorio — es. "soli-factory"
  source_repo: ""                             # formato org/repo — es. "soli92/soli-multi-agents-factory"
  pat_env: SOLI_FRAMES_PAT                   # PAT fine-grained (Contents:write su soli-frames SOLO)
  secret_env: SOLI_FRAMES_DISPATCH_SECRET    # valore inviato come dispatch_secret nel payload
  publish_default: draft                      # mai publish automatico
  size_limit_kb: 100                         # hard limit decoded HTML (EGRESS_BLOCK)
  size_warn_kb: 80                           # soglia warning (EGRESS_WARN)
  artifact_categories:
    prototype: true                           # artefatti EP-035
    analytics_report: true                    # report EP-009 (soggetti a R.CS4)
    custom: true
```

Secret locali in `.claude/settings.local.json` (gitignored):
```json
{ "env": { "SOLI_FRAMES_PAT": "<pat>", "SOLI_FRAMES_DISPATCH_SECRET": "<secret>" } }
```

### §32.6 — Comandi

```
/share <html-path> [--slug=<slug>] [--title=<titolo>] [--dry-run]
```

| Flag | Default | Descrizione |
|---|---|---|
| `<html-path>` | obbligatorio | Path al file HTML da pubblicare |
| `--slug` | `{source_repo_slug}-{basename}` | Override content-slug (senza prefisso) |
| `--title` | estratto da `<title>` HTML | Titolo leggibile; fallback a slug |
| `--dry-run` | off | Fasi 0-3 incluso gate umano; bypassa Fase 4 |

Il comando `/share` non ha side-effect automatici: ogni invocazione richiede gate umano (R.CS3).
Per prototipi EP-035: usare il path di output di `prototype-generator`. Per report EP-009:
verificare R.CS4 egress classification con `--dry-run` prima del dispatch reale.

### §32.7 — Autenticazione

Il PAT `SOLI_FRAMES_PAT` DEVE essere fine-grained (non PAT classic):
- **Scope**: `Contents:write` su `soli92/soli-frames` ONLY (non org-wide)
- **Rationale**: blast radius minimo su revoca; PAT classic con scope `repo` darebbe
  write access a tutti i repo privati
- **Rotation**: ≤90 giorni (raccomandata); la revoca non impatta altri repo
- **`GITHUB_TOKEN` nativo**: NON usabile — e' disponibile solo dentro GHA, non dall'esterno

Setup completo: `wiki/runbooks/content-share-setup.md`

### §32.8 — Integrazione con capability esistenti

EP-048 si integra con il framework esistente senza modificarlo:

- **EP-035 Prototype Generation**: l'output di `prototype-generator` (HTML file) e' direttamente
  pubblicabile via `/share`. Workflow tipico: `/prototype` → `/share <output.html>`.
- **EP-009 Analytics**: i report HTML sono pubblicabili ma soggetti a R.CS4 egress check.
  Artefatti con dati per-attore o rate card → EGRESS_BLOCK. Usare `--dry-run` per verificare.
- **Token Ledger (EP-022)**: il dispatch via `gh api` non genera chiamate LLM; il costo e'
  trascurabile. La Fase 3 (gate umano) e' l'unica interazione che produce token.
- **Dispatch policy §8**: `content_share` annunciato come capability opt-in nella tabella slug.
- **Backward compat totale**: nessuna factory v2.32 e' impattata. Il blocco `content_share:`
  con `enabled: false` e' l'unico artefatto aggiunto a `factory.config.yaml` (R.CS2).
  Tutti gli altri file sono invariati.
- **soli-frames hub**: il viewer accetta HTML da qualsiasi factory autorizzata via
  `CONTENT_DISPATCH_SECRET`. Slug guard US-021 + sourceRepo field US-022 gia' in produzione.
  `<a href="https://...">` navigazionali permessi; `src/poster/action` assoluti bloccati.

## §33 — Code Intelligence Layer (EP-054, v2.37, opt-in)

Stack a tre layer local-first per ottimizzare la navigazione del codice da parte
degli agenti. Zero dipendenze esterne: tutto gira offline e in CI container.
`code_intelligence.enabled: false` di default (backward compat totale v2.36).

### §33.1 — Architettura

```
Query agente
    │
    ├─▶ [L1] ctags Symbol Index      ← "dove è definita X?" → file:line (ms, O(1))
    ├─▶ [L2] Semantic Code Search     ← "dove viene gestita Y?" → chunk ranked (s)
    └─▶ [L3] Impact Graph            ← "cosa si rompe se cambio Z?" → blast radius
```

I tre layer sono ortogonali: attivabili indipendentemente, non si bloccano a vicenda.
Un layer non disponibile (prerequisito mancante, flag disabilitato) → SKIP + warning, mai STOP.

### §33.2 — L1: Symbol Resolver (universal-ctags)

**Scopo**: lookup esatto O(1) su simboli senza consumare token LLM.

**Prerequisito**: `universal-ctags` installato (`brew install universal-ctags` su macOS,
`apt-get install universal-ctags` su Linux). NON compatibile con Exuberant Ctags (built-in macOS).

**Funzionamento**:
1. `tools/code-intelligence/ctags-index.sh <repo_path> <slug>` genera l'indice
2. Side-channel: `.ctags-state/<slug>/tags` + `meta.json` (gitignored)
3. Query: `grep "^<symbol>\t" .ctags-state/<slug>/tags`
4. Output: `{file, line, type, signature}` — milliseconds anche su 200k LOC

**Aggiornamento**: automatico post `/repo-sync` se `l1_ctags.enabled: true`.
Incrementale: `--update` rimuove entry obsolete e appende nuove.

**Skill**: `.claude/skills/ctags-index-protocol.md`

### §33.3 — L2: Semantic Code Search (tree-sitter + nomic-embed-code + LanceDB)

**Scopo**: retrieval semantico su query in linguaggio naturale ("trova il codice che
gestisce l'autenticazione JWT") con precisione symbol-level invece di file-level.

**Prerequisiti**:
```bash
pip install tree-sitter>=0.21 sentence-transformers>=2.7 lancedb>=0.6 pyarrow
pip install tree-sitter-python tree-sitter-typescript tree-sitter-javascript
pip install tree-sitter-java tree-sitter-go tree-sitter-rust
```

**Pipeline**:
1. `chunk-code.py` — tree-sitter estrae chunk symbol-level (function/class/interface)
2. `index-code.py` — embedding con `nomic-embed-code` (Apache 2.0, 137M params, 768-dim) + upsert LanceDB
3. Tabella LanceDB: `code_chunks` (distinta da `wiki_chunks` EP-042)
4. Query: `/code-search <query>` → top-K chunk ranked per similarity score

**Chunking**: nodi tree-sitter target per linguaggio (vedere `code-chunk-protocol.md`).
Chunk max `chunk_max_lines` (default 150) — split con overlap 10 righe se superato.
Stato incrementale: hash SHA256 per file, skip se invariato.

**Embedding model default**: `nomic-ai/nomic-embed-text-v1` (nomic-embed-code variant).
Override: `code_intelligence.l2_semantic.embedding_model` in factory.config.yaml.
Caching locale HuggingFace (`~/.cache/huggingface/`), download solo al primo uso (~137MB).

**Indice**: `.code-search/index.lance` (gitignored). Separato dall'indice wiki (EP-042).
I vettori dei due indici NON sono cross-compatibili (modelli distinti).

**Skill**: `.claude/skills/code-chunk-protocol.md`
**Comando**: `/code-search <query> [--top=N] [--lang=<lang>] [--type=<type>]`
**Reindex**: `/code-search reindex [--full] [--slug=<name>]`

### §33.4 — L3: Impact Graph (graphify affected in dev-protocol)

**Scopo**: pre-analysis automatica del blast radius prima di scrivere codice,
integrata come Fase 0.bis nel `dev-protocol`.

**Prerequisiti**: graphify installato + graph costruito per il code_path target (EP-052).

**Funzionamento** (R.CI4 — analysis-only):
1. Agente dev estrae simboli principali dal TSK
2. Per ogni simbolo: `graphify affected "<symbol>" --format=json --depth=2`
3. Output in memoria: `{symbol, affected_files, affected_symbols, depth, blast_radius}`
4. Se blast_radius > 10 file → `[L3-WARN]` + richiesta conferma se scope fuori TSK

**Attivazione**: `code_intelligence.l3_impact.enabled: true` + `auto_run_on_dev: true`
per trigger automatico in Fase 0.bis. Default entrambi `false`.

**Integrazione**: vedi `dev-protocol.md` Fase 0.bis.

### §33.5 — Invarianti locali EP-054

Queste invarianti sono contratti locali dell'EP, non invarianti §7 globali.

| ID | Invariante | Violazione |
|---|---|---|
| R.CI1 | `code_intelligence.enabled: false` di default — backward compat totale v2.36 | STOP silenzioso |
| R.CI2 | Ogni layer: prerequisito mancante → SKIP + warning, mai STOP | exit 0 con `[L1/L2/L3-SKIP]` |
| R.CI3 | L1 e L2 sono read-only verso il repo sorgente (scrivono solo side-channel) | STOP se violato |
| R.CI4 | L3 Fase 0.bis è analysis-only — nessuna modifica file in questo step | STOP se violato |
| R.CI5 | Fallback garantito: indice assente/corrotto → lista vuota + `fallback:true`, mai crash | exit 0 |

### §33.6 — Configurazione

```yaml
code_intelligence:
  enabled: false                          # master switch (R.CI1)
  l1_ctags:
    enabled: false                        # R.CI2 per-layer
    languages: [python, typescript, javascript, java, go, rust, c, cpp]
    side_channel: .ctags-state           # gitignored
    extra_flags: []
  l2_semantic:
    enabled: false                        # requires: tree-sitter + sentence-transformers + lancedb
    embedding_model: nomic-embed-code    # local HF model, Apache 2.0, 137M params
    chunk_max_lines: 150
    lancedb_path: .code-search/index.lance  # gitignored
    exclude_patterns: ["**/node_modules/**", "**/__pycache__/**", "**/vendor/**"]
  l3_impact:
    enabled: false                        # requires: graphify + graph built (EP-052)
    auto_run_on_dev: false               # se true: Fase 0.bis si attiva automaticamente
    min_symbol_confidence: 0.7
```

### §33.7 — Comandi

```
/code-search <query>               ricerca semantica L2 sul code index
/code-search reindex [--full]      rebuild indice L2 (chunk + embed)
/code-search status                stato indice (chunk count, timestamp, dimensione)
```

Per L1: `bash tools/code-intelligence/ctags-index.sh <path> <slug>` + grep diretto.
Per L3: automatico in Fase 0.bis dev-protocol (se `auto_run_on_dev: true`) o manuale
con `graphify affected "<symbol>"`.

### §33.8 — Integrazione con capability esistenti

- **EP-042 Hybrid Wiki Search**: L2 estende la `wiki-search-protocol` con source `code`.
  Tabelle LanceDB separate (wiki_chunks vs code_chunks). `/code-search --all` mergia con RRF.
- **EP-052 Graphify**: L3 usa il graph esistente senza ricostruirlo. Se graph non presente
  per un code_path → `[L3-SKIP]`; agente può lanciare `/graphify-sync <target>` per costruirlo.
- **EP-053 dev-protocol checkpoint**: Fase 0.bis L3 eredita il principio analysis-only
  di TSK-451 (dev-protocol checkpoint). I due step coesistono in Fase 0.bis.
- **repo-extraction-protocol**: post `/repo-sync`, se L1 enabled → `ctags-index.sh` aggiornato
  automaticamente; se L2 enabled → `chunk-code.py` + `index-code.py` run incrementale.
- **Backward compat totale v2.36**: blocco `code_intelligence:` con tutti default `false`
  è l'unico delta a `factory.config.yaml`. Tutti gli altri file sono additive-only.
- **Side-channel gitignored**: `.ctags-state/` e `.code-search/` aggiunti a `.gitignore`
  (non committati, rigenerabili in qualsiasi momento — analogo a `.graphify-state/`).

Fonte: EP-054 | [[code-intelligence-stack]] | `wiki/runbooks/code-intelligence.md`

Fonte: EP-048 | [[content-share-hub-pattern]] | `.claude/skills/content-share-protocol.md` | `wiki/runbooks/content-share-setup.md`

---

## §34 — Semantic Purpose Layer — `wiki/purpose.md` (EP-055, v2.38, opt-in)

Pattern-stealing concettuale da `llm_wiki` (GPL v3, reimplementato da zero — vedi §23.10).
`factory.config.yaml` copre la configurazione **tecnica** della factory; `wiki/purpose.md`
copre le **direttive semantiche di dominio** che orientano ingest e lint. Due file
complementari, mai sovrapposti.

### §34.1 — Scopo

`wiki/purpose.md` è un file **maintainer-authored** (scritto a mano, non generato) che
esprime i principi guida semantici del progetto: di cosa parla la wiki, quali tipi di entità
sono prioritari, con che tono, e cosa è fuori scope. Colma il gap per cui `wiki-keeper` non
sa, ad esempio, che in una factory i "pattern" contano più delle "entità organizzative", o
che il tono deve essere tecnico-prescrittivo e non narrativo.

### §34.2 — Formato (frontmatter YAML + corpo markdown)

Deciso per consenso in TR-llmwiki-20260824 (D1): frontmatter YAML strutturato (parsabile
deterministicamente da `wiki-lint`) + corpo markdown libero (espressività per gli agenti).
JSON-LD escluso (over-engineered); markdown puro escluso (non parsabile).

```yaml
---
type: purpose
domain: <stringa — descrizione del dominio del progetto>
priority_entity_types: [<lista — tipi di entità prioritari nell'ingest>]
tone: technical-prescriptive         # | narrative | mixed
exclusions: [<lista — argomenti/tipi fuori scope, può essere vuota>]
---

# Purpose

<corpo markdown libero: descrizione estesa, esempi, note per gli agenti>
```

Campi obbligatori: `domain`, `priority_entity_types`, `tone`, `exclusions`.
`tone` ∈ `{technical-prescriptive, narrative, mixed}`.

### §34.3 — Comportamento

- **`wiki-keeper`** (US-200): legge `wiki/purpose.md` se presente, all'inizio dell'ingest,
  come **contesto** (non gate). Read-only: mai lo modifica (unico autore = maintainer).
  Assente → ingest standard, comportamento invariato.
- **`wiki-lint`** (US-201): assente → **WARNING** (non ERROR: la wiki resta valida);
  presente con frontmatter incompleto o `tone` fuori enum → WARNING con dettaglio.
  Non `heal-eligible` (giudizio semantico, non fix meccanico).

### §34.4 — Invarianti

- **Opt-in / additivo**: factory senza `wiki/purpose.md` sono identiche a prima. Nessun
  config flag: il file è letto se presente, sempre.
- **Maintainer-sovrano**: `purpose.md` è contesto d'ingest, non un vincolo hard. Il
  maintainer resta l'unico autore; nessun agente lo genera o modifica.
- **Non duplica `factory.config.yaml`**: tecnico (config) vs semantico-di-dominio (purpose).

### §34.5 — File chiave

- `.claude/skills/scrivi-purpose.md` — template + guida alla scrittura
- `wiki/purpose.md` — reference implementation (questa factory)
- `.claude/skills/lint-checks.md` — Check 4an (presenza + frontmatter + enum tone)

Fonte: EP-055 | wiki/decisions/tavola-rotonda-TR-llmwiki-20260824-2026-08-24.md | §23.10

---

## §35 — Wiki Keeper 2.0 — CoT Handoff & Semantic Sweep (EP-056, v2.38, opt-in)

Due ottimizzazioni della pipeline di ingest, pattern-stealing concettuale da `llm_wiki`
(GPL v3, reimplementato da zero — §23.10). La deliberazione TR-llmwiki-20260824 ha
riconosciuto che l'architettura `wiki-keeper` + `wiki-keeper-worker` implementa **già** il
2-step CoT: qui si esplicita il CoT intermedio (§35.2) e si aggiunge un pass di qualità
semantica assente nel framework (§35.3). Foundation **read-only** su EP-042/EP-054 (stability
window): nessuna modifica ai layer esistenti.

### §35.1 — Scopo

- **CoT handoff** (US-202): un piano di pagine esplicito tra merge (Fase 1.bis) e generazione
  (Fase 3) → generazione su input strutturato, meno allucinazione, wikilink più coerenti, gap
  come artefatto esplicito.
- **sweep-reviews** (US-203): ciclo di qualità **semantico** su `wiki/` che il lint meccanico e
  `heal-protocol` non coprono (claim non supportati, wikilink dangling, deriva terminologica).

### §35.2 — CoT handoff (Fase 1.ter)

`wiki-keeper-worker` emette `plan_reasoning` per pagina; il `wiki-keeper` sintetizza in
**Fase 1.ter "Piano di pagine (CoT esplicito)"** (nuova, tra 1.bis e Fase 2): ordine di
scrittura topologico sui wikilink, grafo wikilink con dangling → candidati gap, coerenza
terminologica contro `wiki/purpose.md` (§34), claim → citazione. Ramo seriale (N<3): piano
inline equivalente. Nessun file persistito obbligatorio.

### §35.3 — sweep-reviews (loop semantico bounded gated)

Controparte **semantica** di Heal (§3), stessa struttura loop-bounded + gate bulk, natura
opposta:

| | Dominio | Natura | Inferenza | Applicazione | Gate | Attivazione |
|---|---|---|---|---|---|---|
| **Heal** (§3) | `wiki/` | meccanico (whitelist deterministica) | vietata | in-place puro | bulk | always-on |
| **CQRL** (§19) | codice | idiomaticità/design/robustezza | — | task_package | severity-tiered | `code_quality.enabled` |
| **sweep-reviews** (§35) | `wiki/` | semantico (claim/link/terminologia) | ammessa, gated | `## Aggiornamenti` (§7 r.7) | bulk stretto + confidence | `wiki_sweep.enabled` |

Categorie: `unsupported-claim` (claim >20 parole senza `[^src:]` → fonte o gap),
`dangling-concept` (`[[X]]` verso pagina inesistente non in gaps → stub o gap),
`terminology-drift` (termini incoerenti giudicati contro `purpose.md`; skip se assente).
Loop bounded (`max_iterations`), scarto sotto `confidence_min`, gate umano bulk PRIMA di
applicare, terminazione `closed|stuck|regression|max-iterations|user-rejected|no-items|empty-diff`.

### §35.4 — Invarianti

- **Opt-in totale** (R.P3): `wiki_sweep.enabled: false` di default → factory identica a v2.37
  pre-EP-056. CoT handoff è additivo e backward-compat (Fase 1.ter no-op sul comportamento se
  non produce cambi).
- **Single-committer preservato** (§7 r.12): sweep-reviews è capability del `wiki-keeper`, non
  un nuovo agente (Accordo Round 2).
- **No auto-apply**: ogni risoluzione semantica passa dal gate umano bulk.
- **§7 r.7**: risoluzioni semantiche via `## Aggiornamenti (vYYYY-MM-DD)`, mai in-place (a
  differenza di Heal, meccanico).
- **§10 non-override**: `## Contradictions` mai risolte silenziosamente; `## Storie collegate`
  (PM) mai toccate.
- **Stability window**: EP-042/EP-054 usati read-only; retrieval 4-fase e KG 4-segnali restano
  backlog (EP-042.1 / spike, D2/D3).

### §35.5 — Config + file chiave

```yaml
wiki_sweep:
  enabled: false                 # opt-in (R.P3)
  max_iterations: 3
  confidence_min: 0.7
  categories: [unsupported-claim, dangling-concept, terminology-drift]
  use_purpose_md: true           # terminology-drift usa wiki/purpose.md (§34)
```

- `.claude/skills/sweep-reviews-protocol.md` — detection + resolution loop
- `.claude/skills/ingest-protocol.md` — Fase 1.ter (CoT)
- `.claude/skills/wiki-keeper-worker-protocol.md` — `plan_reasoning`
- `.claude/commands/sweep-reviews.md` — comando gated
- `.claude/skills/wiki-log-entry.md` — template `sweep`

Cross-ref: §34 (purpose.md), §23.10 (licenza pattern-stealing), §3 (Heal), §19 (CQRL), §16 (ingest).

Fonte: EP-056 | wiki/decisions/tavola-rotonda-TR-llmwiki-20260824-2026-08-24.md (Accordi Round 2/4) | §34

## §36 — Refactor Skill Layer / Fleet Health (EP-060, v2.41, opt-in)

Introdotto in v2.41. Capability opt-in che rifattorizza le unità di contesto
agentiche (SKILL.md, file di agenti, indici di flotta) in *divulgazione
progressiva*: spina dorsale nel corpo (contesto garantito) + foglie in
`references/` (contesto opzionale con trigger vincolanti).

### Concetti fondanti

Tre **specie** della stessa struttura:

- **Skill** (`SKILL.md`) — trigger = `description`; corpo = istruzioni operative
- **Agente / sotto-agente** — trigger = `description`; corpo = prompt di sistema
- **Indice di flotta** (`AGENTS.md` o equivalente) — non triggerato; corpo = mappa
  team/membership/handoff

Le 3 specie condividono la disciplina di taglio (vedi
`.claude/skills/references/refactor/criteri-di-taglio.md`).

### Soglie

| Righe corpo | Verdetto |
|---|---|
| `>500` | **REFACTOR raccomandato** |
| `300–500` | **VALUTARE** |
| `<300` | ok — non intervenire |

Post-refactor: corpo ≤ 250 righe; foglie 50–250 righe.

### 9 Vincoli non negoziabili (V-1..V-9)

V-1 Spina dorsale inamovibile · V-2 Trigger vincolanti al punto d'uso ·
V-3 Triggering e dispatch invariati · V-4 Una sola radice per unità ·
V-5 Equivalenza prima della sostituzione · V-6 Snapshot prima di toccare ·
V-7 Nessuna duplicazione · V-8 Integrità del grafo · **V-9 Sicurezza di dispatch**.

V-9 è specifico di Claude Code: se un agente è dispatchato per iniezione del
corpo, le foglie esterne sono pericolose. Vedi
`.claude/skills/references/refactor/topologia-e-dispatch.md`. Questa factory
usa **Pattern A** (`subagent_type`), quindi V-9 near-zero — vettore residuo:
compression layer opt-in.

### 11 Gate strutturali (G1..G11)

G1 unica radice · G2 frontmatter valido · G3 frontmatter invariato ·
G4 path esistenti · G5 no foglie orfane · G6 script eseguibili · G7 righe entro
soglia · G8 ancore valide · G9 riferimenti risolti · G10 no orfani/irraggiungibili ·
G11 dispatch-safe (V-9).

G1–G8 in `tools/refactor/verifica_flotta.py`.
G9–G11 in `tools/refactor/mappa_riferimenti.py --gate`.

**Owner G1–G11**: agente `fleet-doctor` (`.claude/agents/fleet-doctor.md`).

### Boundary con altre capability

- **Ponytail (EP-057)**: valuta codice di prodotto (`.py/.ts`). Fleet-health
  valuta markdown agentici (`.claude/{agents,skills}/*.md`). Scope disgiunto.
- **code-review-protocol (v2.12)**: valuta output dei dev-agent nei code_path.
  Fleet-health valuta file meta-framework. Scope disgiunto.
- **complexity-budget-check**: valuta struttura di TSK (numero step, granularità).
  Fleet-health valuta lunghezza di unità di contesto. Complementari.

### Config e invarianti locali

Config: `refactor_agent_skills:` in `factory.config.yaml`.

- **R.FH1 (opt-in totale)**: `enabled: false` di default. A flag spento la
  capability è invisibile ai dev-agent e la factory è identica a v2.40.
- **R.FH2 (WARNING-only)**: Check 4ap emette WARNING, mai ERROR. Il refactor
  non è mai imposto.
- **R.FH3 (fail-open)**: se gli script mancano, il check skip silente. La
  lint pipeline generale non fallisce.

### Ambito d'uso

- **Auto-mode** (default): rifattorizza unità della factory stessa (`code_path: "."`).
- **external_target**: differito. Sblocco condizionato a: protocollo topologia
  esterna ignota validato su ≥1 factory derivata reale.

### Trigger

- Comando esplicito: `/refactor <target>` (via agente `fleet-doctor`).
- Lint check automatico: Check 4ap (WARNING-only) nel dominio lint.
- Dispatch orchestrator: `layer: refactor` (opzionale, `scheduler.domains.refactor: false` default).

### Risorse

- `.claude/agents/fleet-doctor.md` — agente owner G1–G11
- `.claude/skills/refactor-agent-skills.md` — skill operativa (spina dorsale + fasi 0–5)
- `.claude/skills/references/refactor/` — foglie di riferimento:
  - `topologia-e-dispatch.md` — specie, topologia, meccanica dispatch, V-9
  - `criteri-di-taglio.md` — tassonomia contenuti, criteri di taglio, trigger, anti-pattern
  - `integrita-riferimenti.md` — forme di riferimento, gate di grafo G9–G11
  - `igiene-flotta.md` — ottimizzazioni di flotta oggettive
  - `protocollo-test-equivalenza.md` — Fase 4 completa
- `tools/refactor/analizza_target.py` — inventario, outline, verdetto soglie
- `tools/refactor/mappa_riferimenti.py` — grafo riferimenti, gate G9–G11
- `tools/refactor/verifica_flotta.py` — gate strutturali G1–G8
- `.claude/skills/lint-checks-agent-fleet.md` — Check 4ap
- `wiki/runbooks/skill-hygiene.md` — runbook narrativo, esempi d'uso

Fonte: EP-060 | `raw/refactor-agent-skills/SKILL.md` (V-1..V-9, G1..G11)

### Criteri di taglio applicati (empirical evidence 11 pilot)

Sette criteri unici applicati durante i pilot EP-060, mai riusati:

| # | Criterio | Pilot | Quando applicare |
|---|---|---|---|
| 1 | Per fase del flusso | #1 tavola-rotonda-protocol, #9 functional-oracle | Skill sequenziale con fasi distinte, ognuna con input/output dichiarato |
| 2 | Per variante versione | #2 factory-bootstrap | Meta-comando dispatcher con case-per-version che cresce linearmente |
| 3 | Per frequenza d'uso | #3 tavola-rotonda-moderatore, #10 parallel-scheduling, #11 dev-protocol | Corpo con zone always-on (Class A) + zone opt-in (Class B) chiaramente separate |
| 4 | Per opt-in capability | #4 fe-dev | Corpo dominato da opt-in section per capability config (ognuna con flag distinto) |
| 5 | Per fase pesante | #5 prototype-generation | Skill con fasi molto grandi + logica per-backend già delegata a skill secondarie |
| 6 | Per destinazione contenuto | #6 commands/prototype | Command con 3 audience distinte (agent execution / user output / operator docs) |
| 7 | Per famiglia (dedup) | #8 lint-checks | Skill con famiglie modulari già estratte ma spina non allineata (allineamento + dedup) |

Casi speciali:
- **Pilot #7 (prototype-generator)**: verdetto NO-REFACTOR motivato — dominanza Classe A + micro-foglie anti-pattern. Dimostra che la capability discrimina target cohesive da target misto.

### Metriche empirical evidence (11 pilot Wave D)

| Metrica | Valore |
|---|---|
| Pilot totali | 11 (10 ACCEPT + 1 NO-REFACTOR motivato) |
| Righe corpo totali eliminate | ~6300 |
| Foglie totali create | 27 |
| Convenzioni directory validate | 3 (agents/skills/commands references) |
| Test empirici TSK-546 AC2 consecutivi ACCEPT | 7 |
| Riduzione min | -17.6% (pilot #3, VALUTARE cohesive borderline) |
| Riduzione max | -94.6% (pilot #8 lint-checks, allineamento EP-052) |
| Riduzione media (10 accept) | ~-58% |

### Riferimenti ADR

- **ADR-EP060-001**: boundary + Pattern A + PA-5 + owner G1-G11
- **ADR-EP060-002**: pattern emergenti (trilogia directory + drift reconciliation + fix inline 2 famiglie + Class A anchor + T3 soft-fail)
- **ADR-EP060-003**: external_target foundation (5 decisioni sblocco Decisione 5)

## §37 — Session Observability (EP-061 + EP-062, v2.42, opt-in)

Introdotto in v2.42. Pattern **agent-agnostic** per l'osservazione post-hoc
dell'attività agentica di una sessione conclusa. Rileva anomalie via regole
deterministiche su un fan-in di transcript strutturati (main + sub-agenti).
Adapter-neutral: la sorgente dati è il transcript JSONL dell'adapter attivo
(Claude Code, Cursor, Aider…); ogni adapter è responsabile di fornire un walker
compatibile.

Origine: Tavola Rotonda TR-c4e8f1b2 (2026-09-08, forced-synthesis Round 3).
Blackboard: `wiki/decisions/tavola-rotonda-c4e8f1b2-...-2026-09-08.md`.

### Principi fondanti

1. **Determinism-first**: la rilevazione anomalie è 100% regole deterministiche
   su campi strutturati (usage, stop_reason, timestamp, attribution). LLM
   *advisory* ammesso solo in sezioni narrative del report (`## Punti Aperti`,
   `## Provenienza & limiti`). Mai per detection.
2. **Post-hoc only, mai in-sessione** (invariante R-SAA-8): l'analisi opera su
   sessioni **chiuse** (heuristica mtime + env var CLAUDE_SESSION_ID). Motivo:
   i file `<session-uuid>/subagents/*.jsonl` sono in append durante l'esecuzione
   — letture in-sessione producono race condition (tail troncato, JSON parziale)
   e circolarità (l'analizzatore si include nel campione).
3. **Read-only + confinamento scrittura in `raw/`** (R-SAA-1, R-SAA-2): mai
   scrittura in `~/.claude/`, `code_path`, `wiki/` (eccetto append `wiki/log.md`).
   L'unico output è `raw/YYYY-MM-DD-session-analysis-<id-8char>.{md,json}`.
4. **Redazione PII non negoziabile** (R-SAA-3): strip path assoluti utente,
   email (tranne owner), credential shapes (regex `sk-*`, `Bearer *`, `.env`),
   body di `tool_result`. `evidence_excerpt` cap 200 char con marker
   `[TRUNCATED]`.
5. **Nessun auto-fix, nessun ingest wiki automatico** (R-SAA-5, R-SAA-6): il
   report ha frontmatter invariante `ingest_eligible: false`,
   `wiki_ingest_policy: incidents-only`, `ttl_days: 90`. Ogni raccomandazione è
   testuale — mai `auto_apply`. L'azione è sempre umana o delegata a
   fleet-doctor (che ha propri gate G1-G11).
6. **Anti-fabbricazione via provenance** (R-SAA-7): ogni anomalia DEVE avere
   `provenance: {source_field, source_file}` valorizzato — traccia esatta al
   campo del tool che l'ha prodotta. Se una regola non riesce a citare la
   source → skip l'anomalia (fail-loud su stderr, mai emettere anomalia
   fabbricata).
7. **Schema-version guard** (R-SAA-9): il walker deve mantenere un
   `SUPPORTED_CC_VERSIONS` esplicito. Versione ignota → modalità degradata con
   WARNING fail-loud (mai parsing "best effort" silenzioso). Fixture di
   transcript reale versionata in `tests/fixtures/transcripts/` + contract-test
   che rompe se lo schema drifta.
8. **Kill criterion §23.8 obbligatorio pre-codice** (R-SAA-10): la capability
   dichiara `sunset_condition:` nel frontmatter TSK dell'EP prima
   dell'implementazione. Soglie oggettive misurate ex-post: <N anomalie
   azionabili per periodo → sunset automatico senza bypass.

### Architettura di riferimento (thin-agent / fat-skill / deterministic-tools, §29)

```
Comando (/session-analysis)
    → Skill (session-analysis-protocol.md, 5 fasi)
        → Tool chain deterministica Python stdlib-only:
            → parse-transcript.py    (fan-in main + subagents, normalize, redaction, R-SAA-8 gate)
            → fleet-metrics.py       (rollup per-agente/modello/wave, pricing, dispatch_efficiency)
            → detect-anomalies.py    (regole deterministiche → anomalie con provenance)
            → generate-report.py     (dual md+JSON in raw/, frontmatter canonico, 7 sezioni obbligatorie)
        → Handoff advisory verso fleet-doctor (§36) via campo fleet_recommendations
```

**Perché tool separati e non un unico script**: ogni tool è testabile in
isolamento con fixture, riusabile in altre pipeline (es. debug ad-hoc), e
sostituibile (chi vuole detector custom sostituisce solo `detect-anomalies.py`).

### Tassonomia anomalie v1 (deterministica, adapter-agnostic)

3 categorie **core** enabled by default:

- **ERROR**: pattern testuali `(?i)error|failed|fatal` in `stop_reason` (NON il
  flag `is_error` — invariante rilevato: sempre 0 su Claude Code 2.1.258).
- **BUDGET**: `session_totals.cost_usd_approx ≥ budget.max_cost_usd`; tier
  mismatch (opus per task con `token_out < 500`).
- **DISPATCH**: stesso agent invocato >2 volte in stessa wave; wave con
  `dispatch_efficiency.score < 0.5` (parallelismo non sfruttato).

2 categorie **opt-in roadmap** (`--enable-latency`, `--enable-fleet`):

- **LATENCY**: straggler (`p85_elapsed_ms > 2 × mediana per tipo agente`).
- **FLEET**: skill citata in `Agent` tool_call ma non trovata in
  `.claude/skills/`.

Scope numerico e naming sono empirici (misura signal/noise su fixture reali;
ferma tassonomia dove signal/noise ≥ soglia). Categorie escluse dalla v1
(SAA-V/C/G/O/S, GOVERNANCE) restano roadmap fino a evidenza di segnale reale.

### Boundary con altri layer

| Layer | Ruolo | Confine con Session Observability |
|---|---|---|
| Token Ledger EP-022 (`show-session-tokens.py`) | Cattura cheap in-session/on-Stop | Session Observability legge ledger + arricchisce con analisi anomalie post-hoc |
| Analytics EP-009/010 (`analytics-reporter`) | Aggregati economico-progettuali (per-TSK, per-wave, per-sprint) | analytics-reporter = **writer** di `analytics/events/`; session-analyst = **reader**. Ortogonali, due agenti, stessa fonte. |
| Fleet Doctor EP-060 (§36) | Refactor statico skill/agenti | session-analyst produce `fleet_recommendations` advisory; fleet-doctor consuma opzionalmente. Flusso unidirezionale. Mai auto-invoke. |
| Code Reviewer CQRL EP-002/012 (§19) | Qualità codice per-TSK | Confine netto: CQRL su diff codice; session-analyst su transcript agentico. |
| Wiki Keeper (§35) | Ingest wiki | `ingest_eligible: false` invariante: report session-analysis MAI ingeriti in wiki (evita loop di auto-analisi). Pattern aggregabili in `wiki/patterns/` solo con gate umano esplicito. |

### Prerequisito hard: telemetry integrity (EP-062)

Il pattern §37 non è affidabile senza un walker che catturi correttamente
l'attività dei sub-agenti dell'adapter attivo. Su Claude Code 2.1.258+ i
sub-agenti vivono in `<session-uuid>/subagents/agent-*.jsonl` (directory
separata), non nel JSONL principale. Il campo `isSidechain` è `false` ovunque
nel main → attribuzione via `isSidechain` produce cecità sul 60%+ dell'attività.
EP-062 Fleet Telemetry Hardening ripara il walker + aggiunge schema-guard +
fixture + contract-test. Precondizione **hard** per EP-061.

Adapter diversi (Cursor, Aider…) forniranno il proprio walker equivalente.
Il pattern §37 è agent-agnostic: la skill invoca il walker come contratto
di interfaccia (input: transcript path; output: JSON normalizzato con
attribuzione main/subagent).

### Riferimenti

- **Blackboard TR-c4e8f1b2**: `wiki/decisions/tavola-rotonda-c4e8f1b2-...-2026-09-08.md`
- **Wiki concept**: `wiki/concepts/session-agentic-analyser.md`
- **Runbook handoff**: `wiki/runbooks/session-analysis-fleet-doctor-handoff.md`
- **Precedente diagnosi**: `analytics/ANALYTICS-DIAGNOSIS.md` (TSK-407 EP-049, TSK-549 EP-062)
- **Test contract**: `tests/test_harvest_contract.py` (7 test EP-062), `tests/test_session_analysis_e2e.py` (10 test EP-061)
