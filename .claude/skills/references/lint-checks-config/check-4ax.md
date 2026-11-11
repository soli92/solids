# Check 4ax — `ignore = dirty` sui submodule (dettaglio)

Ambito: dettaglio del Check 4ax in `lint-checks-config.md`. Leggere prima di eseguire.

---

**Cosa verifica**: che ogni sezione `[submodule "…"]` di `.gitmodules` dichiari
`ignore = dirty` (accettato anche `all`).

**Perche'**: senza `ignore`, ogni `git status` sul padre apre un processo `git status`
dentro **ciascun** submodule per sapere se il suo worktree ha modifiche. Su una derivata con
63 submodule (misure del 2026-09-25): 12-17 s su Windows con antivirus in real-time, ~6 s su
macOS. Quel comando lo lanciano Claude Code all'apertura di ogni chat, gli agenti nelle
verifiche e VS Code a ogni refresh. Con `ignore = dirty` i processi figli sono 0.

**Cosa resta visibile**: lo spostamento del puntatore (` M <path>`). Sparisce solo il
contenuto non committato dei worktree, che si legge con `git -C <submodule> status` o, sul
padre, con `git status --ignore-submodules=none` (lo usa `tools/vcs/sm_doctor.py`).

**Implementazione**: legge `.gitmodules` come testo, senza lanciare git. Exit 0 anche con
finding (non blocca `run-deterministic.py`), exit 1 con `--strict`.

**Heal**: `git config -f .gitmodules submodule.<nome>.ignore dirty`. Va aggiunto anche quando
si registra un nuovo submodule (`bootstrap-vcs-protocol` stampa il comando).

### Output

```
## WARNING (prestazioni, heal-eligible)
- [WARNING][submodule-ignore-missing][4ax] .gitmodules: submodule "<path>" con nessun `ignore`: ogni `git status` sul padre apre un processo dentro questo submodule. Heal: git config -f .gitmodules submodule.<path>.ignore dirty
```

### Cross-link

4ax → `tools/lint/check-submodule-ignore.py` (implementazione) +
`tools/tests/test_check_submodule_ignore.py` (regressione) +
`.claude/skills/shell-portability.md` §Prestazioni (regole d'uso di `git status`).
