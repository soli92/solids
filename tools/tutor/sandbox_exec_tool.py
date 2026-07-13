"""
sandbox_exec_tool.py — subprocess isolato per esecuzione snippet Python.

Tool che abilita le asserzioni L1 del tutor: esegue il codice e riporta
l'output reale (exit_code, stdout, stderr, elapsed_ms, timed_out).

Solo stdlib Python 3.10+. Nessuna dipendenza esterna.

Mini-CLI:
    echo "print('hello')" | python3 tools/tutor/sandbox_exec_tool.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Limite assoluto non overridabile per timeout_s
_MAX_TIMEOUT_S: float = 30.0
_MAX_STDOUT_CHARS: int = 4096
_MAX_STDERR_CHARS: int = 1024


def _get_repo_root() -> Path:
    """
    Risale dal CWD cercando .git/ o factory.config.yaml.

    Returns:
        Path al root del repo, oppure CWD se non trovato.
    """
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "factory.config.yaml").exists():
            return candidate
    # Fallback al CWD se non trovato
    return current


def _truncate(text: str, max_chars: int, marker: str = "[...troncato]") -> str:
    """Tronca text a max_chars aggiungendo marker se necessario."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + marker


def execute_snippet(
    code: str,
    timeout_s: float = 10.0,
    working_dir: str | None = None,
) -> dict:
    """
    Esegue uno snippet Python in subprocess isolato.

    Args:
        code: codice Python da eseguire (stringa)
        timeout_s: timeout in secondi (default 10s; massimo 30s, clamp silenzioso)
        working_dir: directory di lavoro (default: repo root)

    Returns:
        {
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "elapsed_ms": float,
            "timed_out": bool,
        }
    """
    # Clamp silenzioso del timeout al massimo consentito
    effective_timeout = min(float(timeout_s), _MAX_TIMEOUT_S)

    # Directory di lavoro
    cwd = Path(working_dir).resolve() if working_dir else _get_repo_root()

    tmp_path: Path | None = None
    exit_code: int = -1
    stdout_text: str = ""
    stderr_text: str = ""
    elapsed_ms: float = 0.0
    timed_out: bool = False

    try:
        # 1. Scrive il codice in file temporaneo
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = Path(tmp_file.name)

        # 2. Esegue il subprocess con timeout
        t_start = time.monotonic()
        try:
            result = subprocess.run(
                ["python3", str(tmp_path)],
                capture_output=True,
                timeout=effective_timeout,
                cwd=str(cwd),
            )
            elapsed_ms = (time.monotonic() - t_start) * 1000.0

            # 3. Cattura output
            exit_code = result.returncode
            raw_stdout = result.stdout.decode("utf-8", errors="replace")
            raw_stderr = result.stderr.decode("utf-8", errors="replace")

            # 4. Tronca a limiti di sicurezza
            stdout_text = _truncate(raw_stdout, _MAX_STDOUT_CHARS)
            stderr_text = _truncate(raw_stderr, _MAX_STDERR_CHARS)

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.monotonic() - t_start) * 1000.0
            timed_out = True
            exit_code = -1
            stdout_text = ""
            stderr_text = "TIMEOUT"

    finally:
        # 5. Cleanup file temporaneo — nessun leak
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return {
        "exit_code": exit_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "elapsed_ms": round(elapsed_ms, 3),
        "timed_out": timed_out,
    }


if __name__ == "__main__":
    # Mini-CLI: legge codice da stdin e stampa il risultato JSON.
    # Utilizzo:
    #   echo "print('hello')" | python3 tools/tutor/sandbox_exec_tool.py
    code_input = sys.stdin.read()
    if not code_input.strip():
        print(
            json.dumps(
                {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Nessun codice fornito su stdin.",
                    "elapsed_ms": 0.0,
                    "timed_out": False,
                }
            )
        )
        sys.exit(1)

    output = execute_snippet(code_input)
    print(json.dumps(output, ensure_ascii=False, indent=2))
