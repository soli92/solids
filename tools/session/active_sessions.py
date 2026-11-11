#!/usr/bin/env python3
"""
active_sessions.py — CLI per `memory/active-sessions.yaml` (cooperative locking, EP-053).

Unico scrittore a comando del file: gli agenti e i protocolli (session-start,
session-close, dev-protocol) lo chiamano invece di editare lo YAML a mano.
Schema e parsing: `tools/session/claims.py` (puro, senza scritture).

I claim sono ADVISORY. `claim` e `conflicts` stampano avvisi ed escono 0: nessun
lock, nessun lease, nessun arbitro (coerenza con EP-064). Chi legge l'avviso decide.

Uso:
  python3 tools/session/active_sessions.py list [--all] [--json]
  python3 tools/session/active_sessions.py gc [--dry-run] [--json]
  python3 tools/session/active_sessions.py conflicts [--domain D ...] [--json]
  python3 tools/session/active_sessions.py claim --agent A --domain D [--kind agent|session]
          [--ttl N] [--context TXT] [--operator OP] [--uuid U] [--json]
  python3 tools/session/active_sessions.py release --domain D [--uuid U] [--kind K] [--json]

Opzioni comuni: --root <factory_root> (default: CWD), --now <ISO8601> (test).
Default di --uuid: `tools/session/session_id.py --short`. Default di --operator:
`git config user.name`. `release` rimuove SOLO per uuid + domain, mai per operatore
o posizione (piu' sessioni dello stesso operatore possono convivere).

Exit: 0 sempre per list/gc/conflicts/claim/release riusciti; 2 su argomenti o
file illeggibile. Un conflitto NON cambia l'exit code.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claims as C  # noqa: E402
from session_id import resolve_session_id  # noqa: E402

REL_PATH = "memory/active-sessions.yaml"

DEFAULT_HEADER = """\
# Cooperative locking (EP-053) — claim ADVISORY: avvisano, non bloccano.
# Nessun lock, nessun lease, nessun arbitro (coerenza con EP-064).
# Scrittura: python3 tools/session/active_sessions.py {claim|release|gc}
# Lettura:   python3 tools/session/active_sessions.py {list|conflicts}
#
# Procedura (agenti con write scope e /session-start):
#   1. gc         — rimuovi le entry scadute ((last_seen|started_at) + ttl_min < ora).
#   2. conflicts  — se un'altra sessione dichiara lo stesso domain: AVVISO in chat.
#   3. claim      — aggiungi il tuo claim (stesso uuid+domain = rinnovo di last_seen).
#   4. release    — rimuovi il tuo claim al termine (per uuid + domain, mai per operatore).
#
# Schema entry (US-316: lo schema EP-053 resta valido; campi opzionali in coda):
#   - uuid: <8 car.>           # python3 tools/session/session_id.py --short (US-308)
#     agent: <agent-name>      # es. orchestrator, wiki-keeper, tpm; «session-start» per kind: session
#     domain: <domain>         # es. wiki, kanban, sprint, docs; «session» per kind: session
#     started_at: <ISO8601>    # es. 2026-07-30T10:00:00Z
#     ttl_min: 30              # scadenza = (last_seen|started_at) + ttl_min
#     kind: agent              # opzionale: agent (default, omesso) | session (/session-start)
#     operator: <user.name>    # opzionale: git config user.name
#     last_seen: <ISO8601>     # opzionale: rinnovo del claim
#     context: "<testo>"       # opzionale: intent della sessione
#
# Letti per compatibilita' (riscritti in forma canonica): id, opened_at, claimed_at,
# ttl_minutes, claims: [{domain, operation}].
"""


def _now(raw: str | None) -> datetime:
    return C.parse_ts(raw) if raw else datetime.now(timezone.utc)


def _operator(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "config", "user.name"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _load(path: Path):
    if not path.is_file():
        return DEFAULT_HEADER.rstrip("\n").splitlines() + [""], []
    return C.load_text(path.read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _edit(path: Path, header, entries, **kw) -> None:
    """File esistente: modifica chirurgica (storico e formato altrui intatti); nuovo: render."""
    if path.is_file():
        _write(path, C.edit_text(path.read_text(encoding="utf-8"), **kw))
    else:
        _save(path, header, entries)


def _save(path: Path, header, entries) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(C.render(header, entries), encoding="utf-8")
    os.replace(tmp, path)


def _emit(args, payload: dict, lines: list[str]) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)


def _describe(e: dict) -> str:
    who = e.get("operator") or "?"
    return (f"{e.get('uuid', '?')}  {e.get('kind', 'agent'):7}  {e.get('agent', '?')}"
            f"  domain={','.join(C.domains_of(e)) or '?'}  operator={who}"
            f"  da {e.get('started_at', '?')}  ttl {e.get('ttl_min')}m")


def _conflict_lines(found: list[dict]) -> list[str]:
    if not found:
        return []
    out = [f"AVVISO (advisory, non bloccante): {len(found)} claim di altre sessioni"]
    for c in found:
        out.append(f"  - {c['uuid']}  {c.get('operator') or '?'}  {c.get('agent') or '?'}"
                   f"  domain={','.join(c['domains'])}  ({c['reason']})")
    out.append("  Nessun lock: coordina con chi ha il claim, poi procedi a tua scelta.")
    return out


def cmd_list(args, path: Path) -> int:
    _, entries = _load(path)
    live, expired = C.split_live(entries, _now(args.now))
    shown = live + (expired if args.all else [])
    lines = [_describe(e) + ("  [scaduta]" if e in expired else "") for e in shown]
    if not shown:
        lines = ["nessun claim attivo" + (f" ({len(expired)} scaduti, usa gc)" if expired else "")]
    _emit(args, {"live": live, "expired": expired if args.all else len(expired)}, lines)
    return 0


def cmd_gc(args, path: Path) -> int:
    header, entries = _load(path)
    live, expired = C.split_live(entries, _now(args.now))
    if expired and not args.dry_run and path.is_file():
        ids = {(e.get("uuid"), e.get("domain"), e.get("started_at")) for e in expired}
        _edit(path, header, live,
              drop=lambda e: (e.get("uuid"), e.get("domain"), e.get("started_at")) in ids)
    verb = "da rimuovere" if args.dry_run else "rimossa"
    lines = [f"{verb}: claim {e.get('uuid', '?')} ({e.get('agent', '?')}, "
             f"domain={e.get('domain', '?')}) — TTL scaduto" for e in expired]
    _emit(args, {"removed": [e.get("uuid") for e in expired], "dry_run": args.dry_run,
                 "remaining": len(live)}, lines or ["gc: nessun claim scaduto"])
    return 0


def cmd_conflicts(args, path: Path) -> int:
    root = Path(args.root)
    _, entries = _load(path)
    uuid = (args.uuid or resolve_session_id()[0])[:8]
    found = C.conflicts(entries, uuid, args.operator or _operator(root),
                        args.domain or [], _now(args.now))
    _emit(args, {"conflicts": found, "advisory": True},
          _conflict_lines(found) or ["nessun conflitto"])
    return 0


def cmd_claim(args, path: Path) -> int:
    root = Path(args.root)
    header, entries = _load(path)
    now = _now(args.now)
    uuid = (args.uuid or resolve_session_id()[0])[:8].lower()
    operator = args.operator or _operator(root)
    found = C.conflicts(entries, uuid, operator, [args.domain], now)

    stamp = C.fmt_ts(now)
    mine = [e for e in entries if C.same_uuid(e.get("uuid"), uuid)
            and C.has_domain(e, args.domain)]
    nuove = []
    if mine:
        mine[0]["last_seen"] = stamp
        if args.context:
            mine[0]["context"] = args.context
        action = "rinnovato"
    else:
        entry = {"uuid": uuid, "kind": args.kind, "agent": args.agent,
                 "domain": args.domain, "operator": operator, "started_at": stamp,
                 "ttl_min": args.ttl or C.DEFAULT_TTL[args.kind]}
        if args.kind == "session":
            entry["last_seen"] = stamp
        if args.context:
            entry["context"] = args.context
        entries.append(entry)
        nuove = [entry]
        action = "aggiunto"
    stessa = (lambda e: C.same_uuid(e.get("uuid"), uuid) and C.has_domain(e, args.domain))
    _edit(path, header, entries, touch=(stessa, stamp) if mine else None, add=nuove)
    _emit(args, {"action": action, "uuid": uuid, "domain": args.domain,
                 "conflicts": found, "advisory": True},
          [f"claim {action}: {uuid} domain={args.domain}"] + _conflict_lines(found))
    return 0


def cmd_release(args, path: Path) -> int:
    header, entries = _load(path)
    uuid = (args.uuid or resolve_session_id()[0])[:8]
    keep = [e for e in entries if not (
        C.same_uuid(e.get("uuid"), uuid) and C.has_domain(e, args.domain)
        and (args.kind is None or e.get("kind") == args.kind))]
    removed = len(entries) - len(keep)
    if removed and path.is_file():
        _edit(path, header, keep, drop=lambda e: (
            C.same_uuid(e.get("uuid"), uuid) and C.has_domain(e, args.domain)
            and (args.kind is None or e.get("kind") == args.kind)))
    msg = (f"claim rimosso: {uuid} domain={args.domain}" if removed else
           f"nessun claim {uuid} domain={args.domain}: nulla da rimuovere")
    _emit(args, {"removed": removed, "uuid": uuid, "domain": args.domain}, [msg])
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="active_sessions.py",
                                description="Claim advisory in memory/active-sessions.yaml.")
    p.add_argument("--root", default=".")
    p.add_argument("--now", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list"); s.add_argument("--all", action="store_true")
    s = sub.add_parser("gc"); s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("conflicts")
    s.add_argument("--domain", action="append")
    s.add_argument("--uuid"); s.add_argument("--operator")
    s = sub.add_parser("claim")
    s.add_argument("--agent", required=True); s.add_argument("--domain", required=True)
    s.add_argument("--kind", choices=("agent", "session"), default="agent")
    s.add_argument("--ttl", type=int); s.add_argument("--context")
    s.add_argument("--operator"); s.add_argument("--uuid")
    s = sub.add_parser("release")
    s.add_argument("--domain", required=True); s.add_argument("--uuid")
    s.add_argument("--kind", choices=("agent", "session"))

    # --json / --root / --now accettati anche dopo il sottocomando
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        sp.add_argument("--root", default=argparse.SUPPRESS)
        sp.add_argument("--now", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    args = p.parse_args(argv)
    path = Path(args.root) / REL_PATH
    try:
        return {"list": cmd_list, "gc": cmd_gc, "conflicts": cmd_conflicts,
                "claim": cmd_claim, "release": cmd_release}[args.cmd](args, path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[active_sessions] file illeggibile: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
