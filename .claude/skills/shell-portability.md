---
name: shell-portability
description: Regole per comandi di shell compatibili con Linux, macOS, WSL2 e Git Bash. Riferimento unico per agenti con il tool Bash; include il check sui nomi di file portabili su Windows.
---
# Portabilità dei comandi di shell

Questa è la **single source of truth** per i comandi di shell scritti da agenti e skill.
Gli agenti con il tool `Bash` la seguono; le skill non duplicano varianti per piattaforma.

## Baseline

| Ambiente | Stato | Note |
|---|---|---|
| Linux, WSL2 (repo in `~/`) | **raccomandato** | coincide con CI e container |
| macOS | supportato | utility BSD: vedi §Insidie BSD |
| Git Bash su Windows | supportato, fragile | path misti, CRLF, utility parziali |
| PowerShell | **non supportato** | le skill non hanno varianti PowerShell |

## Regole

1. **Su Windows usa il tool `Bash` (Git Bash), mai il tool PowerShell** per comandi della
   factory o dei submodule: le skill sono scritte per bash.
2. **POSIX e flag comuni.** Usa solo opzioni che esistono sia in GNU sia in BSD. Se un
   comando richiede un'estensione GNU, riscrivilo o passa a Python.
3. **Parsing non banale → Python** (`python3`, fallback `python`/`py`), non catene lunghe
   di `awk`/`sed`/`cut`. Vale per JSON (`python3 -c 'import json…'` o `jq` se presente),
   date e calcoli.
4. **Path**: sempre con `/`, relativi alla root factory o assoluti POSIX. Mai `C:\`, mai
   `~` dentro le virgolette. Quota sempre le variabili (`"$path"`): `design_&_architecture/`
   contiene `&`.
5. **Fine riga LF.** Script `.sh` e heredoc con LF; se uno script fallisce con
   `$'\r': command not found`, la causa è CRLF (`git config core.autocrlf input`).
6. **Errori espliciti**: `2>/dev/null` solo dove il fallimento è atteso e gestito
   (`|| echo …`), mai per nascondere errori reali.
7. **Niente comandi interattivi** (`git rebase -i`, `git add -i`, editor, `read`).

## Nomi di file portabili su Windows

I nomi di file illegali su Windows (`< > : " | ? *`, riservati DOS, punto o spazio finali)
rendono impossibile il `git clone` per i collaboratori che lavorano su Windows.

Check eseguibile:

```bash
python3 tools/lint/check-portable-paths.py
```

Exit 0 = OK; exit 1 = almeno una violazione con dettaglio. Usare `--json` per output
machine-readable. Il check opera su `git ls-files` (file committati, non il working tree).

## Insidie BSD (macOS)

| Evita (GNU-only) | Usa |
|---|---|
| `sed -i 's/a/b/' f` | `sed -i.bak 's/a/b/' f && rm f.bak`, oppure Edit/Python |
| `date -d '…'`, `date --iso-8601` | `date -u +"%Y-%m-%dT%H:%M:%SZ"`; per aritmetica sulle date, Python |
| `grep -P` | `grep -E`, oppure Python `re` |
| `readlink -f` | `cd "$(dirname "$p")" && pwd -P`, oppure `python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$p"` |
| `stat -c` | `python3 -c 'import os,sys;print(os.stat(sys.argv[1]).st_mtime)' "$f"` |
| `xargs -r` | `xargs` con input garantito non vuoto, oppure un loop `while read` |
| `sort -V` | Python (`packaging.version`) o confronto semver esplicito |
| `find -printf` | `find … -exec stat …` o Python `os.walk` |
| `timeout N cmd` | `curl --max-time N`, `git -c http.lowSpeedTime=N`, oppure Python |

## Prestazioni

Su Windows con antivirus in real-time ogni processo costa **300-550 ms** prima di fare
qualunque lavoro (Linux/macOS: 1-3 ms). Il costo è per processo, non per byte: si paga la
chiamata, non la dimensione del file. Le regole valgono ovunque, ma su quelle macchine fanno
la differenza fra una sessione usabile e una bloccata (misure su una derivata, 2026-09-25).
Il costo c'è anche nei lanci nativi (non solo Git Bash); causa antivirus non provata. Su Windows
usa Python gestito da uv o python.org, non l'alias dello Store (716 vs 229 ms, misura 2026-10-12).

1. **`git status` sul padre è economico solo se non scende nei submodule.** `.gitmodules`
   dichiara `ignore = dirty` su ogni submodule (lint 4ax): il comando non apre processi figli
   e mostra comunque lo spostamento dei puntatori. `--ignore-submodules=none` solo se la
   domanda è proprio il contenuto non committato dei submodule; per uno solo,
   `git -C <submodule> status`. Per i soli file della factory: `git status --porcelain -- wiki/`.
2. **Un comando, una chiamata.** Comandi indipendenti in un'unica invocazione di `Bash` (o in
   uno script Python), non dieci chiamate da una riga.
3. **Niente attraversamenti dei repo di codice.** Su un albero di ~290k entry `find` costa
   16-54 s su Windows. L'elenco dei submodule è in `.gitmodules`; i file di un repo in
   `git -C <submodule> ls-files`; per cercare, Grep su un path ristretto.
4. **Mai `$(git submodule …)` in sostituzione di comando.** `git submodule` è uno script
   shell: annidato in `$(…)` su Git Bash con antivirus fallisce in modo deterministico
   (`open_setup failed, Win32 error 5`) e restituisce una stringa vuota senza errore.
   Redirigi su file e leggi il file, oppure usa Python.
5. **Registri mai letti per intero.** `memory/active-sessions.yaml`, `wiki/log.md`,
   `management/kanban/sprint.md`, `factory.config.yaml`: grep mirato, poi solo l'intervallo
   che serve.
6. **Deliverable scritti nella destinazione finale, a pezzi.** Mai assemblare un artefatto
   lungo nello scratchpad per spostarlo alla fine: lo scratchpad è volatile e fuori da git.
7. **PC poco potenti: meno sub-agenti in parallelo.** Si abbassa per macchina in
   `.claude/settings.local.json` (non versionato):
   `{"env": {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "4"}}`.

L'ambiente raccomandato su Windows resta WSL2 con il repo in `~/`: la creazione dei processi
è nativa Linux e non passa dall'emulazione MSYS di Git Bash. Installazione di WSL2, misura di
riferimento e diagnosi dell'antivirus da fare **prima** di chiedere qualcosa all'IT:
[`references/shell-portability/windows-wsl2-e-diagnosi-antivirus.md`](references/shell-portability/windows-wsl2-e-diagnosi-antivirus.md).
