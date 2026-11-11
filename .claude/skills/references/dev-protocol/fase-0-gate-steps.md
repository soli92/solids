# Fase 0 — Gate steps dettagliati: target resolution, branch alignment, build, checkpoint, bugfix

**Ambito**: dettaglio degli step di Fase 0 di `dev-protocol.md`. Leggere obbligatoriamente
prima di procedere con la Fase 0 — se il file manca, STOP e segnala.
Contiene: Step 2-bis (target resolution multi-repo), Step 2-ter (branch alignment gate),
Step 2-quater (ambiente di build pronto), Checkpoint analysis-only, Gate bugfix.

---

## Step 2-bis — Target resolution (v2.12 multi-repo, PATTERN §5 + §13)

Determina il `code_path` effettivo (`resolved_code_path`) e la `resolved_vcs` da usare:

**Caso A — Legacy single-repo** (`code_path:` valorizzato, `code_paths: []` o assente):
- `resolved_code_path = factory.config.yaml.code_path`
- `resolved_vcs = factory.config.yaml.vcs` (top-level)
- `resolved_target_name = "default"` (per logging)
- Procedi.

**Caso B — Multi-repo** (`code_paths: [<entry>, ...]` non vuoto):

1. Read TSK `target:` frontmatter.
2. Se `target:` valorizzato: cerca `entry = code_paths[name == target]`.
   - Non trovato → **ERROR** «TSK <id> ha `target: <X>` ma nessuna entry in `code_paths` con quel nome». STOP.
   - Trovato ma `<tuo-layer>` non in `entry.layers` → **ERROR** «TSK <id> ha layer <Y> e target <X>, ma entry <X> non lista <Y> in `layers`». STOP.
   - `resolved_code_path = entry.path`; `resolved_vcs = entry.vcs`; `resolved_target_name = entry.name`. Procedi.
3. Se `target:` assente: `candidates = [e for e in code_paths if <tuo-layer> in e.layers]`.
   - `len == 0` → **ERROR** «Nessuna entry in `code_paths` lista <tuo-layer>; routing.<layer>: agent richiede almeno una entry. Lint Check 4c violato». STOP.
   - `len == 1` → auto-derive da `candidates[0]`. Procedi.
   - `len >= 2` → **ERROR** «TSK <id> layer <Y> ambiguo: ≥ 2 entry in `code_paths` listano <Y>. Il TPM doveva valorizzare `target:`. Lint Check 4j violato». STOP. Mai indovinare.
4. Verifica accessibilità `resolved_code_path`: esiste sul filesystem o è creabile.
   - Non esiste e non creabile → **ERROR** «code_path <path> per target <name> non accessibile». STOP.
5. Log a chat: `Target resolved: <name> → <resolved_code_path> (vcs: <mode>)`

Tutto il resto del protocollo (Fasi 1-5) usa `resolved_code_path` e `resolved_vcs` al
posto del legacy `code_path` + `vcs`. La citazione codice nei dev-agent usa il prefisso
appropriato in base a `resolved_vcs.mode`.

---

## Step 2-ter — Branch alignment gate (opt-in, EP-034 v2.25, PATTERN §15)

Gate **pre-dispatch** che verifica di trovarsi sul branch giusto *prima* di scrivere codice.
Critico per target `submodule`/`sibling` (problema dei due HEAD).

**No-op a flag spento (default)**: si attiva **solo se**
`resolved_vcs.branch_awareness.enabled: true` AND `resolved_vcs.branch_awareness.dispatch_gate ≠ off`.
Altrimenti comportamento identico a v2.24 (R.B10): salta direttamente a Fase 1.

Quando attivo, e **solo** per `resolved_vcs.mode ∈ {submodule, sibling}` (per `monorepo`/`external`
il gate è degenere e viene saltato):

1. Calcola `expected_branch` invocando `branch-resolver` (R.B9) con `resolved_vcs`,
   `resolved_target_name` e il TSK corrente.
2. Determina lo stato reale del target (read-only, R.B7):
   - Se `submodule` e `<submodule_path>/.git` assente → **STOP** «submodule <name> non
     inizializzato: `git submodule update --init <submodule_path>`».
   - Branch corrente via `git -C <dir> symbolic-ref --short HEAD` (fallisce = detached).
3. Confronta:
   - **detached HEAD** → gestione secondo `dispatch_gate` (vedi sotto).
   - `expected_branch` valorizzato E ≠ branch corrente → mismatch.
   - `expected_branch` null (es. `shared` senza `base_branch`) e HEAD su un branch → OK.
4. Azione secondo `dispatch_gate`:
   - **`block`** → **STOP** con il comando esatto di remediation. Non procedere alla Fase 1.
   - **`warn`** → WARNING inline con il comando suggerito, poi **procedi**.
   - Se `auto_align: propose` → proponi `git checkout <expected_branch>` sotto **gate umano**
     (mai eseguirlo in autonomia, R.B8). Su conferma esplicita checkout; senza → STOP.

**Vincolo (R.B8)**: il gate **non esegue mai `git checkout` automatico**. Al massimo lo propone
sotto gate umano (`auto_align: propose`). La responsabilità dello stato dei repo esterni resta umana.

---

## Step 2-quater — Ambiente di build pronto

**Trigger**: la DoD del TSK include una build o test che richiedono le dipendenze installate.
Altrimenti no-op, si passa alla Fase 1.

1. Verifica le dipendenze installate nella root di `resolved_code_path` (es. `node_modules/`,
   virtualenv) e in ogni package annidato da cui la build dipende (es. un design system in
   submodule dentro il target).
2. Assenti in uno dei due → **STOP soft**: segnala che l'ambiente non e' pronto, proponi il
   comando di installazione del progetto che rispetta il lockfile (es. `npm ci`) e **attendi
   conferma**.
3. **Mai installare in silenzio**: l'installazione puo' riscrivere il lockfile e cambiare le
   dipendenze del repo cliente.
4. Se la factory documenta problemi noti dell'ambiente di build (runbook o entita' in `wiki/`),
   leggili prima di toccare la configurazione di build: un errore che nasce dalle dipendenze si
   ripara nell'ambiente, non nella config del bundler.

[^src: portale-servizi-factory raw/retro-2026-07-29-UP-TSK-021b.md §R1 §R2 — backport 2026-10-08]

---

## Checkpoint analysis-only (EP-053, loop-1)

Applicabile al **primo ciclo di esecuzione (loop-1)** quando le AC del TSK includono
formule come: «nessuna modifica al codice», «solo censimento», «solo documentazione»,
«analysis only», o equivalenti.

Prima di produrre qualsiasi modifica al codice:

1. **Verifica esplicita**: controlla se un'istruzione umana (nel thread corrente) estende o
   sovrascrive lo scope del TSK originale.
2. Se l'estensione è **ambigua** (formulazione informale, implicita, o non riconducibile
   univocamente a una AC del TSK) → **STOP**: chiedi conferma esplicita prima di procedere.
3. Registra la decisione nel log di sessione (in chat o in `wiki/log.md`).

Un'estensione verbale informale non sovrascrive le AC del TSK. L'ambiguità va sciolta
*prima* dell'azione, non dopo.

[^src: portale-servizi-factory .claude/skills/dev-protocol.md §Checkpoint loop-1 — EP-053 backport 2026-07-30]

---

## Gate bugfix — red-capable command (EP-065, US-273)

Se il TSK è un **bugfix**, Fase 0 **non procede** senza un comando **già eseguito almeno una volta** con tutte e cinque le proprietà seguenti — **tutte necessarie**:

1. **red-capable** — fallisce sul difetto (esercita il path del bug e asserisce il sintomo esatto riportato, non «non crasha»);
2. **deterministico** — stesso verdetto a ogni run (per bug non deterministici: tasso di riproduzione pinnato e alto);
3. **veloce** — secondi, non minuti;
4. **agent-runnable** — eseguibile non presidiato;
5. **con l'output mostrato** — l'output va incollato nel contesto corrente, redatto dei segreti.

**Seam-as-finding**: se non esiste un seam corretto dove ancorare il comando, quella stessa è la scoperta — l'architettura sta impedendo di bloccare il bug — e va registrata come finding architetturale, non aggirata.

[^src: US-273 AC2, AC3 — EP-065 gate red-capable 2026-09-21]
