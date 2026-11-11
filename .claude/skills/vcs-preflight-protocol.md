---
name: vcs-preflight-protocol
description: >-
  Snapshot read-only dello stato VCS: branch vs atteso, detached HEAD, submodule non inizializzato, drift parent-ref vs submodule-HEAD. Produce tabella + comandi di remediation. Mai muta lo stato. Invocata da /vcs-status e dal dashboard /run.
epic_id: EP-034
pattern_version: "2.25"
---
# Skill — vcs-preflight-protocol

Produce uno **snapshot read-only** dello stato VCS di tutti i target della factory, per
rendere immediatamente visibile «su quale branch sto / su quale dovrei stare», con focus sui
submodule (problema dei due HEAD, PATTERN §15 §Branch Awareness Layer).

**READ-ONLY assoluto (R.B7)**: usa solo `git status`, `git branch`, `git rev-parse`,
`git symbolic-ref`, `git merge-base`, `git submodule status`, `git ls-files`, lettura di
`.gitmodules`/`.factory-branches.yaml`. **Mai** `checkout`, `commit`, `fetch`, `pull`, `reset`,
`submodule update`. Non modifica nessun file. Non è un gate: informa, non blocca.

---

## Step 1 — Bootstrap

1. Leggi `factory.config.yaml`. Raccogli i target:
   - Multi-repo: ogni entry di `code_paths` con `vcs.mode ∈ {submodule, sibling, monorepo}`
     (`external`/`none` → riga informativa «non gestito», nessun check branch).
   - Legacy single-repo: la entry `vcs:` top-level.
2. Determina la modalità di invocazione:
   - **Esplicita** (`/vcs-status`): esegui sempre, anche a `branch_awareness.enabled: false`
     (esecuzione esplicita = volontà esplicita).
   - **Dashboard** (da `/run`): esegui solo se `branch_awareness.enabled: true` AND
     `branch_awareness.preflight: true`. Altrimenti no-op (R.B10).
3. Leggi opzionalmente `.factory-branches.yaml` (manifest per-sprint), se presente.

## Step 2 — Raccolta stato per target (read-only)

Per ciascun target, esegui i comandi di sola lettura appropriati al `mode`.

### Determina la directory git
- `monorepo` → factory repo root.
- `submodule` → `<submodule_path>`. Prima verifica init: se `<submodule_path>/.git` **non
  esiste** → stato = `NOT_INITIALIZED`, salta gli altri check per questo target.
- `sibling` → `<path>` (repo esterno).

### Comandi (per la git dir del target)
```bash
# branch corrente ("HEAD" se detached)
git -C <dir> symbolic-ref --quiet --short HEAD 2>/dev/null || echo "(detached)"
# commit corrente
git -C <dir> rev-parse --short HEAD
# stato working tree (pulito/sporco)
git -C <dir> status --porcelain
```

### Detached HEAD (submodule/sibling)
Se `symbolic-ref` fallisce → **detached**. In più, per aiutare la scelta del branch:
```bash
# branch locali che contengono il commit corrente (candidati per il checkout)
git -C <dir> branch --contains HEAD --format='%(refname:short)'
```

### Drift parent-ref vs submodule-HEAD (solo `submodule`, se `drift_check` o invocazione esplicita)
```bash
# commit registrato dal parent (gitlink) per questo submodule
git -C <factory-root> ls-tree HEAD <submodule_path> | awk '{print $3}'   # -> parent_ref (short via rev-parse)
# commit realmente checked-out nel submodule
git -C <submodule_path> rev-parse HEAD                                     # -> sub_head
```
Se `parent_ref != sub_head` → **drift** (segnala).

## Step 2-bis — Remote perimeter staleness (EP-053, opt-in per submodule multi-utente)

Check **informativo** applicabile ai target `submodule` con `branch_awareness.enabled: true`.
Emette al più un WARN — non blocca mai (R.14). Eseguito dopo la raccolta dello stato locale
(Step 2) e prima della determinazione del branch atteso (Step 3).

Per ciascun target submodule eleggibile, esegui:

```bash
# Aggiorna i ref di tracking remoto (solo ref, non il working tree)
git -C <submodule_path> fetch --quiet origin
# File divergenti tra HEAD locale e tip remoto del branch base
git -C <submodule_path> diff --name-only HEAD...origin/<base_branch>
```

dove `<base_branch>` è il branch corrente nel submodule (da Step 2) oppure il branch atteso
da `branch-resolver` se già noto.

Se l'intersezione tra {file remoti cambiati} e {glob del TSK `code_path`} è **non vuota**
→ emetti WARN visibile:

> **WARN — Remote perimeter staleness**: il branch remoto (`origin/<base_branch>`) ha
> modifiche sui file nel tuo perimetro di lavoro (`<glob>`). Considera un `git pull`
> prima di procedere per evitare race con collaboratori umani.

Regole di applicazione:
- Il WARN è **solo informativo** — non blocca il dispatch (R.14).
- **Non eseguire `git pull` o `git merge` automaticamente.**
- Se il `diff --name-only` restituisce lista vuota (o la sovrapposizione con `code_path` è
  vuota) → nessun output; non emettere WARN inutili.
- Se `git fetch` fallisce (rete assente, autenticazione) → log nota «remote staleness check
  non eseguito (fetch fallito)» e prosegui senza WARN.
- Applicabile **solo** ai target `submodule` con `branch_awareness.enabled: true`; gli altri
  target restano no-op per questo step.

> **Nota R.B7**: `git fetch --quiet origin` è permesso in questo step perché aggiorna
> esclusivamente i ref di tracking remoto (`origin/*`), senza modificare HEAD, il working
> tree, né la staging area. È classificato «read per lo stato locale» in questa skill.
> Tutti gli altri comandi vietati da R.B7 (`pull`, `checkout`, `commit`, `reset`,
> `submodule update`) restano proibiti.

[^src: portale-servizi-factory .claude/skills/vcs-preflight-protocol.md §Step 2-bis — EP-053 backport 2026-07-30]

## Step 3 — Expected branch

Per ciascun target invoca `branch-resolver` (single source of truth, R.B9) passando
`resolved_vcs`, il `target_name` e — se disponibile in contesto — il TSK corrente. In modalità
snapshot generale senza TSK, `per-tsk`/`per-sprint` ritornano `expected_branch: null` (vedi
`branch-resolver` Step 3): in quel caso non emettere verdict ACTION sul *naming*, ma continua a
valutare detached/NOT_INITIALIZED/drift.

## Step 4 — Verdict per target

| Condizione | Verdict |
|---|---|
| `NOT_INITIALIZED` | **ACTION** — submodule non inizializzato |
| detached HEAD | **ACTION** — HEAD detached |
| drift parent-ref ≠ submodule-HEAD | **ACTION** — drift |
| `expected_branch` valorizzato E ≠ branch corrente | **ACTION** — branch mismatch |
| tutto allineato (o expected null e HEAD su un branch) | **OK** |

`WARN` (non ACTION): working tree sporco su branch atteso corretto → nota informativa, non blocca.

## Step 5 — Output (tabella + remediation)

Stampa una tabella markdown:

```
| target | mode | branch corrente | branch atteso | HEAD | drift | verdict |
|---|---|---|---|---|---|---|
| backend-api  | submodule | (detached @a1b2) | tsk-042-... | ⚠ detached | ✗ parent@a1b2≠sub@c3d4 | ACTION |
| frontend-web | sibling   | develop          | develop     | ✓         | —                      | OK     |
```

Poi, per **ogni riga ACTION**, il comando esatto di remediation:

- **NOT_INITIALIZED** → `git submodule update --init <submodule_path>`
- **detached** con branch candidato dal `--contains` → `git -C <dir> checkout <candidato>`;
  se nessun candidato → `git -C <dir> checkout -b <expected_branch>` (o il branch desiderato).
- **branch mismatch** → `git -C <dir> checkout <expected_branch>`
- **drift** → mostra i due commit e spiega: «il parent punta a X, il submodule è su Y. Per
  allineare il parent al submodule: `git -C <factory-root> add <submodule_path>` poi commit;
  per allineare il submodule al parent: `git -C <submodule_path> checkout X`». **Non scegliere
  automaticamente** — la direzione è una decisione umana.

Chiudi con un riepilogo: `N target · K OK · M ACTION`. Se M=0 → «Tutti i target allineati».

## Vincoli inviolabili

- **R.B7 read-only**: nessun comando che muti stato. Se serve muovere un branch, **stampa** il
  comando; l'umano lo esegue. Mai eseguirlo da qui.
- **Non è un gate**: `/vcs-status` non blocca mai un flusso. Il blocco (opt-in) vive nel gate
  Fase 0 di `dev-protocol` (`dispatch_gate`), non qui.
- **Robustezza**: target non-git, path assente, `.gitmodules` mancante → riga con nota, mai
  crash dell'intero snapshot (best-effort per-target, isola i fallimenti).

## Cross-link

- PATTERN §15 §«Branch Awareness Layer» (R.B7, tabella inspect).
- `branch-resolver` (expected branch), `vcs-handoff` (commit-time, condivide il resolver).
- Comando `/vcs-status`; integrazione dashboard: `orchestrator.md` §VCS Branch Preflight.
- ADR-EP034-001.
