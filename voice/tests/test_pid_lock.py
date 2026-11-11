"""
Unit tests for the pid_lock() context manager — TSK-331 (US-159).

Covers 4 acceptance criteria:
  AC2  — doppia istanza: processo vivo → SystemExit codice != 0, PID in stderr
  AC3  — stale lock: file sovrascritto con PID corrente, nessuna SystemExit
  AC4  — cleanup: PID file rimosso dopo uscita dal context manager
  AC6  — auto-crea directory: mkdir -p implicito prima della scrittura

Nessun hardware audio coinvolto: i test importano solo `pid_lock` da voice.app,
che dipende esclusivamente da stdlib (os, pathlib, contextlib, sys).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from voice.app import pid_lock


# ---------------------------------------------------------------------------
# AC2 — doppia istanza: processo vivo → SystemExit != 0 + PID in stderr
# ---------------------------------------------------------------------------

def test_pid_lock_alive_process_exits_with_nonzero_code(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Se il PID file contiene il PID del processo corrente (sicuramente vivo),
    pid_lock deve sollevare SystemExit con codice != 0."""
    pid_file = tmp_path / "voice.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        with pid_lock(pid_file):
            pass  # must not be reached

    assert exc_info.value.code != 0


def test_pid_lock_alive_process_stderr_contains_pid(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Se il PID file contiene il PID del processo corrente (sicuramente vivo),
    il messaggio su stderr deve includere quel PID."""
    pid_file = tmp_path / "voice.pid"
    own_pid = os.getpid()
    pid_file.write_text(str(own_pid), encoding="utf-8")

    with pytest.raises(SystemExit):
        with pid_lock(pid_file):
            pass

    captured = capsys.readouterr()
    assert str(own_pid) in captured.err


# ---------------------------------------------------------------------------
# AC3 — stale lock: nonexistent PID → file overwritten, no SystemExit
# ---------------------------------------------------------------------------

def test_pid_lock_stale_lock_does_not_raise(tmp_path: Path) -> None:
    """Se il PID file contiene un PID inesistente (stale lock),
    pid_lock non deve sollevare SystemExit."""
    pid_file = tmp_path / "voice.pid"
    pid_file.write_text("99999999", encoding="utf-8")

    # Must not raise anything
    with pid_lock(pid_file):
        pass


def test_pid_lock_stale_lock_overwrites_with_current_pid(tmp_path: Path) -> None:
    """Dopo l'acquisizione del lock su stale lock, il file deve contenere
    il PID del processo corrente, non il valore precedente."""
    pid_file = tmp_path / "voice.pid"
    pid_file.write_text("99999999", encoding="utf-8")

    with pid_lock(pid_file):
        content = pid_file.read_text(encoding="utf-8").strip()
        assert content == str(os.getpid()), (
            f"Atteso PID corrente {os.getpid()}, trovato {content!r}"
        )


# ---------------------------------------------------------------------------
# AC4 — cleanup: PID file removed after exiting context manager
# ---------------------------------------------------------------------------

def test_pid_lock_removes_pid_file_on_exit(tmp_path: Path) -> None:
    """Dopo l'uscita dal blocco `with pid_lock(...)`, il PID file deve essere
    stato rimosso (cleanup garantito dal finally interno)."""
    pid_file = tmp_path / "voice.pid"

    with pid_lock(pid_file):
        assert pid_file.exists(), "Il PID file deve esistere all'interno del context"

    assert not pid_file.exists(), "Il PID file deve essere rimosso dopo l'uscita dal context"


def test_pid_lock_pid_file_exists_during_context(tmp_path: Path) -> None:
    """Durante l'esecuzione del blocco `with`, il PID file deve esistere
    e contenere il PID del processo corrente."""
    pid_file = tmp_path / "voice.pid"

    with pid_lock(pid_file):
        assert pid_file.exists()
        assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())


# ---------------------------------------------------------------------------
# AC6 — auto-create directory: implicit mkdir -p before write
# ---------------------------------------------------------------------------

def test_pid_lock_creates_missing_parent_directory(tmp_path: Path) -> None:
    """pid_lock deve creare la directory padre se non esiste,
    senza sollevare FileNotFoundError."""
    nested_dir = tmp_path / "nonexistent" / "subdir"
    pid_file = nested_dir / "voice.pid"

    assert not nested_dir.exists(), "La directory non deve preesistere"

    with pid_lock(pid_file):
        assert nested_dir.exists(), "La directory deve essere stata creata"
        assert pid_file.exists(), "Il PID file deve essere stato creato"


def test_pid_lock_created_directory_contains_correct_pid(tmp_path: Path) -> None:
    """Dopo la creazione automatica della directory, il PID file deve contenere
    il PID del processo corrente."""
    nested_dir = tmp_path / "auto" / "created"
    pid_file = nested_dir / "voice.pid"

    with pid_lock(pid_file):
        content = pid_file.read_text(encoding="utf-8").strip()
        assert content == str(os.getpid())
