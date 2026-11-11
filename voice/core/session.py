"""
voice/core/session.py — Traccia il contesto di una singola sessione vocale.

Ogni sessione nasce con un identificatore univoco breve (primi 8 char di uuid4)
e registra l'istante di inizio e il numero di turni completati.

Uso tipico (dalla state machine):

    from voice.core.session import new_session

    session = new_session()
    turn_id = session.new_turn()    # es. "a3f2b1c4-t1"
    # passa turn_id o session.session_id al runtime.submit(...)
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone


class VoiceSession:
    """Contesto di una sessione vocale.

    Attributi:
        session_id:  Identificatore univoco breve (es. ``"a3f2b1c4"``).
                     Derivato dai primi 8 caratteri di un uuid4. Passa a
                     FactoryRuntime.submit() come session_id.
        started_at:  Timestamp Unix (float) del momento di creazione.
                     Compatibile con il campo DoD US-143 AC2 (``started_at: float``).
        turn_count:  Numero di turni completati nella sessione (inizia a 0).
    """

    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())[:8]
        self.started_at: float = time.time()
        self.turn_count: int = 0

    @property
    def started_at_dt(self) -> datetime:
        """Timestamp di inizio come datetime UTC (conveniienza)."""
        return datetime.fromtimestamp(self.started_at, tz=timezone.utc)

    def new_turn(self) -> str:
        """Incrementa il contatore turni e restituisce l'ID del turno corrente.

        Formato: ``"{session_id}-t{turn_count}"`` — es. ``"a3f2b1c4-t1"``.

        Returns:
            Stringa identificativa del turno (passata a runtime.submit() come
            session_id se si vuole granularita' per-turno).
        """
        self.turn_count += 1
        return f"{self.session_id}-t{self.turn_count}"

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"VoiceSession("
            f"session_id={self.session_id!r}, "
            f"started_at={self.started_at:.3f}, "
            f"turn_count={self.turn_count})"
        )


def new_session() -> VoiceSession:
    """Crea e restituisce una nuova VoiceSession.

    Factory function (DoD US-143 AC2): equivalente a ``VoiceSession()``,
    esportata come entry point nominato per chiarezza semantica.

    Returns:
        VoiceSession con session_id univoco e turn_count=0.
    """
    return VoiceSession()


# ---------------------------------------------------------------------------
# Seam session-owner (US-170 EP-046)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402


@dataclass
class SessionContext:
    """Contesto identificativo di una sessione vocale.
    Candidato owner: VoiceSessionManager (seam US-170 EP-046).
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VoiceSessionManager:
    """Candidato owner della qualità del contesto di sessione.
    Interfaccia no-op: should_reset() ritorna sempre False.
    Il timeout semantico è out-of-scope — vedi voice/docs/session-owner-gap.md.
    """
    def __init__(self) -> None:
        self.context = SessionContext()

    def should_reset(self) -> bool:
        """Hook per futura logica di reset sessione. Sempre False (no-op)."""
        return False

    def end(self) -> None:
        """Stub — chiamato alla fine della sessione. Implementazione futura."""
        pass
