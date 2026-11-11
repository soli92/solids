"""
voice/audio/capture.py — Cattura audio real-time via PortAudio (sounddevice).

Design:
- Il callback PortAudio gira sul thread real-time di sounddevice e NON deve mai
  bloccare (US-143 AC7, §5.3).
- I frame numpy vengono depositati nella queue thread-safe via `put_nowait()`.
- `sounddevice` e' importato lazily dentro `start()`, non a livello di modulo,
  cosi' l'import del modulo non fallisce se sounddevice non e' installato.
- AEC pre-filtro opzionale (US-147 AC5): cattura → AEC → VAD → ...
  Se `aec_processor` e' fornito, ogni frame viene passato attraverso
  `aec_processor.process(mic_frame, far_end_ref)` prima di essere depositato
  in queue. Se None (default), il comportamento e' identico a quello precedente.

Uso tipico (Fase 1, sequenziale):
    from voice.config import load_config
    from voice.audio.capture import AudioCapture

    config = load_config()
    capture = AudioCapture(config)
    capture.start()
    try:
        while True:
            frame = capture.queue.get()   # numpy array float32, shape (chunk, channels)
            ...                            # passa a STT, ecc.
    finally:
        capture.stop()
"""
from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from voice.audio.aec import AECProcessor
    from voice.audio.playback import PlaybackFarEndSink
    from voice.config import VoiceConfig


# Parametri di default per Fase 1 (push-to-talk sequenziale)
_DEFAULT_SAMPLERATE: int = 16000   # Hz — compatibile con faster-whisper
_DEFAULT_CHANNELS: int = 1         # mono
_DEFAULT_DTYPE: str = "float32"    # formato nativo sounddevice (no conversione)
_DEFAULT_CHUNK_MS: int = 32        # ms per chunk → blocksize = 512 frame @ 16kHz (min Silero VAD)


class AudioCapture:
    """
    Cattura audio real-time da un device PortAudio.

    Il callback `_audio_callback` gira sul thread PortAudio real-time e deposita
    ogni frame numpy nella `queue` thread-safe usando `put_nowait()` (non-blocking,
    mai bloccante — US-143 AC7).

    Attributi pubblici:
        queue   — `queue.Queue` thread-safe; ogni elemento e' un numpy array
                  float32 di shape `(blocksize, channels)`.

    Esempio:
        capture = AudioCapture(config)
        capture.start()
        frame = capture.queue.get()   # blocca finche' arriva un frame
        capture.stop()
    """

    def __init__(
        self,
        config: "VoiceConfig",
        aec_processor: Optional["AECProcessor"] = None,
        far_end_sink: Optional["PlaybackFarEndSink"] = None,
    ) -> None:
        """
        Inizializza AudioCapture.

        Args:
            config:        VoiceConfig da `voice.config`. Il device di input (se
                           configurato in config.audio.input_device) viene usato
                           come default in `start()` quando device_index non e'
                           specificato.
            aec_processor: AECProcessor opzionale per la cancellazione eco
                           (US-147 AC5). Se None, nessuna elaborazione AEC
                           (backward compat totale). Posizione nella catena:
                           cattura → AEC → queue → VAD → STT.
            far_end_sink:  PlaybackFarEndSink opzionale che fornisce il segnale
                           TTS in riproduzione come reference far-end per l'AEC.
                           None in Fase 1 (push-to-talk sequenziale): il processore
                           gestisce reference_frame=None con pass-through (AC4).
        """
        self._config = config
        # Calcola il blocksize di default: _DEFAULT_CHUNK_MS ms @ _DEFAULT_SAMPLERATE
        self._default_blocksize: int = max(
            1, int(_DEFAULT_SAMPLERATE * _DEFAULT_CHUNK_MS / 1000)
        )  # = 480 frame @ 16kHz + 30ms

        # Queue thread-safe: capacita' illimitata (il chiamante drena in tempo reale)
        self._queue: queue.Queue = queue.Queue()

        # AEC pre-filtro opzionale (US-147 AC5): cattura → AEC → VAD
        # Se None: nessuna elaborazione AEC (NoOpProcessor implicito, zero overhead).
        self._aec_processor: Optional["AECProcessor"] = aec_processor
        # Sink far-end: fornisce i frame TTS in riproduzione come reference per AEC.
        # None in Fase 1 (push-to-talk: cattura e playback non si sovrappongono).
        self._far_end_sink: Optional["PlaybackFarEndSink"] = far_end_sink

        # Stato interno
        self._stream: Optional[object] = None
        self._lock = threading.Lock()

    @property
    def queue(self) -> queue.Queue:
        """Coda thread-safe dove il callback deposita i frame numpy (float32)."""
        return self._queue

    def start(
        self,
        device_index: Optional[int] = None,
        samplerate: int = _DEFAULT_SAMPLERATE,
        channels: int = _DEFAULT_CHANNELS,
        dtype: str = _DEFAULT_DTYPE,
    ) -> None:
        """
        Avvia lo stream PortAudio e registra il callback real-time.

        I parametri espliciti sovrascrivono i default. Quando `device_index` e'
        None, viene usato `config.audio.input_device` (nome stringa) se impostato,
        altrimenti il device di input di default del sistema.

        Chiamata idempotente: se lo stream e' gia' aperto, non fa nulla.

        Args:
            device_index:  indice intero del device PortAudio (None = usa config
                           o device di default).
            samplerate:    frequenza di campionamento in Hz (default 16000).
            channels:      numero di canali (default 1, mono).
            dtype:         tipo numpy per i frame ('float32' default, consigliato
                           per sounddevice).

        Raises:
            ImportError: se sounddevice non e' installato.
        """
        # Import lazy: sounddevice gira solo se richiamato (non a livello modulo)
        try:
            import sounddevice as sd  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "sounddevice non trovato. "
                "Installa le dipendenze vocali: pip install '.[voice]'"
            ) from exc

        with self._lock:
            if self._stream is not None:
                return  # gia' avviato, no-op

            # Risolvi il device: priorita' → argomento esplicito → config → default
            device = device_index
            if device is None and self._config.audio.input_device is not None:
                device = self._config.audio.input_device  # stringa nome device

            blocksize = self._default_blocksize

            import logging as _log  # noqa: PLC0415
            _log.getLogger(__name__).info(
                "AudioCapture: apertura stream device=%r samplerate=%d blocksize=%d",
                device, samplerate, blocksize,
            )
            try:
                dev_info = sd.query_devices(device, "input")
                _log.getLogger(__name__).info(
                    "AudioCapture: device selezionato → '%s'", dev_info.get("name", "?")
                )
            except Exception:  # noqa: BLE001
                pass
            self._stream = sd.InputStream(
                samplerate=samplerate,
                channels=channels,
                dtype=dtype,
                blocksize=blocksize,
                device=device,
                callback=self._audio_callback,
            )
            self._stream.start()

    def stop(self) -> None:
        """
        Ferma la cattura e chiude lo stream PortAudio.

        Idempotente: puo' essere chiamato piu' volte senza eccezioni.
        """
        with self._lock:
            if self._stream is None:
                return
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

    def _audio_callback(
        self,
        indata: "np.ndarray",  # noqa: F821
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """
        Callback PortAudio — gira sul thread real-time di sounddevice.

        Posizione nella catena: cattura → AEC (pre-filtro) → queue → VAD → STT
        (US-147 AC5). Il processore AEC e' applicato qui, subito dopo la cattura
        del frame, prima di depositarlo nella queue per il VAD.

        VINCOLO (US-143 AC7): questo metodo NON deve mai bloccare.
        Usa `put_nowait()` (non-blocking); se la queue e' piena il frame viene
        silenziosamente scartato per mantenere il real-time budget.

        Args:
            indata:      numpy array float32 shape `(blocksize, channels)` con i
                         campioni audio del chunk corrente.
            frames:      numero di frame nel chunk (= blocksize).
            time_info:   dizionario con timing PortAudio (non usato in Fase 1).
            status:      flag di stato PortAudio (overflow, underflow, ecc.).
        """
        # Copia difensiva: indata e' un buffer temporaneo che sounddevice potrebbe
        # riutilizzare dopo il ritorno del callback.
        frame = indata.copy()

        # AEC pre-filtro (US-147 AC5): cattura → AEC → VAD.
        # Se aec_processor e' None: nessuna elaborazione (zero overhead, backward compat).
        # Se aec_processor e' impostato, ogni frame transita per il processore prima
        # di essere depositato in queue — eliminando l'eco TTS prima del VAD.
        if self._aec_processor is not None:
            # Flatten to mono (N,) per AECProcessor.process() — indata e' gia' float32
            # per _DEFAULT_DTYPE='float32'. Se multi-canale, prende il primo canale.
            mic_mono = frame[:, 0] if frame.ndim > 1 else frame.ravel()
            # Reference far-end: frame TTS piu' recente in riproduzione (dal sink).
            # None in Fase 1 (push-to-talk sequenziale: capture e playback non si
            # sovrappongono). Il processore gestisce reference_frame=None con
            # pass-through graceful (US-147 AC4).
            ref = (
                self._far_end_sink.get_latest()
                if self._far_end_sink is not None
                else None
            )
            processed = self._aec_processor.process(mic_mono, ref)
            # Reshape (N,) → (N, 1) per compatibilita' con i consumer downstream
            # (es. _drain_queue in state_machine.py che fa audio[:, 0] su shape
            # (total_frames, channels)).
            frame = processed.reshape(-1, 1)

        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            # Queue piena: scarta il frame piuttosto che bloccare il thread RT
            pass
