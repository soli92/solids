---
name: release-protocol
description: >-
  Orchestrazione processo di release in 4 fasi (Preparazione → Validazione → Tag → Post-release).
  Skill fat che chiama release-validation-gate come step atomico senza ridefinirne i criteri. Gate
  umano Fase 3 NON bypassabile. Tecnologia-agnostica. [^src: US-225 EP-059 — TSK-519 analisi
  comparativa 2026-09-02]
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

**Leggi obbligatoriamente** `.claude/skills/references/release-protocol/fase1-preparazione.md`
all'ingresso di questa fase — se il file manca, STOP e segnala.
Contiene: Step 1.1 (CHANGELOG.md), Step 1.2 (pattern_version), Step 1.3 (meta-prompts/),
Step 1.4 (CLAUDE.md heading + README.md §Available versions), Step 1.5 (Checkpoint).

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

**Leggi obbligatoriamente** `.claude/skills/references/release-protocol/fase4-post-release.md`
all'ingresso di questa fase — se il file manca, STOP e segnala.
Contiene: Step 4.1 (sprint.md milestone), Step 4.2 (memory/episodic/),
Step 4.3 (wiki/log.md entry append-only), Step 4.4 (Checkpoint e chiusura).

## Diagramma flusso complessivo

```
Boot check
  └─ config check, version arg, VCS clean
       ↓
Fase 1 — Preparazione (idempotente)
  ├─ CHANGELOG.md sezione v<version>
  ├─ factory.config.yaml pattern_version
  ├─ meta-prompts/v<X>-<Y>/factory-bootstrap.md
  └─ CLAUDE.md heading + meta-prompts/README.md §Available versions
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

## Gate locali (opzione worktree-gate)

Per check pre-tag su SHA immutabile: vedi `.claude/skills/worktree-gate.md`
(invarianti R.WG1-R.WG5, cleanup garantito). Opzione del manutentore, non requisito;
`release-protocol` non la invoca automaticamente.

## Skill correlate

- [release-validation-gate](release-validation-gate.md) — delegata in Fase 2 (CHECKs)
- [dev-handoff](dev-handoff.md) — pattern append wiki/log.md
- [vcs-handoff](vcs-handoff.md) — pattern VCS post-commit
- [worktree-gate](worktree-gate.md) — gate locali su SHA immutabile (opzione per pre-tag check)

[^src: US-225 EP-059 — TSK-520 creazione release-protocol generalizzato 2026-09-02]
[^src: TSK-519 analisi comparativa release-protocol (portale) vs release-validation-gate (soli)]
