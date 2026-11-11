---
name: repo-align
description: "Verifica se il lavoro locale e' gia' sul remote, per tutti i vcs.mode di PATTERN §15 (monorepo, submodule, sibling, external). Zero mutazione: usa solo git ls-remote. Verdetto per target: aligned | diverged | unverified. Per diverged distingue avanti (commit locali non pushati) da indietro (remote avanti). Funziona anche a repo_align.enabled: false (on_explicit: true)."
argument-hint: "[--repos=<n1,n2>] [--json]"
allowed-tools: Bash
---

# /repo-align

Risponde a: **«il mio lavoro locale e' gia' sul remote?»** — senza toccare nulla.

Per ogni target dichiarato in `factory.config.yaml` (`code_paths[]` + legacy `code_path:`),
esegue la verifica appropriata al suo `vcs.mode` (PATTERN §15) e restituisce un verdetto
in `{aligned, diverged, unverified}`.

Il caso `diverged` distingue **avanti** (ho commit che il remote non ha, il mio silenzio
e' invisibile al resto della flotta) da **indietro** (il remote ha commit che io non ho
ancora).

**Zero mutazione assoluta (R.14, R.B8)**: l'unica operazione con effetti remoti e'
`git ls-remote`. MAI `fetch`, `pull`, `checkout`, `reset`, `submodule update`.

**on_explicit: true** — il comando funziona **anche** a `repo_align.enabled: false` in
`factory.config.yaml`. La configurazione controlla i trigger automatici (post-TSK, post-session),
non l'esecuzione esplicita.

---

## Utilizzo

```bash
/repo-align                         # tutti i target da factory.config.yaml
/repo-align --repos=factory,be-api  # solo i target indicati (per nome)
/repo-align --json                  # output machine-readable JSON
```

Lo script invocato: `tools/vcs/repo-align.py`

```bash
python3 tools/vcs/repo-align.py [--repos=<n1,n2>] [--json] [--config=<path>]
```

---

## Comportamento per vcs.mode (PATTERN §15)

| `vcs.mode`  | Primitiva | Verdetto possibile |
|---|---|---|
| `monorepo`  | `git rev-parse HEAD` vs `git ls-remote origin refs/heads/<branch>` | aligned / diverged / unverified |
| `submodule` | `git ls-files -s <path>` (gitlink-SHA nel parent) vs `ls-remote` nel submodule | aligned / diverged / unverified |
| `sibling`   | come monorepo, nel working tree del sibling | aligned / diverged / unverified |
| `external`  | — | unverified (reason: opaque_topology) |
| `none`      | — | escluso dal set (non target, non unverified) |

**Nota submodule**: il detached HEAD del submodule NON e' segnale di divergenza.
Il confronto e' sempre gitlink-SHA nel parent vs SHA remoto — mai HEAD locale del submodule.

---

## Output testuale

```
[repo-align — snapshot @2026-09-25T14:39:09Z]
=====================================================
Primitiva: git ls-remote --heads (zero mutazione su working tree e refs/remotes/)

ALIGNED (1):
  factory-guide        mode=monorepo   branch=main
    local=abc1234 == remote=abc1234

DIVERGED (1):
  factory              mode=monorepo   branch=main
    local=cac8177 != remote=79101e4
    -> avanti di 1 commit (commit locali non presenti sul remote)

UNVERIFIED (0): (nessuno)

-----------------------------------------------------
Nessuna azione automatica eseguita (R.14, R.B8).
```

---

## Reason enum per unverified

`unreachable | auth_failure | auth_missing | no_remote | detached_head | not_a_git_repo | opaque_topology | base_branch_undeclared | base_branch_misplaced | archived`

`auth_missing`: il remote ha rifiutato e il token dichiarato in `auth_domains[]` non si
risolve, ne' in ambiente ne' in `env_file`. Senza token dichiarato lo stesso rifiuto resta
`auth_failure`.

`base_branch_misplaced`: il submodule dichiara `base_branch` dentro `vcs.branch_awareness`
invece che in `vcs.base_branch` (PATTERN §15). Il valore non viene usato, perche' non lo
usano nemmeno `branch-resolver` e il dispatch gate: un verdetto calcolato su quel branch
direbbe una cosa diversa dal gate. Si sposta la riga e il target diventa verificabile.

---

## Cosa il comando NON fa

- Non allinea nulla.
- Non pusha, non fetcha, non esegue checkout.
- Non modifica il working tree in alcun modo.
- Non agisce: osserva e dichiara.

---

## Configurazione opzionale (`factory.config.yaml`)

Il blocco `repo_align:` e' opzionale (default: assente = tool disponibile a invocazione esplicita):

```yaml
repo_align:
  enabled: false            # trigger automatici on/off; on_explicit sempre true
  triggers:
    on_tsk_closed_count: 5  # verifica ogni N TSK chiusi
    on_session_close: false # verifica a fine sessione
  env_file: .env.locale     # opzionale: file KEY=VALUE per i token assenti dall'ambiente (letto, mai eseguito)
  auth_domains:             # opzionale: token per remote privati; lookup per name o per path
    - path: code_repos/my-api
      remote: origin
      branch: main              # branch PRIMARIO che il gitlink segue, non il feature branch
      token_env_var: MY_API_TOKEN   # (o token_env) env var con il token; assente → credenziali d'ambiente
```

Se `auth_domains` e' assente o un repo non vi e' mappato, si usano le credenziali gia'
in ambiente (git credential store). Fallimento di autenticazione → `unverified: auth_failure`,
mai un crash.

---

## Cross-link

- Script: `tools/vcs/repo-align.py`
- Test: `tools/tests/test_repo_align.py`
- Storia: `management/kanban/EP-068-backport-enforcement-factory-derivata/US-299-repo-align-multi-vcs-mode/US-299.md`
- PATTERN §15 (VCS integration)
- Comando correlato: `/vcs-status` (stato branch/HEAD/drift, focus submodule)
