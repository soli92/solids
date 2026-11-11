"""Check 4bf (ordine di wiki/log.md) e 4bg (contatore Sources di wiki/index.md)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
TOOLS = RADICE / "tools"
PY = sys.executable

TESTA_LOG = (
    "---\ntype: wiki-log\nappend_only: true\n---\n\n# Wiki Log\n\n"
    "---\ndate: 2026-11-01\ntype: develop\ncontext: voce di partenza\n---\n"
)


def voce(data: str, contesto: str) -> str:
    return f"\n---\ndate: {data}\ntype: develop\ncontext: {contesto}\n---\n"


def _carica(nome: str, percorso: Path):
    spec = importlib.util.spec_from_file_location(nome, percorso)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


derivati = _carica("check_dati_derivati_t", TOOLS / "lint" / "check_dati_derivati.py")


def _wiki(tmp_path: Path, log: str | None = None, index: str | None = None) -> Path:
    (tmp_path / "wiki").mkdir(exist_ok=True)
    if log is not None:
        (tmp_path / "wiki" / "log.md").write_text(log)
    if index is not None:
        (tmp_path / "wiki" / "index.md").write_text(index)
    return tmp_path


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(TOOLS / "lint" / "check_dati_derivati.py"), *args, str(root)],
                          capture_output=True, text=True)


def test_4bf_log_in_ordine_non_segnala(tmp_path):
    root = _wiki(tmp_path, TESTA_LOG + voce("2026-11-02", "b") + voce("2026-11-05", "c"))
    findings, entro = derivati.check_ordine_log(root, 7)
    assert findings == [] and entro == 0
    assert _cli(root, "--strict").returncode == 0


def test_4bf_ordine_rotto_fallisce_il_lint(tmp_path):
    root = _wiki(tmp_path, TESTA_LOG + voce("2026-11-09", "recente") + voce("2026-09-01", "molto vecchia"))
    findings, _ = derivati.check_ordine_log(root, 7)
    assert len(findings) == 1
    f = findings[0]
    assert f["check"] == "4bf" and f["data"] == "2026-09-01" and f["precedente"] == "2026-11-09"
    assert f["giorni"] == 69
    out = _cli(root, "--strict")
    assert out.returncode == 1 and "[4bf]" in out.stdout and "[ERROR]" in out.stdout
    # senza --strict il comando riporta ma non fallisce
    assert _cli(root).returncode == 0


def test_4bf_tolleranza_di_sette_giorni(tmp_path):
    log = TESTA_LOG + voce("2026-11-10", "avanti") + voce("2026-11-03", "indietro di 7")
    root = _wiki(tmp_path, log)
    findings, entro = derivati.check_ordine_log(root, 7)
    assert findings == [] and entro == 1
    findings, entro = derivati.check_ordine_log(root, 6)
    assert len(findings) == 1 and entro == 0
    assert _cli(root, "--strict", "--tolleranza", "6").returncode == 1
    assert _cli(root, "--strict").returncode == 0


def test_4bf_riconosce_anche_le_voci_a_titolo(tmp_path):
    log = "# Log\n\n## 2026-11-10 10:00 — nuova\n\ntesto\n\n## 2026-10-01 10:00 — vecchia dopo\n\ntesto\n"
    findings, _ = derivati.check_ordine_log(_wiki(tmp_path, log), 7)
    assert [f["data"] for f in findings] == ["2026-10-01"]


def test_4bf_senza_log_nessun_finding(tmp_path):
    assert derivati.check_ordine_log(tmp_path, 7) == ([], 0)


def test_4bf_il_confronto_e_con_la_data_massima_non_con_la_precedente(tmp_path):
    log = TESTA_LOG + voce("2026-11-20", "a") + voce("2026-11-10", "b") + voce("2026-11-09", "c")
    findings, _ = derivati.check_ordine_log(_wiki(tmp_path, log), 7)
    assert [f["data"] for f in findings] == ["2026-11-10", "2026-11-09"]
    assert all(f["precedente"] == "2026-11-20" for f in findings)


def _index(dichiarato: int, voci: int, dopo: str = "## Altro\n\n- [[fuori-sezione]]\n") -> str:
    corpo = "".join(f"- [[fonte-{i}]]\n" for i in range(voci))
    return f"# Index\n\n## Sources ({dichiarato})\n\n<!-- commento -->\n{corpo}\n{dopo}"


def test_4bg_contatore_corretto_accettato(tmp_path):
    root = _wiki(tmp_path, index=_index(3, 3))
    assert derivati.check_contatore_sources(root) is None
    assert "contatore Sources coerente" in _cli(root, "--strict").stdout
    assert _cli(root, "--strict").returncode == 0


def test_4bg_scarto_segnalato_con_i_due_valori(tmp_path):
    root = _wiki(tmp_path, index=_index(2, 5))
    f = derivati.check_contatore_sources(root)
    assert f == {"check": "4bg", "dichiarato": 2, "reale": 5, "scarto": 3}
    out = _cli(root, "--strict")
    assert out.returncode == 1
    assert "[WARNING][sources-contatore][4bg]" in out.stdout and "Sources (2)" in out.stdout and "5 voci" in out.stdout


def test_4bg_contatore_superiore_alle_voci(tmp_path):
    f = derivati.check_contatore_sources(_wiki(tmp_path, index=_index(9, 4)))
    assert f["scarto"] == -5


def test_4bg_conta_solo_la_sezione_sources(tmp_path):
    # la voce dopo «## Altro» non entra nel conteggio; ultima sezione senza intestazione successiva
    assert derivati.check_contatore_sources(_wiki(tmp_path, index=_index(2, 2))) is None
    solo = "# Index\n\n## Sources (1)\n\n- [[a]]\n- [[b]]\n"
    assert derivati.check_contatore_sources(_wiki(tmp_path, index=solo))["reale"] == 2


def test_4bg_senza_sezione_o_senza_index_nessun_finding(tmp_path):
    assert derivati.check_contatore_sources(tmp_path) is None
    assert derivati.check_contatore_sources(_wiki(tmp_path, index="# Index\n\n## Altro\n")) is None


def test_json_riporta_entrambi_i_check(tmp_path):
    root = _wiki(tmp_path, TESTA_LOG + voce("2026-11-20", "a") + voce("2026-10-01", "b"), _index(1, 2))
    dati = json.loads(_cli(root, "--json").stdout)
    assert {f["check"] for f in dati["findings"]} == {"4bf", "4bg"}


def test_4bg_sul_repository_reale_e_in_sola_lettura():
    """Il check gira sui file reali senza modificarli e produce solo finding ben formati."""
    index = RADICE / "wiki" / "index.md"
    prima = index.read_bytes()
    f = derivati.check_contatore_sources(RADICE)
    assert f is None or {"dichiarato", "reale", "scarto"} <= set(f)
    assert index.read_bytes() == prima


def test_registrato_nel_runner_deterministico():
    mod = _carica("run_det_t", TOOLS / "lint" / "run-deterministic.py")
    voci = [c for c in mod.CHECKS if "4bf" in c[0]]
    assert len(voci) == 1 and voci[0][0] == ("4bf", "4bg")
    assert (TOOLS / "lint" / voci[0][2]).is_file()
    assert "{root}" in voci[0][3]
