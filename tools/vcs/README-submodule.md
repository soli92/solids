---
type: tool-readme
title: "Submodule tooling guidato dalla config"
status: active
epic: EP-069
us: US-311
updated_by: US-325
created: 2026-10-05
updated: 2026-10-06
ingest_eligible: false
---

# Runbook: Submodule tooling guidato dalla config

Tooling Python stdlib-only per la gestione dei submodule dichiarati in
`factory.config.yaml` (code_paths[] con `vcs.mode: submodule`). Cross-platform:
macOS, Linux, Windows nativo (cmd/PowerShell/Git Bash).

Backportato da portale-servizi-factory (US-311 EP-069): tutte le costanti
verticali (host, nomi repo, prefissi directory) sono rimosse -- i target
vengono dalla config.

---

## Prerequisito unico: Python 3.9+

- **macOS / Linux**: `python3` e' quasi sempre presente. Verifica: `python3 --version`
- **Windows**: installa Python da [python.org](https://www.python.org/downloads/).
  Verifica in PowerShell / cmd: `python --version` (oppure `py --version`).

Nessun'altra dipendenza: gli script usano solo la **standard library**.

---

## Come invocare gli script

### macOS / Linux

```bash
python3 tools/vcs/sm_doctor.py --dry-run
python3 tools/vcs/sm_status.py
python3 tools/vcs/sm_commit.py --coordinated "fix: bug" --target my-repo --push
python3 tools/vcs/sm_checkout.py develop --target my-repo
python3 tools/vcs/sm_update.py --merge --target my-repo
python3 tools/vcs/install_submodule_hooks.py --dry-run
python3 tools/vcs/install_factory_hooks.py --dry-run
```

### Windows nativo (PowerShell o cmd)

```powershell
python tools\vcs\sm_doctor.py --dry-run
python tools\vcs\sm_status.py
python tools\vcs\sm_commit.py --coordinated "fix: bug" --target my-repo
python tools\vcs\sm_checkout.py develop --target my-repo
python tools\vcs\sm_update.py --merge --target my-repo
python tools\vcs\install_submodule_hooks.py --dry-run
python tools\vcs\install_factory_hooks.py --dry-run
```

> Se `python` non e' nel PATH prova `py tools\vcs\...`.

### Windows con Git Bash / WSL

```bash
python3 tools/vcs/sm_doctor.py --dry-run
```

---

## Quali submodule senza `--target`

`vcs_tooling.submodule_scope` decide su quali submodule lavorano `sm_status`, `sm_doctor`,
`sm_update` e `sm_checkout` quando non si passa `--target`:

| Valore | Submodule |
|---|---|
| `code_paths` (default) | i dichiarati in `code_paths[]` con `vcs.mode: submodule` |
| `gitmodules` | tutti quelli di `.gitmodules`, nell'ordine del file |

`gitmodules` serve alle factory con molti submodule di servizio che non sono code_path (una
derivata ne ha 63 e ne dichiara 4). Con `--target` lo scope non conta: si cerca in `.gitmodules`.

`vcs_tooling.default_target: <nome>`: il submodule su cui lavorano `sm_checkout`, `sm_update` e
`sm_commit --coordinated` quando `--target` manca e i candidati sono piu' d'uno. Senza, quei
comandi chiedono `--target` invece di scegliere: nessuno aggiorna 63 submodule per sbaglio.

## Senza submodule dichiarati in config

Se `factory.config.yaml` non ha entry `code_paths[]` con `vcs.mode: submodule`,
**ogni tool esce 0 con un messaggio esplicito**:

```
Nessun submodule dichiarato in factory.config.yaml (code_paths[] con vcs.mode: submodule).
```

Non e' un errore. Questa factory potrebbe non avere submodule gestiti. Per
aggiungere un submodule alla gestione:

```yaml
# in factory.config.yaml
code_paths:
  - name: my-repo
    path: code_repos/my-repo
    vcs:
      mode: submodule
      base_branch: main
```

---

## Submodule archiviati (US-325)

Un submodule puo' essere marcato come archiviato (read-only sull'host remoto)
aggiungendo la chiave `archived = true` nella sezione corrispondente di
`.gitmodules`:

```ini
[submodule "code_repos/my-archived-repo"]
    path = code_repos/my-archived-repo
    url  = https://example.com/my-archived-repo.git
    branch = main
    archived = true
```

**Fonte unica**: `.gitmodules` (non `factory.config.yaml`). Git stesso legge
`.gitmodules` ed e' il luogo naturale per metadati di submodule.

**Comportamento dei tool con `archived = true`**:

| Tool | Comportamento |
|---|---|
| `sm_checkout.py` | Rifiuta (exit 1, messaggio «archiviato: sola lettura») |
| `sm_commit.py --coordinated` | Rifiuta (exit 1) |
| `sm_update.py` | Rifiuta (exit 1) |
| `sm_doctor.py` | Solo informativo — nessun healed, nessun needs_human |
| `sm_status.py` | Mostra etichetta `[archiviato (read-only)]`; nessun segnale di drift puntatore |
| `init_check.py` | Entry separata PASS «submodule (archiviati)», escluso dal perimetro |
| `repo-align.py` | `unverified: archived` (la verifica remota non ha senso su un repo read-only) |
| `/session-start` | Mostrato senza numero, non selezionabile, non entra nel sync |

---

## sm_doctor.py -- diagnosi + auto-heal

```
python3 tools/vcs/sm_doctor.py [--target <nome>] [--align] [--dry-run] [--quiet]
```

| Caso | Comportamento |
|------|---------------|
| Submodule non inizializzato | `git submodule update --init` (auto) |
| Out of sync + tree pulito + detached | Allinea al puntatore (auto) |
| Hook §ai_policy mancanti | Reinstalla (auto, solo se `suppress_ai_traces: true`) |
| Out of sync + modifiche non committate | Segnala + suggerisce stash (mai tocca) |
| Out of sync + su branch | Segnala (propone `--align` o pointer-only) |

Exit 0 = tutto in ordine o auto-riparato. Exit 1 = azioni umane residue.

**Invariante**: mai `--force`, mai `git clean`, mai reset di tree sporchi.

---

## sm_commit.py -- commit coordinato (modalita' --coordinated)

Estende l'esistente `sm_commit.py` con una modalita' coordinata per factory
con submodule:

```bash
# FASE 1: commit nel submodule + push + FASE 2: bump puntatore factory
python3 tools/vcs/sm_commit.py --coordinated "fix: bug" --target my-repo --push

# Solo bump puntatore (FASE 2) se il submodule e' gia' su remote
python3 tools/vcs/sm_commit.py --coordinated --pointer-only --target my-repo

# Commit submodule senza bump puntatore (branch effimero non ancora mergiato)
python3 tools/vcs/sm_commit.py --coordinated "fix: bug" --target my-repo --no-pointer
```

**Filtri §ai_policy** (sempre attivi in entrambe le modalita'):
- Strip attribution AI dal messaggio
- Strip ID kanban factory dal messaggio
- Gate di conferma se il messaggio viene alterato

**Gate REMOTE**: prima di aggiornare il puntatore factory, verifica che il
commit del submodule sia presente su un branch remoto. Se non lo e', offre
tre opzioni: push adesso / skip (rischio dangling ref) / abort.

---

## install_factory_hooks.py -- hook auto-align nel repo padre

```bash
python3 tools/vcs/install_factory_hooks.py --dry-run   # diagnosi
python3 tools/vcs/install_factory_hooks.py             # installa
python3 tools/vcs/install_factory_hooks.py --force     # sovrascrive senza prompt
```

Installa `post-merge` e `post-checkout` nel repo padre (`.git/hooks`).
Dopo ogni `git pull` / `git checkout <branch>`, i submodule seguono
automaticamente il commit tracciato (chiama `sm_doctor.py --align --quiet`).

**Non distruttivi**: il doctor salta i tree con modifiche non committate.

---

## install_submodule_hooks.py -- hook §ai_policy nei submodule

```bash
python3 tools/vcs/install_submodule_hooks.py --dry-run
python3 tools/vcs/install_submodule_hooks.py
python3 tools/vcs/install_submodule_hooks.py --target my-repo --force
```

**Gating**: si attiva SOLO se `ai_attribution_policy.suppress_ai_traces: true`
in `factory.config.yaml`. Se il flag e' assente o false, l'installer avvisa
e non installa nulla (exit 0 -- non e' un errore).

Installa `pre-commit` e `commit-msg` nei submodule dichiarati in config.

**Attenzione `core.hooksPath`**: se il submodule usa husky o un hook manager
che ridefinisce `core.hooksPath`, git IGNORA `.git/hooks` -- gli hook §ai_policy
sarebbero inerti. L'installer lo rileva e avvisa (non installa, non tace).

---

## Configurazione clone locale (sm_update --from-local)

Per aggiornare un submodule da un clone locale senza rete:

```bash
# Crea tools/vcs/.env.local-repos (gitignored) con:
LOCAL_REPO_MY_REPO=/path/al/repo/locale

# Poi:
python3 tools/vcs/sm_update.py --from-local develop --target my-repo
```

Il file `.env.local-repos` e' gitignored. Usa forward slash anche su Windows.

---

## Windows -- note specifiche

### Git Bash vs PowerShell/cmd

Le skill e i comandi usano bash. Su Windows:
- **Git Bash** (raccomandato): usa `python3 tools/vcs/...`
- **PowerShell / cmd**: usa `python tools\vcs\...` (nessun forward slash)
- **PowerShell / cmd non supportato** per i workflow bash delle skill

### Nomi di file

I nomi di file illegali su Windows (`< > : " | ? *`, DOS reserved, punto/spazio finali)
rendono impossibile `git clone`. Verifica:

```bash
python3 tools/lint/check-portable-paths.py
```

### Blocco `protocol.file.allow`

`sm_doctor.py` e `sm_update.py` usano `-c protocol.file.allow=always` per
`git submodule update --init`. Su Windows con Git recente questo e' necessario
quando il remote e' un path locale (es. `--from-local`).

### CRLF

Gli script `.sh` e i hook devono avere LF. Se un hook fallisce con
`$'\r': command not found`, la causa e' CRLF:

```bash
git config core.autocrlf input
```

---

## Cross-link

- **Diagnosi**: `/sm-doctor` (`.claude/commands/sm-doctor.md`)
- **Tool principale**: `tools/vcs/sm_doctor.py`
- **API §ai_policy**: `tools/vcs/ai_policy.py` (fonte unica pattern)
- **Libreria condivisa**: `tools/vcs/smlib/`
- **Config**: `factory.config.yaml` blocco `vcs_tooling` (opt-in, default disabled)
- **Test**: `tests/vcs/` (48 test)
