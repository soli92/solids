"""vcs_tooling.submodule_scope e factory_name da project.name (EP-072, ritorno dalla derivata).

La derivata ha 63 submodule e ne dichiara 4 in code_paths[]: i suoi strumenti lavoravano su
tutti, quelli del master solo sui dichiarati. Lo scope rende la scelta esplicita in config.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vcs"))
from smlib.factory_config import factory_name, submodule_scope  # noqa: E402
from smlib.submodule import default_targets  # noqa: E402

_GM = "".join(f'[submodule "r/{n}"]\n\tpath = r/{n}\n\turl = https://example.invalid/{n}\n' for n in ("a", "b", "c"))
_CFG = """project:
  name: derivata-di-prova
code_paths:
  - name: b
    path: r/b
    vcs:
      mode: submodule
"""


def _root(tmp: Path, extra: str = "") -> Path:
    (tmp / ".gitmodules").write_text(_GM)
    (tmp / "factory.config.yaml").write_text(_CFG + extra)
    return tmp


def test_default_solo_i_dichiarati(tmp_path):
    root = _root(tmp_path)
    assert submodule_scope(root) == "code_paths"
    assert default_targets(root) == ["r/b"]


def test_scope_gitmodules_tutti_in_ordine(tmp_path):
    root = _root(tmp_path, "vcs_tooling:\n\n  submodule_scope: gitmodules   # tutti\n")
    assert submodule_scope(root) == "gitmodules"
    assert default_targets(root) == ["r/a", "r/b", "r/c"]


def test_valore_sconosciuto_ricade_sul_default(tmp_path):
    root = _root(tmp_path, "vcs_tooling:\n  submodule_scope: tutto\n")
    assert default_targets(root) == ["r/b"]


def test_factory_name_da_project(tmp_path):
    assert factory_name(_root(tmp_path)) == "derivata-di-prova"


def _modulo(nome: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(nome, Path(__file__).resolve().parents[1] / "vcs" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_target_scelto_quando_i_candidati_sono_piu_d_uno(tmp_path):
    root = _root(tmp_path, "vcs_tooling:\n  submodule_scope: gitmodules\n  default_target: c\n")
    for nome in ("sm_checkout", "sm_update"):
        assert _modulo(nome)._resolve_target(root, "") == "r/c"
        assert _modulo(nome)._resolve_target(root, "a") == "r/a"   # --target esplicito vince


def test_senza_default_target_piu_candidati_e_errore(tmp_path):
    root = _root(tmp_path, "vcs_tooling:\n  submodule_scope: gitmodules\n")
    assert _modulo("sm_checkout")._resolve_target(root, "") is None
