---
name: session-start-protocol
description: Protocollo di apertura sessione (EP-069 US-316) — guard di idempotenza, ambiente da `environment:`, claim advisory in active-sessions.yaml, pull e selezione submodule, raw/ non ingestati, briefing (gap, sprint, sessione precedente). Modalita' manual / quick / auto. Invocato da /session-start.
---
# session-start-protocol — Apertura di sessione (EP-069 US-316)

> v1.0 EP-069 US-316 TSK-722 | simmetrico a `session-close-protocol` (US-313)
> Backport generalizzato da una factory derivata: nessun file di credenziali, token,
> branch o submodule cablato. Ambiente da `environment:` (US-315), base branch da
> `vcs`, submodule da `code_paths[]`, session_id da `tools/session/session_id.py`.

Sincronizza la factory, segnala i raw/ non ingestati, orienta la sessione con un
briefing leggibile in meno di un minuto. **Non arbitra**: le altre sessioni aperte
sono un avviso nel briefing, mai uno STOP (coerenza con EP-064: nessun lock, nessun
lease, nessun arbitro; la visibilita' e' al ciclo di scrittura dei claim, minuti).

## Input

```yaml
context: "<opzionale, max 120 car.>"
factory_root: "<root della factory — default CWD>"
mode: manual | quick | auto          # default manual
hook_seen: false                     # true se l'invocazione arriva dall'hook SessionStart
skip_init_check: false
show_init_check: false               # --init-check o session_start.init_check_on_start
```

## Modalita'

| Fase | `manual` | `--quick` | `--auto` |
|---|---|---|---|
| 0-ter guard di idempotenza | SKIP | attivo | attivo (no-op se `hook_seen`) |
| 0.2 ambiente | STOP se BLOCKED | STOP se BLOCKED | STOP se BLOCKED |
| 0.3 claim di altre sessioni | avviso | avviso | avviso |
| 1.1 working tree sporco | domanda [s/c/a] | avviso, continua | avviso, continua |
| 1.2 `git pull --ff-only` | eseguito | SKIP | SKIP |
| 1.3 divergenza dall'upstream | conferma sopra soglia | STOP sopra soglia | STOP sopra soglia |
| 1.4-1.5 submodule | selezione + doctor + update | SKIP | SKIP |
| 2 raw/ non ingestati | domanda [s/n/lista] | conteggio | conteggio |
| 3-4 briefing | + domanda di scope | `scope: all` | `scope: all` |
| 5 claim + log | eseguiti | eseguiti | solo se `auto_launch.log_writes: true` |

STOP ammessi in ogni modalita': ambiente BLOCKED (0.2), errore git o merge conflict
(Fase 1), divergenza oltre soglia in `quick`/`auto` (1.3). **Mai** per un claim.

## Fase 0-ter — Guard di idempotenza (solo `quick`/`auto`)

1. `SESSION_ID=$(python3 tools/session/session_id.py)` — una volta sola, valido per
   tutte le fasi; `CLAIM_ID` = primi 8 caratteri. Mai generare UUID ad-hoc.
2. Se `hook_seen: true` → no-op: l'hook ha gia' registrato l'id in
   `memory/auto-launch-seen.yaml`. Vai a Fase 0.
3. Altrimenti leggi `memory/auto-launch-seen.yaml` (formato e GC: docstring di
   `tools/session/auto_start_hook.py`). Id gia' presente (anche sul prefisso di 8)
   entro `auto_launch.idempotency_ttl_minutes` → banner e fine:
   `[session-start] Sessione gia' inizializzata — skip. /session-start senza flag per forzare.`
4. Se il resolver dichiara `source=generated`, la chat non e' riconoscibile: prosegui
   senza dedup e dillo nel briefing.

## Fase 0 — Gate e preflight

### 0.1 Gate
`session_start.enabled: true` in `factory.config.yaml`, altrimenti STOP. Estrai
`project.name`, `project.pattern_version`, `session_start.*`.

### 0.2 Ambiente e credenziali
Salta se `skip_init_check`. Altrimenti:
```bash
python3 tools/env/init_check.py --json      # locale, nessuna probe di rete
```
- `env_configured: false` → nota «environment non configurato», prosegui.
- `state: BLOCKED` → STOP: elenca le `label` dei check FAIL (file in `env_files`,
  variabili `required`, binari). **Mai** contenuto di file o valori di variabili.
- `PARTIAL` → nota nel briefing. Con `show_init_check` mostra la tabella completa.

### 0.3 Claim di altre sessioni (cooperative locking, EP-053)
```bash
python3 tools/session/active_sessions.py gc
python3 tools/session/active_sessions.py conflicts --domain session --json
```
`gc` rimuove le entry con `(last_seen|started_at) + ttl_min` passato. Ogni conflitto
(stesso dominio, o sessione aperta di un altro operatore) va in **ALTRE SESSIONI** nel
briefing. Nessuna domanda, nessuno STOP.

### 0.4 Avvio caldo o freddo
- **Caldo**: esiste gia' un claim `kind: session` con lo stesso `CLAIM_ID` (stessa chat,
  `/session-start` rilanciato) → salta 1.2 e 2.3, Fase 5 rinnova `last_seen`.
  Annuncia `[avvio caldo: sessione gia' aperta — percorso breve]`.
- **Freddo**: tutto il resto.

### 0.5 Operatore
`git -C <factory_root> config user.name`, altrimenti `unknown`.

## Fase 1 — VCS

Qualunque errore git → STOP prima dell'analisi. In `quick`/`auto` solo 1.1 e 1.3.
In `manual` leggi **prima** `.claude/skills/references/session-start-protocol/manual-interactive.md`
(prompt di 1.1, 1.2, 1.3, 1.4, 4.2, 4.3); se manca → STOP e segnalalo.

- **1.1** `git -C <factory_root> status --short`.
- **1.2** `git -C <factory_root> pull --ff-only` (solo `manual`, mai su avvio caldo).
- **1.3** Divergenza dall'upstream, senza fetch:
  `git -C <factory_root> rev-list --count HEAD..@{u}` (in `manual` dopo il pull:
  `ORIG_HEAD..HEAD`). Nessun upstream → `n/a`, avviso non bloccante. Soglia:
  `dispatch_gate_divergence_threshold` (default 50); avviso morbido sopra
  `session_start.vcs_soft_warning_threshold` se valorizzato.
- **1.4** Selezione submodule (solo `manual`): i candidati sono le entry di
  `code_paths[]` con `vcs.mode: submodule`; nessuna → `[nessun submodule in config]`,
  passa a Fase 2. I submodule con `archived = true` in `.gitmodules` sono mostrati
  senza numero, non sono selezionabili e non entrano nel sync (solo lettura).
  Mai allineare senza scelta esplicita; `nessuno` e' una risposta valida.
- **1.5** Sui soli selezionati (esclusi gli archiviati): `python3 tools/vcs/sm_doctor.py --target <name>`
  (exit != 0 non e' STOP), poi `git submodule update` come da foglia.

## Fase 2 — raw/ non ingestati

Sola lettura su `raw/` (§7 r.1), nessun auto-ingest. Confronta `raw/*.md` e
`raw/sessions/*.md` con `raw/.extraction-manifest.json`: algoritmo in
`.claude/skills/references/session-start-protocol/fase-2-detail.md`. Risultato:
`pending_ingest_count`. In `manual` con `> 0`: domanda [s/n/lista]; `s` invoca
`wiki-keeper` esplicitamente.

## Fase 3 — Stato della factory

Ogni fonte e' opzionale: se manca, `_non disponibile_`. Mai inventare gap, TSK o sessioni.

- **3a** Gap aperti: `python3 tools/wiki/gaps_open_view.py` rigenera `memory/gaps-open.md`
  (gitignorato); leggi CRITICAL/HIGH da li'. Tool assente o in errore → `wiki/gaps.md`.
- **3b** Sprint: `python3 tools/analytics/sprint-progress.py --json` se
  `analytics.sprint_progress.enabled`, altrimenti `management/kanban/sprint.md`
  (titolo, date, TSK `in-progress`/`blocked` con motivo).
- **3c** Branch factory + submodule: `python3 tools/vcs/sm_status.py` (read-only;
  base branch per target da `vcs.base_branch` della entry, default `main`).
  I submodule con `archived = true` in `.gitmodules` sono esclusi dal controllo
  di divergenza: `sm_status.py` li mostra con etichetta `[archiviato (read-only)]`
  ma non segnala drift del puntatore (il repo e' read-only, nessuna azione richiesta).
- **3d** Sessione precedente: il `.md` piu' recente in `raw/sessions/` (scritto da
  `/session-close`, US-313) → `session_label`, `context`, `outcome`. Fonte primaria.
- **3e** Fallback: ultime 10 entry di `wiki/log.md`.
- **3f** Costi in token (skill `cost-alert-protocol`, sola lettura, nessun agente):
  `python3 tools/analytics/cost_alert.py check --period daily` in `--auto`/`--quick`,
  `--period all` in manual. Righe, note e alert pendenti vanno nella riga COSTI del briefing.
  Capability spenta o errore: `_non disponibile_`, mai STOP.

## Fase 4 — Briefing

- **4.1** `context` presente → e' lo scope, nessuna domanda.
- **4.2-4.3** Solo `manual`: domanda di scope e di focus (foglia `manual-interactive.md`).

```
[SESSION-START — briefing]
Sessione: <CLAIM_ID>  |  <opened_at>  |  mode: <mode>  |  avvio: caldo|freddo
Scope:    <scope>
Branch:   <branch>  (<N> commit dietro l'upstream | n/a)
Ambiente: READY | PARTIAL (<label>) | non configurato

SPRINT CORRENTE      <titolo + date>
GAP APERTI (max 5)   <id  severity  titolo> | (nessun gap CRITICAL/HIGH aperto)
TSK IN CORSO (max 5) <TSK-id  titolo> | (nessuno)
TSK BLOCCATI         <TSK-id  titolo — motivo> | (nessuno)
RAW NON INGESTATI    <N>
SESSIONE PRECEDENTE  <label | context | esito> | (nessuna sessione precedente)
COSTI (3f)           <righe del verdetto cost_alert.py + note + alert pendenti> | (cost-alert spento)
ALTRE SESSIONI       <uuid  operator  domain  da started_at> | (nessuna dichiarata)
```

**ALTRE SESSIONI** e' informativa: «dichiarate nel file dei claim all'ultima scrittura»,
non «nessuno sta lavorando». Il briefing non dice mai che il conflitto e' impossibile.

## Fase 5 — Claim, log, return

In `auto` con `auto_launch.log_writes: false` (default) salta 5.1 e 5.2.

- **5.1** Claim di sessione (advisory; con `context` se presente):
  ```bash
  python3 tools/session/active_sessions.py claim --kind session --agent session-start \
    --domain session --ttl 120 --context "<context>"
  ```
  Su avvio caldo lo stesso comando rinnova `last_seen`. Lo rilascia `/session-close`.
- **5.2** Entry in coda a `wiki/log.md` (§7 r.5, append-only):
  ```markdown
  ---
  date: <YYYY-MM-DD>
  type: session-start
  session_id: <CLAIM_ID>
  operator: <operator>
  branch: <branch>
  synced_repos: [<nomi>]
  pending_ingest_count: <N>
  scope: <scope>
  ---
  ```
- **5.3** Return:
  ```yaml
  status: success | stop
  session_id: <CLAIM_ID>
  mode: <mode>
  start: warm | cold
  synced_repos: [...]
  pending_ingest_count: <N>
  other_sessions: <N>
  suggested_next: "/dev <TSK-id>" | "/run" | "/query"
  ```
  `suggested_next`: primo TSK in corso nello scope, altrimenti `/run`.

## Vincoli

- Domande all'utente solo in Fase 1.1, 1.4 e Fase 4, e solo in `manual`.
- `wiki/log.md` solo in Fase 5. `raw/` sola lettura.
- Nessun secret nel briefing: token e credenziali → `[redatto]`.
- Nessun `git push`, nessun clone, nessuna scansione profonda; Fase 1 < 15 s.
- Claim advisory: nessuna fase si ferma per un claim altrui.
