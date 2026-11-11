#!/usr/bin/env python3
"""
check-portable-paths.py — tracked paths must be checkout-able on Windows.

A single file whose name is illegal on Windows makes `git pull` and `git clone`
fail for the whole repository, with `error: invalid path ...` followed by
`fatal: unable to checkout working tree`. It is not fixable client-side: the name
comes from the repo. This is why the check lives here and not in a client hook.

Real incident (2026-09-16): three release-gate audit logs were written with a full
extended ISO-8601 timestamp — `2026-06-26T18:00:00Z-pass.log` — because
`.claude/skills/release-validation-gate.md` documented `<timestamp>` with a colon
in its example. A Windows colleague could not pull the repo at all.

Checks (against `git ls-files`, i.e. exactly what a clone writes to disk):
  1. characters forbidden on Windows:  < > : " | ? *  and control chars
  2. reserved DOS device names:        CON PRN AUX NUL COM1-9 LPT1-9 CLOCK$
  3. trailing space or dot in any path segment
  4. case-insensitive collisions (Windows cannot hold both files)
  5. NFC/NFD collisions (macOS writes NFD, Windows expects NFC)
  6. paths long enough to risk MAX_PATH=260 once the clone prefix is added

Exit codes:
  0 — OK
  1 — at least one violation
  2 — usage / git failure

Run from anywhere inside the repo:
  python3 tools/lint/check-portable-paths.py
  python3 tools/lint/check-portable-paths.py --json
  python3 tools/lint/check-portable-paths.py --max-path-budget 180
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from collections import defaultdict

FORBIDDEN_CHARS = set('<>:"|?*') | {chr(c) for c in range(32)}
RESERVED_STEMS = (
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def tracked_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        print(f"ERROR: git ls-files failed: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [p for p in proc.stdout.split("\0") if p]


def scan(paths: list[str], max_path_budget: int) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []

    for path in paths:
        for segment in path.split("/"):
            bad = sorted(set(segment) & FORBIDDEN_CHARS)
            if bad:
                shown = " ".join(repr(c) for c in bad)
                violations.append(
                    {
                        "rule": "forbidden-char",
                        "path": path,
                        "detail": f"carattere vietato su Windows: {shown}",
                    }
                )
                break
            if segment.split(".")[0].upper() in RESERVED_STEMS:
                violations.append(
                    {
                        "rule": "reserved-name",
                        "path": path,
                        "detail": f"nome riservato DOS: {segment}",
                    }
                )
                break
            if segment != segment.rstrip(" ."):
                violations.append(
                    {
                        "rule": "trailing-space-or-dot",
                        "path": path,
                        "detail": f"segmento con spazio o punto finale: {segment!r}",
                    }
                )
                break

        if len(path) > max_path_budget:
            violations.append(
                {
                    "rule": "long-path",
                    "path": path,
                    "detail": f"{len(path)} caratteri (budget {max_path_budget}, MAX_PATH Windows 260)",
                }
            )

    for key, group in _groups(paths, lambda p: p.lower()):
        violations.append(
            {
                "rule": "case-collision",
                "path": " <-> ".join(group),
                "detail": f"differiscono solo per maiuscole/minuscole: {key}",
            }
        )

    for key, group in _groups(paths, lambda p: unicodedata.normalize("NFC", p)):
        violations.append(
            {
                "rule": "unicode-collision",
                "path": " <-> ".join(group),
                "detail": "collidono dopo normalizzazione NFC (macOS scrive NFD)",
            }
        )

    return violations


def _groups(paths: list[str], key_fn):
    buckets: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        buckets[key_fn(path)].append(path)
    return [(k, v) for k, v in buckets.items() if len(v) > 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--max-path-budget",
        type=int,
        default=200,
        help="lunghezza massima di un path tracciato (default 200, lascia 60 per il prefisso del clone)",
    )
    args = parser.parse_args()

    paths = tracked_paths()
    violations = scan(paths, args.max_path_budget)

    if args.json:
        print(
            json.dumps(
                {"tracked": len(paths), "violations": violations},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"path tracciati: {len(paths)}")
        for v in violations:
            print(f"ERROR [{v['rule']}] {v['path']}\n        {v['detail']}")
        if not violations:
            print("OK — ogni path e' scrivibile su Windows, macOS e Linux")
        else:
            print(
                f"\n{len(violations)} violazione(i): su Windows questi path fanno "
                "fallire `git pull`/`git clone` dell'intero repo."
            )

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
