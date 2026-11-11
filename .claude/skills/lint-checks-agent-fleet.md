---
skill: lint-checks-agent-fleet
part_of: lint-checks (modular)
family: agent-fleet
parent: lint-checks
description: "Check lint sulla flotta agentica — dimensione unità di contesto, igiene skill/agenti, roll-up di stato — check-family agent-fleet"
---

# Lint Checks — Agent Fleet

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 4ap (unità di contesto agentica sopra soglia, WARNING-only, EP-060 opt-in),
> Check 4at (disciplina d'ingresso di una capability — divieto, ERROR, always-on, EP-065/US-278),
> Check 4au (roll-up di stato TSK→US→epica — WARNING-only, always-on, EP-068/US-296)

Check ordinati per severità: ERROR → WARNING → INFO.

---

## Check 4at — Disciplina d'ingresso di una capability (ERROR)

**Severità**: `error`. **Trigger**: **always-on**, nessun flag lo gatea — la regola governa
*l'ingresso* di una capability, quindi non può dipendere dal flag della capability che entra.
**Esecutore deterministico, exit code nel path**: `pytest tests/test_fleet_contract.py -k asse4`
(estensione della famiglia di US-271; nessun predicato riscritto).

[^src: management/kanban/EP-065-sanatoria-della-flotta/US-278-pattern-238-regola-negativa/US-278.md §AC1..§AC10]
[^src: PATTERN.md §23.8 — condizione di falsificazione]
[^src: factory.config.yaml — complexity_budget.sunset_falsification_days]

### La regola è un DIVIETO, non un permesso

> Una capability nel **bucket di ingresso** è **in violazione** se ha una **sezione
> `PATTERN.md`**, una **invariante §7**, un **lint check**, un **runbook** o una **concept page**.

«Un permesso si concede; un divieto **si viola**, ed è la violazione che un check può vedere.»
Un flag spento **non esenta da nessuno degli artefatti di cerimonia**: `enabled: false` è un
interruttore di runtime, **non uno stadio di maturità**.

### Perché ERROR e non WARNING — la ragione è misurata, non preferita

Check 4ap è acceso dal **2026-09-04**, spara su **32 unità** e in **17 giorni** ha prodotto
**zero refactor**. Il WARNING su questa flotta non è debole: è **dimostrato inerte**, e sarebbe
il quinto — dopo il complexity budget mai vincolante, il release gate bypassato 3×, Ponytail
non misurato, 4ap inerte.

### Algoritmo — deterministico, nessun LLM nel path del verdetto

1. **capability** = ogni chiave **top-level** di `factory.config.yaml` il cui blocco contiene una
   riga `enabled:`. Lettore: `yaml_scalare` di `tools/fleet-observer/observe.py` (importato, non
   riscritto).
2. `bucket_ingresso = capability − allowlist` (§Allowlist di grandfathering, sotto).
3. Per ogni chiave del bucket, con gli alias `chiave` e la sua forma con trattini, cerca le cinque
   classi di cerimonia:

   | classe | dove si cerca |
   |---|---|
   | sezione `PATTERN.md` | corpo di una sezione `##` di `PATTERN.md`, escluso il changelog §21 |
   | invariante §7 | corpo di una regola numerata dell'elenco canonico di §7 |
   | lint check | `.claude/skills/lint-checks*.md` |
   | runbook | nome o contenuto di un file sotto `wiki/runbooks/` |
   | concept page | nome o contenuto di un file sotto `wiki/concepts/` |

4. **≥1 classe trovata → ERROR**, una riga per capability con le classi e i file che la provano.
5. **Condizione di falsificazione** (PATTERN §23.8): una capability accesa che non produce
   artefatti misurabili entro `complexity_budget.sunset_falsification_days` giorni
   dall'attivazione è **candidata a sunset alle stesse condizioni di una capability non adottata**.
   Il conteggio si legge da `python3 tools/fleet-observer/observe.py --load` — metrica di record
   unica — **non dalla memoria di qualcuno**. Corollario enforced: la **riaccensione** di una
   capability spenta per assenza di esercizio è **ERROR** finché quella metrica resta a zero. Si
   blocca la **riaccensione del flag**, mai l'unità.
6. Il check **non scrive niente**: nessun auto-fix, nessun `git checkout`, nessun revert (R.S5).

### Come si applica oggi a EP-060

`refactor_agent_skills` è stata accesa il **2026-09-04** e al **2026-09-21** aveva prodotto zero
refactor conformi: **17 giorni > N**, quindi era candidata a sunset. La condizione **si è
soddisfatta spegnendola**, e questo non è un difetto — **è il rimedio**: una capability accesa e
mai esercitata è **un'affermazione falsa** della factory, e §23.8 esiste per rendere vere le
affermazioni della factory. Da qui in avanti il finding è sulla **riaccensione**.

Questa è anche la risposta alla tesi avversaria di `mattpocock/skills` («owning the process makes
bugs in the process hard to resolve»): **ne accetta il criterio invece di negarlo**. Per questo
`PATTERN.md` non contiene nessuna replica (una difesa scritta nella spec aggiunge massa nel
documento la cui dimensione è l'accusa).

### Allowlist di grandfathering — CONGELATA IN SOLA DIMINUZIONE

**Perché è necessaria**: **EP-061 la viola in massa**. `session_analysis` è stata spedita a flag
spento **con** `PATTERN.md` §37, un runbook, una concept page, 10 invarianti locali R-SAA-1..10, un
JSON Schema Draft 2020-12, 4 tool e una skill — **più un kill criterion che ammette che potrebbe
non valere nulla**. «Ho confuso un interruttore di runtime con uno stadio di maturità.»

**Non è un costo aggiuntivo**: la lista è un **sottoprodotto del check** — è l'insieme che il
passo 1 dell'algoritmo calcola sul commit di congelamento.

**Regola di sola diminuzione — scritta, non implicita**:

- una voce si **cancella**, mai si **aggiunge**. Aggiungerne una è a sua volta una violazione.
- il **tetto** è congelato **fuori da questo file**, in `tests/test_fleet_contract.py`
  (`ALLOWLIST_TETTO_CONGELATO`): il file del check **non può alzare il proprio tetto**, e una voce
  aggiunta qui rende **rosso** il contract test.
- una voce si cancella quando la capability scompare da `factory.config.yaml`, oppure quando la sua
  cerimonia viene rimossa. Da quel momento quella capability è soggetta al divieto come una nuova.
- il grandfathering **non è un'assoluzione**: esenta dal divieto d'**ingresso**, non dalla
  condizione di falsificazione del passo 5, che si applica a tutte.

**Deroghe registrate** (violazioni dichiarate della sola diminuzione, mai da un agente):

| Data | Voce | Tetto | Decisione | Ragione |
|---|---|---|---|---|
| 2026-10-06 | `pm_report` | 27 → 28 | committente (soli92), TSK-736 | accesa in questa factory perche' la plancia (EP-067) mostri il report PM di EP-070. Non e' un precedente: resta soggetta al passo 5 |

<!-- ALLOWLIST-GRANDFATHERING:INIZIO — sola diminuzione: si cancella, mai si aggiunge (congelata 2026-09-21; una deroga dichiarata, 2026-10-06: pm_report) -->
- a11y
- analytics
- capability_formativa
- code_intelligence
- code_paths
- code_quality
- compression
- content_share
- design_intelligence
- fe_correctness
- kanban_coordination
- mcp_server
- ponytail
- pm_report
- prototyping
- qa_layer
- refactor_agent_skills
- release_governance
- scheduler
- session_analysis
- tavola_rotonda
- temporal
- ux_ui
- vcs
- voice_channel
- wiki_lint
- wiki_search
- wiki_sweep
<!-- ALLOWLIST-GRANDFATHERING:FINE -->

### La sanzione è lo SVUOTAMENTO A STUB, non la cancellazione

Scaduti gli N giorni senza artefatti misurabili, la sanzione **non è cancellare** — cancellare a
robot su un meta-framework è lo scenario di fallimento del Critico, e serve un umano — **ma lo
svuotamento della `description:` a stub**: l'unità **resta su disco**, **esce dal carico
always-on** (la `description` si carica a ogni turno, il corpo no), e il finding diventa
**binario**: la `description` è uno stub, o non lo è. Lo svuotamento lo applica un TSK, **non**
questo check.

### LIMITE DICHIARATO E NON RIMEDIATO — dissenso 5 di EP-065

È stato **misurato** che Check 4ap non ha mai sparato **perché il runner non è mai partito**:
`/lint` **zero invocazioni in 17 giorni**, zero dispatch `Task(subagent_type=wiki-lint)`.

> **Un check ERROR su un runner che nessuno invoca è inerte quanto un WARNING.**

La severità ERROR è consegnata **sapendolo**. Il rimedio — far girare il runner — **non è in
scope di EP-065 e nessuna sua US lo affronta**. Mitigazione parziale, non equivalente: l'esecutore
del passo «Esecutore deterministico» è un test `pytest`, che gira in CI e in locale **senza**
passare dal runner del lint.

### Output format

```
## ERROR (disciplina d'ingresso, mai heal-eligible)
- [ERROR][capability-ingress][4at] <N> capability nel bucket di ingresso portano cerimonia.
  <chiave>: sezione PATTERN.md (§NN), runbook (<file>), concept page (<file>)
  Azione: rimuovere la cerimonia, oppure portare la capability a un artefatto di esercizio.
  L'allowlist di grandfathering NON si allarga (sola diminuzione).
- [ERROR][capability-reignition][4at] <chiave> riaccesa con metrica di esercizio a zero.
  Comando: python3 tools/fleet-observer/observe.py --load
```

### Scenari di verifica

| # | stato | esito atteso |
|---|---|---|
| 1 | capability nell'allowlist con cerimonia | nessun finding (grandfathering) |
| 2 | capability **fuori** allowlist con ≥1 classe di cerimonia | **ERROR** |
| 3 | capability fuori allowlist, zero cerimonia | nessun finding (l'ingresso è lecito) |
| 4 | allowlist con una voce **in più** del tetto congelato | **ERROR** (rosso del contract test) |
| 5 | allowlist svuotata | **ERROR** su tutte le capability con cerimonia (stato misurato: 27/27) |
| 6 | capability spenta per assenza di esercizio e **riaccesa** | **ERROR** finché la metrica è zero |

### Cross-link

4at → `PATTERN.md` §23.8 (sunset policy + condizione di falsificazione) +
`factory.config.yaml.complexity_budget.sunset_falsification_days` +
`tests/test_fleet_contract.py` (asse 4, esecutore) +
`tools/fleet-observer/observe.py` (metrica di record) + `wiki/concepts/complexity-budget.md`.

---

## Check 4ap — Unità di contesto agentica sopra soglia (WARNING-only)

**Severità**: `warning` (mai bloccante — R.FH2 opt-in).
**Trigger**: `refactor_agent_skills.enabled: true` in `factory.config.yaml`.
Se `enabled: false` (default), il check è **skip silente** (fail-open, R.FH3).

[^src: EP-060 US-231 AC3]
[^src: factory.config.yaml — refactor_agent_skills.thresholds]
[^src: tools/refactor/analizza_target.py]

### Algoritmo

1. Leggi `factory.config.yaml`: se il blocco `refactor_agent_skills:` è assente O
   `refactor_agent_skills.enabled != true` → **skip silenzioso** (no-op totale, 0 WARNING).
2. Verifica esistenza di `tools/refactor/analizza_target.py`:
   - Se mancante → **skip silenzioso** con log INFO `[Check 4ap] tools/refactor/analizza_target.py
     assente — check saltato (R.FH3 fail-open)`. Non blocca la lint pipeline.
3. Leggi soglie da config (default se assenti): `error: 500`, `warning: 300`.
4. Per ogni file `.md` in `.claude/agents/` e `.claude/skills/` (escluse sottodirectory
   `evals/`, `references/refactor/` — le foglie non sono unità autonome ai fini di questo check):

   ```bash
   python3 tools/refactor/analizza_target.py <file>
   ```

   Estrarre il verdetto dal campo `verdict` dell'output:
   - `REFACTOR (>500)` → emette **WARNING** «Unità sopra soglia critica»
   - `VALUTARE` (300-500) → emette **WARNING** «Unità sopra soglia raccomandazione»
   - `ok` → nessun output

5. Aggrega i WARNING e presenta un riepilogo:
   ```
   [WARNING][agent-fleet-oversize][4ap] <N> unità sopra soglia: <lista-file>
   Azione: invocare /refactor <file> per avviare il protocollo di refactor conservativo
   tramite l'agente fleet-doctor. Nessuna azione automatica applicata.
   ```

### Azione suggerita

Invocare `/refactor <file>` per avviare il protocollo di refactor conservativo tramite
l'agente `fleet-doctor` (`.claude/agents/fleet-doctor.md`). Nessuna azione automatica
viene applicata: il check è puramente informativo.

### Anti-fabbricazione

Il check non stima costi, non promette risparmi, non applica modifiche. Segnala
solo l'evidenza numerica (`corpo N righe > threshold`).

### Invarianti

- **Warning-only**: mai ERROR — la capability è opt-in, una unità fuori soglia è
  recuperabile (R.FH2).
- **Fail-open**: se `tools/refactor/analizza_target.py` manca, skip silenzioso con
  log INFO — non blocca la lint pipeline (R.FH3).
- **No-op a flag spento**: factory con `refactor_agent_skills.enabled: false` (default)
  non vedono mai questo check (R.FH1, backward compat totale).
- **Read-only**: il check non modifica alcun file.
- **Never heal-eligible**: il refactor richiede approvazione umana (gate Fase 1).

### Output format

```
## WARNING (igiene, mai heal-eligible)
- [WARNING][agent-fleet-oversize][4ap] <N> unità sopra soglia.
  REFACTOR: [lista file >500 righe]
  VALUTARE: [lista file 300-500 righe]
  Azione: /refactor <file> per avviare il protocollo conservativo via fleet-doctor.
  Vedi wiki/runbooks/skill-hygiene.md
```

### Scenari di verifica

| # | `refactor_agent_skills.enabled` | script presente | esito atteso |
|---|---|---|---|
| 1 | assente / `false` (default) | — | no warning (gate off, R.FH1 — backward compat) |
| 2 | `true` | assente | log INFO skip (R.FH3 fail-open), lint pipeline prosegue |
| 3 | `true` | presente | nessuna unità fuori soglia → no warning |
| 4 | `true` | presente | unità 300-500 righe → WARNING «VALUTARE» |
| 5 | `true` | presente | unità >500 righe → WARNING «REFACTOR» |
| 6 | `true` | presente | più unità fuori soglia → un WARNING aggregato con lista |

### Cross-link

4ap → `factory.config.yaml.refactor_agent_skills` + EP-060 (Fleet Health) +
`wiki/runbooks/skill-hygiene.md` + PATTERN §36 (Refactor Skill Layer) +
skill `refactor-agent-skills.md` + agente `fleet-doctor.md` +
`tools/refactor/analizza_target.py`.

---

## Check 4au — Roll-up di stato TSK/US/epica (WARNING)

**Severita'**: `warning` (mai bloccante — diagnostico puro).
**Trigger**: always-on. Nessun flag di capability lo gatea.
**Mandato**: rileva, non corregge. Nessun auto-fix, nessun auto-rollup (R.7).

[^src: management/kanban/EP-068-backport-enforcement-factory-derivata/US-296-check-4au-rollup-stato/US-296.md §Criteri di accettazione]
[^src: EP-068.md §Audit di verticalita' — generalizzazioni G1/G2/G3]

### Problema rilevato

Con task su 6 chiusi e US ancora `todo` nella riga di `sprint.md`, il disallineamento
e' stato rilevato dall'utente, non dal sistema. Un roll-up manuale parziale era passato
per completo: la riga *Totale* e l'intestazione di `sprint.md` aggiornate, le singole
righe TSK lasciate indietro.

Il rischio e' strutturalmente identico su questa factory — 69 epiche, roll-up manuale —
e non era mai stato misurato perche' nessun check lo guardava.

### Sub-check

| ID | Trigger | Descrizione |
|---|---|---|
| 4au.1 | US con tutti i TSK terminali, status US non terminale | US «bloccata» dopo i task |
| 4au.2 | US con status terminale, almeno un TSK non terminale | US chiusa con task aperti |
| 4au.3 | Epica con tutte le US terminali, status epica non terminale | Epica bloccata dopo le US |
| 4au.4 | Epica con status terminale, almeno una US non terminale | Epica chiusa con US aperte |
| 4au.5 | Mismatch status artefatto: frontmatter vs riga `sprint.md` | Roll-up parziale in sprint.md |
| 4au.6 | US dichiarata in tabella di epica senza file corrispondente | US prenotata mai materializzata |
| 4au.7 | US con `epic:` che punta a epica che non la elenca | Riferimento US→epica orfano |

### Vincoli tecnici (misurati su dati reali 2026-09-25)

**V1 — Solo frontmatter YAML.** Il corpo di molti TSK contiene blocchi YAML di esempio
(template, skeleton) con righe `status: todo`. Un grep sull'intero file produce falsi positivi
confermati. L'algoritmo deve estrarre il solo blocco frontmatter:

```
match ^---\n(.*?)\n---\n in testa al file (re.DOTALL), max 4 KB
cercare ^status: solo dentro quel blocco
```

**V2 — Normalizzazione stati.** Varianti ammesse:

```
TERMINAL = {done, completed, superseded, cancelled, renamed, wontfix}
OPEN     = {todo, in_progress, in-progress, blocked, review, deferred, on_hold}
```

`in_progress` e `in-progress` sono trattati come equivalenti (normalizzare prima del
confronto). `on_hold`, `deferred`, `blocked` sono stati aperti non-progressing — contano
come aperti ai fini del roll-up.

### Algoritmo

> **[TRIGGER VINCOLANTE]** Il check si **esegue** con lo script
> `python3 tools/lint/check-status-rollup.py` (anche dentro `tools/lint/run-deterministic.py`)
> e se ne riportano le righe: non si ricostruisce, non si stima, non si campiona.
> Generalizzazioni G1/G2/G3, passi, regole applicate e limiti sono in:
> `.claude/skills/references/lint-checks-agent-fleet/check-4au.md`
>
> Leggi obbligatoriamente quella foglia prima di eseguire il check.
> Se il file manca → STOP e segnala a wiki-lint.

Passi eseguiti dallo script: raccolta EP/US/TSK, 4au.1 e 4au.2 (US vs TSK), 4au.3 e 4au.4
(epica vs US), 4au.5 (mismatch sprint.md, **G2**), 4au.6 (US in tabella senza file, **G3**),
4au.7 (US con `epic:` orfano).

**Generalizzazioni obbligatorie** (dall'audit EP-068 §Audit di verticalita'):

| # | Assunzione sorgente non valida qui | Forma generale applicata |
|---|---|---|
| G1 | Prefisso namespace obbligatorio (`.+-EP-\d+$`) | Prefisso opzionale: `(?:[A-Z]{2,4}-)?(?:EP\|US\|TSK)-\d+` |
| G2 | `sprint.md` epica-level, status in seconda colonna | `sprint.md` TSK-level, status nell'**ultima colonna** — generalizzato a qualunque granularita' |
| G3 | ID US in tabella epica come ID nudo | ID US puo' essere in link markdown `[US-268](path)` — regex tollerante |

Senza G1 e G3 il check non matcha nessun file di questa factory e passa in silenzio.
Senza G2 il sub-check 4au.5 non ha righe da leggere.

### Output format

```
## WARNING (roll-up di stato, mai heal-eligible)

- [WARNING][status-rollup][4au.1] management/kanban/EP-068/US-296/US-296.md
  US status=todo — tutti i 2 TSK sono terminali (done/completed).
  Azione: aggiornare manualmente status della US a done o in_progress.

- [WARNING][status-rollup][4au.2] management/kanban/EP-NNN/US-NNN/US-NNN.md
  US status=done — 1 TSK ancora aperto:
    management/kanban/.../TSK-NNN.md (status=todo)
  Azione: verificare se il TSK e' effettivamente aperto o va chiuso.

- [WARNING][status-rollup][4au.3] management/kanban/EP-NNN/EP-NNN.md
  Epica status=todo — tutte le N US sono terminali.
  Azione: aggiornare manualmente status epica.

- [WARNING][status-rollup][4au.4] management/kanban/EP-NNN/EP-NNN.md
  Epica status=done — 1 US ancora aperta:
    management/kanban/.../US-NNN.md (status=todo)

- [WARNING][status-rollup][4au.5] management/kanban/sprint.md
  TSK-640: sprint.md="todo" vs file="done" — disallineamento
  [4au.5] sprint.md: 18 righe lette (forma rilevata: TSK-level — status in ultima colonna)

- [WARNING][status-rollup][4au.6] management/kanban/EP-NNN/EP-NNN.md
  US-NNN dichiarata in tabella epica ma nessun file trovato in management/kanban/

- [WARNING][status-rollup][4au.7] management/kanban/EP-NNN/US-NNN/US-NNN.md
  epic: EP-NNN — ID non trovato nella tabella epica [potenziale falso positivo se tabella usa ID locali relativi]

Riepilogo 4au: 4au.1=N, 4au.2=N, 4au.3=N, 4au.4=N, 4au.5=N, 4au.6=N, 4au.7=N
```

### Invarianti

- **Warning-only**: mai ERROR. Un disallineamento di stato non blocca un rilascio.
- **Read-only**: il check non modifica alcun file kanban, sprint.md o frontmatter.
- **Nessun auto-rollup**: la correzione richiede un'azione umana o di un agente esplicito (R.7).
- **Frontmatter only**: il grep di `status:` avviene solo nel blocco frontmatter (V1), mai nel corpo.
- **Never heal-eligible**: finding diagnostico, non riparabile automaticamente.

### Scenari di verifica

| # | Condizione | Sub-check | Esito atteso |
|---|---|---|---|
| 1 | US todo, tutti i TSK done | 4au.1 | WARNING |
| 2 | US done, un TSK todo | 4au.2 | WARNING |
| 3 | Epica todo, tutte le US done | 4au.3 | WARNING |
| 4 | Epica done, una US todo | 4au.4 | WARNING |
| 5 | Artefatto status in frontmatter != sprint.md ultima colonna | 4au.5 | WARNING |
| 6 | US in tabella epica (anche via link markdown), nessun file | 4au.6 | WARNING |
| 7 | US con `epic:` non elencata nell'epica | 4au.7 | WARNING |
| 8 | TSK con `status: todo` nel corpo (template) ma frontmatter done | — | nessun falso positivo (V1) |
| 9 | US con stato `in-progress` (trattino) | — | normalizzato uguale a `in_progress` (V2) |
| 10 | US todo con TSK misti (alcuni done, alcuni todo) | 4au.1 | nessun finding (non tutti terminali) |
| 11 | Artefatto sprint.md `completed`, frontmatter `done` | 4au.5 | nessun finding (entrambi terminali) |
| 12 | ID senza prefisso namespace (es. `EP-068`, `TSK-690`) | tutti | matchato correttamente (G1) |
| 13 | US in tabella epica come link markdown `[US-268](path)` | 4au.6 | ID estratto correttamente (G3) |
| 14 | sprint.md TSK-level, status nell'ultima colonna | 4au.5 | status estratto correttamente (G2) |

### Cross-link

4au → `management/kanban/sprint.md` (sub-check 4au.5) +
`.claude/skills/references/lint-checks-agent-fleet/check-4au.md` (algoritmo con G1/G2/G3) +
`.claude/skills/lint-checks-kanban.md` (Check 3, integrita' frontmatter — complementare) +
`.claude/skills/lint-checks-index.md` (registro modulare) +
EP-068 US-296 (origine del check).
