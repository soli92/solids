"""
Hybrid semantic + full-text search su indice LanceDB (EP-042, US-149).

Invarianti:
    R.WS1 — Fallback garantito: index assente / disabled / import fail →
             {"results": [], "fallback": True}  (mai eccezione verso l'utente)
    R.WS2 — Import lazy: lancedb e sentence_transformers mai importati a
             livello di modulo; il modulo è importabile senza le dipendenze.
    R.WS3 — Read-only: nessun write sull'indice durante search().

Public API:
    SearchResult (dataclass)
    HybridSearcher (class)
    search_wiki(query, index_path, top_k) -> list[SearchResult]  # convenience
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default config values — usati se il blocco wiki_search: manca in
# factory.config.yaml (o se il file non esiste).
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_INDEX_PATH = ".wiki-search/index.lance"
DEFAULT_TABLE = "pages"
DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_K = 20
DEFAULT_TOP_K = 5
SNIPPET_LEN = 200


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """Un singolo risultato di ricerca restituito da HybridSearcher."""

    path: str
    title: str
    section: str
    score: float
    snippet: str    # ~200 char attorno al miglior match FTS in content
    type: str
    status: str


# ---------------------------------------------------------------------------
# HybridSearcher
# ---------------------------------------------------------------------------

class HybridSearcher:
    """
    Hybrid semantic + full-text search su indice LanceDB.

    Invariante R.WS1: se l'indice non esiste → ritorna lista vuota
    (fallback graceful).
    Invariante R.WS3: nessuna modifica all'indice durante la ricerca.
    """

    def __init__(self, config_path: str = None):
        """
        Legge il blocco wiki_search: da factory.config.yaml.
        Se config_path=None, risale da cwd finché trova il file.
        Valori di default hard-coded se il blocco manca.
        Apre la tabella LanceDB 'pages' in read-only (R.WS3).
        Carica lazy il modello embedding (no import a livello di classe).
        In caso di errore (index assente, lancedb non installato,
        load modello fallito): imposta self._fallback = True, nessuna eccezione.
        """
        self._fallback: bool = False
        self._table = None
        self._model = None

        # Load wiki_search config block
        cfg = self._load_config(config_path)
        self._enabled: bool = bool(cfg.get("enabled", False))
        self._index_path: str = str(cfg.get("index_path", DEFAULT_INDEX_PATH))
        self._table_name: str = str(cfg.get("index_table", DEFAULT_TABLE))
        self._model_name: str = str(cfg.get("embedding_model", DEFAULT_MODEL))
        self._rrf_k: int = int(cfg.get("rrf_k", DEFAULT_RRF_K))
        self._candidate_k: int = int(cfg.get("candidate_k", DEFAULT_CANDIDATE_K))
        self._default_mode: str = str(cfg.get("mode", "hybrid"))

        if not self._enabled:
            # enabled: false → fallback immediato (R.WS1, R.WS2: no import)
            self._fallback = True
            return

        self._init_table()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self, config_path: Optional[str]) -> dict:
        """
        Carica il blocco wiki_search: da factory.config.yaml.
        Risale da cwd se config_path=None.
        Ritorna {} in caso di errore (mai eccezione).
        """
        if config_path is not None:
            # config_path può essere il file YAML o la sua directory
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

        try:
            import yaml  # pyyaml — disponibile nella maggior parte degli env

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
        Apre la tabella LanceDB in read-only.
        Imposta _fallback=True su qualsiasi errore (R.WS1).
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
            # R.WS3: apre in sola lettura (nessuna chiamata di scrittura successiva)
            self._table = db.open_table(self._table_name)
        except Exception as exc:
            log.debug("Impossibile aprire tabella LanceDB: %s", exc)
            self._fallback = True

    # ------------------------------------------------------------------
    # Embedding model (lazy)
    # ------------------------------------------------------------------

    def _ensure_model(self) -> bool:
        """
        Carica il modello sentence-transformers in modo lazy.
        Ritorna False (e imposta _fallback) in caso di errore.
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
        """Controlla se l'indice esiste ed è leggibile."""
        return not self._fallback and self._table is not None

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        mode: str = "hybrid",
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Hybrid search: vector + full-text con RRF (k=60).
        Se indice non disponibile → ritorna {"results": [], "fallback": True}
        (R.WS1).

        Args:
            query:   testo della query
            top_k:   numero di risultati da restituire (default 5)
            mode:    "hybrid" (default) | "vector" | "fts"
            filters: dict di filtri su metadati, applicati pre-rerank su
                     entrambi i rami (push-down). Es. {"type": "concept"}.

        Returns:
            {
              "results": [
                {path, title, section, score, snippet, type, status},
                ...
              ],
              "fallback": bool
            }
        """
        if self._fallback or not self._enabled:
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
        Traduce un dict di filtri in una clausola WHERE LanceDB.
        Ritorna None se filters è vuoto o None.
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
        Ricerca vettoriale su LanceDB (similarità coseno).
        Ritorna lista vuota in caso di errore.
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
        Full-text search su LanceDB (usa tantivy se disponibile).
        Fallback: scan con term-frequency se tantivy non è indicizzato.
        """
        # Tentativo 1: FTS nativo (tantivy index, query_type="fts")
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

        # Fallback: scan term-frequency (nessun indice tantivy richiesto)
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
        Fallback FTS via scansione con term-frequency quando tantivy non è
        disponibile. Non richiede indici aggiuntivi su LanceDB.
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
        Reciprocal Rank Fusion: combina due ranked lists.

        score_rrf(doc) = sum(1 / (k + rank_i(doc)))

        dove rank_i è la posizione 1-based del documento nella lista i-esima
        (0-based nell'array → rank+1).  Solo i rami in cui il documento
        compare contribuiscono al punteggio.
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
        Estrai ~200 char attorno al miglior match FTS in content.
        Fallback: testa di content per hit solo-vettoriali (nessun termine
        trovato nel content).
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
            # Hit solo-vettoriale: restituisce testa del content
            snippet = content[:length]
        else:
            # Centra la finestra attorno al match
            start = max(0, best_pos - length // 3)
            end = min(len(content), start + length)
            snippet = content[start:end]

        # Normalizza whitespace
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
    Entry point semplice per uso da wiki-query agent.

    Crea un HybridSearcher leggendo factory.config.yaml dalla cwd (walk-up).
    Se l'indice non è disponibile tramite config ma index_path è esplicitamente
    fornito, tenta di usarlo come override diretto.
    Ritorna [] senza eccezioni se l'indice non è disponibile (R.WS1).

    Args:
        query:      testo della query
        index_path: path alla directory LanceDB (default ".wiki-search");
                    ignorato se factory.config.yaml contiene wiki_search.index_path
        top_k:      numero di risultati (default 5)

    Returns:
        list[SearchResult]  — lista vuota se fallback attivo
    """
    searcher = HybridSearcher()

    # Se la config-driven init è in fallback ma l'utente ha fornito un
    # index_path esplicito non-default, tenta un override diretto.
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
