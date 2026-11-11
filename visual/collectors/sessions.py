"""Sessioni e wave attive — `memory/active-sessions.yaml` (cooperative locking).

E' il solo posto in cui la factory dichiara chi sta lavorando su cosa. La plancia lo
legge e basta: **non arbitra** (US-291 — nessun lock, nessun lease), e dichiara
l'eta' di cio' che ha visto, perche' una entry con TTL scaduto e' un dato storico,
non una sessione viva.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tools.session.claims import load_text, split_live
from visual.collectors.base import Collector, Reading


def _age_minutes(raw: str) -> float | None:
    try:
        when = datetime.fromisoformat(raw.strip().strip("'\"").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - when).total_seconds() / 60, 1)


def _nota(expired: list) -> str:
    # Le entry scadute non sono sessioni vive: si contano, non si mostrano come attive.
    return f"{len(expired)} claim con TTL scaduto esclusi (dato storico)" if expired else ""


class SessionCollector(Collector):
    key = "sessions"
    source = "memory/active-sessions.yaml"
    titolo = "Chi sta lavorando"
    descrizione = "Sessioni che hanno dichiarato un claim. Osservato, non arbitrato."

    def collect(self) -> list[Reading]:
        path = self.root / "memory/active-sessions.yaml"
        if not path.is_file():
            return [Reading.unavailable(self.key, self.source,
                                        "active-sessions.yaml assente: nessun claim registrato")]

        # Parsing e scadenza dallo schema unico (US-316): `tools/session/claims.py` e'
        # puro, non scrive. Legge sia lo schema EP-053 per agente sia le entry di
        # sessione {id, operator, opened_at, last_seen, ttl_minutes, claims[]}.
        _, entries = load_text(path.read_text(encoding="utf-8", errors="replace"))
        live, expired = split_live(entries)
        for entry in live:
            entry["age_minutes"] = _age_minutes(entry.get("started_at") or "")
        entries = live
        if not entries:
            # Zero LEGITTIMO: il file c'e' ed e' leggibile, e dice che nessuno sta lavorando.
            # Diverso da `unavailable`, ed e' esattamente la distinzione che US-281 impone.
            return [Reading.ok("sessions.active", [], self.source, unit="sessioni", label="Sessioni attive",
                               vuoto="nessuna sessione attiva",
                               note=_nota(expired) or "file leggibile, nessun claim attivo")]
        return [
            Reading.ok("sessions.active", entries, self.source, unit="sessioni",
                       label="Sessioni attive", vuoto="nessuna sessione attiva",
                       **({"note": _nota(expired)} if expired else {})),
            Reading.ok("sessions.count", len(entries), self.source, unit="sessioni", label="Quante"),
        ]
