"""
tools/tutor/retrieval_tool.py

EP-045 retrieval tool — Phases 2 and 3 of retrieval-protocol.md.

Public API
----------
search_wiki(query, repo_root)           → list[wiki_citation]
search_codebase(query, repo_root)       → list[code_citation]
emit_gap_record(concept, original_query) → gap_record dict
_ep042_enabled(repo_root)               → bool  (semi-public for callers)

Schemas
-------
wiki_citation  = {source: str, section: str, excerpt?: str}
code_citation  = {file: str, function?: str, class?: str}
gap_record     = {concept: str, original_query: str, timestamp: str (ISO-8601 UTC)}

Design
------
- Python 3.10+ stdlib only (subprocess, pathlib, json, re, datetime).
  No external dependencies required.
- ripgrep (`rg`) is used when available in PATH; falls back to `grep -r`.
- All public functions read from filesystem at invocation time.
  No in-process cache between calls (freshness guarantee — retrieval-protocol §Vincoli 1).
- EP-042 branch: when wiki_search.enabled=true in factory.config.yaml, search_wiki
  attempts the wiki-search-protocol CLI first; degrades to grep on any failure (AC6).

[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-348-retrieval-tool-python.md §Technical Specs]
[^src: .claude/skills/retrieval-protocol.md §Fase 2 §Fase 3 §Schemi di citazione]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RG_CHECKED: bool | None = None  # module-level cache for rg availability


def _rg_available() -> bool:
    """Return True if ripgrep (rg) is found in PATH. Result is memoised per-process."""
    global _RG_CHECKED
    if _RG_CHECKED is None:
        try:
            r = subprocess.run(
                ["rg", "--version"],
                capture_output=True,
                timeout=5,
            )
            _RG_CHECKED = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _RG_CHECKED = False
    return _RG_CHECKED


def _run_search(
    pattern: str,
    target: str | Path,
    *,
    case_insensitive: bool = True,
    extra_rg_args: list[str] | None = None,
    extra_grep_args: list[str] | None = None,
) -> list[tuple[str, int, str]]:
    """
    Run rg (preferred) or grep on *target* directory/file.

    Returns a list of (filepath, 1-based line_num, matched_text) tuples.
    Returns [] on any error (timeout, command not found, non-zero exit).

    Note: paths in output tuples are as returned by the tool (may be absolute
    or relative depending on how *target* was specified).
    """
    extra_rg_args = extra_rg_args or []
    extra_grep_args = extra_grep_args or []

    if _rg_available():
        cmd = [
            "rg",
            "--line-number",
            "--no-heading",
            "--with-filename",
            "--no-color",
        ]
        if case_insensitive:
            cmd.append("--ignore-case")
        cmd.extend(extra_rg_args)
        cmd.extend([pattern, str(target)])
    else:
        cmd = ["grep", "-rn", "--with-filename"]
        if case_insensitive:
            cmd.append("-i")
        cmd.extend(extra_grep_args)
        cmd.extend([pattern, str(target)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    hits: list[tuple[str, int, str]] = []
    for line in result.stdout.splitlines():
        # Expected format: filepath:line_num:matched_text
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        try:
            hits.append((parts[0], int(parts[1]), parts[2].strip()))
        except ValueError:
            continue
    return hits


def _read_lines(path: str | Path) -> list[str]:
    """Read file and return its lines. Returns [] on any I/O error."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _nearest_heading(lines: list[str], line_num: int) -> str:
    """
    Scan backward from line_num (1-based) to find the nearest H2 or H3 heading.
    Falls back to H1 if no H2/H3 is found. Returns "" if no heading exists at all.
    """
    upper = min(line_num - 1, len(lines) - 1)
    for i in range(upper, -1, -1):
        m = re.match(r"^#{2,3}\s+(.+)", lines[i])
        if m:
            return m.group(1).strip()
    # H1 fallback
    for i in range(upper, -1, -1):
        m = re.match(r"^#\s+(.+)", lines[i])
        if m:
            return m.group(1).strip()
    return ""


def _excerpt(lines: list[str], line_num: int, max_chars: int = 200) -> str:
    """
    Build a short excerpt around line_num (1-based), capped at max_chars.
    Collapses consecutive whitespace for readability.
    """
    start = max(0, line_num - 2)  # one line of context before the match
    end = min(len(lines), line_num + 2)  # one line of context after
    raw = " ".join(lines[start:end]).strip()
    text = re.sub(r"\s+", " ", raw)
    return text[:max_chars]


def _nearest_scope(
    lines: list[str],
    line_num: int,
    lookahead: int = 60,
) -> tuple[str | None, str | None]:
    """
    Scan backward up to *lookahead* lines from line_num (1-based) to find the
    innermost enclosing Python `def` / `async def` and `class` declarations.

    Returns (function_name, class_name) — each None if not found.
    Only meaningful for Python source files; for other file types both are None.
    """
    fn_name: str | None = None
    cls_name: str | None = None
    limit = max(0, line_num - lookahead)
    upper = min(line_num - 1, len(lines) - 1)

    for i in range(upper, limit - 1, -1):
        raw = lines[i]
        if fn_name is None:
            m = re.match(r"\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", raw)
            if m:
                fn_name = m.group(1)
        if cls_name is None:
            m = re.match(r"\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", raw)
            if m:
                cls_name = m.group(1)
        if fn_name and cls_name:
            break

    return fn_name, cls_name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _flag(content: str, blocco: str, chiave: str) -> bool | None:
    """Legge `blocco:` → `  chiave: true|false` senza pyyaml. `None` se assente.

    `None` e `False` sono cose diverse: «non dichiarato» e «dichiarato spento» portano
    a messaggi diversi verso l'utente, e collassarli produce la stessa ambiguita' di uno
    zero al posto di «non lo so».
    """
    idx = content.find(f"{blocco}:")
    if idx == -1:
        return None
    for line in content[idx + len(blocco) + 1:].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_]", line):      # nuova chiave top-level: blocco finito
            break
        m = re.match(rf"\s+{chiave}\s*:\s*(true|false)", line)
        if m:
            return m.group(1).lower() == "true"
    return None


def retrieval_gate(repo_root: str = ".") -> tuple[bool, str | None]:
    """(il retrieval semantico e' attivo, ragione se no) — US-175, TSK-675.

    **Doppio gate.** Il retrieval semantico nel tutor sta all'incrocio di due capability
    indipendenti, e serve che siano accese ENTRAMBE:

      - `capability_formativa.enabled` — senza tutor non c'e' nessuno che interroghi;
      - `wiki_search.enabled` — senza indice non c'e' niente da interrogare;

    piu' l'interruttore dell'integrazione, `capability_formativa.wiki_search_integration`,
    che esiste perche' avere le due capability accese non implica volerle collegate.

    A gate chiuso il tutor si comporta **esattamente come prima di questa storia**: usa il
    contenuto del nodo di curriculum e il grep, e non cerca l'indice. La ragione viene
    restituita e non scartata: un retrieval che non parte senza dire perche' e'
    indistinguibile da un retrieval che non trova nulla.
    """
    try:
        content = (Path(repo_root) / "factory.config.yaml").read_text(encoding="utf-8")
    except OSError:
        return False, "factory.config.yaml non leggibile"

    integrazione = _flag(content, "capability_formativa", "wiki_search_integration")
    if integrazione is not True:
        return False, ("capability_formativa.wiki_search_integration non e' attivo"
                       if integrazione is False else
                       "capability_formativa.wiki_search_integration non e' dichiarato")

    for blocco, chiave, cosa in (
        ("capability_formativa", "enabled", "la capability formativa e' spenta"),
        ("wiki_search", "enabled", "wiki_search e' spento: nessun indice da interrogare"),
    ):
        if _flag(content, blocco, chiave) is not True:
            return False, cosa
    return True, None


def _ep042_enabled(repo_root: str = ".") -> bool:
    """Compatibilita': i chiamanti storici leggevano questo. Ora risponde il doppio gate.

    Prima bastava `wiki_search.enabled`, e il tutor interrogava l'indice anche con
    l'integrazione dichiarata `false` in configurazione — cioe' il flag
    `capability_formativa.wiki_search_integration` non governava niente.
    """
    attivo, _ = retrieval_gate(repo_root)
    return attivo


#: Ultime degradazioni del retrieval semantico, in memoria. Serve a rispondere alla
#: domanda «perche' la risposta e' piu' povera del previsto», che senza questo registro
#: non ha risposta: il grep funziona, quindi nulla fallisce e nulla viene detto.
_DEGRADAZIONI: list[dict] = []


def _degradazione(ragione: str, *, gate: bool = False) -> None:
    _DEGRADAZIONI.append({
        "ragione": ragione,
        "tipo": "gate-chiuso" if gate else "indice-non-utilizzabile",
        "quando": datetime.now(timezone.utc).isoformat(),
    })
    del _DEGRADAZIONI[:-20]


def ultima_degradazione() -> dict | None:
    """L'ultima ragione per cui il retrieval semantico non e' stato usato. `None` se
    e' stato usato, o se non e' mai stato tentato."""
    return _DEGRADAZIONI[-1] if _DEGRADAZIONI else None


def verifica_citazioni(citazioni: list[dict], repo_root: str = ".") -> list[dict]:
    """Scarta le citazioni il cui `source` non esiste su disco (US-175, TSK-677).

    Una risposta piu' ricca ma non verificabile e' peggio di una piu' povera: il tutor ha
    tag epistemici L1/L2/L3 proprio per non far passare per sapere cio' che e' inferenza,
    e una citazione che non risolve e' un'inferenza travestita da fonte.

    Il rischio e' concreto sul ramo semantico: l'indice puo' essere piu' vecchio del wiki
    e restituire pagine **rinominate o cancellate** — e in quel caso il tutor citerebbe
    con sicurezza un file che non esiste piu'. Il grep non ha questo problema perche'
    legge il disco; l'indice si', ed e' la ragione per cui questo filtro esiste.

    Lo scarto e' registrato come degradazione: una citazione persa in silenzio fa
    sembrare povero il retrieval invece che stantio l'indice.
    """
    radice = Path(repo_root)
    valide, scartate = [], []
    for c in citazioni:
        origine = c.get("source", "")
        if origine and (radice / origine).is_file():
            valide.append(c)
        else:
            scartate.append(origine or "<senza source>")
    if scartate:
        _degradazione(f"{len(scartate)} citazioni scartate perche' il file non esiste "
                      f"(indice piu' vecchio del wiki?): {', '.join(scartate[:3])}")
    return valide


def search_wiki(query: str, repo_root: str = ".") -> list[dict]:
    """
    Search the wiki/ directory for *query* and return wiki citations.

    Returns a list of wiki_citation dicts (may be empty):
        [{"source": str, "section": str, "excerpt": str}, ...]

    Retrieval strategy (AC6):
    - EP-042 ON  (wiki_search.enabled=true): try wiki-search-protocol CLI via
      subprocess; degrade to grep/rg on any failure.
    - EP-042 OFF (default):                  use rg/grep directly on wiki/.

    Results are deduplicated by (source, section) pair and capped at 10 items.
    Freshness: no cache — filesystem is read at every invocation.
    """
    wiki_dir = Path(repo_root) / "wiki"
    if not wiki_dir.exists():
        return []

    citations: list[dict] = []
    seen: set[tuple[str, str]] = set()  # (source, section) dedup

    def _grep_fallback() -> list[dict]:
        """grep/rg search on wiki/. Used when EP-042 is off or unavailable."""
        nonlocal citations
        hits = _run_search(
            query,
            wiki_dir,
            extra_rg_args=["--glob", "*.md"],
            extra_grep_args=["--include=*.md"],
        )
        results: list[dict] = []
        for filepath, line_num, _ in hits:
            try:
                rel = str(Path(filepath).relative_to(Path(repo_root).resolve()))
            except ValueError:
                rel = filepath

            lines = _read_lines(filepath)
            section = _nearest_heading(lines, line_num)
            key = (rel, section)
            if key in seen:
                continue
            seen.add(key)

            citation: dict = {"source": rel, "section": section}
            ex = _excerpt(lines, line_num)
            if ex:
                citation["excerpt"] = ex
            results.append(citation)
            if len(results) >= 10:
                break
        return results

    attivo, ragione = retrieval_gate(repo_root)
    if attivo:
        # Gate aperto — si tenta l'indice semantico, e se non risponde si degrada al grep
        # DICHIARANDOLO. `wiki_search.enabled: true` non garantisce che l'indice esista:
        # va costruito con `/wiki-search reindex`, e un tutor che tace la differenza fa
        # sembrare povero il corpus quando invece manca l'indice (TSK-676).
        try:
            result = subprocess.run(
                [
                    "python3", "-m", "wiki_search",
                    "--query", query,
                    "--json",
                    "--top-k", "5",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                raw = json.loads(result.stdout)
                hits = raw if isinstance(raw, list) else raw.get("results", [])
                for hit in hits:
                    source = hit.get("source") or hit.get("path", "")
                    section = hit.get("section") or hit.get("heading", "")
                    excerpt = (hit.get("excerpt") or hit.get("text", ""))[:200]
                    if not source:
                        continue
                    key = (source, section)
                    if key in seen:
                        continue
                    seen.add(key)
                    citation: dict = {"source": source, "section": section}
                    if excerpt:
                        citation["excerpt"] = excerpt
                    citations.append(citation)
                verificate = verifica_citazioni(citations, repo_root)
                if verificate:
                    return verificate
                if citations:
                    # L'indice ha risposto, ma tutte le pagine che nomina sono sparite.
                    # Non e' «nessun risultato»: e' un indice stantio, e va detto.
                    _degradazione("l'indice ha risposto ma nessuna pagina citata esiste "
                                  "piu': ricostruiscilo con `/wiki-search reindex`")
            _degradazione(
                "l'indice semantico non ha restituito risultati utilizzabili")
        except FileNotFoundError:
            _degradazione("l'indice non e' stato costruito: `/wiki-search reindex`")
        except subprocess.TimeoutExpired:
            _degradazione("l'indice non ha risposto entro 30s")
        except Exception as problema:      # noqa: BLE001 — un guasto e' un dato
            _degradazione(f"{type(problema).__name__}: {problema}")
    elif ragione:
        _degradazione(ragione, gate=True)

    # Gate chiuso, oppure aperto ma indice non utilizzabile: si torna al grep, che e'
    # esattamente il comportamento precedente a questa storia (R.WS1, fallback garantito).
    return _grep_fallback()


def search_codebase(query: str, repo_root: str = ".") -> list[dict]:
    """
    Search the entire codebase (rooted at repo_root) for *query*.

    Excludes: .git/, node_modules/, __pycache__/, *.pyc.

    Returns a list of code_citation dicts (may be empty):
        [{"file": str, "function": str (opt), "class": str (opt)}, ...]

    For each match the function scans backward up to 60 lines to identify the
    nearest enclosing Python def/class.  For non-Python files both fields are
    absent.  Results are deduplicated by (file, function, class) triple and
    capped at 20 items.

    Freshness: no cache — filesystem is read at every invocation.
    """
    root = Path(repo_root)
    if not root.exists():
        return []

    rg_exclude = [
        "--glob", "!.git",
        "--glob", "!node_modules",
        "--glob", "!__pycache__",
        "--glob", "!*.pyc",
    ]
    grep_exclude = [
        "--exclude-dir=.git",
        "--exclude-dir=node_modules",
        "--exclude-dir=__pycache__",
        "--exclude=*.pyc",
    ]

    hits = _run_search(
        query,
        root,
        extra_rg_args=rg_exclude,
        extra_grep_args=grep_exclude,
    )

    results: list[dict] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    for filepath, line_num, _ in hits:
        try:
            rel = str(Path(filepath).relative_to(root.resolve()))
        except ValueError:
            rel = filepath

        lines = _read_lines(filepath)
        fn_name, cls_name = _nearest_scope(lines, line_num)

        key = (rel, fn_name, cls_name)
        if key in seen:
            continue
        seen.add(key)

        citation: dict = {"file": rel}
        if fn_name:
            citation["function"] = fn_name
        if cls_name:
            citation["class"] = cls_name
        results.append(citation)

        if len(results) >= 20:
            break

    return results


def emit_gap_record(concept: str, original_query: str) -> dict:
    """
    Build a structured gap-record compatible with wiki/gaps.md (append-only format).

    Returns:
        {
            "concept":        str  — concept slug, max 80 chars,
            "original_query": str  — verbatim query text,
            "timestamp":      str  — ISO-8601 UTC, e.g. "2026-07-10T14:00:00Z",
        }

    Does NOT write to wiki/gaps.md.  The caller (tutor agent) is responsible
    for deciding whether and when to append this record to the gaps file.
    """
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "concept": concept[:80],
        "original_query": original_query,
        "timestamp": ts,
    }


# ---------------------------------------------------------------------------
# Mini-CLI — for manual testing
# Usage:
#   python3 tools/tutor/retrieval_tool.py wiki "modello epistemico"
#   python3 tools/tutor/retrieval_tool.py code "search_wiki"
#   python3 tools/tutor/retrieval_tool.py gap "modello epistemico"
#   python3 tools/tutor/retrieval_tool.py ep042
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="retrieval_tool.py",
        description=(
            "EP-045 retrieval tool — manual test CLI.\n"
            "Modes: wiki | code | gap | ep042"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=["wiki", "code", "gap", "ep042"],
        help=(
            "wiki   — search_wiki(query)\n"
            "code   — search_codebase(query)\n"
            "gap    — emit_gap_record(query, query)\n"
            "ep042  — print _ep042_enabled() result"
        ),
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Search query or concept name (required for wiki/code/gap modes).",
    )
    parser.add_argument(
        "--repo",
        default=".",
        metavar="PATH",
        help="Repository root (default: current directory).",
    )
    args = parser.parse_args()

    if args.mode == "ep042":
        enabled = _ep042_enabled(args.repo)
        print(f"EP-042 (wiki_search.enabled): {enabled}")
        sys.exit(0)

    if not args.query:
        parser.error(f"'query' argument is required for mode '{args.mode}'")

    if args.mode == "wiki":
        output = search_wiki(args.query, args.repo)
    elif args.mode == "code":
        output = search_codebase(args.query, args.repo)
    else:  # gap
        output = emit_gap_record(args.query, args.query)

    print(json.dumps(output, indent=2, ensure_ascii=False))
