"""`Reading` — il tipo che impedisce di mostrare un numero senza la sua provenienza.

US-281 chiede tre cose che in una dashboard normale si dimenticano una per volta:
ogni numero dichiara la propria fonte, ogni numero dichiara la propria eta', e una
fonte illeggibile produce «non osservabile» e **mai** uno zero.

Sono garantite dal tipo invece che dalla disciplina: non esiste un costruttore che
restituisca un valore senza `source`, e l'unico modo di dire «non lo so» e'
`Reading.unavailable(...)`, che porta `value=None` — non `0`. Uno zero nella resa
puo' allora venire solo da una misura che vale davvero zero.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Reading:
    """Una misura, con provenienza ed eta'. Mai un numero nudo."""

    key: str
    value: Any
    source: str
    observed_at: float
    available: bool = True
    reason: str | None = None
    unit: str = ""
    detail: dict = field(default_factory=dict)
    #: Quando risale il DATO, non la lettura. Sono due eta' diverse e confonderle e' il
    #: difetto che questa riga esiste per chiudere: l'event store di questo repo era fermo
    #: da due giorni e la plancia lo mostrava come «letto 0 s fa» — vero, e inutile. Chi
    #: guardava vedeva una fonte fresca su un dato morto. `None` = il collettore non sa
    #: datare cio' che ha letto, ed e' diverso da «e' appena successo».
    data_at: float | None = None

    #: Come si chiama un elemento quando non ce ne sono: «nessuna sessione attiva» e non
    #: «nessuna sessioni». L'accordo grammaticale non si deduce da `unit` al plurale, e
    #: comporlo nel frontend produce esattamente quell'errore.
    vuoto: str = ""
    #: Come si chiama questa misura per una persona. Sta nel tipo per la stessa ragione
    #: per cui ci sta la provenienza: se l'etichetta vivesse nel frontend, una misura
    #: nuova comparirebbe in pagina col proprio nome di variabile — ed e' esattamente
    #: cio' che e' successo, con `events.by_state` e `sprint.tsk_by_status` letti da un
    #: umano. Chi produce la misura sa come si chiama; chi la disegna no.
    label: str = ""

    @classmethod
    def ok(cls, key: str, value: Any, source: str, *, unit: str = "", label: str = "",
           vuoto: str = "", data_at: float | None = None, **detail: Any) -> "Reading":
        return cls(key, value, source, time.time(), True, None, unit, detail,
                   data_at, vuoto, label or key)

    @classmethod
    def unavailable(cls, key: str, source: str, reason: str, *, label: str = "") -> "Reading":
        # value=None, mai 0: «non osservabile» e «zero» non devono poter collidere.
        return cls(key, None, source, time.time(), False, reason, label=label or key)

    def age_seconds(self) -> float:
        """Da quanto e' stata fatta la LETTURA."""
        return max(0.0, time.time() - self.observed_at)

    def data_age_seconds(self) -> float | None:
        """Da quanto risale il DATO. `None` se il collettore non sa datarlo."""
        return None if self.data_at is None else max(0.0, time.time() - self.data_at)

    def is_stale(self, after_seconds: int) -> bool:
        return self.available and self.age_seconds() > after_seconds

    def as_dict(self, stale_after: int) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "observed_at": self.observed_at,
            "age_seconds": round(self.age_seconds(), 1),
            "available": self.available,
            "reason": self.reason,
            "unit": self.unit,
            "stale": self.is_stale(stale_after),
            "data_age_seconds": (None if self.data_age_seconds() is None
                                 else round(self.data_age_seconds(), 1)),
            "label": self.label or self.key,
            "vuoto": self.vuoto,
            "detail": self.detail,
        }


class Collector:
    """Un collettore per fonte. `read()` non solleva mai: un guasto e' una `Reading`.

    Fail-open in lettura (un riquadro rotto non abbatte gli altri), fail-loud nel
    contenuto (il riquadro dice *perche'* non ha potuto leggere).

    `deadline_seconds` esiste perche' «rotto» non e' l'unico modo di non rispondere.
    Un collettore LENTO e' indistinguibile da uno rotto per chi guarda la pagina, e
    se le letture sono sequenziali ne blocca anche gli altri: il ledger dei token,
    che lancia un sottoprocesso, teneva ferma l'intera vista per venti secondi e
    l'unico sintomo era una pagina vuota. La scadenza trasforma la lentezza in cio'
    che gia' sappiamo trattare — una `Reading.unavailable` con la sua ragione.
    """

    key = "collector"
    source = "?"
    #: Titolo del riquadro e riga che spiega cosa ci si guarda. Stessa ragione di `label`.
    titolo = "Fonte"
    descrizione = ""

    #: Quanto la vista attende QUESTO collettore prima di dichiararlo non pervenuto.
    #: E' una scadenza individuale, misurata dall'inizio della richiesta: un collettore
    #: paziente non deve poter imporre la propria attesa a tutti gli altri.
    deadline_seconds = 2.0

    #: Ogni quanto rileggere davvero. `0` = sempre. Per una fonte costosa si serve
    #: l'ultima lettura riuscita — che NON e' una bugia, perche' `Reading` porta con se'
    #: `observed_at`: la vista la mostra con la sua eta' vera e la marca stantia da sola.
    #: E' la ragione per cui la provenienza sta nel tipo e non in una convenzione.
    refresh_seconds = 0.0

    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self) -> list[Reading]:
        try:
            return self.collect()
        except Exception as problem:  # noqa: BLE001 — un guasto e' un dato, non un crash
            return [Reading.unavailable(self.key, self.source, f"{type(problem).__name__}: {problem}")]

    def collect(self) -> list[Reading]:
        raise NotImplementedError

    # -- helper condivisi, in sola lettura -------------------------------------
    def _require(self, relative: str) -> Path:
        path = self.root / relative
        if not path.exists():
            raise FileNotFoundError(f"{relative} non esiste sotto la radice della factory")
        return path
