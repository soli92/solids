# Pattern e ADR di riferimento

**Ambito**: pattern architetturali istanziati (evaluator-optimizer, fail-closed,
single-source, side-channel riuso CQRL), tabella ADR vincolanti.
Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## evaluator-optimizer ([[evaluator-optimizer]])

Questa skill è un'istanza esplicita del pattern `evaluator-optimizer`:
- **Producer** (`qa-dev`): esercita l'app reale (fase produttiva: Serve → Drive Scenario).
- **Engine deterministico**: valuta gli esiti (fase di asserzione: Assert Outcomes —
  asserzioni binarie, mai LLM nel path decisionale).
- **Critic LLM**: aggiunge osservazioni advisory senza alterare il verdict.
- **Loop bounded**: `conditional` → re-Develop → functional-oracle iter N+1, max
  `max_iterations`.

Stessa famiglia di pattern già istanziata da:
- `visual-oracle-protocol` (EP-005): producer = `fe-dev` scrive il codice; evaluator =
  critic visivo LLM; loop bounded `fe_correctness.max_iterations`.
- `code-review-protocol` (CQRL, PATTERN §19): producer = dev-agent sviluppa; evaluator
  = `code-reviewer` su regole; loop bounded `code_quality.max_iterations`.

**Differenza chiave**: il verdict è **deterministico** (asserzioni binarie). Nel visual
oracle il critic LLM *è* il verdict; qui è solo advisory dopo un verdict già calcolato
(ADR-067 §B). Massima difesa anti-fabbricazione.

Ordering nel cascade (ADR-066 §Conseguenze): `develop → visual-oracle → functional-oracle → review`.

## fail-closed (anti-fabbricazione, [[fail-closed]])

Verdict nasce **esclusivamente** da asserzioni binarie deterministiche (ADR-065 §C).
Nessun LLM nel path di `pass`/`fail`. Un esito senza evidenza deterministica non può
essere `pass` (ADR-063 §B evidence-provenance obbligatoria per ogni finding critic).
Traiettoria: ADR-063 → ADR-064 → ADR-065 → ADR-067.

## single-source per riga di runtime

Nessuna logica di runtime è inline in questa skill:
- **Serve** dell'app → ADR-064 Step 1.0 (app-lifecycle serve, unico punto di verità
  per il ciclo di vita del server).
- **Interazione Playwright** → `interaction-drive-protocol` (ADR-066 §B, single source
  of truth per il runtime di interazione).
- **Cattura screenshot** → `screenshot-capture-protocol` (ADR-017, single source of
  truth per il runtime di cattura).

Questo evita duplicazione, deriva, e facilita l'aggiornamento indipendente di ciascuna
componente di runtime.

## side-channel report (riuso CQRL + visual-oracle)

Report in `code_quality/reports/<TSK-id>-functional-iter-<N>.{json,md}` — stesso
side-channel di CQRL (`<TSK-id>-iter-<N>.{json,md}`) e visual oracle
(`<TSK-id>-visual-iter-<N>.{json,md}`). Lo slug `-functional-` distingue gli artefatti
senza conflitti di naming. Un solo path da configurare, gitignorare, e monitorare
(ADR-065 §Storage).

## Tabella ADR vincolanti

| ADR | Decisione vincolante per questa skill |
|---|---|
| `ADR-065` | Schema acceptance-spec (framework vs contenuto progetto); primitive domain-agnostic; semantica a severità blocking/advisory; storage frontmatter `functional_status:`; fail-loud §E |
| `ADR-066` | Runtime condiviso interazione Playwright → `interaction-drive-protocol`; ordering nel cascade; delega caricamento fixture |
| `ADR-067` | Esecutore = `qa-dev` in modalità functional-oracle (no nuovo agent); verdict DETERMINISTICO; critic LLM solo advisory; loop bounded `max_iterations` default 3 |
| `ADR-017` | `screenshot-capture-protocol` — single source of truth per cattura screenshot; riusato in Fase 3 per evidenza trace |
| `ADR-008` | Playwright via Bash (no MCP custom); runner in `.factory-runners/`; fail-loud su browser non disponibile |

[^src: design_&_architecture/decisions/ADR-067.md §Rationale — anti-fabbricazione strutturale]
[^src: design_&_architecture/decisions/ADR-066.md §Rationale — single-source per riga di runtime]
[^src: design_&_architecture/decisions/ADR-065.md §Storage — side-channel report]
[^src: design_&_architecture/decisions/ADR-008.md §Decisione — Playwright via Bash]
[^src: design_&_architecture/decisions/ADR-017.md §Decisione — screenshot-capture-protocol]
