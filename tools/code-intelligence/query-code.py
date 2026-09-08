#!/usr/bin/env python3
"""query-code.py — Query semantica su indice LanceDB code_chunks (EP-054 L2).

Usage:
    python3 query-code.py "<query>" [--top=5] [--lang=python] [--type=function]
                           [--db=.code-search/index.lance] [--model=nomic-embed-code]
    python3 query-code.py --status [--db=.code-search/index.lance]
"""
import sys
import json
import argparse

# EP-054 R.CI2: prerequisite check — SKIP non STOP
try:
    import lancedb
except ImportError:
    print("[L2-SKIP] lancedb not installed — pip install lancedb")
    sys.exit(0)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[L2-SKIP] sentence-transformers not installed — pip install sentence-transformers")
    sys.exit(0)

DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1"
DEFAULT_DB = ".code-search/index.lance"
TABLE_NAME = "code_chunks"


def format_result(row: dict, score: float) -> str:
    file_line = f"{row['file']}:{row['start_line']}"
    sym_type = f"[{row['type']}]"
    symbol = row["symbol"]
    return f"{file_line:<45} {sym_type:<12} {symbol} — {score:.2f}"


def show_status(db_path: str) -> None:
    from pathlib import Path
    import datetime
    import os

    p = Path(db_path)
    print("CODE INTELLIGENCE INDEX STATUS (L2)")
    print("=====================================")
    print(f"index-path  : {db_path}")

    if not p.exists():
        print(f"              NON TROVATO")
        print()
        print("Esegui /code-search reindex per costruire l'indice.")
        print("Prerequisiti: vedi wiki/runbooks/code-intelligence.md")
        return

    db = lancedb.connect(str(p))
    if TABLE_NAME not in db.list_tables():
        print(f"table       : {TABLE_NAME} — NON TROVATO")
        print()
        print("Esegui /code-search reindex per costruire l'indice.")
        return

    tbl = db.open_table(TABLE_NAME)
    df = tbl.to_pandas()
    total = len(df)
    print(f"table       : {TABLE_NAME}")
    print(f"rows        : {total} chunks")

    if total > 0 and "slug" in df.columns:
        slugs = df.groupby("slug").size()
        slug_str = ", ".join(f"{slug} ({cnt})" for slug, cnt in slugs.items())
        print(f"slugs       : {slug_str}")

    # Recupera modello da factory.config.yaml se disponibile
    model_name = DEFAULT_MODEL
    try:
        import yaml
        cfg_path = Path("factory.config.yaml")
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f) or {}
            model_name = (
                cfg.get("code_intelligence", {})
                   .get("embedding_model", DEFAULT_MODEL)
            )
    except Exception:
        pass
    print(f"model       : {model_name}")

    # Dimensione su disco
    size_bytes = sum(
        f.stat().st_size for f in p.rglob("*") if f.is_file()
    )
    if size_bytes > 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{size_bytes / 1024:.1f} KB"

    # Timestamp ultimo aggiornamento
    mtime = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()), default=None)
    if mtime:
        ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print()
        print(f"Ultimo aggiornamento: {ts}")
    print(f"Dimensione su disco : {size_str}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query semantica su indice LanceDB code_chunks (EP-054 L2)"
    )
    parser.add_argument("query", nargs="?", default=None, help="Query semantica")
    parser.add_argument("--top", type=int, default=5, help="Numero risultati (max 20)")
    parser.add_argument("--lang", default=None, help="Filtra per linguaggio")
    parser.add_argument("--type", dest="sym_type", default=None, help="Filtra per tipo simbolo")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path indice LanceDB")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Sentence-transformer model")
    parser.add_argument("--json", action="store_true", help="Output JSON machine-readable")
    parser.add_argument("--status", action="store_true", help="Mostra stato indice e STOP")
    args = parser.parse_args()

    # Clamp top a 20
    top_k = min(args.top, 20)

    if args.status:
        show_status(args.db)
        return

    if not args.query:
        parser.print_help()
        sys.exit(0)

    from pathlib import Path

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[L2-FALLBACK] index not found at {args.db} — run /code-search reindex")
        sys.exit(0)

    db = lancedb.connect(str(db_path))
    if TABLE_NAME not in db.list_tables():
        print(f"[L2-FALLBACK] table '{TABLE_NAME}' not found — run /code-search reindex")
        sys.exit(0)

    tbl = db.open_table(TABLE_NAME)

    # Prefisso nomic per distinguere query da document
    if "nomic" in args.model.lower():
        query_text = f"search_query: {args.query}"
    else:
        query_text = args.query

    model = SentenceTransformer(args.model, trust_remote_code=True)
    query_vec = model.encode(query_text, normalize_embeddings=True).tolist()

    # Overquery per post-filter: recupera top_k * 3 e poi filtra
    q = tbl.search(query_vec, vector_column_name="vector").limit(top_k * 3)
    results_df = q.to_pandas()

    if results_df.empty:
        print("[L2] No results found")
        sys.exit(0)

    # Post-filtri opzionali
    if args.lang and "language" in results_df.columns:
        results_df = results_df[results_df["language"] == args.lang]
    if args.sym_type and "type" in results_df.columns:
        results_df = results_df[results_df["type"] == args.sym_type]

    results_df = results_df.head(top_k)

    if results_df.empty:
        print("[L2] No results found after filtering")
        sys.exit(0)

    if args.json:
        results = []
        for _, row in results_df.iterrows():
            score = 1.0 - float(row.get("_distance", 0))
            results.append(
                {
                    "file": row["file"],
                    "symbol": row["symbol"],
                    "type": row["type"],
                    "language": row.get("language", ""),
                    "start_line": int(row["start_line"]),
                    "end_line": int(row.get("end_line", row["start_line"])),
                    "score": round(score, 4),
                    "docstring": row.get("docstring", ""),
                    "slug": row.get("slug", ""),
                }
            )
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for _, row in results_df.iterrows():
            score = 1.0 - float(row.get("_distance", 0))
            print(format_result(row.to_dict(), score))


if __name__ == "__main__":
    main()
