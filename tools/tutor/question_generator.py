"""
QuestionGenerator — genera domande di richiamo calibrate su scaffold_level.

Modulo BE per EP-045 US-163. Primo step del loop di retrieval practice: produce
una domanda il cui testo dipende dal livello di scaffolding gia' risolto dalla
logica tutor (tutor_logic.py, TSK-362) e da una classificazione epistemica
euristica del contenuto del nodo.

INVARIANTE G-1: il testo della domanda dipende da scaffold_level; i tre livelli
producono sempre template distinti e non interscambiabili.

INVARIANTE G-2: questo componente NON valuta mai le risposte — nessuna funzione
di verifica e' esposta. La separazione Generator/Validator e' invariante (US-163
Principio P5 / AC2). Solo `generate_recall_question` fa parte dell'API pubblica.

Requisiti: Python 3.10+, solo stdlib.

[^src: management/kanban/EP-045-capability-formativa/US-163-loop-retrieval-practice/TSK-387-question-generator.md §Technical Specs]
[^src: management/kanban/EP-045-capability-formativa/US-163-loop-retrieval-practice/US-163.md §Business Rules §AC1 §AC2]
[^src: .claude/skills/scaffolding-protocol.md §Calibrazione domanda di richiamo]
"""

__all__ = ["generate_recall_question"]

# ---------------------------------------------------------------------------
# Costanti livelli epistemic_level
# ---------------------------------------------------------------------------

_EPISTEMIC_L1_CODE = 1   # nodo contiene snippet di codice
_EPISTEMIC_L2_CITE = 2   # nodo contiene riferimenti wiki / citazioni
_EPISTEMIC_L3_CLAIM = 3  # nodo e' un claim / concetto testuale generico

# Indicatori euristici per L1 e L2
_CODE_MARKERS: tuple[str, ...] = ("```", "def ", "class ")
_CITE_MARKERS: tuple[str, ...] = ("wiki/", "[^src:")


# ---------------------------------------------------------------------------
# Funzioni interne
# ---------------------------------------------------------------------------

def _infer_epistemic_level(node_content: str) -> int:
    """
    Stima euristica del livello epistemico del nodo in base al contenuto testuale.

    Scala:
      L1 (1) — il contenuto contiene snippet di codice (`` ``` ``, ``def ``, ``class ``).
      L2 (2) — il contenuto contiene riferimenti wiki (``wiki/``, ``[^src:``).
      L3 (3) — default: claim / concetto testuale generico.

    La priorita' e' L1 > L2 > L3: se il contenuto ha sia codice che citazioni
    viene classificato L1 (dominanza codice).

    Args:
        node_content: testo del nodo di competenza (stringa libera).

    Returns:
        Intero 1, 2 o 3 corrispondente al livello epistemico.
    """
    if any(marker in node_content for marker in _CODE_MARKERS):
        return _EPISTEMIC_L1_CODE
    if any(marker in node_content for marker in _CITE_MARKERS):
        return _EPISTEMIC_L2_CITE
    return _EPISTEMIC_L3_CLAIM


def _build_question_text(node_id: str, node_content: str, scaffold_level: int) -> str:
    """
    Costruisce il testo della domanda di richiamo sulla base del livello di scaffolding.

    Template per livello (INVARIANTE G-1 — mai un testo generico identico):
      L1 (worked_example): mostra un excerpt e chiede i passi applicati.
      L2 (fill_in_blank):  chiede di completare la lacuna concettuale.
      L3 (autonomous):     domanda aperta sintetica senza struttura guidata.

    Args:
        node_id:       identificatore del nodo di competenza.
        node_content:  testo del nodo (usato per l'excerpt in L1).
        scaffold_level: 1 | 2 | 3 gia' risolto da tutor_logic.py.

    Returns:
        Stringa con il testo della domanda.

    Raises:
        ValueError: se scaffold_level non e' 1, 2 o 3.
    """
    if scaffold_level == 1:
        # Livello 1 — worked example: mostra un breve excerpt del nodo.
        # Tronca il contenuto a 200 caratteri per mantenere la domanda leggibile.
        excerpt = node_content[:200].strip()
        if len(node_content) > 200:
            excerpt += "..."
        return (
            f"Osserva questo esempio relativo a `{node_id}`: {excerpt} "
            f"Quali passi applica?"
        )

    if scaffold_level == 2:
        # Livello 2 — fill-in-blank: domanda con lacuna concettuale.
        return f"Completa la lacuna: `{node_id}` funziona perche' ___."

    if scaffold_level == 3:
        # Livello 3 — autonomous: problema aperto senza struttura guidata.
        return (
            f"Spiega con parole tue come funziona `{node_id}` e quando usarlo."
        )

    raise ValueError(
        f"scaffold_level deve essere 1, 2 o 3; ricevuto: {scaffold_level!r}"
    )


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def generate_recall_question(
    node_id: str,
    node_content: str,
    scaffold_level: int,  # 1=worked_example, 2=fill_in_blank, 3=autonomous
) -> dict:
    """
    Genera una domanda di richiamo calibrata per il nodo.

    Il ``scaffold_level`` e' gia' risolto dalla logica tutor (tutor_logic.py,
    TSK-362) sulla base della mastery letta dallo Student Model (US-162 / TSK-357):
      mastery < 0.4   → scaffold_level=1 (worked_example)
      0.4..0.7        → scaffold_level=2 (fill_in_blank)
      >= 0.7          → scaffold_level=3 (autonomous)

    Args:
        node_id:       identificatore del nodo di competenza.
        node_content:  testo completo del nodo (usato per excerpt e heuristic).
        scaffold_level: 1 | 2 | 3 — livello di scaffolding gia' determinato.

    Returns:
        Dizionario con esattamente 4 campi::

            {
              "node_id":         str,  # identificatore del nodo
              "question":        str,  # testo della domanda di richiamo
              "scaffold_level":  int,  # 1 | 2 | 3
              "epistemic_level": int,  # 1=L1(code) | 2=L2(citation) | 3=L3(claim)
            }

    INVARIANTE G-1: il testo della domanda dipende da scaffold_level e non e'
    mai generico o identico tra livelli diversi.

    INVARIANTE G-2: questo componente NON valuta mai le risposte. Nessuna
    funzione di verifica risposta e' esposta (separazione Generator/Validator,
    US-163 Principio P5 / AC2).

    Raises:
        ValueError: se scaffold_level non e' 1, 2 o 3.

    Example::

        >>> q = generate_recall_question(
        ...     node_id="list-comprehension",
        ...     node_content="```python\\n[x*2 for x in range(5)]\\n```",
        ...     scaffold_level=1,
        ... )
        >>> q["scaffold_level"]
        1
        >>> q["epistemic_level"]
        1
        >>> "list-comprehension" in q["question"]
        True
    """
    epistemic_level = _infer_epistemic_level(node_content)
    question = _build_question_text(node_id, node_content, scaffold_level)

    return {
        "node_id": node_id,
        "question": question,
        "scaffold_level": scaffold_level,
        "epistemic_level": epistemic_level,
    }
