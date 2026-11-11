---
name: interaction-drive-protocol
description: >-
  Skill interna per l'esecuzione di passi di interazione Playwright scriptati. Vocabolario 6 azioni: click/type/set_input_files/wait_for/wait_ms/keyboard. Consumatori: functional-oracle-protocol + visual-oracle-protocol. Bash + Playwright, niente MCP.
---
# Protocollo Interaction Drive — esecuzione Playwright scriptata condivisa

Skill **interna condivisa** (single source of truth) per l'esecuzione di una sequenza di
passi di interazione su un'applicazione target via Playwright headless. Estrae la logica di
«drive interaction» in modo che sia riutilizzabile da tutti i consumer che guidano il browser
in modo scriptato — senza duplicare il runtime Playwright né il vocabolario di azioni.

Analoga a `screenshot-capture-protocol` (ADR-017) per la cattura: quella skill è
single-source per gli screenshot, questa è single-source per l'interazione.

Questa skill **non gestisce il ciclo di vita del browser**: il caller apre il browser,
naviga al target, e passa il `page_context` aperto. La skill esegue i passi e ritorna
un trace; il caller è responsabile del teardown. Niente MCP: usa lo stesso meccanismo
Bash + script runner di EP-005 (ADR-008), runner in `.factory-runners/` (gitignored).

Riferimenti: ADR-066 §B (single source per l'interazione Playwright, skill condivisa
functional-oracle ↔ visual-oracle), ADR-017 (analogia con screenshot-capture-protocol,
pattern refactor non distruttivo), ADR-008 (Playwright via Bash, no MCP, runner in
`.factory-runners/`, fail-loud su prerequisito mancante).

[^src: design_&_architecture/decisions/ADR-066.md §B §C]
[^src: design_&_architecture/decisions/ADR-017.md §Decisione]
[^src: design_&_architecture/decisions/ADR-008.md §Decisione]

---

## Contratto di invocazione

```
drive_scenario(steps: ScenarioStep[], page_context)

  steps:        ScenarioStep[]   # array di { action: string, ...params }
                                 # vedi §Vocabolario azioni per lo schema per azione
  page_context: PlaywrightPage   # handle di una Page Playwright già aperta dal caller;
                                 # il caller ha già navigato al target e imposta il CWD
                                 # corretto prima della chiamata (ADR-064 §D — vedi §CWD)

  returns:
    trace:  StepTrace[]          # un entry per step eseguito (vedi §Trace)
    errors: string[]             # lista di errori non fatali (passi skippati / avvisi);
                                 # un passo fatale causa STOP prima di popolare errors
```

### Tipo `ScenarioStep`

```
ScenarioStep:
  action: string          # uno dei 6 valori nel §Vocabolario azioni
  selector?: string       # richiesto da: click, type, set_input_files, wait_for
  value?: string | number # richiesto da: type (string), wait_ms (number)
  files?: string[]        # richiesto da: set_input_files — lista path assoluti o relativi al CWD
  state?: string          # richiesto da: wait_for — "visible" | "hidden" | "attached" | "detached"
  timeout_ms?: number     # usato da: wait_for (default: 30000 ms se omesso)
  key?: string            # richiesto da: keyboard — es. "Enter", "Tab", "Escape"
```

### Tipo `StepTrace`

```
StepTrace:
  step_index: number      # indice 0-based nel array steps
  action: string          # azione eseguita
  status: "ok" | "error"  # esito del passo
  duration_ms: number     # tempo di esecuzione del singolo passo
  detail?: string         # messaggio opzionale (diagnostico su errore, url, selector risolto)
```

---

## Vocabolario azioni (set chiuso — 6 azioni)

| Azione | Parametri richiesti | Descrizione |
|---|---|---|
| `click` | `selector` | click su elemento identificato dal selettore CSS / test-id |
| `type` | `selector`, `value` (string) | cancella il campo e digita il valore (equivale a `fill` in Playwright) |
| `set_input_files` | `selector`, `files` (array di path) | carica uno o più file tramite un `<input type="file">` (usato per le fixture — vedi §Gestione fixture) |
| `wait_for` | `selector`, `state` (`visible`\|`hidden`\|`attached`\|`detached`), `timeout_ms` (opzionale) | attende che l'elemento raggiunga lo stato atteso entro il timeout (default 30 000 ms) |
| `wait_ms` | `value` (number) | pausa fissa in millisecondi — usare con parsimonia (preferire `wait_for`) |
| `keyboard` | `key` (string) | pressione di un tasto speciale, es. `"Enter"`, `"Tab"`, `"Escape"`, `"ArrowDown"` |

Il vocabolario è **chiuso**: nessuna azione al di fuori di queste 6 è supportata.

---

## Fail-loud su azione non riconosciuta

Se uno step ha `action` non presente nel vocabolario, la skill si ferma **immediatamente**
prima di eseguire qualsiasi passo successivo. Messaggio canonico **verbatim**:

```
[INTERACTION-DRIVE] azione '<action>' non supportata. Azioni disponibili: click | type | set_input_files | wait_for | wait_ms | keyboard.
```

Nessun degrado silenzioso: uno step con azione ignota indica un errore di schema
nell'`acceptance-spec` o nella `interaction_test_spec` e deve essere corretto alla fonte.

---

## Logica interna (Playwright headless via Bash)

1. Genera/riusa uno **script runner Bash** in `.factory-runners/` (cartella **gitignored**,
   non inquina il code_path — ADR-008 §Rationale 2). Lo script pilota Playwright **via Bash**,
   **NON un MCP tool** (ADR-008 §Decisione: «niente MCP custom»).
2. Lo script riceve in input una rappresentazione serializzata degli `steps` (JSON) e il
   `page_context` handle aperto dal caller; itera sul array e applica la primitiva Playwright
   corrispondente:

   | Azione | Primitiva Playwright |
   |---|---|
   | `click` | `page.click(selector)` |
   | `type` | `page.fill(selector, value)` |
   | `set_input_files` | `page.setInputFiles(selector, files)` |
   | `wait_for` | `page.waitForSelector(selector, { state, timeout: timeout_ms })` |
   | `wait_ms` | `page.waitForTimeout(value)` |
   | `keyboard` | `page.keyboard.press(key)` |

3. Per ogni passo, registra: `step_index`, `action`, `status`, `duration_ms`. In caso di errore
   Playwright (elemento non trovato, timeout), registra `status: "error"` + `detail` con il
   messaggio dell'eccezione e **STOP** (non continua i passi successivi — fail-loud §ADR-008).
4. Ritorna l'intero `trace` al caller.

---

## CWD di esecuzione (ADR-064 §D)

Lo script runner fa `require('playwright')`, che risolve da `node_modules` **della CWD**.
Il **caller** deve impostare il CWD al package target (dove `package.json` installa Playwright)
**prima** di invocare la skill. Eseguirla dalla CWD sbagliata produce
`Cannot find module 'playwright'`: è un **errore tecnico fail-loud** (exit != 0), non un
degrado silenzioso. Idem per la versione Node: allinea al `.nvmrc` del target.

Responsabilità del caller:

1. Risolvi il `code_path` / package target da `factory.config.yaml`.
2. Imposta il CWD a quella directory prima di invocare lo script runner.
3. Verifica che Playwright sia installato (vedi §Fail-loud su Playwright mancante).

---

## Fail-loud su Playwright mancante

Se Playwright non è disponibile nel project host → **STOP fail-loud**, nessun degrado
silenzioso (ADR-008 §Rationale 5). Messaggio azionabile **verbatim**:

> Interaction drive richiede Playwright. Eseguire: `npm i -D @playwright/test && npx playwright install --with-deps chromium`. Vedi runbook `wiki/runbooks/visual-oracle-installation.md` se disponibile.

---

## Gestione fixture

Le fixture sono file di input reali (ROM, audio, immagini, testo) caricati tramite
`set_input_files` nei passi dello scenario.

### Convenzione path

- Path canonico nel progetto: `<package>/public/test-fixtures/` oppure `test-fixtures/`
  alla radice del progetto.
- Referenziate nell'`acceptance-spec` con **path relativo al progetto** (non assoluto,
  non relativo al repo factory).
- Esempio: `packages/app/public/test-fixtures/test-rom.gba`.

### Fail-loud su fixture mancante

Se al momento dell'esecuzione il file fixture referenziato nello scenario non esiste al path
dichiarato → **fail-loud** prima di tentare `set_input_files`. Messaggio canonico **verbatim**:

```
[FUNCTIONAL-ORACLE] fixture mancante: '<path>' dichiarata in acceptance-spec non trovata. Verificare il path o aggiungere il file.
```

Mai ignorare silenziosamente una fixture mancante: potrebbe mascherare un test parziale
(ADR-065 §B, §E — stessa filosofia anti-fabbricazione).

### Preflight check (Fase 2 di `functional-oracle-protocol`)

La verifica dell'esistenza delle fixture avviene **prima** dell'esecuzione dello scenario:
`functional-oracle-protocol` esegue un **preflight check** nella propria Fase 2 — itera
su tutti i `files` referenziati nelle azioni `set_input_files` dell'`acceptance-spec` e
verifica che i path esistano. Se uno o più file sono assenti, emette il messaggio canonico
verbatim (sopra) e **STOP** prima di aprire il browser o eseguire qualsiasi passo. In questo
modo il fail-loud avviene al momento più precoce possibile, con diagnostica chiara e senza
lasciare processi browser in sospeso.

### .gitignore — blocco template per fixture binarie

I file di fixture binari di grandi dimensioni (ROM, file audio/video, bin) devono essere
esclusi dal repository con pattern `.gitignore` appropriati. Il template framework pubblica
nel `.gitignore` del progetto il blocco commentato seguente (il progetto lo completa con
i propri pattern):

```
# Fixture binarie per functional oracle (es. ROM, audio, video) — escludere per dimensione
# test-fixtures/*.rom
# test-fixtures/*.gba
# **/test-fixtures/*.bin
```

### Nota licenze fixture

Le fixture usate nell'`acceptance-spec` devono avere una licenza **compatibile con l'uso
in test automatizzati**:

- Esempi accettabili: ROM homebrew legalmente distribuibili (public domain o licenza
  permissiva esplicita), file CC0/MIT, screenshot o file generati dall'app stessa.
- **Mai** includere ROM o file coperti da copyright commerciale: la distribuzione di ROM
  di giochi commerciali è illegale anche a fini di test. Usare esclusivamente homebrew/freeware
  con licenza esplicita o file prodotti dal progetto stesso.
- Il **framework non verifica le licenze**: è responsabilità esclusiva del progetto
  selezionare fixture con licenza adeguata.
- Il progetto è invitato a documentare la scelta in un file `FIXTURE-NOTICE.md` nella
  cartella `test-fixtures/` (opzionale, non verificato dal lint).

---

## Consumatori

| Consumer | EP / US | Uso |
|---|---|---|
| `functional-oracle-protocol` | EP-018 | Fase 3 — esegue gli `steps` dell'`acceptance-spec` app-level (ADR-065 §B); single consumer primario |
| `visual-oracle-protocol` / US-020 | EP-005 | Migrazione opzionale e non distruttiva dell'interaction step sul runtime condiviso (ADR-066 §C — refactor opzionale, EP-005 già done, nessuna regressione forzata) |

La migrazione di EP-005 US-020 su questa skill è **opzionale**: EP-005 può continuare a
gestire l'interaction step inline. Il refactor non distruttivo è possibile in futuro se il
team EP-005 lo ritiene conveniente (stesso pattern di ADR-017 per la cattura).

---

## Pattern

- **ADR-066 §B** — single source of truth per l'interazione Playwright scriptata: una sola
  infrastruttura di «drive interaction» nel framework, un solo punto dove correggere bug /
  aggiungere azioni / gestire il fail-loud. Coupling intenzionale e positivo EP-018 ↔ EP-005
  (DRY al livello dell'operazione semantica, non della riga). Analoga a `screenshot-capture-protocol`
  (ADR-017) per la cattura.
- **ADR-017** — il pattern della skill interna condivisa già validato da `screenshot-capture-protocol`:
  estrai l'operazione atomica in una skill, i consumer la invocano con i propri parametri. Refactor
  non distruttivo: l'API esterna dei consumer resta invariata.
- **ADR-008** — Playwright via Bash, no MCP custom; runner generati in `.factory-runners/`
  (gitignored); fail-loud su prerequisito mancante.

[^src: design_&_architecture/decisions/ADR-066.md §B §C]
[^src: design_&_architecture/decisions/ADR-017.md §Rationale]
[^src: design_&_architecture/decisions/ADR-008.md §Rationale]
