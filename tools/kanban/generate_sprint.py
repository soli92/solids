#!/usr/bin/env python3
"""Rigenera management/kanban/sprint.md dal frontmatter dei TSK.

sprint.md e' una view: ogni riga viene dal file TSK, mai da una versione
precedente della view. Scope:
  - sprint corrente: TSK in_progress, review, blocked + todo P0/P1
  - lookahead:       TSK todo P2/P3 (e todo senza priorita')
Lo storico delle versioni precedenti sta in sprint-archive-*.md.

Opzionale: adottarlo vuol dire che sprint.md smette di essere curato a mano (archiviare prima la
versione corrente in sprint-archive-<periodo>.md). ID con o senza prefisso di namespace (modulo
condiviso tools/coordinamento/kanban_ids.py). Dalla factory derivata portale-servizi-factory.

Uso:
  python3 tools/kanban/generate_sprint.py            # scrive sprint.md
  python3 tools/kanban/generate_sprint.py --check    # exit 1 se sprint.md non e' aggiornato
  python3 tools/kanban/generate_sprint.py --stdout   # stampa senza scrivere
  python3 tools/kanban/generate_sprint.py --root <factory> --stdout
"""

import argparse
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "coordinamento"))
import kanban_ids  # noqa: E402  (fonte unica della forma degli ID)
KANBAN = ROOT / "management" / "kanban"
SPRINT = KANBAN / "sprint.md"


def _imposta_radice(root):
    global ROOT, KANBAN, SPRINT
    ROOT = pathlib.Path(root).resolve()
    KANBAN = ROOT / "management" / "kanban"
    SPRINT = KANBAN / "sprint.md"


def _nome_progetto():
    cfg = ROOT / "factory.config.yaml"
    if cfg.is_file():
        m = re.search(r"^project:[ \t]*\n(?:[ \t]+.*\n|[ \t]*\n)*?[ \t]+name:\s*[\"']?([^\"'#\n]+?)[\"']?\s*(?:#.*)?$",
                      cfg.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return ROOT.name

CURRENT_STATUSES = ("in_progress", "review", "blocked")
OPEN_STATUSES = CURRENT_STATUSES + ("todo",)
STATUS_ORDER = {s: i for i, s in enumerate(("blocked", "in_progress", "review", "todo"))}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _frontmatter(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    fm = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            # lista a blocchi: "  - voce"
            items = []
            while i < len(lines) and re.match(r"^\s+-\s+", lines[i]):
                items.append(re.sub(r"^\s+-\s+", "", lines[i]).strip().strip("\"'"))
                i += 1
            fm[key] = items
            continue
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            continue
        val = re.sub(r"\s+#.*$", "", val) if not val.startswith(("\"", "'")) else val
        fm[key] = val.strip().strip("\"'")
    return fm


def _short_id(ref):
    m = re.search(r"(?:[A-Z]{2,4}-)?(?:TSK|US|EP)-\d+", str(ref))
    return m.group(0) if m else str(ref)


def _cell(value):
    return str(value or "—").replace("|", "\\|").replace("\n", " ").strip() or "—"


def load_tasks():
    tasks = []
    for path in sorted(KANBAN.glob("*/**/*TSK-*.md")):
        fm = _frontmatter(path)
        tid = fm.get("id") or path.stem
        if not kanban_ids.TSK_RE.match(str(tid)):
            continue
        status = str(fm.get("status", "")).strip().replace("-", "_")
        if status not in OPEN_STATUSES:
            continue
        deps = fm.get("depends_on") or fm.get("dependencies") or fm.get("blocked_by") or []
        if isinstance(deps, str):
            deps = [d for d in re.split(r"[,\s]+", deps) if d]
        tasks.append({
            "id": tid,
            "title": fm.get("title", ""),
            "epic": _short_id(fm.get("epic") or path.relative_to(KANBAN).parts[0]),
            "us": _short_id(fm.get("us") or fm.get("story") or ""),
            "layer": fm.get("layer", ""),
            "priority": fm.get("priority", ""),
            "status": status,
            "owner": fm.get("owner") or fm.get("assignee") or "",
            "deps": [_short_id(d) for d in deps],
            "path": path.relative_to(KANBAN).as_posix(),
        })
    return tasks


def load_epics():
    epics = {}
    for path in KANBAN.glob("*/*EP-*.md"):
        fm = _frontmatter(path)
        eid = fm.get("id") or path.stem
        epics[eid] = {"title": fm.get("title", ""), "status": fm.get("status", ""),
                      "path": path.relative_to(KANBAN).as_posix()}
    return epics


def _sort_key(t):
    num = re.search(r"(\d+)$", t["id"])
    return (STATUS_ORDER.get(t["status"], 9), PRIORITY_ORDER.get(t["priority"], 9),
            int(num.group(1)) if num else 0)


def _table(rows):
    out = ["| TSK | Titolo | US | Layer | Pri | Status | Owner | Dipende da |",
           "|---|---|---|---|---|---|---|---|"]
    for t in sorted(rows, key=_sort_key):
        out.append("| [{id}]({path}) | {title} | {us} | {layer} | {pri} | {status} | {owner} | {deps} |".format(
            id=t["id"], path=t["path"], title=_cell(t["title"]), us=_cell(t["us"]),
            layer=_cell(t["layer"]), pri=_cell(t["priority"]), status=t["status"],
            owner=_cell(t["owner"]), deps=_cell(", ".join(t["deps"]))))
    return out


def _by_epic(tasks, epics, heading):
    out = [f"## {heading}", ""]
    if not tasks:
        return out + ["Nessun TSK.", ""]
    for eid in sorted({t["epic"] for t in tasks}):
        ep = epics.get(eid, {})
        title = f" — {ep['title']}" if ep.get("title") else ""
        out += [f"### {eid}{title}", ""]
        out += _table([t for t in tasks if t["epic"] == eid])
        out.append("")
    return out


def _riga_archivi():
    archivi = sorted(KANBAN.glob("sprint-archive-*.md"))
    if not archivi:
        return ["> `python3 tools/kanban/generate_sprint.py`."]
    return ["> `python3 tools/kanban/generate_sprint.py`. Storico delle versioni precedenti:",
            "> " + ", ".join(f"[`{a.name}`]({a.name})" for a in archivi) + "."]


def render(tasks, epics, generated_at):
    current = [t for t in tasks if t["status"] in CURRENT_STATUSES
               or (t["status"] == "todo" and t["priority"] in ("P0", "P1"))]
    lookahead = [t for t in tasks if t not in current]

    out = [
        "<!-- generated, do not edit -->",
        f"<!-- Generato da tools/kanban/generate_sprint.py il {generated_at} -->",
        "",
        f"# Sprint view — {_nome_progetto()}",
        "",
        "> View generata dal frontmatter dei TSK: non modificarla a mano, rigenerala con",
    ] + _riga_archivi() + [
        ">",
        "> Sprint corrente: TSK `in_progress`, `review`, `blocked` e `todo` P0/P1.",
        "> Lookahead: TSK `todo` P2/P3 o senza priorita'.",
        "",
        "## Epiche con lavoro aperto",
        "",
        "| Epica | Titolo | Status epica | blocked | in_progress | review | todo |",
        "|---|---|---|---|---|---|---|",
    ]
    for eid in sorted({t["epic"] for t in tasks}):
        ep = epics.get(eid, {})
        counts = {s: sum(1 for t in tasks if t["epic"] == eid and t["status"] == s)
                  for s in ("blocked", "in_progress", "review", "todo")}
        link = f"[{eid}]({ep['path']})" if ep.get("path") else eid
        out.append(f"| {link} | {_cell(ep.get('title'))} | {_cell(ep.get('status'))} | "
                   f"{counts['blocked']} | {counts['in_progress']} | {counts['review']} | {counts['todo']} |")
    out += ["", f"Totale TSK aperti: {len(tasks)} (sprint corrente {len(current)}, lookahead {len(lookahead)}).", ""]
    out += _by_epic(current, epics, "Sprint corrente")
    out += _by_epic(lookahead, epics, "Lookahead")
    return "\n".join(out).rstrip() + "\n"


def _strip_timestamp(text):
    return re.sub(r"^<!-- Generato da .*-->$", "", text, count=1, flags=re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 se sprint.md non e' aggiornato")
    mode.add_argument("--stdout", action="store_true", help="stampa senza scrivere")
    ap.add_argument("--root", help="radice della factory (default: quella dello script)")
    args = ap.parse_args()
    if args.root:
        _imposta_radice(args.root)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = render(load_tasks(), load_epics(), now)

    if args.stdout:
        sys.stdout.write(content)
        return 0
    if args.check:
        current = SPRINT.read_text(encoding="utf-8") if SPRINT.exists() else ""
        if _strip_timestamp(current) != _strip_timestamp(content):
            print("sprint.md non e' aggiornato: python3 tools/kanban/generate_sprint.py", file=sys.stderr)
            return 1
        return 0
    SPRINT.write_text(content, encoding="utf-8")
    print(f"scritto {SPRINT.relative_to(ROOT)} ({content.count(chr(10))} righe)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
