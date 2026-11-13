"""Test di verify_vendor con piu' copie in vendor/ (default, --vendor, --all, manomissione)."""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "pocock" / "verify_vendor.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_default_invariato():
    r = run()
    assert r.returncode == 0, r.stdout
    assert "mattpocock-skills" in r.stdout and "0 differenze" in r.stdout


def test_vendor_emilkowalski():
    r = run("--vendor", "emilkowalski-skills")
    assert r.returncode == 0, r.stdout
    assert "9 file dichiarati" in r.stdout


def test_all():
    r = run("--all")
    assert r.returncode == 0, r.stdout
    assert "mattpocock-skills" in r.stdout and "emilkowalski-skills" in r.stdout


def test_file_manomesso(tmp_path):
    copia = tmp_path / "emilkowalski-skills"
    shutil.copytree(ROOT / "vendor" / "emilkowalski-skills", copia)
    with open(copia / "skills" / "break-ui" / "SKILL.md", "ab") as f:
        f.write(b"\nmodifica\n")
    r = run("--vendor", str(copia))
    assert r.returncode == 1
    assert "modificato: skills/break-ui/SKILL.md" in r.stdout


def test_file_non_dichiarato(tmp_path):
    copia = tmp_path / "emilkowalski-skills"
    shutil.copytree(ROOT / "vendor" / "emilkowalski-skills", copia)
    (copia / "extra.md").write_text("x", encoding="utf-8")
    r = run("--vendor", str(copia))
    assert r.returncode == 1
    assert "non dichiarato: extra.md" in r.stdout


def test_all_senza_cartella_vendor_niente_traceback(tmp_path):
    """Derivata aggiornata prima di EP-090: vendor/ assente -> messaggio ed exit 1, non un crash."""
    tools = tmp_path / "tools" / "pocock"
    tools.mkdir(parents=True)
    shutil.copy(SCRIPT, tools / "verify_vendor.py")
    r = subprocess.run([sys.executable, str(tools / "verify_vendor.py"), "--all"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert "vendor/ assente" in r.stdout
