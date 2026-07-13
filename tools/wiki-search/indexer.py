"""
Core indexing logic: crawl wiki/, chunk by H2, embed, upsert LanceDB.

Public API (TSK-308 DoD):
    crawl_wiki(wiki_root: str) -> list[dict]
    chunk_h2(page: dict) -> list[dict]
    embed_batch(texts: list[str], model_name: str) -> list[list[float]]
    upsert_table(db_path: str, rows: list[dict]) -> None

Additional exports (convenience):
    WikiChunk (dataclass)
    WikiIndexer (class wrapper: crawl_and_chunk, embed_chunks, upsert, build)

Import contract (R.WS2): lancedb and sentence_transformers are imported ONLY
inside the functions that use them — never at module level.  The module is
importable on environments that have neither package installed; the functions
fail with ImportError only when actually called.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
CONTENT_CAP = 2000  # max chars per section chunk

# Files that receive type: "meta" regardless of frontmatter
_META_PATHS = {"gaps.md", "log.md"}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class WikiChunk:
    """One H2 section of a wiki page, ready for embedding and indexing."""
    id: str          # "<path>#<section-slug>"
    path: str        # relative to wiki root, e.g. "concepts/foo.md"
    title: str       # from frontmatter or filename
    section: str     # H2 heading text, or "_root" for pre-H2 intro
    content: str     # section body text (heading excluded, capped)
    type: str        # frontmatter `type`, "meta", or "unknown"
    status: str      # frontmatter `status` or "unknown"
    tags_json: str   # json.dumps(list) from frontmatter `tags` or "[]"


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with hyphens, strip edges."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9À-ɏ]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Frontmatter parser (no external dep — pure stdlib yaml via split on ---)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Return (frontmatter_dict, body_text).
    If no valid YAML frontmatter block is found, returns ({}, original text).
    """
    fm: dict = {}
    if not text.startswith("---"):
        return fm, text

    end = text.find("\n---", 3)
    if end < 0:
        return fm, text

    fm_raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    try:
        import yaml  # stdlib-only fallback: pyyaml is almost universally installed
        fm = yaml.safe_load(fm_raw) or {}
    except Exception as exc:
        log.debug("Frontmatter parse error: %s", exc)

    return fm, body


# ---------------------------------------------------------------------------
# Public function: crawl_wiki
# ---------------------------------------------------------------------------

def crawl_wiki(wiki_root: str) -> list[dict]:
    """
    Glob <wiki_root>/**/*.md, parse frontmatter YAML, return one dict per page.

    Each dict has keys:
        path       (str)  relative to wiki_root
        title      (str)  from frontmatter or filename
        type       (str)  frontmatter "type", "meta" for gaps.md/log.md, else "unknown"
        status     (str)  frontmatter "status" or "unknown"
        tags_json  (str)  json.dumps(list)
        raw_body   (str)  Markdown body with frontmatter stripped

    Files that have no frontmatter get type="unknown".
    wiki/gaps.md and wiki/log.md always get type="meta".
    """
    root = Path(wiki_root)
    pages: list[dict] = []

    for md_path in sorted(root.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception as exc:
            log.warning("Skipping %s: %s", md_path, exc)
            continue

        fm, body = _parse_frontmatter(text)
        rel = str(md_path.relative_to(root))

        # Determine type
        if md_path.name in _META_PATHS:
            doc_type = "meta"
        elif fm:
            doc_type = str(fm.get("type", "unknown"))
        else:
            doc_type = "unknown"

        title = str(fm.get("title", md_path.stem.replace("-", " ").title()))
        status = str(fm.get("status", "unknown"))
        raw_tags = fm.get("tags", [])
        tags_json = json.dumps(raw_tags if isinstance(raw_tags, list) else [])

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
# Public function: chunk_h2
# ---------------------------------------------------------------------------

def chunk_h2(page: dict) -> list[dict]:
    """
    Split page["raw_body"] by H2 headings (^## ).

    Content before the first H2 → section="_root".
    Each section produces one dict:
        {id, path, title, section, content, type, status, tags_json}
    where id = "<path>#<section-slug>".

    Sections with empty content are skipped (except _root if it has text).
    content is capped at CONTENT_CAP characters.
    """
    path: str = page["path"]
    raw_body: str = page.get("raw_body", "")
    title: str = page["title"]
    doc_type: str = page["type"]
    status: str = page["status"]
    tags_json: str = page["tags_json"]

    # Split on ## headings
    parts = re.split(r"^## (.+)$", raw_body, flags=re.MULTILINE)
    # parts = [pre_h2_text, h2_title_1, h2_body_1, h2_title_2, h2_body_2, ...]

    chunks: list[dict] = []

    # Intro block (pre-first-H2)
    intro = parts[0].strip()
    if intro:
        section_id = f"{path}#_root"
        chunks.append({
            "id": section_id,
            "path": path,
            "title": title,
            "section": "_root",
            "content": intro[:CONTENT_CAP],
            "type": doc_type,
            "status": status,
            "tags_json": tags_json,
        })

    # H2 sections
    h2_titles = parts[1::2]
    h2_bodies = parts[2::2]

    for h2_title, h2_body in zip(h2_titles, h2_bodies):
        content = h2_body.strip()
        if not content:
            continue
        slug = _slugify(h2_title.strip()) or "section"
        section_id = f"{path}#{slug}"
        chunks.append({
            "id": section_id,
            "path": path,
            "title": title,
            "section": h2_title.strip(),
            "content": content[:CONTENT_CAP],
            "type": doc_type,
            "status": status,
            "tags_json": tags_json,
        })

    return chunks


# ---------------------------------------------------------------------------
# Public function: embed_batch
# ---------------------------------------------------------------------------

def embed_batch(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
) -> list[list[float]]:
    """
    Lazily load SentenceTransformer(model_name) and embed texts.

    Returns a list of float vectors (each EMBEDDING_DIM = 384 elements).
    Raises ImportError if sentence-transformers is not installed.
    """
    try:
        from sentence_transformers import SentenceTransformer  # lazy import — R.WS2
    except ImportError:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Run: pip install -e '.[wiki-search]'"
        )

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# Public function: upsert_table
# ---------------------------------------------------------------------------

def upsert_table(db_path: str, rows: list[dict]) -> None:
    """
    Open or create LanceDB table 'pages' at <db_path> and upsert <rows>.

    Table schema (created on first call if missing):
        id         str
        path       str
        title      str
        section    str
        content    str
        type       str
        status     str
        tags_json  str
        embedding  vector(384)   — field name "embedding", dim EMBEDDING_DIM

    Upsert strategy: delete existing rows with same id, then add.
    Raises ImportError if lancedb is not installed.
    """
    if not rows:
        return

    try:
        import lancedb  # lazy import — R.WS2
    except ImportError:
        raise ImportError(
            "lancedb is not installed. "
            "Run: pip install -e '.[wiki-search]'"
        )

    Path(db_path).mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(db_path)

    if "pages" not in db.table_names():
        db.create_table("pages", data=rows)
        return

    table = db.open_table("pages")
    ids = [r["id"] for r in rows]

    # Delete existing rows with matching ids, then add new ones.
    if len(ids) == 1:
        id_filter = f"id = '{ids[0]}'"
    else:
        quoted = ", ".join(f"'{i}'" for i in ids)
        id_filter = f"id IN ({quoted})"

    try:
        table.delete(id_filter)
    except Exception as exc:
        log.debug("Delete before upsert failed (may be empty table): %s", exc)

    table.add(rows)


# ---------------------------------------------------------------------------
# WikiIndexer — class wrapper (convenience, used by build-index.py / update-index.py)
# ---------------------------------------------------------------------------

class WikiIndexer:
    """
    High-level wrapper around the four public functions.

    Usage:
        indexer = WikiIndexer(wiki_root=Path("wiki"), index_path=Path(".wiki-search/index.lance"))
        n = indexer.build()
    """

    def __init__(
        self,
        wiki_root: Path,
        index_path: Path,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self.wiki_root = wiki_root
        self.index_path = index_path
        self.model_name = model_name

    # ------------------------------------------------------------------
    # crawl_and_chunk — returns list[WikiChunk]
    # ------------------------------------------------------------------

    def crawl_and_chunk(self, paths: Optional[list[Path]] = None) -> list[WikiChunk]:
        """
        Crawl wiki_root (or the provided path list) and chunk by H2.
        Returns a list of WikiChunk dataclass instances.
        """
        if paths is not None:
            # Convert explicit path list → per-page dicts via chunk_h2
            all_chunks: list[WikiChunk] = []
            root = self.wiki_root
            for md_path in paths:
                try:
                    text = md_path.read_text(encoding="utf-8")
                except Exception as exc:
                    log.warning("Skipping %s: %s", md_path, exc)
                    continue

                fm, body = _parse_frontmatter(text)
                try:
                    rel = str(md_path.relative_to(root))
                except ValueError:
                    rel = str(md_path)

                if md_path.name in _META_PATHS:
                    doc_type = "meta"
                elif fm:
                    doc_type = str(fm.get("type", "unknown"))
                else:
                    doc_type = "unknown"

                title = str(fm.get("title", md_path.stem.replace("-", " ").title()))
                status = str(fm.get("status", "unknown"))
                raw_tags = fm.get("tags", [])
                tags_json = json.dumps(raw_tags if isinstance(raw_tags, list) else [])

                page = {
                    "path": rel,
                    "title": title,
                    "type": doc_type,
                    "status": status,
                    "tags_json": tags_json,
                    "raw_body": body,
                }
                for chunk_dict in chunk_h2(page):
                    all_chunks.append(WikiChunk(**chunk_dict))
            return all_chunks

        pages = crawl_wiki(str(self.wiki_root))
        result: list[WikiChunk] = []
        for page in pages:
            for chunk_dict in chunk_h2(page):
                result.append(WikiChunk(**chunk_dict))
        return result

    # ------------------------------------------------------------------
    # embed_chunks — returns list[dict] ready for upsert
    # ------------------------------------------------------------------

    def embed_chunks(
        self,
        chunks: list[WikiChunk],
        batch_size: int = 64,
    ) -> list[dict]:
        """
        Embed chunks and return a list of dicts suitable for upsert_table.

        Each dict contains all WikiChunk fields plus "embedding" (list[float]).
        """
        rows: list[dict] = []
        texts = [
            f"{c.title} {c.section} {c.content}".strip()
            for c in chunks
        ]

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            embeddings = embed_batch(batch_texts, model_name=self.model_name)
            for chunk, emb in zip(chunks[i : i + batch_size], embeddings):
                rows.append({
                    "id": chunk.id,
                    "path": chunk.path,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "type": chunk.type,
                    "status": chunk.status,
                    "tags_json": chunk.tags_json,
                    "embedding": emb,
                })
        return rows

    # ------------------------------------------------------------------
    # upsert — delegates to module-level upsert_table
    # ------------------------------------------------------------------

    def upsert(self, rows: list[dict]) -> int:
        """Upsert rows into LanceDB. Returns number of rows upserted."""
        if not rows:
            return 0
        upsert_table(str(self.index_path), rows)
        return len(rows)

    # ------------------------------------------------------------------
    # build — full pipeline
    # ------------------------------------------------------------------

    def build(self, force_rebuild: bool = False) -> int:
        """
        Full build: crawl → chunk → embed → upsert.
        Returns the number of chunks written to the index.

        If force_rebuild=True, the existing index directory is deleted first.
        """
        if force_rebuild and self.index_path.exists():
            shutil.rmtree(self.index_path)
            log.info("Removed existing index at %s", self.index_path)

        chunks = self.crawl_and_chunk()
        if not chunks:
            log.warning("No chunks found under %s", self.wiki_root)
            return 0

        rows = self.embed_chunks(chunks)
        return self.upsert(rows)
