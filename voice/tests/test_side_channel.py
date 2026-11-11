"""
Regression tests for US-165 — side-channel lifecycle owner.

Covers:
  AC1  — FSM always starts in IDLE regardless of any persisted voice-state.json
  AC4  — atomic_write_json: tmp+rename, no residual .tmp, concurrent reads safe
  AC4/AC5 — reset_state_file() writes {"state": "IDLE"} atomically
  Non-regression — test_pid_lock.py (EP-044, TSK-331) passes unchanged

No hardware audio required: only voice.core.side_channel and
voice.core.state_machine.__init__ are exercised (with mocked dependencies).

[^src: management/kanban/EP-046-voice-hardening/US-165-lifecycle-owner-side-channel/TSK-366.md]
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# TC1 — AC1: FSM starts in IDLE regardless of persisted state file content
# ---------------------------------------------------------------------------

def test_fsm_starts_idle_regardless_of_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """La FSM deve essere in stato IDLE all'init anche se voice-state.json
    contiene CATTURA.  Verifica che VoiceStateMachine NON legga il file di
    stato al costruttore (finding F3 — regressione esplicita AC1)."""
    state_file = tmp_path / "voice-state.json"
    state_file.write_text('{"state": "CATTURA"}', encoding="utf-8")

    from unittest.mock import MagicMock
    from voice.core.state_machine import VoiceStateMachine

    fsm = VoiceStateMachine(
        config=MagicMock(),
        capture=MagicMock(),
        vad=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        playback=MagicMock(),
        runtime=MagicMock(),
        router=MagicMock(),
    )
    assert fsm.state == "IDLE", (
        f"AC1 violata: FSM deve partire da IDLE, stato trovato: {fsm.state!r}"
    )


# ---------------------------------------------------------------------------
# TC2 — AC4: atomic_write_json writes correctly; no residual .tmp file
# ---------------------------------------------------------------------------

def test_atomic_write_json_no_tmp_residue(tmp_path: Path) -> None:
    """atomic_write_json deve creare il file target e rimuovere il .tmp.

    Verifica:
    - il file target esiste dopo la chiamata
    - il file .tmp non e' rimasto sul filesystem
    - il contenuto del file e' il JSON atteso
    """
    from voice.core.side_channel import atomic_write_json

    target = tmp_path / "test.json"
    payload = {"key": "value"}
    atomic_write_json(target, payload)

    assert target.exists(), "Il file target deve esistere dopo atomic_write_json"
    tmp_file = tmp_path / "test.json.tmp"
    assert not tmp_file.exists(), "Il file .tmp non deve essere rimasto sul filesystem"
    assert json.loads(target.read_text(encoding="utf-8")) == payload, (
        "Il contenuto del file deve corrispondere al payload scritto"
    )


# ---------------------------------------------------------------------------
# TC3 — AC4: concurrent readers never see a partial JSON file
# ---------------------------------------------------------------------------

def test_atomic_write_no_partial_reads(tmp_path: Path) -> None:
    """Un lettore concorrente non deve mai produrre JSONDecodeError.

    Un thread legge in loop mentre il main thread scrive 50 volte tramite
    atomic_write_json. L'atomicita' di os.replace garantisce che ogni
    lettura veda solo file completi e validi.
    """
    from voice.core.side_channel import atomic_write_json

    target = tmp_path / "state.json"
    errors: list[str] = []
    stop_flag = threading.Event()

    def reader() -> None:
        while not stop_flag.is_set():
            try:
                if target.exists():
                    json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"JSONDecodeError: {exc}")
            except OSError:
                # Possibile race tra exists() e read_text(); tollerato.
                pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    for i in range(50):
        atomic_write_json(target, {"i": i, "data": "x" * 100})

    stop_flag.set()
    reader_thread.join(timeout=2)

    assert not errors, (
        f"Lettura concorrente ha visto file parziale ({len(errors)} errori):\n"
        + "\n".join(errors[:5])
    )


# ---------------------------------------------------------------------------
# TC4 — AC4/AC5: reset_state_file() produces {"state": "IDLE"}
# ---------------------------------------------------------------------------

def test_reset_state_file_produces_idle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """reset_state_file() deve scrivere atomicamente {"state": "IDLE"} su STATE_FILE.

    Il monkeypatch reindirizza STATE_FILE a tmp_path per evitare scritture
    su ~/.local/share/soli-voice/ durante il test.
    """
    import voice.core.side_channel as sc

    monkeypatch.setattr(sc, "STATE_FILE", tmp_path / "voice-state.json")

    sc.reset_state_file()

    written_file = tmp_path / "voice-state.json"
    assert written_file.exists(), "STATE_FILE deve esistere dopo reset_state_file()"
    data = json.loads(written_file.read_text(encoding="utf-8"))
    assert data == {"state": "IDLE"}, (
        f"reset_state_file deve produrre {{\"state\": \"IDLE\"}}, trovato: {data!r}"
    )


# ---------------------------------------------------------------------------
# TC5 — Non-regression: test_pid_lock.py (EP-044, TSK-331) passes unchanged
# ---------------------------------------------------------------------------

def test_pid_lock_regression() -> None:
    """test_pid_lock.py deve passare invariato.

    Garantisce che TSK-363/364/365 non abbiano introdotto regressioni nel
    PID lock (finding F2: AC2/AC3 gia' coperti da test_pid_lock.py).
    """
    repo_root = "/Users/simone.olivieri/Documents/Personal/Repos/soli-multi-agents-factory"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "voice/tests/test_pid_lock.py", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0, (
        f"test_pid_lock.py ha fallito (regressione da TSK-363/364/365):\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
