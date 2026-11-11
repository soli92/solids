"""Soglie di costo — riuso di `tools/analytics/cost_alert.py check --json` (cost-alert).

Il tool calcola costi e verdetti; qui li si mostra soltanto. Le note del verdetto (cosa il
numero non copre: altre macchine, Cursor, modelli a prezzo stimato) vanno in pagina insieme
ai numeri: senza, un costo parziale si legge come completo.

`stdin=DEVNULL` per la stessa ragione di `visual.collectors.tokens`: un sottoprocesso
lanciato da un servizio non deve restare con stdin aperto.
"""
from __future__ import annotations

import json
import subprocess
import sys

from visual.collectors.base import Collector, Reading

# Il controllo settimanale rilegge i transcript della settimana: ~2 s su una macchina
# carica. La scadenza lo copre; il refresh evita di pagarlo a ogni ciclo.
TIMEOUT = 15
PERIODO = {"session": "Sessione", "daily": "Giorno", "weekly": "Settimana"}


class CostAlertCollector(Collector):
    key = "cost_alert"
    titolo = "Soglie di costo"
    descrizione = "Costo dell'operatore su questa macchina contro analytics/alert-rules.yaml."
    deadline_seconds = 3.0
    refresh_seconds = 60.0
    source = "tools/analytics/cost_alert.py check --json"

    def collect(self) -> list[Reading]:
        tool = self.root / "tools/analytics/cost_alert.py"
        if not tool.is_file():
            return [Reading.unavailable(self.key, self.source, "cost_alert.py non presente")]
        try:
            done = subprocess.run([sys.executable, str(tool), "check", "--json"],
                                  capture_output=True, text=True, timeout=TIMEOUT,
                                  cwd=str(self.root), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return [Reading.unavailable(self.key, self.source,
                                        f"cost_alert.py non ha risposto entro {TIMEOUT}s")]
        try:
            v = json.loads((done.stdout or "").strip() or "{}")
        except json.JSONDecodeError:
            return [Reading.unavailable(self.key, self.source, "cost_alert.py non ha restituito JSON")]
        if not v.get("enabled"):
            return [Reading.unavailable(self.key, self.source,
                                        "; ".join(v.get("notes") or ["capability spenta"]))]

        readings = []
        for r in v.get("results") or []:
            stato = "superata" if r["breached"] else f"{r['ratio'] * 100:.0f}% della soglia"
            readings.append(Reading.ok(
                f"cost_alert.{r['period']}", round(r["cost_usd"], 2), self.source, unit="USD",
                label=f"{PERIODO.get(r['period'], r['period'])} — soglia "
                      f"{r['threshold_usd']:.0f} USD, {stato} ({r['action']})",
                threshold_usd=r["threshold_usd"], breached=r["breached"], action=r["action"]))
        readings.append(Reading.ok("cost_alert.pending", v.get("pending", 0), self.source,
                                   unit="alert", vuoto="nessun alert pendente",
                                   label="Alert da prendere in carico (/cost-alert --pending)"))
        for i, nota in enumerate(v.get("notes") or [], 1):
            readings.append(Reading.ok(f"cost_alert.nota_{i}", nota, self.source, label="Nota"))
        return readings
