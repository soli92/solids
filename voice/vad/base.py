"""voice/vad/base.py — Interfaccia astratta Voice Activity Detection.

Modulo importabile senza dipendenze esterne (lazy import nei sottomoduli).
Nessuna dipendenza a livello di modulo: solo stdlib.
"""

from abc import ABC, abstractmethod


class VADBase(ABC):
    """Interfaccia astratta per un rilevatore di attivita' vocale (VAD).

    Le implementazioni concrete (SileroVAD, WebRTCVAD) devono importare
    le proprie dipendenze lazily per garantire l'importabilita' su ambienti
    senza torch / webrtcvad installati.
    """

    @abstractmethod
    def is_speech(self, frame: bytes, samplerate: int) -> bool:
        """Ritorna True se il frame audio contiene parlato.

        Args:
            frame: Chunk di audio grezzo PCM a 16-bit little-endian.
            samplerate: Frequenza di campionamento in Hz (es. 16000).

        Returns:
            True se il frame e' classificato come parlato, False altrimenti.
        """
        ...
