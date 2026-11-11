---
description: Invoca functional-oracle-protocol (serve app + Playwright + asserzioni + critic) su un TSK FE o un'app. Ritorna verdict pass|conditional|reject. Funziona indipendentemente da fe_correctness.functional_oracle.enabled (esecuzione esplicita = volonta' esplicita).
argument-hint: <TSK-id|app> [--dry-run] [--ephemeral]
allowed-tools: Read, Write, Edit, Bash, Glob
---

Comando della capability [[fe-functional-oracle-capability]] (EP-018, ADR-067).
Esecuzione esplicita nel thread principale (ha `Bash`), indipendente dalla topologia:
analogo a `/visual-oracle` (ADR-012 §E) e `/ux-ui-review` (EP-008). Thin dispatcher
verso `qa-dev` in modalità functional-oracle (sub-skill `functional-oracle-protocol`),
con fallback `fe-dev` se `qa-dev` non in topologia (ADR-067 §A).

Riferimenti architetturali: EP-018 (`management/kanban/EP-018-fe-functional-oracle/EP-018.md`),
ADR-067 (esecutore + mix binario/LLM), ADR-065 (verdict deterministico da asserzioni binarie),
ADR-066 (scheduling functional oracle). PATTERN §3 (operazioni opzionali), R.P3 (opt-in totale).

## Sintassi

```
/functional-oracle <TSK-id|app>            → functional oracle standard
/functional-oracle <TSK-id|app> --dry-run  → mostra spec risolta + schema validata senza eseguire lo scenario
/functional-oracle <TSK-id|app> --ephemeral  → run standard, nessuna scrittura in code_quality/reports/
```

Argomenti utente: `$ARGUMENTS`

- Primo argomento: **TSK-id** (es. `TSK-042`) o **app** (es. `emulator-gba`), obbligatorio.
- Flag `--dry-run`: debug config — mostra la spec risolta e la acceptance-spec validata senza eseguire
  il scenario Playwright. Il frontmatter TSK non viene aggiornato.
- Flag `--ephemeral`: il report non viene scritto in `code_quality/reports/` (restituito solo in chat).
  L'entry su `wiki/log.md` viene comunque appesa.

## `<target>` — 2 forme

| Forma | Esempio | Risoluzione |
|---|---|---|
| **TSK-id** | `/functional-oracle TSK-042` | Legge `functional_acceptance_spec:` dal frontmatter del TSK; il valore è il path della spec YAML. |
| **app** | `/functional-oracle emulator-gba` | Risolve `code_quality/acceptance/<app>.acceptance.yaml` come spec di default per l'app. |

- **TSK-id**: `Glob management/kanban/**/TSK-<id>.md`. Se 0 match o > 1 match → ABORT
  «TSK non trovato / ambiguo». Estrae `functional_acceptance_spec:` dal frontmatter.
  Se il campo è assente → ABORT «Campo `functional_acceptance_spec:` non presente nel frontmatter
  del TSK. Aggiungere il path spec o usare la forma `<app>`.»
- **app**: il path `code_quality/acceptance/<app>.acceptance.yaml` deve esistere →
  se assente → ABORT «Spec non trovata: `code_quality/acceptance/<app>.acceptance.yaml`.
  Creare la spec o usare `<TSK-id>` con `functional_acceptance_spec:` valorizzato.»

## Gate `fe_correctness.functional_oracle.enabled`

Leggi `factory.config.yaml` → campo `fe_correctness.functional_oracle.enabled`.

- Se il campo **non è presente** nel blocco `fe_correctness` (factory pre-EP-018) → trattalo
  come `false`.
- Se `enabled: false` (default) → emetti il messaggio canonico e STOP:

```
[FUNCTIONAL-ORACLE] capability non abilitata.
Impostare fe_correctness.functional_oracle.enabled: true in factory.config.yaml.
```

**Eccezione**: l'invocazione esplicita di `/functional-oracle` **bypassa** il master switch
(esecuzione esplicita = volontà esplicita, analogia con `/visual-oracle` per `fe_correctness.enabled`
e `/review` per CQRL). Utile come gate manuale o re-check su regressione anche a flag spento.

> La semantica "bypass a flag spento" significa che il gate sopra viene applicato **solo in
> invocazione automatica** (dominio scheduler `functional-oracle`). Nell'invocazione diretta da
> riga di comando il messaggio canonico NON viene emesso e la skill procede normalmente.
> Coerente con US-070 §Business Rules e ADR-012 §E (stesso schema di `/visual-oracle`).

## Comportamento

### `/functional-oracle <TSK-id|app>`

1. **Risoluzione target** — vedi tabella sopra.
2. **Discovery esecutore** (ADR-067 §A):
   - Se `.claude/agents/qa-dev.md` è presente nella topologia → usa `qa-dev` in modalità
     functional-oracle (sub-skill `functional-oracle-protocol`).
   - **Fallback**: se `qa-dev` non è in topologia ma `.claude/agents/fe-dev.md` è presente →
     la skill `functional-oracle-protocol` viene eseguita via `fe-dev` (precedenza analoga ad
     ADR-014 per a11y).
   - Se **nessuno dei due** è in topologia → ABORT fail-loud:
     «Nessun agente disponibile per il functional oracle (`qa-dev` o `fe-dev` richiesti).
     Vedi `factory.config.yaml.topology` e `.claude/agents/`.»
3. **Invoca la skill `functional-oracle-protocol`** (EP-018 US-068, `.claude/skills/functional-oracle-protocol.md`)
   passando: spec risolta, target (TSK-id o app), flag `ephemeral`. La skill esegue le fasi
   (Bootstrap → Preflight → Serve App → Drive Scenario → Evaluate Asserzioni → Critic Advisory
   → Verdict + Report) ed è il single-writer di `functional_status:` (analogia R.Q2 / ADR-012 §A).
4. **Aggiornamento frontmatter** (solo con target TSK-id, non `--dry-run`, non `--ephemeral`) —
   la skill scrive `functional_status:` (`pending | pass | conditional | reject`) + `updated:`
   nel frontmatter TSK. Mai modificare il corpo del TSK.
5. **Output chat** — vedi sezione Output.

### `/functional-oracle <TSK-id|app> --dry-run`

Identico ai punti 1–2, ma la skill:
- legge e valida la spec (schema YAML, kind delle asserzioni, fixture existence check) senza
  aprire il browser né eseguire scenari Playwright.
- Stampa in chat la spec risolta (path, numero asserzioni, fixture, thresholds) + eventuale
  errore di validazione schema.
- **Non aggiorna** `functional_status:` nel frontmatter TSK.
- **Non scrive** report in `code_quality/reports/`.

Utile per debug config prima di un run reale.

### `/functional-oracle <TSK-id|app> --ephemeral`

Identico al run standard, ma il report **non viene scritto** in `code_quality/reports/`
(risultato restituito solo in chat). L'entry su `wiki/log.md` viene comunque appesa.
Analogo a `/query --ephemeral`.

## Verdict

Il verdict nasce **esclusivamente** dalle asserzioni binarie (ADR-067 §B, ADR-065 §D).
**Nessun LLM nel path di pass/fail.** Fail-closed: un esito senza evidenza deterministica
non può essere `pass`.

| Verdict | Significato |
|---|---|
| `pass` | Tutte le asserzioni `blocking` hanno risposto `true`; advisory ≤ `thresholds.advisory_max`. |
| `conditional` | ≥1 asserzione `advisory` fallita (non blocking); critic LLM può abbassare a `conditional` aggiungendo osservazioni. |
| `reject` | ≥1 asserzione `blocking` fallita. L'LLM non può promuovere a `pass` ciò che le asserzioni binarie hanno bocciato. |

Il critic LLM multimodale (ADR-067 §B, riuso ADR-009) ispeziona il trace (screenshot
sequenziali + console/network log) e produce **solo** osservazioni `advisory` /
`open_questions` — mai il verdict bloccante. Ogni osservazione cita un artefatto reale
del trace (evidence-provenance, ADR-063 §B).

## Output chat

Al termine il comando mostra:

```
FUNCTIONAL ORACLE — <TSK-id|app> (iter <N>)
============================================
verdict:          pass | conditional | reject
assertions_total: <N>
assertions_fail:  <N>
advisory_count:   <N osservazioni critic>
report_path:      code_quality/reports/<TSK-id|app>-functional-iter-<N>.md
```

Con `--dry-run`:

```
FUNCTIONAL ORACLE — <TSK-id|app> (dry-run)
===========================================
spec_path:    <path spec risolta>
assertions:   <N> (blocking: <N>, advisory: <N>)
fixtures:     <ok|MANCANTI: ...>
schema_valid: ok | ERROR: <messaggio>
dry-run: scenario NON eseguito, frontmatter NON aggiornato.
```

Con `--ephemeral` viene aggiunta la nota «ephemeral: report NON scritto in code_quality/reports/».

Il `report_path` punta al digest umano nel side-channel `code_quality/reports/`
(slug `functional` per distinguere dagli iter `visual` / `a11y` / `uxui-review` / CQRL —
ADR-067, riuso path CQRL ADR-012 §B). Il JSON strutturato gemello vive in
`code_quality/reports/<TSK-id|app>-functional-iter-<N>.json`.

## Storage

- **Con TSK-id** → `code_quality/reports/<TSK-id>-functional-iter-<N>.{json,md}`
- **Con app** → `code_quality/reports/<app>-functional-iter-<N>.{json,md}`
- **`--ephemeral`** → nessuna scrittura in `code_quality/reports/` (solo chat + log)
- **`--dry-run`** → nessuna scrittura (solo chat)

## Logging

Ogni invocazione (incluse `--dry-run` e `--ephemeral`) appende a `wiki/log.md` una entry
nel formato canonico:

```
[YYYY-MM-DD HH:MM] functional-oracle <target> → <verdict|dry-run>
```

## Cascade ordering (scheduler)

Il functional oracle si posiziona nel cascade di un TSK FE:

```
develop → visual-oracle → functional-oracle → review
```

Precondizione additiva: se `visual_status: pending` (visual oracle non ancora eseguito) →
aspetta visual oracle prima di eseguire functional oracle (stesso pattern `ux-ui-review` →
`visual_status`, US-070 §Business Rules).

Il dominio scheduler è `functional-oracle` (default `false`, opt-in). Quando
`fe_correctness.functional_oracle.enabled: true` il dominio viene attivato automaticamente
(analogamente ad ADR-012 §F per `visual-oracle`). Policy: serial same-app (race condition
sul serve port + stato DOM), parallel cross-app (antichain conflict-free) — ADR-066.

## Prerequisiti (fail-loud)

- **Skill `functional-oracle-protocol` presente** (`.claude/skills/functional-oracle-protocol.md`,
  EP-018 US-068). Se assente → ABORT «Skill `functional-oracle-protocol` non scaffoldata (US-068).
  Comando non eseguibile.»
- **`qa-dev` o `fe-dev`** in topologia — vedi Discovery esecutore sopra.
- **Node.js + Playwright installati** (ADR-064 precondizione). Se assenti → la skill fa ABORT
  con fail-loud (messaggio canonico ADR-064).
- **Spec YAML valida** — schema `.claude/schemas/acceptance-spec.schema.yaml` (TSK-144).

## Backward compat

L'assenza del file `.claude/commands/functional-oracle.md` **non** produce ERROR di lint:
il comando è opzionale e additivo (EP-018 opt-in, ADR-067). Una factory che non lo scaffolda
mantiene comportamento identico a v2.19 (R.P3 opt-in totale, 0 nuove ERROR/WARNING).

## Vincoli (ADR-067)

- **Single-writer**: solo la skill `functional-oracle-protocol` scrive `functional_status:`.
  Il comando non lo scrive direttamente.
- **Verdict deterministico**: il verdict (`pass|conditional|reject`) nasce esclusivamente
  dalle asserzioni binarie. Il critic LLM (advisory) non può modificare il verdict bloccante.
- Mai modificare il corpo del TSK (solo frontmatter `functional_status:` + `updated:`,
  e solo via skill, e solo se NOT `--dry-run` e NOT `--ephemeral`).
- Mai bypassare `functional_oracle.max_iterations` (loop bounded dalla skill, default 3,
  come R.Q4 / EP-005 — ADR-067 §C).
- `--dry-run` è sempre side-effect-free sul frontmatter TSK e sul report.

Vedi `.claude/skills/functional-oracle-protocol.md` per la procedura completa, ADR-067
per lo schema esecutore + mix binario/LLM, ADR-065 per il verdict + acceptance-spec schema,
ADR-066 per lo scheduling, e [[fe-functional-oracle-capability]] per il contratto completo.
