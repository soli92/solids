"""verifica_flotta: path citati risolti anche contro root della factory e root dell'adapter.

Backport dalla derivata (EP-072): G4 risolveva i path solo contro la cartella passata sulla
riga di comando, e `scripts/x.py` (scritto rispetto alla root della factory, non della skill) risultavano «file assente» pur esistendo: 30 falsi positivi misurati sulla derivata.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_VF = Path(__file__).resolve().parents[1] / "refactor" / "verifica_flotta.py"

_SKILL = """---
name: s
description: Skill di prova per la risoluzione dei path citati dal gate G4.
---

# s

Usa `scripts/y.py` e delega a `agents/x.md`.
"""
_AGENT = """---
name: x
description: Agente di prova citato dalla skill.
---

# x
"""


def _factory(tmp: Path) -> Path:
    (tmp / "factory.config.yaml").write_text('pattern_version: "2.44"\n')
    (tmp / "scripts").mkdir()
    (tmp / "scripts" / "y.py").write_text("print(1)\n")
    (tmp / ".claude" / "agents").mkdir(parents=True)
    (tmp / ".claude" / "skills").mkdir(parents=True)
    (tmp / ".claude" / "agents" / "x.md").write_text(_AGENT)
    (tmp / ".claude" / "skills" / "s.md").write_text(_SKILL)
    return tmp


def test_path_citati_risolti_contro_factory_e_adapter(tmp_path):
    root = _factory(tmp_path)
    r = subprocess.run([sys.executable, str(_VF), str(root / ".claude" / "skills")],
                       capture_output=True, text=True)
    g4 = [l for l in r.stdout.splitlines() if " G4 " in l]
    assert g4 and all("[OK]" in l for l in g4), r.stdout
    assert "file assente" not in r.stdout


def test_path_davvero_assente_resta_errore(tmp_path):
    root = _factory(tmp_path)
    (root / ".claude" / "skills" / "s.md").write_text(_SKILL.replace("scripts/y.py", "scripts/manca.py"))
    r = subprocess.run([sys.executable, str(_VF), str(root / ".claude" / "skills")],
                       capture_output=True, text=True)
    assert "manca.py" in r.stdout and r.returncode == 1, r.stdout


_MR = Path(__file__).resolve().parents[1] / "refactor" / "mappa_riferimenti.py"


def _agente(root: Path, corpo: str) -> None:
    (root / ".claude" / "agents" / "x.md").write_text(_AGENT + "\n" + corpo + "\n")


def _v9(root: Path) -> list[str]:
    r = subprocess.run([sys.executable, str(_MR), str(root / ".claude"), "--gate",
                        "--injection-glob", "agents/*.md"], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if "[V-9]" in l]


def test_v9_path_dalla_root_della_factory_e_raggiungibile(tmp_path):
    """La cwd di un subagent e' la root: `wiki/log.md` scritto da li' non e' una foglia persa."""
    root = _factory(tmp_path)
    (root / "wiki").mkdir()
    (root / "wiki" / "log.md").write_text("# log\n")
    _agente(root, "Appende a `wiki/log.md`.")
    assert _v9(root) == []


def test_v9_foglia_dell_adapter_senza_forma_claude_resta_violazione(tmp_path):
    root = _factory(tmp_path)
    (root / ".claude" / "skills" / "references").mkdir()
    (root / ".claude" / "skills" / "references" / "f.md").write_text("# f\n")
    _agente(root, "Leggi `skills/references/f.md`.")
    assert any("skills/references/f.md" in l for l in _v9(root))
