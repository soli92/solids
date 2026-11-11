#!/usr/bin/env python3
"""
session_id.py — resolver canonico del session_id per la factory.

Ordine di risoluzione (US-308, EP-069):
  1. CLAUDE_CODE_SESSION_ID — variabile d'ambiente impostata da Claude Code
     in CLI e VS Code; UUID completo della chat corrente.
  2. UUID dallo scratchpad — il path dello scratchpad di sessione contiene
     l'UUID come ultimo segmento prima di «scratchpad»; viene estratto dalla
     variabile CLAUDE_CODE_SCRATCHPAD se presente, altrimenti dal path corrente.
  3. uuid4 generato — fallback: la chat non e' riconoscibile dai canali
     istituzionali; viene generato un UUID casuale e il fatto viene dichiarato
     su stderr (o nel campo «source» con --json).

Il modulo NON persiste nulla: e' un resolver puro. La persistenza (seen file,
claim in active-sessions.yaml) e' responsabilita' del chiamante.

API:
  resolve_session_id() -> tuple[str, str]
      Ritorna (uuid_str, source) dove source e' uno di:
        "env"        — da CLAUDE_CODE_SESSION_ID
        "scratchpad" — estratto dal path dello scratchpad
        "generated"  — uuid4, fallback

CLI:
  python3 tools/session/session_id.py [--short] [--json]
    --short  stampa solo i primi 8 caratteri (usato come claim_id)
    --json   stampa {"id": ..., "source": ..., "short": ...}
    se source == "generated" emette avviso su stderr anche senza --json

Cross-platform: stdlib pura, nessun «:» nei nomi file generati.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid as _uuid_mod
from typing import Tuple

# Regex per estrarre UUID v4 da un path qualsiasi.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _uuid_from_scratchpad() -> str | None:
    """
    Tenta di estrarre l'UUID della sessione dal path dello scratchpad.

    Claude Code imposta CLAUDE_CODE_SCRATCHPAD (o equivalente); se assente
    tenta anche la variabile generica TMPDIR / scratchpad noto.
    Il pattern atteso e': .../scratchpad/<uuid>/scratchpad o .../session-<uuid>/...
    """
    candidates = [
        os.environ.get("CLAUDE_CODE_SCRATCHPAD", ""),
        os.environ.get("CLAUDE_SCRATCHPAD", ""),
    ]
    for path in candidates:
        if not path:
            continue
        # Cerca UUID seguito da /scratchpad o come penultimo segmento prima di scratchpad
        # Es.: /private/tmp/claude-501/.../960d764c-ffc0-4876-97bc-974e6ffebf3f/scratchpad
        m = _UUID_RE.search(path)
        if m:
            return m.group(0).lower()
    return None


def resolve_session_id() -> Tuple[str, str]:
    """
    Risolve il session_id della sessione corrente.

    Ritorna:
        (session_id: str, source: str)
        source in {"env", "scratchpad", "generated"}

    Se source == "generated" il chiamante dovrebbe avvisare l'utente
    (cooperare con il log su stderr e' opzionale: e' responsabilita' del CLI).
    """
    # Priorita' 1: variabile d'ambiente istituzionale
    env_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if env_id:
        return (env_id, "env")

    # Priorita' 2: UUID estratto dallo scratchpad
    scratch_id = _uuid_from_scratchpad()
    if scratch_id:
        return (scratch_id, "scratchpad")

    # Priorita' 3: generato — fallback dichiarato
    generated = str(_uuid_mod.uuid4())
    return (generated, "generated")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="session_id.py",
        description="Risolve il session_id canonico della sessione corrente.",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Stampa solo i primi 8 caratteri (claim_id per active-sessions.yaml).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output JSON {id, source, short}.",
    )
    args = parser.parse_args()

    session_id, source = resolve_session_id()
    short_id = session_id[:8]

    if source == "generated":
        # Avviso su stderr: la chat non e' riconoscibile dai canali istituzionali
        sys.stderr.write(
            f"[session_id] source=generated: CLAUDE_CODE_SESSION_ID non impostato "
            f"e scratchpad non rilevato. UUID casuale: {session_id[:8]}...\n"
        )

    if args.as_json:
        out = {"id": session_id, "source": source, "short": short_id}
        print(json.dumps(out))
    elif args.short:
        print(short_id)
    else:
        print(session_id)


if __name__ == "__main__":
    _main()
