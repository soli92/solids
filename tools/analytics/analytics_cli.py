"""Contratto CLI comune agli strumenti di analytics (US-327).

Gli script bash storici rispondono a un argomento sconosciuto con un messaggio su stderr,
``{"status":"error","error":"unknown argument: <arg>"}`` su stdout ed exit 1. ``argparse``
di default esce con 2 e stdout vuoto: chi legge lo stdout come JSON si troverebbe una stringa
vuota. Questo parser ripristina il contratto «stdout JSON / stderr log / exit code».
"""
from __future__ import annotations

import argparse
import json
import re
import sys


class ContractArgumentParser(argparse.ArgumentParser):
    """``ArgumentParser`` che sugli errori rispetta il contratto degli strumenti di analytics."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)  # lo .sh non accetta abbreviazioni
        super().__init__(*args, **kwargs)

    def error(self, message: str):  # noqa: D401 — firma di argparse
        m = re.match(r"unrecognized arguments: (\S+)", message)
        err = f"unknown argument: {m.group(1)}" if m else message
        print(f"ERRORE: {message}. {self.format_usage().strip()}", file=sys.stderr)
        print(json.dumps({"status": "error", "error": err}))
        sys.exit(1)


def fail(message: str, error: str, code: int = 1):
    """Errore fail-loud: messaggio leggibile su stderr, JSON su stdout."""
    print(message, file=sys.stderr)
    print(json.dumps({"status": "error", "error": error}))
    sys.exit(code)


def jq_numbers(obj):
    """Numeri come li stampa jq: un float intero (1440.0) diventa 1440.

    Serve dove il numero finisce in testo (tabelle Markdown): nel JSON 1440 e 1440.0 sono lo
    stesso valore, in una tabella no.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    if isinstance(obj, dict):
        return {k: jq_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [jq_numbers(v) for v in obj]
    return obj
