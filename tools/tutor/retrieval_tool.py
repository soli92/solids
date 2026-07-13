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


def _ep042_enabled(repo_root: str = ".") -> bool:
    """
    Return True if `wiki_search.enabled` is `true` in factory.config.yaml.

    Parsed with stdlib only (no pyyaml). Falls back to False on missing file,
    parse error, or absent key.

    Called internally by search_wiki to select the retrieval branch (AC6).
    """
    config_path = Path(repo_root) / "factory.config.yaml"
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Locate the wiki_search: block in the YAML (top-level key).
    idx = content.find("wiki_search:")
    if idx == -1:
        return False

    # Take the text immediately after "wiki_search:" and scan for "enabled:".
    # Stop scanning when we encounter a new top-level key (unindented non-empty
    # non-comment line), which signals we have left the wiki_search block.
    snippet = content[idx + len("wiki_search:"):]
    for line in snippet.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # A new top-level YAML key starts at column 0 (no leading whitespace).
        if re.match(r"^[A-Za-z_]", line):
            break
        # Match indented "enabled: true|false" (comment suffix allowed).
        m = re.match(r"\s+enabled\s*:\s*(true|false)", line)
        if m:
            return m.group(1).lower() == "true"

    return False


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

    if _ep042_enabled(repo_root):
        # EP-042 ON — attempt wiki-search-protocol CLI.
        # If the subprocess call fails for any reason, degrade to grep (AC6).
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
                if citations:
                    return citations
        except Exception:
            pass  # degrade to grep

    # EP-042 off — or EP-042 on but CLI unavailable/failed.
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
