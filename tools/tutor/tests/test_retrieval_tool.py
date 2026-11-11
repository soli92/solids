"""tools/tutor/tests/test_retrieval_tool.py — Test retrieval-protocol (US-160 AC1-AC6).

6 test cases corresponding to the US-160 Acceptance Criteria:

  Test 1 (AC1): hit wiki + structured citation (source + section)
  Test 2 (AC2): miss wiki → empty list (the tool does not invent content)
  Test 3 (AC3): emit_gap_record → schema {concept, original_query, ISO-8601 Z timestamp}
  Test 4 (AC4): codebase hit → quote with file path + class detected
  Test 5 (AC5): session freshness — change visible immediately without reboot
  Test 6 (AC6): _ep042_enabled() reads factory.config.yaml with toggle enabled true/false

Testing strategy:
- Test 1, 2, 4: monkeypatch on _run_search for deterministic and CI-safe results
  (no rg/grep dependencies available in CI environment).
- Test 3, 6: no subprocess — direct invocations of pure functions.
- Test 5: real subprocess (grep/rg) to genuinely verify the absence of cache
  (The whole point of AC5 is that the tool rereads the filesystem on every call.)

Framework: pytest + stdlib. No external dependencies.
Fixture: tmp_path (pytest built-in) for isolated filesystem structures.

[^src: management/kanban/EP-045-capability-formativa/US-160-retrieval-vivo-citato/TSK-349-test-retrieval-protocol.md]


"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import tools.tutor.retrieval_tool as rt


# ---------------------------------------------------------------------------
# Helpers for building filesystem fixtures

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

    # Monkeypatch _run_search: Returns a hit on line 3 of the wiki file.

    # The path is absolute and resolved (as grep would do with an absolute target).

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
# Test 2 — AC2: miss wiki → empty list

# ---------------------------------------------------------------------------

def test_ac2_wiki_miss_returns_empty_list(tmp_path: Path, monkeypatch) -> None:
    """AC2: search_wiki restituisce [] quando nessun file matcha la query.

    Il tool non deve inventare contenuto — la lista vuota e' il segnale
    esplicito per il caller di dichiarare una lacuna (gap-record).
    """
    # Wiki with irrelevant content

    _create_wiki_file(tmp_path, "unrelated.md", "Questo file non contiene nulla di utile.\n")

    # _run_search finds nothing (no grep/rg match)

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

    # ISO-8601 UTC timestamp with trailing Z: YYYY-MM-DDTHH:MM:SSZ

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

    # Hit on line 1 (1-based) where "class MyClass:" is located

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

    # _nearest_scope finds MyClass going back from line 1

    assert first.get("class") == "MyClass", (
        f"'class' deve essere 'MyClass', got: {first.get('class')!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — AC5: session freshness (real subprocess)

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

    # --- First search: no match expected ---

    result_before = rt.search_wiki("parola unica", repo_root=str(tmp_path))
    assert result_before == [], (
        f"Attesa lista vuota prima della modifica del file, got: {result_before}"
    )

    # --- Edit the file in the same Python session ---

    fresh_file.write_text(
        "## parola unica\n\nDescrizione della parola unica.\n",
        encoding="utf-8",
    )

    # --- Second search: must find updated content ---
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

def test_ac6_ep042_enabled_ora_richiede_il_doppio_gate(tmp_path: Path) -> None:
    """AC6, aggiornato da US-175 (TSK-675): `wiki_search.enabled` non basta piu'.

    **Cosa asseriva prima, e perche' e' cambiato.** Questo test pretendeva che
    `wiki_search.enabled: true` da solo aprisse il retrieval semantico. Era il
    comportamento reale, ed era un difetto: `capability_formativa.wiki_search_integration`
    era dichiarato in `factory.config.yaml` e **non governava niente** — il tutor
    interrogava l'indice anche con l'integrazione esplicitamente spenta.

    US-175 lo corregge con un doppio gate piu' l'interruttore dell'integrazione.
    L'asserzione cambia perche' e' cambiato **il requisito**, non perche' il codice sia
    diventato scomodo da testare: la copertura non si abbassa, si sposta su
    `test_retrieval_gate.py`, che prova tutte e cinque le combinazioni dei tre flag.
    """
    config_path = tmp_path / "factory.config.yaml"
    tre_flag = ("capability_formativa:\n  enabled: {cf}\n  wiki_search_integration: {i}\n"
                "wiki_search:\n  enabled: {ws}\n")

    # `wiki_search` da solo NON basta piu': e' il cuore del cambiamento.
    config_path.write_text("wiki_search:\n  enabled: true\n", encoding="utf-8")
    assert rt._ep042_enabled(repo_root=str(tmp_path)) is False

    # Le due capability accese ma l'integrazione spenta: ancora chiuso.
    config_path.write_text(tre_flag.format(cf="true", ws="true", i="false"), encoding="utf-8")
    assert rt._ep042_enabled(repo_root=str(tmp_path)) is False

    # Tutti e tre: aperto.
    config_path.write_text(tre_flag.format(cf="true", ws="true", i="true"), encoding="utf-8")
    assert rt._ep042_enabled(repo_root=str(tmp_path)) is True

    # Fail-closed: config assente non solleva e non apre.
    assert rt._ep042_enabled(repo_root=str(tmp_path / "vuota")) is False


