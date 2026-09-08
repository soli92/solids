#!/usr/bin/env python3
"""chunk-code.py — Chunking symbol-level via tree-sitter (EP-054 L2).

Usage:
    python3 chunk-code.py <repo_path> <slug> [--output=chunks.jsonl] [--incremental]

Output: JSONL (un chunk per riga) con schema:
    {id, file, symbol, type, language, start_line, end_line, code, docstring}
"""
import sys
import os
import json
import hashlib
import fnmatch
import argparse
from pathlib import Path
from datetime import datetime, timezone

# EP-054 R.CI2: prerequisite check — SKIP non STOP
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    print("[L2-SKIP] tree-sitter not installed — pip install tree-sitter tree-sitter-python tree-sitter-typescript tree-sitter-javascript tree-sitter-java tree-sitter-go tree-sitter-rust")
    sys.exit(0)

# Mapping estensione → (grammar_package, linguaggio, nodi target)
LANG_MAP = {
    ".py": ("python", "tree_sitter_python", [
        "function_definition", "class_definition", "decorated_definition"
    ]),
    ".ts": ("typescript", "tree_sitter_typescript.language_typescript", [
        "function_declaration", "class_declaration", "interface_declaration",
        "method_definition", "lexical_declaration"
    ]),
    ".tsx": ("tsx", "tree_sitter_typescript.language_tsx", [
        "function_declaration", "class_declaration", "interface_declaration",
        "method_definition"
    ]),
    ".js": ("javascript", "tree_sitter_javascript", [
        "function_declaration", "class_declaration", "method_definition",
        "lexical_declaration"
    ]),
    ".jsx": ("javascript", "tree_sitter_javascript", [
        "function_declaration", "class_declaration", "method_definition"
    ]),
    ".java": ("java", "tree_sitter_java", [
        "method_declaration", "class_declaration", "interface_declaration", "enum_declaration"
    ]),
    ".go": ("go", "tree_sitter_go", [
        "function_declaration", "method_declaration", "type_declaration"
    ]),
    ".rs": ("rust", "tree_sitter_rust", [
        "function_item", "impl_item", "struct_item", "enum_item", "trait_item"
    ]),
}

DEFAULT_EXCLUDE = [
    "**/node_modules/**", "**/__pycache__/**", "**/vendor/**",
    "**/*.min.js", "**/*.generated.*", "**/.git/**",
    "**/.claude/worktrees/**", "**/.code-search/**", "**/.ctags-state/**",
    "**/.wiki-search/**", "**/.graphify-state/**",
    "**/dist/**", "**/build/**", "**/.next/**", "**/.nuxt/**",
]

CHUNK_MAX_LINES = 150


def load_grammar(module_path: str):
    """Carica grammar tree-sitter. Ritorna None se non disponibile (R.CI2)."""
    try:
        parts = module_path.split(".")
        if len(parts) == 1:
            mod = __import__(parts[0])
            return Language(mod.language())
        else:
            mod = __import__(".".join(parts[:-1]), fromlist=[parts[-1]])
            lang_fn = getattr(mod, parts[-1])
            return Language(lang_fn())
    except (ImportError, AttributeError, Exception):
        return None


def extract_symbol_name(node, source_bytes: bytes) -> str:
    """Estrae il nome del simbolo dal nodo AST."""
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "property_identifier",
                          "field_identifier", "name"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
    return f"anonymous_{node.type}"


def extract_docstring(node, source_bytes: bytes, lines: list) -> str:
    """Estrae docstring/commento precedente al simbolo."""
    start_line = node.start_point[0]
    # Cerca nelle 5 righe precedenti
    doc_lines = []
    i = start_line - 1
    while i >= 0 and (start_line - i) <= 5:
        line = lines[i].strip()
        if line.startswith(("#", "//", "*", "/**", "///", '"""', "'''")):
            doc_lines.insert(0, lines[i].strip().lstrip("#/ *"))
        elif not line:
            break
        else:
            break
        i -= 1
    # Python docstring: primo statement del body
    if not doc_lines and node.type in ("function_definition", "class_definition"):
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for s in stmt.children:
                            if s.type == "string":
                                raw = source_bytes[s.start_byte:s.end_byte].decode("utf-8", errors="replace")
                                return raw.strip('"\' \n')
    return " ".join(doc_lines)


def chunk_node(node, source_bytes: bytes, lines: list, file_rel: str,
               slug: str, language: str, chunk_max: int) -> list:
    """Converte un nodo AST in uno o più chunk JSON."""
    start = node.start_point[0]
    end = node.end_point[0]
    symbol = extract_symbol_name(node, source_bytes)
    docstring = extract_docstring(node, source_bytes, lines)
    code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    base_id = f"{slug}:{file_rel}:{symbol}:{start + 1}"

    if (end - start) > chunk_max:
        mid = (start + end) // 2
        overlap = 10
        part1_code = "\n".join(lines[start:mid + overlap])
        part2_code = "\n".join(lines[max(0, mid - overlap):end + 1])
        return [
            {"id": f"{base_id}:part1", "file": file_rel, "symbol": symbol,
             "type": node.type, "language": language, "start_line": start + 1,
             "end_line": mid + overlap, "code": part1_code, "docstring": docstring},
            {"id": f"{base_id}:part2", "file": file_rel, "symbol": symbol,
             "type": node.type, "language": language, "start_line": max(1, mid - overlap + 1),
             "end_line": end + 1, "code": part2_code, "docstring": ""},
        ]

    return [{"id": base_id, "file": file_rel, "symbol": symbol, "type": node.type,
             "language": language, "start_line": start + 1, "end_line": end + 1,
             "code": code, "docstring": docstring}]


def is_excluded(path: str, patterns: list) -> bool:
    norm = path.replace("\\", "/")
    for pattern in patterns:
        # Strip leading **/ for substring-based matching
        inner = pattern.strip("*/")
        if inner and inner in norm:
            return True
        if fnmatch.fnmatch(norm, pattern):
            return True
    return False


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    parser.add_argument("slug")
    parser.add_argument("--output", default=None)
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--chunk-max-lines", type=int, default=CHUNK_MAX_LINES)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    repo = Path(args.repo_path).resolve()
    if not repo.is_dir():
        print(f"[L2-ERROR] repo_path not found: {repo}", file=sys.stderr)
        sys.exit(1)

    exclude_patterns = DEFAULT_EXCLUDE + args.exclude
    state_dir = Path(".code-search/chunk-state")
    state_file = state_dir / f"{args.slug}.json"
    state = {}

    if args.incremental and state_file.exists():
        with open(state_file) as f:
            state = json.load(f).get("files", {})

    # Pre-carica grammar (R.CI2: skip se non disponibile)
    grammars = {}
    for ext, (lang_name, mod_path, _) in LANG_MAP.items():
        if lang_name not in grammars:
            g = load_grammar(mod_path)
            if g is None:
                print(f"[L2-SKIP] grammar not found for {lang_name} — pip install tree-sitter-{lang_name.split('.')[0]}")
            grammars[lang_name] = g

    out_fh = open(args.output, "w") if args.output else sys.stdout
    new_state = {}
    total_chunks = 0
    seen_ids: dict = {}

    for src_file in sorted(repo.rglob("*")):
        if not src_file.is_file():
            continue
        rel = str(src_file.relative_to(repo))
        if is_excluded(rel, exclude_patterns):
            continue
        ext = src_file.suffix.lower()
        if ext not in LANG_MAP:
            continue

        lang_name, _, target_types = LANG_MAP[ext]
        grammar = grammars.get(lang_name)
        if grammar is None:
            continue

        fhash = file_hash(src_file)
        new_state[rel] = fhash
        if args.incremental and state.get(rel) == fhash:
            continue

        try:
            source_bytes = src_file.read_bytes()
            lines = source_bytes.decode("utf-8", errors="replace").splitlines()
            p = Parser(grammar)
            tree = p.parse(source_bytes)

            def walk(node):
                if node.type in target_types:
                    chunks = chunk_node(node, source_bytes, lines, rel,
                                        args.slug, lang_name, args.chunk_max_lines)
                    for c in chunks:
                        # Deduplicate IDs: add counter suffix if already seen
                        cid = c["id"]
                        if cid in seen_ids:
                            seen_ids[cid] += 1
                            c["id"] = f"{cid}:{seen_ids[cid]}"
                        else:
                            seen_ids[cid] = 0
                        print(json.dumps(c, ensure_ascii=False), file=out_fh)
                        nonlocal total_chunks
                        total_chunks += 1
                for child in node.children:
                    walk(child)

            walk(tree.root_node)
        except Exception as e:
            print(f"[L2-WARN] parse error {rel}: {e}", file=sys.stderr)

    if args.output:
        out_fh.close()

    # Aggiorna state
    state_dir.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump({"files": new_state, "generated": datetime.now(timezone.utc).isoformat()}, f)

    print(f"[L2] Chunking done: {total_chunks} chunks from {args.slug}", file=sys.stderr)


if __name__ == "__main__":
    main()
