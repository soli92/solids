"""tools/tutor/tests/test_retrieval_loop.py — Test loop retrieval practice (TSK-390).

5 test case che coprono l'Acceptance Criterion AC7 di US-163 e le invarianti L-1/L-3:

  Test 1 (AC4+AC7): mastery_after > mastery_before su risposta corretta
  Test 2 (AC4+AC7): mastery_after <= mastery_before e errore registrato su risposta errata
  Test 3 (AC5+AC7): next_review(correct=True) > next_review(correct=False) per stesso nodo
  Test 4 (AC6/L-1): loop schedula sempre anche con correct=None (L3 epistemico)
  Test 5 (AC2/L-3): question_generator e answer_evaluator sono moduli distinti

Framework: pytest + stdlib + unittest.mock. Nessuna dipendenza esterna.
Fixture: tmp_path (pytest built-in) per isolamento filesystem per-test.

[^src: management/kanban/EP-045-capability-formativa/US-163-loop-retrieval-practice/TSK-390-test-retrieval-loop.md]
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from tools.tutor.retrieval_loop import run_retrieval_loop
from tools.tutor.student_model import StudentModel


# ---------------------------------------------------------------------------
# Helper — context manager che patcha tools.tutor.retrieval_loop.evaluate_answer
# ---------------------------------------------------------------------------

@contextmanager
def mock_evaluate_answer(correct):
    """Patcha evaluate_answer nel namespace retrieval_loop con un fake deterministico.

    Args:
        correct: bool | None — valore restituito nel campo "correct" del dict.
    """
    def fake_eval(question, student_answer):
        return {
            "correct": correct,
            "feedback": "mock",
            "epistemic_level": question.get("epistemic_level", 3),
            "method": "mock",
        }
    with patch("tools.tutor.retrieval_loop.evaluate_answer", side_effect=fake_eval):
        yield


# ---------------------------------------------------------------------------
# Test 1 — AC4 + AC7: mastery aumenta su risposta corretta
# ---------------------------------------------------------------------------

def test_mastery_increases_on_correct(tmp_path):
    """mastery_after > mastery_before quando evaluate_answer restituisce correct=True."""
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("test-node", mastery=0.3)

    with mock_evaluate_answer(correct=True):
        result = run_retrieval_loop(
            node_id="test-node",
            node_content="Esempio di contenuto nodo.",
            student_model=sm,
            scaffold_level=1,
            student_answer_fn=lambda q: "La risposta corretta al nodo test-node.",
        )

    assert result["mastery_after"] > result["mastery_before"], (
        f"mastery_after={result['mastery_after']} doveva essere > "
        f"mastery_before={result['mastery_before']}"
    )


# ---------------------------------------------------------------------------
# Test 2 — AC4 + AC7: mastery non aumenta ed errore registrato su risposta errata
# ---------------------------------------------------------------------------

def test_mastery_decreases_on_wrong(tmp_path):
    """mastery_after <= mastery_before e nodo["errors"] non vuoto quando correct=False."""
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("test-node", mastery=0.5)

    with mock_evaluate_answer(correct=False):
        result = run_retrieval_loop(
            node_id="test-node",
            node_content="Esempio di contenuto.",
            student_model=sm,
            scaffold_level=2,
            student_answer_fn=lambda q: "risposta errata",
        )

    assert result["mastery_after"] <= result["mastery_before"], (
        f"mastery_after={result['mastery_after']} doveva essere <= "
        f"mastery_before={result['mastery_before']}"
    )
    node = sm.get_node("test-node")
    assert node is not None, "nodo test-node non trovato nello Student Model"
    assert len(node.get("errors", [])) > 0, (
        "L'errore doveva essere registrato nel nodo dopo risposta errata"
    )


# ---------------------------------------------------------------------------
# Test 3 — AC5 + AC7: schedulazioni differenziate (correct > wrong)
# ---------------------------------------------------------------------------

def test_schedules_differ_correct_vs_wrong(tmp_path):
    """next_review(correct=True) > next_review(correct=False) per stesso nodo e stessa data."""
    sm_correct = StudentModel(path=str(tmp_path / "correct.json"))
    sm_correct.upsert_node("x", mastery=0.3)

    sm_wrong = StudentModel(path=str(tmp_path / "wrong.json"))
    sm_wrong.upsert_node("x", mastery=0.3)

    with mock_evaluate_answer(correct=True):
        result_correct = run_retrieval_loop(
            node_id="x",
            node_content="contenuto",
            student_model=sm_correct,
            scaffold_level=1,
            student_answer_fn=lambda q: "ok",
        )

    with mock_evaluate_answer(correct=False):
        result_wrong = run_retrieval_loop(
            node_id="x",
            node_content="contenuto",
            student_model=sm_wrong,
            scaffold_level=1,
            student_answer_fn=lambda q: "no",
        )

    date_correct = date.fromisoformat(result_correct["next_review"])
    date_wrong = date.fromisoformat(result_wrong["next_review"])

    assert date_correct > date_wrong, (
        f"next_review corretta ({date_correct}) doveva essere > "
        f"next_review errata ({date_wrong})"
    )


# ---------------------------------------------------------------------------
# Test 4 — AC6 / INVARIANTE L-1: loop schedula sempre anche con correct=None
# ---------------------------------------------------------------------------

def test_loop_always_schedules(tmp_path):
    """INVARIANTE L-1: result['next_review'] e' non-None e non-'' anche per L3 (correct=None)."""
    sm = StudentModel(path=str(tmp_path / "m.json"))
    sm.upsert_node("x")

    with mock_evaluate_answer(correct=None):
        result = run_retrieval_loop(
            node_id="x",
            node_content="contenuto L3",
            student_model=sm,
            scaffold_level=3,
            student_answer_fn=lambda q: "claim",
        )

    assert result["next_review"] is not None, (
        "next_review non deve essere None anche per L3 (correct=None)"
    )
    assert result["next_review"] != "", (
        "next_review non deve essere stringa vuota anche per L3 (correct=None)"
    )


# ---------------------------------------------------------------------------
# Test 5 — AC2 / INVARIANTE L-3: Generatore e Valutatore sono moduli distinti
# ---------------------------------------------------------------------------

def test_generator_and_evaluator_are_separate_modules():
    """INVARIANTE L-3: question_generator non ha evaluate_answer, answer_evaluator non ha generate_recall_question."""
    import tools.tutor.question_generator as gen_mod
    import tools.tutor.answer_evaluator as eval_mod

    assert not hasattr(gen_mod, "evaluate_answer"), (
        "Il Generatore (question_generator) non deve esporre evaluate_answer"
    )
    assert not hasattr(eval_mod, "generate_recall_question"), (
        "Il Valutatore (answer_evaluator) non deve esporre generate_recall_question"
    )
