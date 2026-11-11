"""Parita' fra canale audio e canale visivo (EP-067 US-295).

Il contratto e' **asimmetrico per costruzione**: voce e schermo trasportano cose
diverse — `SpokenSummary` al TTS, `Artifact` solo allo schermo. Parita' quindi non
significa duplicazione: significa che i due canali descrivono lo **stesso stato**,
perche' derivano dalla **stessa sequenza di eventi**.

Il modo per garantirlo non e' riconciliare due fonti, e' non averne due. `Tee`
distribuisce un solo flusso a N consumatori, in ordine, e ogni consumatore applica
il proprio filtro. Cosi' una divergenza non e' improbabile: e' **impossibile per
costruzione**, salvo che un consumatore sollevi — e in quel caso lo si registra
invece di lasciarlo scomparire.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Protocol


class Consumatore(Protocol):
    def consume(self, event: Any) -> Any: ...


class Tee:
    """Un flusso, N consumatori, un solo ordine."""

    def __init__(self, *consumatori: Consumatore | Callable[[Any], Any]) -> None:
        self._consumatori = list(consumatori)
        self._lock = threading.Lock()
        self.contati = 0
        self.ultimo_a: float | None = None
        #: Guasti di un consumatore. Non si propagano agli altri — un canale rotto non
        #: deve spegnere l'altro — ma non si perdono nemmeno: un `except: pass` qui
        #: renderebbe la divergenza invisibile, che e' il solo esito peggiore di averla.
        self.guasti: list[dict] = []

    def aggiungi(self, consumatore: Consumatore | Callable[[Any], Any]) -> None:
        with self._lock:
            self._consumatori.append(consumatore)

    def dispatch(self, event: Any) -> None:
        with self._lock:
            consumatori = list(self._consumatori)
            self.contati += 1
            self.ultimo_a = time.time()
        for consumatore in consumatori:
            try:
                funzione = getattr(consumatore, "consume", consumatore)
                funzione(event)
            except Exception as problema:  # noqa: BLE001
                self.guasti.append({
                    "consumatore": type(consumatore).__name__,
                    "evento": type(event).__name__,
                    "errore": f"{type(problema).__name__}: {problema}",
                    "a": time.time(),
                })

    def stato(self) -> dict:
        ritardo = None if self.ultimo_a is None else round(time.time() - self.ultimo_a, 2)
        return {
            "consumatori": len(self._consumatori),
            "eventi_distribuiti": self.contati,
            # Un canale in ritardo lo DICHIARA. Non finge di essere aggiornato.
            "ritardo_ultimo_evento_s": ritardo,
            "guasti": self.guasti[-5:],
            "in_parita": not self.guasti,
        }
