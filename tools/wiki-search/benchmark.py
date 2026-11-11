"""
benchmark.py — Precision@3 benchmark for EP-042 Phase 2 (TSK-505).

Compares baseline H2-section chunker vs ADR-C ast_aware chunker on 50 queries
(25 IT + 25 EN) using heuristic ground truth: a wiki page is "relevant" to a
query if it contains ALL keywords from the query.

Modes:
  real        — builds two real LanceDB+SentenceTransformer indices and runs
                vector-similarity search (requires lancedb + sentence_transformers)
  structural  — stdlib-only TF-IDF proxy (no ML deps), used when real deps absent

Usage:
  python3 tools/wiki-search/benchmark.py
  python3 tools/wiki-search/benchmark.py --mode real
  python3 tools/wiki-search/benchmark.py --mode structural

Results are saved to tools/wiki-search/benchmark_results.json.

NOTE on bug found during TSK-505:
  indexer.py:crawl_wiki() raises TypeError when a wiki page has a YAML frontmatter
  field whose value is a Python datetime.date (e.g. `tags: [2026-09-02]`).
  The json.dumps() call does not handle date objects.
  This is a pre-existing bug in the tested code (indexer.py). A separate TSK is
  required to fix it (see KNOWN_BUG_TSK below). The benchmark works around this
  by using its own date-safe crawl_wiki_safe() that JSON-serializes dates as strings.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

KNOWN_BUG_TSK = "BUG-TSK-505-001: indexer.py crawl_wiki() — TypeError for YAML date objects in frontmatter fields (e.g. tags: [2026-09-02]). Affects upsert path (json.dumps fails). Chunking functions (chunk_h2/chunk_ast_aware) are unaffected."

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
RESULTS_PATH = Path(__file__).resolve().parent / "benchmark_results.json"
INDEXER_PATH = Path(__file__).resolve().parent / "indexer.py"

# ---------------------------------------------------------------------------
# Query set: 25 IT + 25 EN = 50 total
# ---------------------------------------------------------------------------

QUERIES_IT = [
    "come funziona il compression layer a due assi",
    "quali sono le invarianti del tavola rotonda",
    "quando usare pattern-steal vs vendor-in",
    "come si configura il budget della tavola rotonda",
    "differenza tra wiki-keeper 2.0 e wiki-keeper originale",
    "quali capability sono marcate SUNSET",
    "come funziona il parallel scheduler",
    "come si abilita wiki_search",
    "cosa fa il graphify sync",
    "come si esegue un factory upgrade",
    "che cos e la dispatch-policy",
    "come funziona il ponytail decision ladder",
    "differenza tra compression output e compression context",
    "come si configura il kanban publish",
    "che cos e il token ledger",
    "come si crea una nuova user story",
    "quando invocare wiki-keeper per ingest",
    "come funziona il functional oracle",
    "come si avvia una tavola rotonda session",
    "cosa fa il release-manager nel factory",
    "come si esegue il code review CQRL",
    "che cos e il semantic drift scan",
    "come si gestisce un submodule VCS branch",
    "che cosa e l EP-054 code intelligence stack",
    "come si usa il voice channel modulo",
]

QUERIES_EN = [
    "how to install graphify for code intelligence",
    "what is the RRF fusion formula used in wiki search",
    "steps to create a new epic in the factory",
    "how does the parallel scheduler dispatch work",
    "wiki-search reindex command options",
    "what is the caveman protocol compression",
    "how to configure the code quality reviewer",
    "what does the consistency checker do in lint",
    "how to set up kanban publish to GitHub",
    "what is the purpose of the premortem skill",
    "how does the dev-protocol checkpoint work",
    "what is pattern version 2.39 ponytail",
    "how to run a Tavola Rotonda session",
    "what are the R.WS invariants wiki search",
    "how to use the visual oracle fe-dev",
    "what is the token ledger analytics show session",
    "how to promote a wiki page status",
    "what is the YAGNI ladder in ponytail decision",
    "how does the heal protocol work on lint errors",
    "how to configure compression output caveman",
    "what is the factory topology hybrid-fe-agents",
    "how to run the benchmark for wiki search precision",
    "what are the code intelligence L1 L2 L3 layers",
    "how to sync a PDF document with sync-docs",
    "what is the purpose of the factory-bootstrap meta-prompt",
]

ALL_QUERIES = QUERIES_IT + QUERIES_EN
assert len(ALL_QUERIES) == 50, f"Expected 50 queries, got {len(ALL_QUERIES)}"


# ---------------------------------------------------------------------------
# Date-safe JSON encoder (workaround for BUG-TSK-505-001)
# ---------------------------------------------------------------------------

import datetime

class _DateSafeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


def _safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, cls=_DateSafeEncoder, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Date-safe crawl_wiki (benchmark-local copy; does not modify indexer.py)
# ---------------------------------------------------------------------------

_META_PATHS_BENCH = {"gaps.md", "log.md"}


def _parse_frontmatter_bench(text: str) -> tuple[dict, str]:
    fm: dict = {}
    if not text.startswith("---"):
        return fm, text
    end = text.find("\n---", 3)
    if end < 0:
        return fm, text
    fm_raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        import yaml
        fm = yaml.safe_load(fm_raw) or {}
    except Exception:
        pass
    return fm, body


def crawl_wiki_safe(wiki_root: Path) -> list[dict]:
    """
    Date-safe variant of indexer.crawl_wiki(). Used only in this benchmark.
    Converts YAML date/datetime values to ISO strings before json.dumps.
    """
    pages: list[dict] = []
    for md_path in sorted(wiki_root.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, body = _parse_frontmatter_bench(text)
        rel = str(md_path.relative_to(wiki_root))

        if md_path.name in _META_PATHS_BENCH:
            doc_type = "meta"
        elif fm:
            doc_type = str(fm.get("type", "unknown"))
        else:
            doc_type = "unknown"

        title = str(fm.get("title", md_path.stem.replace("-", " ").title()))
        status = str(fm.get("status", "unknown"))
        raw_tags = fm.get("tags", [])
        if not isinstance(raw_tags, list):
            raw_tags = []
        # Date-safe serialization
        tags_json = _safe_json_dumps(raw_tags)

        pages.append({
            "path": rel,
            "title": title,
            "type": doc_type,
            "status": status,
            "tags_json": tags_json,
            "raw_body": body,
        })
    return pages


# ---------------------------------------------------------------------------
# Heuristic ground truth
# ---------------------------------------------------------------------------

def _keywords(query: str) -> list[str]:
    """Extract searchable keywords from a query (length >= 3, common stopwords removed)."""
    stopwords = {
        "come", "cosa", "che", "quando", "quali", "quale", "si", "il", "la",
        "lo", "un", "una", "di", "del", "della", "dei", "le", "li", "gli",
        "tra", "per", "nel", "nelle", "nel", "da", "con", "sul", "alla",
        "how", "what", "when", "which", "the", "and", "for", "are", "is",
        "to", "in", "of", "on", "at", "by", "an", "a", "do", "does",
        "vs", "tra", "e", "o", "fa", "do", "use", "run",
    }
    words = re.findall(r"[a-zA-Z0-9_\-\.@]{3,}", query.lower())
    return [w for w in words if w not in stopwords]


def build_ground_truth(wiki_root: Path, queries: list[str]) -> dict[str, list[str]]:
    """
    For each query, find wiki pages whose content contains ALL keywords.
    Returns {query: [list of relevant page paths]}.
    """
    pages: list[tuple[str, str]] = []  # (rel_path, lowercased content)
    for md_path in sorted(wiki_root.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8").lower()
            rel = str(md_path.relative_to(wiki_root))
            pages.append((rel, text))
        except Exception:
            continue

    gt: dict[str, list[str]] = {}
    for q in queries:
        kws = _keywords(q)
        if not kws:
            gt[q] = []
            continue
        relevant = []
        for rel, text in pages:
            if all(kw in text for kw in kws):
                relevant.append(rel)
        gt[q] = relevant

    return gt


# ---------------------------------------------------------------------------
# TF-IDF structural mode (stdlib only)
# ---------------------------------------------------------------------------

def _tfidf_search(query: str, pages: list[tuple[str, str]], top_k: int = 3) -> list[str]:
    """
    Simple TF-IDF ranking over (rel_path, content) pairs.
    Returns top_k page paths sorted by descending score.
    """
    kws = _keywords(query)
    if not kws:
        return []

    # IDF: log((N+1)/(df+1)) + 1
    N = len(pages)
    df: dict[str, int] = {}
    for _, text in pages:
        seen = set()
        for kw in kws:
            if kw in text and kw not in seen:
                df[kw] = df.get(kw, 0) + 1
                seen.add(kw)

    idf = {kw: math.log((N + 1) / (df.get(kw, 0) + 1)) + 1.0 for kw in kws}

    scores: list[tuple[float, str]] = []
    for rel, text in pages:
        score = 0.0
        word_count = max(len(text.split()), 1)
        for kw in kws:
            tf = text.count(kw) / word_count
            score += tf * idf[kw]
        if score > 0:
            scores.append((score, rel))

    scores.sort(reverse=True)
    return [rel for _, rel in scores[:top_k]]


def run_structural_benchmark(
    wiki_root: Path,
    queries: list[str],
    ground_truth: dict[str, list[str]],
    top_k: int = 3,
) -> tuple[list[dict], dict]:
    """
    Structural mode: compare chunk quality metrics + TF-IDF precision@k.

    chunk_h2 vs chunk_ast_aware are compared by:
    - avg_chunk_size
    - pct_code_fence_intact (fraction of chunks that contain intact ``` fences)
    - section_count

    For search precision, TF-IDF on chunk content is used as proxy.
    Returns (per_query_rows, summary_dict).
    """
    # Import indexer chunking functions (stdlib-safe; crawl_wiki is NOT used here
    # to avoid BUG-TSK-505-001 — we use crawl_wiki_safe from this benchmark module)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from indexer import chunk_h2, chunk_ast_aware  # noqa: E402

    print("  Crawling wiki pages...", flush=True)
    pages = crawl_wiki_safe(wiki_root)
    print(f"  {len(pages)} pages found.", flush=True)

    # --- Chunk quality comparison ---
    def _analyze_chunks(chunks_list: list[dict]) -> dict:
        sizes = [len(c["content"]) for c in chunks_list]
        avg_size = sum(sizes) / max(len(sizes), 1)
        fence_intact = sum(
            1 for c in chunks_list
            if "```" in c["content"] and c["content"].count("```") % 2 == 0
        )
        pct_fence = fence_intact / max(len(chunks_list), 1)
        return {
            "chunk_count": len(chunks_list),
            "avg_chunk_size": round(avg_size, 1),
            "pct_code_fence_intact": round(pct_fence * 100, 1),
        }

    h2_chunks: list[dict] = []
    ast_chunks: list[dict] = []
    for page in pages:
        h2_chunks.extend(chunk_h2(page))
        ast_chunks.extend(chunk_ast_aware(page))

    h2_quality = _analyze_chunks(h2_chunks)
    ast_quality = _analyze_chunks(ast_chunks)

    print(f"  H2  chunks: {h2_quality['chunk_count']}  avg_size={h2_quality['avg_chunk_size']}  fence_intact={h2_quality['pct_code_fence_intact']}%")
    print(f"  AST chunks: {ast_quality['chunk_count']}  avg_size={ast_quality['avg_chunk_size']}  fence_intact={ast_quality['pct_code_fence_intact']}%")

    # Build TF-IDF corpus from chunks
    def _chunks_corpus(chunks: list[dict]) -> list[tuple[str, str]]:
        # Aggregate chunks by page path
        page_text: dict[str, str] = {}
        for c in chunks:
            page_text.setdefault(c["path"], "")
            page_text[c["path"]] += " " + c["content"]
        return [(path, txt.lower()) for path, txt in page_text.items()]

    h2_corpus = _chunks_corpus(h2_chunks)
    ast_corpus = _chunks_corpus(ast_chunks)

    # Per-query precision@k
    per_query_rows: list[dict] = []
    h2_p3_list: list[float] = []
    ast_p3_list: list[float] = []

    for q in queries:
        gt_pages = ground_truth.get(q, [])

        h2_top = _tfidf_search(q, h2_corpus, top_k)
        ast_top = _tfidf_search(q, ast_corpus, top_k)

        def _p3(retrieved: list[str]) -> float:
            if not retrieved or not gt_pages:
                return 0.0 if gt_pages else 1.0  # no GT = vacuously relevant
            hits = sum(1 for r in retrieved if r in gt_pages)
            return hits / len(retrieved)

        h2_p = _p3(h2_top)
        ast_p = _p3(ast_top)
        delta = ast_p - h2_p

        h2_p3_list.append(h2_p)
        ast_p3_list.append(ast_p)

        per_query_rows.append({
            "query": q,
            "gt_pages": len(gt_pages),
            "baseline_p3": round(h2_p, 3),
            "adr_c_p3": round(ast_p, 3),
            "delta": round(delta, 3),
        })

    avg_h2 = sum(h2_p3_list) / len(h2_p3_list)
    avg_ast = sum(ast_p3_list) / len(ast_p3_list)
    avg_delta = avg_ast - avg_h2
    delta_pct = (avg_delta / max(avg_h2, 1e-9)) * 100

    summary = {
        "mode": "structural",
        "note": "TF-IDF proxy over chunk corpus; not real vector search. Structural comparison.",
        "chunk_quality": {
            "h2_section": h2_quality,
            "ast_aware": ast_quality,
        },
        "precision_at_3": {
            "baseline_avg": round(avg_h2, 4),
            "adr_c_avg": round(avg_ast, 4),
            "delta_abs": round(avg_delta, 4),
            "delta_pct": round(delta_pct, 2),
        },
        "acc7_verdict": _acc7_verdict(delta_pct),
    }
    return per_query_rows, summary


# ---------------------------------------------------------------------------
# Real mode: LanceDB + SentenceTransformer
# ---------------------------------------------------------------------------

def _build_index(
    wiki_root: Path,
    index_path: Path,
    strategy: str,
    model_name: str,
) -> int:
    """
    Build a LanceDB index with the given chunking strategy. Returns chunk count.

    Uses crawl_wiki_safe (benchmark-local) to avoid BUG-TSK-505-001.
    Then delegates chunking to indexer.chunk_h2 / chunk_ast_aware (tested code).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from indexer import chunk_document, embed_batch, upsert_table  # noqa: E402

    pages = crawl_wiki_safe(wiki_root)
    all_chunks: list[dict] = []
    for page in pages:
        all_chunks.extend(chunk_document(page, strategy))

    if not all_chunks:
        return 0

    texts = [f"{c['title']} {c['section']} {c['content']}".strip() for c in all_chunks]

    # Single embed_batch call to avoid re-loading SentenceTransformer model per batch.
    # indexer.embed_batch() passes all texts to model.encode() directly.
    embeddings: list[list[float]] = embed_batch(texts, model_name)

    rows = []
    for chunk, emb in zip(all_chunks, embeddings):
        rows.append({**chunk, "embedding": emb})

    upsert_table(str(index_path), rows)
    return len(rows)


def _vector_search(
    query: str,
    index_path: Path,
    model_name: str,
    top_k: int = 3,
) -> list[str]:
    """Run vector similarity search on a LanceDB index. Returns list of page paths."""
    try:
        import lancedb  # noqa: E402 (lazy)
        from sentence_transformers import SentenceTransformer  # noqa: E402

        db = lancedb.connect(str(index_path))
        if "pages" not in db.table_names():
            return []
        table = db.open_table("pages")

        model = SentenceTransformer(model_name)
        q_vec = model.encode([query], normalize_embeddings=True)[0].tolist()

        results = table.search(q_vec).limit(top_k).to_list()
        return [r["path"] for r in results]
    except Exception as e:
        print(f"    [WARN] search error: {e}", file=sys.stderr)
        return []


def run_real_benchmark(
    wiki_root: Path,
    queries: list[str],
    ground_truth: dict[str, list[str]],
    top_k: int = 3,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> tuple[list[dict], dict]:
    """
    Real mode: build two LanceDB indices (h2_section + ast_aware), run vector
    search on all queries, measure precision@3.
    Returns (per_query_rows, summary_dict).
    """
    with tempfile.TemporaryDirectory(prefix="bench_") as tmpdir:
        tmp = Path(tmpdir)
        h2_index = tmp / "index_h2"
        ast_index = tmp / "index_ast"

        print("  [1/4] Building h2_section index...", flush=True)
        t0 = time.time()
        n_h2 = _build_index(wiki_root, h2_index, "h2_section", model_name)
        print(f"        {n_h2} chunks indexed in {time.time()-t0:.1f}s", flush=True)

        print("  [2/4] Building ast_aware index...", flush=True)
        t0 = time.time()
        n_ast = _build_index(wiki_root, ast_index, "ast_aware", model_name)
        print(f"        {n_ast} chunks indexed in {time.time()-t0:.1f}s", flush=True)

        # Cache model (single load)
        print("  [3/4] Loading embedding model (single load)...", flush=True)
        from sentence_transformers import SentenceTransformer  # noqa: E402
        import lancedb as _lancedb  # noqa: E402

        _model = SentenceTransformer(model_name)
        _db_h2 = _lancedb.connect(str(h2_index))
        _db_ast = _lancedb.connect(str(ast_index))
        _tbl_h2 = _db_h2.open_table("pages") if "pages" in _db_h2.table_names() else None
        _tbl_ast = _db_ast.open_table("pages") if "pages" in _db_ast.table_names() else None

        def _search_table(table: Any, q: str) -> list[str]:
            if table is None:
                return []
            try:
                q_vec = _model.encode([q], normalize_embeddings=True)[0].tolist()
                results = table.search(q_vec).limit(top_k).to_list()
                return [r["path"] for r in results]
            except Exception as e:
                print(f"    [WARN] {e}", file=sys.stderr)
                return []

        print("  [4/4] Running queries...", flush=True)
        per_query_rows: list[dict] = []
        h2_p3_list: list[float] = []
        ast_p3_list: list[float] = []

        for i, q in enumerate(queries, 1):
            gt_pages = ground_truth.get(q, [])

            h2_top = _search_table(_tbl_h2, q)
            ast_top = _search_table(_tbl_ast, q)

            def _p3(retrieved: list[str]) -> float:
                if not retrieved or not gt_pages:
                    return 0.0 if gt_pages else 1.0
                hits = sum(1 for r in retrieved if r in gt_pages)
                return hits / len(retrieved)

            h2_p = _p3(h2_top)
            ast_p = _p3(ast_top)
            delta = ast_p - h2_p

            h2_p3_list.append(h2_p)
            ast_p3_list.append(ast_p)

            per_query_rows.append({
                "query": q,
                "gt_pages": len(gt_pages),
                "baseline_top3": h2_top,
                "adr_c_top3": ast_top,
                "baseline_p3": round(h2_p, 3),
                "adr_c_p3": round(ast_p, 3),
                "delta": round(delta, 3),
            })

            if i % 10 == 0:
                print(f"        {i}/{len(queries)} queries done", flush=True)

    avg_h2 = sum(h2_p3_list) / len(h2_p3_list)
    avg_ast = sum(ast_p3_list) / len(ast_p3_list)
    avg_delta = avg_ast - avg_h2
    delta_pct = (avg_delta / max(avg_h2, 1e-9)) * 100

    summary = {
        "mode": "real",
        "model": model_name,
        "index_sizes": {"h2_section": n_h2, "ast_aware": n_ast},
        "precision_at_3": {
            "baseline_avg": round(avg_h2, 4),
            "adr_c_avg": round(avg_ast, 4),
            "delta_abs": round(avg_delta, 4),
            "delta_pct": round(delta_pct, 2),
        },
        "acc7_verdict": _acc7_verdict(delta_pct),
    }
    return per_query_rows, summary


# ---------------------------------------------------------------------------
# ACC-7 verdict
# ---------------------------------------------------------------------------

def _acc7_verdict(delta_pct: float) -> str:
    if delta_pct >= 15.0:
        return "GO: delta >= 15% — proceed ADR-A + ADR-B high priority"
    elif delta_pct >= 10.0:
        return "GO-CAUTIOUS: 10% <= delta < 15% — ADR-A first, ADR-B conditional"
    else:
        return "NO-GO: delta < 10% — close EP-042 Phase 2 with ADR-C only"


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def print_table(rows: list[dict]) -> None:
    col_q = max(len(r["query"]) for r in rows)
    col_q = min(col_q, 60)
    header = f"{'Query':<{col_q}}  {'GT':>3}  {'Base P@3':>8}  {'ADR-C P@3':>9}  {'Delta':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        q = r["query"][:col_q]
        print(
            f"{q:<{col_q}}  {r['gt_pages']:>3}  {r['baseline_p3']:>8.3f}"
            f"  {r['adr_c_p3']:>9.3f}  {r['delta']:>+7.3f}"
        )


def print_summary(summary: dict) -> None:
    p3 = summary["precision_at_3"]
    print()
    print("=" * 60)
    print(f"MODE            : {summary['mode']}")
    if summary.get("note"):
        print(f"NOTE            : {summary['note']}")
    if summary.get("model"):
        print(f"EMBEDDING MODEL : {summary['model']}")
    print(f"BASELINE P@3    : {p3['baseline_avg']:.4f}")
    print(f"ADR-C P@3       : {p3['adr_c_avg']:.4f}")
    print(f"DELTA ABS       : {p3['delta_abs']:+.4f}")
    print(f"DELTA %         : {p3['delta_pct']:+.2f}%")
    print(f"ACC-7 VERDICT   : {summary['acc7_verdict']}")
    print("=" * 60)

    if "chunk_quality" in summary:
        print()
        print("Chunk quality comparison:")
        for strategy, q in summary["chunk_quality"].items():
            print(
                f"  {strategy:12s}  chunks={q['chunk_count']}  "
                f"avg_size={q['avg_chunk_size']}  "
                f"fence_intact={q['pct_code_fence_intact']}%"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="EP-042 Phase 2 benchmark (TSK-505)")
    parser.add_argument(
        "--mode",
        choices=["real", "structural"],
        default=None,
        help="Force mode (default: auto-detect based on deps availability)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="k for precision@k (default 3)",
    )
    args = parser.parse_args()

    # Auto-detect mode
    if args.mode is None:
        try:
            import lancedb  # noqa: F401
            import sentence_transformers  # noqa: F401
            mode = "real"
        except ImportError:
            mode = "structural"
        print(f"[auto-detect] mode={mode}")
    else:
        mode = args.mode

    print(f"\n[TSK-505] EP-042 Phase 2 — Precision@3 Benchmark")
    print(f"  Wiki root  : {WIKI_ROOT}")
    print(f"  Queries    : {len(ALL_QUERIES)} (25 IT + 25 EN)")
    print(f"  Mode       : {mode}")
    print(f"  Top-k      : {args.top_k}")
    print()

    # Build ground truth
    print("[Step 1/3] Building heuristic ground truth...")
    t0 = time.time()
    ground_truth = build_ground_truth(WIKI_ROOT, ALL_QUERIES)
    gt_sizes = [len(v) for v in ground_truth.values()]
    print(
        f"  GT built in {time.time()-t0:.1f}s  "
        f"avg_relevant_pages={sum(gt_sizes)/max(len(gt_sizes),1):.1f}  "
        f"queries_with_gt={sum(1 for s in gt_sizes if s>0)}/{len(ALL_QUERIES)}"
    )
    print()

    # Run benchmark
    print(f"[Step 2/3] Running {mode} benchmark...")
    t0 = time.time()
    if mode == "real":
        per_query_rows, summary = run_real_benchmark(
            WIKI_ROOT, ALL_QUERIES, ground_truth, top_k=args.top_k
        )
    else:
        per_query_rows, summary = run_structural_benchmark(
            WIKI_ROOT, ALL_QUERIES, ground_truth, top_k=args.top_k
        )
    elapsed = time.time() - t0
    print(f"  Benchmark done in {elapsed:.1f}s")
    print()

    # Display results
    print("[Step 3/3] Results")
    print()
    print_table(per_query_rows)
    print_summary(summary)

    # Save JSON
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tsk": "TSK-505",
        "queries_count": len(ALL_QUERIES),
        "summary": summary,
        "per_query": per_query_rows,
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nResults saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
