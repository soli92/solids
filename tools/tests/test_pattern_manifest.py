"""US-319 / TSK-728 — il manifesto di caricamento copre tutta la flotta.

Ogni comando e agente di `.claude/` compare nella foglia del manifesto, e ogni modulo
che la foglia nomina e' un modulo vero dell'indice (tabella §Moduli di PATTERN.md).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "lint"))
from pattern_modules import module_names, pattern_files  # noqa: E402

LEAF = ROOT / ".claude" / "skills" / "references" / "dispatch-policy" / "manifesto-caricamento.md"


def _units(kind: str) -> list[str]:
    return sorted(p.stem for p in (ROOT / ".claude" / kind).glob("*.md"))


def test_ogni_comando_e_agente_ha_una_riga():
    text = LEAF.read_text(encoding="utf-8")
    mancanti = [f"/{c}" for c in _units("commands") if f"`/{c}`" not in text]
    mancanti += [a for a in _units("agents") if f"`{a}`" not in text]
    assert not mancanti, f"unita' senza riga nel manifesto: {mancanti}"


def test_i_moduli_nominati_sono_quelli_dell_indice():
    text = LEAF.read_text(encoding="utf-8")
    nominati = set(re.findall(r"`(PATTERN-[a-z]+\.md)`", text))
    indice = set(module_names((ROOT / "PATTERN.md").read_text(encoding="utf-8")))
    assert nominati == indice, (nominati, indice)
    assert len(pattern_files(ROOT)) == 1 + len(indice)
