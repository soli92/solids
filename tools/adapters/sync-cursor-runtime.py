#!/usr/bin/env python3
"""Sync Cursor runtime (.cursor/) from meta-framework adapter templates.

Templates live in ``adapters/cursor/templates/{commands,rules}/`` in the meta clone.
Runtime paths mirror that layout under ``<factory>/.cursor/``.

Default: non-destructive (COPY missing, SKIP identical, CONFLICT if customized).
``--overwrite-changed``: refresh files that differ from canonical templates (with backup).

Also ``--ensure-adapter``: append ``cursor`` to ``factory.config.yaml.adapters[]`` if absent.
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

README = "README.md"
CURSOR_ADAPTER_ENTRY = """  - name: cursor
    folder: .cursor
    maturity: core
"""


def _template_root(meta_source: Path) -> Path:
    root = meta_source / "adapters/cursor/templates"
    if not root.is_dir():
        raise SystemExit(f"Missing Cursor templates: {root}")
    return root


def _iter_template_files(template_root: Path) -> list[tuple[Path, Path]]:
    """Return (src_file, rel_under_.cursor) for each scaffold file."""
    out: list[tuple[Path, Path]] = []
    for src in sorted(template_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(template_root)
        if rel.name == README and rel.parent == Path("."):
            continue
        out.append((src, rel))
    return out


def ensure_cursor_adapter(factory_path: Path, dry_run: bool) -> bool:
    cfg = factory_path / "factory.config.yaml"
    if not cfg.is_file():
        raise SystemExit(f"Not a factory: {cfg}")
    text = cfg.read_text(encoding="utf-8")
    if re.search(r"^\s*-\s*name:\s*cursor\s*$", text, re.M):
        return False
    if "adapters:" not in text:
        addition = "\nadapters:\n" + CURSOR_ADAPTER_ENTRY
        new_text = text.rstrip("\n") + addition + "\n"
    else:
        lines = text.splitlines(keepends=True)
        insert_at = len(lines)
        in_adapters = False
        for i, line in enumerate(lines):
            if line.startswith("adapters:"):
                in_adapters = True
                continue
            if in_adapters and line and not line[0].isspace() and not line.lstrip().startswith("#"):
                insert_at = i
                break
        block = [CURSOR_ADAPTER_ENTRY if CURSOR_ADAPTER_ENTRY.endswith("\n") else CURSOR_ADAPTER_ENTRY + "\n"]
        new_text = "".join(lines[:insert_at] + block + lines[insert_at:])
    if dry_run:
        print("[DRY-RUN] would append cursor to factory.config.yaml adapters[]")
        return True
    cfg.write_text(new_text, encoding="utf-8")
    return True


def sync_cursor_runtime(
    factory_path: Path,
    meta_source: Path,
    dry_run: bool = False,
    overwrite_changed: bool = False,
) -> dict:
    template_root = _template_root(meta_source)
    cursor_root = factory_path / ".cursor"
    stats = {
        "copy": 0,
        "skip_identical": 0,
        "overwrite": 0,
        "conflict": 0,
        "conflict_paths": [],
        "copy_paths": [],
        "overwrite_paths": [],
    }

    backup_dir: Path | None = None
    if overwrite_changed and not dry_run:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        backup_dir = factory_path / ".factory-upgrade-backup" / f"cursor-sync-{ts}"
        backup_dir.mkdir(parents=True, exist_ok=True)

    for src, rel in _iter_template_files(template_root):
        dest = cursor_root / rel
        if dest.exists() and _files_identical(src, dest):
            stats["skip_identical"] += 1
            continue
        if not dest.exists():
            stats["copy"] += 1
            stats["copy_paths"].append(str(rel))
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            continue
        if overwrite_changed:
            stats["overwrite"] += 1
            stats["overwrite_paths"].append(str(rel))
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if backup_dir:
                    b = backup_dir / str(rel).replace("/", "__")
                    b.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, b)
                shutil.copy2(src, dest)
            continue
        stats["conflict"] += 1
        stats["conflict_paths"].append(str(rel))

    return stats


def _files_identical(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and filecmp.cmp(a, b, shallow=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("factory_path", type=Path)
    p.add_argument("--meta-source", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--overwrite-changed",
        action="store_true",
        help="replace .cursor files that differ from templates (backup under .factory-upgrade-backup/)",
    )
    p.add_argument(
        "--ensure-adapter",
        action="store_true",
        help="append cursor to factory.config.yaml adapters[] if missing",
    )
    args = p.parse_args()
    factory = args.factory_path.resolve()
    meta = args.meta_source.resolve()

    if args.ensure_adapter:
        ensure_cursor_adapter(factory, args.dry_run)

    stats = sync_cursor_runtime(factory, meta, args.dry_run, args.overwrite_changed)
    print("=" * 60)
    print(f"{'DRY-RUN ' if args.dry_run else ''}CURSOR RUNTIME SYNC")
    print(f"Factory: {factory}")
    print(f"Templates: {meta / 'adapters/cursor/templates'}")
    print(
        f"COPY {stats['copy']}  OVERWRITE {stats['overwrite']}  "
        f"SKIP(identical) {stats['skip_identical']}  CONFLICT {stats['conflict']}"
    )
    if stats["copy_paths"]:
        print("COPY:", *stats["copy_paths"][:20], sep="\n  ")
        if len(stats["copy_paths"]) > 20:
            print(f"  ... +{len(stats['copy_paths']) - 20} more")
    if stats["overwrite_paths"]:
        print("OVERWRITE:", *stats["overwrite_paths"][:20], sep="\n  ")
    if stats["conflict_paths"]:
        print("CONFLICT (customized — merge manually or re-run with --overwrite-changed):")
        print(*stats["conflict_paths"][:25], sep="\n  ")
    print("=" * 60)
    if stats["conflict"] and not args.overwrite_changed:
        sys.exit(2)


if __name__ == "__main__":
    main()
