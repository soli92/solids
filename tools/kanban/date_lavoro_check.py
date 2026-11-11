#!/usr/bin/env python3
"""
date_lavoro_check.py — Check 4be: date di lavoro obbligatorie sui TSK (ERROR).

Controlla solo i TSK che hanno cambiato stato verso in-progress o done in un commit con data
>= `kanban_dates.required_from` di factory.config.yaml, piu' quelli con un cambio di stato non
ancora committato (working tree contro HEAD). I TSK chiusi prima dell'adozione sono esenti.

  done         richiede started_at e closed_at (YYYY-MM-DD, closed_at >= started_at)
  in-progress  richiede started_at

La data e' quella del lavoro, non della registrazione. A chiave assente il check non segnala nulla.
Non verifica chi ha fatto il lavoro ne' i commit (fuori da questo check).

USO:
  python3 tools/kanban/date_lavoro_check.py [--root <factory>] [--check] [--json] [--dal AAAA-MM-GG]

Solo stdlib + git. Read-only.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "analytics"))
from kanban_history import (  # noqa: E402
    CLOSED_FIELDS, STARTED_FIELDS, TSK_RE, first_field, frontmatter, transitions,
)

KANBAN = "management/kanban"
ARCHIVE = KANBAN + "/archive/"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ATTIVI = ("in_progress", "done")


def required_from(root):
    """Valore di kanban_dates.required_from, o None se blocco o chiave mancano."""
    cfg = root / "factory.config.yaml"
    if not cfg.exists():
        return None
    in_blocco = False
    for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^kanban_dates:\s*(#.*)?$", line):
            in_blocco = True
            continue
        if in_blocco:
            if line.strip() and not line.startswith((" ", "\t", "#")):
                break
            m = re.match(r"^\s+required_from:\s*[\"']?([^\"'#\s]*)", line)
            if m:
                return m.group(1) or None
    return None


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _norm(status):
    return (status or "").replace("-", "_")


def uncommitted_changes(root):
    """TSK (percorso) il cui status nel working tree differisce da HEAD."""
    out = _git(root, "status", "--porcelain", "--untracked-files=all", "--", KANBAN).stdout
    changed = set()
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not TSK_RE.search(rel) or rel.startswith(ARCHIVE) or not (root / rel).exists():
            continue
        now = _norm(frontmatter((root / rel).read_text(encoding="utf-8", errors="replace")).get("status"))
        head = _git(root, "show", f"HEAD:{rel}")
        before = _norm(frontmatter(head.stdout).get("status")) if head.returncode == 0 else None
        if now != before and now in ATTIVI:
            changed.add(rel)
    return changed


def check(root, since):
    touched = {p for p, hist in transitions([KANBAN], since=since, root=root).items()
               if any(h[0] in ATTIVI for h in hist)}
    touched |= uncommitted_changes(root)
    violations = []
    for rel in sorted(touched):
        if rel.startswith(ARCHIVE) or not (root / rel).exists():
            continue
        fm = frontmatter((root / rel).read_text(encoding="utf-8", errors="replace"))
        status = _norm(fm.get("status"))
        if status not in ATTIVI:
            continue
        started_raw = (fm.get("started_at") or "").strip()
        closed_raw = next(((fm.get(n) or "").strip() for n in CLOSED_FIELDS if (fm.get(n) or "").strip()), "")
        missing, problems = [], []
        for nome, raw in (("started_at", started_raw),) + ((("closed_at", closed_raw),) if status == "done" else ()):
            if not raw:
                missing.append(nome)
            elif not ISO_DATE.match(raw):
                problems.append(f"{nome} «{raw}» non e' nel formato AAAA-MM-GG")
        if not missing and not problems and status == "done" and closed_raw < started_raw:
            problems.append(f"closed_at {closed_raw} precede started_at {started_raw}")
        if missing or problems:
            violations.append({
                "id": TSK_RE.search(rel).group(1), "path": rel, "status": status,
                "mancanti": missing, "incoerenze": problems,
            })
    return violations


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parent.parent.parent))
    ap.add_argument("--check", action="store_true", help="exit 1 se ci sono violazioni")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dal", help="sovrascrive kanban_dates.required_from della config")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root).resolve()

    since = a.dal or required_from(root)
    v = check(root, since) if since else []
    if a.json:
        print(json.dumps({"check": "4be", "dal": since, "violazioni": v}, indent=2, ensure_ascii=False))
    elif not since:
        print("[4be] OK — kanban_dates.required_from assente: nessun controllo")
    else:
        for x in v:
            what = "; ".join(([f"mancano {', '.join(x['mancanti'])}"] if x["mancanti"] else []) + x["incoerenze"])
            print(f"- [ERROR][date-lavoro][4be] {x['id']} ({x['status']}): {what} — {x['path']}")
        print(f"[4be] {len(v)} TSK con date di lavoro mancanti o incoerenti (cambi di stato dal {since}).")
    return 1 if a.check and v else 0


if __name__ == "__main__":
    sys.exit(main())
