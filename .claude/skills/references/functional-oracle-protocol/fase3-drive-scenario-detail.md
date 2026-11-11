# Fase 3 — Drive Scenario: procedura dettagliata

**Ambito**: §3.1 verifica prerequisito, §3.2 apertura browser e intercettazione log,
§3.3 esecuzione scenario via `interaction-drive-protocol`, §3.4 cattura screenshot
via `screenshot-capture-protocol`, §3.5 chiusura log e produzione `scenario_evidence`.
Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## §3.1 — Verifica prerequisito `interaction-drive-protocol`

Verifica che `.claude/skills/interaction-drive-protocol.md` esista. Se assente →
**STOP fail-loud verbatim**:

> Functional oracle: skill `interaction-drive-protocol` non trovata al path
> `.claude/skills/interaction-drive-protocol.md`. La skill è un prerequisito obbligatorio
> (ADR-066 §B). Eseguire il bootstrap o aggiornare la factory per includere EP-018.

Nessun degrado silenzioso: senza `interaction-drive-protocol` la delega dell'interazione
non è possibile (ADR-066 §B).

## §3.2 — Apertura browser e intercettazione log

1. Apri un contesto browser Playwright headless con CWD = directory del package target
   (ADR-064 §D). Naviga a `server_url`.
2. Inizia l'intercettazione dei log **dalla navigazione iniziale**:
   - **Console log**: registra tutti gli eventi `page.on('console')` di livello `error` e
     `warning`. Per ogni evento: `{ type, text, timestamp_ms }`.
   - **Network log**: registra tutte le richieste `page.on('request')` e risposte
     `page.on('response')`. Per ogni coppia: `{ url, method, status, duration_ms }`.
   L'intercettazione prosegue fino alla fine dello scenario (incluse azioni asincrone
   post-ultimo step).

## §3.3 — Esecuzione scenario via `interaction-drive-protocol`

Invoca la skill `interaction-drive-protocol` con il contratto seguente:

```
drive_scenario(
  steps        = spec.scenario,        # array ScenarioStep[] dall'acceptance-spec (ADR-065 §B)
  page_context = <handle Page aperto al passo 3.2>
)
returns:
  trace: StepTrace[]   # { step_index, action, status, duration_ms, detail? }
  errors: string[]     # errori non fatali (passi skippati / avvisi)
```

**Nessuna logica di interazione Playwright è inline in questa skill.** Tutta l'esecuzione
dei passi (click, type, set_input_files, wait_for, wait_ms, keyboard) avviene dentro
`interaction-drive-protocol`. Questa skill si limita a passare `spec.scenario` e
raccogliere il `trace`.

Se `interaction-drive-protocol` ritorna con un passo `status: "error"` → il trace è
comunque salvato (§3.4) e la Fase 4 valuta le asserzioni sul trace parziale. Alcuni
`selector_visible`/`attr_equals` falliscono deterministically → `reject` senza ambiguità.

## §3.4 — Cattura screenshot via `screenshot-capture-protocol`

Dopo ogni step che modifica lo stato UI (azioni `click`, `type`, `set_input_files`,
`keyboard` + ogni `wait_for` con `status: "ok"`) invoca `screenshot-capture-protocol`
(ADR-017):

```
capture_screenshot(
  target      = server_url,
  viewport    = { width: 1280 },
  output_dir  = "code_quality/reports/<TSK-id>-functional-iter-<N>/",
  naming_pattern = "step-{step_index}-{action}.png"
)
```

Naming convention: `step-00-click.png`, `step-01-wait_for.png` (indice 0-padded a 2
cifre per ordinamento alfabetico corretto fino a 99 step).

Gli screenshot sono **evidenza del trace**, non input per asserzione visiva (EP-005):
usati dalla Fase 4 dal critic LLM advisory (§4.4) e inclusi nel report della Fase 5.

## §3.5 — Chiusura log e produzione `scenario_evidence`

Al termine dell'esecuzione (ultimo step del `trace` o STOP su errore fatale):

1. Termina l'intercettazione dei log.
2. Salva i log come artefatti nella cartella side-channel:
   - `code_quality/reports/<TSK-id>-functional-iter-<N>/console.log.json` — array di
     `{ type, text, timestamp_ms }` filtrati a `error` e `warning`.
   - `code_quality/reports/<TSK-id>-functional-iter-<N>/network.log.json` — array di
     `{ url, method, status, duration_ms }` per tutte le richieste del ciclo.
3. Chiudi il contesto browser Playwright. Il teardown del browser è responsabilità di
   questa skill (non di `interaction-drive-protocol`, che non gestisce il lifecycle).

## Output prodotto

```
scenario_evidence:
  trace:             StepTrace[]    # da interaction-drive-protocol
  screenshots:       string[]       # path PNG ordinati per step_index
  console_log:       ConsoleLine[]  # filtrati a error+warning
  network_log:       NetworkEntry[] # tutte le richieste del ciclo
  console_log_path:  string         # path JSON side-channel
  network_log_path:  string         # path JSON side-channel
```

**Criterio**: `trace` disponibile (anche parziale su errore fatale); `console_log_path`
e `network_log_path` scritti sul filesystem; browser chiuso.

[^src: design_&_architecture/decisions/ADR-066.md §B — single source runtime interazione]
[^src: design_&_architecture/decisions/ADR-017.md §Decisione — screenshot-capture-protocol]
[^src: design_&_architecture/decisions/ADR-064.md §D — CWD del package target]
[^src: management/kanban/EP-018-fe-functional-oracle/US-068-skill-functional-oracle-protocol/US-068.md §Fase 3]
