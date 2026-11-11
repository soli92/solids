#!/usr/bin/env python3
"""id_registry_check.py — presidio eseguibile del registro dei namespace kanban.

Verifica tre invarianti per ogni namespace dichiarato in
`management/kanban/id-registry.yaml`:

  1. COLLISIONE ATTIVA — nessun ID deve esistere in >1 file/cartella con almeno
     uno degli artefatti in stato aperto. I duplicati tutti-chiusi (done/wontfix/…)
     sono storici benigni → solo INFO.

  2. REGISTRY STALE — le prenotazioni dichiarate nel registro devono coprire il
     massimo ID realmente presente sul filesystem. Un registro stale causa la
     prossima collisione.

  3. RANGE SOVRAPPOSTI — due prenotazioni per lo stesso namespace+kind non devono
     coprire range sovrapposti.

  4. PREFISSO NON REGISTRATO — un namespace trovato sul filesystem non dichiarato
     nel registro (WARNING, non errore: factory master non usa prefissi).

  5. PRENOTAZIONE IN CONFLITTO — un US dichiarato nella tabella di un'epica (prima cella
     di una riga, anche prima che la cartella esista) non deve essere materializzato sotto
     un'epica diversa. Il glob sul filesystem non vede le prenotazioni: e' il buco da cui
     e' passata una collisione reale su una derivata (registry allineato, un solo file).
     `us_range:` non si espande: e' una sintesi che puo' sovra-dichiarare.

Forma degli ID e delle cartelle (con o senza prefisso, con o senza slug): da
`tools/coordinamento/kanban_ids.py`, come gli altri strumenti del kanban.

Generalizzato dalla factory derivata portale-servizi-factory (EP-069 US-314).
Stdlib + PyYAML (gia' presente in M). Zero mutation, zero git, zero rete.

USO:
  python3 tools/kanban/id_registry_check.py            # report
  python3 tools/kanban/id_registry_check.py --check     # exit 1 su collisione attiva o stale
  python3 tools/kanban/id_registry_check.py --markdown  # report in markdown

Se il registro non esiste → exit 0 con messaggio esplicito (fail-open).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

FACTORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FACTORY_ROOT / "tools" / "coordinamento"))
import kanban_ids  # noqa: E402
KANBAN = FACTORY_ROOT / "management" / "kanban"
REGISTRY = KANBAN / "id-registry.yaml"


def _registry_path(root: Path) -> Path:
    """`kanban_namespaces.registry` di factory.config.yaml se il file esiste; poi i due nomi in uso
    (`id-registry.yaml` del master, `tsk-id-registry.yaml` di una derivata). Un registro che c'e'
    ma ha un altro nome non deve dare «registro assente → OK»."""
    kanban = root / "management" / "kanban"
    cfg = root / "factory.config.yaml"
    if cfg.is_file():
        m = re.search(r"^kanban_namespaces:[^\n]*\n(?:[ \t]+[^\n]*\n|[ \t]*\n)*?[ \t]+registry:\s*[\"']?([^\s\"'#]+)",
                      cfg.read_text(encoding="utf-8"), re.M)
        if m and (root / m.group(1)).is_file():
            return root / m.group(1)
    for nome in ("id-registry.yaml", "tsk-id-registry.yaml"):
        if (kanban / nome).is_file():
            return kanban / nome
    return kanban / "id-registry.yaml"


def _imposta_radice(root: Path) -> None:
    global FACTORY_ROOT, KANBAN, REGISTRY
    FACTORY_ROOT = root.resolve()
    KANBAN = FACTORY_ROOT / "management" / "kanban"
    REGISTRY = _registry_path(FACTORY_ROOT)


_NS_CHIAVE = re.compile(r"^([A-Z]{2,4})-(EP|US|TSK)$")
REGISTRY = _registry_path(FACTORY_ROOT)

OPEN_STATUSES = {"todo", "in_progress", "in-progress", "review", "blocked",
                 "wip", "doing", "ready", "open"}

def _load_registry() -> dict:
    """Carica il registro YAML. Ritorna {} se assente (fail-open)."""
    if not REGISTRY.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"# WARN: impossibile leggere il registro: {exc}", file=sys.stderr)
        return {}


def _status_of(md_path: Path) -> str:
    try:
        for line in md_path.read_text(encoding="utf-8").splitlines()[:40]:
            m = re.match(r"^status:\s*([A-Za-z_-]+)", line.strip())
            if m:
                return m.group(1).lower()
    except Exception:
        pass
    return ""


def _chiave(ident: str) -> Tuple[str, str, int]:
    """('XX' o '', tipo, numero) di un ID del kanban."""
    return (kanban_ids.prefisso_di(ident) or "", kanban_ids.tipo_di(ident), int(ident.rsplit("-", 1)[1]))


def _cartella(path: Path, tipo: str):
    """ID della cartella se comincia con un ID del tipo richiesto (con o senza slug)."""
    ident, t = kanban_ids.id_cartella(path.name)
    return ident if t == tipo else None


def collect() -> Dict[Tuple[str, str, int], List[Path]]:
    """Mappa (prefix_or_'', type, id) -> lista di path. Cartelle con o senza slug."""
    index: Dict[Tuple[str, str, int], List[Path]] = defaultdict(list)
    for ep_dir in KANBAN.glob("*"):
        ep = _cartella(ep_dir, "EP") if ep_dir.is_dir() else None
        if not ep:
            continue
        md = ep_dir / f"{ep}.md"
        index[_chiave(ep)].append(md if md.exists() else ep_dir)
        for us_dir in ep_dir.iterdir():
            us = _cartella(us_dir, "US") if us_dir.is_dir() else None
            if not us:
                continue
            md_us = us_dir / f"{us}.md"
            index[_chiave(us)].append(md_us if md_us.exists() else us_dir)
            for tsk in us_dir.glob("*.md"):
                if kanban_ids.tipo_di(tsk.stem) == "TSK":
                    index[_chiave(tsk.stem)].append(tsk)
    return index


def collect_declared() -> Dict[Tuple[str, str, int], List[str]]:
    """(prefix, 'US', n) -> epiche che dichiarano quell'US nella propria tabella.

    Vale solo la prima cella di una riga di tabella con un solo ID: e' li' che un'epica
    elenca le sue storie. `us_range:` non si espande (puo' sovra-dichiarare).
    """
    declared: Dict[Tuple[str, str, int], List[str]] = defaultdict(list)
    for ep_dir in KANBAN.glob("*"):
        ep = _cartella(ep_dir, "EP") if ep_dir.is_dir() else None
        md = ep_dir / f"{ep}.md" if ep else None
        if not md or not md.is_file():
            continue
        found = set()
        for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("|") or line.count("|") < 2:
                continue
            ids = kanban_ids.ID_IN_TESTO.findall(line.split("|")[1])
            if len(ids) == 1 and kanban_ids.tipo_di(ids[0]) == "US":
                found.add(_chiave(ids[0]))
        for key in found:
            declared[key].append(ep)
    return declared


def analyze(reg: dict, index: Dict[Tuple[str, str, int], List[Path]],
            declared: Dict[Tuple[str, str, int], List[str]] | None = None):
    grezzi = reg.get("namespaces") or []
    allocati: Dict[Tuple[str, str], int] = {}
    if isinstance(grezzi, dict):
        # forma a mappa (derivata): «UP-TSK: {last_allocated: N, ...}» — un namespace per prefisso e tipo
        namespaces = {}
        for chiave, val in grezzi.items():
            m = _NS_CHIAVE.match(str(chiave))
            if not m:
                continue
            namespaces[m.group(1)] = val or {}
            try:
                allocati[(m.group(1), m.group(2))] = int((val or {}).get("last_allocated"))
            except (TypeError, ValueError):
                pass
    else:
        namespaces = {n.get("prefix", ""): n for n in grezzi}
    reservations = reg.get("reservations") or []
    declared = declared or {}

    # Collisioni
    active_collisions: List[dict] = []
    benign_collisions: List[dict] = []
    fs_max: Dict[Tuple[str, str], int] = {}

    for (prefix, typ, num), paths in index.items():
        key = (prefix, typ)
        fs_max[key] = max(fs_max.get(key, 0), num)
        if len(paths) > 1:
            statuses = [_status_of(p) if p.is_file() else "" for p in paths]
            active = any(s in OPEN_STATUSES or s == "" for s in statuses)
            rec = {
                "id": f"{prefix+'-' if prefix else ''}{typ}-{num}",
                "paths": [str(p.relative_to(KANBAN)) for p in paths],
                "statuses": statuses,
            }
            (active_collisions if active else benign_collisions).append(rec)

    # Registry stale: il massimo `to` per ogni prefix+kind deve coprire il max reale.
    # Si considera stale solo se l'intero insieme delle prenotazioni non copre il max
    # filesystem: un ID in un secondo range e' coperto, non stale.
    from collections import defaultdict as _dd
    max_to_by_ns: Dict[Tuple[str, str], int] = {}
    for res in reservations:
        prefix = res.get("prefix", "")
        kind = res.get("kind", "").upper()
        key = (prefix, kind)
        max_to_by_ns[key] = max(max_to_by_ns.get(key, 0), int(res.get("to", 0)))

    stale: List[dict] = []
    for (prefix, kind), dichiarato in sorted(allocati.items()):
        # forma a mappa: `last_allocated` deve coprire il massimo reale
        if fs_max.get((prefix, kind), 0) > dichiarato and (prefix, kind) not in max_to_by_ns:
            stale.append({"namespace": f"{prefix}-{kind}", "declared_to": dichiarato,
                          "filesystem_max": fs_max[(prefix, kind)]})
    for (prefix, kind), max_to in max_to_by_ns.items():
        actual_max = fs_max.get((prefix, kind), 0)
        if actual_max > max_to:
            stale.append({
                "namespace": f"{prefix+'-' if prefix else ''}{kind}",
                "declared_to": max_to,
                "filesystem_max": actual_max,
            })

    # Range sovrapposti per stesso prefix+kind
    overlapping: List[dict] = []
    by_ns: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for res in reservations:
        by_ns[(res.get("prefix", ""), res.get("kind", "").upper())].append(res)
    for (prefix, kind), ress in by_ns.items():
        ress_sorted = sorted(ress, key=lambda r: int(r.get("from", 0)))
        for i in range(len(ress_sorted) - 1):
            a, b = ress_sorted[i], ress_sorted[i + 1]
            if int(a.get("to", 0)) >= int(b.get("from", 0)):
                overlapping.append({
                    "namespace": f"{prefix+'-' if prefix else ''}{kind}",
                    "a": f"{a.get('epic','?')} [{a.get('from')}-{a.get('to')}]",
                    "b": f"{b.get('epic','?')} [{b.get('from')}-{b.get('to')}]",
                })

    # Prenotazioni in conflitto: US dichiarato da un'epica, materializzato sotto un'altra
    reserved_conflicts: List[dict] = []
    for (prefix, typ, num), epics in sorted(declared.items()):
        owners = set()
        for path in index.get((prefix, typ, num), []):
            for part in path.relative_to(KANBAN).parts:
                ident = _cartella(Path(part), "EP")
                if ident:
                    owners.add(ident)
        foreign = sorted(owners - set(epics))
        if foreign:
            reserved_conflicts.append({
                "id": f"{prefix+'-' if prefix else ''}{typ}-{num}",
                "declared_by": sorted(set(epics)),
                "materialized_in": foreign,
            })

    # Prefissi non registrati (WARNING)
    registered_prefixes = set(namespaces.keys())
    fs_prefixes = {prefix for (prefix, _) in fs_max if prefix}
    missing_ns = sorted(fs_prefixes - registered_prefixes)

    return {
        "active_collisions": sorted(active_collisions, key=lambda r: r["id"]),
        "benign_collisions": sorted(benign_collisions, key=lambda r: r["id"]),
        "stale": stale,
        "overlapping": overlapping,
        "missing_ns": missing_ns,
        "reserved_conflicts": reserved_conflicts,
    }


def _report(res: dict, markdown: bool) -> str:
    L: List[str] = []
    h = (lambda s: f"## {s}") if markdown else (lambda s: s)
    L.append(h("id-registry-check — presidio unicita' ID kanban (EP/US/TSK)"))
    L.append("")

    ac = res["active_collisions"]
    L.append(f"!! COLLISIONI ATTIVE ({len(ac)}) — ID duplicato con almeno un artefatto aperto:")
    for r in ac:
        L.append(f"  {r['id']}  [{', '.join(r['statuses']) or '?'}]")
        for p in r["paths"]:
            L.append(f"      {p}")
    if not ac:
        L.append("  (nessuna)")
    L.append("")

    st = res["stale"]
    L.append(f"!! REGISTRY STALE ({len(st)}) — prenotazione scaduta (rischio collisione):")
    for r in st:
        L.append(f"  {r['namespace']}: max_prenotato={r['declared_to']} < max_reale={r['filesystem_max']}")
    if not st:
        L.append("  (nessuno)")
    L.append("")

    ov = res["overlapping"]
    L.append(f"!! RANGE SOVRAPPOSTI ({len(ov)}) — due prenotazioni si intersecano:")
    for r in ov:
        L.append(f"  {r['namespace']}  {r['a']}  <->  {r['b']}")
    if not ov:
        L.append("  (nessuno)")
    L.append("")

    rc = res.get("reserved_conflicts", [])
    L.append(f"!! PRENOTAZIONI IN CONFLITTO ({len(rc)}) — US dichiarato da un'epica e materializzato sotto un'altra:")
    for r in rc:
        L.append(f"  {r['id']}  dichiarato da {', '.join(r['declared_by'])}  ->  in {', '.join(r['materialized_in'])}")
    if not rc:
        L.append("  (nessuna)")
    L.append("")

    bc = res["benign_collisions"]
    L.append(f"?  duplicati storici benigni ({len(bc)}) — tutti chiusi, non rinumerati:")
    for r in bc[:20]:
        L.append(f"  {r['id']}  [{', '.join(r['statuses'])}]")
    if len(bc) > 20:
        L.append(f"  … e altri {len(bc) - 20}")
    if not bc:
        L.append("  (nessuno)")
    L.append("")

    if res["missing_ns"]:
        L.append(f"?  prefissi sul filesystem non dichiarati nel registro: {', '.join(res['missing_ns'])}")
        L.append("")

    ok = not ac and not st and not ov and not rc
    L.append("check: OK — nessuna collisione attiva, range sovrapposto, prenotazione in conflitto o registry stale."
             if ok else
             "check: FAIL — vedi COLLISIONI ATTIVE / REGISTRY STALE / RANGE SOVRAPPOSTI / PRENOTAZIONI IN CONFLITTO sopra.")
    return "\n".join(L)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Presidio unicita' ID kanban con namespace.")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 su collisione attiva, registry stale o range sovrapposto.")
    parser.add_argument("--markdown", action="store_true", help="Output in markdown.")
    parser.add_argument("--root", help="radice della factory (default: quella dello script)")
    args = parser.parse_args(argv)
    if args.root:
        _imposta_radice(Path(args.root))

    reg = _load_registry()
    if not reg and not REGISTRY.exists():
        print("id-registry-check: registro assente "
              f"({REGISTRY.relative_to(FACTORY_ROOT)}) — nessun namespace da controllare. "
              "OK (exit 0).")
        return 0

    index = collect()
    res = analyze(reg, index, collect_declared())
    print(_report(res, args.markdown))

    failed = (bool(res["active_collisions"]) or bool(res["stale"]) or bool(res["overlapping"])
              or bool(res.get("reserved_conflicts")))
    if args.check:
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
