# tools/ — Guida cross-platform (Windows / macOS / Linux)

Dalla migrazione **EP-068 US-301**, la logica canonica degli script
`tools/temporal/` e `tools/vcs/sm_commit.py` e' in **Python 3.9+** e gira
**nativamente** su macOS, Linux e **Windows (cmd.exe, PowerShell, Git Bash)** —
senza dipendere da un ambiente bash.

I file `.sh` con lo stesso nome restano come **thin shim retro-compatibili**
che delegano al `.py` corrispondente. Servono per i riferimenti storici
(kanban, skill, ADR) e richiedono comunque bash (Git Bash / WSL su Windows).

---

## Prerequisito unico: Python 3.9+

Nessun'altra dipendenza: tutti gli script usano solo la **standard library**
(nessun `pip install`).

- **macOS / Linux**: `python3` e' quasi sempre presente.
  Verifica: `python3 --version`.
- **Windows**: installa Python gestito da uv o da [python.org](https://www.python.org/downloads/),
  non dall'alias del Microsoft Store: su una postazione misurata costa 716 ms netti per avvio
  contro 229 ms di Python gestito da uv. Verifica con `python --version` (oppure `py --version`)
  e con `where python`: un percorso sotto `WindowsApps` e' l'alias dello Store.

---

## Script coperti

| Script Python | Shim bash | Funzione |
|---|---|---|
| `tools/temporal/utc-now.py` | `tools/temporal/utc-now.sh` | Timestamp UTC ISO-8601 (ADR-030 §A) |
| `tools/temporal/build-temporal-context.py` | `tools/temporal/build-temporal-context.sh` | Temporal Context Injection (PATTERN §3, ADR-030 §A §E, ADR-031 §B) |
| `tools/temporal/rebuild-state-from-events.py` | `tools/temporal/rebuild-state-from-events.sh` | Rebuild state machine da eventi JSONL (ADR-028 §B.2) |
| `tools/vcs/sm_commit.py` | `tools/vcs/sm-commit.sh` | Commit senza attribution AI e senza ID factory interni (ADR-074, PATTERN §23.9) |

---

## Come invocare gli script

### Windows nativo (PowerShell o cmd) — raccomandato

```powershell
# Timestamp UTC
python tools\temporal\utc-now.py
python tools\temporal\utc-now.py --precision milliseconds

# Temporal Context Injection
python tools\temporal\build-temporal-context.py --task-started-at 2026-09-25T10:00:00Z --session-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Rebuild state machine
python tools\temporal\rebuild-state-from-events.py --task-id TSK-701

# Commit senza attribution AI
python tools\vcs\sm_commit.py "fix: correzione"
python tools\vcs\sm_commit.py "fix: correzione" --dry-run
python tools\vcs\sm_commit.py "fix: correzione" --yes
```

> Se `python` non e' nel PATH prova `py tools\temporal\utc-now.py`.

### macOS / Linux

```bash
python3 tools/temporal/utc-now.py
python3 tools/temporal/build-temporal-context.py --task-started-at 2026-09-25T10:00:00Z --session-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
python3 tools/temporal/rebuild-state-from-events.py --task-id TSK-701
python3 tools/vcs/sm_commit.py "fix: correzione"

# oppure tramite gli shim retro-compatibili (richiedono bash):
bash tools/temporal/utc-now.sh
bash tools/temporal/build-temporal-context.sh --task-started-at 2026-09-25T10:00:00Z --session-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
bash tools/temporal/rebuild-state-from-events.sh --task-id TSK-701
bash tools/vcs/sm-commit.sh "fix: correzione"
```

### Windows con Git Bash / WSL

Funzionano sia l'invocazione diretta Python (`python3 tools/temporal/utc-now.py`)
sia gli shim `.sh` (`bash tools/temporal/utc-now.sh`).
In WSL il disco C: e' montato in `/mnt/c/`.

---

## Dettaglio per script

### `tools/temporal/utc-now.py`

Genera un timestamp UTC ISO-8601 (ADR-030 §A, formato `YYYY-MM-DDTHH:MM:SSZ`).

```
utc-now.py [--precision=seconds|milliseconds]
```

- Default: secondi.
- `--precision milliseconds` → formato `YYYY-MM-DDTHH:MM:SS.sssZ`.

### `tools/temporal/build-temporal-context.py`

Emette il blocco YAML `TEMPORAL CONTEXT` per il system prompt degli agenti
(PATTERN §3, ADR-030 §A §E, ADR-031 §B). No-op silenzioso (exit 0) se
`temporal.context_injection.enabled` e' `false` in `factory.config.yaml`.

```
build-temporal-context.py --task-started-at <UTC-ts> --session-id <uuid4> [--config <path>]
```

Argomenti obbligatori quando il flag e' attivo:

| Argomento | Formato | Esempio |
|---|---|---|
| `--task-started-at` | `YYYY-MM-DDTHH:MM:SS[.sss]Z` | `2026-09-25T10:00:00Z` |
| `--session-id` | UUID v4 | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |

### `tools/temporal/rebuild-state-from-events.py`

Ricostruisce il file di stato `management/state/<TSK-id>.json` dai file JSONL
in `analytics/events/` (ADR-028 §B.2, idempotente). Richiede `factory.config.yaml`
con `state_machine.source: events` e `analytics.measurement.enabled: true`.

```
rebuild-state-from-events.py --task-id <TSK-id> [--events-dir <path>] [--output-dir <path>] [--config <path>]
```

### `tools/vcs/sm_commit.py`

Esegue `git commit` rimuovendo automaticamente attribution AI e ID factory
interni dal messaggio (PATTERN §23.9, ADR-074). Usato nelle factory con
`ai_attribution_policy.suppress_ai_traces: true`.

```
sm_commit.py "messaggio commit" [path]
sm_commit.py --message "messaggio" --path /repo [--dry-run] [--yes]
```

**Importante per invocazione da script non interattivi**: quando i filtri
alterano il messaggio (perche' contiene una traccia AI o un ID factory), lo
script mostra il messaggio risultante e attende conferma. Se non c'e' un
terminale (sessione non interattiva, CI, sub-processo) **e `--yes` non e'
presente, il commit viene rifiutato** con exit 1 e un messaggio esplicito.
Chi invoca `sm_commit.py` da script deve quindi:

- passare `--yes` se accetta il messaggio filtrato senza conferma interattiva, oppure
- riscrivere il messaggio di commit eliminando manualmente le tracce prima di passarlo.

Il flag `--dry-run` mostra messaggio originale e messaggio filtrato senza
committare nulla: utile per diagnostica preventiva.

---

## Gli shim `.sh` richiedono bash

I file `.sh` (`utc-now.sh`, `build-temporal-context.sh`,
`rebuild-state-from-events.sh`, `sm-commit.sh`) sono thin shim che delegano
al corrispondente `.py` tramite `exec python3 "$SCRIPT_DIR/<nome>.py" "$@"`.

**Richiedono bash** per essere eseguiti direttamente. Su Windows nativo
(cmd.exe / PowerShell) non funzionano: usare direttamente il `.py`.
Su Git Bash / WSL funzionano come su Linux.

I riferimenti storici in kanban, skill e ADR che citano il percorso `.sh`
continuano a funzionare invariati su tutti gli ambienti bash.
