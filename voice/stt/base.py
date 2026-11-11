from abc import ABC, abstractmethod


class BaseSTT(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Ritorna il testo trascritto.

        Args:
            audio_bytes: Audio grezzo in formato PCM int16 (little-endian).
                         Se vuoto, restituisce stringa vuota senza chiamate esterne.
            sample_rate: Frequenza di campionamento in Hz (default 16000).

        Returns:
            Testo trascritto come stringa. Stringa vuota se audio_bytes e' vuoto.
        """
        ...
