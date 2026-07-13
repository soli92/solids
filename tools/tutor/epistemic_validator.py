"""
epistemic_validator.py — Guard Python per il modello epistemico del tutor (EP-045).

Implementa le 3 funzioni di validazione corrispondenti ai guard INV-T1, INV-T2, INV-T3
definiti in `.claude/skills/epistemic-tag-protocol.md`.

Usato da tools/tutor/tests/test_epistemic_tag_protocol.py (TSK-355).
Solo stdlib. Nessuna dipendenza esterna.

[^src: .claude/skills/epistemic-tag-protocol.md §Guard]
[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/TSK-355-test-invarianti-epistemiche.md §Technical Specs]
"""

from __future__ import annotations


def validate_l1_response(
    response: str,
    exec_output: dict | None,
) -> tuple[bool, str]:
    """Valida una risposta L1 (asserzione su comportamento eseguibile di codice).

    Una risposta L1 e' valida se:
    - exec_output non e' None (il tutor ha eseguito sandbox_exec_tool)
    - il tag [L1:exec] e' presente nella risposta

    Guard INV-T1 (epistemic-tag-protocol §Guard): se exec_output e' None la risposta
    e' rifiutata indipendentemente dal contenuto, perche' nessuna esecuzione reale
    ha avuto luogo.

    Args:
        response:    testo della risposta del tutor.
        exec_output: dict con exit_code/stdout/stderr/elapsed_ms/timed_out,
                     oppure None se sandbox_exec_tool non e' stato invocato.

    Returns:
        (True, "OK") se valida.
        (False, reason) se non valida; reason contiene la stringa diagnostica.
    """
    if exec_output is None:
        return (
            False,
            "[REJECT:INV-T1] esecuzione effettiva richiesta — vedi sandbox_exec_tool",
        )
    if "[L1:exec" not in response:
        return False, "tag [L1:exec] assente nella risposta pur avendo exec_output"
    return True, "OK"


def validate_l2_response(
    response: str,
    citations: list[dict],
) -> tuple[bool, str]:
    """Valida una risposta L2 (asserzione su concetto documentato nel wiki o codebase).

    Una risposta L2 e' valida se:
    - citations non e' vuota (il tutor ha recuperato almeno una citazione da retrieval-protocol)
    - il tag [L2:fonte] e' presente nella risposta

    Guard INV-T2 (epistemic-tag-protocol §Guard): se citations e' vuota la risposta
    e' rifiutata perche' nessuna fonte documentata supporta l'affermazione.

    Args:
        response:  testo della risposta del tutor.
        citations: lista di wiki_citation o code_citation (schema retrieval-protocol).
                   Lista vuota significa RETRIEVAL_NOT_FOUND.

    Returns:
        (True, "OK") se valida.
        (False, reason) se non valida.
    """
    if not citations:
        return (
            False,
            "[REJECT:INV-T2] citazione alla fonte richiesta — nessun hit da retrieval-protocol",
        )
    if "[L2:fonte" not in response:
        return False, "tag [L2:fonte] assente nella risposta pur avendo citazioni"
    return True, "OK"


def validate_l3_response(response: str) -> tuple[bool, str]:
    """Valida una risposta L3 (giudizio-team su convenzione non documentata formalmente).

    Una risposta L3 e' valida se il tag [L3:giudizio-team] e' visibile nella risposta.
    Guard INV-T3 (epistemic-tag-protocol §Guard): il tag e' obbligatorio per qualsiasi
    affermazione L3. Non esiste REJECT per L3, ma l'assenza del tag e' una violazione.

    Args:
        response: testo della risposta del tutor.

    Returns:
        (True, "OK") se il tag e' presente.
        (False, reason) se il tag e' assente; reason contiene "tag [L3:giudizio-team] richiesto".
    """
    if "[L3:giudizio-team" not in response:
        return (
            False,
            "[INV-T3] tag [L3:giudizio-team] richiesto — risposta L3 non conforme",
        )
    return True, "OK"
