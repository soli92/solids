"""pattern_modules.py — il PATTERN e' un indice piu' moduli (US-319, TSK-728).

`PATTERN.md` contiene titolo, §0-§11 e la tabella «## Moduli»; le sezioni §12+ vivono
nei file `PATTERN-<nome>.md` elencati in quella tabella. La numerazione § e' unica su
tutti i file. Un lettore meccanico che cerca una sezione deve leggere l'indice **e** i
moduli: questo modulo e' il solo posto in cui si decide quali file sono «il PATTERN».

Regole:
  - i moduli sono quelli **linkati nella tabella §Moduli** dell'indice, nell'ordine della
    tabella. Mai un glob: `PATTERN-historical.md` (archivio, ADR-055) non e' contratto;
  - un modulo linkato ma assente non e' saltato in silenzio: `missing_modules()` lo dice;
  - una factory col PATTERN monolitico (nessuna tabella) resta valida: l'elenco e' il
    solo `PATTERN.md`, e il testo e' quello di sempre.

Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path

INDEX_NAME = "PATTERN.md"
_MODULES_HEADING_RE = re.compile(r"^##\s+Moduli\b", re.M)
_MODULE_LINK_RE = re.compile(r"\]\((PATTERN-[A-Za-z0-9_\-]+\.md)\)")


def _index_path(root_or_index: Path) -> Path:
    p = Path(root_or_index)
    return p if p.suffix == ".md" else p / INDEX_NAME


def module_names(index_text: str) -> list[str]:
    """Nomi dei moduli linkati nella tabella «## Moduli» dell'indice, in ordine."""
    m = _MODULES_HEADING_RE.search(index_text)
    if not m:
        return []
    seen: list[str] = []
    for name in _MODULE_LINK_RE.findall(index_text[m.end():]):
        if name not in seen:
            seen.append(name)
    return seen


def pattern_files(root_or_index: Path) -> list[Path]:
    """`[PATTERN.md, PATTERN-<a>.md, …]` esistenti, nell'ordine dell'indice."""
    index = _index_path(root_or_index)
    if not index.is_file():
        return []
    text = index.read_text(encoding="utf-8", errors="replace")
    out = [index]
    for name in module_names(text):
        p = index.parent / name
        if p.is_file():
            out.append(p)
    return out


def missing_modules(root_or_index: Path) -> list[str]:
    """Moduli linkati nell'indice ma assenti su disco."""
    index = _index_path(root_or_index)
    if not index.is_file():
        return []
    text = index.read_text(encoding="utf-8", errors="replace")
    return [n for n in module_names(text) if not (index.parent / n).is_file()]


def pattern_text(root_or_index: Path) -> str:
    """Testo del PATTERN completo: indice + moduli, concatenati in ordine."""
    parts = [p.read_text(encoding="utf-8", errors="replace") for p in pattern_files(root_or_index)]
    return "\n".join(parts)
