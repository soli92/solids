---
name: worktree-gate
description: >-
  Gate locali su SHA immutabile: worktree git detached con hooks disabilitati
  (core.hooksPath=/dev/null), dipendenze condivise via symlink, exit code di ogni
  comando letto senza pipe, cleanup garantito anche su errore. Portabile
  Linux/macOS/WSL2. Invocata da artifact-release-protocol (Fase 1c) e, facoltativamente,
  da release-protocol come opzione per i propri gate locali. Script di supporto:
  tools/release/worktree_gate.py (stdlib).
---
# Skill: worktree-gate

Gate locali su SHA immutabile in un worktree temporaneo. L'obiettivo e' eseguire
una sequenza di comandi (build, lint, test) su un commit preciso senza toccare il
working tree corrente del repo, anche se usato da altre sessioni in parallelo.

---

## Invarianti locali

| Codice | Invariante |
|---|---|
| R.WG1 | Il worktree e' sempre `--detach`: nessun branch viene spostato. |
| R.WG2 | Gli hooks git sono sempre disabilitati nel worktree: `-c core.hooksPath=/dev/null`. |
| R.WG3 | Il cleanup del worktree e' garantito anche in caso di errore o SIGINT (trap). |
| R.WG4 | L'exit code di ogni comando e' letto senza pipe: la pipe maschera il codice reale. |
| R.WG5 | Il path del worktree e' nella directory di scratch di sessione, mai nel repo. |

---

## Algoritmo

```
Input:
  repo_path            : path assoluto al repo (o submodulo) da gating
  sha                  : SHA del commit su cui eseguire i gate
  commands             : lista ordinata di comandi shell (stringa ciascuno)
  node_modules_symlink : (opzionale) path assoluto alla directory da linkare come node_modules
  workdir_in_wt        : (opzionale) sottodirectory del worktree da usare come cwd (default: root WT)
  extra_env            : (opzionale) variabili aggiuntive da esportare nel contesto del worktree

Output:
  exit 0  → tutti i comandi PASS
  exit 1  → almeno un comando FAIL (con output del comando fallito)
```

### Passo 1 — Crea worktree detached

```bash
# WT nella directory di scratch di sessione (mai nella root del repo)
WT="$CLAUDE_SCRATCHPAD/wt-gate-$(date -u +%s)"

trap "git -C '$repo_path' worktree remove --force '$WT' 2>/dev/null; exit" EXIT INT TERM

git -C "$repo_path" fetch origin >/dev/null 2>&1 || true  # best-effort, non bloccante
git -C "$repo_path" -c core.hooksPath=/dev/null worktree add --detach "$WT" "$sha"
```

> `CLAUDE_SCRATCHPAD` e' la variabile di sessione che punta alla directory di scratch
> (`/private/tmp/claude-<uid>/...`). Se non disponibile nell'ambiente del comando,
> usa `TMPDIR` o `/tmp` con un nome univoco (UUID o timestamp).

### Passo 2 — Dipendenze condivise (opzionale)

```bash
# Solo se node_modules_symlink e' valorizzato
if [ -n "$node_modules_symlink" ]; then
  ln -s "$node_modules_symlink" "$WT/node_modules"
fi
```

Usare i `node_modules` del submodule originale via symlink evita un `npm install`
nel worktree (piu' veloce, stesso albero di dipendenze). Funziona solo se il worktree
e il submodule condividono la stessa versione di `package.json`.

Se la versione e' diversa (es. il bump introduce nuove dipendenze):
```bash
# Alternativa: install completo nel worktree (piu' lento, isolato)
npm --prefix "$WT" install --ignore-scripts 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: npm install fallito (exit $rc)."; exit $rc; }
```

### Passo 3 — Esecuzione gate (senza pipe)

```bash
cd "$WT${workdir_in_wt:+/$workdir_in_wt}"

# Esporta variabili aggiuntive
for var in $extra_env; do export "$var"; done

# Esegui ogni comando; leggi exit code direttamente
for cmd in "${commands[@]}"; do
  echo "[gate] Esecuzione: $cmd"
  eval "$cmd"          # eval necessario per comandi con spazi/flag
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "[gate FAIL] '$cmd' ha restituito exit $rc."
    exit $rc           # la trap garantisce il cleanup
  fi
  echo "[gate PASS] '$cmd'"
done
```

> **Perche' senza pipe**: `cmd | tail -n 20` fa uscire lo script con il codice di `tail`
> (sempre 0), mascherando un `command not found` o un fallimento del gate.
> Salvare stdout/stderr in una variabile e' l'alternativa portabile a `tee`:
> ```bash
> OUT=$(eval "$cmd" 2>&1); rc=$?
> echo "$OUT"
> [ $rc -ne 0 ] && exit $rc
> ```

### Passo 4 — Cleanup (garantito da trap)

La trap `EXIT INT TERM` esegue `git worktree remove --force` in ogni caso.
L'uscita pulita (exit 0) e quella con errore (exit 1) passano entrambe dalla trap.

---

## Invocazione da artifact-release-protocol

La skill `artifact-release-protocol` chiama `worktree-gate` con i parametri letti da
`release_targets[].local_gates[]`. Il formato nel config e':

```yaml
local_gates:
  - "npm run lint"
  - "npm run build"
  - "npm test"
```

Il `sha` e' `MAIN_SHA` risolto nella Fase 1a del protocollo.

---

## Invocazione da release-protocol (factory)

La skill `release-protocol` (processo di rilascio **della factory**) puo' usare
`worktree-gate` come opzione per i propri gate locali pre-tag.

Rimando: vedi `.claude/skills/release-protocol.md` §Gate locali (opzione worktree-gate).

---

## Script di supporto: tools/release/worktree_gate.py

Per invocazioni programmatiche (CI locale, pytest) e' disponibile lo script Python
`tools/release/worktree_gate.py` (stdlib, nessuna dipendenza esterna).

Interfaccia CLI:
```bash
python3 tools/release/worktree_gate.py \
  --repo <path_assoluto_repo> \
  --sha <sha_commit> \
  --cmd "npm run lint" \
  --cmd "npm test" \
  [--node-modules-symlink <path>] \
  [--workdir <subdir_nel_wt>]
```

Exit 0 = tutti i comandi PASS. Exit 1 = almeno un comando FAIL (con output).
