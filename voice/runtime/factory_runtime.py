"""
voice/runtime/factory_runtime.py — Interfaccia astratta FactoryRuntime e tassonomia eventi.

Questo modulo definisce il contratto (§7) tra il layer vocale e qualunque runtime LLM.
FactoryRuntime e' l'unico punto di contatto: riceve testo + session_id, restituisce uno
stream asincrono di eventi tipizzati.

Contratto §7.2:
  - submit() DEVE emettere Acknowledgment entro poche centinaia di ms per lavori lunghi.
  - Artifact.content NON deve mai essere passato a nessun componente TTS (US-145 AC3).
    Solo SpokenSummary, Acknowledgment e Question vengono instradati al TTS via router.
  - cancel() e' idempotente: chiamarlo piu' volte per la stessa session_id non causa errori.
  - aclose() rilascia le risorse e puo' essere chiamato anche se nessun submit() e' in corso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Union


# ---------------------------------------------------------------------------
# Tassonomia eventi (output del runtime verso il layer vocale)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Acknowledgment:
    """
    Conferma immediata di ricezione («ci sto lavorando...»).

    Deve essere emessa entro poche centinaia di ms dall'avvio dell'elaborazione
    (contratto §7.2: reattivita' per lavori lunghi).
    Destinazione: coda TTS (pronunciata subito dal sintetizzatore vocale).
    """
    text: str


@dataclass(frozen=True)
class Progress:
    """
    Aggiornamento di avanzamento opzionale durante l'elaborazione.

    pct: percentuale di completamento, None se non disponibile.
    Destinazione: canale visivo (barra di progresso); eventuale annuncio breve al TTS.
    """
    text: str
    pct: float | None = None


@dataclass(frozen=True)
class SpokenSummary:
    """
    Sintesi dell'elaborazione pensata per essere pronunciata dal TTS.

    E' l'UNICO testo di risposta LLM instradato alla coda TTS.
    Prodotto dal router (voice/core/router.py) che estrae la sintesi parlata
    dal flusso grezzo del runtime.
    Destinazione: coda TTS (via router, unico percorso autorizzato).
    """
    text: str


@dataclass(frozen=True)
class Artifact:
    """
    Artefatto strutturato prodotto dall'elaborazione (codice, diff, log, JSON, tabella...).

    INVARIANTE NON NEGOZIABILE — contratto §4.2 e US-145 AC3:
      Artifact.content NON deve mai essere passato a nessun componente TTS.
      Il router (voice/core/router.py) garantisce che raggiunga esclusivamente
      il canale visivo (stdout strutturato in MVP). Non esiste percorso di codice
      che trasferisca questo campo a piper_tts o a qualunque altro sintetizzatore.

    kind: categoria dell'artefatto (es. "text", "code", "diff", "json", "table").
    content: contenuto grezzo — MAI al TTS.
    Destinazione: canale visivo ESCLUSIVAMENTE.
    """
    kind: str
    content: str


@dataclass(frozen=True)
class Question:
    """
    Domanda di chiarimento che richiede risposta vocale dall'utente.

    Interrompe il flusso corrente in attesa di input vocale.
    Destinazione: coda TTS (il testo viene pronunciato per sollecitare risposta).
    """
    text: str


@dataclass(frozen=True)
class Done:
    """
    Segnale di fine elaborazione. Chiude il turno corrente.

    Sempre l'ultimo evento emesso da submit() in caso di successo.
    La macchina a stati (voice/core/state_machine.py) usa Done per transitare
    da ELABORAZIONE a PARLATO (quando almeno uno SpokenSummary e' nella coda TTS)
    oppure direttamente a IDLE (se nessun testo parlato e' stato prodotto).
    """


@dataclass(frozen=True)
class Error:
    """
    Errore durante l'elaborazione LLM o nella gestione del tool loop.

    message: descrizione human-readable dell'errore (breve, pronunciabile).
    Destinazione: coda TTS (versione breve) + canale visivo (dettaglio).
    Sempre l'ultimo evento emesso da submit() in caso di errore fatale.
    """
    message: str


# Union type: tutti i possibili eventi emessi da FactoryRuntime.submit()
RuntimeEvent = Union[Acknowledgment, Progress, SpokenSummary, Artifact, Question, Done, Error]


# ---------------------------------------------------------------------------
# Interfaccia astratta
# ---------------------------------------------------------------------------

class FactoryRuntime(ABC):
    """
    Contratto §7 — unico punto di contatto tra il layer vocale e il runtime LLM.

    Il layer vocale (state_machine, router) non conosce i dettagli implementativi
    del runtime: interagisce solo tramite questa interfaccia. Questo permette di
    sostituire l'implementazione concreta (es. da CustomLoopAdapter a un futuro
    AgentSDKAdapter) senza modificare nessun componente vocale.

    Contratto di comportamento (§7.2):
      - submit() DEVE emettere Acknowledgment entro poche centinaia di ms
        per lavori che richiedono elaborazione non immediata.
      - Artifact.content NON deve mai essere passato a nessun componente TTS (US-145 AC3).
      - cancel() e' idempotente: chiamarlo piu' volte per la stessa session_id e' sicuro.
      - aclose() rilascia le risorse in modo sicuro anche se nessun submit() e' in corso.

    Implementazione concreta MVP: CustomLoopAdapter (Opzione B, loop LLM+tool custom).
    Vedi: voice/runtime/custom_loop_adapter.py
    """

    @abstractmethod
    async def submit(self, text: str, session_id: str) -> AsyncIterator[RuntimeEvent]:
        """
        Invia la direttiva utente al runtime LLM e itera gli eventi di risposta.

        Il metodo e' un async generator: il layer vocale lo consuma con::

            async for event in runtime.submit(text, session_id):
                await router.dispatch(event)

        Contratto:
          - DEVE emettere Acknowledgment come primo evento, entro poche centinaia di ms.
          - DEVE emettere Done (o Error) come ultimo evento del turno.
          - DEVE controllare il flag di cancel a ogni yield e terminare pulitamente
            quando cancel(session_id) viene chiamato (barge-in, Fase 3 US-144).
          - NON DEVE bloccare l'event loop asyncio: le operazioni lente (chiamate HTTP,
            tool execution) devono girare su task asyncio o in executor.

        Args:
            text: testo trascritto dall'STT (direttiva utente in linguaggio naturale).
            session_id: identificatore univoco del turno corrente (UUID o stringa).

        Yields:
            RuntimeEvent: sequenza tipizzata di eventi nell'ordine di emissione.
        """
        ...

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        """
        Interrompe l'elaborazione in corso per la sessione indicata.

        Imposta il segnale di cancel che il generator submit() controlla a ogni yield.
        Non blocca: restituisce immediatamente; e' compito del generator terminare pulito.

        Idempotente: chiamarlo su una session_id non attiva, gia' completata o gia'
        cancellata non causa eccezioni. Usato per barge-in (Fase 3, US-144) e shutdown.

        Args:
            session_id: identificatore della sessione da interrompere.
        """
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """
        Rilascia le risorse del runtime (executor, connessioni HTTP/LLM, cache interna).

        Chiamato dallo state_machine al termine della sessione vocale o in caso di
        errore fatale non recuperabile. Idempotente: chiamarlo piu' volte e' sicuro.
        """
        ...

    def is_consumer_alive(self) -> bool:
        """Pre-flight check liveness del consumer. Default True (no disaccoppiamento produttore/consumer).
        Override in FilePipeAdapter per TTL freshness su voice-consumer.alive.

        Tutti gli adapter esistenti (mock, ollama, claude-code, cursor, anthropic,
        custom-loop) ereditano questo default True → comportamento EP-044 invariato.
        """
        return True
