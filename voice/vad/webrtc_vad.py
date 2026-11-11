"""voice/vad/webrtc_vad.py — Wrapper WebRTC VAD (fallback leggero, frame-based).

Importabile senza webrtcvad installato: l'import di webrtcvad e' lazy.

Per installare le dipendenze:
    pip install -e ".[voice]"
    # oppure: pip install webrtcvad-wheels  (wheels precompilate, consigliato)

WebRTC VAD opera su frame a 10, 20 o 30 ms a 8000, 16000, 32000, 48000 Hz.
La lunghezza in byte del frame deve essere esattamente:
    frame_bytes = sample_rate * frame_ms // 1000 * 2   (PCM 16-bit mono)
"""

from __future__ import annotations

from voice.vad.base import VADBase

# Frame duration ammesse da webrtcvad (ms)
_VALID_FRAME_MS = (10, 20, 30)

# Sample rate ammessi da webrtcvad (Hz)
_VALID_SAMPLE_RATES = (8000, 16000, 32000, 48000)


class WebRTCVAD(VADBase):
    """VAD basato su WebRTC (libreria webrtcvad), leggero e deterministico.

    Progettato come alternativa senza GPU a SileroVAD. Non richiede torch.
    L'import di webrtcvad e' lazy: il costruttore non fallisce se la libreria
    non e' installata; il fallimento avviene alla prima chiamata a is_speech().

    Args:
        aggressiveness: Livello di aggressivita' (0=meno aggressivo, 3=piu');
                        default 2. Controlla quanta voce bassa viene filtrata.
        sample_rate:    Frequenza di campionamento (default 16000 Hz).
                        Valori ammessi: 8000, 16000, 32000, 48000.
    """

    def __init__(
        self,
        aggressiveness: int = 2,
        sample_rate: int = 16000,
    ) -> None:
        if aggressiveness not in range(4):
            raise ValueError(
                f"aggressiveness deve essere 0, 1, 2 o 3, ricevuto: {aggressiveness}"
            )
        if sample_rate not in _VALID_SAMPLE_RATES:
            raise ValueError(
                f"WebRTCVAD supporta solo sample_rate in {_VALID_SAMPLE_RATES}, "
                f"ricevuto: {sample_rate}"
            )
        self.aggressiveness = aggressiveness
        self.sample_rate = sample_rate

        # Lazy init — valorizzato al primo is_speech()
        self._vad = None

    # ------------------------------------------------------------------
    # Metodo privato di inizializzazione lazy
    # ------------------------------------------------------------------

    def _ensure_vad(self) -> None:
        """Crea l'istanza webrtcvad.Vad al primo utilizzo (lazy init).

        Raises:
            ImportError: Se webrtcvad non e' installato.
        """
        if self._vad is not None:
            return

        try:
            import webrtcvad  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "webrtcvad non e' installato. Per abilitare WebRTCVAD esegui:\n"
                "    pip install -e '.[voice]'\n"
                "oppure: pip install webrtcvad-wheels"
            ) from exc

        self._vad = webrtcvad.Vad(self.aggressiveness)

    # ------------------------------------------------------------------
    # Interfaccia VADBase
    # ------------------------------------------------------------------

    def is_speech(self, frame: bytes, samplerate: int) -> bool:
        """Classifica il frame audio tramite WebRTC VAD.

        Il frame deve avere una durata di 10, 20 o 30 ms a sample_rate Hz,
        codificata come PCM 16-bit little-endian mono.

        Args:
            frame:      Chunk di audio grezzo PCM a 16-bit little-endian mono.
            samplerate: Frequenza di campionamento in Hz.

        Returns:
            True se il frame contiene parlato.

        Raises:
            ImportError: Se webrtcvad non e' installato (al primo utilizzo).
            ValueError:  Se samplerate o la dimensione del frame non sono validi.
        """
        if samplerate not in _VALID_SAMPLE_RATES:
            raise ValueError(
                f"WebRTCVAD supporta solo sample_rate in {_VALID_SAMPLE_RATES}, "
                f"ricevuto: {samplerate}"
            )

        # Verifica che la lunghezza del frame corrisponda a una durata ammessa
        num_samples = len(frame) // 2  # PCM 16-bit = 2 bytes/sample
        frame_ms = num_samples * 1000 // samplerate
        if frame_ms not in _VALID_FRAME_MS:
            expected = {
                ms: samplerate * ms // 1000 * 2
                for ms in _VALID_FRAME_MS
            }
            raise ValueError(
                f"WebRTCVAD richiede frame a 10, 20 o 30 ms. "
                f"Frame ricevuto: {len(frame)} bytes ({frame_ms} ms a {samplerate} Hz). "
                f"Dimensioni attese a {samplerate} Hz: {expected}"
            )

        self._ensure_vad()
        return self._vad.is_speech(frame, samplerate)
