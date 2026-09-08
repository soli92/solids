---
name: refactor
description: "Invoca fleet-doctor per rifattorizzare in divulgazione progressiva una unita' di contesto agentica (skill/agente/command). Gated su refactor_agent_skills.enabled. Supporta --external per factory esterne (ADR-EP060-003)."
argument-hint: "<target> [--external <path>] [--adapter=<claude|cursor>] [--dry-run]"
allowed-tools: Read, Glob, Bash
---

# /refactor

Argomenti utente: `$ARGUMENTS`

Dispatcher thin verso l'agente `fleet-doctor` per rifattorizzare una unita' di
contesto agentica (skill, agente, command) applicando la divulgazione progressiva
definita in EP-060. Con `--external <path>` opera su una factory esterna mantenendo
la factory corrente in modalita' read-only (ADR-EP060-003 Decisione 1).

---

## Sintassi

```
/refactor <target>
/refactor <target> --dry-run
/refactor <target> --external <path>
/refactor <target> --external <path> --adapter=<claude|cursor>
/refactor <target> --external <path> --adapter=cursor --dry-run
```

| Argomento | Tipo | Default | Semantica |
|---|---|---|---|
| `target` | stringa | obbligatorio | Path del file target relativo alla factory (es. `.claude/agents/<agent-slug>.md`) |
| `--external <path>` | path assoluto | assente (self) | Path assoluto della factory esterna (es. `/Users/.../soli-boy/`). Se assente: opera sulla factory corrente. |
| `--adapter=<name>` | enum `claude\|cursor` | `claude` | Adapter target nella factory esterna: `claude` per `.claude/`, `cursor` per `.cursor/`. Ignorato in self mode. |
| `--dry-run` | flag | assente | Esegue solo Fase 0-1 (detection topologia + analisi) senza modificare nulla. Obbligatorio per il primo run su factory esterna sconosciuta. |

---

## Procedura

### Step 0 — Gate `refactor_agent_skills.enabled` (precondizione assoluta)

Leggi `factory.config.yaml` e controlla il flag:

```
SE factory.config.yaml.refactor_agent_skills.enabled == false (default opt-in):
  STOP — non invocare fleet-doctor, non creare file, nessun side-effect.
  Emetti in chat:
    "EP-060 non abilitato. Aggiungi `refactor_agent_skills.enabled: true`
     in factory.config.yaml prima di usare /refactor."
```

Il messaggio deve essere esplicito e orientare l'azione. Se
`refactor_agent_skills.enabled: true`, prosegui.

### Step 1 — Parse `$ARGUMENTS`

Dall'input `$ARGUMENTS` estrai:

- `target` — primo token non-flag (obbligatorio); se assente, STOP:
  ```
  [/refactor] Target mancante.

  Utilizzo: /refactor <target> [--external <path>] [--adapter=<claude|cursor>] [--dry-run]

  Esempi:
    /refactor .claude/agents/wiki-keeper.md
    /refactor .claude/agents/<agent-slug>.md --external /Users/.../soli-boy/
    /refactor .claude/agents/<agent-slug>.md --dry-run
    /refactor .cursor/rules/<rule-slug>.md --external /Users/.../ --adapter=cursor

  Fornisci il path del file target da rifattorizzare.
  ```
- `flag_external` — valore di `--external` se presente (path assoluto), altrimenti `null`
- `flag_adapter` — valore di `--adapter` se presente (stringa), altrimenti `null`
- `flag_dry_run` — `true` se `--dry-run` presente, altrimenti `false`

Validazioni:
- Se `--adapter` valorizzato e valore non in `{claude, cursor}`: STOP —
  «Valore --adapter non valido: `<v>`. Valori ammessi: `claude`, `cursor`.»
- Se `--external` valorizzato e il path non e' assoluto (non inizia con `/`): STOP —
  «Il path `--external` deve essere assoluto. Ricevuto: `<v>`.»

### Step 2 — Risoluzione parametri con default

Applica i default per i parametri non forniti:

- `mode` = `external` se `flag_external` e' valorizzato, altrimenti `self`
- `external_path` = `flag_external` se valorizzato, altrimenti `null`
- `adapter` = `flag_adapter` se valorizzato, altrimenti `claude`
- `dry_run` = `flag_dry_run`

Deriva `adapter_dir` da `adapter`:
- `claude` → `.claude`
- `cursor` → `.cursor`

Segnala in chat i valori risolti:

```
[/refactor] Parametri risolti:
  target:        <target>
  mode:          self | external
  external_path: <path> | —
  adapter:       <claude|cursor>
  adapter_dir:   <.claude|.cursor>
  dry_run:       true | false
```

### Step 3 — Validazione target

**Self mode** (mode == `self`):

Verifica che il file target esista nella factory corrente:
`Glob <target>`

Se non esiste: STOP —
«Target non trovato: `<target>`. Verifica che il file esista nella factory
corrente prima di procedere.»

**External mode** (mode == `external`):

1. Verifica che `external_path` esista come directory:
   ```bash
   Bash: test -d "<external_path>"
   ```
   Se non esiste: STOP — «Path esterno non trovato: `<external_path>`.»

2. Verifica che l'adapter sia installato nella factory esterna:
   ```bash
   Bash: test -d "<external_path>/<adapter_dir>"
   ```
   Se non esiste: STOP —
   «Adapter `<adapter>` non trovato in `<external_path>`. Verifica che
   `<adapter_dir>/` esista nella factory esterna prima di procedere.»

3. Verifica che il file target esista nella factory esterna:
   `Glob <external_path>/<target>`
   Se non esiste: STOP —
   «Target non trovato nella factory esterna: `<external_path>/<target>`.»

### Step 4 — Guard EP-060 in factory target (Decisione 4 ADR-EP060-003)

Solo in **external mode**:

Verifica la presenza di EP-060 nella factory esterna:
```bash
Bash: test -d "<external_path>/<adapter_dir>/skills/references/refactor"
```

Se la directory non esiste, STOP con messaggio strutturato:

```
STOP — external_target non eseguibile

Factory esterna: <external_path>
Motivo: EP-060 (skill references/refactor/) non trovato nell'adapter <adapter_dir>.

Per abilitare external_target su questa factory:
1. Aggiorna la factory target: /factory-upgrade <external_path> --to=v2-41 --apply
2. Verifica che il blocco `refactor_agent_skills.enabled: true` sia presente in
   <external_path>/factory.config.yaml
3. Ri-esegui: /refactor <target> --external <external_path>

Alternativa (dry-run senza modifica): /refactor <target> --external <external_path> --dry-run
non e' disponibile se EP-060 non e' installato (la detection Fase 0.0 richiede le foglie).
```

In self mode questo step e' no-op (EP-060 e' gia' verificato al Step 0).

### Step 5 — Invocazione `fleet-doctor`

Lancia l'agente `fleet-doctor` via `Task(subagent_type="fleet-doctor")` passando
il payload YAML strutturato:

```yaml
target: <target>
mode: self | external
external_path: <path> | null
adapter: <claude|cursor>
dry_run: <true|false>
```

L'agente esegue le fasi del protocollo `refactor-agent-skills`:

| Fase | Nome | Azione |
|---|---|---|
| 0 | Topologia | Detection dispatch pattern (A/B/C) del target |
| 1 | Analisi | Misura dimensioni, fan-in, complessita' del target |
| 2 | Snapshot | Baseline in `<factory>/.fleet-health/workspace/` |
| 3 | Refactor | Applica divulgazione progressiva (skip in dry-run) |
| 4 | Verifica | Gate strutturali G1-G11; report equivalenza |
| 5 | Report | Output in-chat + artefatto JSON con campo `mode` |

---

## Esempi d'uso

```bash
# Self mode — rifattorizza un agente nella factory corrente
/refactor .claude/agents/wiki-keeper.md

# External mode — rifattorizza un agente in una factory esterna
/refactor .claude/agents/<agent-slug>.md --external /Users/simone.olivieri/soli-boy/

# Dry-run — analisi senza modifiche (raccomandato per il primo run su factory esterne)
/refactor .claude/agents/<agent-slug>.md --dry-run

# External mode con adapter Cursor
/refactor .cursor/rules/<rule-slug>.md --external /Users/simone.olivieri/portale-servizi-factory/ --adapter=cursor

# External mode + dry-run (combinazione sicura per ricognizione iniziale)
/refactor .claude/agents/<agent-slug>.md --external /Users/simone.olivieri/soli-boy/ --dry-run
```

---

## Vincoli

- **Gate `refactor_agent_skills.enabled`** (Step 0): il comando non procede e non
  e' silenzioso a flag spento — emette un errore esplicito con le istruzioni di
  attivazione.
- **`--external` richiede path assoluto**: path relativi sono rifiutati (Step 1).
  La semantica dipende dal CWD e renderebbe l'operazione non-riproducibile.
- **Guard EP-060 in factory esterna** (Step 4): il fleet-doctor non installa nulla
  nella factory esterna; se EP-060 manca, STOP esplicito con le istruzioni di upgrade
  (Decisione 4 ADR-EP060-003 — Opzione A, nessun partial-install).
- **V-3 preserved**: il frontmatter di triggering/dispatch del target NON viene
  modificato dal refactor (invariante di equivalenza comportamentale EP-060).
- **Backward-compat totale**: senza `--external`, il comportamento e' identico
  all'invocazione manuale di `fleet-doctor` in self mode. Zero side-effect su
  factory che non usano `--external`.
- **Factory master read-only in external mode**: in `--external`, il fleet-doctor
  opera solo nella factory target. Nessuna scrittura nella factory corrente.
- **`--dry-run` consigliato** per la prima esecuzione su una factory esterna ignota.
  Obbligatorio per ricognizione senza side-effect.
- **Thin dispatcher**: nessuna logica business in questo comando; solo
  parse + validate + dispatch verso `fleet-doctor`.

---

## Prerequisiti

- `factory.config.yaml.refactor_agent_skills.enabled: true` (gate Step 0).
- `.claude/agents/fleet-doctor.md` presente nella factory corrente.
- Per self mode: il file `<target>` esiste nella factory corrente.
- Per external mode:
  - `<external_path>/` esiste ed e' accessibile.
  - `<external_path>/<adapter_dir>/` esiste (adapter installato).
  - `<external_path>/<adapter_dir>/skills/references/refactor/` esiste (EP-060
    installato nella factory target).
  - `<external_path>/<target>` esiste.

Sezione minima in `factory.config.yaml`:

```yaml
refactor_agent_skills:
  enabled: true
```

---

## Cross-link

- **Agente invocato**: `.claude/agents/fleet-doctor.md` (EP-060)
- **Skill eseguita**: `.claude/skills/refactor-agent-skills.md` (EP-060 TSK-556)
- **ADR normativo**: `design_&_architecture/decisions/ADR-EP060-003-external-target-foundation.md`
- **US di appartenenza**: `management/kanban/EP-060-fleet-health/US-237-implementazione-refactor-external/`
- **EP root**: `management/kanban/EP-060-fleet-health/`
- **Analogia strutturale**:
  - `/tavola-rotonda` (EP-039) — gate config + parse flag + dispatch agente
  - `/review` (v2.12) — gate config + invocazione agente + report finale
  - `/prototype` (EP-035) — gate config + parse flag + dispatch agente + output artefatto

[^src: design_&_architecture/decisions/ADR-EP060-003-external-target-foundation.md §Decisione 1..4]
[^src: management/kanban/EP-060-fleet-health/US-237-implementazione-refactor-external/TSK-554.md §Technical Specs]
