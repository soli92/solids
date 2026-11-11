"""Test seam session-owner US-170 EP-046.

Verifica:
  TC1 — AC1: SessionContext e VoiceSessionManager importabili con struttura corretta
  TC2 — AC3: should_reset() ritorna False in tutti gli scenari
  TC3 — AC5: regressione suite esistente (import smoke test)
"""
import pytest

from voice.core.session import SessionContext, VoiceSessionManager


# ---------------------------------------------------------------------------
# TC1 — AC1: interface present and correct
# ---------------------------------------------------------------------------

def test_tc1_interfaccia_presente():
    """SessionContext e VoiceSessionManager importabili con attributi e metodi corretti."""
    ctx = SessionContext()
    assert isinstance(ctx.session_id, str) and len(ctx.session_id) > 0
    assert isinstance(ctx.started_at, str) and "T" in ctx.started_at  # ISO 8601

    mgr = VoiceSessionManager()
    assert hasattr(mgr, "should_reset") and callable(mgr.should_reset)
    assert hasattr(mgr, "end") and callable(mgr.end)


# ---------------------------------------------------------------------------
# TC2 — AC3: should_reset() = False in all scenarios
# ---------------------------------------------------------------------------

def test_tc2_should_reset_sempre_false():
    """should_reset() deve ritornare False in tutti i casi (no-op)."""
    mgr = VoiceSessionManager()
    assert mgr.should_reset() is False
    assert mgr.should_reset() is False
    assert mgr.should_reset() is False


# ---------------------------------------------------------------------------
# TC3 — AC5: existing suite regression (import smoke test)
# ---------------------------------------------------------------------------

def test_tc3_regressione_import_moduli_voice():
    """I moduli principali del package voice/ devono importarsi senza errori."""
    import voice.core.session  # noqa: F401
    import voice.core.side_channel  # noqa: F401
    import voice.config  # noqa: F401
    # VoiceSession e new_session esistenti invariati
    from voice.core.session import VoiceSession, new_session
    s = new_session()
    assert isinstance(s, VoiceSession)
    assert s.turn_count == 0
