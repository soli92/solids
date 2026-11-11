"""
test_epistemic_tag_protocol.py — 7 tests for tutor epistemic invariants (US-161).

Covers US-161 ACs testable without full wiring with the Student Model
(AC4 and AC5 depend on US-162, tested in TSK-362):

  Test 1 (AC1): L1 valid — exec_output present + tag [L1:exec] → valid=True
  Test 2 (AC1): Guard INV-T1 — exec_output=None → valid=False, reason "actual execution requested"
  Test 3 (AC2): L2 valid — citations not empty + tag [L2:source] → valid=True
  Test 4 (AC2): Guard INV-T2 — citations=[] → valid=False, reason "source citation required"
  Test 5 (AC3): L3 valid — tag [L3:team-judgment] present → valid=True
  Test 6 (AC3): Guard INV-T3 — tag absent → valid=False, reason "tag [L3:judgment-team] required"
  Test 7 (AC6): execute_snippet("print(2+2)") → stdout="4\\n", exit_code=0 — REAL output, no mock

Framework: pytest + stdlib. No external dependencies.
Test 7 invokes REAL execute_snippet (isolated subprocess) — no mocks.

[^src: management/kanban/EP-045-capability-formativa/US-161-tutor-modello-epistemico/TSK-355-test-invarianti-epistemiche.md]
[^src: .claude/skills/epistemic-tag-protocol.md §Guard]


"""
from __future__ import annotations

import tools.tutor.epistemic_validator as ev
from tools.tutor.sandbox_exec_tool import execute_snippet


# ---------------------------------------------------------------------------
# Test 1 — AC1: Valid L1 with exec_output present

# ---------------------------------------------------------------------------

def test_l1_valid_with_exec_output() -> None:
    """AC1: risposta L1 con exec_output reale e tag [L1:exec] → valid=True.

    Simula il caso in cui il tutor ha eseguito sandbox_exec_tool e dispone
    di un output reale (exit_code=0, stdout="42\n").
    """
    exec_output = {
        "exit_code": 0,
        "stdout": "42\n",
        "stderr": "",
        "elapsed_ms": 12.5,
        "timed_out": False,
    }
    response = "[L1:exec — stdout: 42]"
    valid, reason = ev.validate_l1_response(response, exec_output=exec_output)
    assert valid is True, f"Atteso valid=True, got valid={valid!r}, reason={reason!r}"


# ---------------------------------------------------------------------------
# Test 2 — AC1: Guard L1 senza exec (INV-T1)
# ---------------------------------------------------------------------------

def test_l1_guard_without_exec_output() -> None:
    """AC1/Guard INV-T1: exec_output=None → valid=False con reason 'esecuzione effettiva richiesta'.

    Il tutor non ha eseguito sandbox_exec_tool per questa affermazione.
    La guard INV-T1 blocca la risposta.
    """
    response = "La funzione ritorna 42"
    valid, reason = ev.validate_l1_response(response, exec_output=None)
    assert valid is False, f"Atteso valid=False (guard INV-T1), got valid={valid!r}"
    assert "esecuzione effettiva" in reason, (
        f"reason deve contenere 'esecuzione effettiva', got: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 — AC2: valid L2 with citations present

# ---------------------------------------------------------------------------

def test_l2_valid_with_citations() -> None:
    """AC2: risposta L2 con citations non vuota e tag [L2:fonte] → valid=True."""
    citations = [
        {
            "source": "wiki/concepts/x.md",
            "section": "Y",
            "excerpt": "Definizione del concetto X.",
        }
    ]
    response = "[L2:fonte — wiki/concepts/x.md §Y] testo"
    valid, reason = ev.validate_l2_response(response, citations)
    assert valid is True, f"Atteso valid=True, got valid={valid!r}, reason={reason!r}"


# ---------------------------------------------------------------------------
# Test 4 — AC2: Guard L2 senza citazione (INV-T2)
# ---------------------------------------------------------------------------

def test_l2_guard_without_citations() -> None:
    """AC2/Guard INV-T2: citations=[] → valid=False con reason 'citazione alla fonte richiesta'.

    Il retrieval-protocol non ha trovato hit (RETRIEVAL_NOT_FOUND).
    La guard INV-T2 blocca la risposta.
    """
    response = "Il concetto X significa..."
    valid, reason = ev.validate_l2_response(response, citations=[])
    assert valid is False, f"Atteso valid=False (guard INV-T2), got valid={valid!r}"
    assert "citazione alla fonte" in reason, (
        f"reason deve contenere 'citazione alla fonte', got: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — AC3: Valid L3 with caution tag present
# ---------------------------------------------------------------------------

def test_l3_valid_with_tag() -> None:
    """AC3: risposta L3 con tag [L3:giudizio-team] presente → valid=True."""
    response = (
        "[L3:giudizio-team — convenzione non documentata] praticamente usiamo X"
    )
    valid, reason = ev.validate_l3_response(response)
    assert valid is True, f"Atteso valid=True, got valid={valid!r}, reason={reason!r}"


# ---------------------------------------------------------------------------
# Test 6 — AC3: Guard L3 senza tag cautela (INV-T3)
# ---------------------------------------------------------------------------

def test_l3_guard_without_tag() -> None:
    """AC3/Guard INV-T3: tag [L3:giudizio-team] assente → valid=False.

    Qualsiasi affermazione L3 richiede il tag obbligatorio (INV-T3).
    Assenza del tag = risposta non conforme.
    """
    response = "Praticamente usiamo sempre X, e' la nostra pratica"
    valid, reason = ev.validate_l3_response(response)
    assert valid is False, f"Atteso valid=False (guard INV-T3), got valid={valid!r}"
    assert "L3:giudizio-team" in reason, (
        f"reason deve contenere 'tag [L3:giudizio-team] richiesto', got: {reason!r}"
    )


# ---------------------------------------------------------------------------
# Test 7 — AC6: sandbox exec produces real output (no mock)
# ---------------------------------------------------------------------------

def test_sandbox_exec_produces_real_output() -> None:
    """AC6: execute_snippet('print(2+2)') produce stdout='4\\n' ed exit_code=0.

    Test REALE: nessun mock su execute_snippet. Verifica che sandbox_exec_tool
    esegua effettivamente il codice in subprocess isolato e catturi l'output reale.
    La stringa "print(2+2)" viene eseguita da python3 in un file temporaneo;
    l'output atteso e' la stringa "4" seguita da newline.
    """
    result = execute_snippet("print(2+2)")
    assert result["stdout"] == "4\n", (
        f"Atteso stdout='4\\n', got: {result['stdout']!r}"
    )
    assert result["exit_code"] == 0, (
        f"Atteso exit_code=0, got: {result['exit_code']!r}"
    )
