#!/usr/bin/env python3
"""namespace_orphans.py — indice inverso per code_path dei task kanban (presidio C-004).

Problema che risolve
--------------------
La convenzione C-004 mappa un prefisso namespace su un solo code_path. Le epiche di
migrazione tra repo (eccezione C-004.1) violano quella mappatura per costruzione: i loro
task vivono nella sorgente, nel target, nei consumer e nella factory.

Conseguenza: un task aperto su un repo puo' stare sotto un prefisso estraneo ed essere
invisibile a chi guarda la board di quel repo.

Uso
---
    python3 tools/kanban/namespace_orphans.py              # report leggibile
    python3 tools/kanban/namespace_orphans.py --markdown   # sezione per sprint.md
    python3 tools/kanban/namespace_orphans.py --check      # exit 1 se ci sono violazioni C-004

Se il registro e' assente o non ha namespace dichiarati → exit 0 con messaggio esplicito.

Generalizzato dalla factory derivata portale-servizi-factory (EP-069 US-314).
Stdlib + PyYAML (gia' presente in M). Zero mutation, zero git, zero rete.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
KANBAN = ROOT / "management" / "kanban"
REGISTRY = KANBAN / "id-registry.yaml"

OPEN_STATES = {"todo", "in_progress", "in-progress", "blocked", "review",
               "wip", "doing", "ready", "open"}

TYPE_ALIASES = {
    "epic": {"epic"},
    "story": {"user-story", "story", "us", "user_story"},
    "task": {"task"},
}


def _load_namespace_by_path() -> dict[str, str]:
    """Legge prefix->code_path dal registro. Ritorna {} se registro assente o vuoto."""
    if not REGISTRY.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    ns_list = data.get("namespaces") or []
    # mappa code_path -> prefix (per l'indice inverso)
    return {n["code_path"]: n["prefix"] for n in ns_list
            if n.get("code_path") and n.get("prefix")}


def frontmatter(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if mm:
            out[mm.group(1)] = mm.group(2).strip().strip('"')
    return out


def collect() -> list[dict[str, str]]:
    items = []
    for glob, kind in (("*-EP-*.md", "epic"), ("*-US-*.md", "story"), ("*-TSK-*.md", "task")):
        for path in KANBAN.rglob(glob):
            d = frontmatter(path)
            if d.get("type") not in TYPE_ALIASES[kind] or "id" not in d:
                continue
            d["_kind"] = kind
            d["_path"] = str(path.relative_to(ROOT))
            items.append(d)
    return items


def migration_epics() -> set[str]:
    out = set()
    for path in KANBAN.rglob("*-EP-*.md"):
        d = frontmatter(path)
        if d.get("type") == "epic" and d.get("migration_epic", "").lower() == "true":
            out.add(d.get("id", ""))
    return out


def orphans(
    tasks: list[dict[str, str]],
    namespace_by_path: dict[str, str],
) -> tuple[dict, dict]:
    """Artefatti aperti il cui code_path appartiene a un namespace diverso dal loro prefisso."""
    mig = migration_epics()
    giustificati: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    violazioni: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for t in tasks:
        if t.get("status") not in OPEN_STATES:
            continue
        code_path = t.get("code_path", "")
        expected_prefix = namespace_by_path.get(code_path)
        if not expected_prefix:
            continue  # code_path non mappato nel registro: nessuna board da presidiare
        # Estrai il prefisso dell'ID dell'artefatto (es. "UP" da "UP-TSK-042")
        id_str = t.get("id", "")
        m = re.match(r"^([A-Z]{2,4})-(?:EP|US|TSK)-\d+$", id_str)
        actual_prefix = (m.group(1) if m else None)
        if actual_prefix is None:
            # ID senza prefisso (namespace unico factory master): non e' un orfano
            continue
        if actual_prefix == expected_prefix:
            continue
        bucket = giustificati if t.get("epic") in mig else violazioni
        bucket[code_path].append(t)
    for m_dict in (giustificati, violazioni):
        for v in m_dict.values():
            v.sort(key=lambda t: (t["_kind"] != "epic", t["_kind"] != "story", t["id"]))
    return dict(sorted(giustificati.items())), dict(sorted(violazioni.items()))


def _table(items: list[dict[str, str]]) -> list[str]:
    rows = ["| Artefatto | Livello | Epica | Consumer | Stato | Titolo |",
            "|---|---|---|---|---|---|"]
    for t in items:
        title = t.get("title", "").replace("|", "\\|")[:80]
        rows.append(
            f"| `{t['id']}` | {t['_kind']} | {t.get('epic','')} | {t.get('consumer','')} "
            f"| {t.get('status','')} | {title} |"
        )
    return rows


def render_markdown(giustificati: dict, violazioni: dict,
                    namespace_by_path: dict[str, str]) -> str:
    lines = [
        "## Indice inverso per code_path — task sotto prefisso estraneo",
        "",
        "> Generato da `tools/kanban/namespace_orphans.py`. **Non editare a mano.**",
        "> Rigenera con: `python3 tools/kanban/namespace_orphans.py --markdown`",
        "",
    ]
    lines += ["### Giustificati da C-004.1 (epiche di migrazione) — da indicizzare", ""]
    if not giustificati:
        lines += ["Nessuno.", ""]
    for code_path, items in giustificati.items():
        exp = namespace_by_path.get(code_path, "?")
        lines += [f"**`{code_path}`** — namespace proprio `{exp}-`", ""]
        lines += _table(items) + [""]
    lines += ["### Violazioni C-004 — epiche ordinarie, da sanare", ""]
    if not violazioni:
        lines += ["Nessuna.", ""]
    for code_path, items in violazioni.items():
        exp = namespace_by_path.get(code_path, "?")
        lines += [f"**`{code_path}`** — namespace proprio `{exp}-`", ""]
        lines += _table(items) + [""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--markdown", action="store_true",
                    help="Emette la sezione markdown per sprint.md")
    ap.add_argument("--check", action="store_true",
                    help="Exit 1 se esistono VIOLAZIONI C-004")
    args = ap.parse_args(argv)

    namespace_by_path = _load_namespace_by_path()
    if not namespace_by_path:
        print("namespace_orphans: registro assente o nessun namespace dichiarato — "
              "nessun indice inverso da calcolare. OK (exit 0).")
        return 0

    giustificati, violazioni = orphans(collect(), namespace_by_path)

    if args.markdown:
        print(render_markdown(giustificati, violazioni, namespace_by_path), end="")
        return 0

    n_g = sum(len(v) for v in giustificati.values())
    n_v = sum(len(v) for v in violazioni.values())

    def dump(title: str, m: dict) -> None:
        print(title)
        if not m:
            print("  (nessuno)\n")
            return
        for code_path, items in m.items():
            exp = namespace_by_path.get(code_path, "?")
            print(f"  {code_path}  (namespace proprio: {exp}-)")
            for t in items:
                print(f"    {t['id']:<16} {t['_kind']:<7} {t.get('status',''):<12} "
                      f"{t.get('consumer',''):<7} {t.get('title','')[:50]}")
            print()

    dump(f"GIUSTIFICATI C-004.1 (da indicizzare): {n_g}", giustificati)
    dump(f"VIOLAZIONI C-004 (da sanare): {n_v}", violazioni)

    if args.check and n_v:
        print(f"check: FAIL — {n_v} violazioni C-004 su epiche ordinarie.")
        return 1
    if args.check:
        print("check: OK — nessuna violazione C-004.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
