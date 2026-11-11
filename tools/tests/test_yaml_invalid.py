"""Check 3 yaml-invalid — frontmatter che un parser YAML scarterebbe (EP-072, backport)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "lint" / "check-kanban-integrity.py"
_spec = importlib.util.spec_from_file_location("cki", _SCRIPT)
cki = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cki)


def fm(corpo: str) -> str:
    return f"---\n{corpo}\n---\n# corpo\n"


@pytest.mark.parametrize("corpo", [
    "id: TSK-1\ntitle: \"EP-005 (ADR-008): quotato\"\nstatus: todo",
    "id: TSK-1\nnote: >-\n  testo: con due punti\n  su piu' righe",
    "id: TSK-1\ndepends_on:\n  - TSK-2\n  - \"TSK-3: quotato\"",
    "id: TSK-1\nstatus: todo  # commento: in linea",
    "id: TSK-1\nlinks: [a, b]\n\n# commento: a inizio riga",
])
def test_frontmatter_validi(corpo):
    assert cki.yaml_invalido(fm(corpo)) is None


@pytest.mark.parametrize("corpo,motivo", [
    ("id: TSK-1\ntitle: EP-005 (ADR-008): non quotato", "valore non quotato"),
    ("id: TSK-1\nsource:\n  - nota: con altri: due punti", "valore non quotato"),
    ("id: TSK-1\ncode_repos/x\nstatus: todo", "riga senza chiave"),
    ("id: TSK-1\n> citazione nel frontmatter", "blockquote"),
])
def test_frontmatter_non_validi(corpo, motivo):
    assert motivo in cki.yaml_invalido(fm(corpo))


def test_senza_frontmatter_non_e_compito_di_questo_controllo():
    assert cki.yaml_invalido("# nessun frontmatter\n") is None
