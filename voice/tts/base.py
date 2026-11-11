"""voice/tts/base.py — interfaccia astratta TTS.

Modulo importabile senza dipendenze esterne (lazy import nei sottomoduli).
L'unica dipendenza è numpy, che fa parte dell'ambiente standard [voice].
"""

from abc import ABC, abstractmethod

import numpy as np


class TTSBase(ABC):
    """Interfaccia astratta per i motori Text-to-Speech.

    Tutte le implementazioni concrete restituiscono audio PCM float32 mono
    normalizzato in [-1.0, 1.0].

    Uso asincrono raccomandato (da state_machine o router):
        audio: np.ndarray = await asyncio.to_thread(tts.synthesize, text)
    """

    @abstractmethod
    def synthesize(self, text: str) -> np.ndarray:
        """Sintetizza *text* in audio PCM float32 mono.

        Args:
            text: Testo da sintetizzare.

        Returns:
            np.ndarray float32 mono, valori in [-1.0, 1.0].
            Shape: (N,) dove N e' il numero di campioni.
            Array vuoto se la sintesi non produce output.
        """
        ...
