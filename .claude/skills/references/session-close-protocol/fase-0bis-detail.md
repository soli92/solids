# session-close-protocol — Fase 0-bis §B e §D: pseudocodice

Ambito: implementazione Python dettagliata del dual-read §B e del cleanup §D.
Lettura obbligatoria in esecuzione (trigger vincolante dal core — §B e §D).

## §B — Dual-read opened_at (ADR-084 Fase 2, session_id-primary)

```python
# Pseudocodice dual-read §B (session-close v1.0 EP-069 US-313)
# Session ID: usa resolve_session_id() da tools/session/session_id.py (US-308).
import subprocess, sys, os, yaml
from pathlib import Path

# Aggiunge il root della factory a sys.path se necessario
sys.path.insert(0, "<factory_root>")
from tools.session.session_id import resolve_session_id

ACTIVE_SESSIONS_PATH = "<factory_root>/memory/active-sessions.yaml"

opened_at_found    = None
session_uuid_found = None   # REGOLA DURA — vedi sotto
context_found      = None

SESSION_ID, _source = resolve_session_id()
# Operatore come lo scrive active_sessions.py nel campo `operator` (non `agent`, che e' il nome
# dell'agente): git config user.name.
operator = subprocess.run(["git", "config", "user.name"], capture_output=True,
                          text=True).stdout.strip() or None
SESSION_ID = SESSION_ID.lower() if SESSION_ID else None

# ── Passo 1: active-sessions.yaml (fonte primaria) ───────────────────────────
try:
    with open(ACTIVE_SESSIONS_PATH, 'r') as f:
        data = yaml.safe_load(f) or {}
    sessions_list = data.get('sessions', [])
    if not isinstance(sessions_list, list):
        sessions_list = []

    if SESSION_ID:
        # Lookup per [:8] — claim scritto con id=SESSION_ID[:8].
        # Preferisci l'entry `kind: session` (scritta da /session-start, US-316): il suo
        # started_at e' l'apertura della sessione, non l'inizio di un'operazione di agente.
        mine = [e for e in sessions_list
                if str(e.get('uuid', e.get('id', ''))).lower()[:8] == SESSION_ID[:8]]
        mine.sort(key=lambda e: e.get('kind') != 'session')
        for entry in mine[:1]:
            opened_at_found    = entry.get('started_at', entry.get('opened_at'))
            session_uuid_found = SESSION_ID[:8]
            context_found      = entry.get('context')
    else:
        operator_matches = [e for e in sessions_list
                            if operator and e.get('operator') == operator]
        # Come nel ramo per session_id: un'entry `kind: session` basta a decidere.
        sessioni = [e for e in operator_matches if e.get('kind') == 'session']
        if len(sessioni) == 1:
            operator_matches = sessioni
        if len(operator_matches) == 1:
            entry = operator_matches[0]
            opened_at_found = entry.get('started_at')
            context_found   = entry.get('context')
        elif len(operator_matches) > 1:
            ids_info = ", ".join(
                f"{e.get('uuid', e.get('id', '?'))} (started_at: {e.get('started_at', '?')})"
                for e in operator_matches
            )
            print(
                f"[session-close §B] WARNING: session_id non derivabile e "
                f"trovate {len(operator_matches)} entry per operator '{operator}' "
                f"in active-sessions.yaml: [{ids_info}]. "
                f"Impossibile scegliere con certezza. opened_at sarà approssimato."
            )

except FileNotFoundError:
    pass

# ── Passo 2: graceful ─────────────────────────────────────────────────────
if opened_at_found is None:
    print("[session-close §B] WARNING: opened_at non determinabile.")
    if SESSION_ID:
        print(f"  active-sessions.yaml: nessuna entry con id='{SESSION_ID[:8]}'.")
    else:
        print(
            f"  session_id non derivabile; ricerca per operator '{operator}' "
            f"non conclusiva (0 match o multiple entry)."
        )
    print("  opened_at sarà approssimato (now - 1h). Precisione ridotta per git log --since.")
```

**Nota**: il campo claim in `active-sessions.yaml` (schema EP-053) usa il campo `uuid`
(o `id` per compatibilità). Il session_id viene risolto via `resolve_session_id()` da
`tools/session/session_id.py` (US-308 EP-069): mai generato ad-hoc in questo punto.

**Regola dura:** `session_uuid_found` sostituisce `SESSION_UUID` SOLO se trovato per
`session_id` (Passo 1, ramo `if SESSION_ID`). Mai per match operator.
La sostituzione usa `session_uuid_found[:8]` (regex `[a-f0-9]{8}` del `session_label`
deve restare valida).

**Azioni post-lettura:**
- `opened_at_found` → usa come `opened_at` nel payload.
- `session_uuid_found` → sostituisce `SESSION_UUID` solo se non None; usa `[:8]`.
- `context_found` → fallback se `context` da input è vuoto.

## §D — Cleanup claim in active-sessions.yaml [FINALLY block]

La close rimuove il proprio claim da `active-sessions.yaml` se presente.
Se il claim non c'è lo dice (warning non bloccante), non fallisce.

Il registro si scrive solo con la CLI (scrittura chirurgica: mai a mano, mai con `yaml.dump`,
che riscrive il file e perde i commenti dell'intestazione):

```bash
python3 tools/session/active_sessions.py release --domain raw/sessions --uuid <SESSION_ID[:8]> \
  || echo "[session-close §D] WARNING: rilascio claim fallito, GC TTL risolverà."
```

Se la claim non c'è, la CLI non scrive nulla. Registro assente: nulla da rimuovere. Rilasciata
l'ultima entry la CLI riscrive `sessions: []`.

**Chiusura della sessione (US-316)**: dopo il claim `raw/sessions`, la close rilascia anche
il claim di sessione scritto da `/session-start` (se presente):

```bash
python3 tools/session/active_sessions.py release --domain session --kind session
```

Equivalente CLI del blocco sopra, senza PyYAML:
`python3 tools/session/active_sessions.py release --domain raw/sessions`.

**Invariante**: il cleanup rimuove SOLO i claim con `uuid == SESSION_CLAIM_ID` AND
`domain` ∈ {`raw/sessions`, `session`}. Mai rimuovere per operator/posizione (rischio INCIDENTE
multi-sessione).

[^src: .claude/skills/session-close-protocol.md — Fase 0-bis §B, §D]
