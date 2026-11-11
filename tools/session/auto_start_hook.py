#!/usr/bin/env python3
"""
auto_start_hook.py — hook per l'auto-apertura di sessione (US-316).

Eventi gestiti:
  UserPromptSubmit  vettore principale: scatta al primo messaggio di ogni chat, anche
                    nell'estensione VS Code, e il contesto arriva accanto al messaggio.
  SessionStart      ancora accettato. Nell'estensione VS Code scatta una volta sola
                    all'avvio dell'estensione, con un session_id che non corrisponde a
                    nessuna chat, e il suo contesto non arriva a nessuna chat: per questo
                    non e' piu' registrato in `.claude/settings.json`.

Contratto:
  stdin   payload JSON dell'hook di Claude Code ({session_id, hook_event_name, source,
          prompt, transcript_path, cwd, ...}).
  stdout  vuoto, oppure un solo JSON `hookSpecificOutput.additionalContext` che chiede
          all'assistente di eseguire `/session-start --auto` (o `--quick`).
  exit    sempre 0: un hook che fallisce non deve mai impedire l'apertura della chat.

Esce 0 SENZA ALCUN OUTPUT (nemmeno su stderr) se in factory.config.yaml
`session_start.enabled` o `session_start.auto_launch.enabled` non valgono `true`.
A flag spenti la factory e' identica a prima.

Guard di idempotenza: `memory/auto-launch-seen.yaml` (gitignorato, per macchina)
registra i session_id gia' serviti; una entry vale `idempotency_ttl_minutes`
(default 1440). Stesso session_id (o stesso prefisso di 8 caratteri) entro il TTL
→ nessuna iniezione. `source` resume/clear/compact → nessuna iniezione (non e' una
chat nuova). Con UserPromptSubmit: messaggio che e' gia' `/session-start` → id registrato,
nessuna iniezione; transcript che contiene gia' una risposta dell'assistente (chat ripresa
oltre il TTL) → id registrato, nessuna iniezione. Il session_id viene dal payload; altrimenti da
`tools/session/session_id.py` (US-308). Se nemmeno quello lo riconosce (uuid4
generato) non si puo' deduplicare: nessuna iniezione, nota su stderr.

L'hook NON scrive claim in `memory/active-sessions.yaml`: lo fa la Fase 5 del
protocollo, se e quando gira.

Snippet per `.claude/settings.json` (da aggiungere a mano, non lo fa questo script):

  "UserPromptSubmit": [{"hooks": [{"type": "command",
    "command": "python3 \\"$CLAUDE_PROJECT_DIR/tools/session/auto_start_hook.py\\" 2>/dev/null || true",
    "timeout": 10}]}]
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEEN_REL = "memory/auto-launch-seen.yaml"
DEFAULT_TTL_MIN = 1440
SKIP_SOURCES = {"resume", "clear", "compact"}
SESSION_START_PROMPT = re.compile(r"^\s*/session-start(\s|$)")


def _note(msg: str) -> None:
    try:
        sys.stderr.write(f"[auto_start_hook] {msg}\n")
    except OSError:
        pass


def config_block(text: str, path: tuple[str, ...]) -> dict:
    """Scalari figli diretti del blocco annidato `path` (parser per indentazione)."""
    stack: list[tuple[int, str]] = []
    out: dict = {}
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", stripped)
        if not m:
            continue
        indent = len(raw) - len(raw.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key, val = m.group(1), re.split(r"\s+#", m.group(2), maxsplit=1)[0].strip()
        if tuple(k for _, k in stack) == path and key not in out:
            out[key] = val.strip("\"'")
        if val == "":
            stack.append((indent, key))
    return out


def _true(value) -> bool:
    return str(value).strip().lower() in ("true", "yes", "on", "1")


def load_seen(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    entries, cur = [], None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if s.startswith("- "):
            cur = {}
            entries.append(cur)
            s = s[2:].strip()
        m = re.match(r"^(id|first_seen):\s*(.+)$", s)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip().strip("\"'")
    return entries


def write_seen(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Session_id gia' serviti dall'auto-apertura (tools/session/auto_start_hook.py).",
             "# Stato per macchina, gitignorato. GC a session_start.auto_launch.idempotency_ttl_minutes.",
             "seen:"]
    for e in entries:
        lines += [f"  - id: {e['id']}", f"    first_seen: {e['first_seen']}"]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _parse_ts(raw: str):
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _transcript_has_reply(path_raw) -> bool:
    """True se il transcript contiene gia' una risposta dell'assistente (chat non nuova)."""
    if not path_raw:
        return False
    try:
        with open(Path(str(path_raw)).expanduser(), encoding="utf-8", errors="replace") as fh:
            return any('"type":"assistant"' in line for line in fh)
    except OSError:
        return False


def _resolve_id(payload: dict, root: Path) -> tuple[str, str]:
    sid = str(payload.get("session_id") or "").strip()
    if sid:
        return sid.lower(), "payload"
    sys.path.insert(0, str(root / "tools" / "session"))
    try:
        from session_id import resolve_session_id
        sid, source = resolve_session_id()
        return sid.lower(), source
    except Exception:  # noqa: BLE001 — un hook non deve mai esplodere
        return "", "none"


def run(payload: dict, root: Path, now: datetime | None = None) -> str | None:
    """Ritorna il JSON da stampare, oppure None (nessun output)."""
    cfg = root / "factory.config.yaml"
    if not cfg.is_file():
        return None
    text = cfg.read_text(encoding="utf-8", errors="replace")
    block = config_block(text, ("session_start",))
    auto = config_block(text, ("session_start", "auto_launch"))
    if not (_true(block.get("enabled")) and _true(auto.get("enabled"))):
        return None  # silenzio totale a flag spenti

    event = str(payload.get("hook_event_name") or "SessionStart")
    source = str(payload.get("source") or "startup")
    if event == "SessionStart" and source in SKIP_SOURCES:
        return None
    sid, id_source = _resolve_id(payload, root)
    if not sid or id_source == "generated":
        _note("session_id non riconoscibile: idempotenza impossibile, nessuna iniezione")
        return None

    try:
        ttl = int(auto.get("idempotency_ttl_minutes") or DEFAULT_TTL_MIN)
    except ValueError:
        ttl = DEFAULT_TTL_MIN
    now = now or datetime.now(timezone.utc)
    seen_path = root / SEEN_REL
    entries = [e for e in load_seen(seen_path)
               if e.get("id") and (_parse_ts(e.get("first_seen", "")) or now - timedelta(days=3650))
               >= now - timedelta(minutes=ttl)]
    if any(e["id"] == sid or e["id"][:8] == sid[:8] for e in entries):
        write_seen(seen_path, entries)  # applica comunque la GC
        return None

    entries.append({"id": sid, "first_seen": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    write_seen(seen_path, entries)
    if event == "UserPromptSubmit":
        if SESSION_START_PROMPT.match(str(payload.get("prompt") or "")):
            return None  # l'utente lo sta gia' lanciando a mano
        if _transcript_has_reply(payload.get("transcript_path")):
            return None  # chat ripresa: non e' una chat nuova
    mode = auto.get("mode_default") or "auto"
    mode = mode if mode in ("auto", "quick") else "auto"
    hook_event = event if event in ("SessionStart", "UserPromptSubmit") else "SessionStart"
    context = (f"Auto-apertura di sessione attiva (session_start.auto_launch): questa e' una "
               f"chat nuova. PRIMA di qualsiasi altra azione, e prima di rispondere al "
               f"messaggio dell'utente, esegui `/session-start --{mode}`: invoca il tool "
               f"Skill con skill \"session-start\" e args \"--{mode}\"; poi rispondi al "
               f"messaggio. "
               f"session_id={sid[:8]} event={hook_event}. "
               f"L'hook ha gia' registrato questo session_id: la Fase 0-ter non va ripetuta "
               f"(hook_seen: true).")
    return json.dumps({"hookSpecificOutput": {"hookEventName": hook_event,
                                              "additionalContext": context}})


def main() -> int:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        payload = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        payload = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    try:
        out = run(payload if isinstance(payload, dict) else {}, root)
    except Exception as exc:  # noqa: BLE001
        _note(f"errore ignorato: {exc}")
        out = None
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
