"""tools/tutor/tests/test_retrieval_tool.py — Test retrieval-protocol (US-160 AC1-AC6).

6 test case corrispondenti agli Acceptance Criteria di US-160:

  Test 1 (AC1): hit wiki + citazione strutturata (source + section)
  Test 2 (AC2): miss wiki → lista vuota (il tool non inventa contenuto)
  Test 3 (AC3): emit_gap_record → schema {concept, original_query, timestamp ISO-8601 Z}
  Test 4 (AC4): hit codebase → citazione con percorso file + class rilevata
  Test 5 (AC5): freshness sessione — modifica visibile immediatamente senza riavvio
  Test 6 (AC6): _ep042_enabled() legge factory.config.yaml con toggle enabled true/false

Strategia di test:
- Test 1, 2, 4: monkeypatch su _run_search per risultati deterministici e CI-safe
  (nessuna dipendenza da rg/grep disponibile nell'ambiente di CI).
- Test 3, 6: nessun subprocess — invocazioni dirette delle funzioni pure.
- Test 5: subprocess reale (grep/rg) per verificare genuinamente l'assenza di cache
  (il punto centrale dell'AC5 e' che il tool rilegge il filesystem a ogni chiamata).

Framework: pytest + stdlib. Nessuna dipendenza esterna.
Fixture: tmp_path (pytest built-in) per strutture filesystem isolate.

[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-349-test-retrieval-protocol.md]
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import tools.tutor.retrieval_tool as rt


# ---------------------------------------------------------------------------
# Helpers per la costruzione di fixture filesystem
# ---------------------------------------------------------------------------

def _create_wiki_file(tmp_path: Path, filename: str, content: str) -> Path:
    """Crea tmp_path/wiki/concepts/<filename> con il contenuto dato."""
    target = tmp_path / "wiki" / "concepts" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _create_src_file(tmp_path: Path, filename: str, content: str) -> Path:
    """Crea tmp_path/src/<filename> con il contenuto dato."""
    target = tmp_path / "src" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Test 1 — AC1: hit wiki + citazione strutturata
# ---------------------------------------------------------------------------

def test_ac1_wiki_hit_returns_citation(tmp_path: Path, monkeypatch) -> None:
    """AC1: search_wiki restituisce una citation con 'source' e 'section' corretti.

    Setup: wiki fittizio con heading ## Test Section.
    _run_search e' mockata per restituire un hit deterministico sulla riga 3
    del file (dove appare il testo che matcha la query).
    Assert: source termina con test-concept.md, section == 'Test Section'.
    """
    wiki_file = _create_wiki_file(
        tmp_path,
        "test-concept.md",
        "## Test Section\n\nQuesta e' una definizione di test concept.\n",
    )

    # Monkeypatch _run_search: restituisce un hit sulla riga 3 del file wiki.
    # Il percorso e' assoluto e risolto (come farebbe grep con un target assoluto).
    def _fake_run_search(pattern, target, **kwargs):
        return [(str(wiki_file), 3, "test concept")]

    monkeypatch.setattr(rt, "_run_search", _fake_run_search)

    result = rt.search_wiki("test concept", repo_root=str(tmp_path))

    assert len(result) > 0, "Atteso almeno un risultato per una query che matcha il file"
    first = result[0]

    assert "source" in first, f"Citation deve contenere il campo 'source', got keys: {list(first.keys())}"
    assert "section" in first, f"Citation deve contenere il campo 'section', got keys: {list(first.keys())}"

    assert first["source"].endswith("test-concept.md"), (
        f"'source' deve terminare con 'test-concept.md', got: {first['source']!r}"
    )
    assert first["section"] == "Test Section", (
        f"'section' deve essere 'Test Section', got: {first['section']!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — AC2: miss wiki → lista vuota
# ---------------------------------------------------------------------------

def test_ac2_wiki_miss_returns_empty_list(tmp_path: Path, monkeypatch) -> None:
    """AC2: search_wiki restituisce [] quando nessun file matcha la query.

    Il tool non deve inventare contenuto — la lista vuota e' il segnale
    esplicito per il caller di dichiarare una lacuna (gap-record).
    """
    # Wiki con contenuto non pertinente
    _create_wiki_file(tmp_path, "unrelated.md", "Questo file non contiene nulla di utile.\n")

    # _run_search non trova nulla (nessun match grep/rg)
    monkeypatch.setattr(rt, "_run_search", lambda *a, **kw: [])

    result = rt.search_wiki("concetto inesistente xyz987", repo_root=str(tmp_path))

    assert result == [], (
        f"Attesa lista vuota per miss totale, got: {result}"
    )


# ---------------------------------------------------------------------------
# Test 3 — AC3: gap-record strutturato
# ---------------------------------------------------------------------------

def test_ac3_emit_gap_record_schema() -> None:
    """AC3: emit_gap_record ritorna un dict con le chiavi concept, original_query, timestamp.

    timestamp deve essere una stringa ISO-8601 UTC con suffisso Z.
    Nessun subprocess coinvolto — funzione pura.
    """
    concept = "concetto inesistente"
    query = "Cos'e' il concetto inesistente?"

    record = rt.emit_gap_record(concept, query)

    assert isinstance(record, dict), f"Atteso dict, got: {type(record)}"

    for key in ("concept", "original_query", "timestamp"):
        assert key in record, f"Chiave '{key}' mancante nel gap-record: {list(record.keys())}"

    assert record["concept"] == concept, (
        f"concept deve essere {concept!r}, got: {record['concept']!r}"
    )
    assert record["original_query"] == query, (
        f"original_query deve essere {query!r}, got: {record['original_query']!r}"
    )

    # timestamp ISO-8601 UTC con Z finale: YYYY-MM-DDTHH:MM:SSZ
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    assert iso_pattern.match(record["timestamp"]), (
        f"timestamp non conforme al formato ISO-8601Z, got: {record['timestamp']!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 — AC4: hit codebase + percorso file
# ---------------------------------------------------------------------------

def test_ac4_codebase_hit_returns_file_citation(tmp_path: Path, monkeypatch) -> None:
    """AC4: search_codebase restituisce una citation con 'file' e 'class' rilevata.

    Setup: codebase fittizio con class MyClass e metodo my_function.
    _run_search e' mockata per restituire un hit deterministico sulla riga 1
    (dove c'e' la dichiarazione 'class MyClass:').
    Assert: 'file' contiene mymodule.py, 'class' == 'MyClass'.
    """
    py_file = _create_src_file(
        tmp_path,
        "mymodule.py",
        "class MyClass:\n    def my_function(self):\n        pass\n",
    )

    # Hit sulla riga 1 (1-based) dove si trova "class MyClass:"
    def _fake_run_search(pattern, target, **kwargs):
        return [(str(py_file), 1, "class MyClass:")]

    monkeypatch.setattr(rt, "_run_search", _fake_run_search)

    result = rt.search_codebase("MyClass", repo_root=str(tmp_path))

    assert len(result) > 0, "Atteso almeno un risultato per la query 'MyClass'"
    first = result[0]

    assert "file" in first, f"Citation codebase deve contenere il campo 'file', got: {list(first.keys())}"
    assert "mymodule.py" in first["file"], (
        f"'file' deve contenere 'mymodule.py', got: {first['file']!r}"
    )

    # _nearest_scope rileva MyClass risalendo dalla riga 1
    assert first.get("class") == "MyClass", (
        f"'class' deve essere 'MyClass', got: {first.get('class')!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — AC5: freshness sessione (subprocess reale)
# ---------------------------------------------------------------------------

def test_ac5_freshness_modifica_visibile_senza_riavvio(tmp_path: Path) -> None:
    """AC5: una modifica al file wiki e' visibile nella chiamata successiva senza riavvio.

    Verifica l'assenza di cache intra-processo: il tool rilegge il filesystem
    a ogni invocazione (retrieval-protocol §Vincoli 1).
    Test usa subprocess reale (grep/rg) — unico AC che richiede integrazione reale
    per essere significativo.
    """
    fresh_file = _create_wiki_file(
        tmp_path,
        "fresh.md",
        "Placeholder content\n",
    )

    # --- Prima ricerca: nessun match atteso ---
    result_before = rt.search_wiki("parola unica", repo_root=str(tmp_path))
    assert result_before == [], (
        f"Attesa lista vuota prima della modifica del file, got: {result_before}"
    )

    # --- Modifica il file nella stessa sessione Python ---
    fresh_file.write_text(
        "## parola unica\n\nDescrizione della parola unica.\n",
        encoding="utf-8",
    )

    # --- Seconda ricerca: deve trovare il contenuto aggiornato ---
    result_after = rt.search_wiki("parola unica", repo_root=str(tmp_path))
    assert len(result_after) > 0, (
        "Atteso almeno un risultato dopo la modifica — freshness garantita dal tool "
        "(nessuna cache intra-processo)"
    )
    assert any("fresh.md" in r["source"] for r in result_after), (
        f"fresh.md non trovato nelle source dei risultati: "
        f"{[r['source'] for r in result_after]}"
    )


# ---------------------------------------------------------------------------
# Test 6 — AC6: toggle EP-042 via factory.config.yaml
# ---------------------------------------------------------------------------

def test_ac6_ep042_enabled_reads_flag_correctly(tmp_path: Path) -> None:
    """AC6: _ep042_enabled() legge correttamente wiki_search.enabled da factory.config.yaml.

    Verifica entrambi i branch (enabled: false → False, enabled: true → True)
    e assicura che nessuna eccezione venga sollevata in nessuno dei due casi.
    Nessun subprocess coinvolto — parsing YAML stdlib.
    """
    config_path = tmp_path / "factory.config.yaml"

    # --- Branch enabled: false ---
    config_path.write_text(
        "wiki_search:\n  enabled: false\n",
        encoding="utf-8",
    )
    result_false = rt._ep042_enabled(repo_root=str(tmp_path))
    assert result_false is False, (
        f"Atteso False con 'enabled: false', got: {result_false!r}"
    )

    # --- Branch enabled: true ---
    config_path.write_text(
        "wiki_search:\n  enabled: true\n",
        encoding="utf-8",
    )
    result_true = rt._ep042_enabled(repo_root=str(tmp_path))
    assert result_true is True, (
        f"Atteso True con 'enabled: true', got: {result_true!r}"
    )
