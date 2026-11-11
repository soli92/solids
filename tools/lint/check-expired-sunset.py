#!/usr/bin/env python3
"""Check 4ar — annotazioni SUNSET scadute (ERROR, always-on).

PATTERN §23.8 dichiara una sunset policy: una capability annotata `SUNSET: vX.Y`
va rimossa (o l'annotazione rinnovata con motivazione) entro quella versione.
Il reperto che motiva questo check (Tavola Rotonda TR-9b4e7c02, 2026-09-17):
§23.8 e' stato eseguito come annotazione e mai come azione, 0 su 7 — 7 annotazioni
`SUNSET: v2.36` erano ancora presenti sei release dopo la scadenza dichiarata.

Un'annotazione scaduta e' un fallimento *silenzioso* della governance: senza questo
check la sopravvivenza per inerzia non produce nessun segnale.

Non heal-eligible per costruzione: uccidere un layer richiede giudizio umano.
Uso:
    python3 tools/lint/check-expired-sunset.py [--json] [<root>]
Exit code: 0 = nessuna annotazione scaduta, 1 = almeno una scaduta.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# File esclusi: la release history contiene annotazioni storiche per natura.
EXCLUDED_NAMES = {"CHANGELOG.md"}
EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", "archive", "decisions", "meta-prompts"}
# Prefissi di path esclusi: un artefatto di pianificazione *parla* di annotazioni,
# non le porta. Un TSK il cui titolo cita `SUNSET: v2.36` descrive il lavoro di
# risolverla — flaggarlo significa che il check accusa la propria remediation.
# Complementa la regola dei backtick, che copre solo le citazioni inline.
EXCLUDED_PREFIXES = ("management/kanban/", "raw/", "validation/")

SUNSET_RE = re.compile(r"SUNSET:\s*v(\d+)\.(\d+)")
EXEMPT_RE = re.compile(r"SUNSET-EXEMPT")
VERSION_RE = re.compile(r'^pattern_version:\s*["\']?(\d+)\.(\d+)', re.MULTILINE)

SCANNED_SUFFIXES = {".yaml", ".yml", ".md", ".py", ".sh", ".json"}


def read_pattern_version(root: pathlib.Path) -> tuple[int, int] | None:
    """SSOT della versione corrente: factory.config.yaml#pattern_version."""
    cfg = root / "factory.config.yaml"
    try:
        m = VERSION_RE.search(cfg.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return (int(m.group(1)), int(m.group(2))) if m else None


def iter_files(root: pathlib.Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if path.name in EXCLUDED_NAMES:
            continue
        if EXCLUDED_DIRS & set(p.name for p in path.parents):
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        yield path


def in_code_span(line: str, index: int) -> bool:
    """True se `index` cade dentro uno span delimitato da backtick.

    Un'annotazione racchiusa in backtick e' una *citazione* dell'annotazione
    (prosa, log, testo di un TSK), non un'annotazione viva su una capability.
    Senza questa distinzione il check flagga la documentazione di se stesso.
    """
    return line.count("`", 0, index) % 2 == 1


def scan(root: pathlib.Path) -> list[dict]:
    current = read_pattern_version(root)
    if current is None:
        # Graceful degradation: senza SSOT di versione non si puo' decidere la scadenza.
        return []
    findings = []
    for path in iter_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if EXEMPT_RE.search(line):
                continue
            m = SUNSET_RE.search(line)
            if not m or in_code_span(line, m.start()):
                continue
            declared = (int(m.group(1)), int(m.group(2)))
            if declared < current:
                overdue = (current[1] - declared[1]) if current[0] == declared[0] else None
                findings.append({
                    "file": str(path.relative_to(root)),
                    "line": lineno,
                    "declared": f"v{declared[0]}.{declared[1]}",
                    "current": f"v{current[0]}.{current[1]}",
                    "releases_overdue": overdue,
                    "context": line.strip()[:160],
                })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4ar — annotazioni SUNSET scadute")
    ap.add_argument("root", nargs="?", default=".", help="root della factory (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    findings = scan(root)

    if args.json:
        print(json.dumps({"check": "4ar", "findings": findings}, indent=2, ensure_ascii=False))
    elif not findings:
        print("[4ar] OK — nessuna annotazione SUNSET scaduta")
    else:
        print("## ERROR (governance, mai heal-eligible)")
        for f in findings:
            overdue = f"{f['releases_overdue']} release oltre la scadenza" if f["releases_overdue"] is not None else "scaduta"
            print(f"- [ERROR][sunset-expired][4ar] {f['file']}:{f['line']}: "
                  f"annotazione {f['declared']} con pattern_version {f['current']} ({overdue}). "
                  f"Azione: rimuovere la capability, oppure rinnovare l'annotazione con motivazione esplicita, "
                  f"oppure marcarla SUNSET-EXEMPT. Contesto: {f['context']}")
        print(f"\nTotale: {len(findings)} annotazioni SUNSET scadute (PATTERN §23.8)")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
