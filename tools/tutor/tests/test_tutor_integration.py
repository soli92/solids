"""tools/tutor/tests/test_tutor_integration.py — Tutor + StudentModel integration test.

6 test cases corresponding to the Acceptance Criteria AC4 and AC5 of US-161:

  Test 1 (AC4): low mastery (0.2) → scaffold_level == 1 (worked example)
  Test 2 (AC4): average mastery (0.5) → scaffold_level == 2 (example with holes)
  Test 3 (AC4): high mastery (0.8) → scaffold_level == 3 (autonomous problem)
  Test 4 (AC5): Unlock mode → should_ask_recall == False
  Test 5 (AC5): Learning mode → should_ask_recall == True
  Test 6 (AC4): node absent → mastery default 0.0 → scaffold_level == 1

Framework: pytest + stdlib. No external dependencies.
Fixture: tmp_path (pytest built-in) for per-test filesystem isolation.

[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/TSK-362-test-integration-tutor-student-model.md]


"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.tutor.student_model import StudentModel
from tools.tutor.tutor_logic import select_scaffold_level, should_ask_recall


# ---------------------------------------------------------------------------
# Test 1 — AC4: low mastery → worked example (level 1)

# ---------------------------------------------------------------------------

def test_scaffold_low_mastery(tmp_path: Path) -> None:
    """AC4: mastery=0.2 (< 0.4) → livello 1 (worked example).

    Setup: StudentModel con nodo "x" a mastery=0.2.
    Assert: select_scaffold_level ritorna 1.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("x", mastery=0.2)

    level = select_scaffold_level(sm, "x")

    assert level == 1


# ---------------------------------------------------------------------------
# Test 2 — AC4: average mastery → example with holes (level 2)

# ---------------------------------------------------------------------------

def test_scaffold_medium_mastery(tmp_path: Path) -> None:
    """AC4: mastery=0.5 (0.4..0.7) → livello 2 (esempio con buchi).

    Setup: StudentModel con nodo "x" a mastery=0.5.
    Assert: select_scaffold_level ritorna 2.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("x", mastery=0.5)

    level = select_scaffold_level(sm, "x")

    assert level == 2


# ---------------------------------------------------------------------------
# Test 3 — AC4: high mastery → autonomous problem (level 3)

# ---------------------------------------------------------------------------

def test_scaffold_high_mastery(tmp_path: Path) -> None:
    """AC4: mastery=0.8 (>= 0.7) → livello 3 (problema autonomo).

    Setup: StudentModel con nodo "x" a mastery=0.8.
    Assert: select_scaffold_level ritorna 3.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("x", mastery=0.8)

    level = select_scaffold_level(sm, "x")

    assert level == 3


# ---------------------------------------------------------------------------
# Test 4 — AC5: Unlocking mode → no recall request

# ---------------------------------------------------------------------------

def test_sblocco_no_recall() -> None:
    """AC5: modalita' Sblocco → should_ask_recall == False.

    Nessuna fixture richiesta: funzione pura senza I/O.
    """
    assert should_ask_recall("Sblocco") is False


# ---------------------------------------------------------------------------
# Test 5 — AC5: Learning mode → recall question

# ---------------------------------------------------------------------------

def test_apprendimento_recall() -> None:
    """AC5: modalita' Apprendimento → should_ask_recall == True.

    Nessuna fixture richiesta: funzione pura senza I/O.
    """
    assert should_ask_recall("Apprendimento") is True


# ---------------------------------------------------------------------------
# Test 6 — AC4: node absent → mastery default 0.0 → level 1

# ---------------------------------------------------------------------------

def test_scaffold_missing_node(tmp_path: Path) -> None:
    """AC4: nodo non presente nel modello → mastery default 0.0 → livello 1.

    Setup: StudentModel vuoto (nessun nodo creato).
    Assert: select_scaffold_level su "nodo_inesistente" ritorna 1.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    # No intentionally created nodes

    level = select_scaffold_level(sm, "nodo_inesistente")

    assert level == 1
