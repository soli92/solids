"""Il percorso di scrittura della plancia (US-288..US-291).

**LA PLANCIA NON E' UNO SCRITTORE.** Non modifica `wiki/`, non modifica
`management/kanban/`, non cambia nessun `status:`, non scrive in `analytics/`. Ogni
azione dell'utente diventa una `FactoryRuntime.submit()`: **lo scrittore resta la
sessione**, che resta singola.

Non e' una precauzione, e' il vincolo che rende sicuro lo stadio di scrittura. EP-064
ha misurato la classe di problema del doppio scrittore sul kanban e ha deciso che
l'arbitro non valeva il costo; qui il problema non si presenta perche' non esistono
due scrittori — esiste un client e uno scrittore. Se un giorno qualcuno aggiungesse
qui una scrittura diretta, EP-067 diventerebbe il caso che EP-064 ha rifiutato di
risolvere. Per questo il divieto e' verificato da un test sull'AST e non affidato a
questo commento.

Runtime non raggiungibile ⇒ **fail-closed in scrittura, fail-open in lettura**: i
comandi si disabilitano dichiarando la ragione, le viste continuano a funzionare.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from visual.channel import VisualChannel
from visual.parita import Tee

#: Azioni offerte dalla plancia. NON sono hardcoded nel frontend: si derivano dalle
#: capability dichiarate dalla factory (US-290 AC1), e ognuna dichiara se e' difficile
#: da annullare — nel qual caso la conferma deve descrivere la CONSEGUENZA, non
#: chiedere «sei sicuro».
@dataclass(frozen=True)
class Azione:
    nome: str
    direttiva: str
    descrizione: str
    #: `None` = nessuna conferma. Altrimenti e' il testo che dice cosa accadra'.
    conseguenza: str | None = None
    #: Flag di `factory.config.yaml` che deve essere acceso perche' l'azione esista.
    richiede_capability: str | None = None

    @property
    def difficile_da_annullare(self) -> bool:
        return self.conseguenza is not None

    def as_dict(self) -> dict:
        return {"nome": self.nome, "direttiva": self.direttiva,
                "descrizione": self.descrizione, "conseguenza": self.conseguenza,
                "difficile_da_annullare": self.difficile_da_annullare}


#: Catalogo minimo. Ogni voce e' una DIRETTIVA in linguaggio naturale, perche' e' cio'
#: che il contratto accetta: la plancia non chiama funzioni della factory, le chiede.
CATALOGO = (
    Azione("Stato del progetto", "/run",
           "Mostra lo stato del progetto e il prossimo passo suggerito"),
    Azione("Controllo di salute", "/lint",
           "Verifica wiki/ e management/kanban/. Solo report, non corregge nulla"),
    Azione("Avanzamento sprint", "/sprint-progress",
           "Burndown dello sprint corrente",
           richiede_capability="analytics.sprint_progress"),
    Azione("Chi sta su cosa", "/kanban-status",
           "Coordinamento kanban: chi lavora su cosa e quanta contesa c'e'",
           richiede_capability="kanban_coordination"),
    Azione("Promuovi una pagina", "/promote",
           "Promuove una pagina wiki allo stato successivo",
           conseguenza="Cambia lo `status:` di una pagina della wiki. La modifica viene "
                       "scritta dalla sessione e finisce nella cronologia del repository."),
)


@dataclass
class Turno:
    """Un turno in corso o concluso. La plancia ne tiene UNO alla volta, di proposito:
    due turni paralleli dalla stessa superficie sarebbero due richieste concorrenti
    alla stessa sessione."""

    id: str
    direttiva: str
    avviato_a: float = field(default_factory=time.time)
    concluso: bool = False
    errore: str | None = None


class RuntimeNonDisponibile(RuntimeError):
    """Nessun adapter utilizzabile. Porta con se' la ragione: un comando disabilitato
    senza spiegazione manda a indovinare."""


class Submitter:
    """L'unico percorso di scrittura. Non scrive: chiede alla sessione di scrivere."""

    def __init__(self, root: Path, channel: VisualChannel, *, runtime: Any | None = None,
                 tee: Tee | None = None, timeout_seconds: int = 300) -> None:
        self.root, self.channel = root, channel
        self.timeout_seconds = timeout_seconds
        # Un solo flusso, N consumatori. Il canale audio si registra qui con
        # `tee.aggiungi(...)`: i due canali non hanno due fonti da riconciliare.
        self.tee = tee or Tee(channel)
        self._runtime = runtime
        self._turno: Turno | None = None
        #: Traccia in memoria delle direttive inviate. NON e' l'event store: scriverci
        #: violerebbe US-288, e il record durevole lo produce la sessione quando esegue
        #: la direttiva. Questa e' la risposta alla domanda «cosa ho chiesto io da qui»,
        #: che nessuna altra fonte sa dare perche' la sessione registra l'azione, non
        #: la sua provenienza. Va persa al riavvio, ed e' il prezzo di non scrivere.
        self.storico: list[dict] = []
        self._lock = threading.Lock()
        self._motivo_indisponibile: str | None = None

    # -- disponibilita' -------------------------------------------------------
    def runtime(self) -> Any:
        if self._runtime is not None:
            return self._runtime
        try:
            from voice.config import VoiceConfig
            from voice.runtime.claude_code_adapter import ClaudeCodeAdapter
        except ImportError as mancante:
            self._motivo_indisponibile = f"adapter non importabile: {mancante}"
            raise RuntimeNonDisponibile(self._motivo_indisponibile) from mancante
        try:
            # Si riusa la configurazione del Voice Channel: i due canali parlano allo
            # stesso runtime, quindi devono parlarci con gli stessi parametri —
            # `allowed_tools`, timeout, binario. Una seconda configurazione sarebbe una
            # seconda verita' sullo stesso oggetto, ed e' da li' che nasce la deriva.
            configurazione = VoiceConfig()
            # Stesso adapter, attesa diversa: il default di 120 s e' tarato su una domanda
            # parlata, e una direttiva come `/run` non ci sta dentro — il primo test
            # funzionale e' scaduto esattamente li'. Cambiare il parametro NON e'
            # modificare il Voice Channel: `git diff voice/` resta a zero.
            configurazione.runtime.claude_code_timeout = self.timeout_seconds
            adapter = ClaudeCodeAdapter(configurazione, repo_dir=str(self.root))
            if getattr(adapter, "_startup_error", ""):
                self._motivo_indisponibile = adapter._startup_error
                raise RuntimeNonDisponibile(self._motivo_indisponibile)
            self._runtime = adapter
        except RuntimeNonDisponibile:
            raise
        except Exception as problema:  # noqa: BLE001
            self._motivo_indisponibile = f"adapter non inizializzabile: {problema}"
            raise RuntimeNonDisponibile(self._motivo_indisponibile) from problema
        return self._runtime

    def disponibile(self) -> tuple[bool, str | None]:
        """(scrittura possibile, ragione se no). Fail-closed: in dubbio, no."""
        try:
            self.runtime()
        except RuntimeNonDisponibile as problema:
            return False, str(problema)
        return True, None

    def azioni(self, capability_attive: set[str]) -> list[dict]:
        """Le azioni derivate dalle capability dichiarate, non un elenco fisso."""
        return [a.as_dict() for a in CATALOGO
                if a.richiede_capability is None or a.richiede_capability in capability_attive]

    # -- invio ----------------------------------------------------------------
    def invia(self, direttiva: str, *, conferma: bool = False) -> dict:
        """Manda una direttiva al runtime. Non tocca nessun file della factory."""
        azione = next((a for a in CATALOGO if a.direttiva == direttiva.split()[0]), None)
        if azione and azione.difficile_da_annullare and not conferma:
            return {"stato": "conferma-richiesta", "conseguenza": azione.conseguenza,
                    "direttiva": direttiva}

        ok, ragione = self.disponibile()
        if not ok:
            # Fail-closed in scrittura: si rifiuta dichiarando la ragione, non si prova.
            return {"stato": "non-disponibile", "ragione": ragione}

        with self._lock:
            if self._turno and not self._turno.concluso:
                return {"stato": "occupato", "turno": self._turno.id,
                        "ragione": "un turno e' gia' in corso: la plancia ne tiene uno alla volta"}
            self._turno = Turno(id=str(uuid.uuid4())[:8], direttiva=direttiva)
            turno = self._turno

        self.channel.begin_turn()
        self.storico.append({"turno": turno.id, "direttiva": direttiva,
                             "origine": "canale-visivo", "a": turno.avviato_a})
        del self.storico[:-50]
        threading.Thread(target=self._consuma, args=(turno,), daemon=True).start()
        return {"stato": "avviato", "turno": turno.id, "direttiva": direttiva}

    def _consuma(self, turno: Turno) -> None:
        """Consuma gli eventi del runtime nel canale visivo. Nessuna scrittura su disco."""
        from voice.runtime.factory_runtime import Done, Error

        async def scorri() -> None:
            async for evento in self.runtime().submit(turno.direttiva, turno.id):
                self.tee.dispatch(evento)
                if isinstance(evento, (Done, Error)):
                    turno.errore = getattr(evento, "message", None)
                    turno.concluso = True

        try:
            asyncio.run(scorri())
        except Exception as problema:  # noqa: BLE001
            from voice.runtime.factory_runtime import Error as ErroreRuntime
            self.tee.dispatch(ErroreRuntime(f"{type(problema).__name__}: {problema}"))
            turno.errore, turno.concluso = str(problema), True
        finally:
            turno.concluso = True

    def attivita_del_turno(self, turno: Turno) -> list[dict]:
        """Cosa sta facendo la sessione che esegue la direttiva, adesso.

        Non e' telemetria nuova: e' il transcript che il runtime scrive comunque, e che
        nessuno stava leggendo. Read-only, come tutto il resto.
        """
        try:
            from visual.collectors.sessione import azioni_da, transcript_del_turno
            azioni: list[dict] = []
            for percorso in transcript_del_turno(self.root, turno.avviato_a):
                azioni += azioni_da(percorso, self.root, turno.avviato_a)
            azioni.sort(key=lambda a: a["a"])
            return azioni[-12:][::-1]
        except Exception:  # noqa: BLE001 — il dettaglio e' un di piu', non deve rompere il turno
            return []

    def rispondi(self, testo: str) -> dict:
        """Risponde all'agente: a un `Question` esplicito **o** a un turno concluso.

        **Perche' non basta il `Question`.** Il tipo esiste nel contratto dal 2026-07-08 e
        **nessuno dei sei adapter lo emette**: `grep -c 'yield Question' voice/runtime/*.py`
        da' zero su sei. Una domanda dell'agente arriva dentro il `SpokenSummary` — «Palla
        a te: approvi Wave 1?» — e il turno si chiude come qualunque altro.

        Fino al 2026-09-24 questo metodo rifiutava la risposta con «nessun gate aperto»:
        la domanda finiva in un vicolo cieco, e la plancia diceva «Il lavoro si e' concluso»
        mentre l'agente aspettava. US-289 era verde perche' il suo test usava un runtime
        finto che `Question` lo emetteva — il difetto che questa factory chiama **handle
        falso**, introdotto qui da chi scriveva il test.

        Il rimedio non e' indovinare se la sintesi contenga una domanda: e' **non far
        dipendere la risposta da un evento che nessuno produce**. Si risponde quando c'e'
        un turno concluso, perche' proseguire una conversazione e' sempre legittimo. Il
        `Question` esplicito resta trattato come tale — piu' prominente, con il focus —
        quando un adapter comincera' a emetterlo.
        """
        istantanea = self.channel.snapshot()
        if istantanea.get("question"):
            self.channel.answer_question()
        elif istantanea.get("phase") == "inattivo":
            return {"stato": "nessun-turno",
                    "ragione": "non c'e' nessun turno a cui rispondere: avvia un comando"}
        return self.invia(testo, conferma=True)

    def stato(self) -> dict:
        with self._lock:
            turno = self._turno
        ok, ragione = self.disponibile()
        return {
            "scrittura_disponibile": ok,
            "ragione_indisponibile": ragione,
            "timeout_secondi": self.timeout_seconds,
            "turno_in_corso": None if turno is None or turno.concluso else {
                "id": turno.id, "direttiva": turno.direttiva,
                "da_secondi": round(time.time() - turno.avviato_a, 1),
                # La scadenza e' DICHIARATA mentre si attende, non rivelata quando scatta.
                # Serviva perche' l'adapter non era streaming e fra l'acknowledgment e la
                # fine non arrivava nulla; da TSK-689 gli avanzamenti arrivano, ma la
                # scadenza resta comunque un'informazione che l'utente deve avere PRIMA
                # che scatti, non dopo.
                "scade_fra_secondi": max(0, round(
                    turno.avviato_a + self.timeout_seconds - time.time())),
                # Il dettaglio di cosa sta facendo, letto dal transcript della sessione
                # FIGLIA. Nato perche' il contratto non emetteva `Progress`; da TSK-689
                # `ClaudeCodeAdapter` lo emette, e **questa lettura resta lo stesso** —
                # decisione esplicita, non inerzia:
                #   - vale per i cinque adapter che NON fanno streaming, che altrimenti
                #     tornerebbero alla pagina ferma su una riga;
                #   - da la storia ORDINATA delle azioni, mentre `turn.progress` tiene solo
                #     l'ultima: sono due informazioni diverse, non due copie della stessa;
                #   - non dipende dal formato di output della CLI, che e' cambiato una volta
                #     e puo' cambiare ancora.
                "attivita": self.attivita_del_turno(turno)},
            "storico": self.storico[-10:][::-1],
            "parita": self.tee.stato(),
        }
