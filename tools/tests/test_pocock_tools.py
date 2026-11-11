"""Test di tools/pocock: verify_vendor, kpi_pilota e bilancio_n1 su fixture sintetiche."""
import datetime as dt
import pathlib
import subprocess
import sys

import pytest

POCOCK = pathlib.Path(__file__).resolve().parents[1] / "pocock"
sys.path.insert(0, str(POCOCK))

import bilancio_n1  # noqa: E402
import kpi_pilota  # noqa: E402
import verify_vendor  # noqa: E402

yaml = pytest.importorskip("yaml")


def tsk(path, **fm):
    fm.setdefault("type", "task")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(fm, allow_unicode=True) + "---\n# corpo\n", encoding="utf-8")


def test_vendor_copia_fedele():
    r = subprocess.run([sys.executable, str(POCOCK / "verify_vendor.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert "0 differenze" in r.stdout


def test_blob_sha_noto():
    # impronta git del blob vuoto
    assert verify_vendor.blob_sha(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_kpi_su_fixture(tmp_path):
    kanban, reg, rep = tmp_path / "kanban", tmp_path / "reg", tmp_path / "reports"
    rep.mkdir(); reg.mkdir()
    tsk(kanban / "TSK-001.md", id="TSK-001", layer="fe", status="done", closed_at="2026-10-05",
        created="2026-10-01", title="Nuova pagina", review_status="passed")
    tsk(kanban / "TSK-002.md", id="TSK-002", layer="fe", status="done", closed_at="2026-10-06",
        created="2026-10-02", title="Fix tooltip", regression_test="tests/x.spec")
    tsk(kanban / "TSK-003.md", id="TSK-003", layer="be", status="done", closed_at="2026-10-06",
        created="2026-10-02", title="Bug sul login")
    tsk(kanban / "TSK-004.md", id="TSK-004", layer="fe", status="todo", created="2026-09-01", title="Fuori finestra")
    (rep / "TSK-002-iter-1.json").write_text(
        '{"tsk_id": "TSK-002", "verdict": "pass", "generated_at": "2026-10-06T10:00:00Z"}', encoding="utf-8")
    (rep / "TSK-009-iter-1.json").write_text(
        '{"tsk_id": "TSK-009", "verdict": "conditional", "generated_at": "2026-10-06T10:00:00Z"}', encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "lint.py").write_text("x", encoding="utf-8")
    (reg / "controlli.yaml").write_text(yaml.safe_dump({"controlli": [
        {"data": "2026-10-05", "errore": "e", "controllo": "c", "path": "tools/lint.py"},
        {"data": "2026-10-05", "errore": "e", "controllo": "c", "path": "tools/mancante.py"}]}), encoding="utf-8")
    (reg / "invenzioni.yaml").write_text(yaml.safe_dump({"casi": [
        {"data": "2026-10-07", "agente": "a", "caso": "x"}, {"data": "2026-01-01", "agente": "a", "caso": "y"}]}),
        encoding="utf-8")

    r = kpi_pilota.kpi(dt.date(2026, 10, 1), dt.date(2026, 11, 1), kanban=kanban, registri=reg, reports=rep,
                       root=tmp_path, layer="fe", con_costo=False)
    assert r["1_copertura_cqrl"]["num"] == 2 and r["1_copertura_cqrl"]["den"] == 2
    assert r["2_tsk_correzione"]["num"] == 2 and r["2_tsk_correzione"]["den"] == 3
    assert r["3_first_pass_cqrl"]["num"] == 1 and r["3_first_pass_cqrl"]["den"] == 2
    assert r["4_bug_con_regressione"]["num"] == 1 and r["4_bug_con_regressione"]["den"] == 2
    assert r["6_controlli"]["valore"] == 1
    assert r["7_invenzioni"]["valore"] == 1
    assert r["8_costo_per_tsk"]["valore"] is None and r["8_costo_per_tsk"]["tsk_chiusi"] == 3


def test_kpi_registri_vuoti_e_assenti(tmp_path):
    kanban, reg, rep = tmp_path / "k", tmp_path / "r", tmp_path / "rep"
    kanban.mkdir(); rep.mkdir(); reg.mkdir()
    (reg / "controlli.yaml").write_text("controlli: []\n", encoding="utf-8")
    r = kpi_pilota.kpi(dt.date(2026, 1, 1), dt.date(2026, 2, 1), kanban=kanban, registri=reg, reports=rep,
                       root=tmp_path)
    assert r["1_copertura_cqrl"]["valore"] is None
    assert r["6_controlli"]["valore"] == 0 and r["7_invenzioni"]["valore"] == 0


def test_bilancio_su_repo_sintetico(tmp_path):
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.org"); git("config", "user.name", "t")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "a.md").write_text("uno due tre quattro", encoding="utf-8")
    git("add", "."); git("commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / ".claude" / "skills" / "a.md").write_text("uno due", encoding="utf-8")
    (tmp_path / ".claude" / "skills" / "nuova.md").write_text("a b c d e f", encoding="utf-8")
    (tmp_path / "altro.md").write_text("ignorato", encoding="utf-8")
    mod, nuovi = bilancio_n1.bilancio(tmp_path, base)
    assert mod == [(".claude/skills/a.md", 4, 2)]
    assert nuovi == [(".claude/skills/nuova.md", 0, 6)]


def test_settings_default_e_config(tmp_path):
    from _config import settings
    assert settings(tmp_path)["kanban_path"] == "management/kanban"
    (tmp_path / "factory.config.yaml").write_text(
        "engineering_practices:\n  enabled: false\n  kanban_path: k\n", encoding="utf-8")
    s = settings(tmp_path)
    assert s["kanban_path"] == "k" and s["analytics_path"] == "analytics/pocock-pilota"
