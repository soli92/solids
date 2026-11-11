"""Test di tools/lint/ste_lite.py (EP-076 TSK-805)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "tools" / "lint" / "ste_lite.py"

_spec = importlib.util.spec_from_file_location("ste_lite", _SCRIPT)
ste = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ste)

CFG = ste.carica_config("/inesistente")


def regole(testo, cfg=CFG, lang=None):
    return [v["regola"] for v in ste.analizza(testo, cfg, lang)["violazioni"]]


def lunga(n, parola="parola"):
    return "La " + " ".join([parola] * (n - 1)) + "."


# --- segmentazione ----------------------------------------------------------------------

def test_esclusi_frontmatter_codice_tabelle_titoli():
    testo = "\n".join([
        "---", "title: " + "x " * 40, "---",
        "# Titolo " + "lungo " * 40,
        "```", "codice " * 40, "```",
        "| a | " + "cella " * 40 + "|",
        "<!-- " + "commento " * 40 + " -->",
        "Il file è corto.",
    ])
    esito = ste.analizza(testo, CFG, "it")
    assert esito["frasi"] == 1
    assert esito["violazioni"] == []


def test_abbreviazioni_e_decimali_non_spezzano():
    assert ste.frasi("Usa il valore 3.5 ecc. per il test. Poi chiudi.") == [
        "Usa il valore 3.5 ecc. per il test.", "Poi chiudi."]
    assert len(ste.frasi("Vedi es. la sezione e cfr. il log.")) == 1


def test_apostrofo_conta_due_parole_e_codice_inline_uno():
    assert len(ste.parole("l'agente")) == 2
    assert len(ste.parole(ste.pulisci("apri `factory.config.yaml` ora"))) == 3


def test_url_e_link_ripuliti():
    assert ste.pulisci("vedi [la guida](http://x.y/z) e https://a.b/c") == "vedi la guida e URL"


# --- regole -----------------------------------------------------------------------------

def test_frase_descrittiva_al_limite_e_oltre():
    assert regole(lunga(25), lang="it") == []
    assert regole(lunga(26), lang="it") == ["frase-descrittiva"]


def test_frase_procedurale_da_elenco_numerato_e_da_imperativo():
    voce = "1. " + lunga(21)[0].lower() + lunga(21)[1:]
    assert regole(voce, lang="it") == ["frase-procedurale"]
    assert regole("Apri " + " ".join(["file"] * 20) + ".", lang="it") == ["frase-procedurale"]
    assert regole("Apri " + " ".join(["file"] * 19) + ".", lang="it") == []


def test_paragrafo_oltre_sei_frasi_solo_nella_prosa():
    sette = " ".join(["Il file è corto."] * 7)
    assert regole(sette, lang="it") == ["paragrafo"]
    assert regole(" ".join(["Il file è corto."] * 6), lang="it") == []
    assert "paragrafo" not in regole("- " + sette, lang="it")


def test_punto_e_virgola():
    assert regole("Il file è corto; il log è lungo.", lang="it") == ["punto-e-virgola"]


def test_istruzioni_multiple_in_procedura():
    assert regole("Apri il file e salva la copia.", lang="it") == ["istruzioni-multiple"]
    assert regole("Apri il file e la cartella.", lang="it") == []
    assert regole("Open the file and save a copy.", lang="en") == ["istruzioni-multiple"]


def test_passivo_solo_nelle_procedure():
    assert regole("1. Il file viene chiuso dal tool.", lang="it") == ["passivo-procedura"]
    assert regole("Il file viene chiuso dal tool.", lang="it") == []
    assert regole("1. The valve must be closed.", lang="en") == ["passivo-procedura"]
    assert regole("1. Close the valve.", lang="en") == []


def test_contrazione_fuori_dal_codice_inline():
    assert regole("Il raw → la wiki.", lang="it") == ["contrazione"]
    assert regole("Il tool ret il valore.", lang="it") == ["contrazione"]
    assert regole("Il valore `a → b` è corretto.", lang="it") == []


def test_glossario_sinonimo_vietato():
    cfg = dict(CFG, glossary={"task": ["compito", "attività"]})
    esito = ste.analizza("Il compito è chiuso.", cfg, "it")
    assert [(v["regola"], v["misura"], v["limite"]) for v in esito["violazioni"]] == [
        ("glossario", "compito", "task")]


def test_lingua_riconosciuta():
    assert ste.lingua("The file is open and the log is closed.") == "en"
    assert ste.lingua("Il file è aperto e il log della sessione è chiuso.") == "it"


def test_conformita_conta_le_frasi_non_le_violazioni():
    esito = ste.analizza("Il file è corto; il log è lungo. Il file è corto.", CFG, "it")
    assert esito["frasi"] == 2
    assert esito["frasi_conformi"] == 0.5


# --- riga di comando --------------------------------------------------------------------

def test_cli_advisory_strict_e_json(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text("Il file è corto; il log è lungo.\n", encoding="utf-8")
    assert ste.main([str(f), "--root", str(tmp_path)]) == 0
    assert ste.main([str(f), "--strict", "--root", str(tmp_path)]) == 1
    capsys.readouterr()
    assert ste.main([str(f), "--json", "--root", str(tmp_path)]) == 0
    dati = json.loads(capsys.readouterr().out)
    assert dati["enabled"] is False
    assert dati["file"][str(f)]["per_regola"] == {"punto-e-virgola": 1}


def test_cli_file_assente_e_nessun_argomento(tmp_path):
    assert ste.main([str(tmp_path / "manca.md"), "--root", str(tmp_path)]) == 2
    assert ste.main(["--root", str(tmp_path)]) == 2


def test_targets_a_flag_spento_exit_0(tmp_path, capsys):
    (tmp_path / "factory.config.yaml").write_text(
        "ste_lite:\n  enabled: false\n  targets: ['*.md']\n", encoding="utf-8")
    assert ste.main(["--targets", "--root", str(tmp_path)]) == 0
    assert "enabled: false" in capsys.readouterr().out


def test_config_limiti_e_targets(tmp_path):
    (tmp_path / "factory.config.yaml").write_text(
        "ste_lite:\n  enabled: true\n  targets: ['*.md']\n"
        "  limits:\n    descriptive_words: 10\n", encoding="utf-8")
    (tmp_path / "a.md").write_text(lunga(11) + "\n", encoding="utf-8")
    cfg = ste.carica_config(str(tmp_path))
    assert cfg["limits"]["descriptive_words"] == 10
    assert cfg["limits"]["procedural_words"] == 20
    assert ste.main(["--targets", "--strict", "--root", str(tmp_path)]) == 1


def test_config_del_repo_spenta():
    assert ste.carica_config(str(_REPO_ROOT))["enabled"] is False
