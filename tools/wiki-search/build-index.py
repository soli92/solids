#!/usr/bin/env python3
"""
Build or rebuild the wiki hybrid search index.

Usage:
    python tools/wiki-search/build-index.py                  # full build
    python tools/wiki-search/build-index.py --rebuild        # force full rebuild
    python tools/wiki-search/build-index.py --incremental    # solo file modificati (stub)
    python tools/wiki-search/build-index.py --wiki-root wiki/ --index-path .wiki-search/index.lance
    python tools/wiki-search/build-index.py --dry-run        # mostra statistiche senza scrivere
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repo-root discovery
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """
    Walk up from start looking for factory.config.yaml or a wiki/ directory.
    Falls back to start.resolve() if neither marker is found.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "factory.config.yaml").exists() or (candidate / "wiki").is_dir():
            return candidate
    return current


# ---------------------------------------------------------------------------
# Import helper (indexer.py lives alongside this file)
# ---------------------------------------------------------------------------

def _import_indexer():
    """
    Insert the directory that contains this script into sys.path so that
    indexer.py is importable regardless of the caller's cwd.
    The file is named build-index.py (hyphen) — not importable as a module;
    all reusable logic lives in indexer.py (TSK-308, R.WS1).
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
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="build-index.py",
        description="Build or rebuild the wiki hybrid search index (LanceDB + embeddings).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force full rebuild — delete the existing index and rebuild from scratch.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help=(
            "Incremental update — reserved for TSK-315 / update-index.py. "
            "This version logs a TODO and exits cleanly with code 0."
        ),
    )
    parser.add_argument(
        "--wiki-root",
        default=None,
        metavar="PATH",
        help=(
            "Path to the wiki directory "
            "(default: auto-detected <repo-root>/wiki/)."
        ),
    )
    parser.add_argument(
        "--index-path",
        default=None,
        metavar="PATH",
        help=(
            "LanceDB database path where the index is stored "
            "(default: auto-detected <repo-root>/.wiki-search/index.lance)."
        ),
    )
    parser.add_argument(
        "--model",
        default="paraphrase-multilingual-MiniLM-L12-v2",
        metavar="MODEL",
        help=(
            "Sentence-Transformers model name used for embedding "
            "(default: paraphrase-multilingual-MiniLM-L12-v2)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Crawl and chunk only — print statistics without embedding or "
            "writing the index."
        ),
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
    # --incremental stub (TSK-315 will replace this)
    # ------------------------------------------------------------------
    if args.incremental:
        print("TODO: incrementale — usa update-index.py")
        return 0

    # ------------------------------------------------------------------
    # Resolve wiki-root and index-path
    # ------------------------------------------------------------------
    repo_root = _find_repo_root(Path.cwd())
    wiki_root = Path(args.wiki_root) if args.wiki_root else repo_root / "wiki"
    index_path = (
        Path(args.index_path)
        if args.index_path
        else repo_root / ".wiki-search" / "index.lance"
    )

    if not wiki_root.is_dir():
        print(f"ERROR: wiki root not found: {wiki_root}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Import WikiIndexer (deferred so --help works without deps installed)
    # ------------------------------------------------------------------
    WikiIndexer = _import_indexer()

    print(f"wiki-root  : {wiki_root}")
    print(f"index-path : {index_path}")
    print(f"model      : {args.model}")
    print(f"rebuild    : {args.rebuild}")
    print(f"dry-run    : {args.dry_run}")
    print()

    indexer = WikiIndexer(
        wiki_root=wiki_root,
        index_path=index_path,
        model_name=args.model,
    )

    t0 = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1 — crawl + chunk (calls crawl_wiki + chunk_h2 internally)
    # ------------------------------------------------------------------
    try:
        chunks = indexer.crawl_and_chunk()
    except Exception as exc:
        log.exception("Crawl/chunk failed.")
        print(f"ERROR during crawl/chunk: {exc}", file=sys.stderr)
        return 1

    page_count = len({c.path for c in chunks})
    chunk_count = len(chunks)

    # ------------------------------------------------------------------
    # --dry-run: stop before embedding / writing
    # ------------------------------------------------------------------
    if args.dry_run:
        elapsed = time.monotonic() - t0
        print(f"[dry-run] pages crawled : {page_count}")
        print(f"[dry-run] chunks created: {chunk_count}")
        print(f"[dry-run] elapsed       : {elapsed:.1f}s")
        print("[dry-run] index NOT written.")
        return 0

    # ------------------------------------------------------------------
    # --rebuild: remove existing index before writing
    # ------------------------------------------------------------------
    if args.rebuild and index_path.exists():
        shutil.rmtree(index_path)
        log.info("Removed existing index at %s", index_path)

    # ------------------------------------------------------------------
    # Step 2 — embed (calls embed_batch internally)
    # Step 3 — upsert (calls upsert_table internally)
    # ------------------------------------------------------------------
    try:
        rows = indexer.embed_chunks(chunks)
        n_indexed = indexer.upsert(rows)
    except ImportError as exc:
        print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        log.exception("Embed/upsert failed.")
        print(f"ERROR during embed/upsert: {exc}", file=sys.stderr)
        return 1

    elapsed = time.monotonic() - t0
    print(f"pages crawled : {page_count}")
    print(f"chunks indexed: {n_indexed}")
    print(f"elapsed       : {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
