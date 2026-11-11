---
description: "Travaso di un albero di codice da un repo sorgente a uno SHA immutabile verso un repo target, senza trasferire history. Gate fail-closed G1-G4. Push sempre gate umano. Richiede repo_handover.enabled: true in factory.config.yaml."
argument-hint: '<source>@<sha> <target> [--path=<subdir>] [--exclude=<pattern>] [--dry-run]'
version: "1.0"
since: "2026-10-05"
status: active
trigger: /repo-handover
owner: soli92
epic: EP-069
us: US-318
---

# /repo-handover — Travaso sorgente→target senza history

Argomenti utente: `$ARGUMENTS`

Porta il codice da un repo sorgente (a SHA immutabile) a un repo target,
**senza trasferire history, senza creare merge-base**. Progettato per i casi
in cui target e sorgente hanno storie non correlate.

---

## Fallback a capability spenta

Leggi `factory.config.yaml` e verifica `repo_handover.enabled`.

Se `repo_handover.enabled` è `false` o assente:

```
Capability repo-handover non attiva.
Per abilitarla: imposta repo_handover.enabled: true in factory.config.yaml.
Blocco di config di riferimento: .claude/skills/references/repo-handover-protocol/config-block.md
```

**STOP** — non procedere oltre.

---

## Sintassi

```
/repo-handover <source>@<sha> <target> [--path=<subdir>] [--exclude=<pattern>] [--dry-run]
```

| Argomento | Obbligatorio | Significato |
|---|---|---|
| `<source>@<sha>` | SI | Path al repo sorgente + SHA del commit da travasare |
| `<target>` | SI | Path al repo target |
| `--path=<subdir>` | no | Limita il travaso a una sottodirectory del sorgente (ripetibile) |
| `--exclude=<pattern>` | no | Pattern fnmatch da escludere (ripetibile) |
| `--dry-run` | no | Elenca i file senza scrivere nel target |

Esempi:

```bash
# Dry-run: mostra i file che verranno trasferiti
/repo-handover /path/to/source@a1b2c3d /path/to/target --dry-run

# Travaso della sottodirectory src/ escludendo i log
/repo-handover /path/to/source@a1b2c3d /path/to/target \
    --path=src --exclude="*.log"
```

---

## Esecuzione — 4 gate fail-closed

Eseguire i gate in sequenza. Non avanzare a Gn+1 se Gn non è verde.

### G1 — Preflight

```bash
# (a) SHA immutabile nel sorgente
git -C "<source>" cat-file -t "<sha>"   # deve stampare "commit"

# (b) Target pulito
git -C "<target>" status --porcelain    # deve essere vuoto

# (c) Branch di arrivo dichiarato e attivo nel target
git -C "<target>" branch --show-current
```

**Se (a) fallisce:** il SHA non esiste nel sorgente — verificare il parametro.
**Se (b) fallisce:** committare o stashare le modifiche nel target, poi ripetere G1.
**Se (c):** creare il branch se non esiste (`git -C <target> checkout -b <branch>`).

---

### G2 — Selezione dell'albero (gate umano)

Eseguire il dry-run e presentare il perimetro all'utente:

```bash
python3 tools/vcs/repo_handover.py \
    --source "<source>" --sha "<sha>" \
    --target "<target>" \
    [--path <subdir>] [--exclude <pattern>] \
    --dry-run
```

Mostrare:
- Conteggio totale dei file
- Lista completa (o campione top-20 se >20 file)

**Attendere conferma esplicita dell'utente prima di procedere a G3.**

---

### G3 — Import nel target

Dopo conferma G2, eseguire il travaso:

```bash
python3 tools/vcs/repo_handover.py \
    --source "<source>" --sha "<sha>" \
    --target "<target>" \
    [--path <subdir>] [--exclude <pattern>]
```

Poi creare il commit di import nel target.

**Messaggio di commit obbligatorio** (includere il registro di provenienza):

```
chore: import da <source_slug>@<sha_short>

Sorgente: <source_path>
SHA: <sha>
Data: <YYYY-MM-DD>
```

**Se `ai_attribution_policy.suppress_ai_traces: true` nel target:**
usare `python3 tools/vcs/sm_commit.py` invece di `git commit` diretto.

```bash
# Staging
git -C "<target>" add -A

# Verifica cosa stai committando
git -C "<target>" status --short

# Commit (con filtri ai_policy se suppress_ai_traces: true)
python3 tools/vcs/sm_commit.py \
    --path "<target>" \
    "chore: import da <source_slug>@<sha_short>

Sorgente: <source_path>
SHA: <sha>
Data: <YYYY-MM-DD>"
```

**Gate locali opzionali:** se `repo_handover.local_gates[]` è valorizzato in
`factory.config.yaml`, eseguire i gate locali via `worktree-gate` sul commit
appena creato prima di procedere a G4.

---

### G4 — Conferma push / apertura PR (gate umano)

Presentare il riepilogo:

```bash
git -C "<target>" log --oneline origin/<branch>..HEAD
git -C "<target>" diff --stat origin/<branch>..HEAD
```

**STOP — §7 r.14:** nessun push automatico.

Riportare all'utente:
- Numero di commit pronti al push
- Diff stat di riepilogo
- Comando da eseguire per il push (senza eseguirlo)

```bash
# Comando da eseguire (proposto, non eseguito automaticamente)
git -C "<target>" push origin <branch>
# oppure per aprire una PR:
gh pr create --repo <owner/repo> --base main --head <branch>
```

---

## Nessuna scrittura nel repo sorgente

Il sorgente è **read-only** in ogni fase. L'unica operazione eseguita sul sorgente
è `git archive` (lettura).

---

## Riferimenti

- Skill: `.claude/skills/repo-handover-protocol.md`
- Config di riferimento: `.claude/skills/references/repo-handover-protocol/config-block.md`
- Script: `tools/vcs/repo_handover.py`
- Gate locali: `.claude/skills/worktree-gate.md`
- Commit con §ai_policy: `tools/vcs/sm_commit.py`
