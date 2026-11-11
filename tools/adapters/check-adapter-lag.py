#!/usr/bin/env python3
"""
check-adapter-lag.py — adapter registry health vs capability matrix (Sprint 1).

Reads:
  - factory.config.yaml → pattern_version
  - adapters/capability-matrix.yaml
  - adapters/*/manifest.yaml

Exit codes:
  0 — OK (warnings allowed)
  1 — errors (missing required fields / unknown maturity / broken registry)
  2 — usage / IO failure

Run from repo root:
  python3 tools/adapters/check-adapter-lag.py
  python3 tools/adapters/check-adapter-lag.py --strict   # warnings → exit 1

Additive mode (EP-065 / US-272 / TSK-644) — leaves the default run untouched:
  python3 tools/adapters/check-adapter-lag.py --cross-adapter
      Direction of the dependencies between adapters: an adapter may point at the
      agnostic layer and at itself, never at another adapter. stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# yaml is imported lazily inside _load_yaml (TSK-645 refactor).
# The --cross-adapter path is stdlib-only (US-272 AC5) and never calls _load_yaml,
# so PyYAML is never imported on that path even if it is installed.
yaml = None  # type: ignore[assignment]  # sentinel kept for compatibility

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTERS_DIR = REPO_ROOT / "adapters"
MATRIX_PATH = ADAPTERS_DIR / "capability-matrix.yaml"
CONFIG_PATH = REPO_ROOT / "factory.config.yaml"

# US-319: il PATTERN e' indice + moduli. Un solo posto decide quali file sono «il
# PATTERN» (tools/lint/pattern_modules.py, stdlib); qui lo si importa, non lo si rifa'.
sys.path.insert(0, str(REPO_ROOT / "tools" / "lint"))
from pattern_modules import missing_modules, pattern_files, pattern_text  # noqa: E402,F401

VALID_MATURITY = {"full", "core", "partial", "manifest-only"}
VALID_PROFILES = {"native", "sequential", "external", "viewer"}
REQUIRED_FEATURES = (
    "local_fs_read",
    "local_fs_write",
    "subagent_fanout",
    "parallel_dispatch",
    "hooks",
    "mcp",
    "shell",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml as _yaml  # lazy: --cross-adapter (stdlib-only) never reaches here
    except ImportError as exc:
        raise ImportError("PyYAML required (pip install -r tools/requirements.txt)") from exc
    with path.open(encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping at root")
    return data


def _parse_version(v: Any) -> tuple[int, ...]:
    s = str(v).strip().lstrip("v")
    parts: list[int] = []
    for p in s.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def _template_repo_path(adapter_dir: Path, declared_path: str) -> Path:
    """Map a manifest `path` (runtime-relative, e.g. .cursor/rules/x.mdc) to its template file."""
    rel = declared_path
    for prefix in (".cursor/", ".aider/", ".openai/", ".gemini/", ".chatgpt/", ".claude/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
            break
    rel = rel.replace("commands/", "commands/", 1)
    return adapter_dir / "templates" / rel


def check_template_integrity(
    adapter_dir: Path, manifest: dict[str, Any], name: str
) -> tuple[list[str], list[str]]:
    """Every manifest-declared template must exist; every mdc: cross-reference must resolve.

    Catches the failure mode repaired on 2026-09-16: manifest promising
    .cursor/rules/figma-sync.mdc while the template file was never written, so
    scaffolding a derived factory silently produced a broken adapter.
    """
    errors: list[str] = []
    warnings: list[str] = []
    templates_dir = adapter_dir / "templates"
    if not templates_dir.is_dir():
        return errors, warnings  # adapter ships no templates (manifest-only): nothing to check

    # `full` E `core` promettono un set di template spedito: per entrambi un template
    # dichiarato e assente e' un ERRORE (TSK-571, EP-063). Solo `partial` puo' usare il
    # manifest come roadmap — e da quando esiste la sezione `roadmap:` esplicita non ha
    # piu' nemmeno bisogno di farlo: cio' che non si spedisce si dichiara li'.
    #
    # La severita' e' stata alzata SOLO DOPO aver ripagato il debito noto, non prima:
    # con aider a 27 template fantasma e openai a 2, un check bloccante sarebbe stato
    # rosso al primo giro e disattivato al secondo. L'ordine e' il punto — si ripara,
    # poi si chiude la porta.
    blocking = str(manifest.get("maturity", "")) in {"full", "core"}
    bucket = errors if blocking else warnings

    declared_paths: dict[str, str] = {}
    for kind, entries in (manifest.get("templates") or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or "path" not in entry:
                continue
            target = _template_repo_path(adapter_dir, str(entry["path"]))
            declared_paths[str(entry.get("name", target.stem))] = str(entry["path"])
            if not target.is_file():
                bucket.append(
                    f"{name}: manifest declares {kind}/{entry.get('name')} → "
                    f"{entry['path']} but {target.relative_to(REPO_ROOT)} does not exist"
                )

    # templates on disk that the manifest never declares → scaffolding skips them
    declared_stems = {Path(p).stem for p in declared_paths.values()}
    for path in sorted(templates_dir.rglob("*")):
        if not path.is_file() or path.name == "README.md":
            continue
        if path.suffix not in {".mdc", ".md"}:
            continue
        if path.stem not in declared_stems:
            warnings.append(
                f"{name}: {path.relative_to(REPO_ROOT)} present but not declared in "
                "manifest.templates (it will not be scaffolded)"
            )

    # cross-references between templates must resolve
    for path in sorted(templates_dir.rglob("*")):
        if not path.is_file() or path.suffix not in {".mdc", ".md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"mdc:([^\)\s]+)", text):
            ref = match.group(1)
            if "<" in ref or not ref.endswith((".mdc", ".md")):
                continue  # placeholder in docs/README, not a real reference
            if not _template_repo_path(adapter_dir, ref).is_file():
                bucket.append(
                    f"{name}: {path.relative_to(REPO_ROOT)} references {ref} "
                    "which has no template file"
                )

    return errors, warnings


# ===========================================================================
# Cross-adapter dependency direction  (--cross-adapter)
#
# EP-065 / US-272 / TSK-644. Additive: the default run above is untouched, and
# this path needs no PyYAML.
#
# The Round Table optimised the always-on load, which is by construction a
# metric of ONE adapter. The factory is agnostic (PATTERN §12.2, R.A1-R.A6,
# 7 registered adapters), so the cleanliness criterion has to be checked on the
# direction of the dependencies instead. Three directions, treated differently
# (US-272 AC4):
#
#   adapter → agnostic layer (PATTERN.md, CHANGELOG.md, CAPABILITIES.md,
#                             meta-prompts/)                    → legitimate
#   adapter → its own adapter                                   → legitimate
#   adapter → another adapter                                   → reported
#
# Inside the third direction the finding is graded by WHAT is named, because the
# blast radius differs:
#
#   ERROR  another adapter's ROOT INSTRUCTION FILE (CLAUDE.md, CONVENTIONS.md,
#          .cursorrules, GEMINI.md …). Those files sit at the factory root, next
#          to the agnostic layer, and are read by their runtime without being
#          asked: naming one from another adapter's template makes that template
#          silently adapter-specific — if the file is renamed, the line lies.
#
#   WARN   another adapter's NAMESPACED path (.claude/**, .cursor/** …) inside
#          normative body text. Real coupling, kept visible but non-blocking:
#          repairing those files is outside this TSK's write scope (US-272 AC8 —
#          the check is read-only beyond the one explicit remedy).
#
#   INFO   provenance / equivalence declarations ("Adapter Cursor della skill X
#          definita in .claude/skills/X.md") and registry documents
#          (adapters/README.md, adapters/*/README.md, manifest.yaml,
#          capability-matrix.yaml). Naming the reference adapter is their job:
#          adapters/cursor/templates/README.md mandates that header and the
#          EP-063 template-integrity check relies on the pairing.
#
# The predicate counts textual references REGARDLESS OF POLARITY. A line that
# says "not CLAUDE.md" is still coupled to the claude adapter: it has to name a
# foreign file in order to explain itself.
#
# Out of scope by construction (US-272 AC6): this mode does NOT require content
# parity between adapters — that is EP-063. An adapter with a smaller declared
# perimeter passes.
# ===========================================================================

AGNOSTIC_ARTIFACTS = (
    "PATTERN.md",
    "CHANGELOG.md",
    "CAPABILITIES.md",
    "QUICKSTART.md",
    "meta-prompts/",
)

# Root-level instruction surface per runtime: the file that runtime reads at the
# factory root without being asked. Seeded here because the manifests do not
# declare it uniformly; augmented at runtime from manifest-declared template
# paths that sit at the factory root (today: aider's CONVENTIONS.md).
ADAPTER_ROOT_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "claude": ("CLAUDE.md",),
    "cursor": (".cursorrules",),
    "aider": ("CONVENTIONS.md", ".aider.conf.yml"),
    "gemini": ("GEMINI.md",),
    "chatgpt": (),
    "openai": (),
    "mcp": (),
}

# Never promote these to "root artifact of adapter X": they are agnostic or
# generic, and would produce false cross-adapter findings everywhere.
_NEVER_ROOT_ARTIFACT = {
    "README.md",
    "PATTERN.md",
    "CHANGELOG.md",
    "CAPABILITIES.md",
    "QUICKSTART.md",
    "factory.config.yaml",
    "config.yaml",
    "manifest.yaml",
}

SCANNED_SUFFIXES = {".md", ".mdc", ".yaml", ".yml", ".sh", ".py", ".json", ".txt"}
REGISTRY_FILENAMES = {"README.md", "manifest.yaml", "capability-matrix.yaml"}

# A reference is a provenance/equivalence declaration when the line's job is to
# say "this file is the translation of that one" — the maintenance map, not a
# runtime dependency.
PROVENANCE_RE = re.compile(
    r"\bequivalent\w*\b|\bdefinit[ao]\s+in\b|\bdefined\s+in\b|\btradott\w*\b|"
    r"\btranslat\w*\b|\bcontropart\w*\b|\bcounterpart\b|\bderivat[ao]\s+da\b|"
    r"\bderived\s+from\b|\badapter\s+\w+\s+(?:della|del|dello|di)\b",
    re.IGNORECASE,
)

_MANIFEST_FIELD_RE = re.compile(
    r"^(adapter_name|adapter_folder|maturity|contract_version)\s*:\s*(.+?)\s*$", re.M
)
_MANIFEST_ROOT_TEMPLATE_RE = re.compile(r"path:\s*([A-Za-z0-9_.-]+\.(?:md|ya?ml|json|sh))\s*[,}]")

# Anchors pointing at PATTERN.md §-numbered sections (must start with a digit).
# Non-digit anchors (§AC, §Autenticazione, §flows …) belong to other documents and are
# skipped: they do not use PATTERN.md's numbering scheme.
_PATTERN_SEC_ANCHOR_RE = re.compile(r"§(\d[A-Za-z0-9]*(?:\.\d+)*)")
_CONFIG_PATTERN_VERSION_RE = re.compile(r"^pattern_version\s*:\s*[\"']?([0-9][0-9.]*)", re.M)

# Declared lag: reading context for the report, NOT a defect of this check (AC7).
DECLARED_LAG_NOTE = (
    "contesto di lettura, non un difetto di questo EP (US-272 AC7): lag dichiarato "
    "degli adapter — cursor contract 2.37, aider 2.13, openai partial, "
    "gemini/chatgpt manifest-only, vs pattern {pattern_version}. Un contenuto che "
    "atterra solo in .claude/ non raggiunge nessuno di questi."
)


# --- public predicate, consumed by TSK-645 and by the TSK-643 contract test ---

# Canonical heading form of a PATTERN.md section: `## §12.2 — <title>`. The `§`
# must open the heading text: a heading that merely cites `§29` in its title is a
# reference, not a declaration, and must not become a resolvable anchor.
_PATTERN_HEADING_RE = re.compile(r"^#{1,6}\s+§([A-Za-z0-9][A-Za-z0-9_.\-]*)")


def pattern_sections(pattern_path: Path | None = None) -> set[str]:
    """Section ids declared by the headings of `PATTERN.md` **and its modules**.

    Since US-319 the PATTERN is an index (`PATTERN.md`, §0-§11) plus the modules
    linked in its «## Moduli» table (§12+). Numbering is shared, so the set is
    the union over all files (see tools/lint/pattern_modules.py).

    Returned WITHOUT the leading `§` and normalised: {"0", "7", "12.2", "37", …}.
    Fenced code blocks are skipped, so YAML/markdown samples inside ``` fences
    cannot inject phantom anchors (e.g. the `§13.x` in the config sample).

    Public on purpose: TSK-645 (resolution of the 52 `adapters/` → `PATTERN.md`
    anchors) and the TSK-643 contract test must IMPORT this instead of
    re-deriving it — one predicate, one place to be wrong (countermeasure to A-6).
    """
    path = pattern_path or (REPO_ROOT / "PATTERN.md")
    if not path.is_file():
        return set()
    sections: set[str] = set()
    in_fence = False
    for line in pattern_text(path).splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _PATTERN_HEADING_RE.match(line)
        if match:
            sections.add(match.group(1).rstrip(".,;:—-"))
    return sections


def pattern_section_exists(
    section: str,
    sections: set[str] | None = None,
    pattern_path: Path | None = None,
) -> bool:
    """Does `§<section>` resolve to a heading of `PATTERN.md`?

    Accepts `"§7"`, `"7"`, `"§12.2"`, `"12.2"`. Pass a pre-computed `sections`
    set when checking many anchors in a loop.

    Public on purpose (same reason as `pattern_sections`). US-272 AC3 declares a
    pointer to a non-existent `§n` an ERROR, not a warning; the enforcement that
    uses this predicate is TSK-645, not this TSK.
    """
    known = sections if sections is not None else pattern_sections(pattern_path)
    key = str(section).strip().lstrip("§").rstrip(".,;:—-")
    if not key:
        return False
    if key in known:
        return True
    # "§12" also resolves when PATTERN.md only declares "§12.2"-style subsections
    if "." not in key:
        return any(k.split(".")[0] == key for k in known)
    return False


# --- adapter identity table (stdlib parsing: no PyYAML on this path) ---------


def _pattern_version_from_config(config_path: Path | None = None) -> str:
    path = config_path or CONFIG_PATH
    if not path.is_file():
        return "?"
    match = _CONFIG_PATTERN_VERSION_RE.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else "?"


def discover_adapters(adapters_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Identity of every registered adapter, read from `adapters/*/manifest.yaml`.

    Regex parsing on purpose: `--cross-adapter` must run with the standard
    library alone (US-272 AC5).
    """
    base = adapters_dir or ADAPTERS_DIR
    table: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(base.glob("*/manifest.yaml")):
        name = manifest_path.parent.name
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
        fields = {
            m.group(1): m.group(2).strip().strip("\"'")
            for m in _MANIFEST_FIELD_RE.finditer(text)
        }
        folder = (fields.get("adapter_folder") or f".{name}").rstrip("/")
        roots = set(ADAPTER_ROOT_ARTIFACTS.get(name, ()))
        roots.update(
            hit
            for hit in _MANIFEST_ROOT_TEMPLATE_RE.findall(text)
            if hit not in _NEVER_ROOT_ARTIFACT
        )
        table[name] = {
            "name": name,
            "folder": folder,
            "roots": sorted(roots),
            "maturity": fields.get("maturity", "?"),
            "contract_version": fields.get("contract_version", "?"),
        }
    return table


# --- scan --------------------------------------------------------------------


def _iter_adapter_files(adapters_dir: Path | None = None):
    base = adapters_dir or ADAPTERS_DIR
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def _owner_adapter(path: Path, adapters: dict[str, dict[str, Any]]) -> str | None:
    """Which adapter owns this file (None for the shared registry at adapters/)."""
    parts = path.relative_to(ADAPTERS_DIR).parts
    return parts[0] if parts and parts[0] in adapters else None


def _find_references(line: str, adapters: dict[str, dict[str, Any]]) -> list[tuple[str, str, bool]]:
    """[(target_adapter, token, is_root_artifact)] found in a single line."""
    hits: list[tuple[str, str, bool]] = []
    for name, meta in adapters.items():
        folder = meta["folder"]
        if re.search(rf"(?<![\w.\-]){re.escape(folder)}/", line):
            hits.append((name, f"{folder}/", False))
        for root in meta["roots"]:
            if re.search(rf"(?<![\w.\-]){re.escape(root)}(?![\w\-])", line):
                hits.append((name, root, True))
    return hits


def classify_reference(
    owner: str | None, target: str, is_root_artifact: bool, path: Path, line: str
) -> str:
    """One of: self | registry | provenance | cross_root | cross_body."""
    if owner is None or path.name in REGISTRY_FILENAMES:
        return "registry"
    if owner == target:
        return "self"
    if is_root_artifact:
        return "cross_root"
    if line.lstrip().startswith(">") or PROVENANCE_RE.search(line):
        return "provenance"
    return "cross_body"


def scan_pattern_anchors(adapters_dir: Path | None = None) -> dict[str, Any]:
    """Enumerate §N anchors from adapters/** and check each against PATTERN.md sections.

    Returns: {examined, resolved, unresolved, errors: [{file, line, anchor, excerpt}]}.
    US-272 AC3 / TSK-645: a pointer to a non-existent §N is an ERROR, exit != 0.

    Reuses the public predicate pattern_section_exists() — one implementation, one
    place to be wrong (countermeasure to A-6 in EP-065 §Decomposizione).
    The count `examined` is the real runtime count; the «52» in the US is the
    2026-09-21 estimate and may differ from the live result (TSK-645 DoD §2).
    """
    base = adapters_dir or ADAPTERS_DIR
    known = pattern_sections()
    examined: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for path in _iter_adapter_files(base):
        rel = str(path.relative_to(REPO_ROOT))
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for m in _PATTERN_SEC_ANCHOR_RE.finditer(line):
                raw = m.group(1)
                key = raw.rstrip(".,;:—-")
                entry: dict[str, Any] = {
                    "file": rel,
                    "line": lineno,
                    "anchor": f"§{key}",
                    "excerpt": line.strip()[:120],
                }
                examined.append(entry)
                if not pattern_section_exists(key, known):
                    errors.append(entry)

    return {
        "examined": len(examined),
        "resolved": len(examined) - len(errors),
        "unresolved": len(errors),
        "errors": errors,
    }


def scan_cross_adapter(adapters_dir: Path | None = None) -> dict[str, Any]:
    """Classify every adapter-to-adapter reference under `adapters/**` (read-only)."""
    base = adapters_dir or ADAPTERS_DIR
    adapters = discover_adapters(base)
    counts = {k: 0 for k in ("agnostic", "self", "registry", "provenance", "cross_body", "cross_root")}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    files_scanned = 0

    for path in _iter_adapter_files(base):
        files_scanned += 1
        owner = _owner_adapter(path, adapters)
        rel = str(path.relative_to(REPO_ROOT))
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for artifact in AGNOSTIC_ARTIFACTS:
                if artifact in line:
                    counts["agnostic"] += 1
            for target, token, is_root in _find_references(line, adapters):
                verdict = classify_reference(owner, target, is_root, path, line)
                counts[verdict] += 1
                if verdict not in ("cross_root", "cross_body"):
                    continue
                finding = {
                    "file": rel,
                    "line": lineno,
                    "owner": owner,
                    "target": target,
                    "token": token,
                    "excerpt": line.strip()[:160],
                }
                if verdict == "cross_root":
                    finding["reason"] = (
                        f"un template dell'adapter '{owner}' nomina '{token}', il file di "
                        f"istruzioni dell'adapter '{target}': se '{token}' cambia nome questa "
                        "riga mente (US-272 AC1/AC4 — adapter → altro adapter)"
                    )
                    errors.append(finding)
                else:
                    finding["reason"] = (
                        f"l'adapter '{owner}' nomina il path '{token}' dell'adapter '{target}' "
                        "in contenuto normativo (accoppiamento visibile, non bloccante: fuori "
                        "dal write scope di questo TSK — US-272 AC8)"
                    )
                    warnings.append(finding)

    anchors = scan_pattern_anchors(base)

    return {
        "mode": "cross-adapter",
        "pattern_version": _pattern_version_from_config(),
        "adapters": {
            name: {
                "folder": meta["folder"],
                "maturity": meta["maturity"],
                "contract_version": meta["contract_version"],
                "root_artifacts": meta["roots"],
            }
            for name, meta in adapters.items()
        },
        "files_scanned": files_scanned,
        "counts": counts,
        "errors": errors,
        "warnings": warnings,
        "anchors": anchors,
        "pattern_sections_known": len(pattern_sections()),
        "declared_lag_note": DECLARED_LAG_NOTE.format(
            pattern_version=_pattern_version_from_config()
        ),
    }


def run_cross_adapter(as_json: bool = False, strict: bool = False) -> int:
    report = scan_cross_adapter()
    counts = report["counts"]

    if as_json:
        import json

        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            f"cross-adapter direction check — adapters={len(report['adapters'])}  "
            f"pattern_version={report['pattern_version']}  "
            f"file scansionati={report['files_scanned']}"
        )
        print(f"  adapter → agnostico ({', '.join(AGNOSTIC_ARTIFACTS)}): "
              f"{counts['agnostic']}  [legittimo]")
        print(f"  adapter → proprio adapter: {counts['self']}  [legittimo]")
        print(f"  adapter → altro adapter, registro/matrice: {counts['registry']}  [legittimo]")
        print(f"  adapter → altro adapter, dichiarazione di provenienza: "
              f"{counts['provenance']}  [legittimo]")
        print(f"  adapter → altro adapter, corpo normativo: {counts['cross_body']}  [WARN]")
        print(f"  adapter → file di istruzioni di un altro adapter: "
              f"{counts['cross_root']}  [ERROR]")
        for w in report["warnings"]:
            print(f"WARN  {w['file']}:{w['line']}  {w['owner']} → {w['target']} "
                  f"via '{w['token']}'")
            print(f"      {w['excerpt']}")
        for e in report["errors"]:
            print(f"ERROR {e['file']}:{e['line']}  {e['owner']} → {e['target']} "
                  f"via '{e['token']}'")
            print(f"      {e['excerpt']}")
            print(f"      {e['reason']}")
        # --- anchors section (TSK-645 / US-272 AC3) ---
        anchors = report["anchors"]
        note_52 = (
            f" (stima originale US-272: 52; scostamento: {anchors['examined'] - 52:+d})"
            if anchors["examined"] != 52
            else ""
        )
        anchor_status = "OK" if anchors["unresolved"] == 0 else "ERROR"
        print(
            f"anchors  esaminati: {anchors['examined']}{note_52} · "
            f"risolti: {anchors['resolved']} · "
            f"non risolti: {anchors['unresolved']}  [{anchor_status}]"
        )
        for ae in anchors["errors"]:
            print(f"ERROR anchor {ae['anchor']} non trovato in PATTERN.md — "
                  f"{ae['file']}:{ae['line']}")
            print(f"      {ae['excerpt']}")
        print(f"NOTE  {report['declared_lag_note']}")
        ok_direction = not report["errors"]
        ok_anchors = anchors["unresolved"] == 0
        if ok_direction and ok_anchors:
            print(
                "OK — nessun adapter dipende dal file di istruzioni di un altro adapter "
                "e tutti gli ancoraggi §N risolvono"
            )
        elif ok_direction:
            print("OK — direzione dipendenze: nessun adapter dipende da un altro")

    if report["errors"] or report["anchors"]["unresolved"] > 0:
        return 1
    if strict and report["warnings"]:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary on stdout",
    )
    parser.add_argument(
        "--cross-adapter",
        action="store_true",
        help=(
            "Check the direction of the dependencies between adapters "
            "(agnostic layer and own adapter = legitimate, another adapter = error). "
            "Additive mode: does not change the default run. Stdlib only."
        ),
    )
    args = parser.parse_args()

    # Additive mode (TSK-644): own report, own exit code, no PyYAML needed.
    if args.cross_adapter:
        return run_cross_adapter(as_json=args.json, strict=args.strict)

    errors: list[str] = []
    warnings: list[str] = []

    if not MATRIX_PATH.is_file():
        print(f"ERROR: missing {MATRIX_PATH}", file=sys.stderr)
        return 2
    if not CONFIG_PATH.is_file():
        print(f"ERROR: missing {CONFIG_PATH}", file=sys.stderr)
        return 2

    try:
        matrix = _load_yaml(MATRIX_PATH)
        config = _load_yaml(CONFIG_PATH)
    except ImportError as exc:  # lazy yaml: not installed
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to parse YAML: {exc}", file=sys.stderr)
        return 2

    pattern_version = str(config.get("pattern_version", "0"))
    matrix_ref = str(matrix.get("pattern_version_ref", "0"))
    if _parse_version(pattern_version) != _parse_version(matrix_ref):
        warnings.append(
            f"capability-matrix pattern_version_ref={matrix_ref} "
            f"!= factory.config.yaml pattern_version={pattern_version}"
        )

    defaults: dict[str, Any] = matrix.get("adapter_defaults") or {}
    expected_names = set(defaults.keys())

    manifests: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(ADAPTERS_DIR.glob("*/manifest.yaml")):
        name = manifest_path.parent.name
        try:
            manifests[name] = _load_yaml(manifest_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: cannot parse manifest ({exc})")

    for name in expected_names - set(manifests):
        errors.append(f"missing adapters/{name}/manifest.yaml (listed in capability-matrix)")

    for name, extra in manifests.items():
        if name not in expected_names:
            warnings.append(f"{name}: manifest present but not in capability-matrix.adapter_defaults")

        maturity = str(extra.get("maturity", ""))
        if maturity not in VALID_MATURITY:
            errors.append(f"{name}: invalid maturity={maturity!r} (want {sorted(VALID_MATURITY)})")

        orch = extra.get("orchestration") or {}
        if not isinstance(orch, dict) or "profile" not in orch:
            errors.append(f"{name}: missing orchestration.profile (native|sequential|external|viewer)")
        else:
            profile = str(orch.get("profile"))
            if profile not in VALID_PROFILES:
                errors.append(f"{name}: invalid orchestration.profile={profile!r}")
            features = orch.get("features") or {}
            if not isinstance(features, dict):
                errors.append(f"{name}: orchestration.features must be a mapping")
            else:
                for feat in REQUIRED_FEATURES:
                    if feat not in features:
                        warnings.append(f"{name}: orchestration.features.{feat} not declared")

        cv = extra.get("contract_version")
        if cv is None:
            errors.append(f"{name}: missing contract_version")
        else:
            target = (defaults.get(name) or {}).get("contract_version_target")
            if target and _parse_version(cv) < _parse_version(target):
                # intentional lag for core/partial is OK if maturity matches defaults
                expected_maturity = (defaults.get(name) or {}).get("maturity")
                if maturity == "full" and expected_maturity == "full":
                    warnings.append(
                        f"{name}: contract_version {cv} behind target {target} "
                        f"(pattern {pattern_version})"
                    )
                elif maturity == "full" and _parse_version(cv) < _parse_version(pattern_version):
                    warnings.append(
                        f"{name}: maturity=full but contract_version {cv} < pattern {pattern_version}"
                    )

            # False signal: full + large lag
            if maturity == "full" and _parse_version(cv) + (0,) < _parse_version(pattern_version):
                major_lag = _parse_version(pattern_version)[0:2] > _parse_version(cv)[0:2]
                if major_lag:
                    errors.append(
                        f"{name}: maturity=full with contract_version {cv} while pattern is "
                        f"{pattern_version} — use maturity=core or catch up templates"
                    )

        role = extra.get("role_profile")
        if role is not None and role not in {"writer", "viewer", "hybrid"}:
            errors.append(f"{name}: invalid role_profile={role!r}")

        # Align with matrix defaults when present
        if name in defaults:
            exp_mat = defaults[name].get("maturity")
            exp_prof = defaults[name].get("profile")
            if exp_mat and maturity and maturity != exp_mat:
                warnings.append(
                    f"{name}: manifest maturity={maturity} != matrix default {exp_mat}"
                )
            if exp_prof and isinstance(orch, dict) and orch.get("profile") != exp_prof:
                warnings.append(
                    f"{name}: orchestration.profile={orch.get('profile')} "
                    f"!= matrix default {exp_prof}"
                )

    # Template integrity: manifest promises must match template files on disk
    for name, extra in manifests.items():
        t_err, t_warn = check_template_integrity(ADAPTERS_DIR / name, extra, name)
        errors.extend(t_err)
        warnings.extend(t_warn)

    # Canonical tools check + shim policy (.claude/tools must stay thin)
    tools_dir = REPO_ROOT / "tools"
    claude_tools = REPO_ROOT / ".claude" / "tools"
    if not tools_dir.is_dir():
        errors.append("missing canonical tools/ directory at repo root")
    if not (tools_dir / "runtime" / "suggest-next.py").is_file():
        errors.append("missing tools/runtime/suggest-next.py (canonical EP-033 hook)")
    if not (tools_dir / "analytics" / "show-session-tokens.py").is_file():
        errors.append("missing tools/analytics/show-session-tokens.py (canonical Token Ledger)")

    if claude_tools.is_dir():
        if not (claude_tools / "README.md").is_file():
            errors.append(
                ".claude/tools/ exists without README.md — required shim policy note"
            )
        fat: list[str] = []
        for path in sorted(claude_tools.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "README.md" or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            is_shim = "Shim:" in text or "backward-compat wrapper" in text
            if not is_shim or len(lines) > 20:
                fat.append(f"{path.relative_to(REPO_ROOT)} ({len(lines)} lines, shim={is_shim})")
        if fat:
            errors.append(
                ".claude/tools/ must contain only thin shims (≤20 lines, marker 'Shim:'): "
                + "; ".join(fat[:8])
                + ("…" if len(fat) > 8 else "")
            )

    summary = {
        "pattern_version": pattern_version,
        "adapters": sorted(manifests.keys()),
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        import json

        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"pattern_version={pattern_version}  adapters={len(manifests)}")
        for w in warnings:
            print(f"WARN  {w}")
        for e in errors:
            print(f"ERROR {e}")
        if not errors and not warnings:
            print("OK — adapter registry aligned with capability matrix")
        elif not errors:
            print(f"OK with {len(warnings)} warning(s)")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
