---
name: release-protocol
description: Orchestrazione processo di release in 4 fasi (Preparazione → Validazione → Tag → Post-release). Skill fat che chiama release-validation-gate come step atomico senza ridefinirne i criteri. Gate umano Fase 3 NON bypassabile. Tecnologia-agnostica. [^src: US-225 EP-059 — TSK-519 analisi comparativa 2026-09-02]
---
# Skill: release-protocol

> Skill di orchestrazione processo release. Coordina i passi formali dalla preparazione degli
> artefatti al tag VCS al post-release. Non implementa logica di validazione qualitativa: quella
> è delegata interamente a `release-validation-gate` (skill separata, invocata in Fase 2).
>
> **Distinzione fondamentale** (vedi TSK-519 analisi comparativa 2026-09-02):
> - `release-validation-gate` = prerequisiti tecnici (CHECKs): verifica RUN-REPORT, soglie,
>   CHANGELOG schema. Produce GATE-REPORT.md + verdict. Non esegue mai azioni VCS.
> - `release-protocol` = orchestrazione del processo (STEPS): prepara artefatti, invoca la
>   validation gate come black-box, gestisce il gate umano pre-tag, esegue il tag, aggiorna
>   la memoria di progetto. Non ridefinisce criteri di validazione.
>
> La validation-gate non conosce il release-protocol; il release-protocol dipende dalla
> validation-gate come black-box: `input: <version>` → `output: verdict + GATE-REPORT.md`.
>
> [^src: TSK-519 §Distinzione formale — 2026-09-02]
> [^src: .claude/skills/release-validation-gate.md — skill delegata (CHECKs)]

## Invarianti locali

| Codice | Invariante | Bypassabile |
|---|---|---|
| R.RP1 | Gate umano Fase 3 (pre-tag) NON è bypassabile da nessuna config, flag o agente. Solo conferma esplicita dell'utente autorizza il tag VCS. | NO — mai |
| R.RP2 | Idempotenza: ogni fase verifica lo stato attuale prima di applicare modifiche. Ri-eseguire una fase già completata non produce effetti collaterali. | — |
| R.RP3 | La skill non esegue mai `git tag` / `git push` senza conferma esplicita umana (R.RP1). Se la conferma non arriva, la procedura si ferma con stato `aborted` e append a `wiki/log.md`. | NO — mai |
| R.RP4 | Nessun criterio di validazione ridefinito in questa skill. Tutto il giudizio qualitativo sugli artefatti di release è delegato a `release-validation-gate`. | — |

> R.RP1 è un'estensione di R.P1 (`release-validation-gate`: mai auto-tag) al livello
> del processo orchestrante. Anche se `release-validation-gate` è disabilitata (boot check
> no-op), R.RP1 rimane attivo nel release-protocol.

## Boot check

```
1. Leggi factory.config.yaml (root del repo).
   - Verifica che il campo `pattern_version` esista (warning se assente: Fase 1 lo imposterà).

2. Verifica argomento <version>:
   - Formato atteso: X.Y.Z (semver, es. "2.40.0") o vX.Y.Z (con prefisso "v").
   - SE assente o malformato → STOP: "release-protocol: argomento <version> mancante o
     malformato. Uso: invoke release-protocol --version=<X.Y.Z>"

3. Verifica stato VCS (working tree):
   - SE ci sono modifiche non committate sul branch corrente → WARN in chat:
     "Working tree non pulito. Committa o stasha le modifiche prima della release."
     Chiedi conferma prima di procedere.
   - SE working tree pulito → procedi.

4. Log boot:
   - "release-protocol avviato — versione target: v<version> — branch: <current-branch>"
```

## Fase 1 — Preparazione

> Scopo: aggiornare gli artefatti di release (CHANGELOG, config, meta-prompts, CLAUDE.md)
> prima della validazione. Idempotenza: verifica che ogni artefatto non sia già aggiornato.

### Step 1.1 — CHANGELOG.md

```
Azione:
  - Apri CHANGELOG.md.
  - Verifica se esiste già la sezione `## v<version>` (o `## v<X.Y.Z>`).
  - SE già presente → log "CHANGELOG.md: sezione v<version> già presente. Skip." e prosegui.
  - SE assente → aggiungi in testa (dopo header principale) la sezione:

    ## v<version>
    <!-- data: <YYYY-MM-DD> -->

    ### Nuovi EP / feature
    - <EP-NNN> <titolo> — <descrizione breve>

    ### US completate
    - US-NNN <titolo>

    ### Bugfix / tech-debt
    - <descrizione>

    ### Dipendenze e breaking changes
    - <nessuna | descrizione>

    ## Validation evidence (v<version>)
    <!-- sezione compilata dalla release-validation-gate in Fase 2 -->

  Nota: la sezione `## Validation evidence` è richiesta dalla skill `release-validation-gate`
  (Step 5 CHANGELOG validation, ADR-034 §A). Anche se lasciata come placeholder in Fase 1,
  deve essere compilata prima di invocare la validation gate (Fase 2).
```

### Step 1.2 — pattern_version in factory.config.yaml

```
Azione:
  - Leggi factory.config.yaml.pattern_version.
  - SE già impostato a v<version> → log "pattern_version già corretto. Skip." e prosegui.
  - SE assente o impostato a versione diversa:
    - Aggiorna il campo: `pattern_version: v<version>`
    - Log: "factory.config.yaml: pattern_version aggiornato a v<version>."

Nota: SSOT — il campo pattern_version deve essere coerente con il tag che verrà creato.
```

### Step 1.3 — Entry meta-prompts/

```
Azione:
  - Verifica se esiste la directory meta-prompts/v<major>-<minor>/ (es. meta-prompts/v2-40/).
  - SE esiste già → log "meta-prompts/v<X>-<Y>/ già presente. Skip." e prosegui.
  - SE assente:
    - Identifica la directory della versione precedente (ultima presente in meta-prompts/).
    - Crea meta-prompts/v<X>-<Y>/factory-bootstrap.md con il contenuto:
        extends: ../v<prev-X>-<prev-Y>/factory-bootstrap.md
        ## Delta v<version>
        <!-- Lista dei cambiamenti rispetto alla versione precedente: -->
        - EP-NNN <titolo>: <breve descrizione impatto sul bootstrap>
        [Aggiungere una riga per ogni EP incluso in questa release]
    - Log: "meta-prompts/v<X>-<Y>/factory-bootstrap.md creato."

Nota: il file usa il pattern `extends:` della catena delta (CLAUDE.md §Meta-prompt versioning).
```

### Step 1.4 — CLAUDE.md §Meta-prompt versioning

```
Azione:
  - Apri CLAUDE.md.
  - Trova la sezione `## Meta-prompt versioning`.
  - Verifica se la versione v<version> è già dichiarata come "corrente" (current).
  - SE già aggiornata → log "CLAUDE.md: versione v<version> già corrente. Skip." e prosegui.
  - SE non aggiornata:
    - Aggiorna la riga current: cambia la versione precedente da "current" a "previous".
    - Aggiungi la nuova riga per v<version> come "current":
        - [`meta-prompts/v<X>-<Y>/factory-bootstrap.md`](...) — **current** (<descrizione delta>)
    - Log: "CLAUDE.md: §Meta-prompt versioning aggiornato a v<version> come corrente."
```

### Step 1.5 — Checkpoint Fase 1

```
Al termine degli step 1.1..1.4:
  - Verifica che tutti e 4 gli artefatti siano aggiornati (o già corretti).
  - Log complessivo:
    "Fase 1 completata. Artefatti verificati/aggiornati:
     ✓ CHANGELOG.md (sezione v<version>)
     ✓ factory.config.yaml (pattern_version: v<version>)
     ✓ meta-prompts/v<X>-<Y>/factory-bootstrap.md
     ✓ CLAUDE.md (Meta-prompt versioning)"
  - Procedi a Fase 2.
```

## Fase 2 — Validazione

> Scopo: invocare la skill `release-validation-gate` come gate prerequisiti tecnici.
> Questa fase non implementa alcuna logica di validazione — delega completamente alla skill.
> R.RP4: nessun criterio ridefinito qui.

### Step 2.1 — Invocazione release-validation-gate

```
Azione: carica e invoca la skill release-validation-gate con flag --apply --version=v<version>.

Il gate si comporta come descritto in .claude/skills/release-validation-gate.md (5 step):
  - Step 1: Discovery RUN-REPORTs
  - Step 2: Schema validation
  - Step 3: Threshold check + Cross-EP-013
  - Step 4: Aggregate report → GATE-REPORT.md
  - Step 5: CHANGELOG section validation

SE release_governance.battle_test_gate.enabled == false (default factory derivate):
  Il boot check della validation-gate emette: "Gate disabilitato (R.P3 opt-in)."
  → Il release-protocol tratta questo caso come verdict = "gate-disabled" e procede
    direttamente alla Fase 3 con WARN in chat:
    "WARN: release-validation-gate disabilitata. Fase 3 gate umano rimane obbligatorio (R.RP1)."
```

### Step 2.2 — Gestione verdict

```
verdict = output di release-validation-gate (pass | fail | bypass | gate-disabled)

SE verdict == "fail":
  - STOP. Notifica umano con il messaggio strutturato della validation gate.
  - Log: "Fase 2 FAIL. release-validation-gate ha restituito verdict=fail. Release bloccata."
  - Append wiki/log.md:
      <ISO-8601> release-protocol version=v<version> verdict=fail reason="validation-gate fail"
  - NON procedere a Fase 3.

SE verdict == "pass" | "bypass" | "gate-disabled":
  - Log: "Fase 2 completata. verdict=<verdict>. Procedo al gate umano pre-tag (Fase 3)."
  - GATE-REPORT.md path: validation/release-gates/v<version>/GATE-REPORT.md
    (se gate-disabled: GATE-REPORT.md assente — annotare nel payload Fase 3)
  - Procedi a Fase 3.
```

## Fase 3 — Tag [GATE UMANO OBBLIGATORIO — NON BYPASSABILE]

> **R.RP1 ASSOLUTO**: questo gate non è bypassabile da nessuna config, flag, tool o agente.
> Solo la conferma esplicita dell'utente in questo turno di conversazione autorizza il tag VCS.
> Un agente non può auto-confermare per conto dell'utente.

### Step 3.1 — Emissione payload strutturato pre-tag (STOP obbligatorio)

```
Il sub-agent emette il payload strutturato e si ferma (4-step handoff R.14/R.RP1).

OUTPUT OBBLIGATORIO (formato strutturato):

---
gate: pre-tag
action: create_release_tag
timestamp: <ISO-8601 UTC>
payload:
  version: <version>
  tag: v<version>
  current_branch: <branch>
  validation_verdict: <pass | bypass | gate-disabled>
  gate_report: "validation/release-gates/v<version>/GATE-REPORT.md"  # o "N/A" se gate-disabled
  changelog_summary: |
    <Estratto della sezione CHANGELOG ## v<version>: EP inclusi, breaking changes se presenti>
  confirm_required: true
---

⚠️  GATE UMANO PRE-TAG (R.RP1 — non bypassabile)

Per procedere con il tag `v<version>` e il push su origin, conferma esplicitamente.
Rispondi "confermo" per procedere, oppure "annulla" per interrompere la release.

Il sub-agent si ferma qui e attende la risposta dell'utente.
```

### Step 3.2 — Attesa conferma esplicita

```
Il coordinator raccoglie la risposta dell'utente.

SE risposta == "confermo" (o equivalente esplicito affermativo):
  - Riprende il sub-agent con la conferma.
  - Procedi a Step 3.3.

SE risposta == "annulla" (o equivalente negativo) O risposta assente:
  - ABORT: la release non viene taggata.
  - Log: "Gate umano: release v<version> annullata dall'utente (o timeout)."
  - Append wiki/log.md:
      <ISO-8601> release-protocol version=v<version> verdict=aborted reason="gate-umano-annullato"
  - STOP. La Fase 4 non viene eseguita.
```

### Step 3.3 — Esecuzione tag VCS (solo dopo conferma)

```
Solo se Step 3.2 ha ricevuto conferma esplicita:

Azione:
  1. git tag v<version>
  2. git push origin v<version>

SE il tag già esiste (idempotenza):
  - WARN: "Tag v<version> già presente. Verificare se si tratta di un re-run. Skip git tag."
  - Se il tag punta al commit atteso → prosegui a Fase 4.
  - Se il tag punta a un commit diverso → STOP ed escalate all'utente.

SE push fallisce:
  - STOP con messaggio di errore VCS.
  - Log: "Fase 3 ERROR: push tag v<version> fallito. Causa: <errore git>"
  - Append wiki/log.md:
      <ISO-8601> release-protocol version=v<version> verdict=error reason="push-tag-failed"

SE tag e push riusciti:
  - Log: "Fase 3 completata. Tag v<version> creato e pushato su origin."
  - Procedi a Fase 4.
```

## Fase 4 — Post-release

> Scopo: aggiornare la memoria di progetto con la milestone completata.
> Idempotenza: verificare che le entry non siano già presenti prima di appendere.

### Step 4.1 — sprint.md milestone

```
Azione:
  - Apri management/kanban/sprint.md (o file sprint corrente se percorso diverso).
  - Verifica se la release v<version> è già annotata come milestone completata.
  - SE già presente → log "sprint.md: milestone v<version> già annotata. Skip." e prosegui.
  - SE assente → appendi in fondo alla sezione del sprint corrente:
      ## Milestone completata — v<version>
      - data: <YYYY-MM-DD>
      - tag: v<version>
      - validation_verdict: <pass | bypass | gate-disabled>
      - gate_report: validation/release-gates/v<version>/GATE-REPORT.md
```

### Step 4.2 — memory/episodic/ entry release

```
Azione:
  - Crea (o aggiorna se già esiste) memory/episodic/release-<version>.md con:

      ---
      type: release
      version: v<version>
      date: <YYYY-MM-DD>
      validation_verdict: <pass | bypass | gate-disabled>
      gate_report: validation/release-gates/v<version>/GATE-REPORT.md
      tag_pushed: true
      actor: <git user o "unknown">
      ---

      ## Release v<version>

      - EP inclusi: <lista EP dalla sezione CHANGELOG>
      - Validation verdict: <pass | bypass | gate-disabled>
      - Gate umano: confermato dall'utente
      - GATE-REPORT: validation/release-gates/v<version>/GATE-REPORT.md

  SE il file esiste già (idempotenza) → verifica che `tag_pushed` sia `true`; se mancante
  aggiunge il campo; se già corretto → skip.
```

### Step 4.3 — wiki/log.md entry (append-only)

```
Azione: append a wiki/log.md (append-only, mai sovrascrivere righe esistenti).

Entry formato:
  <ISO-8601> develop release-protocol version=v<version> verdict=<pass|bypass|gate-disabled> \
  gate_report=validation/release-gates/v<version>/GATE-REPORT.md actor=<git-user|agent>

SE la riga per v<version> è già presente in wiki/log.md (idempotenza):
  - log "wiki/log.md: entry v<version> già presente. Skip."
  - non appendere duplicati.
```

### Step 4.4 — Checkpoint Fase 4 e chiusura

```
Log finale:
  "Fase 4 completata. Release v<version> conclusa.
   ✓ management/kanban/sprint.md — milestone annotata
   ✓ memory/episodic/release-<version>.md — entry creata/verificata
   ✓ wiki/log.md — entry appesa

   Release v<version> completata con successo. Tag: v<version> su origin."
```

## Diagramma flusso complessivo

```
Boot check
  └─ config check, version arg, VCS clean
       ↓
Fase 1 — Preparazione (idempotente)
  ├─ CHANGELOG.md sezione v<version>
  ├─ factory.config.yaml pattern_version
  ├─ meta-prompts/v<X>-<Y>/factory-bootstrap.md
  └─ CLAUDE.md §Meta-prompt versioning
       ↓
Fase 2 — Validazione
  └─ invoke release-validation-gate --apply --version=v<version>
       ├─ verdict=fail → STOP + wiki/log.md + notifica umano
       └─ verdict=pass|bypass|gate-disabled → procedi
                ↓
[GATE UMANO R.RP1 — NON BYPASSABILE]
  └─ payload strutturato pre-tag + STOP
       ├─ annullato → ABORT + wiki/log.md
       └─ confermato →
                ↓
Fase 3 — Tag (solo dopo conferma)
  ├─ git tag v<version>
  └─ git push origin v<version>
       ↓
Fase 4 — Post-release (idempotente)
  ├─ management/kanban/sprint.md milestone
  ├─ memory/episodic/release-<version>.md
  └─ wiki/log.md entry append-only
```

## Regole operative

| Codice | Regola |
|---|---|
| R.RP1 | Gate umano Fase 3 NON bypassabile — vedi §Invarianti locali |
| R.RP2 | Idempotenza: ogni step verifica lo stato prima di modificare |
| R.RP3 | Nessun `git tag` / `git push` senza conferma esplicita |
| R.RP4 | Logica validazione qualitativa delegata a `release-validation-gate` — non ridefinire qui |
| R.RP5 | In caso di abort (gate umano annullato o fail validation), aggiorna `wiki/log.md` con `verdict=aborted\|fail` e non proseguire alle fasi successive |
| R.RP6 | La skill è tecnologia-agnostica: nessun riferimento a vendor CI/CD, piattaforme di deployment, infrastruttura specifica |

## Invocazione

```
# Uso standard (bot check + 4 fasi)
invoke release-protocol --version=2.40.0

# Con versione prefissata
invoke release-protocol --version=v2.40.0

# Riprendi da una fase specifica (se fase precedente già completata)
invoke release-protocol --version=2.40.0 --start-phase=3
```

> `--start-phase=<N>` è un hint; la skill verifica idempotenza all'ingresso di ogni fase
> indipendentemente da questo flag (R.RP2).

## Skill correlate

- [release-validation-gate](.claude/skills/release-validation-gate.md) — delegata in Fase 2 (CHECKs)
- [dev-handoff](.claude/skills/dev-handoff.md) — pattern append wiki/log.md
- [vcs-handoff](.claude/skills/vcs-handoff.md) — pattern VCS post-commit

[^src: US-225 EP-059 — TSK-520 creazione release-protocol generalizzato 2026-09-02]
[^src: TSK-519 analisi comparativa release-protocol (portale) vs release-validation-gate (soli)]
