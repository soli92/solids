"""tools/tutor/tests/test_student_model.py — Test StudentModel (US-162 AC1-AC6).

6 test cases corresponding to the US-162 Acceptance Criteria:

  Test 1 (AC1): persist cross-session — save and reload mastery
  Test 2 (AC2): Minimum fields present after upsert_node
  Test 3 (AC3): staleness on source change — is_stale=True after different hash
  Test 4 (AC4): topological sort prerequisites — A < B < C
  Test 5 (AC5): update mastery persists on subsequent session
  Test 6 (AC6): spaced repetition — correct date > incorrect date

Framework: pytest + stdlib. No external dependencies.
Fixture: tmp_path (pytest built-in) for per-test filesystem isolation.
Injectable today parameter for determinism in spaced repetition tests.

[^src: management/kanban/EP-045-capability-formativa/US-162-student-model-persistente/TSK-360-test-student-model.md]


"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools.tutor.student_model import StudentModel


# ---------------------------------------------------------------------------
# Test 1 — AC1: persist cross-session
# ---------------------------------------------------------------------------

def test_persist_cross_session(tmp_path: Path) -> None:
    """AC1: mastery aggiornata in sessione 1 e' visibile in sessione 2 dopo reload.

    Setup: StudentModel su percorso temporaneo; update_mastery + save.
    Assert: nuova istanza (stessa path) carica mastery=0.6.
    """
    path = str(tmp_path / "student-model.json")
    sm1 = StudentModel(path=path)
    sm1.update_mastery("retrieval-protocol", 0.6)
    sm1.save()

    sm2 = StudentModel(path=path)  # new instance = new "session"
    node = sm2.get_node("retrieval-protocol")
    assert node is not None
    assert abs(node["mastery"] - 0.6) < 0.001


# ---------------------------------------------------------------------------
# Test 2 — AC2: minimum fields present
# ---------------------------------------------------------------------------

def test_campi_minimi(tmp_path: Path) -> None:
    """AC2: upsert_node garantisce la presenza di tutti i campi obbligatori dello schema.

    Setup: StudentModel in memoria (tmp_path); upsert_node su un nodo "x".
    Assert: i 5 campi obbligatori (mastery, errors, next_review, source_ref,
            is_stale) sono presenti nel nodo restituito da get_node.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("x", mastery=0.3)
    node = sm.get_node("x")
    required_fields = ["mastery", "errors", "next_review", "source_ref", "is_stale"]
    for f in required_fields:
        assert f in node, f"campo {f} assente"


# ---------------------------------------------------------------------------
# Test 3 — AC3: staleness su source change
# ---------------------------------------------------------------------------

def test_staleness_on_source_change(tmp_path: Path) -> None:
    """AC3: is_stale diventa True quando check_staleness riceve un hash diverso.

    Setup: update_provenance con hash_old → is_stale=False.
    Assert: check_staleness con hash_new → restituisce [node_id] e is_stale=True.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.update_provenance("x", "wiki/concepts/x.md", "hash_old")
    assert sm.get_node("x")["is_stale"] == False

    stale = sm.check_staleness("wiki/concepts/x.md", "hash_new")
    assert "x" in stale
    assert sm.get_node("x")["is_stale"] == True


# ---------------------------------------------------------------------------
# Test 4 — AC4: topological sort prerequisiti
# ---------------------------------------------------------------------------

def test_topological_sort(tmp_path: Path) -> None:
    """AC4: topological_order restituisce i nodi in ordine prerequisiti-prima.

    Grafo: C dipende da B, B dipende da A (A e' la radice).
    Assert: A < B < C nell'ordine restituito.
    """
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("A", prerequisite_ids=[])
    sm.upsert_node("B", prerequisite_ids=["A"])
    sm.upsert_node("C", prerequisite_ids=["B"])

    order = sm.topological_order("C")
    # A must precede B, B must precede C

    assert order.index("A") < order.index("B")
    assert order.index("B") < order.index("C")


# ---------------------------------------------------------------------------
# Test 5 — AC5: update mastery reflected next session
# ---------------------------------------------------------------------------

def test_update_mastery_persists(tmp_path: Path) -> None:
    """AC5: la mastery aggiornata con delta e' salvata e ricaricata correttamente.

    Setup: upsert_node mastery=0.2, update_mastery delta=+0.3 (risultato 0.5), save.
    Assert: nuova istanza sulla stessa path carica mastery=0.5.
    """
    path = str(tmp_path / "m.json")
    sm = StudentModel(path=path)
    sm.upsert_node("y", mastery=0.2)
    sm.update_mastery("y", +0.3)  # mastery = 0.5
    sm.save()

    sm2 = StudentModel(path=path)
    assert abs(sm2.get_node("y")["mastery"] - 0.5) < 0.001


# ---------------------------------------------------------------------------
# Test 6 — AC6: spaced repetition comportamentale
# ---------------------------------------------------------------------------

def test_spaced_repetition(tmp_path: Path) -> None:
    """AC6: schedule_next_review(correct=True) produce una data futura piu' lontana
    di schedule_next_review(correct=False) sulla stessa data di riferimento.

    Setup: today iniettato come 2026-07-09 per determinismo.
    Assert: date_correct > date_wrong (SM-2: raddoppio intervallo vs reset a 1).
    """
    TODAY = date(2026, 7, 9)
    sm = StudentModel(path=str(tmp_path / "m.json"))

    # risposta corretta -> data lontana (intervallo raddoppiato)
    sm.upsert_node("z")
    date_correct = sm.schedule_next_review("z", correct=True, today=TODAY)

    sm.upsert_node("z", _internal_interval_days=1)  # reset intervallo
    date_wrong = sm.schedule_next_review("z", correct=False, today=TODAY)

    assert date.fromisoformat(date_correct) > date.fromisoformat(date_wrong)
