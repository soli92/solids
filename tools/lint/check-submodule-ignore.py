#!/usr/bin/env python3
"""Check 4ax — `ignore = dirty` su ogni submodule di .gitmodules (WARNING, heal-eligible).

Senza `ignore`, ogni `git status` sul padre apre un processo `git status` dentro ciascun
submodule per sapere se il suo worktree ha modifiche. Misura su una derivata con 63
submodule (2026-09-25, 7 misure concordi): 12-17 s su Windows con antivirus in real-time,
~6 s anche su macOS; con `ignore = dirty` 0 processi figli e meno di un secondo. Lo stesso
`git status` lo lanciano Claude Code all'apertura di ogni chat, gli agenti nelle verifiche e
VS Code a ogni refresh.

`ignore = dirty` toglie solo la scansione del contenuto: lo spostamento del puntatore
(` M code_repos/<x>`) resta visibile. Chi ha bisogno del contenuto dei worktree usa
`git status --ignore-submodules=none` o `git -C <submodule> status`.

Legge .gitmodules come testo: non lancia git, quindi costa zero anche dove ogni processo
costa centinaia di millisecondi.

Heal: `git config -f .gitmodules submodule.<nome>.ignore dirty`.
Uso:
    python3 tools/lint/check-submodule-ignore.py [--json] [--strict] [<root>]
Exit code: 0 anche con finding (WARNING non blocca run-deterministic.py); con --strict
1 se almeno un submodule è senza `ignore`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

SECTION_RE = re.compile(r'^\s*\[submodule\s+"([^"]+)"\]\s*$')
KEY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s*=\s*(.*?)\s*$")
ACCEPTED = {"dirty", "all"}


def parse_gitmodules(path: pathlib.Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        m = SECTION_RE.match(line)
        if m:
            current = sections.setdefault(m.group(1), {})
            continue
        if stripped.startswith("["):
            current = None
            continue
        m = KEY_RE.match(line)
        if m and current is not None:
            current[m.group(1).lower()] = m.group(2)
    return sections


def scan(root: pathlib.Path) -> list[dict]:
    gm = root / ".gitmodules"
    if not gm.is_file():
        return []
    findings = []
    for name, keys in parse_gitmodules(gm).items():
        value = keys.get("ignore", "")
        if value.lower() not in ACCEPTED:
            findings.append({"submodule": name, "ignore": value or None})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4ax — ignore dei submodule in .gitmodules")
    ap.add_argument("root", nargs="?", default=".", help="root della factory (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono finding")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    findings = scan(root)

    if args.json:
        print(json.dumps({"check": "4ax", "findings": findings}, indent=2, ensure_ascii=False))
    elif not findings:
        print("[4ax] OK — tutti i submodule di .gitmodules hanno `ignore = dirty`")
    else:
        print("## WARNING (prestazioni, heal-eligible)")
        for f in findings:
            current = f"`ignore = {f['ignore']}`" if f["ignore"] else "nessun `ignore`"
            print(f"- [WARNING][submodule-ignore-missing][4ax] .gitmodules: submodule "
                  f"\"{f['submodule']}\" con {current}: ogni `git status` sul padre apre un "
                  f"processo dentro questo submodule. Heal: "
                  f"git config -f .gitmodules submodule.{f['submodule']}.ignore dirty")
        print(f"\nTotale: {len(findings)} submodule senza `ignore = dirty`")

    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
