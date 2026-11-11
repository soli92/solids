"""Colorazione output TTY-aware, cross-platform.

Rispetta NO_COLOR (https://no-color.org) e FORCE_COLOR. Disabilita
automaticamente i codici ANSI quando lo stream non e' un terminale
(es. redirezione su file), cosi' l'output resta pulito nelle pipe.
"""
from __future__ import annotations

import os
import sys
from typing import IO


def _color_enabled(stream: IO) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return bool(stream.isatty())
    except Exception:
        return False


class Color:
    """Helper di colorazione. `enabled=None` -> auto-detect su stdout."""

    _CODES = {
        "red": "0;31",
        "yellow": "1;33",
        "green": "0;32",
        "cyan": "0;36",
    }

    def __init__(self, enabled: bool | None = None, stream: IO | None = None) -> None:
        stream = stream or sys.stdout
        self.enabled = _color_enabled(stream) if enabled is None else enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def red(self, text: str) -> str:
        return self._wrap(self._CODES["red"], text)

    def yellow(self, text: str) -> str:
        return self._wrap(self._CODES["yellow"], text)

    def green(self, text: str) -> str:
        return self._wrap(self._CODES["green"], text)

    def cyan(self, text: str) -> str:
        return self._wrap(self._CODES["cyan"], text)


# Istanza di default (auto-detect su stdout)
color = Color()
