"""
student_model.py — StudentModel (TSK-357, TSK-358, TSK-359, EP-045 US-162)

Gestisce il ciclo di vita del modello dello studente:
  - caricamento e salvataggio su JSON (persistenza cross-sessione, AC1)
  - lettura e aggiornamento dei nodi di competenza
  - ordinamento topologico del DAG dei prerequisiti con Kahn's algorithm (AC4)
  - spaced repetition SM-2 semplificato: schedule_next_review() (TSK-358, AC6)
  - provenance e staleness: update_provenance(), check_staleness(),
    compute_content_hash() (TSK-359, AC3)

Dipendenze: solo stdlib Python 3.10+ (json, pathlib, datetime, collections, hashlib).
Scrittura atomica: write su file temporaneo (.tmp), poi rename — evita corruzione.

Schema JSON: conforme a wiki/concepts/student-model-schema.md (TSK-356).
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

# Spaced repetition — SM-2 semplificato (TSK-358)
MAX_INTERVAL_DAYS = 30   # cap superiore all'intervallo di ripasso (SR-2)
RESET_INTERVAL_DAYS = 1  # intervallo di reset su risposta errata (SR-3)

# Default nodo conforme allo schema TSK-356
DEFAULT_NODE: dict[str, Any] = {
    "mastery": 0.0,
    "confidence": 0.0,
    "errors": [],
    "misconceptions": [],
    "next_review": None,  # schedulato da TSK-358
    "source_ref": {"path": "", "version_hash": ""},
    "is_stale": False,
    "prerequisite_ids": [],
}


class StudentModel:
    """Modello persistente di competenze dello studente su DAG.

    Il modello viene serializzato in ``memory/student-model.json`` (o in un
    path alternativo) al termine di ogni sessione e ricaricato all'inizio
    della successiva.  Ogni nodo rappresenta una competenza con i campi
    definiti in ``DEFAULT_NODE``; gli archi del DAG vivono in
    ``node["prerequisite_ids"]``.
    """

    DEFAULT_PATH = "memory/student-model.json"

    # ------------------------------------------------------------------
    # Costruzione
    # ------------------------------------------------------------------

    def __init__(self, path: str | None = None, student_id: str = "default") -> None:
        """Carica il modello dal file; se assente crea un modello vuoto.

        Args:
            path: path al file JSON (default ``DEFAULT_PATH``).
            student_id: identificatore dello studente (usato solo alla
                        creazione di un nuovo modello).
        """
        self._path: str = path if path is not None else self.DEFAULT_PATH
        self._student_id: str = student_id
        self._data: dict[str, Any] = {}
        self.load(self._path)

    # ------------------------------------------------------------------
    # Persistenza (AC1)
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """Carica da file JSON.  Crea struttura vuota se il file e' assente.

        Se ``schema_version`` nel file e' diversa da ``SCHEMA_VERSION``
        logga un warning su stderr e prosegue senza bloccare.

        Args:
            path: path al file JSON da leggere.
        """
        p = Path(path)
        if not p.exists():
            # File assente: inizializza struttura vuota
            self._data = {
                "schema_version": SCHEMA_VERSION,
                "student_id": self._student_id,
                "nodes": {},
            }
            return

        with p.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        # Validazione schema_version
        found_version = raw.get("schema_version", "")
        if found_version != SCHEMA_VERSION:
            import sys
            print(
                f"[StudentModel] WARNING: schema_version '{found_version}' "
                f"!= expected '{SCHEMA_VERSION}' — proseguo senza migrazione.",
                file=sys.stderr,
            )

        self._data = raw

    def save(self, path: str | None = None) -> None:
        """Salva il modello su file JSON.

        Crea la directory se assente.  Usa scrittura atomica (write su file
        temporaneo con suffisso ``.tmp`` nella stessa directory, poi
        ``os.replace``) per evitare corruzione in caso di interruzione.

        Args:
            path: path di destinazione (default ``self._path``).
        """
        target = Path(path if path is not None else self._path)

        # Crea directory se assente
        target.parent.mkdir(parents=True, exist_ok=True)

        # Scrittura atomica: tmp → rename (os.replace e' atomico su POSIX e Win)
        tmp_path = target.with_suffix(target.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")  # newline finale per compatibilita' POSIX
            os.replace(tmp_path, target)
        except Exception:
            # Pulizia del file temporaneo in caso di errore
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Accesso ai nodi
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> dict | None:
        """Ritorna il nodo o ``None`` se assente.

        Args:
            node_id: slug univoco del nodo (es. ``"retrieval-protocol"``).

        Returns:
            Dizionario del nodo o ``None``.
        """
        return self._data["nodes"].get(node_id)

    def upsert_node(self, node_id: str, **fields: Any) -> None:
        """Crea o aggiorna il nodo con i campi forniti.

        I campi esistenti vengono mantenuti; i campi mancanti sono
        inizializzati da ``DEFAULT_NODE``.

        Args:
            node_id: slug univoco del nodo.
            **fields: campi da impostare/aggiornare.
        """
        nodes: dict = self._data["nodes"]
        if node_id not in nodes:
            # Crea nodo nuovo da DEFAULT_NODE (copia profonda per evitare alias)
            import copy
            node = copy.deepcopy(DEFAULT_NODE)
            node["id"] = node_id
            nodes[node_id] = node

        # Aggiorna solo i campi forniti
        nodes[node_id].update(fields)

    def update_mastery(self, node_id: str, delta: float) -> float:
        """Aggiorna ``mastery`` del nodo applicando ``delta`` e clamp ``[0.0, 1.0]``.

        Crea il nodo se assente.  Ritorna il nuovo valore.

        Args:
            node_id: slug univoco del nodo.
            delta: incremento/decremento (positivo o negativo).

        Returns:
            Nuovo valore di ``mastery`` dopo clamp.
        """
        if node_id not in self._data["nodes"]:
            self.upsert_node(node_id)

        node = self._data["nodes"][node_id]
        new_mastery = float(node.get("mastery", 0.0)) + delta
        # Clamp [0.0, 1.0]
        new_mastery = max(0.0, min(1.0, new_mastery))
        node["mastery"] = new_mastery
        return new_mastery

    # ------------------------------------------------------------------
    # Grafo dei prerequisiti — Kahn's algorithm (AC4)
    # ------------------------------------------------------------------

    def get_prerequisites(self, node_id: str) -> list[str]:
        """Ritorna la lista piatta dei prerequisiti in ordine topologico.

        Implementazione BFS (Kahn's algorithm) sul sottoDAG raggiungibile a
        partire dai prerequisiti di ``node_id``.  Il nodo ``node_id`` stesso
        NON e' incluso nel risultato.

        Args:
            node_id: slug del nodo di destinazione.

        Returns:
            Lista ordinata di ``node_id`` prerequisiti (radici per prime).

        Raises:
            ValueError: se il grafo contiene cicli.
        """
        # Raccoglie tutti i nodi nel sottoDAG (prerequisiti transitivi)
        # escludendo node_id dal risultato finale.
        nodes = self._data["nodes"]

        # BFS per raccogliere tutti i nodi del sottoDAG
        visited: set[str] = set()
        queue: deque[str] = deque()

        start_prereqs = nodes.get(node_id, {}).get("prerequisite_ids", [])
        for pid in start_prereqs:
            if pid not in visited:
                visited.add(pid)
                queue.append(pid)

        subdag_nodes: set[str] = set(start_prereqs)
        while queue:
            current = queue.popleft()
            for pid in nodes.get(current, {}).get("prerequisite_ids", []):
                if pid not in subdag_nodes:
                    subdag_nodes.add(pid)
                    queue.append(pid)

        # Kahn's algorithm sul sottoDAG
        # Costruisce: in-degree e adj-list solo per i nodi nel sottoDAG
        in_degree: dict[str, int] = {n: 0 for n in subdag_nodes}
        adj: dict[str, list[str]] = {n: [] for n in subdag_nodes}

        for n in subdag_nodes:
            for prereq in nodes.get(n, {}).get("prerequisite_ids", []):
                if prereq in subdag_nodes:
                    # prereq → n (prereq deve venire prima di n)
                    adj[prereq].append(n)
                    in_degree[n] += 1

        # Inizializza la coda con i nodi a in-degree 0 (radici)
        kahn_queue: deque[str] = deque(
            sorted(n for n, deg in in_degree.items() if deg == 0)
        )
        topo_order: list[str] = []

        while kahn_queue:
            node = kahn_queue.popleft()
            topo_order.append(node)
            for successor in sorted(adj.get(node, [])):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    kahn_queue.append(successor)

        if len(topo_order) != len(subdag_nodes):
            raise ValueError("ciclo rilevato nel grafo prerequisiti")

        return topo_order

    def topological_order(self, start_node_id: str) -> list[str]:
        """Ritorna il percorso di apprendimento: prerequisiti + nodo finale.

        Chiama ``get_prerequisites()`` e appende ``start_node_id`` alla fine.

        Args:
            start_node_id: slug del nodo obiettivo.

        Returns:
            Lista ``[prereq_1, ..., prereq_N, start_node_id]``.

        Raises:
            ValueError: se il grafo contiene cicli.
        """
        prereqs = self.get_prerequisites(start_node_id)
        return prereqs + [start_node_id]

    # ------------------------------------------------------------------
    # Spaced Repetition — SM-2 semplificato (TSK-358, AC6)
    # ------------------------------------------------------------------

    def schedule_next_review(
        self,
        node_id: str,
        correct: bool,
        today: date | None = None,
    ) -> str:
        """Calcola e imposta ``next_review`` per il nodo usando SM-2 semplificato.

        ALGORITMO:
        - Se ``correct=True``:
              interval = max(1, prev_interval * 2)
              interval = min(interval, MAX_INTERVAL_DAYS)   # cap 30 gg (SR-2)
              next_review = today + timedelta(days=interval)
        - Se ``correct=False``:
              interval = RESET_INTERVAL_DAYS (1)            # reset (SR-3)
              next_review = today + timedelta(days=interval)
              aggiunge entry a node["errors"]

        INVARIANTE SR-1: schedule_next_review(node, correct=True) produce
        next_review strettamente maggiore di schedule_next_review(node,
        correct=False) sulla stessa data (intervallo ≥ 2 vs intervallo = 1).

        Il campo ``_internal_interval_days`` (prefisso underscore = interno,
        fuori schema pubblico TSK-356) persiste l'intervallo corrente per
        il raddoppio iterativo.  Al primo scheduling su un nodo il valore
        di partenza e' 1.

        Args:
            node_id: slug univoco del nodo.
            correct: ``True`` se risposta corretta, ``False`` altrimenti.
            today: data di riferimento (default ``date.today()``); iniettabile
                   per test deterministici.

        Returns:
            ``next_review`` come stringa ISO-8601 (es. ``"2026-07-20"``).
        """
        if today is None:
            today = date.today()

        if node_id not in self._data["nodes"]:
            self.upsert_node(node_id)

        node = self._data["nodes"][node_id]

        if correct:
            prev_interval = int(node.get("_internal_interval_days", 1))
            interval = max(1, prev_interval * 2)
            interval = min(interval, MAX_INTERVAL_DAYS)
        else:
            interval = RESET_INTERVAL_DAYS
            node.setdefault("errors", []).append({
                "timestamp": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "description": "risposta errata — ripasso schedulato",
            })

        next_review = today + timedelta(days=interval)
        node["next_review"] = next_review.isoformat()
        node["_internal_interval_days"] = interval

        return next_review.isoformat()

    # ------------------------------------------------------------------
    # Provenance e Staleness (TSK-359, AC3)
    # ------------------------------------------------------------------

    def update_provenance(
        self,
        node_id: str,
        source_path: str,
        content_hash: str,
    ) -> None:
        """Registra/aggiorna la provenance del nodo.

        Imposta:
            ``node["source_ref"]["path"]`` = ``source_path``
            ``node["source_ref"]["version_hash"]`` = ``content_hash``
            ``node["is_stale"]`` = ``False``  (appena aggiornato, non stale)

        Crea il nodo se non esiste (via ``upsert_node``).

        Args:
            node_id: slug univoco del nodo.
            source_path: path alla fonte (wiki page o file codebase).
            content_hash: hash MD5 del contenuto al momento della stima.
        """
        if node_id not in self._data["nodes"]:
            self.upsert_node(node_id)

        node = self._data["nodes"][node_id]
        node.setdefault("source_ref", {})
        node["source_ref"]["path"] = source_path
        node["source_ref"]["version_hash"] = content_hash
        node["is_stale"] = False

    def check_staleness(
        self,
        source_path: str,
        current_hash: str,
    ) -> list[str]:
        """Confronta ``current_hash`` con ``version_hash`` per tutti i nodi
        che referenziano ``source_path``.

        Per ogni nodo con ``source_ref.path == source_path``:
            se ``source_ref.version_hash != current_hash`` → ``is_stale = True``

        Non chiama ``save()`` automaticamente — il caller decide quando salvare.

        Args:
            source_path: path della fonte da controllare.
            current_hash: hash corrente (MD5 hex) della fonte.

        Returns:
            Lista di ``node_id`` marcati ``is_stale=True`` in questa chiamata.
        """
        stale_ids: list[str] = []
        for node_id, node in self._data["nodes"].items():
            source_ref = node.get("source_ref", {})
            if source_ref.get("path") == source_path:
                if source_ref.get("version_hash") != current_hash:
                    node["is_stale"] = True
                    stale_ids.append(node_id)
        return stale_ids

    def compute_content_hash(self, file_path: str) -> str:
        """Calcola MD5 del contenuto del file (confronto di freshness, non crittografico).

        Args:
            file_path: path al file da hashare.

        Returns:
            Hex digest MD5 del file, o ``""`` se il file e' assente
            (hash assente = stale implicito).
        """
        p = Path(file_path)
        if not p.exists():
            return ""
        return hashlib.md5(p.read_bytes()).hexdigest()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def student_id(self) -> str:
        """Identificatore dello studente."""
        return self._data.get("student_id", self._student_id)

    @property
    def nodes(self) -> dict[str, Any]:
        """Dizionario ``{node_id: nodo}`` (read-only per reference)."""
        return self._data["nodes"]

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"StudentModel(student_id={self.student_id!r}, "
            f"nodes={len(self.nodes)}, path={self._path!r})"
        )


# ---------------------------------------------------------------------------
# Mini-demo (AC1 roundtrip + AC4 topological_order)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("=== StudentModel mini-demo ===\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = str(Path(tmp_dir) / "student-model.json")

        # ---- Sessione 1: crea nodi e aggiorna mastery ----
        sm1 = StudentModel(path=json_path, student_id="demo-student")

        # Nodo radice (nessun prerequisito)
        sm1.upsert_node(
            "wiki-structure",
            source_ref={"path": "wiki/concepts/wiki-structure.md", "version_hash": "abc123"},
        )
        # Nodo intermedio che richiede wiki-structure
        sm1.upsert_node(
            "dev-protocol-flow",
            prerequisite_ids=["wiki-structure"],
            source_ref={"path": "wiki/concepts/dev-protocol.md", "version_hash": "def456"},
        )
        # Nodo foglia che richiede dev-protocol-flow
        sm1.upsert_node(
            "dev-handoff-pattern",
            prerequisite_ids=["dev-protocol-flow"],
            source_ref={"path": "wiki/concepts/dev-handoff.md", "version_hash": "ghi789"},
        )

        # Aggiorna mastery
        new_m = sm1.update_mastery("wiki-structure", 0.8)
        print(f"[sessione 1] wiki-structure mastery dopo update: {new_m}")

        # Salva
        sm1.save()
        print(f"[sessione 1] modello salvato in {json_path}")

        # ---- Sessione 2: ricarica e verifica persistenza (AC1 + AC5) ----
        sm2 = StudentModel(path=json_path)
        node = sm2.get_node("wiki-structure")
        assert node is not None, "nodo wiki-structure non trovato dopo reload"
        assert node["mastery"] == 0.8, f"mastery attesa 0.8, trovata {node['mastery']}"
        print(f"[sessione 2] wiki-structure mastery dopo reload: {node['mastery']} — OK")

        # ---- Ordinamento topologico su DAG a 3 nodi (AC4) ----
        order = sm2.topological_order("dev-handoff-pattern")
        print(f"[AC4] topological_order('dev-handoff-pattern'): {order}")
        assert order == ["wiki-structure", "dev-protocol-flow", "dev-handoff-pattern"], (
            f"ordine topologico errato: {order}"
        )
        print("[AC4] ordine corretto — OK")

        # ---- Rilevazione ciclo ----
        sm2.upsert_node("A", prerequisite_ids=["B"])
        sm2.upsert_node("B", prerequisite_ids=["C"])
        sm2.upsert_node("C", prerequisite_ids=["A"])
        try:
            sm2.topological_order("A")
            raise AssertionError("attesa ValueError per ciclo non sollevata")
        except ValueError as exc:
            print(f"[ciclo] ValueError correttamente sollevata: {exc} — OK")

        # ---- Clamp mastery ----
        v_high = sm2.update_mastery("wiki-structure", 999.0)
        assert v_high == 1.0, f"clamp superiore fallito: {v_high}"
        v_low = sm2.update_mastery("wiki-structure", -999.0)
        assert v_low == 0.0, f"clamp inferiore fallito: {v_low}"
        print(f"[clamp] mastery clamp [0.0, 1.0] — OK (high={v_high}, low={v_low})")

    print("\n=== Tutti i controlli superati ===")
