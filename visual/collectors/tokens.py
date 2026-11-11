"""Token ledger — riuso di `tools/analytics/statusline-ledger.py --json` (EP-022/EP-059).

Il tool esistente e' l'unico lettore autorizzato del transcript: qui lo si invoca,
non lo si riscrive. Se non c'e' o fallisce, lo si dichiara — degradazione gia'
prevista dal tool stesso (exit 0 con riga vuota).

`stdin=DEVNULL` NON e' pulizia: e' necessario. `statusline-ledger.py` e' una
statusline di Claude Code e legge il proprio input JSON **da stdin**; se stdin resta
aperto — ed e' cio' che succede a un sottoprocesso lanciato da un servizio — la
lettura non vede mai EOF e il processo **non termina piu'**. Dal terminale il difetto
non si manifesta (stdin da' EOF subito), quindi si vede solo in servizio, e si vede
come lentezza a intermittenza invece che come blocco: il riquadro usciva «non
osservabile» a caso, il che e' peggio che uscire rotto sempre. Misurato: pipe aperta
-> timeout oltre 6 s; `DEVNULL` -> 0,10 s.

Vale per chiunque nella factory invochi questo tool da un sottoprocesso.
"""
from __future__ import annotations

import json
import subprocess
import sys

from visual.collectors.base import Collector, Reading

# Il costo reale con stdin chiuso e' ~0,1 s. Il margine e' largo perche' il tool legge
# il transcript e cresce con la sessione, non perche' ci si aspetti che sia lento.
TIMEOUT = 10


class TokenLedgerCollector(Collector):
    key = "tokens"
    titolo = "Costo della sessione"
    descrizione = "Token e costo riportati dal runtime di Claude Code."
    deadline_seconds = 1.0
    # Il ledger rilegge il transcript: costa secondi. Rileggerlo a ogni ciclo da 5s
    # significherebbe pagarlo per sempre, per un numero che cambia lentamente.
    refresh_seconds = 30.0
    source = "tools/analytics/statusline-ledger.py --json"

    def collect(self) -> list[Reading]:
        tool = self.root / "tools/analytics/show-session-tokens.py"
        if not tool.is_file():
            return [Reading.unavailable(self.key, self.source,
                                        "show-session-tokens.py non presente")]

        try:
            done = subprocess.run([sys.executable, str(tool), "--json"], capture_output=True,
                                  text=True, timeout=TIMEOUT, cwd=str(self.root),
                                  stdin=subprocess.DEVNULL)   # vedi il docstring: obbligatorio
        except subprocess.TimeoutExpired:
            return [Reading.unavailable(self.key, self.source, f"il ledger non ha risposto entro {TIMEOUT}s")]

        payload = (done.stdout or "").strip()
        if not payload:
            return [Reading.unavailable(self.key, self.source,
                                        "ledger vuoto: token_ledger disattivo o nessuna sessione")]
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return [Reading.unavailable(self.key, self.source, "il ledger non ha restituito JSON")]

        if not data.get("disponibile"):
            return [Reading.unavailable(self.key, self.source,
                                        data.get("ragione") or "il ledger non ha dati")]

        etichette = {"input": "Token in ingresso", "output": "Token in uscita",
                     "cost_usd": "Costo stimato (USD)",
                     "cache_savings_usd": "Risparmio da cache (USD)"}
        # Un valore `None` NON e' una lettura: e' un'assenza, e presentarla come dato e'
        # esattamente cio' che questo riquadro vieta. Il difetto era reale e visibile in
        # pagina — «Costo stimato (USD): null» con il pannello che si dichiarava
        # osservabile — perche' la fonte precedente (`statusline-ledger.py`) legge il
        # contesto di sessione da stdin, e un servizio deve chiuderglielo per non
        # restare appeso: rispondeva `null` su ogni campo, e il collettore quei `null`
        # li impacchettava in `Reading.ok`.
        readings = [Reading.ok(f"tokens.{name}", data[name], self.source,
                               label=etichetta)
                    for name, etichetta in etichette.items()
                    if data.get(name) is not None]
        if not readings:
            return [Reading.unavailable(self.key, self.source,
                                        "il ledger ha risposto senza alcun valore")]
        return readings
