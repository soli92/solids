# /vcs-status — Cursor adapter

Sintassi:
```
/vcs-status [target-name]
```

Equivalente Claude Code: `.claude/commands/vcs-status.md`.

## Comportamento

Snapshot **read-only** dello stato VCS di tutti i target (`code_paths` + submodule): branch
corrente vs atteso, detached HEAD, submodule non inizializzato, drift parent-ref vs
submodule-HEAD, + comando di remediation per ogni riga `ACTION`. Pensato per progetti con
repository sotto git submodule (problema dei due HEAD, PATTERN §15 §Branch Awareness Layer).

Invoca la skill `vcs-preflight-protocol` (5 step). **Read-only assoluto (R.B7)**: solo comandi
git di lettura, mai `checkout`/`commit`/`fetch`. Funziona anche a `branch_awareness.enabled:
false` (esecuzione esplicita = volontà esplicita). Non è un gate.

## Traduzione tool (Cursor)

- Lettura config/git state → Terminal embedded (`git -C <dir> status/branch/rev-parse/symbolic-ref`).
- Nessuna scrittura file (read-only).
