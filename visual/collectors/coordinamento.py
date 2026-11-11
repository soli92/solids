"""Report PM del coordinamento — riuso di `tools/coordinamento/run.py` (EP-070).

Il motore esistente e' l'unico autore dei numeri: qui lo si invoca, non lo si riscrive.
Ogni numero che arriva in pagina e' gia' passato dalla verifica L0 — la seconda
implementazione indipendente che `run.py` esegue prima di produrre il RIEPILOGO. Se L0
trova uno scostamento il motore esce con 1, e il riquadro dice «nessun numero mostrato»
invece di mostrare l'ultimo buono come se fosse attuale.

**Perche' non a ogni ciclo.** La pipeline costa secondi (misurato: 4,5 s sul working
tree, 12 s su un commit, kanban di questa factory). Rilanciarla ogni 5 s significherebbe
pagarla per sempre, per un numero che cambia alla velocita' di un `status:` modificato.
Si rilancia quando cambia l'**impronta** di cio' che il motore legge — HEAD, i file del
kanban, la config dell'operatore, lo store, `factory.config.yaml`, la data — e fra un
cambiamento e l'altro si riusa l'ultima misura, ridatata: la LETTURA e' fresca (l'impronta
e' stata appena verificata), il DATO porta l'eta' della sua fonte.

**Dove scrive il motore.** `run.py` produce snapshot, misura e vista HTML in una cartella
di uscita. La plancia gli passa una cartella **temporanea fuori dal repo**: nessun file
della factory cambia, nemmeno in `deliverables/` (gitignored, ma della factory). E' lo
stesso confine del ledger dei token: il sottoprocesso e' uno strumento della factory con
le proprie uscite, la plancia ne legge l'esito.

**Cosa non vede.** Il lavoro di un'altra sessione compare solo quando arriva in questo
working tree (o in HEAD, con `fonte: commit`): la visibilita' e' al ciclo di push, quindi
minuti — come per tutto il coordinamento kanban (EP-064).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import date
from pathlib import Path

from visual.collectors.base import Collector, Reading

#: Il commit puo' costare 12 s su questo kanban, e cresce col kanban. Il margine e'
#: largo perche' un timeout prematuro produrrebbe un riquadro «non osservabile» a
#: intermittenza, che e' peggio di uno lento.
TIMEOUT = 90
RUN_PY = "tools/coordinamento/run.py"
CONFIG_DIR = "analytics/coordinamento"
FONTI = ("worktree", "commit")

# Lo stato vive nel MODULO, non nell'istanza: `Plancia.observe()` costruisce collettori
# nuovi a ogni ciclo, e un'impronta tenuta su `self` si perderebbe ogni 5 s — cioe' la
# pipeline ripartirebbe sempre, che e' esattamente cio' che l'impronta esiste per evitare.
_LOCK = threading.Lock()
_ESECUZIONE = threading.Lock()
_ULTIMO: dict[str, dict] = {}


def cartella_uscite(root: Path) -> Path:
    """Cartella temporanea per root, fuori dal repo. Non la crea: la crea `run.py`."""
    base = (os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP")
            or "/tmp")
    impronta = hashlib.sha1(str(root.resolve()).encode("utf-8")).hexdigest()[:10]
    return Path(base) / f"plancia-coordinamento-{impronta}"


def vista_corrente(root: Path) -> Path | None:
    """La vista HTML dell'ultima misura riuscita, se esiste ancora ed e' nostra."""
    with _LOCK:
        esito = (_ULTIMO.get(str(root.resolve())) or {}).get("esito") or {}
    html = (esito.get("riepilogo") or {}).get("html")
    if not html:
        return None
    percorso = Path(html).resolve()
    if cartella_uscite(root).resolve() not in percorso.parents or not percorso.is_file():
        return None
    return percorso


def _git(root: Path, *args: str) -> str:
    fatto = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           timeout=10, stdin=subprocess.DEVNULL)
    return fatto.stdout.strip() if fatto.returncode == 0 else ""


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


class CoordinamentoCollector(Collector):
    key = "coordinamento"
    titolo = "Avanzamento delle attivita'"
    descrizione = ("Report PM del coordinamento: avanzamento per obiettivo ed epica, calcolato "
                   "dal motore e ricontrollato dalla verifica L0. Si aggiorna quando cambia il "
                   "kanban locale; il lavoro di altre sessioni compare al ciclo di push, quindi "
                   "in minuti.")
    source = RUN_PY
    deadline_seconds = 1.0
    #: Ogni quanto si ricontrolla l'IMPRONTA — costo di qualche decina di millisecondi.
    #: La pipeline vera parte solo se l'impronta e' cambiata.
    refresh_seconds = 15.0

    # -- risoluzione -----------------------------------------------------------
    def _impostazioni(self) -> tuple[Path | None, str, str | None]:
        """(config dell'operatore, fonte, ragione se la config manca)."""
        from visual.config import load
        cfg = load(self.root)
        fonte = cfg.coordinamento_fonte if cfg.coordinamento_fonte in FONTI else "worktree"
        if cfg.coordinamento_config:
            percorso = (self.root / cfg.coordinamento_config).resolve()
            if not percorso.is_file():
                return None, fonte, (f"visual_channel.coordinamento.config indica "
                                     f"{cfg.coordinamento_config}, che non esiste")
            return percorso, fonte, None
        operatore = _git(self.root, "config", "user.name")
        if operatore:
            candidata = self.root / CONFIG_DIR / f"config-{operatore}.json"
            if candidata.is_file():
                return candidata, fonte, None
        return None, fonte, (
            f"nessuna config operatore: copia {CONFIG_DIR}/config-esempio.json in "
            f"{CONFIG_DIR}/config-{operatore or '<operatore>'}.json, oppure indicala in "
            f"visual_channel.coordinamento.config")

    def _impronta(self, config: Path, fonte: str) -> tuple:
        """Tutto cio' che, cambiando, cambia la misura. Solo `stat`, nessuna lettura."""
        try:
            kanban_root = json.loads(config.read_text(encoding="utf-8")).get(
                "kanban_root", "management/kanban")
        except (OSError, json.JSONDecodeError):
            kanban_root = "management/kanban"
        kanban = None
        if fonte == "worktree":
            # Conteggio E massimo: una cancellazione abbassa il conteggio anche quando il
            # file piu' recente resta lo stesso.
            tempi = [_mtime(p) for p in (self.root / kanban_root).rglob("*.md")]
            kanban = (len(tempi), max(tempi, default=0))
        operatore = config.stem.removeprefix("config-")
        store = self.root / CONFIG_DIR / operatore / "da_assegnare.yaml"
        return (fonte, _git(self.root, "rev-parse", "HEAD"), kanban, _mtime(config),
                _mtime(store), _mtime(self.root / "factory.config.yaml"),
                date.today().isoformat())

    # -- esecuzione ------------------------------------------------------------
    def _esegui(self, config: Path, fonte: str, impronta: tuple) -> dict:
        motore = self.root / RUN_PY
        if not motore.is_file():
            return {"ragione": f"{RUN_PY} non presente in questa factory"}
        comando = [sys.executable, str(motore), "--config", str(config),
                   "--uscite", str(cartella_uscite(self.root)), "--fonte", fonte]
        try:
            fatto = subprocess.run(comando, capture_output=True, text=True, timeout=TIMEOUT,
                                   cwd=str(self.root), stdin=subprocess.DEVNULL,
                                   encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            return {"ragione": f"il motore non ha risposto entro {TIMEOUT}s"}

        righe = (fatto.stdout or "").splitlines()
        stop = next((r for r in reversed(righe) if r.startswith("STOP")), None)
        if fatto.returncode != 0:
            if stop and "verifica_l0" in stop:
                return {"ragione": "la verifica L0 ha trovato uno scostamento fra motore e "
                                   "ricalcolo: nessun numero mostrato"}
            errore = (fatto.stderr or "").strip().splitlines()
            dettaglio = stop or (errore[-1] if errore else "nessun messaggio")
            return {"ragione": f"il motore e' uscito con {fatto.returncode}: {dettaglio}"}
        if stop:   # gate pm_report spento: exit 0 e nessuna uscita
            return {"ragione": stop.removeprefix("STOP:").strip()}
        riga = next((r for r in reversed(righe) if r.startswith("RIEPILOGO ")), None)
        if riga is None:
            return {"ragione": "il motore non ha prodotto il RIEPILOGO"}
        try:
            riepilogo = json.loads(riga.removeprefix("RIEPILOGO "))
        except json.JSONDecodeError:
            return {"ragione": "RIEPILOGO del motore non leggibile come JSON"}

        if fonte == "worktree":
            data_at = (impronta[2][1] / 1e9) if impronta[2] and impronta[2][1] else None
        else:
            quando = _git(self.root, "log", "-1", "--format=%ct", riepilogo["kanban_commit"])
            data_at = float(quando) if quando.isdigit() else None
        return {"riepilogo": riepilogo, "data_at": data_at, "misurato_at": time.time()}

    def collect(self) -> list[Reading]:
        config, fonte, ragione = self._impostazioni()
        if config is None:
            return [Reading.unavailable(self.key, self.source, ragione or "config assente")]
        impronta = self._impronta(config, fonte)
        chiave = str(self.root.resolve())
        # Due lock, non uno. `_ESECUZIONE` serializza la pipeline: due schede aperte non
        # devono lanciarne due sulla stessa impronta, e la seconda trova la misura pronta.
        # `_LOCK` protegge solo il dizionario: se coprisse anche l'esecuzione, la rotta
        # della vista resterebbe appesa per tutti i secondi di una misura in corso.
        with _ESECUZIONE:
            with _LOCK:
                ultimo = _ULTIMO.get(chiave)
            if ultimo is None or ultimo["impronta"] != impronta:
                ultimo = {"impronta": impronta, "esito": self._esegui(config, fonte, impronta)}
                with _LOCK:
                    _ULTIMO[chiave] = ultimo
        esito = ultimo["esito"]
        if "riepilogo" not in esito:
            return [Reading.unavailable(self.key, self.source, esito["ragione"])]
        return self._letture(esito, config, fonte)

    # -- resa ------------------------------------------------------------------
    def _letture(self, esito: dict, config: Path, fonte: str) -> list[Reading]:
        r, data_at = esito["riepilogo"], esito["data_at"]
        fonte_letta = f"{RUN_PY} --config {config.name} --fonte {fonte}"
        pct = lambda v: "non misurato" if v is None else f"{v}%"  # noqa: E731

        obiettivi, epiche, avvisi = [], [], []
        for o in r.get("obiettivi", []):
            obiettivi.append({
                "obiettivo": o["nome"],
                "avanzamento": (pct(o.get("avanzamento_pct")) if o.get("misurato")
                                else "non misurato"),
                "scadenza": o.get("data_target") or "—",
                "giorni lavorativi rimasti": o.get("giorni_lavorativi_rimasti", "—"),
                "avvisi": len(o.get("avvisi", [])),
            })
            for e in o.get("epiche", []):
                epiche.append({
                    "epica": e["id"], "obiettivo": o["nome"],
                    "fatti": f"{e['fatto']} su {e['base']}", "avanzamento": pct(e.get("pct")),
                    "in attesa di prerequisito": e.get("in_attesa_prerequisito", 0),
                    "chiusi senza esito": e.get("chiusi_senza_esito", 0),
                })
            for a in o.get("avvisi", []):
                avvisi.append({"obiettivo": o["nome"], "livello": a.get("livello", "—"),
                               "avviso": a.get("testo", a.get("codice", "—"))})

        provenienza = {
            "commit misurato": r.get("kanban_commit", "?"),
            "fonte": "working tree (anche non committato)" if fonte == "worktree" else "commit",
            "file del kanban non committati": r.get("non_committati", 0),
            "commit non pushati": r.get("non_pushati", 0),
            "verifica L0": "superata",
        }
        qualita = {
            "voci di config non allineate": r.get("config_non_allineata", 0),
            "TSK illeggibili": r.get("tsk_illeggibili", 0),
            "anomalie del dato": r.get("qualita_dato", 0),
        }
        comune = {"data_at": data_at}
        return [
            Reading.ok("coordinamento.obiettivi", obiettivi, fonte_letta, unit="obiettivi",
                       singolare="obiettivo", righe=None, label="Avanzamento per obiettivo",
                       vuoto="nessun obiettivo in config", **comune),
            Reading.ok("coordinamento.epiche", epiche, fonte_letta, unit="epiche",
                       singolare="epica", righe=None, label="Avanzamento per epica",
                       vuoto="nessuna epica misurata nel perimetro", **comune),
            Reading.ok("coordinamento.avvisi", avvisi, fonte_letta, unit="avvisi",
                       singolare="avviso", righe=None, label="Avvisi dalle regole",
                       vuoto="nessun avviso dalle regole", **comune),
            Reading.ok("coordinamento.provenienza", provenienza, fonte_letta,
                       label="Provenienza della misura", **comune),
            Reading.ok("coordinamento.qualita", qualita, fonte_letta,
                       label="Qualita' del dato", **comune),
            Reading.ok("coordinamento.vista", "Apri il report completo", fonte_letta,
                       label="Report completo", href="/coordinamento/vista", **comune),
        ]
