"""Test per tools/vcs/sm_commit.py — TSK-700.

Verifica i tre casi DoD:
  (a) Messaggio con Co-Authored-By → riga rimossa, avviso su stderr.
  (b) Messaggio con TSK-690 nel subject → token rimosso, avviso su stderr.
  (c) Messaggio con la parola «task» → invariato.

Plus:
  - --dry-run mostra originale e filtrato senza committare.
  - CLI posizionale retro-compatibile.
"""
from __future__ import annotations

import importlib.util
import sys
from io import StringIO
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import dello script (non installato come package)
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent.parent  # repo root / tools/
SM_COMMIT = HERE / "vcs" / "sm_commit.py"

spec = importlib.util.spec_from_file_location("sm_commit", SM_COMMIT)
sm_commit = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(sm_commit)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run_main(argv: list[str], capture_stderr: bool = True):
    """Esegue sm_commit.main() e restituisce (returncode, stderr_text)."""
    old_stderr = sys.stderr
    buf = StringIO()
    if capture_stderr:
        sys.stderr = buf
    try:
        rc = sm_commit.main(argv)
    finally:
        sys.stderr = old_stderr
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# (a) Messaggio con Co-Authored-By — riga deve essere rimossa
# ---------------------------------------------------------------------------

class TestStripAttribution:
    MSG = "feat: aggiunge funzionalita'\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

    def test_dry_run_removes_coauthored_line(self, capsys):
        rc, stderr = run_main(["--dry-run", self.MSG])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Co-Authored-By" not in out.split("--- messaggio filtrato ---")[-1]

    def test_warns_on_stderr(self):
        _, stderr = run_main(["--dry-run", self.MSG])
        assert "Attribution AI rimossa" in stderr
        assert "Co-Authored-By" in stderr

    def test_filtered_message_keeps_subject(self, capsys):
        rc, _ = run_main(["--dry-run", self.MSG])
        out = capsys.readouterr().out
        filtered = out.split("--- messaggio filtrato ---")[-1].strip()
        assert "feat: aggiunge funzionalita'" in filtered


# ---------------------------------------------------------------------------
# (b) Messaggio con TSK-690 nel subject — token deve essere rimosso
# ---------------------------------------------------------------------------

class TestStripFactoryId:
    MSG = "fix: corregge il comportamento di TSK-690 nel flusso"

    def test_dry_run_removes_tsk_token(self, capsys):
        rc, _ = run_main(["--dry-run", self.MSG])
        assert rc == 0
        out = capsys.readouterr().out
        filtered = out.split("--- messaggio filtrato ---")[-1].strip()
        assert "TSK-690" not in filtered

    def test_warns_on_stderr(self):
        _, stderr = run_main(["--dry-run", self.MSG])
        assert "TSK-690" in stderr

    def test_rest_of_subject_preserved(self, capsys):
        run_main(["--dry-run", self.MSG])
        out = capsys.readouterr().out
        filtered = out.split("--- messaggio filtrato ---")[-1].strip()
        assert "fix:" in filtered
        assert "corregge il comportamento" in filtered


# ---------------------------------------------------------------------------
# (c) Messaggio con la parola «task» — deve restare INVARIATO
# ---------------------------------------------------------------------------

class TestNeutralMessage:
    MSG = "refactor: semplifica il task di validazione"

    def test_dry_run_no_modification(self, capsys):
        rc, _ = run_main(["--dry-run", self.MSG])
        assert rc == 0
        out = capsys.readouterr().out
        # Prende solo le righe dopo '--- messaggio filtrato ---' che
        # non siano la nota '[sm_commit] Nessuna modifica...'
        after_label = out.split("--- messaggio filtrato ---")[-1]
        filtered_lines = [
            l for l in after_label.splitlines()
            if l and not l.startswith("[sm_commit]")
        ]
        assert "\n".join(filtered_lines).strip() == self.MSG

    def test_no_warning_on_stderr(self):
        _, stderr = run_main(["--dry-run", self.MSG])
        assert "rimoss" not in stderr

    def test_no_change_note_printed(self, capsys):
        run_main(["--dry-run", self.MSG])
        out = capsys.readouterr().out
        assert "Nessuna modifica" in out


# ---------------------------------------------------------------------------
# Argparse / CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_missing_message_returns_error(self):
        rc, stderr = run_main([])
        assert rc == 1
        assert "obbligatorio" in stderr

    def test_message_flag_accepted(self, capsys):
        rc, _ = run_main(["--dry-run", "--message", "chore: test flag"])
        assert rc == 0

    def test_positional_message_accepted(self, capsys):
        rc, _ = run_main(["--dry-run", "chore: test posizionale"])
        assert rc == 0

    def test_flag_overrides_positional(self, capsys):
        rc, _ = run_main(["--dry-run", "posizionale", "--message", "da flag"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "da flag" in out


# ---------------------------------------------------------------------------
# --dry-run vince sulla modalita' coordinata (dalla derivata portale-servizi)
# ---------------------------------------------------------------------------

class TestDryRunCoordinated:
    @pytest.mark.parametrize("extra", [["--coordinated"], ["--pointer-only"]])
    def test_dry_run_non_entra_nel_ramo_coordinato(self, monkeypatch, capsys, extra):
        def vietato(*_a, **_k):
            raise AssertionError("--dry-run non deve entrare nel ramo coordinato")
        monkeypatch.setattr(sm_commit, "_coordinated_main", vietato)
        rc, _ = run_main(["--dry-run", *extra, "chore: prova"])
        assert rc == 0
        assert "messaggio filtrato" in capsys.readouterr().out
