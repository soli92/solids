"""Sprint corrente e conteggio TSK — `management/kanban/`.

Conta i frontmatter `status:` dei TSK dello sprint dichiarato in `sprint.md`.
Nessuna interpretazione: se `sprint_current:` manca, lo dice invece di indovinare.
"""
from __future__ import annotations

import re
from collections import Counter

from visual.collectors.base import Collector, Reading

_STATUS = re.compile(r"^status:\s*([a-z-]+)", re.M)

#: Stessa ragione di `STATI_IT` in events.py: `done` e `todo` sono valori dello schema
#: del kanban, non parole per chi guarda.
STATI_IT = {"done": "fatti", "todo": "da fare", "in-progress": "in corso",
            "blocked": "bloccati", "review": "in revisione", "senza-status": "senza stato"}
_SPRINT = re.compile(r"^sprint:\s*(\d+)", re.M)


class SprintCollector(Collector):
    key = "sprint"
    source = "management/kanban/"
    titolo = "Sprint corrente"
    descrizione = "Avanzamento dei task dello sprint dichiarato nel kanban."

    #: Apre SEICENTO file a ogni lettura: 0,3 s a vuoto, oltre la scadenza su una
    #: macchina carica. Senza questa riga il costo si ripaga a ogni ciclo e il
    #: riquadro sfarfalla fra il dato e «lettura in corso» — indistinguibile da un
    #: guasto per chi guarda. Il board cambia alla velocita' di un commit, non del
    #: secondo, e la lettura servita porta con se' `observed_at`: la vista ne mostra
    #: l'eta' vera e la marca stantia da sola. Non e' una cache che nasconde, e'
    #: una lettura datata.
    refresh_seconds = 10.0

    def collect(self) -> list[Reading]:
        board = self._require("management/kanban")
        plan = board / "sprint.md"
        if not plan.is_file():
            return [Reading.unavailable(self.key, self.source, "sprint.md assente")]

        text = plan.read_text(encoding="utf-8", errors="replace")
        found = re.search(r"^sprint_current:\s*(\d+)", text, re.M)
        if not found:
            return [Reading.unavailable(self.key, f"{self.source}sprint.md",
                                        "sprint.md non dichiara `sprint_current:`")]
        current = int(found.group(1))

        states: Counter[str] = Counter()
        senza_sprint: Counter[str] = Counter()
        piu_recente = 0.0
        for path in board.rglob("TSK-*.md"):
            piu_recente = max(piu_recente, path.stat().st_mtime)
            head = path.read_text(encoding="utf-8", errors="replace")[:600]
            sprint = _SPRINT.search(head)
            status = _STATUS.search(head)
            stato = status.group(1) if status else "senza-status"
            if not sprint or sprint.group(1) in ("null", "None"):
                # Lavoro che non appartiene a nessuno sprint: senza questa riga
                # NON COMPARE DA NESSUNA PARTE. Un board con lavoro invisibile e'
                # peggio di un board vuoto, perche' sembra aggiornato. Trenta TSK
                # creati in un giorno sono rimasti fuori da ogni pannello cosi'.
                if stato not in ("done", "cancelled"):
                    senza_sprint[stato] += 1
                continue
            if int(sprint.group(1)) != current:
                continue
            states[stato] += 1

        total = sum(states.values())
        done = states.get("done", 0)
        return [
            Reading.ok("sprint.current", current, f"{self.source}sprint.md",
                       label="Numero sprint", data_at=plan.stat().st_mtime),
            Reading.ok("sprint.tsk_by_status",
                       {STATI_IT.get(k, k): v for k, v in states.most_common()}, self.source,
                       unit="TSK", label="Task per stato", data_at=piu_recente or None),
            Reading.ok("sprint.total", total, self.source, unit="TSK", label="Task nello sprint"),
            Reading.ok("sprint.senza_sprint",
                       {STATI_IT.get(k, k): v for k, v in senza_sprint.most_common()}, self.source,
                       unit="TSK", label="Aperti fuori da ogni sprint",
                       vuoto="nessuno: tutto il lavoro aperto e' pianificato",
                       data_at=piu_recente or None),
            Reading.ok("sprint.done_pct", round(100 * done / total, 1) if total else 0.0,
                       self.source, unit="%", label="Completamento", done=done, total=total),
        ]
