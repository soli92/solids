---
type: runbook
title: "Skill Hygiene — refactor di skill/agenti/flotte (EP-060, v2.41)"
status: published
ep: EP-060
related: [refactor-agent-skills, fleet-doctor, EP-060]
pattern_version: "2.41"
created: 2026-09-04
updated: 2026-09-04
---

# Skill Hygiene — refactor di skill/agenti/flotte

> Runbook narrativo per la capability EP-060 Fleet Health.
> Complementa la skill eseguibile `.claude/skills/refactor-agent-skills.md`
> senza duplicarla: fornisce esempi d'uso, casi tipo e guardrail pratici.
>
> [^src: US-231 AC7]
> [^src: .claude/skills/refactor-agent-skills.md — spina dorsale]
> [^src: wiki/runbooks/code-intelligence.md — modello narrativo]

## Quando serve

Una skill o un agente **cresce nel tempo** ogni volta che un EP aggiunge fasi,
edge-case o context extra al suo corpo. Sopra una certa soglia il contenuto
garantito diventa troppo denso: la finestra di contesto porta tutto, ma
l'agente perde aderenza sui segmenti distanti dall'inizio.

Segnali che indicano che serve un refactor:

- **Dimensione diretta**: il file supera 500 righe di corpo (escluso frontmatter).
  Check 4ap lo segnala automaticamente come `WARNING [REFACTOR]`.
- **Segnali indiretti**: l'agente produce output non conformi su prompt che prima
  funzionavano; il codice review trova fasi dimenticate; si notano allucinazioni
  su dettagli operativi.
- **300–500 righe con contenuto misto**: procedure operative mescolate a dettaglio
  consultivo — Check 4ap segnala `WARNING [VALUTARE]`.

Esempi concreti da questa factory:

- `tavola-rotonda-protocol.md` — ~799 righe, candidata #1 per EP-060.
- Agenti cresciuti lungo più sprint (orchestrator.md, wiki-keeper.md): corpi
  accumulati da EP diversi senza un taglio periodico.
- Skill di ingest che contengono sia la spina dorsale sia varianti di edge-case
  che potrebbero diventare foglie.

Sotto i 300 righe: non intervenire. Il protocollo stesso ha questa soglia come
gate obbligatorio (V-1 regola di non intervento sotto soglia).

## Come attivare la capability

1. In `factory.config.yaml` impostare:
   ```yaml
   refactor_agent_skills:
     enabled: true
   ```
2. Verificare che gli script siano presenti:
   ```bash
   python3 tools/refactor/analizza_target.py .claude/
   ```
   Se il comando restituisce un inventario di unità con verdetto, la capability
   è operativa. Se manca lo script, il Check 4ap skip silente (R.FH3 fail-open)
   ma il comando `/refactor` non funzionerà finché US-230 non viene completata.
3. Lanciare la lint per vedere i candidati attuali:
   ```
   /lint
   ```
   Check 4ap emette WARNING per ogni unità sopra soglia. Non blocca la pipeline.
4. Per avviare il refactor di un candidato specifico:
   ```
   /refactor .claude/skills/tavola-rotonda-protocol.md
   ```
   L'agente `fleet-doctor` prende il controllo e guida il processo con gate di
   approvazione obbligatorio in Fase 1 (piano dichiarato prima di toccare file).

## Esempi d'uso

### Esempio 1 — Refactor conservativo di una skill sopra soglia

**Scenario**: `tavola-rotonda-protocol.md` ha raggiunto 799 righe dopo 3 EP
successivi. Check 4ap emette `WARNING [REFACTOR]: .claude/skills/tavola-rotonda-protocol.md
(corpo 799 righe > soglia 500)`.

**Procedura**:

1. `/refactor .claude/skills/tavola-rotonda-protocol.md`
2. `fleet-doctor` esegue Fase 0 (ricognizione + snapshot V-6).
3. Fase 1: il piano dichiara il criterio di taglio scelto (es. «per fase del
   flusso: Fase 1–2 nel corpo; Fase 3–5 in foglie distinte») e la tabella di
   trigger. **Gate**: approvazione esplicita prima di procedere.
4. Fase 2: esecuzione — corpo riscritto come spina dorsale (vincoli + fasi +
   gate + trigger al punto d'uso); dettaglio migrato in foglie
   `.claude/skills/references/refactor/`.
5. Fase 3: `verifica_flotta.py` + `mappa_riferimenti.py --gate` → exit 0.
6. Fase 4: test di equivalenza — stessi prompt su snapshot baseline e su
   versione rifattorizzata; accettazione se pass-rate funzionale ≥ baseline.
7. Fase 5: riepilogo righe prima/dopo, elenco foglie create.

**Esito atteso**: corpo ridotto a ≤250 righe; 2–4 foglie in `references/`;
nessun riferimento rotto; comportamento equivalente verificato.

### Esempio 2 — Analisi di un'intera flotta

**Scenario**: si vuole capire quale sottoinsieme della flotta ha unità fuori
soglia prima di pianificare uno sprint di igiene.

**Procedura**:

1. Abilitare la capability (se non già attiva).
2. Eseguire direttamente lo script di analisi:
   ```bash
   python3 tools/refactor/analizza_target.py .claude/
   ```
   L'output elenca ogni file con conteggio righe e verdetto.
3. Usare `mappa_riferimenti.py` per il grafo dei riferimenti tra unità:
   ```bash
   python3 tools/refactor/mappa_riferimenti.py .claude/
   ```
   Identifica agenti orfani, collisioni di description, membership rotta.
4. Pianificare i TSK di refactor in ordine di priorità: prima le unità
   con verdetto `REFACTOR` e maggiore fan-in (più agenti le citano).
5. Solo in seguito eseguire `/refactor <file>` uno per uno — V-4 impone
   una sola radice per unità e V-5 impone equivalenza prima della sostituzione.

### Esempio 3 — Cosa NON fare (anti-pattern)

Questi comportamenti violano i vincoli del protocollo e producono degradazione
silente:

- **Non intervenire sotto 300 righe**: under la soglia il refactor è inutile e
  introduce complessità senza beneficio (V-1: non toccare se non necessario).
- **Non spostare vocabolari chiusi in foglia**: se una sezione elenca valori
  enumerati usati come condizioni di routing o naming di agenti, resta nel corpo
  (V-1: la spina dorsale governa il comportamento).
- **Non riscrivere il frontmatter**: `name`, `description`, `tools`, `model` sono
  il contratto di attivazione e routing. Cambiarli durante il refactor rompe il
  dispatch (V-3).
- **Non sostituire prima del test di equivalenza**: Fase 3 e Fase 4 devono essere
  entrambe PASS prima di eliminare lo snapshot (V-5).
- **Non creare foglie senza trigger vincolante nel corpo**: una foglia senza trigger
  al punto d'uso viene ignorata — produce un'unità apparentemente snella ma
  effettivamente incompleta (V-2).
- **Non usare path relativi nelle foglie**: i path devono essere `.claude/`-ancorati
  per garantire che gli agenti dispatchati per iniezione corpo possano risolverli
  (V-9, Pattern A/B).

## Guardrail V-9 (sicurezza di dispatch)

Questa factory usa **Pattern A**: gli agenti sono dispatchati via `subagent_type`
con il loro file di definizione come contesto. Le foglie esterne sono accessibili
al momento del dispatch. V-9 near-zero in questo contesto.

Tuttavia, se si usa la skill `refactor-agent-skills` su agenti in factory che
adottano Pattern B (iniezione del corpo nel prompt di Task), V-9 diventa critico:
una foglia esterna non raggiungerà mai il subagent. In quel caso il contenuto
vincolante non può migrare in foglia.

La foglia `.claude/skills/references/refactor/topologia-e-dispatch.md` contiene
il protocollo completo per determinare il Pattern della factory target prima di
iniziare qualsiasi refactor.

## Come leggere il report di `fleet-doctor`

Al termine di Fase 5 il report include:

| Sezione | Contenuto |
|---|---|
| **Righe prima/dopo** | per ogni unità rifattorizzata |
| **Stima token risparmiati** | al caricamento del contesto (non guarantita) |
| **Esito gate G1–G11** | exit 0 = tutti i gate strutturali e di grafo PASS |
| **Esito Fase 4** | pass-rate funzionale vs baseline; aderenza trigger 100% |
| **Foglie create** | elenco con trigger e punto d'inserzione |
| **Ottimizzazioni flotta** | agenti orfani rimossi, collision description risolte |

Un gate FAIL in Fase 3 o Fase 4 interrompe il protocollo: `fleet-doctor` propone
iterazione o rollback. Lo snapshot in `snapshot_dir` resta disponibile finché
l'utente non conferma l'adozione.

## Casi d'uso reali (11 pilot Wave D EP-060)

Sette criteri di taglio applicati con verdetto ACCEPT:

### Pilot #1 — Skill grande sequenziale (per fase del flusso)
- Target: `.claude/skills/tavola-rotonda-protocol.md` (790 → 211 righe, -73%)
- 7 foglie in `.claude/skills/references/tavola-rotonda/` (una per fase 0-4 + 2 sezioni consultive)
- Insight: pilot canonical della capability

### Pilot #2 — Meta-comando con versioni (per variante)
- Target: `.claude/commands/factory-bootstrap.md` (584 → 173 righe, -71%)
- 4 foglie in `.claude/commands/references/factory-bootstrap/` (recent/mid/legacy/changelog)
- Fix inline D-2/D-3 (v2.32 stale → v2.40)
- Insight: fix inline pattern con 2 famiglie asserzioni

### Pilot #3 — Agente borderline VALUTARE (per frequenza)
- Target: `.claude/agents/tavola-rotonda-moderatore.md` (450 → 371 righe, -17.6%)
- 2 foglie in `.claude/agents/references/tavola-rotonda-moderatore/` (nuova convenzione agent-slug)
- Drift reconciliation elegante senza cross-pilot touch
- Insight: manutenibilità come beneficio principale su VALUTARE borderline

### Pilot #4 — Dev-agent con capability opt-in (per opt-in)
- Target: `.claude/agents/fe-dev.md` (400 → 84 righe, -79%)
- 5 foglie in `.claude/agents/references/fe-dev/` (una per opt-in flag)
- Primo test empirico TSK-546 AC2 (fleet-doctor Fase 4 hardening)
- Insight: opt-in capability naturale trigger

### Pilot #5 — Skill max (per fase pesante)
- Target: `.claude/skills/prototype-generation-protocol.md` (638 → 245 righe, -61.6%)
- 4 foglie (input + fase1 + fase3 + fase4)
- Class A anchor + template migrated pattern (Step 4.1 log entry)
- Insight: la logica per-backend era già delegata a skill secondarie

### Pilot #6 — Command con 3 audience (per destinazione contenuto)
- Target: `.claude/commands/prototype.md` (325 → 210 righe, -35%)
- 2 foglie in `.claude/commands/references/prototype/` (nuova convenzione command-slug)
- T3 soft-fail trigger inaugurato (contenuto consultivo)
- Insight: audience-based è ortogonale ai criteri strutturali

### Pilot #7 — NO-REFACTOR motivato
- Target: `.claude/agents/prototype-generator.md` (301 righe, VALUTARE borderline)
- Verdetto: no-refactor con proiezione controfattuale (4 scenari, tutti anti-pattern)
- Insight: la capability sa dire di no motivamente (6/7 accept = 14% cohesive detection)

### Pilot #8 — Skill enorme allineamento modularizzazione (per famiglia)
- Target: `.claude/skills/lint-checks.md` (2196 → 119 righe, -94.6% RECORD)
- **0 foglie nuove** (le 10 famiglie EP-052 esistevano complete) + 10 trigger
- Gap fix EP-060: aggiunto trigger 4ap per `lint-checks-agent-fleet.md`
- Insight: dedup reale possibile quando la modularizzazione precedente è parziale

### Pilot #9 — Skill grande FE oracle (per fase)
- Target: `.claude/skills/functional-oracle-protocol.md` (963 → 342 righe, -64.5%)
- 7 foglie in `.claude/skills/references/functional-oracle-protocol/`
- Insight: dispatch cascaded (skill invocata da fe-dev + qa-dev + command)

### Pilot #10 — Wave scheduler critico (per frequenza + conservative)
- Target: `.claude/skills/parallel-scheduling.md` (625 → 371 righe, -40%)
- 4 foglie con conservative bias (Temporal Awareness ~97 righe resta Class A)
- Insight: quando il target è critico, riduzione modesta con anchor conservative è preferibile

### Pilot #11 — Dev-protocol usato da 5 agenti (per frequenza)
- Target: `.claude/skills/dev-protocol.md` (516 → 288 righe, -44%)
- 3 foglie in `.claude/skills/references/dev-protocol/` (Fase 4-bis/ter + analytics)
- Insight: fan-in 5 dev-agent moltiplica il beneficio del taglio ×5

## Boundary con altre capability

- **Non è code-review**: `code-review-protocol` (CQRL v2.12) valuta output dei
  dev-agent nei code_path (`.py`, `.ts`, ecc.). Fleet-health valuta unità di
  contesto agentico (`.claude/{agents,skills}/*.md`). Scope **disgiunto**.
- **Non è Ponytail**: `ponytail` (EP-057) applica il YAGNI ladder su codice di
  prodotto. Fleet-health analizza markdown agentici. Scope **disgiunto**.
- **Non è complexity-budget**: il check di complessità TSK valuta numero di step
  e granularità di un task. Fleet-health valuta lunghezza di un file di contesto.
  I due strumenti sono **complementari**.
- **Non è refactoring-docs**: la skill `refactoring-docs` gestisce README e
  documentazione tecnica. `refactor-agent-skills` gestisce esclusivamente file
  agentici in `.claude/`. Scope **disgiunto**.
- **`/refactor --external <path>`** (ADR-EP060-003): rifattorizza factory esterne. Guard Decisione 4 rifiuta factory senza EP-060 con messaggio strutturato `/factory-upgrade --to=v2-41 --apply`. Test empirico su soli-boy + portale-servizi in TSK-557.

## Prossimi passi

Stato al 2026-09-04 (post Wave D EP-060):

- **12 commit su main** — tutti i pilot Wave D integrati e verificati.
- **27 TSK done** (29 incluse US-239 human-gated) — sprint EP-060 quasi completo.
- **Gate grafo PASS pulito** — `verifica_flotta.py` + `mappa_riferimenti.py --gate` exit 0 su tutta la flotta rifattorizzata.
- Prossima attività: TSK-557 test empirico `/refactor --external` su factory derivate (soli-boy + portale-servizi); poi gate v2.41.

## Riferimenti

- `.claude/skills/refactor-agent-skills.md` — skill operativa (spina dorsale, Fasi 0–5)
- `.claude/agents/fleet-doctor.md` — agente owner (G1–G11)
- `.claude/skills/lint-checks-agent-fleet.md` — Check 4ap
- `PATTERN.md §36` — pattern formale Refactor Skill Layer
- `CLAUDE.md §refactor_agent_skills` — quick-reference capability
- `factory.config.yaml` → `refactor_agent_skills:` — config gate
- `tools/refactor/` — script analisi (US-230, installazione separata)
