"""
Hybrid semantic + full-text search on LanceDB index (EP-042, US-149).

Invariants:
    R.WS1 — Guaranteed fallback: missing index / disabled / import fail →
             {"results": [], "fallback": True}  (never exception to user)
    R.WS2 — Lazy import: lancedb and sentence_transformers never imported at
             module level; the module is importable without dependencies.
    R.WS3 — Read-only: no index writes during search().

Public API:
    SearchResult (dataclass)
    HybridSearcher (class)
    search_wiki(query, index_path, top_k) -> list[SearchResult]  # convenience
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ---------------------------------------------------------------------------
# Default config values — used if wiki_search: block is missing in
# factory.config.yaml (or if the file does not exist).
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_INDEX_PATH = ".wiki-search/index.lance"
DEFAULT_TABLE = "pages"
DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_K = 20
DEFAULT_TOP_K = 5
SNIPPET_LEN = 200


# ---------------------------------------------------------------------------
# Selezione del backend
# ---------------------------------------------------------------------------

def _hybrid_deps_importable() -> bool:
    """True se lancedb e sentence_transformers sono installati (senza importarli)."""
    import importlib.util

    try:
        return all(
            importlib.util.find_spec(m) is not None
            for m in ("lancedb", "sentence_transformers")
        )
    except Exception:
        return False


def resolve_backend(configured: str = "auto") -> str:
    """auto → hybrid se le dipendenze ci sono, altrimenti fts5. Valore sconosciuto → auto."""
    configured = (configured or "auto").strip().lower()
    if configured in ("fts5", "hybrid"):
        return configured
    return "hybrid" if _hybrid_deps_importable() else "fts5"


def _fts_find_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "factory.config.yaml").is_file():
            return p
    return Path.cwd()


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result returned by HybridSearcher."""

    path: str
    title: str
    section: str
    score: float
    snippet: str    # ~200 chars around best FTS match in content
    type: str
    status: str


# ---------------------------------------------------------------------------
# HybridSearcher
# ---------------------------------------------------------------------------

class HybridSearcher:
    """
    Hybrid semantic + full-text search on LanceDB index.

    Invariant R.WS1: if index does not exist → returns empty list
    (graceful fallback).
    Invariant R.WS3: no index modification during search.
    """

    def __init__(self, config_path: str = None):
        """
        Read wiki_search: block from factory.config.yaml.
        If config_path=None, walk up from cwd until file is found.
        Hard-coded defaults if block is missing.
        Opens LanceDB 'pages' table read-only (R.WS3).
        Lazily loads embedding model (no import at class level).
        On error (missing index, lancedb not installed,
        model load failed): sets self._fallback = True, no exception.
        """
        self._fallback: bool = False
        self._table = None
        self._model = None
        self._root: Optional[Path] = None
        self._backend: str = "hybrid"

        # Load wiki_search config block
        cfg = self._load_config(config_path)
        self._enabled: bool = bool(cfg.get("enabled", False))
        self._index_path: str = str(cfg.get("index_path", DEFAULT_INDEX_PATH))
        self._table_name: str = str(cfg.get("index_table", DEFAULT_TABLE))
        self._model_name: str = str(cfg.get("embedding_model", DEFAULT_MODEL))
        self._rrf_k: int = int(cfg.get("rrf_k", DEFAULT_RRF_K))
        self._candidate_k: int = int(cfg.get("candidate_k", DEFAULT_CANDIDATE_K))
        self._default_mode: str = str(cfg.get("mode", "hybrid"))
        # ADR-C (TSK-504): chunking strategy — read from config, passed to WikiIndexer
        # at index-build time (R.WS2: default h2_section for backward compat)
        self._chunking_strategy: str = str(cfg.get("chunking", "h2_section"))

        self._fts_db: str = str(cfg.get("fts_db", ".wiki-search/fts.sqlite"))

        if not self._enabled:
            # enabled: false → immediate fallback (R.WS1, R.WS2: no import)
            self._fallback = True
            return

        configured = str(cfg.get("backend", "auto")).strip().lower()
        self._backend = resolve_backend(configured)
        if self._backend == "hybrid" and configured not in ("hybrid", "fts5"):
            # backend auto: le librerie ci sono ma l'indice .lance potrebbe mancare
            self._init_table()
            if self._fallback or self._table is None:
                self._fallback = False
                self._table = None
                self._backend = "fts5"
        if self._backend == "fts5":
            # nessuna dipendenza: l'indice SQLite si costruisce alla prima ricerca
            if self._root is None:
                self._root = _fts_find_root()
            return

        if self._table is None and not self._fallback:
            self._init_table()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self, config_path: Optional[str]) -> dict:
        """
        Load wiki_search: block from factory.config.yaml.
        Walk up from cwd if config_path=None.
        Returns {} on error (never raises).
        """
        if config_path is not None:
            # config_path may be the YAML file or its directory
            p = Path(config_path)
            if p.is_dir():
                candidates = [p / "factory.config.yaml"]
            else:
                candidates = [p]
        else:
            current = Path.cwd()
            candidates = [
                ancestor / "factory.config.yaml"
                for ancestor in [current, *current.parents]
            ]

        config_file: Optional[Path] = None
        for c in candidates:
            if c.exists() and c.is_file():
                config_file = c
                break

        if config_file is None:
            log.debug("factory.config.yaml non trovato; uso valori di default")
            return {}
        self._root = config_file.resolve().parent

        try:
            import yaml  # pyyaml — available in most environments

            raw = config_file.read_text(encoding="utf-8")
            full_cfg = yaml.safe_load(raw) or {}
            wiki_cfg = full_cfg.get("wiki_search", {})
            log.debug("Config wiki_search caricata da %s", config_file)
            return wiki_cfg if isinstance(wiki_cfg, dict) else {}
        except Exception as exc:
            log.debug("Errore parse config (%s): %s", config_file, exc)
            return {}

    # ------------------------------------------------------------------
    # LanceDB table init
    # ------------------------------------------------------------------

    def _init_table(self) -> None:
        """
        Open LanceDB table read-only.
        Sets _fallback=True on any error (R.WS1).
        """
        try:
            import lancedb  # lazy import — R.WS2
        except ImportError:
            log.debug("lancedb non installato; fallback a scan lineare")
            self._fallback = True
            return

        index_path = Path(self._index_path)
        if not index_path.exists():
            log.debug(
                "Indice non trovato in %s; fallback a scan lineare", index_path
            )
            self._fallback = True
            return

        try:
            db = lancedb.connect(str(index_path))
            if self._table_name not in db.table_names():
                log.debug(
                    "Tabella '%s' assente nell'indice %s; fallback",
                    self._table_name,
                    index_path,
                )
                self._fallback = True
                return
            # R.WS3: open read-only (no subsequent write calls)
            self._table = db.open_table(self._table_name)
        except Exception as exc:
            log.debug("Impossibile aprire tabella LanceDB: %s", exc)
            self._fallback = True

    # ------------------------------------------------------------------
    # Embedding model (lazy)
    # ------------------------------------------------------------------

    def _ensure_model(self) -> bool:
        """
        Load sentence-transformers model lazily.
        Returns False (and sets _fallback) on error.
        """
        if self._model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer  # lazy — R.WS2

            self._model = SentenceTransformer(self._model_name)
            return True
        except Exception as exc:
            log.debug(
                "Caricamento modello embedding '%s' fallito: %s",
                self._model_name,
                exc,
            )
            self._fallback = True
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if index exists and is readable."""
        if self._backend == "fts5" and self._enabled:
            try:
                import fts_index  # type: ignore

                return fts_index.fts5_available()
            except Exception:
                return False
        return not self._fallback and self._table is not None

    def _search_fts5(self, query: str, top_k: int, filters: Optional[dict]) -> dict:
        """Backend SQLite FTS5. Costruisce l'indice se manca. Mai eccezioni verso il chiamante."""
        try:
            import fts_index  # type: ignore

            filters = filters or {}
            out = fts_index.search(
                self._root or fts_index.find_root(),
                query,
                top=top_k,
                section=filters.get("section"),
                status=filters.get("status"),
                db=None,
            )
            results = [
                {
                    "path": r["path"],
                    "title": r["title"],
                    "section": r["section"],
                    "score": r["score"],
                    "snippet": r["snippet"],
                    "type": "",
                    "status": r["status"],
                }
                for r in out["results"]
            ]
            return {"results": results, "fallback": False}
        except Exception as exc:
            log.warning("Errore backend fts5: %s", exc)
            return {"results": [], "fallback": True}

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        mode: str = "hybrid",
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Hybrid search: vector + full-text with RRF (k=60).
        If index unavailable → returns {"results": [], "fallback": True}
        (R.WS1).

        Args:
            query:   query text
            top_k:   number of results to return (default 5)
            mode:    "hybrid" (default) | "vector" | "fts"
            filters: metadata filter dict, applied pre-rerank on
                     both branches (push-down). E.g. {"type": "concept"}.

        Returns:
            {
              "results": [
                {path, title, section, score, snippet, type, status},
                ...
              ],
              "fallback": bool
            }
        """
        if not self._enabled:
            return {"results": [], "fallback": True}
        if self._backend == "fts5":
            return self._search_fts5(query, top_k, filters)
        if self._fallback:
            return {"results": [], "fallback": True}

        where_clause = self._build_where(filters)
        candidate_k = self._candidate_k

        try:
            if mode == "vector":
                if not self._ensure_model():
                    return {"results": [], "fallback": True}
                query_emb = self._model.encode(
                    [query], normalize_embeddings=True
                )[0].tolist()
                raw = self._vector_search(query_emb, candidate_k, where_clause)
                ranked = [
                    {**r, "_score": 1.0 / (1 + i)} for i, r in enumerate(raw)
                ]

            elif mode == "fts":
                raw = self._fts_search(query, candidate_k, where_clause)
                ranked = [
                    {**r, "_score": 1.0 / (1 + i)} for i, r in enumerate(raw)
                ]

            else:  # "hybrid" (default)
                if not self._ensure_model():
                    return {"results": [], "fallback": True}
                query_emb = self._model.encode(
                    [query], normalize_embeddings=True
                )[0].tolist()
                vector_results = self._vector_search(
                    query_emb, candidate_k, where_clause
                )
                fts_results = self._fts_search(query, candidate_k, where_clause)
                ranked = self._rrf(vector_results, fts_results, k=self._rrf_k)

            top = ranked[:top_k]
            results = [
                {
                    "path": r.get("path", ""),
                    "title": r.get("title", ""),
                    "section": r.get("section", ""),
                    "score": float(r.get("_score", 0.0)),
                    "snippet": self._extract_snippet(
                        r.get("content", ""), query
                    ),
                    "type": r.get("type", ""),
                    "status": r.get("status", ""),
                }
                for r in top
            ]
            return {"results": results, "fallback": False}

        except Exception as exc:
            log.warning("Errore durante la ricerca: %s", exc)
            return {"results": [], "fallback": True}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_where(self, filters: Optional[dict]) -> Optional[str]:
        """
        Translate a filter dict into a LanceDB WHERE clause.
        Returns None if filters is empty or None.
        """
        if not filters:
            return None
        clauses: list[str] = []
        for key, value in filters.items():
            if isinstance(value, str):
                clauses.append(f"{key} = '{value}'")
            elif isinstance(value, bool):
                clauses.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, (int, float)):
                clauses.append(f"{key} = {value}")
            elif isinstance(value, list):
                quoted = ", ".join(f"'{v}'" for v in value)
                clauses.append(f"{key} IN ({quoted})")
        return " AND ".join(clauses) if clauses else None

    def _vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        where_clause: Optional[str] = None,
    ) -> list[dict]:
        """
        Vector search on LanceDB (cosine similarity).
        Returns empty list on error.
        """
        try:
            q = (
                self._table.search(query_embedding)
                .limit(top_k)
                .metric("cosine")
            )
            if where_clause:
                q = q.where(where_clause, prefilter=True)
            return q.to_list()
        except Exception as exc:
            log.debug("Vector search fallita: %s", exc)
            return []

    def _fts_search(
        self,
        query: str,
        top_k: int,
        where_clause: Optional[str] = None,
    ) -> list[dict]:
        """
        Full-text search on LanceDB (uses tantivy if available).
        Fallback: term-frequency scan if tantivy is not indexed.
        """
        # Attempt 1: native FTS (tantivy index, query_type="fts")
        try:
            q = self._table.search(query, query_type="fts").limit(top_k)
            if where_clause:
                q = q.where(where_clause, prefilter=True)
            return q.to_list()
        except Exception as fts_exc:
            log.debug(
                "FTS nativo non disponibile (%s); fallback a scan TF",
                fts_exc,
            )

        # Fallback: term-frequency scan (no tantivy index required)
        try:
            return self._fts_scan_fallback(query, top_k, where_clause)
        except Exception as scan_exc:
            log.debug("FTS scan fallback fallito: %s", scan_exc)
            return []

    def _fts_scan_fallback(
        self,
        query: str,
        top_k: int,
        where_clause: Optional[str],
    ) -> list[dict]:
        """
        FTS fallback via term-frequency scan when tantivy is not
        available. Does not require additional LanceDB indexes.
        """
        terms = query.lower().split()
        if not terms:
            return []

        q = self._table.search()
        if where_clause:
            q = q.where(where_clause)
        all_rows = q.to_list()

        scored: list[dict] = []
        for row in all_rows:
            haystack = (
                (row.get("content") or "") + " " + (row.get("title") or "")
            ).lower()
            score = sum(haystack.count(t) for t in terms)
            if score > 0:
                scored.append({**row, "_tf_score": score})

        scored.sort(key=lambda r: r["_tf_score"], reverse=True)
        return scored[:top_k]

    def _rrf(
        self,
        vector_results: list[dict],
        fts_results: list[dict],
        k: int = DEFAULT_RRF_K,
    ) -> list[dict]:
        """
        Reciprocal Rank Fusion: combine two ranked lists.

        score_rrf(doc) = sum(1 / (k + rank_i(doc)))

        where rank_i is the 1-based position of the document in the i-th list
        (0-based in array → rank+1). Only branches where the document
        appears contribute to the score.
        """
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for rank, row in enumerate(vector_results):
            doc_id = row.get("id") or f"vec-{rank}"
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            docs[doc_id] = row

        for rank, row in enumerate(fts_results):
            doc_id = row.get("id") or f"fts-{rank}"
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = row

        sorted_ids = sorted(scores, key=lambda d: scores[d], reverse=True)
        merged: list[dict] = []
        for doc_id in sorted_ids:
            row = dict(docs[doc_id])
            row["_score"] = scores[doc_id]
            merged.append(row)
        return merged

    def _extract_snippet(
        self, content: str, query: str, length: int = SNIPPET_LEN
    ) -> str:
        """
        Extract ~200 chars around best FTS match in content.
        Fallback: head of content for vector-only hits (no term
        found in content).
        """
        if not content:
            return ""

        content_lower = content.lower()
        best_pos = -1
        for term in query.lower().split():
            pos = content_lower.find(term)
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            # Vector-only hit: return head of content
            snippet = content[:length]
        else:
            # Center window around match
            start = max(0, best_pos - length // 3)
            end = min(len(content), start + length)
            snippet = content[start:end]

        # Normalize whitespace
        return re.sub(r"\s+", " ", snippet).strip()


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def search_wiki(
    query: str,
    index_path: str = ".wiki-search",
    top_k: int = DEFAULT_TOP_K,
) -> list[SearchResult]:
    """
    Simple entry point for use from wiki-query agent.

    Creates a HybridSearcher reading factory.config.yaml from cwd (walk-up).
    If index is unavailable via config but index_path is explicitly
    provided, attempts to use it as direct override.
    Returns [] without exceptions if index is unavailable (R.WS1).

    Args:
        query:      query text
        index_path: path to LanceDB directory (default ".wiki-search");
                    ignored if factory.config.yaml contains wiki_search.index_path
        top_k:      number of results (default 5)

    Returns:
        list[SearchResult]  — empty list if fallback active
    """
    searcher = HybridSearcher()

    # If config-driven init is in fallback but user provided an
    # explicit non-default index_path, attempt direct override.
    if searcher._fallback and index_path != ".wiki-search":
        lance_path = (
            index_path
            if index_path.endswith(".lance")
            else str(Path(index_path) / "index.lance")
        )
        searcher._index_path = lance_path
        searcher._enabled = True
        searcher._fallback = False
        searcher._init_table()

    result = searcher.search(query, top_k=top_k)
    return [
        SearchResult(
            path=r["path"],
            title=r["title"],
            section=r["section"],
            score=r["score"],
            snippet=r["snippet"],
            type=r.get("type", ""),
            status=r.get("status", ""),
        )
        for r in result.get("results", [])
    ]
