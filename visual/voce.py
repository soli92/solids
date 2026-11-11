"""Canale vocale come secondo consumatore dello stesso flusso (EP-067 US-295).

Non e' un secondo sistema: e' il canale audio agganciato al `Tee` gia' costruito per
la parita'. Voce e schermo leggono **la stessa sequenza di eventi**, quindi non
esistono due verita' da riconciliare — esiste una sequenza e due rese.

**L'INVARIANTE NON NEGOZIABILE DEL CONTRATTO VIVE QUI.** `Artifact.content` non
raggiunge mai il sintetizzatore. Il filtro e' `visual.channel.tts_payload`, lo
**stesso** che il canale visivo usa per decidere cosa sarebbe pronunciabile: una
seconda copia della regola sarebbe una seconda occasione di sbagliarla. Il canale
audio ha gia' il proprio choke point in `voice/core/router.py` (PATTERN §30,
allowlist e non denylist); questo e' il suo equivalente sul percorso della plancia.

Il modello TTS si carica alla PRIMA attivazione, non all'avvio: la plancia deve
partire in un secondo anche su una macchina senza voce, e chi non attiva il canale
non deve pagarne il costo.
"""
from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass
from typing import Any

from visual.channel import tts_payload

#: Oltre questa lunghezza la sintesi diventa un monologo. Il contratto dice che al TTS
#: va la SINTESI parlata, non il testo intero: troncare e' coerente, non una scorciatoia.
MAX_CARATTERI = 400


@dataclass
class StatoVoce:
    attivo: bool
    disponibile: bool
    ragione: str | None
    voce: str | None
    pronunciati: int
    in_coda: int
    scartati_artifact: int

    def as_dict(self) -> dict:
        return {
            "attivo": self.attivo, "disponibile": self.disponibile, "ragione": self.ragione,
            "voce": self.voce, "pronunciati": self.pronunciati, "in_coda": self.in_coda,
            # Contatore esplicito: quante volte l'invariante ha dovuto lavorare. Se resta
            # a zero per sempre non significa che sia inutile — significa che a monte
            # nessuno ha ancora provato a far parlare un artefatto.
            "artefatti_non_pronunciati": self.scartati_artifact,
        }


class CanaleVocale:
    """Consumatore TTS. Si registra sul `Tee`; non conosce il runtime ne' la plancia."""

    def __init__(self, root) -> None:
        self.root = root
        self._tts: Any = None
        self._voce: str | None = None
        self._ragione: str | None = None
        self._attivo = False
        self._coda: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._pronunciati = 0
        self._scartati = 0

    # -- disponibilita' -------------------------------------------------------
    def _carica(self) -> bool:
        if self._tts is not None:
            return True
        try:
            from voice.config import load_config
            from voice.tts.piper_tts import PiperTTS
        except ImportError as mancante:
            self._ragione = f"dipendenza vocale assente: {mancante.name}"
            return False
        try:
            configurazione = load_config()
            if not getattr(configurazione, "enabled", False):
                self._ragione = "voice_channel.enabled e' false in factory.config.yaml"
                return False
            cartella = configurazione.tts.model_dir or os.environ.get("PIPER_MODEL_DIR", "")
            # `~` va espansa: il modello sta sotto la home e il costruttore non la espande
            # da solo. E' il genere di dettaglio che fa fallire un'attivazione con un
            # messaggio che parla d'altro.
            self._tts = PiperTTS(voice=configurazione.tts.voice,
                                 model_dir=os.path.expanduser(cartella))
            self._voce = configurazione.tts.voice
        except Exception as problema:  # noqa: BLE001
            self._ragione = f"{type(problema).__name__}: {str(problema).splitlines()[0][:160]}"
            return False
        self._ragione = None
        return True

    def disponibile(self) -> tuple[bool, str | None]:
        """Non carica il modello: risponde sulla base dei prerequisiti.

        Caricare per rispondere «e' disponibile?» costerebbe un secondo a ogni
        aggiornamento della vista, cioe' ogni cinque secondi, per una domanda che non
        cambia. Il costo si paga all'attivazione, una volta.
        """
        if self._tts is not None:
            return True, None
        try:
            import piper  # noqa: F401
            from voice.config import load_config
        except ImportError as mancante:
            return False, f"dipendenza vocale assente: {mancante.name}"
        try:
            configurazione = load_config()
        except Exception as problema:  # noqa: BLE001
            return False, f"configurazione vocale illeggibile: {problema}"
        if not getattr(configurazione, "enabled", False):
            return False, "voice_channel.enabled e' false in factory.config.yaml"
        cartella = os.path.expanduser(configurazione.tts.model_dir or ".")
        modello = os.path.join(cartella, f"{configurazione.tts.voice}.onnx")
        if not os.path.isfile(modello):
            return False, f"modello vocale non trovato: {modello}"
        return True, None

    # -- accensione -----------------------------------------------------------
    def attiva(self) -> dict:
        if self._attivo:
            return self.stato().as_dict()
        if not self._carica():
            return {**self.stato().as_dict(), "disponibile": False, "ragione": self._ragione}
        self._attivo = True
        self._thread = threading.Thread(target=self._parla, daemon=True, name="plancia-voce")
        self._thread.start()
        self.di("Canale vocale attivo. Leggo la stessa sequenza dello schermo.")
        return self.stato().as_dict()

    def disattiva(self) -> dict:
        if self._attivo:
            self._attivo = False
            self._coda.put(None)          # sveglia il thread perche' esca
        return self.stato().as_dict()

    # -- consumo --------------------------------------------------------------
    def consume(self, event: Any) -> None:
        """Interfaccia del `Tee`. L'unico punto in cui un evento diventa parlato."""
        testo = tts_payload(event)        # stesso filtro del canale visivo, non una copia
        if testo is None:
            if type(event).__name__ == "Artifact":
                self._scartati += 1
            return
        if self._attivo:
            self.di(testo)

    def di(self, testo: str) -> None:
        self._coda.put(testo[:MAX_CARATTERI])

    def _parla(self) -> None:
        import sounddevice as sd
        while self._attivo:
            testo = self._coda.get()
            if testo is None:
                break
            try:
                audio = self._tts.synthesize(testo)
                sd.play(audio, getattr(self._tts, "sample_rate", 22050))
                sd.wait()
                self._pronunciati += 1
            except Exception:  # noqa: BLE001 — una frase non pronunciata non ferma il canale
                continue

    def stato(self) -> StatoVoce:
        disponibile, ragione = self.disponibile()
        return StatoVoce(attivo=self._attivo, disponibile=disponibile,
                         ragione=ragione or self._ragione, voce=self._voce,
                         pronunciati=self._pronunciati, in_coda=self._coda.qsize(),
                         scartati_artifact=self._scartati)
