#!/usr/bin/env python3
"""
session_doc.py — modulo di supporto per session-sync (EP-069 US-313 TSK-719).

Offre tre primitive riutilizzabili:

  scan_secrets(text)          -> list[dict]
      Ricerca pattern di secret nel testo. Ritorna una lista di match con
      {pattern_name, start, end, replacement}.

  redact_secrets(text)        -> tuple[str, int]
      Applica redazione in-place. Ritorna (text_redatto, n_match).

  load_manifest(path)         -> dict
      Carica raw/.extraction-manifest.json. Ritorna {} se assente o malformato.

  update_manifest(path, key, entry) -> None
      Merge non distruttivo: legge il JSON, aggiunge/sovrascrive la chiave,
      riscrive l'intero file. Non tocca le entry altrui.

  check_integrity(md_text)    -> tuple[bool, str]
      Verifica frontmatter parseable + 7 header obbligatori nell'ordine atteso.
      Ritorna (ok: bool, detail: str).

  check_duplicate(manifest, fs_dir, session_label) -> str | None
      Controlla dedup doppio (manifest + filesystem).
      Ritorna None se ok, oppure un messaggio di errore da restituire al chiamante.

Stdlib pura: no dipendenze esterne.
Cross-platform: nessun ':' in nomi file generati.
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Secret scan
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("bearer_token",   re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)),
    ("jwt",            re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    ("pat",            re.compile(r"[Pp][Aa][Tt][\s_-]*[:=]\s*[A-Za-z0-9]{20,}")),
    ("secret_generic", re.compile(r"[Ss][Ee][Cc][Rr][Ee][Tt][\s_-]*[:=]\s*[^\s]{10,}", re.IGNORECASE)),
    ("token_generic",  re.compile(r"[Tt][Oo][Kk][Ee][Nn][\s_-]*[:=]\s*[^\s]{10,}", re.IGNORECASE)),
]

_REDACTION = "[secret redatto]"


def scan_secrets(text: str) -> list[dict]:
    """
    Ricerca tutti i pattern di secret nel testo.

    Ritorna una lista di dict:
        {pattern_name: str, start: int, end: int, matched: str}
    ordinati per posizione nel testo (start crescente).
    """
    results: list[dict] = []
    for name, pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            results.append(
                {
                    "pattern_name": name,
                    "start": m.start(),
                    "end": m.end(),
                    "matched": m.group(0),
                }
            )
    results.sort(key=lambda x: x["start"])
    return results


def redact_secrets(text: str) -> tuple[str, int]:
    """
    Sostituisce i secret trovati con `[secret redatto]`.

    Applica la sostituzione partendo dalla fine del testo per non spostare
    gli offset dei match precedenti.

    Ritorna (text_redatto, n_match).
    """
    matches = scan_secrets(text)
    if not matches:
        return (text, 0)

    # Sostituisci partendo dal match piu' tardo
    for m in reversed(matches):
        text = text[: m["start"]] + _REDACTION + text[m["end"] :]
    return (text, len(matches))


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def load_manifest(path: str | Path) -> dict:
    """
    Carica il manifest JSON. Ritorna {} se assente o malformato.
    Non lancia eccezioni.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        content = p.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return {}


def update_manifest(path: str | Path, key: str, entry: dict) -> None:
    """
    Aggiunge o aggiorna la chiave `key` nel manifest JSON.
    Merge non distruttivo: non tocca le entry altrui.
    Riscrive l'intero file.

    Lancia OSError se la scrittura fallisce.
    """
    p = Path(path)
    manifest = load_manifest(p)
    manifest[key] = entry
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Integrity check
# ---------------------------------------------------------------------------

_REQUIRED_H2 = [
    "## Sommario",
    "## Decisioni prese",
    "## Artefatti toccati",
    "## Task avanzati",
    "## Gap aperti",
    "## Insight",
    "## Token cost",
]


def check_integrity(md_text: str) -> tuple[bool, str]:
    """
    Verifica integrità del documento prodotto da session-sync.

    Controlli:
      A. Frontmatter YAML parseable (delimitato da '---').
      B. I 7 header ## obbligatori presenti nell'ordine atteso.

    Ritorna (True, "") se tutto ok, oppure (False, "<dettaglio errore>").
    """
    # A. Frontmatter
    if md_text.startswith("---"):
        try:
            parts = md_text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                # Verifica parseable con mini-parser YAML (solo chiave: valore)
                _parse_simple_yaml(fm_text)
            else:
                return (False, "Frontmatter non chiuso: mancano i delimitatori '---'.")
        except ValueError as e:
            return (False, f"Frontmatter non parseable: {e}")
    else:
        return (False, "Frontmatter assente (il documento deve iniziare con '---').")

    # B. Header obbligatori nell'ordine
    body_lines = md_text.split("\n")
    h2_found = [ln.rstrip() for ln in body_lines if ln.startswith("## ")]

    # Verifica ordine: ogni header richiesto deve apparire nell'ordine giusto
    h2_iter = iter(h2_found)
    for required in _REQUIRED_H2:
        found = False
        for h in h2_iter:
            if h == required:
                found = True
                break
        if not found:
            return (False, f"Header '## ...' mancante o fuori ordine: '{required}'.")

    return (True, "")


def _parse_simple_yaml(text: str) -> dict:
    """
    Parser YAML minimale: accetta solo `chiave: valore` e liste semplici.
    Usato solo per verificare che il frontmatter sia parseable senza lanci di
    eccezioni da librerie esterne.
    Lancia ValueError se trova una struttura non parseable (es. tab in YAML).
    """
    result: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in line:
            raise ValueError(f"Tab character non ammesso in YAML: {line!r}")
        if ":" in stripped:
            key, _, _ = stripped.partition(":")
            result[key.strip()] = True  # semplificato: verifica solo struttura
    return result


# ---------------------------------------------------------------------------
# Dedup check
# ---------------------------------------------------------------------------

def check_duplicate(manifest: dict, sessions_dir: str | Path, session_label: str) -> str | None:
    """
    Controlla dedup doppio (Accordo #8):
      Layer A — manifest lookup
      Layer B — filesystem check

    Ritorna None se ok (nessun duplicato), oppure una stringa di errore.
    """
    manifest_key = f"raw/sessions/{session_label}"

    # Layer A — manifest lookup
    if manifest_key in manifest:
        return (
            f"session-sync: entry duplicata nel manifest per {session_label} — "
            "skip scrittura. Causa: questa sessione e' gia' stata chiusa in precedenza."
        )

    # Layer B — filesystem check
    fs_path = Path(sessions_dir) / f"{session_label}.md"
    if fs_path.exists():
        return (
            f"session-sync: file {fs_path} gia' presente su disco ma assente dal manifest. "
            "Stato inconsistente — rifiuto scrittura per evitare sovrascrittura. "
            "Azione richiesta: verificare manualmente il file e il manifest."
        )

    return None  # tutto ok


# ---------------------------------------------------------------------------
# CLI (sola diagnostica, non fa scritture)
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="session_doc.py",
        description="Diagnostica session-doc: secret scan + integrity check.",
    )
    sub = parser.add_subparsers(dest="cmd")

    scan_p = sub.add_parser("scan", help="Scansiona i secret in un file")
    scan_p.add_argument("file", help="Percorso del file da scansionare")

    check_p = sub.add_parser("check", help="Verifica integrità di un file sessione")
    check_p.add_argument("file", help="Percorso del file .md da verificare")

    manifest_p = sub.add_parser("manifest", help="Mostra il manifest")
    manifest_p.add_argument("path", help="Percorso del manifest JSON")

    args = parser.parse_args()

    if args.cmd == "scan":
        text = Path(args.file).read_text(encoding="utf-8")
        matches = scan_secrets(text)
        if matches:
            for m in matches:
                print(f"[{m['pattern_name']}] pos {m['start']}-{m['end']}: {m['matched'][:40]!r}…")
        else:
            print("Nessun secret rilevato.")
    elif args.cmd == "check":
        text = Path(args.file).read_text(encoding="utf-8")
        ok, detail = check_integrity(text)
        if ok:
            print("OK — integrità verificata.")
        else:
            print(f"FAIL — {detail}")
            sys.exit(1)
    elif args.cmd == "manifest":
        m = load_manifest(args.path)
        print(json.dumps(m, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _main()
