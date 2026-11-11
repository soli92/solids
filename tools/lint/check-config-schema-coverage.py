#!/usr/bin/env python3
"""
check-config-schema-coverage.py — Copertura schema vs config (TSK-729).

Confronta le chiavi top-level di factory.config.yaml con le properties dichiarate
in schemas/factory.config.schema.json:

  - UNDECLARED: chiave presente in config ma assente nello schema → exit 1, ERROR
  - INFO:       chiave nello schema ma assente dalla config → solo informativa, mai errore

Legge YAML con regex (stesso approccio di check-version-coherence.py, stdlib only).
Legge lo schema con json (stdlib).

Uso:
  python3 tools/lint/check-config-schema-coverage.py
  python3 tools/lint/check-config-schema-coverage.py --json
  python3 tools/lint/check-config-schema-coverage.py --root /path/to/factory
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _find_root(start: Path) -> Path:
    """Risale l'albero fino a factory.config.yaml; fallback: cwd."""
    for parent in [start, *start.parents]:
        if (parent / "factory.config.yaml").exists():
            return parent
    return start


def _config_top_keys(root: Path) -> list[str]:
    """Estrae le chiavi top-level da factory.config.yaml via regex.

    Strategia: una chiave top-level e' una riga che inizia con un identificatore
    immediatamente seguito da ':', senza indentazione. Le righe di commento
    (che iniziano con #) e le righe vuote sono ignorate. I separatori ---
    non introducono chiavi.
    """
    cfg_path = root / "factory.config.yaml"
    if not cfg_path.exists():
        return []
    text = cfg_path.read_text(encoding="utf-8")
    # Matchare solo chiavi top-level (nessuno spazio iniziale, seguite da ':')
    keys: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"^([a-zA-Z_][a-zA-Z0-9_]*):", text, re.MULTILINE):
        k = m.group(1)
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def _schema_properties(root: Path) -> set[str]:
    """Restituisce le chiavi in schema.properties."""
    schema_path = root / "schemas" / "factory.config.schema.json"
    if not schema_path.exists():
        return set()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return set(schema.get("properties", {}).keys())


def _local_keys(root: Path) -> set[str]:
    """`schema_local_keys:` della config (lista inline o a blocco): chiavi proprie della factory."""
    cfg_path = root / "factory.config.yaml"
    if not cfg_path.exists():
        return set()
    text = cfg_path.read_text(encoding="utf-8")
    m = re.search(r"^schema_local_keys:[ \t]*\[([^\]]*)\]", text, re.M)
    if m:
        return {k.strip().strip("\"'") for k in m.group(1).split(",") if k.strip()}
    m = re.search(r"^schema_local_keys:[ \t]*\n((?:[ \t]+-[^\n]*\n?)*)", text, re.M)
    if m:
        return {l.split("-", 1)[1].split("#")[0].strip().strip("\"'")
                for l in m.group(1).splitlines() if l.strip().startswith("-")}
    return set()


def run(root: Path) -> dict:
    """Esegue il check; restituisce un dict con i risultati."""
    config_keys = _config_top_keys(root)
    schema_keys = _schema_properties(root)
    local = _local_keys(root)

    declared_local = [k for k in config_keys if k not in schema_keys and k in local]
    undeclared = [k for k in config_keys if k not in schema_keys and k not in local]
    schema_only = sorted(schema_keys - set(config_keys))

    return {
        "config_keys": sorted(config_keys),
        "schema_keys": sorted(schema_keys),
        "undeclared": undeclared,
        "declared_local": declared_local,
        "schema_only": schema_only,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verifica copertura schema vs factory.config.yaml"
    )
    ap.add_argument(
        "--json", action="store_true", dest="json_out", help="Output JSON machine-readable"
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Root della factory (default: directory del file o del chiamante)",
    )
    args = ap.parse_args()

    root = args.root if args.root else _find_root(Path(__file__).resolve().parent)
    result = run(root)

    undeclared = result["undeclared"]
    schema_only = result["schema_only"]

    if args.json_out:
        out = {
            "undeclared": undeclared,
            "declared_local": result["declared_local"],
            "schema_only": schema_only,
            "exit_code": 1 if undeclared else 0,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if undeclared:
            print(f"ERROR — {len(undeclared)} chiave/i top-level in config ma non nello schema:")
            for k in undeclared:
                print(f"  UNDECLARED  {k}")
        else:
            print("OK — tutte le chiavi top-level di factory.config.yaml sono nello schema.")

        if result["declared_local"]:
            print(f"\nINFO — {len(result['declared_local'])} chiave/i locali dichiarate in schema_local_keys:")
            for k in result["declared_local"]:
                print(f"  locale  {k}")

        if schema_only:
            print(f"\nINFO — {len(schema_only)} chiave/i nello schema ma non nella config (normale):")
            for k in schema_only:
                print(f"  schema-only  {k}")

    return 1 if undeclared else 0


if __name__ == "__main__":
    sys.exit(main())
