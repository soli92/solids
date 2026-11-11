"""Lettura del gate `visual_channel:` da factory.config.yaml.

PyYAML se disponibile, fallback regex altrimenti — stessa convenzione di
`tools/analytics/sprint-progress.py`. Il gate e' opt-in: assente o `false`
significa spento, e spento significa che il comando esce con codice 0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def project_root(start: Path | None = None) -> Path:
    """Risale finche' trova factory.config.yaml. Fallback: cwd."""
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "factory.config.yaml").is_file():
            return candidate
    return Path.cwd()


@dataclass(frozen=True)
class VisualConfig:
    enabled: bool
    host: str
    port: int
    stale_after_seconds: int
    runtime_timeout_seconds: int
    pattern_version: str
    #: Report PM del coordinamento (EP-070). Config dell'operatore, relativa alla root:
    #: vuota = `analytics/coordinamento/config-<git user.name>.json`. `fonte`: `worktree`
    #: (vede anche i `status:` non ancora committati) o `commit` (solo HEAD).
    coordinamento_config: str = ""
    coordinamento_fonte: str = "worktree"

    @property
    def address(self) -> str:
        return f"http://{self.host}:{self.port}"


_DEFAULTS = {"enabled": False, "host": "127.0.0.1", "port": 8756, "stale_after_seconds": 120,
             "runtime_timeout_seconds": 300}


def _parse_with_yaml(text: str) -> dict | None:
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    try:
        return yaml.safe_load(text) or {}
    except Exception:
        return None


def _parse_block_with_regex(text: str, block: str) -> dict:
    """Estrae le coppie `chiave: valore` di un blocco top-level, senza YAML."""
    out: dict = {}
    match = re.search(rf"^{re.escape(block)}:\s*$", text, re.M)
    if not match:
        return out
    for line in text[match.end():].splitlines():
        if line.strip() and not line.startswith((" ", "\t")):
            break  # fine del blocco: nuova chiave top-level
        pair = re.match(r"\s+([a-z_]+):\s*([^#\n]+)", line)
        if pair:
            out[pair.group(1)] = pair.group(2).strip()
    return out


def _coerce(raw: dict) -> dict:
    out = dict(_DEFAULTS)
    for key, default in _DEFAULTS.items():
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if isinstance(default, bool):
            out[key] = value if isinstance(value, bool) else str(value).strip().lower() == "true"
        elif isinstance(default, int):
            try:
                out[key] = int(str(value).strip().strip("'\""))
            except ValueError:
                pass
        else:
            out[key] = str(value).strip().strip("'\"")
    return out


def load(root: Path | None = None) -> VisualConfig:
    root = root or project_root()
    path = root / "factory.config.yaml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""

    parsed = _parse_with_yaml(text)
    if parsed is not None:
        raw = parsed.get("visual_channel") or {}
        pattern = str(parsed.get("pattern_version", "") or "")
    else:
        raw = _parse_block_with_regex(text, "visual_channel")
        found = re.search(r"^pattern_version:\s*\"?([\d.]+)", text, re.M)
        pattern = found.group(1) if found else ""

    values = _coerce(raw if isinstance(raw, dict) else {})
    # Sotto-blocco annidato: lo legge solo PyYAML. Senza, valgono i default — il
    # fallback regex appiattisce i blocchi e non distingue `config:` da altre chiavi.
    coord = raw.get("coordinamento") if isinstance(raw, dict) and parsed is not None else None
    coord = coord if isinstance(coord, dict) else {}
    return VisualConfig(pattern_version=pattern,  # type: ignore[arg-type]
                        coordinamento_config=str(coord.get("config") or ""),
                        coordinamento_fonte=str(coord.get("fonte") or "worktree"),
                        **values)
