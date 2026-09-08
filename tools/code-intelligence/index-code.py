#!/usr/bin/env python3
"""index-code.py — Embedding + LanceDB upsert per code chunks (EP-054 L2).

Usage:
    python3 index-code.py <chunks.jsonl> <slug> [--model=nomic-embed-code]
                          [--db=.code-search/index.lance] [--full-rebuild]

Legge chunk JSONL da chunk-code.py, genera embeddings con sentence-transformers,
fa upsert nella tabella LanceDB "code_chunks".
"""
import sys
import json
import argparse
from pathlib import Path

# EP-054 R.CI2: prerequisite check — SKIP non STOP
try:
    import lancedb
    import pyarrow as pa
except ImportError:
    print("[L2-SKIP] lancedb/pyarrow not installed — pip install lancedb pyarrow")
    sys.exit(0)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[L2-SKIP] sentence-transformers not installed — pip install sentence-transformers")
    sys.exit(0)

DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1"
DEFAULT_DB_PATH = ".code-search/index.lance"
BATCH_SIZE = 4  # nomic-embed 2048 max_seq → OOM at 64 on CPU; 4 safe
MAX_SEQ_LENGTH = 512  # cap tokens per chunk to avoid attention OOM

VECTOR_DIM = 768  # nomic-embed-text-v1 output dimension

SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("slug", pa.string()),
    pa.field("file", pa.string()),
    pa.field("symbol", pa.string()),
    pa.field("type", pa.string()),
    pa.field("language", pa.string()),
    pa.field("start_line", pa.int32()),
    pa.field("end_line", pa.int32()),
    pa.field("code", pa.string()),
    pa.field("docstring", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),  # FixedSizeList required by LanceDB
])


def embed_texts(model: SentenceTransformer, texts: list, model_id: str) -> list:
    """Genera embedding con prefisso instruction-aware per nomic-embed-code."""
    if "nomic" in model_id.lower():
        prefixed = [f"search_document: {t}" for t in texts]
    else:
        prefixed = texts
    vecs = model.encode(prefixed, batch_size=BATCH_SIZE, show_progress_bar=False,
                        normalize_embeddings=True)
    return vecs.tolist()


def chunk_batches(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chunks_jsonl")
    parser.add_argument("slug")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--full-rebuild", action="store_true")
    args = parser.parse_args()

    chunks_path = Path(args.chunks_jsonl)
    if not chunks_path.exists():
        print(f"[L2-ERROR] chunks file not found: {chunks_path}", file=sys.stderr)
        sys.exit(1)

    # Leggi chunks
    chunks = []
    with open(chunks_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    chunks.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"[L2-WARN] skipping invalid JSON line: {e}", file=sys.stderr)

    if not chunks:
        print("[L2] No chunks to index", file=sys.stderr)
        sys.exit(0)

    print(f"[L2] Loading embedding model: {args.model} (~137MB first download)...")
    model = SentenceTransformer(args.model, trust_remote_code=True)
    model.max_seq_length = MAX_SEQ_LENGTH

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(db_path))

    TABLE_NAME = "code_chunks"

    # Full rebuild: recreate the table with fresh schema (mode="overwrite" = drop+create atomico)
    if args.full_rebuild:
        tbl = db.create_table(TABLE_NAME, schema=SCHEMA, mode="overwrite")
        print(f"[L2] Full rebuild: recreated table {TABLE_NAME}")
    elif TABLE_NAME not in db.list_tables():
        tbl = db.create_table(TABLE_NAME, schema=SCHEMA)
        print(f"[L2] Created table: {TABLE_NAME}")
    else:
        tbl = db.open_table(TABLE_NAME)

    # Embedding e insert/upsert in batch
    # Full rebuild: slug rows already deleted → use add (faster, no duplicate-key risk)
    # Incremental: use merge_insert for upsert semantics
    use_add = args.full_rebuild
    total = 0
    for batch in chunk_batches(chunks, BATCH_SIZE):
        texts = [f"{c.get('symbol', '')} {c.get('docstring', '')} {c.get('code', '')[:500]}"
                 for c in batch]
        vectors = embed_texts(model, texts, args.model)

        rows = []
        for c, vec in zip(batch, vectors):
            rows.append({
                "id": c["id"],
                "slug": args.slug,
                "file": c.get("file", ""),
                "symbol": c.get("symbol", ""),
                "type": c.get("type", ""),
                "language": c.get("language", ""),
                "start_line": int(c.get("start_line", 0)),
                "end_line": int(c.get("end_line", 0)),
                "code": c.get("code", "")[:4000],
                "docstring": c.get("docstring", "")[:500],
                "vector": vec,
            })

        if use_add:
            tbl.add(rows)
        else:
            tbl.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(rows)
        total += len(rows)
        print(f"[L2] Indexed {total}/{len(chunks)} chunks...", end="\r", file=sys.stderr)

    print(f"\n[L2] Indexing done: {total} chunks for slug={args.slug} in {args.db}")


if __name__ == "__main__":
    main()
