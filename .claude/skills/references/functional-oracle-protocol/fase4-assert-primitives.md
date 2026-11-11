# Fase 4 — Assert Outcomes: primitive e critic

**Ambito**: §4.1 dispatch 8 primitive domain-agnostic, §4.1.1 canvas_pixel_variance,
§4.3 tabulazione risultati (esempio), §4.4 invocazione critic LLM (schema input/output
e `CriticFinding`). I vincoli §4.2 (verdict deterministico) e §4.4 (4 invarianti critic)
sono nel corpo principale di `functional-oracle-protocol.md`.
Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## §4.1 — Dispatch per `kind` (8 primitive domain-agnostic, ADR-065 §C)

Itera su `spec.assertions[]` nell'**ordine dichiarato**. Per ogni asserzione, dispatcha
su `kind` secondo la tabella:

| `kind` | Input richiesti | Check deterministico | Pass condition |
|---|---|---|---|
| `selector_visible` | `selector` | Playwright: `page.isVisible(selector)` | elemento visibile nel DOM al termine dello scenario |
| `selector_absent` | `selector` | Playwright: `!page.isVisible(selector)` | elemento assente o `display:none` |
| `attr_equals` | `selector`, `attr`, `value` | Playwright: `page.getAttribute(selector, attr) == value` (stringa esatta) | attributo ha il valore atteso |
| `text_matches` | `selector`, `value` (pattern) | Playwright: `page.textContent(selector)` contiene `value` (substring; se `/pattern/` → regex) | testo contiene il pattern |
| `canvas_pixel_variance` | `selector`, `min_variance`, `frames` | campionamento N screenshot del canvas a 500ms; varianza media pixel; vedi §4.1.1 | `var >= min_variance` |
| `storage_key_present` | `store` (`localStorage`\|`idb`\|`fs`), `key_glob` | evalua `localStorage.getItem(...)` / IDB key match / `fs.existsSync(path)` nella CWD del package | almeno una chiave che matcha `key_glob` esiste |
| `console_no_error` | — | conta righe `console_log` con `type == "error"` dalla `scenario_evidence` (Fase 3) | count == 0 |
| `network_no_5xx` | — | conta righe `network_log` con `status >= 500 AND <= 599` dalla `scenario_evidence` (Fase 3) | count == 0 |

Per ogni asserzione produce un record:

```
AssertionResult:
  id:       string        # dall'acceptance-spec
  kind:     string
  severity: "blocking" | "advisory"
  outcome:  "pass" | "fail"
  detail:   string        # valore trovato vs atteso, count, ecc.
```

### §4.1.1 — `canvas_pixel_variance`: procedura di campionamento

1. Riattiva il `page_context` (se chiuso in Fase 3, riaprire la pagina a `server_url`
   nello stesso stato — richiede che il server sia ancora attivo durante Fase 4).
2. Cattura `frames` screenshot del canvas identificato da `selector` a intervalli di
   500ms via `screenshot-capture-protocol` (ADR-017), naming `canvas-frame-{i}.png`
   nella cartella artefatti.
3. Calcola varianza media dei valori dei pixel tra frame consecutivi:
   `var = media(|px_i - px_{i-1}|)` per tutti i pixel, su tutti i frame adiacenti.
4. Pass se `var >= min_variance`; fail con `detail: "varianza calcolata: <N>, attesa >= <min_variance>"`.

## §4.3 — Tabulazione risultati (esempio)

```
| id | kind | severity | outcome | detail |
|---|---|---|---|---|
| canvas-advancing | canvas_pixel_variance | blocking | pass | varianza: 0.034, attesa >= 0.02 |
| state-running    | attr_equals           | blocking | pass | data-state="running" ✓ |
| no-console-error | console_no_error      | advisory | fail | 2 errori console trovati |
| save-artifact    | storage_key_present   | blocking | pass | chiave "savestate:slot0" in IDB |

Blocking: 3/3 pass | Advisory: 0/1 pass (1 fallita, soglia 2)
Verdict: pass
```

## §4.4 — Critic LLM: invocazione e schema

Eseguita SOLO se `fe_correctness.functional_oracle.critic == "advisory"`.
Se `critic: "off"` → salta interamente, nessun costo LLM aggiuntivo.
Le 4 invarianti che il critic NON può violare sono nel corpo principale.

**Invocazione**:

```
critic_input:
  screenshots:     scenario_evidence.screenshots   # path PNG ordinati per step
  console_log:     scenario_evidence.console_log   # filtrati a error+warning
  network_log:     scenario_evidence.network_log   # tutte le richieste
  assertions:      spec.assertions
  verdict_summary: <calcolato in §4.2>

critic_output:
  open_questions: CriticFinding[]
```

**Schema `CriticFinding`**:

```
CriticFinding:
  observation:    string    # osservazione qualitativa concisa
  evidence_ref:   string    # OBBLIGATORIO: path artefatto reale
                            # (es. "step-03-wait_for.png", "console.log.json:line 7",
                            #  "network.log.json:entry 12")
  severity:       "advisory"   # SEMPRE advisory; mai "blocking" o "pass"
```

**Regola di ammissibilità**: un finding senza `evidence_ref` che punta a un artefatto
reale nella cartella `code_quality/reports/<TSK-id>-functional-iter-<N>/` è **scartato**
prima di essere incluso nel report (anti-fabbricazione ADR-063 §B). Se il critic produce
solo finding senza evidenza → `open_questions: []` (nessun finding ammissibile).

## Output prodotto

```
assertion_results:
  results:          AssertionResult[]
  verdict_summary:  VerdictSummary       # §4.2 — calcolato nel corpo principale
  open_questions:   CriticFinding[]      # vuoto se critic: off o no finding ammissibili
```

[^src: design_&_architecture/decisions/ADR-065.md §C — primitive domain-agnostic]
[^src: design_&_architecture/decisions/ADR-065.md §D — semantica blocking/advisory]
[^src: design_&_architecture/decisions/ADR-067.md §B — critic solo advisory, no verdict]
[^src: design_&_architecture/decisions/ADR-063.md §B — evidence-provenance obbligatoria]
