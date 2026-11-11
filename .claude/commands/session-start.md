---
description: Apre una sessione di lavoro — ambiente, claim advisory, pull e submodule scelti, raw/ non ingestati, briefing su gap, sprint e sessione precedente. Simmetrico di /session-close. Opt-in session_start.enabled.
argument-hint: '[--context="<descrizione breve>"] [--quick] [--auto] [--init-check] [--skip-init-check]'
version: "1.0"
since: "2026-10-05"
---

# /session-start — Apertura di sessione (EP-069 US-316)

Argomenti utente: `$ARGUMENTS`

Orienta la sessione con un briefing leggibile in meno di un minuto. Le fasi sono nella
skill `.claude/skills/session-start-protocol.md`; qui stanno flag, configurazione e hook.

**Cosa NON fa** — vincolante: non impedisce che due sessioni lavorino sulla stessa cosa,
non mette lock ne' lease, non arbitra. Le altre sessioni dichiarate in
`memory/active-sessions.yaml` compaiono nel briefing come **avviso**; la visibilita' e'
al ciclo di scrittura dei claim, quindi minuti (coerenza con EP-064).

## Procedura

1. **Gate**: `session_start.enabled` falso o assente → rispondi
   `"/session-start non abilitato: aggiungi session_start: {enabled: true} in factory.config.yaml."`
   e fermati. Nessun side effect.
2. **`--auto` e kill switch**: con `--auto` e `session_start.auto_launch.enabled` non
   `true` → `"[/session-start --auto] auto_launch.enabled: false — usa /session-start senza --auto."`
   e fermati.
3. **Parse**: `--context` (troncato a 120 car., segnalalo); `--auto` > `--quick` >
   `manual` (entrambi presenti: `--auto` vince, segnalalo); flag sconosciuti ignorati
   con avviso. `show_init_check` = `--init-check` oppure
   `session_start.init_check_on_start: true` (ma in `--auto` solo col flag esplicito).
4. **Skill**: invoca `session-start-protocol` con
   `{context, factory_root, mode, hook_seen, skip_init_check, show_init_check}`.
   `hook_seen: true` solo se il contesto iniettato dall'hook dice che l'id e' gia' registrato.
5. **Output**: il briefing della Fase 4, poi
   ```
   /session-start — completato
   Session ID: <uuid[:8]>  |  mode: <mode>  |  avvio: caldo|freddo
   Prossimo:   /dev <TSK-id> | /run | /query "<domanda>"
   ```
   oppure `/session-start — STOP  Fase <N> — <motivo>  Azione: <cosa fare>`.

## Flag

| Flag | Effetto |
|---|---|
| (nessuno) | `manual`: tutte le fasi, domande solo dove servono |
| `--quick` | niente pull, submodule e domande; claim e log scritti; ~5 s |
| `--auto` | come `--quick` + guard di idempotenza; claim e log solo con `auto_launch.log_writes: true`. Richiede `auto_launch.enabled: true` |
| `--context="..."` | scope della sessione, salta la domanda di scope |
| `--init-check` | mostra la tabella completa di `/init-check` |
| `--skip-init-check` | salta anche la verifica d'ambiente della Fase 0.2 |

## Configurazione (`factory.config.yaml`)

```yaml
session_start:
  enabled: false                 # master switch: false = comando inerte
  init_check_on_start: false     # tabella /init-check a ogni apertura (non in --auto)
  vcs_soft_warning_threshold: ~  # avviso morbido di divergenza; ~ = disattivo
  auto_launch:
    enabled: false               # kill switch dell'auto-apertura (hook + istruzione)
    idempotency_ttl_minutes: 1440  # validita' di un session_id nel seen file
    log_writes: false            # --auto scrive claim e log solo se true
    mode_default: auto           # auto | quick
```

Ambiente e credenziali vengono dal blocco `environment:` di `/init-check` (US-315): file,
variabili e binari si dichiarano li', e se ne verifica solo la presenza, mai il valore.
Soglia di divergenza: `dispatch_gate_divergence_threshold` (default 50). Base branch:
`vcs.base_branch` della entry di `code_paths[]`. Submodule: entry con `vcs.mode: submodule`.

## Auto-apertura

Due vettori, entrambi spenti finche' `auto_launch.enabled` non e' `true`:

- **Hook `SessionStart`** (CLI): `tools/session/auto_start_hook.py` — a flag spenti esce 0
  senza output; altrimenti inietta l'istruzione di eseguire `/session-start --<mode_default>`
  una volta per session_id (seen file `memory/auto-launch-seen.yaml`, gitignorato).
  Da aggiungere a mano in `.claude/settings.json`, sotto `hooks`:
  ```json
  "SessionStart": [{"hooks": [{"type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/session/auto_start_hook.py\" || true",
    "timeout": 10}]}]
  ```
- **Istruzione in CLAUDE.md** (per gli ambienti che non eseguono hook): una riga che chiede,
  a `auto_launch.enabled: true`, di eseguire `/session-start --auto` prima della prima
  risposta. E' probabilistica: se non scatta, nessun danno — `/session-start` resta manuale.

## Claim

```bash
python3 tools/session/active_sessions.py list            # chi ha dichiarato cosa
python3 tools/session/active_sessions.py gc --dry-run    # cosa e' scaduto
```

Schema e alias letti per compatibilita': header di `memory/active-sessions.yaml` e
docstring di `tools/session/claims.py`. Il claim `kind: session` scritto in Fase 5 lo
rilascia `/session-close`.

## Diagnostica

| Sintomo | Causa probabile |
|---|---|
| L'hook non inietta nulla | uno dei due flag non e' `true`; `source` resume/clear; id gia' nel seen file |
| `--auto` si ferma subito | `auto_launch.enabled: false` (kill switch) |
| STOP in Fase 0.2 | `/init-check` BLOCKED: guarda le label FAIL, `python3 tools/env/init_check.py` |
| «sessione gia' inizializzata» | stesso session_id entro `idempotency_ttl_minutes`: rilancia senza flag |

## Cross-link

`/session-close` · `/init-check` · `/sm-doctor` · `/kanban-status` · `/sprint-progress` · `/run`
