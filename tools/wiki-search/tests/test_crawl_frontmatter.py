"""Il crawl sopravvive ai tipi che PyYAML restituisce davvero (BUG-TSK-505-001, TSK-532).

`tags: [2026-09-02]` non e' una lista di stringhe: PyYAML riconosce la forma ISO-8601 e
costruisce un `datetime.date`, che `json.dumps` non serializza. Una sola pagina del wiki
con una data fra i tag faceva morire il crawl **dell'intero indice** — e il benchmark
TSK-505 l'aveva aggirato con una copia locale della funzione invece di ripararla.

Il test copre tutti i tipi non-stringa, non solo le date: `int`, `float` e `bool` hanno
la stessa forma di difetto, e il giorno in cui qualcuno scrive `tags: [2]` il crawl
tornerebbe a morire per la stessa ragione con un altro nome.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RADICE / "tools/wiki-search"))

from indexer import _jsonabile, crawl_wiki  # noqa: E402


def test_pyyaml_restituisce_una_data_e_non_una_stringa():
    """La premessa del difetto. Se un giorno cadesse, il resto del test non
    starebbe piu' verificando cio' che crede."""
    yaml = pytest.importorskip("yaml")
    letto = yaml.safe_load("tags: [2026-09-02, alfa]")
    assert isinstance(letto["tags"][0], datetime.date)
    with pytest.raises(TypeError):
        json.dumps(letto["tags"])


def test_jsonabile_converte_ogni_tipo_non_stringa():
    convertito = _jsonabile([datetime.date(2026, 9, 2), "alfa", 3, True, 1.5])
    assert convertito == ["2026-09-02", "alfa", "3", "True", "1.5"]
    assert json.dumps(convertito)          # ora serializza


def test_le_stringhe_non_vengono_toccate():
    """AC3 — nessuna regressione sui campi che gia' funzionavano."""
    originale = ["runbook", "poc", "fase-3a"]
    assert _jsonabile(originale) == originale


def test_una_data_fra_i_tag_non_uccide_il_crawl(tmp_path):
    """AC1 + AC2, su un wiki minimo costruito apposta."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "sana.md").write_text(
        "---\ntitle: Sana\ntype: concept\nstatus: approved\ntags: [alfa, beta]\n---\n\n# Sana\n\nCorpo.\n")
    (wiki / "concepts" / "con-data.md").write_text(
        "---\ntitle: Con data\ntype: concept\nstatus: approved\n"
        "tags: [snapshot, 2026-05-28, 2, true]\n---\n\n# Con data\n\nCorpo.\n")

    pagine = {p["path"]: p for p in crawl_wiki(wiki)}
    assert len(pagine) == 2, "una pagina difettosa non deve portarsi via le altre"
    tags = json.loads(pagine["concepts/con-data.md"]["tags_json"])
    assert tags == ["snapshot", "2026-05-28", "2", "True"]
    assert json.loads(pagine["concepts/sana.md"]["tags_json"]) == ["alfa", "beta"]


def test_il_wiki_reale_si_indicizza():
    """AC2 sul corpus vero: e' li' che il difetto si manifestava."""
    pagine = crawl_wiki(RADICE / "wiki")
    assert len(pagine) > 100
    for pagina in pagine:
        json.loads(pagina["tags_json"])     # ogni riga e' JSON valido
