"""Event store — `analytics/events/<YYYY-MM>.jsonl` (EP-009, ADR-021).

Sola lettura: lo scrittore unico resta `tools/analytics/record-event.sh` (ADR-039 §B).
Righe malformate vengono contate e dichiarate, non silenziate: un parser che le
ignora in silenzio fa sembrare sana una telemetria rotta.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from visual.collectors.base import Collector, Reading

RECENT = 12


#: Gli stati dell'event store sono un'enumerazione inglese del contratto EP-009. Va
#: tradotta dove nasce il dato: una pagina italiana che mostra `finished` costringe
#: chi legge a conoscere lo schema per capire il numero accanto.
STATI_IT = {"finished": "concluso", "started": "avviato", "blocked": "bloccato",
            "aborted": "interrotto", "wave_started": "wave avviata",
            "wave_completed": "wave conclusa", "sub_agent_dispatched": "sub-agente avviato"}

#: Gli stessi al plurale, per i conteggi aggregati. Due tabelle e non una perche'
#: «conclusi 43» e la colonna «concluso» di una singola riga vogliono numeri diversi.
STATI_IT_PLURALE = {"finished": "conclusi", "started": "avviati", "blocked": "bloccati",
                    "aborted": "interrotti", "wave_started": "wave avviate",
                    "wave_completed": "wave concluse",
                    "sub_agent_dispatched": "sub-agenti avviati"}


def _breve(raw: str | None) -> str:
    """`2026-09-21T15:38:45Z` -> `21/09 15:38`. Una marca temporale ISO in una cella e'
    leggibile da una macchina, non da una persona."""
    momento = _parse_ts(str(raw or ""))
    return momento.strftime("%d/%m %H:%M") if momento else str(raw or "—")


def _parse_ts(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class EventStoreCollector(Collector):
    key = "events"
    source = "analytics/events/*.jsonl"
    titolo = "Attività registrata"
    descrizione = ("Esecuzione formale dei TSK: ci finisce cio' che passa da dev-protocol, "
                   "non tutto il lavoro. Un dato vecchio qui con una sessione attiva non e' "
                   "un guasto.")

    def collect(self) -> list[Reading]:
        folder = self._require("analytics/events")
        files = sorted(folder.glob("*.jsonl"))
        if not files:
            return [Reading.unavailable(self.key, self.source,
                                        "nessun file di eventi: la telemetria non e' mai stata scritta",
                                        label="Eventi registrati")]

        events: list[dict] = []
        malformed = 0
        for path in files[-2:]:  # mese corrente + precedente
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    malformed += 1

        if not events:
            return [Reading.unavailable(self.key, self.source,
                                        f"{malformed} righe malformate e nessun evento valido")]

        events.sort(key=lambda e: str(e.get("ts", "")))
        latest = events[-1]
        actors = Counter(e.get("actor_id", "?") for e in events)
        states = Counter(e.get("state", "?") for e in events)

        newest = _parse_ts(str(latest.get("ts", "")))
        # `.days` tronca: 47 ore diventavano «ieri». Per un'etichetta letta da una
        # persona l'arrotondamento e' piu' vero del troncamento.
        age_days = (round((datetime.now(timezone.utc) - newest).total_seconds() / 86400)
                    if newest else None)
        quando = _breve(latest.get("ts"))
        if age_days is not None:
            # «1 giorni fa» e' il genere di dettaglio che fa sembrare automatica una
            # pagina scritta per essere letta da una persona.
            quando += (" (oggi)" if age_days == 0
                       else " (ieri)" if age_days == 1
                       else f" ({age_days} giorni fa)")

        ultimo_a = newest.timestamp() if newest else None
        readings = [
            Reading.ok("events.total", len(events), self.source, unit="eventi",
                       label="Eventi registrati", data_at=ultimo_a,
                       files=[p.name for p in files], malformed=malformed),
            Reading.ok("events.last_ts", quando, self.source, label="Ultimo evento",
                       data_at=ultimo_a,
                       age_days=age_days, task=latest.get("task_id")),
            Reading.ok("events.by_state",
                       {STATI_IT_PLURALE.get(k, k): v for k, v in states.most_common()}, self.source,
                       label="Eventi per stato"),
            Reading.ok("events.top_actors", dict(actors.most_common(6)), self.source,
                       label="Agenti più attivi"),
            # Chiavi in italiano: diventano le intestazioni della tabella, e una colonna
            # che si chiama `ts` e' un nome di variabile mostrato a una persona.
            Reading.ok("events.recent", [
                {"quando": _breve(e.get("ts")), "task": e.get("task_id"),
                 "agente": e.get("actor_id"),
                 "stato": STATI_IT.get(e.get("state"), e.get("state")),
                 "tipo": e.get("task_type")}
                for e in events[-RECENT:][::-1]
            ], self.source, unit="eventi", label="Ultimi eventi"),
        ]
        if malformed:
            readings.append(Reading.ok("events.malformed", malformed, self.source, unit="righe",
                                    label="Righe malformate"))
        return readings
