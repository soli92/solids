#!/usr/bin/env python3
"""Check 4bb — wiki/log.md si scrive solo in coda (WARNING, detective, mai bloccante).

Esegue `tools/wiki/log_append_guard.py` sull'ultimo commit che tocca `wiki/log.md` (con
`--storia N` sugli ultimi N): una riga tolta o modificata senza archivio `wiki/log-*.md` scritto
nello stesso commit e' una perdita silenziosa di entry (R.5). Il frontmatter YAML del log e'
esente. Il blocco preventivo e' un'altra cosa: l'hook di pre-commit opt-in
(`wiki_lint.log_append_guard.hook`, `tools/vcs/install_factory_hooks.py`).

Senza git o senza storia del log il check non ha nulla da dire: OK silenzioso.

Uso:
    python3 tools/lint/check-log-append-guard.py [--json] [--storia N] [--strict] [<root>]
Exit code: 0 anche con finding; con --strict 1 se ce n'e' almeno uno.
Origine della guardia: portale-servizi-factory db21bf88.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

GUARD = pathlib.Path(__file__).resolve().parents[1] / "wiki" / "log_append_guard.py"


def carica(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("log_append_guard", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = root
    return m


def scan(root: pathlib.Path, storia: int = 1) -> tuple[int, list[dict]]:
    """(commit esaminati, finding) — un finding per commit che ha tolto righe senza archivio."""
    g = carica(root)
    shas = g.git("log", f"-{storia}", "--format=%h", "--", g.LOG).stdout.decode().split()
    findings = []
    for sha in shas:
        gone = g.check_commit(sha)
        if gone:
            findings.append({
                "commit": sha,
                "righe": len(gone),
                "entry": sum(1 for l in gone if l.startswith(b"## ")),
                "esempio": gone[0].decode("utf-8", "replace")[:120],
            })
    return len(shas), findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4bb — wiki/log.md append-only")
    ap.add_argument("root", nargs="?", default=".", help="root della factory (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--storia", type=int, default=1, help="quanti commit del log esaminare (default 1)")
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono finding")
    args = ap.parse_args()

    esaminati, findings = scan(pathlib.Path(args.root).resolve(), args.storia)
    if args.json:
        print(json.dumps({"check": "4bb", "esaminati": esaminati, "findings": findings},
                         indent=2, ensure_ascii=False))
    elif not findings:
        print(f"[4bb] OK — {esaminati} commit di wiki/log.md esaminati, nessuna riga tolta senza archivio")
    else:
        print("## WARNING (registro append-only)")
        for f in findings:
            print(f"- [WARNING][log-righe-rimosse][4bb] wiki/log.md: il commit {f['commit']} ha tolto "
                  f"{f['righe']} righe ({f['entry']} entry) senza archivio nello stesso commit, "
                  f"prima: «{f['esempio']}». Recupero: python3 tools/wiki/recover_log_entries.py")
        print(f"\nTotale: {len(findings)} commit su {esaminati} esaminati")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
