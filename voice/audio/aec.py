"""
voice/audio/aec.py — AECProcessor: interfaccia astratta + implementazioni concrete.

Posizione nella catena:  cattura → AEC → VAD → ...  (US-147 AC5)

Architettura (US-147 Note Tecniche §Implementazioni):
    AEC (echo cancellation) != riduzione rumore.
    L'AEC vero richiede la reference far-end (i frame TTS in playback) per
    sottrarre l'eco correlata dal segnale microfono. La riduzione rumore
    (NoiseReduceProcessor) non ha reference far-end: da sola non cancella
    l'eco correlata al TTS — e' solo un pre-filtro complementare o fallback
    degradato.

    | Classe                | Reference far-end | Cosa rimuove                  |
    |-----------------------|-------------------|-------------------------------|
    | WebRTCAPMProcessor    | Si'               | eco correlata al TTS          |
    | SpeexDSPProcessor     | Si'               | eco correlata al TTS (lite)   |
    | NoiseReduceProcessor  | No                | rumore ambientale stazionario |
    | NoOpProcessor         | —                 | pass-through puro             |

Degradazione graceful (US-147 AC3, AC4):
    Se aec.enabled=False → NoOpProcessor (nessun import, zero overhead).
    Se aec.enabled=True ma il provider non e' installabile:
        webrtc-apm → speexdsp → noisereduce (solo noise) → NoOp + WARNING cuffie.

Frame format:
    mic_frame / reference_frame: numpy float32, shape (N,) — mono 1D.
    Il chiamante e' responsabile di flatten da (N, 1) a (N,) se necessario
    (cf. voice/audio/capture.py: indata shape = (blocksize, channels)).

Uso:
    from voice.config import load_config
    from voice.audio.aec import create_aec_processor

    cfg = load_config()
    processor = create_aec_processor(cfg.aec)   # usa cfg.aec (AECConfig)
    filtered = processor.process(mic_frame, reference_frame)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Frequenza di campionamento attesa (coerente con AudioCapture default)
_DEFAULT_SAMPLE_RATE: int = 16_000


# ---------------------------------------------------------------------------
# Interfaccia astratta
# ---------------------------------------------------------------------------

class AECProcessor(ABC):
    """
    Interfaccia astratta per l'Acoustic Echo Cancellation.

    Filtra l'eco acustica dall'audio catturato dal microfono (near-end)
    usando il segnale TTS in riproduzione (far-end reference) quando disponibile.

    Le implementazioni concrete sono responsabili di:
    - effettuare gli import lazy delle librerie di terze parti;
    - gestire il proprio stato interno (reinizializzabile via reset());
    - mantenere la stessa shape in input/output: (N,) float32.
    """

    @abstractmethod
    def process(
        self,
        mic_frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Filtra l'eco dal frame del microfono.

        Args:
            mic_frame:       PCM float32, shape (N,) — segnale near-end (microfono).
            reference_frame: PCM float32, shape (N,) — segnale far-end (TTS in
                             playback); None se non disponibile. Le implementazioni
                             AEC vere (WebRTC, Speex) richiedono questa reference
                             per cancellare l'eco correlata al TTS.

        Returns:
            PCM float32, shape (N,) — frame filtrato (echo-canceled o pass-through).
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """
        Reinizializza lo stato interno del processore.

        Da chiamare tra sessioni vocali distinte o dopo pause prolungate
        per evitare che lo stato AEC residuo contamini i frame successivi.
        """
        ...


# ---------------------------------------------------------------------------
# NoOpProcessor — pass-through puro (default quando aec.enabled: false)
# ---------------------------------------------------------------------------

class NoOpProcessor(AECProcessor):
    """
    Pass-through puro: restituisce mic_frame invariato.

    Zero import, zero overhead. Utilizzato di default quando aec.enabled=False
    (US-147 AC3) o come ultimo fallback della cascata graceful (AC4).
    Con cuffie questo e' il comportamento corretto (canali fisicamente separati).
    """

    def process(
        self,
        mic_frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        return mic_frame

    def reset(self) -> None:
        pass  # nessuno stato interno


# ---------------------------------------------------------------------------
# WebRTCAPMProcessor — provider primario (webrtc-apm)
# ---------------------------------------------------------------------------

class WebRTCAPMProcessor(AECProcessor):
    """
    AEC tramite WebRTC Audio Processing Module (APM).

    Usa il binding Python del WebRTC APM per la cancellazione dell'eco.
    Richiede la reference far-end (i frame TTS in playback) per la correlazione.

    NOTA INSTALLAZIONE: il binding webrtc_audio_processing non e' su PyPI come
    pacchetto standard. Installazione tramite wheel precompilata o build da
    sorgente (documentata nel runbook voice-channel-installation.md §Fase4).
    Se non installato, questo costruttore solleva ImportError con messaggio chiaro.

    Parametri:
        sample_rate: frequenza di campionamento (default 16000 Hz).
        frame_size:  dimensione frame in campioni (default 160 = 10 ms @ 16kHz).
    """

    def __init__(
        self,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        frame_size: int = 160,
    ) -> None:
        # Import lazy — non importare a livello di modulo (US-147 AC3).
        try:
            import webrtc_audio_processing as webrtc_apm  # noqa: PLC0415
            self._webrtc_apm = webrtc_apm
        except ImportError as exc:
            raise ImportError(
                "WebRTC APM non installato. Usa cuffie o installa il binding. "
                "Vedi runbook voice-channel-installation.md §'Fase 4 (opzionale): "
                "AEC per altoparlanti' per le istruzioni di installazione."
            ) from exc

        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._apm = self._build_apm()

    def _build_apm(self) -> object:
        """Costruisce e configura l'istanza APM con AEC attivo."""
        try:
            apm = self._webrtc_apm.AudioProcessingModule()
            # Abilita AEC (echo cancellation)
            if hasattr(apm, "enable_echo_cancellation"):
                apm.enable_echo_cancellation(True)
            elif hasattr(apm, "set_config"):
                # API alternativa presente in alcune versioni del binding
                cfg = self._webrtc_apm.Config()
                if hasattr(cfg, "echo_canceller"):
                    cfg.echo_canceller.enabled = True
                apm.set_config(cfg)
            return apm
        except Exception as exc:  # noqa: BLE001
            # Se l'istanza APM non supporta AEC, logga WARNING e usa pass-through.
            logger.warning(
                "WebRTC APM installato ma AEC non supportato dall'API disponibile. "
                "Il processore agira' come pass-through. "
                "Dettaglio: %s", exc
            )
            return None

    def process(
        self,
        mic_frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if self._apm is None:
            # APM non funzionante — pass-through (gia' loggato nel costruttore)
            return mic_frame

        if reference_frame is None:
            # Senza reference far-end l'AEC non puo' operare: pass-through.
            logger.debug(
                "WebRTCAPMProcessor.process: reference_frame=None, pass-through."
            )
            return mic_frame

        try:
            # Converti in int16 PCM per l'API WebRTC APM (attesa da molte versioni
            # del binding come int16 linear PCM).
            mic_i16 = (np.clip(mic_frame, -1.0, 1.0) * 32767).astype(np.int16)
            ref_i16 = (np.clip(reference_frame, -1.0, 1.0) * 32767).astype(np.int16)

            # Processa in chunk da frame_size se il frame e' piu' lungo.
            if len(mic_i16) <= self._frame_size:
                mic_chunks = [mic_i16]
                ref_chunks = [ref_i16]
            else:
                mic_chunks = [
                    mic_i16[i : i + self._frame_size]
                    for i in range(0, len(mic_i16), self._frame_size)
                ]
                ref_chunks = [
                    ref_i16[i : i + self._frame_size]
                    for i in range(0, len(ref_i16), self._frame_size)
                ]

            out_chunks = []
            for m_chunk, r_chunk in zip(mic_chunks, ref_chunks):
                # Imbottisci l'ultimo chunk se non multiplo di frame_size
                if len(m_chunk) < self._frame_size:
                    pad = self._frame_size - len(m_chunk)
                    m_chunk = np.pad(m_chunk, (0, pad))
                    r_chunk = np.pad(r_chunk, (0, pad)) if len(r_chunk) < self._frame_size else r_chunk[: self._frame_size]

                # API 1: process_capture_frame + set_stream_delay (standard binding)
                if hasattr(self._apm, "process_capture_frame"):
                    if hasattr(self._apm, "set_stream_delay_ms"):
                        self._apm.set_stream_delay_ms(0)
                    out_chunk = self._apm.process_capture_frame(m_chunk, r_chunk)
                # API 2: process con signature (mic, ref) — versioni alternative
                elif hasattr(self._apm, "process"):
                    out_chunk = self._apm.process(m_chunk, r_chunk)
                else:
                    # API non riconosciuta: pass-through del chunk
                    out_chunk = m_chunk

                out_chunks.append(out_chunk)

            # Riassembla e converti in float32
            out_i16 = np.concatenate(out_chunks)[: len(mic_frame)]
            return out_i16.astype(np.float32) / 32767.0

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "WebRTCAPMProcessor.process: errore durante l'elaborazione (%s). "
                "Pass-through per questo frame.", exc
            )
            return mic_frame

    def reset(self) -> None:
        """Reinizializza l'APM per una nuova sessione."""
        if self._apm is not None:
            try:
                if hasattr(self._apm, "initialize"):
                    self._apm.initialize()
            except Exception as exc:  # noqa: BLE001
                logger.debug("WebRTCAPMProcessor.reset: %s", exc)
            # Ricostruisce l'istanza in caso di errore o reset non supportato
            self._apm = self._build_apm()


# ---------------------------------------------------------------------------
# SpeexDSPProcessor — alternativa leggera (speexdsp)
# ---------------------------------------------------------------------------

class SpeexDSPProcessor(AECProcessor):
    """
    AEC tramite SpeexDSP EchoCanceller.

    Alternativa leggera a WebRTC APM. Richiede anch'essa la reference far-end
    (i frame TTS in playback) per la cancellazione dell'eco correlata.
    Installazione: pip install speexdsp

    Qualita' inferiore a WebRTC APM ma sufficiente per mitigare i falsi trigger
    VAD causati dal TTS su altoparlanti (US-147 Note Tecniche).

    Parametri:
        sample_rate:   frequenza di campionamento (default 16000 Hz).
        frame_size:    dimensione frame in campioni (default 160 = 10 ms @ 16kHz).
        filter_length: lunghezza filtro AEC in campioni (default 1600 = 100 ms).
    """

    def __init__(
        self,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        frame_size: int = 160,
        filter_length: int = 1600,
    ) -> None:
        # Import lazy — non importare a livello di modulo (US-147 AC3).
        try:
            import speexdsp  # noqa: PLC0415
            self._speexdsp = speexdsp
        except ImportError as exc:
            raise ImportError(
                "speexdsp non installato. "
                "Installa con: pip install speexdsp"
            ) from exc

        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._filter_length = filter_length
        self._echo_canceller = self._build_canceller()

    def _build_canceller(self) -> object:
        """Costruisce l'istanza SpeexEchoState."""
        try:
            # API standard speexdsp: EchoCanceller(frame_size, filter_length)
            if hasattr(self._speexdsp, "EchoCanceller"):
                return self._speexdsp.EchoCanceller(
                    self._frame_size, self._filter_length
                )
            # API alternativa: SpeexEchoState
            elif hasattr(self._speexdsp, "SpeexEchoState"):
                return self._speexdsp.SpeexEchoState(
                    self._frame_size, self._filter_length
                )
            else:
                logger.warning(
                    "speexdsp installato ma nessuna API EchoCanceller trovata. "
                    "Il processore agira' come pass-through."
                )
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpeexDSPProcessor: errore durante la costruzione del canceller "
                "(%s). Pass-through attivo.", exc
            )
            return None

    def process(
        self,
        mic_frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if self._echo_canceller is None:
            return mic_frame

        if reference_frame is None:
            logger.debug(
                "SpeexDSPProcessor.process: reference_frame=None, pass-through."
            )
            return mic_frame

        try:
            # speexdsp opera su int16 PCM
            mic_i16 = (np.clip(mic_frame, -1.0, 1.0) * 32767).astype(np.int16)
            ref_i16 = (np.clip(reference_frame, -1.0, 1.0) * 32767).astype(np.int16)

            # Processa in chunk da frame_size
            out_chunks = []
            for i in range(0, len(mic_i16), self._frame_size):
                m_chunk = mic_i16[i : i + self._frame_size]
                r_chunk = ref_i16[i : i + self._frame_size]

                # Imbottisci se necessario
                if len(m_chunk) < self._frame_size:
                    pad = self._frame_size - len(m_chunk)
                    m_chunk = np.pad(m_chunk, (0, pad))
                if len(r_chunk) < self._frame_size:
                    pad = self._frame_size - len(r_chunk)
                    r_chunk = np.pad(r_chunk, (0, pad))

                # API speexdsp: echo_cancel(mic_frame, reference_frame)
                if hasattr(self._echo_canceller, "echo_cancel"):
                    out_chunk = self._echo_canceller.echo_cancel(m_chunk, r_chunk)
                elif hasattr(self._echo_canceller, "process"):
                    out_chunk = self._echo_canceller.process(m_chunk, r_chunk)
                else:
                    out_chunk = m_chunk

                out_chunks.append(np.asarray(out_chunk, dtype=np.int16))

            out_i16 = np.concatenate(out_chunks)[: len(mic_frame)]
            return out_i16.astype(np.float32) / 32767.0

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpeexDSPProcessor.process: errore (%s). Pass-through per questo frame.",
                exc,
            )
            return mic_frame

    def reset(self) -> None:
        """Reinizializza il filtro AEC (nuova sessione vocale)."""
        try:
            if self._echo_canceller is not None and hasattr(
                self._echo_canceller, "reset"
            ):
                self._echo_canceller.reset()
            else:
                # Ricostruisce l'istanza se reset() non e' disponibile
                self._echo_canceller = self._build_canceller()
        except Exception as exc:  # noqa: BLE001
            logger.debug("SpeexDSPProcessor.reset: %s", exc)
            self._echo_canceller = self._build_canceller()


# ---------------------------------------------------------------------------
# NoiseReduceProcessor — pre-filtro complementare (noisereduce)
# ---------------------------------------------------------------------------

class NoiseReduceProcessor(AECProcessor):
    """
    Pre-filtro rumore stazionario tramite noisereduce (spectral gating).

    IMPORTANTE — NON e' un AEC vero: non usa reference far-end, non rimuove
    l'eco correlata al TTS. Utile solo come stadio aggiuntivo dopo un AEC vero
    per ripulire il rumore ambientale, oppure come fallback degradato quando
    nessun AEC con reference far-end e' installabile. In quest'ultimo caso
    il runbook deve indicare "cuffie come mitigazione raccomandata" poiche'
    questo processore NON risolve il problema dei falsi trigger da TTS su
    altoparlanti (US-147 Note Tecniche §Degradazione graceful).

    Installazione: pip install noisereduce

    Parametri:
        sample_rate:      frequenza di campionamento (default 16000 Hz).
        stationary:       True = riduzione rumore stazionario (piu' stabile,
                          meno artefatti); False = non-stazionario (piu'
                          aggressivo, piu' adatto a rumori variabili).
        prop_decrease:    fattore di riduzione (0.0–1.0, default 0.9).
    """

    def __init__(
        self,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        stationary: bool = True,
        prop_decrease: float = 0.9,
    ) -> None:
        # Import lazy — non importare a livello di modulo (US-147 AC3).
        try:
            import noisereduce as nr  # noqa: PLC0415
            self._nr = nr
        except ImportError as exc:
            raise ImportError(
                "noisereduce non installato. "
                "Installa con: pip install noisereduce"
            ) from exc

        self._sample_rate = sample_rate
        self._stationary = stationary
        self._prop_decrease = prop_decrease

    def process(
        self,
        mic_frame: np.ndarray,
        reference_frame: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Applica spectral gating per riduzione rumore stazionario.

        reference_frame viene IGNORATO: questo processore non ha reference far-end
        e non cancella l'eco correlata al TTS. Il parametro e' presente solo per
        rispettare l'interfaccia AECProcessor.
        """
        # reference_frame ignorato — documentato sopra
        try:
            out = self._nr.reduce_noise(
                y=mic_frame,
                sr=self._sample_rate,
                stationary=self._stationary,
                prop_decrease=self._prop_decrease,
            )
            return out.astype(np.float32)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "NoiseReduceProcessor.process: errore (%s). Pass-through per questo frame.",
                exc,
            )
            return mic_frame

    def reset(self) -> None:
        """No-op: noisereduce e' stateless (ogni chiamata e' indipendente)."""
        pass


# ---------------------------------------------------------------------------
# Factory function — cascata di fallback
# ---------------------------------------------------------------------------

def create_aec_processor(config) -> AECProcessor:
    """
    Crea il processore AEC appropriato dalla config AECConfig.

    Cascata di fallback (US-147 AC4, Note Tecniche §Degradazione graceful):
        webrtc-apm → speexdsp → noisereduce (solo noise) → NoOp + avviso cuffie.

    Args:
        config: AECConfig (da VoiceConfig.aec).
                Deve avere gli attributi:
                  - enabled: bool
                  - provider: str ('webrtc-apm' | 'speexdsp' | 'noisereduce')

    Returns:
        L'istanza AECProcessor piu' capace installabile nel sistema corrente.

    Note:
        - Se config.enabled=False: restituisce NoOpProcessor senza import (AC3).
        - Se config.enabled=True ma il provider non e' installabile: fallback
          graceful con WARNING, non crash (AC4).
        - Il provider 'webrtc-apm' e' l'unico provider del MVP (US-147 AC2).
    """
    # AC3: aec.enabled=False → NoOpProcessor, zero import
    if not config.enabled:
        return NoOpProcessor()

    provider = getattr(config, "provider", "webrtc-apm")

    # ---- webrtc-apm (provider primario) ------------------------------------
    if provider == "webrtc-apm":
        try:
            processor = WebRTCAPMProcessor()
            logger.info("AEC: WebRTCAPMProcessor attivo.")
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC webrtc-apm non disponibile: %s. "
                "Tentativo con speexdsp.", exc
            )

        # Fallback 1: speexdsp
        try:
            processor = SpeexDSPProcessor()
            logger.warning(
                "AEC: WebRTC APM non disponibile. Uso SpeexDSPProcessor (qualita' "
                "inferiore). Per risultati migliori installa il binding WebRTC APM "
                "(vedi runbook voice-channel-installation.md §Fase4)."
            )
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC speexdsp non disponibile: %s. "
                "Tentativo con noisereduce (SOLO riduzione rumore, NON AEC).", exc
            )

        # Fallback 2: noisereduce (degradato — non e' AEC vero)
        try:
            processor = NoiseReduceProcessor()
            logger.warning(
                "AEC: WebRTC APM e SpeexDSP non disponibili. "
                "Uso NoiseReduceProcessor (SOLO riduzione rumore stazionario — "
                "NON cancella l'eco del TTS). "
                "RACCOMANDAZIONE: usa cuffie per evitare falsi trigger VAD da "
                "altoparlanti, oppure installa webrtc-apm o speexdsp "
                "(vedi runbook voice-channel-installation.md §Fase4)."
            )
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC noisereduce non disponibile: %s. "
                "Degradazione al NoOpProcessor.", exc
            )

        # Fallback finale: NoOp + avviso cuffie
        logger.warning(
            "AEC: nessun provider AEC installato (webrtc-apm, speexdsp, noisereduce). "
            "Il sistema avvia senza cancellazione eco. "
            "RACCOMANDAZIONE CRITICA: usa cuffie per evitare falsi trigger VAD e "
            "auto-barge-in causati dall'audio TTS su altoparlanti. "
            "Per abilitare AEC, vedi runbook voice-channel-installation.md §Fase4."
        )
        return NoOpProcessor()

    # ---- speexdsp (provider esplicito) ------------------------------------
    elif provider == "speexdsp":
        try:
            processor = SpeexDSPProcessor()
            logger.info("AEC: SpeexDSPProcessor attivo.")
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC speexdsp non disponibile: %s. "
                "Tentativo con noisereduce (SOLO riduzione rumore, NON AEC).", exc
            )

        try:
            processor = NoiseReduceProcessor()
            logger.warning(
                "AEC: SpeexDSP non disponibile. "
                "Uso NoiseReduceProcessor (NON AEC vero). "
                "RACCOMANDAZIONE: usa cuffie."
            )
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC noisereduce non disponibile: %s. NoOpProcessor attivo.", exc
            )
        logger.warning(
            "AEC: nessun provider disponibile. Avvio senza AEC. Usa cuffie."
        )
        return NoOpProcessor()

    # ---- noisereduce (provider esplicito — solo riduzione rumore) ----------
    elif provider == "noisereduce":
        try:
            processor = NoiseReduceProcessor()
            logger.warning(
                "AEC: NoiseReduceProcessor attivo (provider='noisereduce'). "
                "ATTENZIONE: NON e' un AEC vero — non cancella l'eco del TTS. "
                "Usa cuffie o scegli provider='webrtc-apm' per AEC reale."
            )
            return processor
        except ImportError as exc:
            logger.warning(
                "AEC noisereduce non disponibile: %s. NoOpProcessor attivo.", exc
            )
        return NoOpProcessor()

    # ---- provider sconosciuto — fallback sicuro ----------------------------
    else:
        logger.warning(
            "AEC: provider sconosciuto %r. Fallback a cascata webrtc-apm.", provider
        )
        # Riesegue con provider di default
        from dataclasses import replace  # noqa: PLC0415
        try:
            config_default = replace(config, provider="webrtc-apm")
            return create_aec_processor(config_default)
        except TypeError:
            # config non e' un dataclass — usa attributo direttamente
            object.__setattr__(config, "provider", "webrtc-apm")
            return create_aec_processor(config)


# Alias per compatibilita' con il DoD del TSK-306 (create_processor)
create_processor = create_aec_processor
