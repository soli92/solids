"""Servizio locale della plancia (US-279). Solo stdlib.

Nessun file di lock, nessuno stato su disco: il processo E' lo stato. Un `kill -9`
non lascia niente da ripulire, e il riavvio immediato riesce — che e' un criterio di
accettazione, non una comodita'.

Il legame col resto: `visual.channel` rende il contratto `FactoryRuntime`,
`visual.collectors` legge le fonti gia' esistenti. Questo modulo li serve e basta.
"""
from __future__ import annotations

import concurrent.futures
import json
import signal
import re
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from visual import PATTERN_VERSION_EXPECTED, __version__
from visual.channel import VisualChannel
from visual.collectors.base import Reading
from visual.collectors.cost_alert import CostAlertCollector
from visual.collectors.coordinamento import CoordinamentoCollector, vista_corrente
from visual.collectors.events import EventStoreCollector
from visual.collectors.kanban import SprintCollector
from visual.collectors.sessione import SessioneCollector
from visual.collectors.sessions import SessionCollector
from visual.collectors.tokens import TokenLedgerCollector
from visual.config import VisualConfig
from visual.submit import Submitter
from visual.voce import CanaleVocale

# L'ordine e' quello delle domande, dalla piu' urgente: «cosa sta succedendo adesso»
# viene prima di «cosa e' stato registrato». Per una giornata intera la plancia non aveva
# la prima, e mostrava la seconda ferma a due giorni prima.
COLLECTORS = (SessioneCollector, EventStoreCollector, SprintCollector,
              CoordinamentoCollector, SessionCollector, TokenLedgerCollector,
              CostAlertCollector)
STATIC = Path(__file__).parent / "static"
PORT_SEARCH = 20


def free_port(host: str, start: int, span: int = PORT_SEARCH) -> int | None:
    """Prima porta libera da `start`. `None` se nessuna nella finestra."""
    for port in range(start, start + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
                return port
            except OSError:
                continue
    return None


class PortBusy(RuntimeError):
    """La porta e' occupata. Porta l'alternativa con se': un errore che non propone
    un rimedio costringe l'utente a cercarlo, ed e' esattamente cio' che US-279
    chiede di non fare."""

    def __init__(self, host: str, port: int, alternative: int | None) -> None:
        self.host, self.port, self.alternative = host, port, alternative
        if alternative:
            super().__init__(f"la porta {port} e' occupata; la {alternative} e' libera — "
                             f"riavvia con --port {alternative}")
        else:
            super().__init__(f"la porta {port} e' occupata e nessuna libera fra "
                             f"{port} e {port + PORT_SEARCH}")


class Plancia:
    """Stato osservabile. Non scrive nulla, da nessuna parte."""

    def __init__(self, root: Path, config: VisualConfig) -> None:
        self.root, self.config = root, config
        self.channel = VisualChannel()
        self.started_at = datetime.now(timezone.utc)
        # Executor di lunga vita, MAI dentro un `with`. Uscire da un blocco `with`
        # chiama `shutdown(wait=True)`, che attende ogni future ancora in corso: la
        # scadenza per collettore diventava allora puramente decorativa, perche' la
        # richiesta si bloccava comunque fino alla fine della lettura piu' lenta.
        # Qui una lettura in ritardo continua in sottofondo e il suo esito e'
        # scartato; la richiesta successiva ne avvia una nuova. Non puo' accumularsi
        # senza limite: l'unico collettore che esce dal processo ha un timeout proprio.
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=len(COLLECTORS) * 3, thread_name_prefix="plancia-lettura")
        self._cache: dict[str, list] = {}      # ultima lettura riuscita, per collettore
        self._pendenti: dict[str, concurrent.futures.Future] = {}
        self.submitter = Submitter(root, self.channel,
                                   timeout_seconds=config.runtime_timeout_seconds)
        # Il canale vocale e' un SECONDO CONSUMATORE dello stesso flusso, non un secondo
        # sistema: si registra sul Tee costruito per la parita' (US-295). Registrato
        # sempre, attivo solo su richiesta — a canale spento `consume()` filtra e basta,
        # e continua a contare gli artefatti che non ha pronunciato.
        self.voce = CanaleVocale(root)
        self.submitter.tee.aggiungi(self.voce)

    def capability_attive(self) -> set[str]:
        """I blocchi di `factory.config.yaml` con `enabled: true`. Le azioni della
        plancia si derivano da qui e non da un elenco scritto a mano (US-290 AC1):
        accendere una capability la fa comparire senza toccare la plancia."""
        testo = (self.root / "factory.config.yaml").read_text(encoding="utf-8", errors="replace")
        attive, blocco = set(), None
        for riga in testo.splitlines():
            if riga[:1].isalpha():
                blocco = riga.split(":")[0]
            elif blocco and re.match(r"\s+enabled:\s*true", riga):
                attive.add(blocco)
            elif blocco and re.match(r"\s+[a-z_]+:\s*$", riga):
                pass
        # sotto-blocchi nella forma `padre.figlio` usati dal catalogo
        for padre, figlio in re.findall(r"^([a-z_]+):[\s\S]{0,4000}?\n  ([a-z_]+):\n    enabled: true",
                                        testo, re.M):
            attive.add(f"{padre}.{figlio}")
        return attive

    def concorrenza(self) -> dict:
        """US-291 — rileva un'altra sessione attiva sullo stesso repo e la DICHIARA.

        Non arbitra: nessun lock, nessun lease, nessun tentativo di risolvere la
        contesa. E' la posizione che EP-064 ha raggiunto sul kanban dopo averne
        misurato il costo, e qui non si ri-delibera. La visibilita' e' al ciclo di
        scrittura del file dei claim: **minuti, non secondi**, e viene dichiarato.
        """
        from visual.collectors.sessions import SessionCollector
        letture = SessionCollector(self.root).read()
        prima = letture[0]
        if not prima.available:
            return {"altre_sessioni": None, "osservabile": False, "ragione": prima.reason,
                    "arbitra": False}
        voci = prima.value if isinstance(prima.value, list) else []
        return {
            "altre_sessioni": len(voci),
            "osservabile": True,
            "voci": voci,
            "eta_osservazione_s": round(prima.age_seconds(), 1),
            "arbitra": False,
            "avvertenza": (
                f"{len(voci)} altra/e sessione/i risultano attive su questo repo. "
                "La plancia NON impedisce il conflitto e NON garantisce alcuna latenza: "
                "la visibilita' e' al ciclo di scrittura dei claim, quindi minuti."
            ) if voci else None,
        }

    def identity(self) -> dict:
        expected = PATTERN_VERSION_EXPECTED
        actual = self.config.pattern_version or "?"
        return {
            "plancia_version": __version__,
            "pattern_version": actual,
            "pattern_version_expected": expected,
            "pattern_version_drift": bool(actual and actual != expected),
            "root": str(self.root),
            "started_at": self.started_at.isoformat(),
            "stale_after_seconds": self.config.stale_after_seconds,
            "read_only": True,
        }

    def observe(self) -> dict:
        """Legge tutte le fonti IN PARALLELO, ciascuna con la propria scadenza.

        Sequenziale era sbagliato in modo non ovvio: `visual.collectors.tokens` lancia
        un sottoprocesso, e finche' quello non rispondeva la pagina restava vuota —
        tutti e quattro i riquadri fermi per colpa di uno. «Un collettore rotto non
        abbatte gli altri» (US-281 AC3) vale anche quando il guasto e' la lentezza.
        """
        stale = self.config.stale_after_seconds
        collettori = [factory(self.root) for factory in COLLECTORS]
        inizio = time.monotonic()

        # Le fonti costose non si rileggono a ogni ciclo: si serve l'ultima lettura
        # riuscita, con la sua eta' vera. Mentirebbe solo se `Reading` non portasse
        # `observed_at` — e lo porta, quindi la vista la marca stantia da sola.
        lavori = []
        for c in collettori:
            # Raccolta del ritardatario: una lettura che aveva sforato la scadenza al
            # giro precedente e' intanto finita. Scartarla significherebbe ripagarla
            # ogni volta e non mostrarla mai — che e' esattamente come si comportava
            # il ledger dei token: lento a intermittenza, quindi «non osservabile» a
            # intermittenza, cioe' il peggiore dei due esiti.
            tardiva = self._pendenti.get(c.key)
            if tardiva is not None and tardiva.done():
                del self._pendenti[c.key]
                try:
                    esito = tardiva.result()
                    if any(r.available for r in esito):
                        self._cache[c.key] = esito
                except Exception:      # noqa: BLE001 — un guasto tardivo resta un dato
                    pass

            fresca = self._cache.get(c.key)
            if tardiva is not None and not tardiva.done():
                lavori.append((c, None))          # gia' in volo: non se ne avvia un'altra
            elif c.refresh_seconds and fresca and fresca[0].age_seconds() < c.refresh_seconds:
                lavori.append((c, None))
            else:
                lavori.append((c, self._pool.submit(c.read)))

        panels: list[dict] = []
        for collector, lavoro in lavori:                      # ordine = ordine di COLLECTORS
            if lavoro is None:
                letture = self._cache.get(collector.key) or [Reading.unavailable(
                    collector.key, collector.source,
                    "prima lettura in corso: il valore comparira' al prossimo aggiornamento")]
            else:
                # Scadenza INDIVIDUALE, misurata dall'inizio comune: un collettore
                # paziente non impone la propria attesa agli altri. Con la scadenza
                # condivisa, una fonte da 0,5 s aspettava i 4 s del vicino piu' lento.
                resta = max(0.0, inizio + collector.deadline_seconds - time.monotonic())
                try:
                    letture = lavoro.result(timeout=resta)
                    if any(r.available for r in letture):
                        self._cache[collector.key] = letture
                except concurrent.futures.TimeoutError:
                    # Non si butta: il future resta in volo e al giro dopo lo si raccoglie.
                    self._pendenti[collector.key] = lavoro
                    letture = self._cache.get(collector.key) or [Reading.unavailable(
                        collector.key, collector.source,
                        f"lettura in corso da oltre {collector.deadline_seconds:.1f}s: "
                        f"comparira' al prossimo aggiornamento")]
            readings = [r.as_dict(stale) for r in letture]
            panels.append({
                "key": collector.key,
                "titolo": collector.titolo,
                "descrizione": collector.descrizione,
                "source": collector.source,
                # Osservabile se ALMENO una lettura lo e'. Fail-open in lettura.
                "observable": any(r["available"] for r in readings),
                "readings": readings,
            })
        return {
            "identity": self.identity(),
            "panels": panels,
            "turn": self.channel.snapshot(),
            "scrittura": {**self.submitter.stato(),
                          "azioni": self.submitter.azioni(self.capability_attive())},
            "concorrenza": self.concorrenza(),
            "voce": self.voce.stato().as_dict(),
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = f"plancia/{__version__}"
    plancia: Plancia = None  # type: ignore[assignment]

    def log_message(self, fmt: str, *args) -> None:  # silenzio: l'accesso non e' un dato
        pass

    def _send(self, code: int, body: bytes, mime: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, code: int = 200) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False, default=str).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 — firma imposta da BaseHTTPRequestHandler
        route = self.path.split("?")[0].rstrip("/") or "/"
        if route == "/api/state":
            return self._json(self.plancia.observe())
        if route == "/api/identity":
            return self._json(self.plancia.identity())
        if route == "/healthz":
            return self._send(200, b"ok", "text/plain; charset=utf-8")
        if route == "/coordinamento/vista":
            # La pagina prodotta dal motore all'ultima misura riuscita, servita cosi' com'e':
            # e' autosufficiente e i suoi numeri sono gli stessi del riquadro. Mai una vista
            # di una misura precedente a uno scostamento L0: `vista_corrente` legge solo
            # l'esito dell'ultima impronta.
            vista = vista_corrente(self.plancia.root)
            if vista is None:
                return self._send(404, "nessuna vista del coordinamento: il riquadro "
                                  "dichiara perche'".encode(), "text/plain; charset=utf-8")
            return self._send(200, vista.read_bytes(), "text/html; charset=utf-8")

        name = "index.html" if route == "/" else route.lstrip("/")
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            return self._send(404, b"non trovato", "text/plain; charset=utf-8")
        mime = {"html": "text/html", "css": "text/css", "js": "text/javascript"}.get(
            target.suffix.lstrip("."), "application/octet-stream")
        self._send(200, target.read_bytes(), f"{mime}; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        """Tre verbi, e tutti e tre finiscono in `FactoryRuntime.submit()`.

        Nessuno di essi tocca un file della factory: la plancia CHIEDE alla sessione di
        agire, non agisce. E' il vincolo di US-288, verificato dall'AST e non affidato a
        questo commento.
        """
        route = self.path.split("?")[0].rstrip("/") or "/"

        if route == "/api/voce":
            # Accendere un sintetizzatore non e' scrivere sullo stato della factory:
            # e' il ciclo di vita di un consumatore locale. US-288 resta intatta.
            lunghezza = int(self.headers.get("Content-Length") or 0)
            try:
                corpo = json.loads(self.rfile.read(lunghezza) or b"{}")
            except json.JSONDecodeError:
                return self._json({"errore": "corpo non JSON"}, 400)
            voce = self.plancia.voce
            esito = voce.attiva() if corpo.get("attiva") else voce.disattiva()
            return self._json(esito, 200 if esito.get("disponibile") else 503)

        if route not in {"/api/invia", "/api/rispondi"}:
            return self._json({"errore": f"nessun verbo di scrittura su {route}"}, 404)

        lunghezza = int(self.headers.get("Content-Length") or 0)
        if lunghezza > 64_000:
            return self._json({"errore": "richiesta troppo grande"}, 413)
        try:
            corpo = json.loads(self.rfile.read(lunghezza) or b"{}")
        except json.JSONDecodeError:
            return self._json({"errore": "corpo non JSON"}, 400)

        testo = str(corpo.get("testo") or "").strip()
        if not testo:
            return self._json({"errore": "campo `testo` mancante o vuoto"}, 400)

        submitter = self.plancia.submitter
        esito = (submitter.rispondi(testo) if route == "/api/rispondi"
                 else submitter.invia(testo, conferma=bool(corpo.get("conferma"))))
        codici = {"conferma-richiesta": 409, "non-disponibile": 503, "occupato": 409,
                  "nessun-gate": 409}
        return self._json(esito, codici.get(esito["stato"], 202))


def build(root: Path, config: VisualConfig) -> tuple[ThreadingHTTPServer, Plancia]:
    port = config.port
    if free_port(config.host, port, 1) is None:
        raise PortBusy(config.host, port, free_port(config.host, port + 1))
    plancia = Plancia(root, config)
    handler = type("BoundHandler", (Handler,), {"plancia": plancia})
    server = ThreadingHTTPServer((config.host, port), handler)
    server.daemon_threads = True   # nessun thread sopravvive all'arresto
    return server, plancia


def serve(root: Path, config: VisualConfig) -> None:
    """Avvia, serve, e rilascia la porta su Ctrl-C **o su SIGTERM**.

    Tre difetti trovati facendola girare davvero, non in un test:

    1. `print()` su stdout rediretto e' bufferizzato, quindi l'indirizzo non compariva
       mai quando la plancia veniva avviata in background — che e' il modo normale di
       avviarla. `flush=True` ovunque.

    2. Si gestiva solo `KeyboardInterrupt`. Un `kill` ordinario (SIGTERM) lasciava la
       porta occupata, e il test in-process non poteva accorgersene perche' chiamava
       `shutdown()` direttamente invece di inviare un segnale.

    3. I gestori si installavano **dopo** `build()`, cioe' dopo che il socket era gia'
       in ascolto. Fra il `bind` e l'installazione c'era una finestra di millisecondi in
       cui un SIGTERM trovava il comportamento predefinito di Python e **uccideva** il
       processo: uscita `-15` invece di `0`, niente «porta rilasciata», nessuno shutdown
       pulito. Si vedeva come un test intermittente al 25%, e la porta si liberava lo
       stesso — la libera il sistema operativo — quindi l'unico sintomo era il codice di
       uscita. Ora i gestori si installano **prima** di aprire il socket: non esiste piu'
       un istante in cui la plancia e' raggiungibile e non sa morire.
    """
    say = lambda line: print(line, flush=True)  # noqa: E731
    fermati = threading.Event()

    def congeda(signum, _frame):
        say(f"\n  segnale {signal.Signals(signum).name}, arresto…")
        fermati.set()

    # PRIMA del bind: vedi il punto 3 del docstring.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, congeda)

    server, plancia = build(root, config)
    identity = plancia.identity()
    say(f"  plancia {identity['plancia_version']} · pattern {identity['pattern_version']} · sola lettura")
    if identity["pattern_version_drift"]:
        say(f"  ATTENZIONE: plancia attesa su pattern {identity['pattern_version_expected']}, "
            f"la factory dichiara {identity['pattern_version']}")
    say(f"  in ascolto su {config.address}    (Ctrl-C per arrestare)")

    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # wait() invece di join(): un Event si sveglia dal gestore di segnale,
        # un join() su un thread daemon no.
        while not fermati.wait(0.25):
            pass
    except KeyboardInterrupt:   # se il gestore non e' installabile (thread non principale)
        say("\n  arresto…")
    finally:
        server.shutdown()
        server.server_close()
        say("  porta rilasciata.")
