---
name: dev-protocol
description: Procedura per un dev-agent che consuma un TSK e produce codice in code_path. Single source of truth per Develop (PATTERN §3).
---
# Procedura — consumare un TSK (Develop, L4 → L5)

Skill condivisa fra `be-dev`, `fe-dev`, `db-dev`, `qa-dev`. La specializzazione
per layer vive nell'agente; questa skill è la spina dorsale comune.

## Ciclo Develop — dove ti trovi

```
dev-protocol      sviluppo del TSK (Fase 0 → 5)            ← ingresso
  ↓
dev-handoff       entry in wiki/log.md, protocollo di chiusura
  ↓
vcs-handoff       commit del codice, gate umano VCS
  ↓
dispatch-policy   dispatch dell'orchestrator a valle (review, oracoli) ← uscita su /run
```

Ogni skill rimanda alla successiva. Se non sai a che punto sei, leggi l'intestazione della skill
che stai eseguendo: in wave parallele saltare una fase e' il difetto tipico.

## Preflight multi-utente — cooperative locking (EP-053)

Prima della Fase 0, in contesti multi-utente, solo con la CLI `tools/session/active_sessions.py`
(mai a mano: lo scrive in modo chirurgico e conserva i commenti):

1. `gc` — rimuove le entry scadute; riporta le rimozioni in chat.
2. `conflicts --domain <d>` — clash sullo stesso domain → **WARN** in chat, conferma prima di procedere.
3. `claim --agent <a> --domain <d> --uuid "$(python3 tools/session/session_id.py --short)" --ttl 30`
   (resolver canonico US-308: `CLAUDE_CODE_SESSION_ID` → scratchpad → uuid4 dichiarato; niente UUID ad-hoc).
4. `release --domain <d> --uuid <id>` al termine (Fase 5 handoff finale).

I claim sono advisory: `conflicts` e `claim` avvisano ed escono 0, nessun lock.
Le entry `kind: session` (scritte da `/session-start`) non sono clash di dominio:
segnalano solo che un'altra sessione e' aperta.

In sessioni single-user questo preflight è no-op (nessun clash trovato = nessun output).

## Fase 0 — Gate preliminare + target resolution (v2.12 multi-repo)

Prima di qualsiasi scrittura:

1. **Leggi `factory.config.yaml`** (root del repo).
2. Verifica:
   - `topology` ammette il tuo layer (es. per `be-dev`: topologia ∈
     {`full-stack-agents`, `hybrid-be-agents`, `custom` con `be-dev` listato}).
   - `routing.<tuo-layer> == agent` (oppure override esplicito via `/dev`).
   - Esiste un percorso L5 risolvibile (vedi step 2-bis: target resolution).
3. **Leggi il TSK**: deve avere `layer: <tuo>`, `consumer: agent`, `status: todo`,
   dipendenze chiuse. Se manca anche solo un campo o un gate, **STOP** e
   segnala in chat (non procedere "in modalità best-effort").
   Se il TSK ha `base_commit:` esegui anche il controllo di deriva (step 5 qui sotto); senza il
   campo non cambia nulla.
4. **Costi in token** (advisory): `dispatch-policy` §13 — `cost_alert.py check --gate`; con una
   regola superata chiedi conferma prima di procedere (una volta per sessione e per alert).
5. **Deriva dal `base_commit`** (solo se il frontmatter ha `base_commit:`): `git -C <code_path> diff
   --name-only <base_commit>..HEAD -- <file target>`. File citati cambiati e estratti non
   corrispondenti → `status: blocked` + handoff «deriva dal base_commit» (file, atteso, trovato), mai
   improvvisare; SHA inesistente → dichiaralo e fermati. Procedura: leggi
   `.claude/skills/references/dev-protocol/base-commit-deriva.md` — se il file manca, STOP e segnala.

**Leggi obbligatoriamente** `.claude/skills/references/dev-protocol/fase-0-gate-steps.md`
per la procedura completa di: Step 2-bis (target resolution multi-repo),
Step 2-ter (branch alignment gate opt-in), Step 2-quater (ambiente di build pronto),
Checkpoint analysis-only (loop-1),
Gate bugfix (red-capable command) — se il file manca, STOP e segnala.

## Fase 0.bis — Impact Pre-Analysis (L3, opt-in, R.CI4)

**Gate**: esegui solo se `code_intelligence.l3_impact.enabled: true`.
Se disabled o chiave assente → **skip silenzioso**, procedi a Fase 1.

**Leggi obbligatoriamente** `.claude/skills/references/dev-protocol/fase-0bis-impact-analysis.md`
prima di eseguire questa fase — se il file manca, STOP e segnala.
Contiene: prerequisiti, esecuzione graphify, output atteso, livelli blast_radius,
scope extension check.

## Fase 1 — Preparazione contesto

1. Leggi la US riferita dal TSK (path deducibile: `EP-XXX-*/US-YYY-*/US-YYY.md`).
2. Leggi l'ADR / sezione di `design_&_architecture/` citato.
3. Apri le pagine `wiki/` citate transitivamente dalla US (concept/entity/synthesis).
   Non citarle direttamente nel codice — citazione cascade: il codice cita TSK/ADR.
4. Leggi `raw/tech_stack.md` per vincoli (versioni, standards).
5. Esplora `<code_path>/**` per capire layout esistente.

## Fase 2 — Handoff iniziale

1. Edit del TSK: `status: in-progress`, `started_at: YYYY-MM-DD` (data del lavoro, obbligatoria: Check 4be), aggiungi `updated: YYYY-MM-DD HH:MM`.
2. **[Analytics — step obbligatorio]** Subito dopo l'edit, emetti l'evento con `<stato>` = `started`, se
   `analytics.measurement.enabled: true` AND `dogfooding.enabled: true`
   (il tool fa early-return silenzioso se i flag sono `false` — no-op sicuro):
   ```bash
   # [analytics] record TSK <stato>: started qui, finished in Fase 5
   _TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   _REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '.')"
   python3 "$_REPO_ROOT/tools/analytics/record-event.py" \
     --event "{\"task_id\":\"<TSK-NNN-slug>\",\"project_id\":\"<project.name>\",\"actor_type\":\"agent\",\"actor_id\":\"<agent-slug>\",\"task_type\":\"<layer>\",\"state\":\"<stato>\",\"ts\":\"$_TS\",\"tokens\":{\"input\":0,\"output\":0,\"cache_read\":0,\"cache_write\":0},\"model\":\"claude-sonnet-4-6\",\"tool_calls\":[]}" \
     2>/dev/null || true
   # Se il comando fallisce (exit non-zero), prosegui comunque (fail-open, ADR-039 §D).
   ```
3. Non toccare il corpo del TSK.

## Fase 3 — Implementazione

1. Implementa secondo:
   - Implementation Steps del TSK (ordine indicativo, non vincolante)
   - Technical Specs del TSK
   - Standards verbatim citati nei raw (PATTERN §11)
2. Atomicità: tutto il cambiamento per **un singolo TSK** deve essere
   coerente (un commit logico, anche se il VCS lo separa in più commit).
3. **Pratiche di ingegneria** (solo con `engineering_practices.enabled: true`). Con
   `test_seams_status: confermati` segui `.claude/skills/pocock-tdd.md` (per seam: test rosso,
   codice minimo, verde); altrimenti non inventare seam: «seam non concordati» nell'handoff.
   Bug con causa ignota: `.claude/skills/pocock-diagnosing-bugs.md`; da sub-agente ti fermi al
   gate prima della correzione e restituisci riproduzione, esito e ipotesi.
4. Se durante l'implementazione scopri che il TSK è **sotto-specificato**:
   - Gap di knowledge base → append `wiki/gaps.md` (vedi `wiki-gap-protocol`)
   - Decisione architetturale mancante → STOP e segnala in chat (`tpm` o
     `lead-architect` la prenderanno; non improvvisare design)
   - Bug pre-esistente fuori scope → segnala in chat (TPM aprirà TSK separato),
     non fixare opportunisticamente (PATTERN §7 r.8)

## Fase 4 — Definition of Done

Verifica la DoD del TSK punto per punto:
- [ ] Codice compila / build passa
- [ ] Test unitari relativi passano
- [ ] (Se applicabile) Test integrazione passano
- [ ] Documentazione inline minima (docstring, README locale solo se richiesto)
- [ ] Niente file fuori scope toccati
- [ ] (`engineering_practices.enabled`, seam confermati) per ogni seam, nell'handoff, comando ed esito rosso prima e verde dopo
- [ ] (`engineering_practices.enabled`, TSK di correzione) `regression_test:` valorizzato nel frontmatter

Se anche un solo punto fallisce e non puoi risolverlo nel TSK corrente:
- Rollback delle modifiche già fatte (preferibile) o segnala chiaramente in chat lo stato parziale.
- Edit `status: in-progress` (NON `done`), e descrivi il blocker in chat.

## Fase 4-bis — Visual Verification (trigger, opt-in fe_correctness)

**Condizione (AND)**: `TSK.layer == 'fe'` AND `fe_correctness.enabled: true`.

**No-op esplicito**: `layer != fe` OR `fe_correctness.enabled: false` → skip diretto a Fase 5.
Comportamento identico a v2.16 su factory senza opt-in.

**Fail-loud**: trigger soddisfatto ma skill `visual-oracle-protocol` assente →
ERROR «`fe_correctness.enabled: true` ma skill `visual-oracle-protocol` assente; impossibile eseguire la Fase 4-bis». STOP.
Mai degradare silenziosamente a no-op quando il flag è attivo.

**Procedura completa, esiti e loop bounded**:
Leggi `.claude/skills/references/dev-protocol/fase4-bis-visual-verification.md`
(esiti: `pass` → Fase 5; `conditional` → loop fe-dev bounded `fe_correctness.max_iterations`; `reject` → gate umano).

## Fase 4-ter — UX/UI Review (trigger, opt-in ux_ui)

**Condizione (AND)**: `TSK.layer == 'fe'` AND `ux_ui.enabled: true`.
**Pre-condizione**: `visual_status` non-pending (Fase 4-bis conclusa); se `visual_status: reject` → SKIP.

**No-op esplicito**: `layer != fe` OR `ux_ui.enabled: false` → skip diretto a Fase 5.
Comportamento identico a v2.17 su factory senza opt-in.

**Fail-loud**: trigger soddisfatto ma né skill `ux-ui-review-protocol` né agente `ux-ui-reviewer` presenti →
ERROR «`ux_ui.enabled: true` ma nessun esecutore ux-ui-review disponibile». STOP.

**Procedura completa, esiti e loop bounded**:
Leggi `.claude/skills/references/dev-protocol/fase4-ter-ux-ui-review.md`
(esiti: `pass` → Fase 5; `conditional` → loop fe-dev bounded `ux_ui.max_iterations`; `reject` → gate umano; `visual_status: reject` → SKIP).

## Fase 4-quater — Trigger CQRL di default (opt-in, `code_quality.trigger_default`)

**Condizione (AND)**: `code_quality.trigger_default.enabled: true` AND `TSK.layer` e
`TSK.consumer` nelle liste del blocco. Il dev-agent imposta `review_status: pending` (mai sopra
`passed`/`rejected`) e non invoca il code-reviewer: lo dispatcha l'orchestrator (`dispatch-policy`
§12). Blocco assente o spento → nulla. Ruleset assente → WARNING, non STOP.
Procedura: leggi `.claude/skills/references/dev-protocol/fase4-quater-cqrl-trigger.md`.

## Fase 5 — Handoff finale (Develop completato)

1. **[Analytics — step obbligatorio]** Emetti l'evento con il comando della Fase 2 e
   `<stato>` = `finished`, PRIMA di editare `status: done` (stesso fail-open).
2. Edit del TSK: `status: done`, `closed_at: YYYY-MM-DD` (data del lavoro, Check 4be), `updated: YYYY-MM-DD HH:MM`.
3. Invoca `dev-handoff` (skill) per scrivere l'entry su `wiki/log.md`.
4. **Invoca `vcs-handoff`** (skill, v2.8 esteso multi-repo v2.12) passando
   `resolved_vcs` + `resolved_target_name` (da Fase 0 step 2-bis). La skill coordina
   i commit per il `vcs.mode` del **target risolto** (monorepo, submodule, sibling, external),
   non per la factory globale; con mode `none` → STOP (incoerenza).

   In multi-repo, **ogni vcs-handoff è per-target**: mai operazioni coordinate cross-target
   automaticamente. Se un TSK richiede modifiche cross-repo, si scompone in N TSK con target
   distinti (responsabilità del TPM). Gate umano obbligatorio per ogni `git commit` (PATTERN §7 r.14).

## Vincoli inviolabili

- **Mai editare il corpo del TSK** (solo `status:` e `updated:`).
- **Mai scrivere su `wiki/**`** se non append a `wiki/log.md` e `wiki/gaps.md`.
- **Mai scrivere su `design_&_architecture/`** (è proprietà di Arch).
- **Mai scrivere su `management/kanban/**`** fuori dal proprio TSK (la generazione TSK è proprietà del TPM).
- **Mai inventare endpoint, tabelle, classi** non specificati nel design.
- **Standards verbatim** (PATTERN §11): se SAML/OIDC/FHIR citati, implementa esattamente quelli.
- **Stop se code_path non è valorizzato.** Mai scrivere "a indovinare" in `./src/`.
- **§ai_policy** (`code_path` con `ai_attribution_policy.suppress_ai_traces: true`, PATTERN
  §23.9): nessuna traccia AI nel lavoro. Niente `Co-Authored-By` ne' firme nei commit, che
  passano dal `commit_tool` (default `tools/vcs/sm-commit.sh`); mai `git commit --no-verify`.
  Gli hook vedono i messaggi di commit, non i **commenti nel codice**: un commento che cita AI o
  un tool di generazione lo puo' evitare solo chi scrive, e nessun controllo successivo lo trova.

## Analytics Instrumentation (opt-in v2.19+)

**Gate**: `analytics.measurement.enabled: true` AND `dogfooding.enabled: true`.
Punti 1-2 (started/finished): comandi inline in Fase 2 e Fase 5.

Leggi obbligatoriamente `.claude/skills/references/dev-protocol/analytics-payloads.md`
per: documentazione Punti 3-4 (blocked/aborted), payloads, regola fail-open —
se il file manca, procedi comunque (analytics non è bloccante).
