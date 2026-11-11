#!/usr/bin/env python3
"""Indice di ricerca SQLite FTS5 per la wiki: nessuna dipendenza oltre la libreria standard.

Un record per ogni sezione H2 di ogni pagina di `wiki/`. Colonne indicizzate: titolo
della pagina, heading della sezione, corpo. Colonne non indicizzate: percorso, sezione
della wiki (prima cartella sotto `wiki/`), stato del frontmatter, hash della pagina.

Uso:
    python3 tools/wiki-search/fts_index.py build [--full]
    python3 tools/wiki-search/fts_index.py search "<query>" [--top N] [--section S]
                                           [--status S] [--json] [--refresh]
    python3 tools/wiki-search/fts_index.py status

L'indice vive in `<root>/.wiki-search/fts.sqlite` (percorso configurabile con
`wiki_search.fts_db`). Se manca, `search` lo costruisce prima di rispondere; se una pagina
della wiki e' piu' recente dell'ultima costruzione, lo aggiorna in modo incrementale
(`--refresh` forza l'aggiornamento).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DB = ".wiki-search/fts.sqlite"
DEFAULT_TOP = 5
BM25_WEIGHTS = "10.0, 5.0, 1.0"  # title, heading, body
# Fonti, sessioni, report di lint e file in radice (log, gaps, index) contano meno delle
# pagine canoniche: senza questo peso le sessioni, molto più numerose, coprono i risultati.
# Il filtro --section resta il modo per cercare proprio lì.
SECONDARY_SECTIONS = ("sources", "sessions", "lint", "_root")
SECONDARY_WEIGHT = 0.5
SCHEMA_VERSION = "1"
_OPERATORS = {"AND", "OR", "NOT", "NEAR"}


# ---------------------------------------------------------------------------
# Radice e configurazione
# ---------------------------------------------------------------------------

def find_root(start: Optional[Path] = None) -> Path:
    """Risale da `start` (default: questo file) fino alla cartella con factory.config.yaml."""
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / "factory.config.yaml").is_file():
            return p
    return Path.cwd()


def load_wiki_search_config(root: Path) -> dict:
    cfg_file = root / "factory.config.yaml"
    if not cfg_file.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        block = data.get("wiki_search", {})
        return block if isinstance(block, dict) else {}
    except Exception:
        return {}


def db_path_for(root: Path, cfg: Optional[dict] = None) -> Path:
    cfg = load_wiki_search_config(root) if cfg is None else cfg
    rel = str(cfg.get("fts_db", DEFAULT_DB))
    p = Path(rel)
    return p if p.is_absolute() else root / p


def fts5_available() -> bool:
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        c.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Lettura delle pagine e chunking per H2
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> Tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    fm: dict = {}
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(raw)
        if isinstance(loaded, dict):
            fm = loaded
    except Exception:
        # senza PyYAML o con YAML non valido: solo le coppie chiave: valore semplici
        for line in raw.splitlines():
            m = re.match(r"^(\w[\w-]*):\s*(.+?)\s*$", line)
            if m:
                fm[m.group(1)] = m.group(2).strip("'\"")
    return fm, body


def split_h2(body: str) -> List[Tuple[str, str]]:
    """Divide il corpo in (heading, testo). Gli `##` dentro i blocchi di codice non contano.

    Il testo prima del primo H2 ha heading vuoto.
    """
    sections: List[Tuple[str, List[str]]] = [("", [])]
    fence = ""
    for line in body.splitlines():
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)[0]
            if not fence:
                fence = marker
            elif fence == marker:
                fence = ""
        h = re.match(r"^## +(.+?)\s*#*\s*$", line) if not fence else None
        if h:
            sections.append((h.group(1).strip(), []))
        else:
            sections[-1][1].append(line)
    out = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if text or heading:
            out.append((heading, text))
    return out


def read_pages(wiki_dir: Path) -> Dict[str, dict]:
    """Ritorna {percorso relativo a root: {hash, mtime, title, status, section, chunks}}."""
    pages: Dict[str, dict] = {}
    root = wiki_dir.parent
    for md in sorted(wiki_dir.rglob("*.md")):
        try:
            data = md.read_bytes()
            text = data.decode("utf-8", errors="replace")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        rel = md.relative_to(root).as_posix()
        parts = md.relative_to(wiki_dir).parts
        section = parts[0] if len(parts) > 1 else "_root"
        title = str(fm.get("title") or md.stem.replace("-", " ").title())
        status = str(fm.get("status") or "unknown")
        pages[rel] = {
            "hash": hashlib.sha256(data).hexdigest(),
            "mtime": md.stat().st_mtime,
            "title": title,
            "status": status,
            "section": section,
            "chunks": split_h2(body),
        }
    return pages


# ---------------------------------------------------------------------------
# Indice
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS pages(path TEXT PRIMARY KEY, hash TEXT NOT NULL, mtime REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    title, heading, body,
    path UNINDEXED, section UNINDEXED, status UNINDEXED, page_hash UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2',
    prefix = '2 3'
);
"""


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def _drop_all(conn: sqlite3.Connection) -> None:
    conn.executescript("DROP TABLE IF EXISTS fts; DROP TABLE IF EXISTS pages; DROP TABLE IF EXISTS meta;")


def build(root: Path, full: bool = False, db: Optional[Path] = None) -> dict:
    """Costruisce o aggiorna l'indice. Ritorna un riepilogo con i contatori."""
    if not fts5_available():
        raise RuntimeError("SQLite senza il modulo FTS5: backend fts5 non utilizzabile")
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"cartella wiki non trovata: {wiki_dir}")
    db = db or db_path_for(root)
    t0 = time.perf_counter()
    pages = read_pages(wiki_dir)
    conn = _connect(db)
    try:
        if not full:
            row = None
            try:
                row = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            except sqlite3.Error:
                pass
            if row is None or row["value"] != SCHEMA_VERSION:
                full = True
        if full:
            _drop_all(conn)
        conn.executescript(_DDL)
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema', ?)", (SCHEMA_VERSION,))
        known = {r["path"]: r["hash"] for r in conn.execute("SELECT path, hash FROM pages")}
        added = changed = unchanged = 0
        for rel, pg in pages.items():
            if rel in known and known[rel] == pg["hash"]:
                unchanged += 1
                continue
            if rel in known:
                changed += 1
                conn.execute("DELETE FROM fts WHERE path = ?", (rel,))
            else:
                added += 1
            for heading, text in pg["chunks"]:
                conn.execute(
                    "INSERT INTO fts(title, heading, body, path, section, status, page_hash) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (pg["title"], heading, text, rel, pg["section"], pg["status"], pg["hash"]),
                )
            conn.execute(
                "INSERT OR REPLACE INTO pages(path, hash, mtime) VALUES (?,?,?)",
                (rel, pg["hash"], pg["mtime"]),
            )
        removed = 0
        for rel in set(known) - set(pages):
            conn.execute("DELETE FROM fts WHERE path = ?", (rel,))
            conn.execute("DELETE FROM pages WHERE path = ?", (rel,))
            removed += 1
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('built_at', ?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"),),
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('max_mtime', ?)",
            (repr(max((pg["mtime"] for pg in pages.values()), default=0.0)),),
        )
        conn.commit()
        chunks = conn.execute("SELECT count(*) FROM fts").fetchone()[0]
    finally:
        conn.close()
    return {
        "full": full,
        "pages": len(pages),
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": unchanged,
        "reindexed": added + changed,
        "chunks": chunks,
        "seconds": round(time.perf_counter() - t0, 3),
        "db": str(db),
    }


def wiki_max_mtime(wiki_dir: Path) -> float:
    """Mtime piu' recente fra i .md della wiki (solo stat, nessuna lettura dei file)."""
    best = 0.0
    for md in wiki_dir.rglob("*.md"):
        try:
            best = max(best, md.stat().st_mtime)
        except OSError:
            continue
    return best


def is_stale(root: Path, db: Path) -> bool:
    """True se una pagina della wiki e' piu' recente dell'ultima costruzione dell'indice."""
    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        return False
    try:
        conn = _connect(db)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='max_mtime'").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return True
    if row is None:
        return True  # indice costruito prima che il valore fosse salvato
    try:
        saved = float(row["value"])
    except ValueError:
        return True
    return wiki_max_mtime(wiki_dir) > saved


def normalize_terms(query: str) -> List[str]:
    """Estrae i termini alfanumerici; scarta gli operatori FTS scritti dall'utente."""
    terms = re.findall(r"\w+", query, flags=re.UNICODE)
    return [t for t in terms if t.upper() not in _OPERATORS]


def to_match(terms: List[str], joiner: str = " ") -> str:
    """Ogni termine come prefisso tra virgolette: "term"*. Le virgolette sono già rimosse."""
    return joiner.join('"%s"*' % t.replace('"', "") for t in terms)


def search(
    root: Path,
    query: str,
    top: int = DEFAULT_TOP,
    section: Optional[str] = None,
    status: Optional[str] = None,
    db: Optional[Path] = None,
    refresh: bool = False,
) -> dict:
    """Ricerca. Se l'indice manca lo costruisce. Ritorna {results, mode, built}."""
    db = db or db_path_for(root)
    built = None
    # aggiornamento incrementale automatico: l'indice e' piu' vecchio di una pagina della wiki
    if not db.is_file() or refresh or is_stale(root, db):
        built = build(root, full=False, db=db)
    terms = normalize_terms(query)
    if not terms:
        return {"results": [], "mode": "empty", "built": built}
    conn = _connect(db)
    try:
        def run(match: str) -> list:
            sql = (
                "SELECT path, title, heading, section, status, "
                "bm25(fts, %s) * CASE WHEN section IN (%s) THEN %s ELSE 1.0 END AS rank, "
                "snippet(fts, 2, '[', ']', '…', 24) AS snip "
                "FROM fts WHERE fts MATCH ?"
                % (BM25_WEIGHTS, ", ".join("?" * len(SECONDARY_SECTIONS)), SECONDARY_WEIGHT)
            )
            args: list = list(SECONDARY_SECTIONS) + [match]
            if section:
                sql += " AND section = ?"
                args.append(section)
            if status:
                sql += " AND status = ?"
                args.append(status)
            sql += " ORDER BY rank LIMIT ?"
            args.append(int(top) * 8)
            # una riga per pagina: la sezione col punteggio migliore
            seen, out = set(), []
            for r in conn.execute(sql, args):
                if r["path"] in seen:
                    continue
                seen.add(r["path"])
                out.append(r)
                if len(out) == int(top):
                    break
            return out

        mode = "and"
        rows = run(to_match(terms, " "))
        if not rows and len(terms) > 1:
            mode = "or"
            rows = run(to_match(terms, " OR "))
    finally:
        conn.close()
    results = [
        {
            "path": r["path"],
            "title": r["title"],
            "section": r["heading"] or "_root",
            "wiki_section": r["section"],
            "status": r["status"],
            "score": round(-r["rank"], 4),
            "snippet": re.sub(r"\s+", " ", r["snip"]).strip(),
        }
        for r in rows
    ]
    return {"results": results, "mode": mode, "built": built}


def status(root: Path, db: Optional[Path] = None) -> dict:
    db = db or db_path_for(root)
    if not db.is_file():
        return {"exists": False, "db": str(db)}
    conn = _connect(db)
    try:
        chunks = conn.execute("SELECT count(*) FROM fts").fetchone()[0]
        pages = conn.execute("SELECT count(*) FROM pages").fetchone()[0]
        built = conn.execute("SELECT value FROM meta WHERE key='built_at'").fetchone()
    finally:
        conn.close()
    return {
        "exists": True,
        "db": str(db),
        "pages": pages,
        "chunks": chunks,
        "built_at": built["value"] if built else None,
        "size_kb": round(db.stat().st_size / 1024, 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Indice FTS5 della wiki")
    ap.add_argument("--root", help="radice factory (default: ricavata da factory.config.yaml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build", help="costruisce o aggiorna l'indice")
    pb.add_argument("--full", action="store_true", help="ricostruzione completa")
    ps = sub.add_parser("search", help="cerca nella wiki")
    ps.add_argument("query")
    ps.add_argument("--top", type=int, default=DEFAULT_TOP)
    ps.add_argument("--section", help="prima cartella sotto wiki/ (es. decisions)")
    ps.add_argument("--status", help="stato del frontmatter (es. approved)")
    ps.add_argument("--json", action="store_true")
    ps.add_argument("--refresh", action="store_true", help="aggiorna l'indice prima di cercare")
    sub.add_parser("status", help="stato dell'indice")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass
    root = Path(args.root).resolve() if args.root else find_root()

    try:
        if args.cmd == "build":
            info = build(root, full=args.full)
            print(
                "indice %s: %d pagine, %d chunk, %d reindicizzate (+%d, ~%d, -%d) in %.2fs"
                % ("ricostruito" if info["full"] else "aggiornato", info["pages"], info["chunks"],
                   info["reindexed"], info["added"], info["changed"], info["removed"], info["seconds"])
            )
            print("db: %s" % info["db"])
        elif args.cmd == "search":
            out = search(root, args.query, args.top, args.section, args.status, refresh=args.refresh)
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                if out["built"]:
                    print("(indice costruito: %d chunk in %.2fs)" % (out["built"]["chunks"], out["built"]["seconds"]))
                if not out["results"]:
                    print('Nessun risultato per "%s".' % args.query)
                for i, r in enumerate(out["results"], 1):
                    print("%d. %s §%s  (score %.2f, %s)" % (i, r["path"], r["section"], r["score"], r["status"]))
                    print("   %s" % r["snippet"])
        else:
            print(json.dumps(status(root), ensure_ascii=False, indent=2))
    except (RuntimeError, FileNotFoundError) as exc:
        print("errore: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
