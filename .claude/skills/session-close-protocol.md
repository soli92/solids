# session-close-protocol — Protocollo canonico di fine sessione (EP-069 US-313)

> v1.0 EP-069 US-313 TSK-718 | PATTERN §16 (Sync) + §2 (Ruoli)
> Backport generalizzato da portale-servizi-factory: costanti verticali eliminate,
> VCS snapshot dinamico su code_paths[], session_id da tools/session/session_id.py.

Protocollo a 5 fasi invocato da `/session-close`. Raccoglie le informazioni salienti
della sessione, compone un documento markdown canonico e lo scrive in `raw/sessions/`
tramite `session-sync`. Append-only su `wiki/log.md`.

## Input

```yaml
context: "<stringa opzionale — descrizione della sessione, max 120 car.>"
factory_root: "<path assoluto della factory>"
dry_run: false   # se true: mostra payload senza scrivere né aggiornare manifest
skip_dirty_check: false
outcome: ~       # opzionale: completed|partial|aborted; assente → euristica auto
```

## Tabella dei gate

Elenco chiuso dei gate di `/session-close`. Il nome e' stabile (`STOP-*` blocca la chiusura, `ADV-*` avvisa
e prosegue). La colonna «Dove» indica la sezione di questo file in cui il gate e' scritto (per titolo, non
per numero di riga). Ogni gate ha un campo nella busta di `tools/session/close_collect.py`
(`sources.<campo>`, colonna «Campo busta»); `STOP-SCHEMA` e `STOP-SYNC-ERROR` sono di Fase 2/3 e nella
busta compaiono come `deferred`.

| Nome | Tipo | Condizione | Dove | Campo busta |
|---|---|---|---|---|
| `STOP-CONFIG` | STOP | `session_close.enabled` falso o assente in `factory.config.yaml` | Fase 0 passo 1 | `config` |
| `STOP-DIRTY` | STOP | `git status --porcelain wiki/ management/` non vuoto e `skip_dirty_check == false` | Fase 0-bis A | `dirty` |
| `STOP-LOCK` | STOP | `LOCK_DIR` esistente con TTL non scaduto, o `mkdir` in race (Fase 0-ter Passo A/B) | Fase 0-ter Passo A/B | `lock` |
| `STOP-SCHEMA` | STOP | Gate schema Fase 2→3 non superato (payload invalido, `error:payload_incomplete`) | Fase 2, Vincoli | `schema` |
| `STOP-SYNC-ERROR` | STOP | `session-sync` restituisce `status: error` o `error:integrity_check_failed` | Fase 3 | `sync_error` |
| `ADV-CLAIM` | advisory | `conflicts`/`claim` su `raw/sessions` (Fase 0-ter Passo C): un conflitto esce 0, si riporta in chat | Fase 0-ter Passo C | `conflicts` |
| `ADV-REPO-ALIGN` | advisory | Fase 1-bis: qualunque errore, «MAI STOP» | Fase 1-bis | `repo_align` |
| `ADV-AI-POLICY` | advisory | Fase 1-ter: qualunque errore, «MAI STOP» | Fase 1-ter | `ai_policy` |
| `ADV-COST-ALERT` | advisory | Fase 1h: fail-open, errore → nota | Fase 1 voce 1h | `cost_alert` |

## Fasi

---

### Fase 0 — Gate e init

0. **Busta di raccolta (sola lettura, una sola chiamata Bash)** — prima di ogni altro comando di raccolta:
   ```bash
   python3 tools/session/close_collect.py [--skip-dirty-check]
   ```
   Stampa su stdout una busta JSON (≤32 KiB) con una fonte per gate, ciascuna con `status`, `severity`
   (`stop`/`advisory`/`info`), `gate` (nome della tabella dei gate), `source` (ancora della sezione sorgente) e
   `data`. La busta non decide: soglie e testi di STOP restano in questo file e nelle foglie.
   - **Exit non-zero** (`complete:false`): fermati, riporta in chat lo stderr e le fonti con `status`
     `error`/`timeout`, non proseguire con i singoli Bash di raccolta. Exit 2 = argomenti non validi.
   - **`attention` non vuoto** (conflitti su `raw/sessions`, advisory): riportalo in chat e prosegui.
   - **Con busta completa** usala al posto dei Bash singoli di: passo 1 (`config`), passo 2 e 4 (`session`),
     Fase 0-bis §A (`dirty`), Fase 0-ter Passo C `conflicts` (`conflicts`), Fase 1-bis (`repo_align`),
     Fase 1-ter (`ai_policy`), Fase 1h `cost_alert check` (`cost_alert`). `status` `fail` su una fonte `stop`
     applica il testo di STOP del gate; `skipped` = gate di config spento; `deferred` = gate di Fase 2/3,
     da valutare piu' avanti; per le fonti advisory in `error` usa il messaggio «non disponibile» della Fase
     corrispondente e prosegui.
   - **Restano comandi con scrittura, fuori dalla busta**: `close_lock.py acquire`/`release`,
     `active_sessions.py gc`/`claim`/`release`, `harvest-session-tokens.py`. La busta e' un'istantanea
     precedente al lock: lo stato di `lock` e' informativo, il gate resta l'`acquire` del Passo A.

1. Leggi `factory.config.yaml`:
   - `session_close.enabled` deve essere `true`. Se `false` o assente → STOP
     (il command `/session-close` ha già verificato, ma la skill ri-verifica
     per sicurezza in caso di invocazione diretta).
   - Estrai `project.pattern_version`, `project.name`, `vcs.factory_repo` (o usa
     il path corrente come factory_root).

2. Genera identificatori:
   ```bash
   SESSION_DATE=$(date -u +%Y-%m-%d-%H)
   # Usa il resolver canonico (US-308 EP-069):
   SESSION_UUID=$(python3 tools/session/session_id.py --short)
   SESSION_LABEL="session-${SESSION_DATE}-${SESSION_UUID}"
   CLOSED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   ```

3. `opened_at` approssimato: `now - 1h` (se non disponibile da Fase 0-bis §B).

4. Determina `operator`: `git -C <factory_root> config user.name` | `"unknown"`

---

### Fase 0-bis — Dirty-wd check + active-sessions.yaml

> Eseguire SUBITO DOPO Fase 0 e PRIMA di Fase 0-ter.

#### A. Dirty working directory check [STOP su fail]

```bash
git -C <factory_root> status --porcelain wiki/ management/
# Aggiunge i code_paths[] con vcs.mode != none e path != "." (se applicabile)
```

SE non-vuoto E `skip_dirty_check == false`:
```
STOP — "[session-close] Dirty working directory rilevato.
        Artefatti con modifiche non committate: <lista file>.
        Commita o stasha prima di chiudere la sessione, poi ri-esegui /session-close.
        Bypass: --skip-dirty-check (non raccomandato)."
```

#### B. Lettura opened_at — dual-read [TRIGGER VINCOLANTE]

Leggi obbligatoriamente `.claude/skills/references/session-close-protocol/fase-0bis-detail.md`
prima di eseguire §B; se il file manca → STOP e segnala.

Fonte primaria: `memory/active-sessions.yaml` lookup per `session_id` (dal resolver).
Graceful se non trovato: `opened_at` approssimato.

#### C. Verifica coerenza claim

Dopo §B, se entry trovata in `active-sessions.yaml`: verifica campi `agent` e `started_at`.
Se assenti: warning non bloccante in chat. La rimozione claim avviene in Fase 0-ter Passo D.

#### D. Cleanup session-open.yaml [DEPRECATED — FINALLY block]

Se esiste `memory/session-open.yaml`: rimuovi slot solo se attribuibile con certezza.
Pseudocodice: `.claude/skills/references/session-close-protocol/fase-0bis-detail.md` §D.

---

### Fase 0-ter — mutex mkdir-lock

> Eseguire DOPO Fase 0-bis e PRIMA di Fase 1.
> Protegge il preflight di cooperative locking (EP-053) da race condition.

- **LOCK_DIR**: `<factory_root>/.session-close.lock/`
- **Passo A**: `python3 tools/session/close_lock.py acquire --session-label "<SESSION_LABEL>" --operator "<operator>" --json`. Se `LOCK_DIR` esiste con TTL scaduto (> 10 min) il comando lo rimuove (GC, messaggio su stderr) e procede; se e' vivo esce 1 → STOP-LOCK.
- **Passo B**: `os.mkdir` atomico dentro lo stesso comando. Fallisce (race) → exit 1 → STOP-LOCK. Riesce → scrive `lock.json` con `{locked_at, operator, session_label}`. Exit 2 = errore di I/O: STOP, non e' un lock vivo.
- **Passo C**: Preflight di cooperative locking (EP-053), con la CLI di `active_sessions.py` (mai a mano, mai `yaml.dump`; le rimozioni del GC si riportano in chat). `<SESSION_ID8>` = `SESSION_UUID` (8 caratteri hex). Advisory: un conflitto esce 0 (avvisa in chat e prosegui). `conflicts` e' gia' nella busta della Fase 0: non rilanciarlo; `gc` e `claim` restano. Dettaglio: `.claude/skills/references/session-close-protocol/fase-0ter-detail.md`.
  ```bash
  python3 tools/session/active_sessions.py gc
  python3 tools/session/active_sessions.py conflicts --domain raw/sessions --uuid <SESSION_ID8>
  python3 tools/session/active_sessions.py claim --agent session-sync --domain raw/sessions --uuid <SESSION_ID8> --ttl 15 --context "session-close"
  ```
  Conserva `SESSION_CLAIM_ID = <SESSION_ID8>`.
- **Passo D** [FINALLY]: `python3 tools/session/close_lock.py release` (idempotente; rimuove `LOCK_DIR` con `lock.json`). Rimuovi claim per `SESSION_CLAIM_ID AND domain=raw/sessions`, poi il claim di sessione di `/session-start` (`domain=session`, `kind: session`, US-316) — MAI per operator/posizione. CLI: `python3 tools/session/active_sessions.py release --domain raw/sessions --uuid <SESSION_CLAIM_ID>`, poi `python3 tools/session/active_sessions.py release --domain session --kind session --uuid <SESSION_CLAIM_ID>`.

---

### Fase 1-bis — Repo align check (best-effort advisory, opt-in)

**Gate**: `repo_align.enabled: true` AND `repo_align.triggers.on_session_close: true`.
Se gate falso → skip silenzioso.

Qualunque errore → `[repo-align] Verifica non disponibile: <motivo>. Procedo con session-close.` e PROSEGUI (MAI STOP).

---

### Fase 1-ter — §ai_policy check (best-effort advisory, opt-in)

**Gate**: `ai_policy_check.enabled: true` AND `ai_policy_check.triggers.on_session_close: true`.
Se gate falso → skip silenzioso.

Qualunque errore → `[ai-policy] non disponibile: <motivo>. Procedo con session-close.` e PROSEGUI (MAI STOP).

---

### Fase 1 — Raccolta fonti

Consulta in parallelo dove possibile. Tutte le fonti opzionali (degrado graceful):

- **1a** `git -C <factory_root> log --oneline --since="<OGGI> 00:00"` — max 30 righe.
- **1b** Per ogni entry in `factory.config.yaml#code_paths[]` con `vcs.mode != none` e path diverso da factory_root:
  `git -C <path> log --oneline --since="<OGGI> 00:00" 2>/dev/null || echo "n/a"`
  (degrado graceful se il path non esiste o non è un repo git)
- **1c** VCS snapshot: HEAD factory + HEAD di ogni code_path (chiavi dinamiche da code_paths[]).
  Comandi: `.claude/skills/references/session-close-protocol/fase-2-detail.md` §VCS Snapshot
- **1d** `wiki/log.md` — entry con `date:` = oggi (max 20).
- **1e** `wiki/gaps.md` — gap aperti o chiusi oggi → `gap_aperti` + `gap_chiusi`.
- **1f** `memory/active-sessions.yaml` — claim aperti o sessioni attive.
- **1h** Costi in token (skill `cost-alert-protocol`, fail-open: errore → nota, mai STOP):
  ```bash
  # 1. registra la sessione nell'event store: in VS Code gli hook SessionEnd non girano
  python3 <factory_root>/tools/analytics/harvest-session-tokens.py <transcript della sessione>
  # 2. verdetto su sessione, giorno e settimana (gia' nella busta della Fase 0, fonte `cost_alert`: rilancialo solo dopo l'harvest se serve il dato aggiornato)
  python3 <factory_root>/tools/analytics/cost_alert.py check --period all --json
  ```
  Il transcript è `~/.claude/projects/<cwd>/<SESSION_ID>.jsonl` (i subagenti li raccoglie
  l'harvest). Dal verdetto: `token_cost.cost_usd` = costo della regola `session` (o
  `breakdown --period session` se non c'è regola di sessione); `token_cost.alert` = righe
  superate + note. Se `escalations` non è vuoto → skill §Step 3 (agente `cost-alert` se
  `agent_enabled`), poi riporta il path del record nel report.
- **1g** Opzionali (non bloccare se assenti):
  - `management/kanban/` — `git diff --name-only HEAD~5 HEAD -- management/kanban/` per task avanzati.

---

### Fase 2 — Composizione payload

Costruisci il payload strutturato dai dati di Fase 1.
Template completo: `.claude/skills/references/session-close-protocol/fase-2-detail.md` §Payload

**Risoluzione `outcome`**: input `--outcome` (manual) → euristica auto se assente.
Dettaglio cascata: foglia sopra §Risoluzione outcome.

**Gate schema Fase 2→3**: `context` ≥ 20 char; `outcome` ∈ enum; `session_label` match regex.
Fail → STOP + rilascia lock. Dettaglio: foglia sopra §Gate schema.

SE `--dry-run`: mostra payload in chat, termina qui, rilascia lock.

---

### Fase 3 — Scrittura (via session-sync)

Invoca `session-sync` con il payload di Fase 2. Esegue (in ordine):
1. Dedup doppio (manifest + filesystem)
2. Secret scan pre-write
3. Serializzazione + scrittura file
4. Verifica post-write integrità
5. Aggiornamento manifest

Restituisce `{ status, path, session_label }`.

Se `session-sync` restituisce `status: error` o `status: error:integrity_check_failed`:
```
STOP — "session-close-protocol Fase 3 FAIL: session-sync ha restituito errore.
Path atteso: raw/sessions/<SESSION_LABEL>.md
Controlla raw/.extraction-manifest.json per dettagli."
```

In ogni caso (successo o errore): **rilascia lock** (Fase 0-ter Passo D).

---

### Fase 4 — Log entry

Appendi in `wiki/log.md` (R.5 append-only):

```markdown
---
date: <YYYY-MM-DD>
type: session-close
session_label: <SESSION_LABEL>
operator: <operator>
outcome: <outcome>
artifact: raw/sessions/<SESSION_LABEL>.md
context: <context>
---
```

---

### Fase 5 — Return al chiamante

```yaml
status: success | error
session_label: <SESSION_LABEL>
path: raw/sessions/<SESSION_LABEL>.md
log_entry: appended
sources_used:
  - git-factory
  - git-code_paths       # per ogni code_path consultato
  - wiki/log.md
  - wiki/gaps.md
  - memory/active-sessions.yaml  # se disponibile
  - analytics/events/            # se disponibile
```

---

## Vincoli

- **R.1** La skill non scrive in `raw/`. SEMPRE delega a `session-sync` (boundary inviolabile).
- **R.2** Mai inventare decisioni, artefatti o insight non verificabili dalle fonti.
- **R.5** `wiki/log.md` append-only.
- **Lock** acquisito PRIMA del preflight di cooperative locking (EP-053), rilasciato in OGNI path. TTL 10 min.
- **Dirty-wd** STOP su artefatti L2 uncommitted. Bypass: `--skip-dirty-check`.
- **Gate schema Fase 2→3** payload invalido → STOP `error:payload_incomplete` + rilascia lock.
- **`--dry-run`** lock acquisito e rilasciato; nessuna scrittura.
- **Fonti opzionali** se assenti → procedi con dati disponibili; segnala `_non disponibile_`.
- **Mai secret** nel documento: git log con token → `[redatto]`.
- **Budget compute** nessun git clone, nessuna scansione ricorsiva. Latenza Fase 1 < 10s.
- **Session ID**: SEMPRE da `tools/session/session_id.py` (US-308 EP-069); mai generare UUID ad-hoc.
- **VCS snapshot**: chiavi dinamiche da `factory.config.yaml#code_paths[]`; mai costanti verticali.

## Cross-link

- `.claude/commands/session-close.md` | `.claude/agents/session-sync.md`
- `factory.config.yaml` blocco `session_close:` | `wiki/sessions/index.md`
- `tools/session/session_id.py` — resolver canonico session_id (US-308 EP-069)
- `tools/session/session_doc.py` — helper dedup/secret-scan/manifest (US-313 EP-069)
- PATTERN §7 (R.1/R.2/R.5) | PATTERN §16 (Sync agent)
- EP-053 cooperative locking (`dispatch-policy` §0)
