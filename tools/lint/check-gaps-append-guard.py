#!/usr/bin/env python3
"""Check 4bd — wiki/gaps.md si scrive solo in coda (WARNING, detective, mai bloccante).

Esegue `tools/wiki/gaps_append_guard.py` sull'ultimo commit che tocca `wiki/gaps.md` (con
`--storia N` sugli ultimi N): una riga tolta o modificata, a parte il cambio `- [ ]` -> `- [x]` e
la sostituzione di `**Aggiornamento...**` con `**Risolto:**` nel blocco chiuso, e' un avviso.
Nessun hook di pre-commit: la guardia e' solo detective.

Senza git o senza storia dei gap il check non ha nulla da dire: OK silenzioso.

Uso:
    python3 tools/lint/check-gaps-append-guard.py [--json] [--storia N] [--strict] [<root>]
Exit code: 0 anche con finding; con --strict 1 se ce n'e' almeno uno.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

GUARD = pathlib.Path(__file__).resolve().parents[1] / "wiki" / "gaps_append_guard.py"


def carica(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("gaps_append_guard", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.lag.ROOT = root
    return m


def scan(root: pathlib.Path, storia: int = 1) -> tuple[int, list[dict]]:
    """(commit esaminati, finding) — un finding per commit che ha tolto righe di gap."""
    g = carica(root)
    shas = g.lag.git("log", f"-{storia}", "--format=%h", "--", g.GAPS).stdout.decode().split()
    findings = []
    for sha in shas:
        gone = g.check_commit(sha)
        if gone:
            findings.append({
                "commit": sha,
                "righe": len(gone),
                "esempio": gone[0].decode("utf-8", "replace")[:120],
            })
    return len(shas), findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4bd — wiki/gaps.md append-only")
    ap.add_argument("root", nargs="?", default=".", help="root della factory (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--storia", type=int, default=1, help="quanti commit dei gap esaminare (default 1)")
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono finding")
    args = ap.parse_args()

    esaminati, findings = scan(pathlib.Path(args.root).resolve(), args.storia)
    if args.json:
        print(json.dumps({"check": "4bd", "esaminati": esaminati, "findings": findings},
                         indent=2, ensure_ascii=False))
    elif not findings:
        print(f"[4bd] OK — {esaminati} commit di wiki/gaps.md esaminati, nessuna riga tolta")
    else:
        print("## WARNING (gap append-only)")
        for f in findings:
            print(f"- [WARNING][gaps-righe-rimosse][4bd] wiki/gaps.md: il commit {f['commit']} ha tolto o "
                  f"modificato {f['righe']} righe, prima: «{f['esempio']}»")
        print(f"\nTotale: {len(findings)} commit su {esaminati} esaminati")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
