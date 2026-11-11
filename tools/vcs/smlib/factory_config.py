"""Parsing mirato di factory.config.yaml -- senza dipendenze esterne.

Estrae:
  - code_paths[] con vcs.mode: submodule (lista dei submodule gestiti dalla factory)
  - base_branch per un target specifico
  - suppress_ai_traces (ai_attribution_policy.suppress_ai_traces)
  - vcs_tooling.submodule_scope (submodule su cui lavorano gli strumenti senza --target)
  - nome factory (`name:` di primo livello, poi `project.name`, poi il nome della cartella)

Parsing riga per riga con regex (stdlib-only, senza PyYAML). Stesso approccio
di tools/vcs/repo-align.py: strip commenti inline, match esatto sui nomi.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(value: str) -> str:
    return value.strip().strip("\"'").strip()


def _scalar(text: str, key: str) -> Optional[str]:
    """Estrae uno scalare di primo livello: `key: value`."""
    m = re.search(
        rf'(?m)^{re.escape(key)}:\s*["\']?([^"\'\n#][^\n#]*?)["\']?\s*(?:#.*)?$',
        text,
    )
    if not m:
        m2 = re.search(rf'(?m)^{re.escape(key)}:\s*["\']["\']', text)
        if m2:
            return ""
        return None
    return m.group(1).strip().strip("\"'")


# ---------------------------------------------------------------------------
# code_paths[] con vcs.mode: submodule
# ---------------------------------------------------------------------------

def list_submodule_code_paths(root: Path) -> List[dict]:
    """Restituisce le entry di code_paths[] con vcs.mode: submodule.

    Ogni dict ha campi: name, path, submodule_path, base_branch.
    """
    config_path = root / "factory.config.yaml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return []

    entries = _parse_code_paths(text)
    return [e for e in entries if e.get("vcs_mode") == "submodule"]


def _parse_code_paths(text: str) -> List[dict]:
    """Parsa code_paths[] da factory.config.yaml (stesso algoritmo di repo-align.py)."""
    lines = text.splitlines()
    in_block = False
    in_vcs = False
    items: List[dict] = []
    current: Optional[dict] = None

    for line in lines:
        raw = line.rstrip()
        stripped = raw.lstrip()

        if not stripped or stripped.startswith("#"):
            continue

        leading = len(raw) - len(stripped)

        if re.match(r'^code_paths:\s*$', raw):
            in_block = True
            continue

        if in_block and leading == 0 and not stripped.startswith("-"):
            in_block = False
            if current is not None:
                items.append(current)
                current = None
            continue

        if not in_block:
            continue

        # Nuovo item: `  - ...`
        if re.match(r'^\s{0,4}-\s', raw):
            if current is not None:
                items.append(current)
            current = {
                "name": None, "path": None, "vcs_mode": None,
                "submodule_path": None, "base_branch": None,
            }
            in_vcs = False
            m = re.match(r'^\s*-\s+(\w[\w_-]*):\s*(.*)', raw)
            if m:
                k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
                if k == "name":
                    current["name"] = v
            continue

        if current is None:
            continue

        # Campi a 4 spazi (item-level)
        if leading == 4:
            in_vcs = False
            m = re.match(r'^\s{4}(\w[\w_-]*):\s*(.*)', raw)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
            if k == "name":
                current["name"] = v
            elif k == "path":
                current["path"] = v
            elif k == "vcs":
                in_vcs = True
            continue

        # Sotto-campi vcs a 6 spazi
        if leading == 6 and in_vcs:
            m = re.match(r'^\s{6}(\w[\w_-]*):\s*(.*)', raw)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip().strip("\"'").split("#")[0].strip()
            if k == "mode":
                current["vcs_mode"] = v
            elif k == "submodule_path":
                current["submodule_path"] = v
            elif k == "base_branch":
                current["base_branch"] = v
            continue

    if in_block and current is not None:
        items.append(current)

    return [i for i in items if i.get("name")]


# ---------------------------------------------------------------------------
# base_branch dal blocco vcs (per target name)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^\s*-\s*name:\s*(.+?)\s*(?:#.*)?$")
_BASE_BRANCH_RE = re.compile(r"^\s*base_branch:\s*(.+?)\s*(?:#.*)?$")


def resolve_base_branch(root: Path, target: str, default: str = "main") -> str:
    """base_branch del target dal blocco vcs, o `default` se non trovato.

    Cerca prima nelle entry code_paths[] con vcs.mode: submodule, poi
    nel blocco legacy vcs. Strip commento inline (no BUG-1). Match esatto
    sul name (no BUG-2, collisione di prefisso).
    """
    # Prima prova: code_paths[] con submodule
    for entry in list_submodule_code_paths(root):
        if entry.get("name") == target:
            bb = entry.get("base_branch")
            if bb:
                return bb

    # Seconda prova: legacy config (riga per riga)
    config_path = root / "factory.config.yaml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return default

    in_target = False
    for line in text.splitlines():
        m_name = _NAME_RE.match(line)
        if m_name:
            name = _clean(m_name.group(1))
            if name == target:
                in_target = True
            elif in_target:
                break
            continue

        m_bb = _BASE_BRANCH_RE.match(line)
        if m_bb and in_target:
            return _clean(m_bb.group(1))

    return default


# ---------------------------------------------------------------------------
# vcs_tooling.submodule_scope
# ---------------------------------------------------------------------------

SCOPES = ("code_paths", "gitmodules")


def submodule_scope(root: Path) -> str:
    """Submodule su cui lavorano gli strumenti senza `--target`.

    `code_paths` (default): solo quelli dichiarati in code_paths[] con vcs.mode: submodule.
    `gitmodules`: tutti quelli di .gitmodules — per le factory con molti submodule di
    servizio che non sono code_path (una derivata ne ha 63, 4 dichiarati).
    """
    try:
        text = (root / "factory.config.yaml").read_text(encoding="utf-8")
    except OSError:
        return "code_paths"
    blocco = re.search(r'(?m)^vcs_tooling:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)', text)
    if blocco:
        m = re.search(r'(?m)^[ \t]+submodule_scope:\s*["\']?([a-z_]+)', blocco.group(1))
        if m and m.group(1) in SCOPES:
            return m.group(1)
    return "code_paths"


def default_target(root: Path) -> Optional[str]:
    """`vcs_tooling.default_target`: submodule usato da checkout/update/commit coordinato
    quando manca --target e i candidati sono piu' d'uno. Assente = nessun default."""
    try:
        text = (root / "factory.config.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    blocco = re.search(r'(?m)^vcs_tooling:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)', text)
    if blocco:
        m = re.search(r'(?m)^[ \t]+default_target:\s*["\']?([^"\'\s#]+)', blocco.group(1))
        if m:
            return m.group(1)
    return None

# ---------------------------------------------------------------------------
# suppress_ai_traces
# ---------------------------------------------------------------------------

def suppress_ai_traces(root: Path) -> bool:
    """True se ai_attribution_policy.suppress_ai_traces: true nel config."""
    config_path = root / "factory.config.yaml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return False
    m = re.search(r'(?m)^\s*suppress_ai_traces:\s*(true|false)\s*(?:#.*)?$', text)
    if m:
        return m.group(1).strip() == "true"
    return False


# ---------------------------------------------------------------------------
# factory_name
# ---------------------------------------------------------------------------

def factory_name(root: Path) -> str:
    """Nome della factory dal config (campo `name:` di primo livello) o dal dirname."""
    config_path = root / "factory.config.yaml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return root.name
    name = _scalar(text, "name")
    if name:
        return name
    progetto = re.search(r'(?m)^project:[ \t]*\n((?:[ \t]+[^\n]*\n?|[ \t]*\n)*)', text)
    if progetto:
        m = re.search(r'(?m)^[ \t]+name:\s*["\']?([^"\'\n#]+?)["\']?\s*(?:#.*)?$', progetto.group(1))
        if m:
            return m.group(1).strip()
    return root.name


# ---------------------------------------------------------------------------
# load_env_file (cross-platform, per sm_update --from-local)
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> dict:
    """Parser minimale di un file KEY=VALUE (stile .env), cross-platform."""
    result: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return result
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):].strip()
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result[key] = value
    return result
