"""La sessione VIVA, non lo stato dichiarato (EP-067, correzione del 2026-09-23).

**Perche' esiste.** La plancia si chiamava «attivita' della factory» e mostrava quattro
fonti che cambiano **solo quando qualcuno ci scrive dentro**: event store, kanban, claim,
ledger. Messa alla prova durante una giornata di lavoro reale — 15 commit, 30 TSK creati,
otto difetti riparati — non ha mostrato **niente**: l'event store era fermo a due giorni
prima, perche' nessuno aveva chiamato `record-event.sh`, e i TSK nuovi avevano
`sprint: null`, quindi il pannello dello sprint non li contava.

La pagina non mentiva. Rispondeva a una domanda diversa da quella che il titolo prometteva:
diceva **cosa la factory ha registrato**, non **cosa sta facendo**. Sono due cose, e la
seconda non aveva nessuna fonte.

Questo collettore legge il transcript della sessione di Claude Code — la stessa fonte che
`harvest-session-tokens.py` usa per i token — e ne ricava l'attivita' in corso: quali
strumenti, su quali file, quando. E' **read-only** come tutto il resto, e non e' una
telemetria nuova: e' una fonte gia' scritta dal runtime che nessuno stava guardando.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from visual.collectors.base import Collector, Reading

#: Quanto indietro guardare. Oltre, non e' piu' «adesso».
FINESTRA_S = 3600
#: Quante righe leggere dal fondo. Un transcript di una sessione lunga arriva a centinaia
#: di MB, e leggerlo intero costerebbe piu' della domanda che risponde.
CODA_BYTE = 2_000_000


def _cartella_progetto(root: Path) -> Path:
    """Claude Code sostituisce con `-` sia `/` sia `.` nel percorso assoluto.

    Il punto conta: su una home come `/Users/nome.cognome/...` la cartella e'
    `-Users-nome-cognome-...`. Sostituire solo le barre produce un percorso che non
    esiste, e il collettore direbbe «nessun transcript» su una macchina che ne ha 22.
    """
    mangiato = str(root.resolve()).replace("/", "-").replace(".", "-")
    return Path.home() / ".claude/projects" / mangiato


def azioni_da(percorso: Path, radice: Path, da: float = 0.0) -> list[dict]:
    """Le chiamate a strumenti in un transcript, dalla piu' vecchia. `da` le filtra per ora.

    Estratta come funzione perche' serve a DUE chiamanti: il collettore della sessione
    osservata, e il turno in corso — che ha bisogno di leggere il transcript della sessione
    **figlia**, quella che `claude --print` apre per eseguire la direttiva.
    """
    fuori: list[dict] = []
    try:
        with percorso.open("rb") as fh:
            fh.seek(max(0, percorso.stat().st_size - CODA_BYTE), os.SEEK_SET)
            righe = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return fuori
    if percorso.stat().st_size > CODA_BYTE:
        righe = righe[1:]                      # la prima e' tagliata a meta'

    for riga in righe:
        try:
            voce = json.loads(riga)
        except json.JSONDecodeError:
            continue
        quando = str(voce.get("timestamp", ""))
        try:
            istante = datetime.strptime(
                quando[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        except (ValueError, TypeError):
            istante = 0.0
        if da and istante and istante < da:
            continue
        contenuto = (voce.get("message") or {}).get("content")
        if not isinstance(contenuto, list):
            continue
        for blocco in contenuto:
            if not isinstance(blocco, dict) or blocco.get("type") != "tool_use":
                continue
            ingresso = blocco.get("input") or {}
            bersaglio = (ingresso.get("file_path") or ingresso.get("description")
                         or ingresso.get("pattern") or ingresso.get("command")
                         or ingresso.get("path") or ingresso.get("prompt") or "")
            if isinstance(bersaglio, str) and bersaglio.startswith(str(radice)):
                bersaglio = bersaglio[len(str(radice)) + 1:]
            fuori.append({
                "strumento": blocco.get("name", "?"),
                "su": " ".join(str(bersaglio).split())[:70],
                "a": istante,
            })
    return fuori


def prima_riga_a(percorso: Path) -> float:
    """Quando inizia un transcript. Serve a distinguere una sessione NUOVA da una in corso."""
    try:
        with percorso.open("r", encoding="utf-8", errors="replace") as fh:
            voce = json.loads(fh.readline() or "{}")
        return datetime.strptime(str(voce.get("timestamp", ""))[:19],
                                 "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0.0


def transcript_del_turno(radice: Path, avviato_a: float) -> list[Path]:
    """I transcript aperti DOPO l'inizio del turno: la sessione figlia e i suoi subagenti.

    L'adapter invoca `claude --print`, che apre una sessione propria e le scrive un
    transcript nuovo. Quella sessione e' l'unica fonte di dettaglio mentre il turno gira —
    il contratto non emetteva `Progress` (TSK-689 lo ha reso emesso da `ClaudeCodeAdapter`,
    ma gli altri cinque adapter restano non-streaming) — e prima di
    questa funzione nessuno la leggeva: la pagina diceva «sto consultando la factory...»
    per tre minuti e nient'altro.
    """
    cartella = _cartella_progetto(radice)
    if not cartella.is_dir():
        return []
    candidati = list(cartella.glob("*.jsonl")) + list(cartella.glob("subagents/*.jsonl"))
    # `margine`: un transcript aperto un istante prima del turno e' comunque suo.
    margine = avviato_a - 5
    return sorted((f for f in candidati
                   if f.stat().st_mtime >= margine and prima_riga_a(f) >= margine),
                  key=lambda f: f.stat().st_mtime)


class SessioneCollector(Collector):
    key = "sessione"
    source = "~/.claude/projects/<progetto>/*.jsonl"
    titolo = "Sessione in corso"
    descrizione = "Cosa sta facendo l'agente adesso, dal transcript del runtime."
    deadline_seconds = 2.0
    refresh_seconds = 4.0     # il transcript cresce di continuo: rileggerlo costa

    def collect(self) -> list[Reading]:
        cartella = _cartella_progetto(self.root)
        if not cartella.is_dir():
            return [Reading.unavailable(
                self.key, self.source,
                "nessun transcript per questo progetto: il runtime non li scrive qui, "
                "oppure la plancia osserva una radice diversa da quella della sessione",
                label="Sessione in corso")]

        trascritti = sorted(cartella.glob("*.jsonl"), key=lambda p: p.stat().st_mtime,
                            reverse=True)
        if not trascritti:
            return [Reading.unavailable(self.key, self.source,
                                        "cartella presente ma nessun transcript dentro",
                                        label="Sessione in corso")]

        vivo = trascritti[0]
        adesso = time.time()
        # Un transcript fermo da un'ora non e' «la sessione in corso»: e' l'ultima che c'e'
        # stata, e dirlo e' diverso da mostrarla come se fosse viva.
        eta_file = adesso - vivo.stat().st_mtime

        with vivo.open("rb") as fh:
            fh.seek(max(0, vivo.stat().st_size - CODA_BYTE), os.SEEK_SET)
            righe = fh.read().decode("utf-8", errors="replace").splitlines()[1:]

        strumenti: Counter[str] = Counter()
        file_toccati: Counter[str] = Counter()
        recenti: list[dict] = []
        ultimo_ts = 0.0

        for riga in righe:
            try:
                voce = json.loads(riga)
            except json.JSONDecodeError:
                continue
            # I timestamp del transcript sono UTC. `time.mktime` li interpreterebbe come
            # ora LOCALE, e su CEST il risultato e' un dato «di 2 ore fa» accanto a uno
            # stato «attiva»: due affermazioni che si contraddicono nella stessa riga.
            quando = voce.get("timestamp", "")
            try:
                istante = datetime.strptime(
                    quando[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            except (ValueError, TypeError):
                istante = 0.0
            ultimo_ts = max(ultimo_ts, istante)

            contenuto = (voce.get("message") or {}).get("content")
            if not isinstance(contenuto, list):
                continue
            for blocco in contenuto:
                if not isinstance(blocco, dict) or blocco.get("type") != "tool_use":
                    continue
                nome = blocco.get("name", "?")
                strumenti[nome] += 1
                ingresso = blocco.get("input") or {}
                bersaglio = (ingresso.get("file_path") or ingresso.get("path")
                             or ingresso.get("pattern") or ingresso.get("description") or "")
                if isinstance(bersaglio, str) and bersaglio.startswith(str(self.root)):
                    bersaglio = bersaglio[len(str(self.root)) + 1:]
                if bersaglio:
                    file_toccati[str(bersaglio)[:70]] += 1
                recenti.append({"strumento": nome, "su": str(bersaglio)[:54]})

        # `data_at` e' il momento dell'ULTIMA attivita', non della lettura: e' la
        # distinzione che mancava e per cui un event store fermo da due giorni compariva
        # come «letto 0 s fa».
        datato = ultimo_ts or vivo.stat().st_mtime
        stato = ("attiva" if eta_file < 120 else
                 "in pausa" if eta_file < FINESTRA_S else "conclusa")

        return [
            Reading.ok("sessione.stato", stato, self.source, label="Stato",
                       data_at=datato, file=vivo.name[:8]),
            Reading.ok("sessione.strumenti", dict(strumenti.most_common(6)), self.source,
                       label="Strumenti usati", data_at=datato,
                       vuoto="nessuno strumento nella finestra"),
            Reading.ok("sessione.chiamate", sum(strumenti.values()), self.source,
                       unit="chiamate", label="Chiamate a strumenti", data_at=datato),
            Reading.ok("sessione.file", dict(file_toccati.most_common(8)), self.source,
                       label="Oggetti piu' toccati", data_at=datato,
                       vuoto="nessun file nella finestra"),
            Reading.ok("sessione.recenti", recenti[-10:][::-1], self.source,
                       unit="azioni", label="Ultime azioni", data_at=datato,
                       vuoto="nessuna azione nella finestra"),
        ]
