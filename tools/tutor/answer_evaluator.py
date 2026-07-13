"""
answer_evaluator.py — Verifica la risposta dello studente con livello epistemico corretto.

Terzo step del loop retrieval-practice (US-163 Business Rule 3).
Dispatcha la verifica sul livello epistemico della domanda (L1/L2/L3).

Solo stdlib + sandbox_exec_tool.execute_snippet + os. Nessuna dipendenza esterna.

INVARIANTE V-1: il Valutatore NON genera domande (nessuna logica generate_*).
INVARIANTE V-2: per L1, la verifica usa esecuzione reale del codice via execute_snippet
               (non semplice pattern matching).
INVARIANTE V-3: per L3, correct=None e method="L3_manual_check_required" — mai invocare
               un LLM come unico valutatore.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from tools.tutor.sandbox_exec_tool import execute_snippet

__all__ = ["evaluate_answer"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_repo_root() -> Path:
    """
    Risale dal CWD cercando .git/ o factory.config.yaml.

    Returns:
        Path al root del repo, oppure CWD se non trovato.
    """
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "factory.config.yaml").exists():
            return candidate
    return current


def _extract_code_snippet(text: str) -> str | None:
    """
    Estrae il primo snippet di codice da text.

    Priorita':
    1. Blocco delimitato da triple backtick (``` ... ```), con o senza language tag.
    2. Linee consecutive che iniziano con 4+ spazi o tab (indentazione).

    Returns:
        Il codice estratto come stringa, oppure None se non trovato.
    """
    # 1. Cerca blocchi ```...```
    pattern_fenced = re.compile(r"```(?:\w+)?\n?(.*?)```", re.DOTALL)
    match = pattern_fenced.search(text)
    if match:
        return match.group(1)

    # 2. Cerca linee indentate con 4+ spazi o tab
    indented_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("    ") or line.startswith("\t"):
            indented_lines.append(line)
        elif indented_lines:
            # Blocco interrotto — usa il primo blocco trovato
            break

    if indented_lines:
        # Dedent: rimuove il prefisso comune minimo
        prefix = "    " if indented_lines[0].startswith("    ") else "\t"
        return "\n".join(
            line[len(prefix):] if line.startswith(prefix) else line
            for line in indented_lines
        )

    return None


# ---------------------------------------------------------------------------
# Valutatori per livello
# ---------------------------------------------------------------------------


def _eval_l1_code_exec(question: dict, student_answer: str) -> dict:
    """
    Estrae lo snippet di codice dalla student_answer ed esegue via execute_snippet.

    correct = (exit_code == 0)
    method  = "code_exec"

    INVARIANTE V-2: usa esecuzione reale del codice, non pattern matching.
    """
    level = question.get("epistemic_level", 1)
    snippet = _extract_code_snippet(student_answer)

    if snippet is None:
        return {
            "correct": False,
            "feedback": "L1: nessun snippet di codice trovato nella risposta. "
                        "Includi il codice tra ``` backtick o con indentazione di 4 spazi.",
            "epistemic_level": level,
            "method": "code_exec",
        }

    result = execute_snippet(snippet)

    if result.get("timed_out"):
        return {
            "correct": False,
            "feedback": (
                "L1: esecuzione scaduta (timeout). "
                f"Stderr: {result.get('stderr', '')}"
            ),
            "epistemic_level": level,
            "method": "code_exec",
        }

    exit_code: int = result.get("exit_code", -1)
    correct: bool = exit_code == 0

    if correct:
        feedback = (
            f"L1: codice eseguito correttamente (exit_code=0). "
            f"Stdout: {result.get('stdout', '').strip()}"
        )
    else:
        feedback = (
            f"L1: codice terminato con exit_code={exit_code}. "
            f"Stderr: {result.get('stderr', '').strip()}"
        )

    return {
        "correct": correct,
        "feedback": feedback,
        "epistemic_level": level,
        "method": "code_exec",
    }


def _eval_l2_citation(question: dict, student_answer: str) -> dict:
    """
    Verifica che student_answer contenga almeno un path wiki/ o tools/ che esiste nel repo.

    Cerca pattern `wiki/\\S+` o `tools/\\S+` nella risposta.
    correct = True se almeno una fonte viene verificata come esistente (os.path.exists).
    method  = "citation_check"
    """
    level = question.get("epistemic_level", 2)
    repo_root = _get_repo_root()

    pattern = re.compile(r"(?:wiki|tools)/\S+")
    candidates: list[str] = pattern.findall(student_answer)

    # Rimuove punteggiatura finale che potrebbe fare parte della frase, non del path
    cleaned: list[str] = []
    for c in candidates:
        c = c.rstrip(".,;:)\"'")
        cleaned.append(c)

    found_existing: list[str] = []
    for raw_path in cleaned:
        full_path = repo_root / raw_path
        if os.path.exists(str(full_path)):
            found_existing.append(raw_path)

    if not candidates:
        return {
            "correct": False,
            "feedback": (
                "L2: nessuna citazione di fonte trovata nella risposta. "
                "Cita almeno un path del tipo wiki/<percorso> o tools/<percorso>."
            ),
            "epistemic_level": level,
            "method": "citation_check",
        }

    correct: bool = len(found_existing) > 0

    if correct:
        feedback = (
            f"L2: fonte verificata — {found_existing[0]} esiste nel repo."
        )
    else:
        feedback = (
            f"L2: path citati ({cleaned}) non trovati nel repo. "
            "Verifica che il percorso sia corretto e relativo alla root del progetto."
        )

    return {
        "correct": correct,
        "feedback": feedback,
        "epistemic_level": level,
        "method": "citation_check",
    }


def _eval_l3_claim(question: dict, student_answer: str) -> dict:
    """
    Non esiste valutatore automatico forte per affermazioni L3.

    correct = None, method = "L3_manual_check_required"
    feedback = "Affermazione L3: richiede revisione contestuale o umana."

    INVARIANTE V-3: non invocare un secondo LLM come unico valutatore.
    """
    level = question.get("epistemic_level", 3)
    return {
        "correct": None,
        "feedback": "Affermazione L3: richiede revisione contestuale o umana.",
        "epistemic_level": level,
        "method": "L3_manual_check_required",
    }


# ---------------------------------------------------------------------------
# Funzione pubblica
# ---------------------------------------------------------------------------


def evaluate_answer(question: dict, student_answer: str) -> dict:
    """
    Verifica student_answer in base al livello epistemico della question.

    Args:
        question:       dict prodotto da question_generator.generate_recall_question().
                        Deve contenere la chiave "epistemic_level" (int 1|2|3).
                        Se assente, fallback a L3.
        student_answer: risposta testuale dello studente.

    Returns:
        {
            "correct":         bool | None,  # None se L3 (non auto-valutabile)
            "feedback":        str,
            "epistemic_level": int,          # 1 | 2 | 3 (copiato dalla question)
            "method":          str,          # "code_exec" | "citation_check" |
                                             # "L3_manual_check_required"
        }

    INVARIANTE V-1: il Valutatore NON genera domande (no question logic).
    INVARIANTE V-2: per L1, la verifica usa esecuzione reale del codice (non pattern matching).
    INVARIANTE V-3: per L3, correct=None e method="L3_manual_check_required" — mai LLM-only.
    """
    level: int = question.get("epistemic_level", 3)  # fallback L3 se assente

    if level == 1:
        return _eval_l1_code_exec(question, student_answer)
    elif level == 2:
        return _eval_l2_citation(question, student_answer)
    else:
        # L3 o qualsiasi valore non riconosciuto
        return _eval_l3_claim(question, student_answer)
