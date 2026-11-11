---
description: Genera un report markdown di fine sessione e lo scrive in raw/sessions/ via session-sync.
argument-hint: '[--context="<descrizione breve>"] [--dry-run] [--skip-dirty-check] [--outcome=<completed|partial|aborted>]'
---

# /session-close — Protocollo canonico di fine sessione

> v1.0 EP-069 (US-313 / TSK-718): backport generalizzato da portale-servizi-factory.
> Costanti verticali eliminate; VCS snapshot dinamico su code_paths[]; session_id da
> tools/session/session_id.py (US-308).

Argomenti utente: `$ARGUMENTS`

Genera un file `session-<YYYY-MM-DD-HH>-<uuid[:8]>.md` in `raw/sessions/` che raccoglie
le informazioni salienti della sessione corrente (decisioni, artefatti, task, gap, insight)
e lo rende ingeribile dalla pipeline wiki-keeper standard.

## Procedura

### Step 0 — Gate `session_close.enabled`

Leggi `factory.config.yaml` e controlla:

```
SE session_close.enabled == false (default):
  STOP — emetti in chat:
    "/session-close non abilitato.
     Aggiungi `session_close: { enabled: true }` in factory.config.yaml per attivarlo."
```

### Step 1 — Parse argomenti

Dall'input `$ARGUMENTS` estrai:

- `context` — valore del flag `--context="..."` (stringa opzionale, max 120 car.);
  se assente, usa stringa vuota (la skill tenterà di derivarlo dal sommario).
- `dry_run` — `true` se `--dry-run` presente; default `false`.
  In dry-run: mostra il payload composto in chat senza scrivere file né aggiornare
  il manifest. Il mutex viene comunque acquisito e rilasciato.
- `skip_dirty_check` — `true` se `--skip-dirty-check` presente; default `false`.
  Salta il dirty working directory check. Non raccomandato: usare solo se
  le modifiche uncommitted sono WIP intenzionale non correlato alla sessione.
- `outcome` — valore del flag `--outcome=<value>` (opzionale). Se presente,
  override manuale dell'esito auto-derivato. Deve essere `completed`, `partial` o
  `aborted`. La skill registra `outcome_source: manual` e traccia eventuali
  discrepanze con l'euristica. Se assente, l'esito è auto-derivato
  (`outcome_source: auto-derived`).

Validazioni:
- `--context` oltre 120 car.: tronca e segnala in chat.
- `--outcome` fuori da `{completed, partial, aborted}`: STOP `error:invalid_outcome`.
- Flag non riconosciuti: ignora con warning in chat.

### Step 1-bis — Nota mutex e dirty-wd (informativa)

Prima di invocare la skill, il command informa l'utente in chat (solo se ci sono
claim attive o WD sporco rilevabile):

> *[session-close] Controllo dirty-wd e mutex in corso…*

Nessuna azione da parte del command: la verifica effettiva è nella skill (Fasi 0-bis e 0-ter).

### Step 2 — Invocazione skill

Invoca la skill `session-close-protocol` passando:

```yaml
context: "<valore estratto>"
factory_root: "<percorso factory — dalla variabile di sessione o da factory.config.yaml#vcs.factory_repo>"
dry_run: <true|false>
skip_dirty_check: <true|false>
outcome: <completed|partial|aborted o ~ se assente>
```

La skill esegue le fasi canoniche:
0. Gate config + init identificatori (session_id da tools/session/session_id.py)
0-bis. Dirty-wd check + lettura active-sessions.yaml
0-ter. mutex mkdir-lock acquisition + preflight di cooperative locking (EP-053)
1. Raccolta fonti (git log factory + code_paths, wiki/log.md, wiki/gaps.md, active-sessions.yaml)
2. Composizione documento + gate schema validation
3. Scrittura in `raw/sessions/` via agente `session-sync` (con secret scan + integrity check)
4. Entry append-only in `wiki/log.md`
5. Return + rilascio lock

### Step 3 — Output finale

Dopo il completamento della skill, riporta in chat:

**Esito positivo**:

```
/session-close — completato
============================
Session label: session-<YYYY-MM-DD-HH>-<uuid[:8]>
File scritto:  raw/sessions/session-<YYYY-MM-DD-HH>-<uuid[:8]>.md
Log entry:     wiki/log.md (entry session-close aggiunta)
Fonti usate:   <lista fonti consultate>
Secret redatti: <N>
Prossimo step: /query "ingest raw/sessions/" oppure invoca wiki-keeper
               manualmente per aggiornare wiki/sessions/
```

**Esito dry-run** (nessuna scrittura):

```
/session-close — dry-run (nessuna scrittura)
=============================================
Session label: session-<YYYY-MM-DD-HH>-<uuid[:8]>
Payload che sarebbe scritto:
<payload markdown>
Fonti consultate: <lista>
Per scrivere davvero: /session-close --context="..."  (senza --dry-run)
```

**Esito STOP** (gate, dirty-wd, mutex o errore):

```
/session-close — STOP
======================
Step <N> — <motivo>
Azione richiesta: <descrizione>
```

## Vincoli

- **Solo invocazione esplicita**: nessun hook Stop lo invoca automaticamente.
  Il suggerimento soft può apparire in `dev-handoff` ma mai come auto-run.
- **Gate `session_close.enabled`** (Step 0): STOP esplicito se flag spento.
- **Dirty-wd check** (Fase 0-bis): STOP se wiki/, management/ e i code_paths dichiarati
  in factory.config.yaml hanno modifiche uncommitted. Bypass: `--skip-dirty-check`.
- **Mutex mkdir-lock** (Fase 0-ter): garantisce che al più un session-close sia in
  esecuzione alla volta. TTL 10 min; GC automatico degli orphan.
- **Scrittura in `raw/`** delegata all'agente `session-sync` (§7 r.1 — Sync agent
  exception). Il command non scrive direttamente file in `raw/`.
- **Append-only** su `wiki/log.md` (§7 r.5).
- **Gate schema** (Fase 2→3): payload con context <20 car. o outcome non valido → STOP.
- Il file prodotto è un artefatto L1 (`raw/`): read-only dopo la scrittura,
  fonte per wiki-keeper; non editabile da altri agenti.

## Esempi d'uso

```bash
# Chiusura sessione senza contesto aggiuntivo
/session-close

# Con descrizione contestuale
/session-close --context="Sessione sviluppo TSK-718 session-close backport"

# Anteprima payload senza scrivere (dry-run)
/session-close --dry-run --context="Verifica session-close generalizzato"

# Con modifiche WIP intenzionali uncommitted (non raccomandato)
/session-close --context="Sessione con WIP" --skip-dirty-check

# Override manuale dell'esito
/session-close --context="Investigazione configurazione, nessun commit" --outcome=completed

# Sessione interrotta a metà
/session-close --context="Migrazione dataset — sospesa" --outcome=partial
```

## Cross-link

- **Skill invocata**: `.claude/skills/session-close-protocol.md`
- **Agente Sync**: `.claude/agents/session-sync.md`
- **Output wiki**: `wiki/sessions/index.md`
- **Config gate**: `factory.config.yaml` blocco `session_close:`
- **PATTERN §16** — Sync agents e invariante raw/ read-only (§7 r.1)
- **Cooperative locking** — claim lifecycle; enforcement in `dispatch-policy` §0
- **Session ID**: `tools/session/session_id.py` (US-308, EP-069)
