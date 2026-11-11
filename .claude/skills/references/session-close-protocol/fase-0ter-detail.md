# session-close-protocol — Fase 0-ter: mutex mkdir-lock dettaglio

Ambito: implementazione del mutex mkdir-lock e del preflight di cooperative locking (EP-053).
Lettura utile in esecuzione per i Passi B-C; il core è `.claude/skills/session-close-protocol.md`.

```bash
LOCK_DIR="<factory_root>/.session-close.lock"
LOCK_FILE="<factory_root>/.session-close.lock/lock.json"
TTL_MINUTES=10
```

Il mutex è in codice: `tools/session/close_lock.py` (sottocomandi `acquire`, `release`, `status`;
`--json` per il risultato su stdout, diagnostica su stderr; `--root` default CWD). `LOCK_DIR` e
`TTL_MINUTES` sopra sono le costanti del tool. Exit: 0 riuscito, 1 lock vivo o race (STOP-LOCK),
2 errore di I/O.

## Passo A — Check esistenza lock

Lo esegue `acquire`: SE `LOCK_DIR` esiste legge `locked_at` da `lock.json` (se manca o è illeggibile,
l'età è quella dell'mtime di `LOCK_DIR`).
- `(now - locked_at) > TTL_MINUTES` → il comando scrive su stderr
  `[session-close] Lock orphan rilevato (TTL scaduto: <locked_at>). GC automatico: rimosso <LOCK_DIR>.`,
  rimuove `LOCK_DIR` e prosegue al Passo B.
- altrimenti esce 1 (STOP-LOCK):
  ```
  STOP — "[session-close] Operazione già in corso
          (session_id: <lock.session_label>, avviata: <lock.locked_at>).
          Riprova tra qualche minuto o verifica che la sessione precedente
          sia completata."
  ```

SE `LOCK_DIR` **non esiste**: prosegue al Passo B.

## Passo B — Acquisizione lock (atomica)

```bash
python3 tools/session/close_lock.py acquire --session-label "<SESSION_LABEL>" --operator "<operator>" --json
```

Il comando esegue `os.mkdir(LOCK_DIR)`. SE fallisce (race condition) esce 1 (STOP-LOCK):
  ```
  STOP — "[session-close] Race condition rilevata: un altro agente ha acquisito
          il lock nell'intervallo di controllo. Riprova."
  ```

SE riesce: scrive `LOCK_FILE`:
```json
{ "locked_at": "<ISO8601-now>", "operator": "<operator>", "session_label": "<SESSION_LABEL>" }
```
Senza `--session-label` il tool deriva `session-<YYYY-MM-DD-HH>-<id8>` da `session_id.py`.
`status` (sola lettura) mostra lo stato del lock senza modificarlo. Exit 1 → STOP-LOCK; exit 2 → STOP
con la diagnostica di stderr (non è un lock vivo).

## Passo C — Preflight di cooperative locking (dopo l'acquisizione del lock)

GC TTL, clash-check e claim con la CLI (scrittura chirurgica: mai a mano, mai con `yaml.dump`,
che riscrive il file e perde i commenti dell'intestazione):
```bash
python3 tools/session/active_sessions.py gc
python3 tools/session/active_sessions.py conflicts --domain raw/sessions --uuid <SESSION_ID[:8]>
python3 tools/session/active_sessions.py claim --agent session-sync --domain raw/sessions \
  --uuid <SESSION_ID[:8]> --ttl 15 --context "session-close"
```
`conflicts` è advisory: un conflitto esce con codice 0 e la CLI lo elenca su stdout; riportalo in chat
e prosegui. Il claim non è `kind: session` (quello è di `/session-start`, dominio `session`).
`--ttl` è in minuti e deve stare sopra la durata massima attesa di una chiusura.
`--uuid`: prime 8 cifre hex del SESSION_ID (da `tools/session/session_id.py --short`). Se SESSION_ID
non è derivabile, genera un uuid-v4 e usane i primi 8 caratteri: è la chiave per il rilascio in Passo D.
Le entry rimosse dal GC si riportano in chat, non come commento nel registro.

Conserva `SESSION_CLAIM_ID = <id usato sopra>` (8 caratteri hex) per il Passo D.

## Passo D — Cleanup lock [FINALLY — ogni path di uscita]

```bash
python3 tools/session/close_lock.py release
```

Idempotente: se il lock è già rilasciato esce 0. Se esce non-zero: warning, il GC TTL del Passo A lo
risolverà alla chiusura successiva.

Rimuovi la claim con la CLI, per uuid e dominio (mai per operator o posizione):

```bash
python3 tools/session/active_sessions.py release --domain raw/sessions --uuid <SESSION_CLAIM_ID> \
  || echo "[session-close Passo D] WARNING: rilascio claim fallito, GC TTL risolverà."
python3 tools/session/active_sessions.py release --domain session --kind session --uuid <SESSION_CLAIM_ID>
```

Nessuna riga di commento di rilascio nel registro: contiene solo le claim vive.

> **`--dry-run`**: lock acquisito normalmente (protegge da interferenze), ma nessuna
> scrittura in `raw/`. Lock rilasciato al termine come di consueto.
