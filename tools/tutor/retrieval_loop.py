"""
retrieval_loop.py — US-163 invariant sequence: generate → response → verify →
update Student Model → review schedule.

INVARIANT L-1: `run_retrieval_loop()` NEVER returns before step 5
  (mandatory scheduling).  There is no early `return`.
INVARIANT L-2: the Student Model is updated in the current cycle (step 4
  performed before step 5).
INVARIANT L-3: the Generator (step 1, `question_generator`) and the Evaluator
  (step 3, `answer_evaluator`) are calls to separate Python modules; not
  there is direct dependency between the two.


"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from tools.tutor.answer_evaluator import evaluate_answer          # INVARIANTE L-3
from tools.tutor.question_generator import generate_recall_question  # INVARIANTE L-3
from tools.tutor.student_model import StudentModel

__all__ = ["run_retrieval_loop"]


def run_retrieval_loop(
    node_id: str,
    node_content: str,
    student_model: StudentModel,
    scaffold_level: int,
    student_answer_fn: Callable[[dict], str],
) -> dict:
    """Esegue un ciclo completo di retrieval practice sul nodo indicato.

    Sequenza invariante US-163:

    1. GENERA:    ``question = generate_recall_question(node_id, node_content,
                  scaffold_level)`` — via ``question_generator`` (L-3).
    2. RISPOSTA:  ``student_answer = student_answer_fn(question)`` — callback
                  iniettabile dal chiamante (es. input CLI, mock in test, LLM).
    3. VERIFICA:  ``evaluation = evaluate_answer(question, student_answer)``
                  — via ``answer_evaluator`` (L-3).
    4. AGGIORNA:  ``student_model.update_mastery()`` + registra errore se
                  ``correct is False``; nessuna modifica se ``correct is None``
                  (L3 epistemico, non auto-valutabile) — INVARIANTE L-2.
    5. SCHEDULA:  ``student_model.schedule_next_review(node_id,
                  correct=effective_correct)`` — SEMPRE eseguito, anche per
                  risposte L3 — INVARIANTE L-1.

    INVARIANTE L-1: nessun ``return`` prima dello step 5.
    INVARIANTE L-2: lo Student Model viene aggiornato nel ciclo corrente
      (step 4 prima di step 5).
    INVARIANTE L-3: Generatore (step 1) e Valutatore (step 3) sono moduli
      Python distinti; import separati, nessuna dipendenza reciproca.

    Args:
        node_id:           Slug univoco del nodo di competenza.
        node_content:      Testo completo del nodo (passato al generatore).
        student_model:     Istanza ``StudentModel`` da aggiornare in-place.
        scaffold_level:    Livello di scaffolding pre-calcolato (1 | 2 | 3).
        student_answer_fn: Callable ``(question: dict) -> str`` che restituisce
                           la risposta dello studente.  Iniettabile per
                           test/mock.

    Returns:
        Dizionario con i seguenti campi::

            {
              "node_id":        str,    # node slug
              "question":       dict,   # prodotto da QuestionGenerator
              "student_answer": str,    # risposta fornita dallo studente
              "evaluation":     dict,   # prodotto da AnswerEvaluator
              "mastery_before": float,  # mastery before step 4
              "mastery_after":  float,  # mastery after step 4
              "next_review":    str,    # data ISO-8601 schedulata allo step 5
            }
    """
    # ------------------------------------------------------------------
    # Step 1 — GENERATE recall request

    # ------------------------------------------------------------------
    question: dict = generate_recall_question(node_id, node_content, scaffold_level)

    # ------------------------------------------------------------------
    # Step 2 — student answer (injectable callback)
    # ------------------------------------------------------------------
    student_answer: str = student_answer_fn(question)

    # ------------------------------------------------------------------
    # Step 3 — CHECK answer (separate form, INVARIANT L-3)

    # ------------------------------------------------------------------
    evaluation: dict = evaluate_answer(question, student_answer)

    # ------------------------------------------------------------------
    # Step 4 — UPDATE Student Model (INVARIANT L-2)

    # ------------------------------------------------------------------
    node_before = student_model.get_node(node_id)
    mastery_before: float = float(node_before["mastery"]) if node_before else 0.0

    correct = evaluation.get("correct")  # bool | None (L3 epistemico)

    if correct is True:
        student_model.update_mastery(node_id, +0.15)
    elif correct is False:
        student_model.update_mastery(node_id, -0.10)
        # `add_error()` does not exist in StudentModel — I use direct pattern

        node = student_model.get_node(node_id)
        if node is not None:
            node.setdefault("errors", []).append({
                "ts": datetime.utcnow().isoformat() + "Z",
                "desc": evaluation.get("feedback", "")[:80],
            })
            student_model.upsert_node(node_id, errors=node["errors"])
    # correct is None (L3): no mastery changes, no errors


    node_after = student_model.get_node(node_id)
    mastery_after: float = float(node_after["mastery"]) if node_after else 0.0

    # ------------------------------------------------------------------
    # Step 5 — SCHEDULE next review (INVARIANT L-1: always performed)

    # ------------------------------------------------------------------
    # For L3 (correct is None): use correct=True cautionary — review soon
    effective_correct: bool = correct if correct is not None else True
    next_review: str = student_model.schedule_next_review(node_id, correct=effective_correct)

    return {
        "node_id": node_id,
        "question": question,
        "student_answer": student_answer,
        "evaluation": evaluation,
        "mastery_before": mastery_before,
        "mastery_after": mastery_after,
        "next_review": next_review,
    }
