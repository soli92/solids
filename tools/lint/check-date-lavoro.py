#!/usr/bin/env python3
"""Check 4be — date di lavoro obbligatorie sui TSK (ERROR).

Wrapper di `tools/kanban/date_lavoro_check.py`: un TSK che passa a `in-progress` dalla data
`kanban_dates.required_from` ha `started_at`; uno che passa a `done` ha `started_at` e `closed_at`
(AAAA-MM-GG, `closed_at >= started_at`). Include i cambi di stato non committati; lo storico e'
esente; a chiave assente nessun finding.

Uso:
    python3 tools/lint/check-date-lavoro.py [--root <factory>] [--json] [--strict]
Exit code: 0 anche con finding; con --strict 1 se ce n'e' almeno uno.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RADICE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools" / "kanban"))
import date_lavoro_check as dl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4be — date di lavoro dei TSK")
    ap.add_argument("root", nargs="?", default=None, help="root della factory (alternativa a --root)")
    ap.add_argument("--root", dest="root_opt", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono finding")
    args = ap.parse_args()
    root = pathlib.Path(args.root_opt or args.root or ".").resolve()
    since = dl.required_from(root)
    v = dl.check(root, since) if since else []
    if args.json:
        print(json.dumps({"check": "4be", "dal": since, "findings": v}, indent=2, ensure_ascii=False))
    elif not v:
        print("[4be] OK — " + (f"nessun TSK con date mancanti (dal {since})" if since
                               else "kanban_dates.required_from assente, nessun controllo"))
    else:
        print("## ERROR (date di lavoro)")
        for x in v:
            what = "; ".join(([f"mancano {', '.join(x['mancanti'])}"] if x["mancanti"] else []) + x["incoerenze"])
            print(f"- [ERROR][date-lavoro][4be] {x['id']} ({x['status']}): {what} — {x['path']}")
        print(f"\nTotale: {len(v)} TSK (cambi di stato dal {since})")
    return 1 if v and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
