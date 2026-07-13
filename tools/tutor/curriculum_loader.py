"""
curriculum_loader.py — CurriculumLoader (TSK-393, EP-045 US-164)

Carica un curriculum YAML (schema v1.0, wiki/concepts/curriculum-schema.md)
e inietta i nodi nel grafo dei prerequisiti dello StudentModel come seme
iniziale del percorso di apprendimento.

Dipendenze: pyyaml (con fallback ImportError informativo se assente).
La lettura avviene a ogni chiamata di load() — nessuna cache persistente (AC4).
Schema atteso: schema_version "1.0", campo 'nodes' lista non vuota.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# PyYAML con fallback informativo se non disponibile
try:
    import yaml as _yaml_lib

    _YAML_AVAILABLE = True
except ImportError:  # pragma: no cover
    _YAML_AVAILABLE = False
    _yaml_lib = None  # type: ignore[assignment]

from tools.tutor.student_model import StudentModel

__all__ = ["CurriculumLoader"]


class CurriculumLoader:
    """Carica un curriculum YAML (schema v1.0) e lo inietta nel grafo dei
    prerequisiti dello Student Model come seme iniziale.

    La lettura avviene a ogni chiamata di load(): modifiche al file curriculum
    sono visibili alla chiamata successiva senza modifiche al codice (AC4).

    Args:
        curriculum_path: path al file YAML del curriculum (es.
            ``tools/tutor/curriculum/factory-onboarding.yaml``).
    """

    SUPPORTED_VERSIONS: tuple[str, ...] = ("1.0",)

    def __init__(self, curriculum_path: str) -> None:
        self.curriculum_path = curriculum_path

    # ------------------------------------------------------------------
    # Lettura e validazione YAML
    # ------------------------------------------------------------------

    def _read_yaml(self) -> dict:
        """Legge e valida la struttura di primo livello del file YAML.

        Verifica:
          - il file esiste
          - ``schema_version`` e' "1.0"
          - ``nodes`` e' una lista non vuota

        Returns:
            Dizionario con i dati del curriculum.

        Raises:
            FileNotFoundError: se il file non esiste.
            ImportError: se pyyaml non e' installato.
            ValueError: se la struttura non rispetta lo schema v1.0.
        """
        p = Path(self.curriculum_path)
        if not p.exists():
            raise FileNotFoundError(
                f"curriculum file non trovato: {self.curriculum_path}"
            )

        if not _YAML_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "pyyaml non disponibile. Installa con: pip install pyyaml"
            )

        with p.open("r", encoding="utf-8") as fh:
            data = _yaml_lib.safe_load(fh)

        if not isinstance(data, dict):
            raise ValueError(
                "il file curriculum non e' un dizionario YAML valido"
            )

        # Valida schema_version
        version = data.get("schema_version")
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(
                f"schema_version non supportata: '{version}'. "
                f"Attese: {self.SUPPORTED_VERSIONS}"
            )

        # Valida nodes: lista non vuota
        nodes = data.get("nodes")
        if not isinstance(nodes, list) or len(nodes) == 0:
            raise ValueError(
                "il campo 'nodes' deve essere una lista non vuota"
            )

        return data

    # ------------------------------------------------------------------
    # Iniezione nodi
    # ------------------------------------------------------------------

    def _inject_node(
        self, node_data: dict, student_model: StudentModel
    ) -> bool:
        """Inietta un singolo nodo nel Student Model.

        Strategia:
          - Nodo nuovo: upsert con ``mastery=0.0``, ``prerequisite_ids``
            dai prerequisites del curriculum, ``source_ref`` dal primo
            entry di ``sources``.
          - Nodo esistente: aggiorna SOLO ``prerequisite_ids`` (il curriculum
            e' source-of-truth per la struttura del grafo — AC3).
            NON sovrascrive ``mastery``, ``errors``, ``next_review``
            (storia di apprendimento dello studente).

        Args:
            node_data: dizionario del nodo dal curriculum YAML.
            student_model: istanza dello StudentModel da aggiornare.

        Returns:
            True se iniettato/aggiornato con successo, False se saltato.
        """
        node_id = node_data.get("id")
        if not node_id or not isinstance(node_id, str):
            return False

        prereqs: list[str] = node_data.get("prerequisites", [])
        if not isinstance(prereqs, list):
            prereqs = []

        existing = student_model.get_node(node_id)

        if existing is None:
            # Nodo nuovo: crea con mastery=0.0 e source_ref dal primo sources
            sources: list[Any] = node_data.get("sources", [])
            source_ref: dict[str, str] = {"path": "", "version_hash": ""}
            if sources and isinstance(sources[0], dict):
                source_ref["path"] = sources[0].get("path", "")

            student_model.upsert_node(
                node_id,
                mastery=0.0,
                prerequisite_ids=prereqs,
                source_ref=source_ref,
            )
        else:
            # Nodo esistente: aggiorna SOLO prerequisite_ids via upsert_node
            # (upsert_node chiama dict.update(**fields), quindi tocca solo
            # le chiavi esplicitamente passate — mastery/errors/next_review
            # rimangono invariati).
            student_model.upsert_node(node_id, prerequisite_ids=prereqs)

        return True

    # ------------------------------------------------------------------
    # Validazione riferimenti
    # ------------------------------------------------------------------

    def validate_refs(self, curriculum_root: str | None = None) -> list[str]:
        """Verifica l'esistenza di tutti i path in sources[*].path del curriculum.

        Args:
            curriculum_root: path base dal quale risolvere i path relativi dei
                sources. Default: root del repo (parent directory di ``tools/``),
                calcolata risalendo di 3 livelli dal file curriculum.

        Returns:
            Lista di stringhe-avviso (una per ogni ref non trovata), es.:
            ``["WARNING: nodo 'repo-structure': sources[0].path non trovato: "
            "'wiki/runbooks/getting-started.md'", ...]``
            Lista vuota = tutti i path esistono.

        INVARIANTE R-1: un ref non valido produce un avviso ESPLICITO,
            NON un errore silenzioso.
        INVARIANTE R-2: la validazione NON blocca il caricamento del nodo
            (warning-only; i nodi vengono comunque iniettati nel Student Model).
        """
        if curriculum_root is None:
            # risale di 3 livelli: tools/tutor/curriculum/ → root repo
            curriculum_root = os.path.abspath(
                os.path.join(os.path.dirname(self.curriculum_path), "../../..")
            )

        data = self._read_yaml()
        warnings: list[str] = []
        for node in data.get("nodes", []):
            for i, source in enumerate(node.get("sources", [])):
                path = source.get("path", "")
                full_path = os.path.join(curriculum_root, path)
                if not os.path.exists(full_path):
                    warnings.append(
                        f"WARNING: nodo '{node['id']}': "
                        f"sources[{i}].path non trovato: '{path}'"
                    )
        return warnings

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def load(self, student_model: StudentModel) -> dict:
        """Legge il file YAML e inietta nodi + archi nel student_model.

        La lettura avviene a ogni chiamata (no cache persistente — AC4).

        Per ogni nodo del curriculum:
          - Se il nodo NON esiste nel Student Model: upsert con mastery=0.0,
            prerequisite_ids dai prerequisites del curriculum, source_ref
            dal primo entry di sources.
          - Se il nodo ESISTE gia' nel Student Model: aggiorna prerequisite_ids
            (il curriculum e' source-of-truth per la struttura del grafo — AC3)
            ma NON sovrascrive mastery, errors, next_review.

        Args:
            student_model: istanza dello StudentModel da aggiornare.

        Returns:
            dict con tre campi:
              - ``loaded``   (int):       nodi iniettati o aggiornati con successo
              - ``skipped``  (int):       nodi saltati (errori schema, id duplicati)
              - ``warnings`` (list[str]): messaggi di avviso non bloccanti
        """
        loaded = 0
        skipped = 0
        warnings: list[str] = []

        try:
            data = self._read_yaml()
        except (FileNotFoundError, ValueError, ImportError) as exc:
            warnings.append(f"Lettura curriculum fallita: {exc}")
            return {"loaded": loaded, "skipped": skipped, "warnings": warnings}

        # AC6 — avvisi espliciti per source refs non validi (R-1 + R-2: non bloccanti)
        warnings.extend(self.validate_refs())

        nodes = data.get("nodes", [])
        seen_ids: set[str] = set()

        for node_data in nodes:
            if not isinstance(node_data, dict):
                skipped += 1
                warnings.append(
                    f"nodo non valido (atteso dict, trovato "
                    f"{type(node_data).__name__}): {node_data!r}"
                )
                continue

            node_id = node_data.get("id")

            # Regola 1 — unicita' degli identificatori (warning non bloccante)
            if node_id and node_id in seen_ids:
                skipped += 1
                warnings.append(
                    f"id duplicato nel curriculum: '{node_id}' — secondo nodo skipped"
                )
                continue

            if node_id:
                seen_ids.add(node_id)

            ok = self._inject_node(node_data, student_model)
            if ok:
                loaded += 1
            else:
                skipped += 1
                warnings.append(
                    f"nodo skippato (id mancante o non valido): {node_data!r}"
                )

        return {"loaded": loaded, "skipped": skipped, "warnings": warnings}

    def reload(self, student_model: StudentModel) -> dict:
        """Forza rilettura del file + re-injection.

        Equivale a load() ma segnala esplicitamente l'intenzione di
        aggiornamento mid-session. Utile per applicare modifiche al file
        YAML senza riavviare la sessione tutor.

        Args:
            student_model: istanza dello StudentModel da aggiornare.

        Returns:
            Stesso formato di load(): {"loaded", "skipped", "warnings"}.
        """
        return self.load(student_model)
