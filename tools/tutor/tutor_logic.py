"""
tutor_logic.py — Tutor core logic (TSK-362, EP-045 US-161)

Exposes the helper functions that implement the tutor's behavior rules:
  - select_scaffold_level(): select the scaffolding level based on mastery
    of the node in the StudentModel (AC4 US-161)
  - should_ask_recall(): Determines whether the session requires a recall question
    based on modality (AC5 US-161)

Dependencies: stdlib Python 3.10+ only.
Type hint on StudentModel use `from __future__ import annotations` to avoid
the mandatory import at runtime (forward reference).

Scaffolding Thresholds (from scaffolding-protocol.md, TSK-352):
  mastery < 0.4 → level 1 (worked example)
  mastery 0.4..0.7 → level 2 (example with holes)
  mastery >= 0.7 → level 3 (autonomous problem)

[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/TSK-362-test-integration-tutor-student-model.md]
"""

from __future__ import annotations

__all__ = ["select_scaffold_level", "should_ask_recall"]

# Soglie di scaffolding — allineate a scaffolding-protocol.md (TSK-352)
_THRESHOLD_LOW = 0.4    # below this threshold → level 1
_THRESHOLD_HIGH = 0.7   # from here up → level 3


def select_scaffold_level(student_model: StudentModel, node_id: str) -> int:  # type: ignore[name-defined]
    """Seleziona il livello di scaffolding in base alla mastery del nodo.

    Legge il valore di ``mastery`` dal nodo ``node_id`` nel ``student_model``.
    Se il nodo e' assente nel modello, usa mastery=0.0 come default (nodo non
    ancora studiato → scaffolding massimo).

    Soglie:
        mastery < 0.4  → 1 (worked example — supporto completo)
        0.4 <= mastery < 0.7 → 2 (esempio con buchi — supporto parziale)
        mastery >= 0.7 → 3 (problema autonomo — nessun supporto)

    Args:
        student_model: istanza di ``StudentModel`` con i dati correnti.
        node_id: slug univoco del nodo di competenza da leggere.

    Returns:
        Livello di scaffolding: 1, 2 o 3.
    """
    node = student_model.get_node(node_id)
    if node is None:
        mastery = 0.0
    else:
        mastery = float(node.get("mastery", 0.0))

    if mastery < _THRESHOLD_LOW:
        return 1
    elif mastery < _THRESHOLD_HIGH:
        return 2
    else:
        return 3


def should_ask_recall(session_mode: str) -> bool:
    """Determina se la sessione prevede una domanda di richiamo.

    In modalita' "Apprendimento" il tutor formula una domanda di richiamo
    prima di presentare il nuovo contenuto (consolidamento della memoria).
    In modalita' "Sblocco" (aiuto puntuale su blocco specifico) la domanda
    di richiamo non e' pertinente.

    Args:
        session_mode: stringa che identifica la modalita' di sessione
                      (es. ``"Apprendimento"`` o ``"Sblocco"``).

    Returns:
        ``True`` se ``session_mode == "Apprendimento"``, ``False`` altrimenti.
    """
    return session_mode == "Apprendimento"
