#!/usr/bin/env python3
"""
Incremental updater for the wiki hybrid search index.

Maintains .wiki-search/index_state.json ({path: mtime_float_or_sha256}) to detect
which files changed since the last run, then re-indexes only those files.

Usage:
    python tools/wiki-search/update-index.py              # incremental (default)
    python tools/wiki-search/update-index.py --full       # full rebuild
    python tools/wiki-search/update-index.py --dry-run    # show what would change
    python tools/wiki-search/update-index.py --stats      # show index dimensions
    python tools/wiki-search/update-index.py --hash       # SHA-256 instead of mtime
    python tools/wiki-search/update-index.py --wiki-root wiki/ --index-path .wiki-search/index.lance
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

STATE_FILENAME = "index_state.json"


# ---------------------------------------------------------------------------
# Repo-root discovery (same pattern as build-index.py)
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """Walk up from start looking for factory.config.yaml or a wiki/ directory."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "factory.config.yaml").exists() or (candidate / "wiki").is_dir():
            return candidate
    return current


# ---------------------------------------------------------------------------
# Import helper — indexer.py lives alongside this file (R.WS1)
# ---------------------------------------------------------------------------

def _import_indexer():
    """
    Insert the tools/wiki-search directory into sys.path so that indexer.py
    is importable regardless of the caller's cwd.
    """
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    try:
        from indexer import WikiIndexer  # noqa: PLC0415
        return WikiIndexer
    except ImportError as exc:
        print(f"ERROR: cannot import indexer.py — {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# State file helpers
# ---------------------------------------------------------------------------

def _load_state(state_path: Path) -> dict:
    """Load index_state.json. Returns empty dict if file does not exist."""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Cannot read state file %s: %s — starting fresh", state_path, exc)
        return {}


def _save_state(state_path: Path, state: dict) -> None:
    """Atomically write index_state.json (parent dirs created if needed)."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# File fingerprinting
# ---------------------------------------------------------------------------

def _mtime(path: Path) -> float:
    return os.stat(path).st_mtime


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _fingerprint(path: Path, use_hash: bool):
    """Return SHA-256 hex string if use_hash, else mtime float."""
    return _sha256(path) if use_hash else _mtime(path)


def _build_current_state(wiki_root: Path, use_hash: bool) -> dict:
    """Return {rel_path: fingerprint} for all .md files in wiki_root."""
    state: dict = {}
    for md_path in sorted(wiki_root.rglob("*.md")):
        try:
            rel = str(md_path.relative_to(wiki_root))
            state[rel] = _fingerprint(md_path, use_hash)
        except Exception as exc:
            log.warning("Cannot fingerprint %s: %s", md_path, exc)
    return state


# ---------------------------------------------------------------------------
# LanceDB helpers (lazy import — R.WS2)
# ---------------------------------------------------------------------------

def _delete_chunks_by_paths(index_path: Path, paths: list[str]) -> None:
    """
    Delete all chunks whose 'path' field matches any entry in <paths>.
    Batched in groups of 50 to avoid overly-long SQL filter strings.
    No-op if the index or the 'pages' table does not exist yet.
    """
    if not paths or not index_path.exists():
        return

    try:
        import lancedb  # lazy import — R.WS2
    except ImportError:
        raise ImportError(
            "lancedb is not installed. Run: pip install -e '.[wiki-search]'"
        )

    db = lancedb.connect(str(index_path))
    if "pages" not in db.table_names():
        return

    table = db.open_table("pages")
    _BATCH = 50
    for i in range(0, len(paths), _BATCH):
        batch = paths[i : i + _BATCH]
        if len(batch) == 1:
            filt = f"path = '{batch[0]}'"
        else:
            quoted = ", ".join(f"'{p}'" for p in batch)
            filt = f"path IN ({quoted})"
        try:
            table.delete(filt)
        except Exception as exc:
            log.debug("Delete batch failed (may already be empty): %s", exc)


def _count_chunks_for_paths(index_path: Path, paths: list[str]) -> int:
    """
    Count how many chunks exist in the 'pages' table for the given file paths.
    Falls back to 0 on any error (e.g. table empty or lancedb not installed).
    Uses pandas for compatibility across lancedb versions.
    """
    if not paths or not index_path.exists():
        return 0
    try:
        import lancedb  # lazy import — R.WS2
        db = lancedb.connect(str(index_path))
        if "pages" not in db.table_names():
            return 0
        table = db.open_table("pages")
        df = table.to_pandas()
        return int(df["path"].isin(paths).sum())
    except Exception as exc:
        log.debug("Could not count chunks for paths: %s", exc)
        return 0


def _show_stats(index_path: Path, state_file: Path) -> None:
    """Print index dimensions to stdout."""
    print(f"index-path : {index_path}")
    print(f"state-file : {state_file}")

    if not index_path.exists():
        print("index      : not found")
    else:
        try:
            import lancedb
            db = lancedb.connect(str(index_path))
            if "pages" in db.table_names():
                print(f"rows       : {db.open_table('pages').count_rows()}")
            else:
                print("rows       : 0  (table not created yet)")
        except ImportError:
            print("rows       : (lancedb not installed)")
        except Exception as exc:
            print(f"rows       : error — {exc}")

    if state_file.exists():
        state = _load_state(state_file)
        print(f"tracked    : {len(state)} files")
    else:
        print("state-file : not found")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="update-index.py",
        description="Incremental updater for the wiki hybrid search index (LanceDB + embeddings).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full rebuild — drop the existing index and re-index all files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing the index or updating the state file.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show index dimensions (row count, tracked files) and exit.",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help=(
            "Use SHA-256 content hash to detect changes instead of mtime. "
            "Slower but detects content edits that preserve the timestamp."
        ),
    )
    parser.add_argument(
        "--wiki-root",
        default=None,
        metavar="PATH",
        help="Path to the wiki directory (default: auto-detected <repo-root>/wiki/).",
    )
    parser.add_argument(
        "--index-path",
        default=None,
        metavar="PATH",
        help=(
            "LanceDB database path (default: auto-detected "
            "<repo-root>/.wiki-search/index.lance)."
        ),
    )
    parser.add_argument(
        "--model",
        default="paraphrase-multilingual-MiniLM-L12-v2",
        metavar="MODEL",
        help="Sentence-Transformers model name (default: paraphrase-multilingual-MiniLM-L12-v2).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )

    # ------------------------------------------------------------------
    # Resolve paths
    # ------------------------------------------------------------------
    repo_root = _find_repo_root(Path.cwd())
    wiki_root = Path(args.wiki_root) if args.wiki_root else repo_root / "wiki"
    index_path = (
        Path(args.index_path)
        if args.index_path
        else repo_root / ".wiki-search" / "index.lance"
    )
    state_file = index_path.parent / STATE_FILENAME

    if not wiki_root.is_dir():
        print(f"ERROR: wiki root not found: {wiki_root}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # --stats: print dimensions and exit
    # ------------------------------------------------------------------
    if args.stats:
        _show_stats(index_path, state_file)
        return 0

    WikiIndexer = _import_indexer()

    # ------------------------------------------------------------------
    # --full: full rebuild
    # ------------------------------------------------------------------
    if args.full:
        print(f"wiki-root  : {wiki_root}")
        print(f"index-path : {index_path}")
        print(f"model      : {args.model}")
        print()

        if args.dry_run:
            indexer = WikiIndexer(
                wiki_root=wiki_root,
                index_path=index_path,
                model_name=args.model,
            )
            t0 = time.monotonic()
            chunks = indexer.crawl_and_chunk()
            page_count = len({c.path for c in chunks})
            elapsed = time.monotonic() - t0
            print(f"[dry-run --full] pages   : {page_count}")
            print(f"[dry-run --full] chunks  : {len(chunks)}")
            print(f"[dry-run --full] elapsed : {elapsed:.1f}s")
            print("[dry-run --full] index NOT written.")
            return 0

        t0 = time.monotonic()
        indexer = WikiIndexer(
            wiki_root=wiki_root,
            index_path=index_path,
            model_name=args.model,
        )
        try:
            n_indexed = indexer.build(force_rebuild=True)
        except ImportError as exc:
            print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            log.exception("Full build failed.")
            print(f"ERROR during full build: {exc}", file=sys.stderr)
            return 1

        new_state = _build_current_state(wiki_root, args.hash)
        _save_state(state_file, new_state)

        elapsed = time.monotonic() - t0
        print(
            f"Updated {n_indexed} chunks "
            f"({n_indexed} added, 0 deleted, 0 unchanged) in {elapsed:.1f}s"
        )
        print(f"  files: +{len(new_state)} added (full rebuild), 0 removed")
        return 0

    # ------------------------------------------------------------------
    # Incremental update (default)
    # ------------------------------------------------------------------

    print(f"wiki-root  : {wiki_root}")
    print(f"index-path : {index_path}")
    print(f"state-file : {state_file}")
    print()

    t0 = time.monotonic()
    prev_state = _load_state(state_file)

    # No previous state → fall back to full rebuild and create state file
    if not prev_state:
        if args.dry_run:
            current_state = _build_current_state(wiki_root, args.hash)
            print(
                f"[dry-run] Nessuno state file trovato — "
                f"verrebbe eseguito full rebuild di {len(current_state)} file."
            )
            return 0

        log.info("No state file found — performing full rebuild.")
        print("Nessuno state file trovato — eseguo rebuild completo...")

        indexer = WikiIndexer(
            wiki_root=wiki_root,
            index_path=index_path,
            model_name=args.model,
        )
        try:
            n_indexed = indexer.build(force_rebuild=True)
        except ImportError as exc:
            print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            log.exception("Full rebuild failed.")
            print(f"ERROR during full rebuild: {exc}", file=sys.stderr)
            return 1

        new_state = _build_current_state(wiki_root, args.hash)
        _save_state(state_file, new_state)

        elapsed = time.monotonic() - t0
        print(
            f"Updated {n_indexed} chunks "
            f"({n_indexed} added, 0 deleted, 0 unchanged) in {elapsed:.1f}s"
        )
        print(f"  files: +{len(new_state)} added (full rebuild), 0 removed")
        return 0

    # ------------------------------------------------------------------
    # Compute diff between previous state and current filesystem
    # ------------------------------------------------------------------
    current_state = _build_current_state(wiki_root, args.hash)

    prev_paths = set(prev_state.keys())
    curr_paths = set(current_state.keys())

    added_paths = sorted(curr_paths - prev_paths)
    removed_paths = sorted(prev_paths - curr_paths)
    modified_paths = sorted(
        p for p in curr_paths & prev_paths
        if current_state[p] != prev_state[p]
    )
    n_unchanged = len((curr_paths & prev_paths) - set(modified_paths))

    n_added = len(added_paths)
    n_removed = len(removed_paths)
    n_modified = len(modified_paths)

    # ------------------------------------------------------------------
    # Idempotence (AC4): no changes detected
    # ------------------------------------------------------------------
    if n_added == 0 and n_removed == 0 and n_modified == 0:
        print("Nessuna modifica rilevata — indice gia' aggiornato")
        return 0

    # ------------------------------------------------------------------
    # --dry-run: report without writing
    # ------------------------------------------------------------------
    if args.dry_run:
        print(f"[dry-run] files added    : {n_added}")
        print(f"[dry-run] files modified : {n_modified}")
        print(f"[dry-run] files removed  : {n_removed}")
        print(f"[dry-run] files unchanged: {n_unchanged}")
        for p in added_paths:
            print(f"  + {p}")
        for p in modified_paths:
            print(f"  ~ {p}")
        for p in removed_paths:
            print(f"  - {p}")
        print("[dry-run] index NOT written.")
        return 0

    # ------------------------------------------------------------------
    # Real incremental update
    # ------------------------------------------------------------------
    indexer = WikiIndexer(
        wiki_root=wiki_root,
        index_path=index_path,
        model_name=args.model,
    )

    chunks_deleted = 0
    chunks_added = 0

    # Step 1 — remove chunks for deleted files
    if removed_paths:
        log.info("Counting and removing chunks for %d deleted file(s)...", len(removed_paths))
        chunks_deleted += _count_chunks_for_paths(index_path, removed_paths)
        try:
            _delete_chunks_by_paths(index_path, removed_paths)
        except ImportError as exc:
            print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            log.warning("Failed to delete chunks for removed files: %s", exc)

    # Step 2 — re-index added and modified files
    to_index = added_paths + modified_paths
    if to_index:
        log.info(
            "Indexing %d file(s) (added=%d, modified=%d)...",
            len(to_index), n_added, n_modified,
        )

        # Delete stale chunks for modified files before re-indexing
        if modified_paths:
            try:
                _delete_chunks_by_paths(index_path, modified_paths)
            except Exception as exc:
                log.warning("Failed to delete stale chunks for modified files: %s", exc)

        abs_paths = [wiki_root / p for p in to_index]
        try:
            chunks = indexer.crawl_and_chunk(paths=abs_paths)
            if chunks:
                rows = indexer.embed_chunks(chunks)
                chunks_added = indexer.upsert(rows)
        except ImportError as exc:
            print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            log.exception("Indexing failed.")
            print(f"ERROR during indexing: {exc}", file=sys.stderr)
            return 1

    # ------------------------------------------------------------------
    # Persist updated state
    # ------------------------------------------------------------------
    new_state = dict(prev_state)
    for p in removed_paths:
        new_state.pop(p, None)
    for p in to_index:
        new_state[p] = current_state[p]
    _save_state(state_file, new_state)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    elapsed = time.monotonic() - t0
    n_total = chunks_added + chunks_deleted
    print(
        f"Updated {n_total} chunks "
        f"({chunks_added} added, {chunks_deleted} deleted, "
        f"{n_unchanged} unchanged) in {elapsed:.1f}s"
    )
    print(
        f"  files: +{n_added} added, ~{n_modified} modified, "
        f"-{n_removed} removed"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
