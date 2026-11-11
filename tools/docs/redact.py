#!/usr/bin/env python3
"""Controllo di redazione: cerca nel testo pattern che somigliano a segreti.

Interfaccia usata dai generatori di documentazione:

    scan(text) -> list[Finding]
    assert_clean(text, label) -> None   (solleva RedactionError)

L'excerpt di ogni Finding è già mascherato: il valore trovato non compare mai per intero.
Solo libreria standard.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import List


class RedactionError(Exception):
    """Il testo contiene pattern di segreti."""

    def __init__(self, label: str, findings: "List[Finding]"):
        self.label = label
        self.findings = findings
        righe = "\n".join(
            "  %s:%d [%s] %s" % (label, f.line, f.kind, f.excerpt) for f in findings
        )
        super().__init__("redazione: %d finding in %s\n%s" % (len(findings), label, righe))


@dataclass
class Finding:
    kind: str
    line: int
    excerpt: str  # già mascherato


# (nome, regex). Le regex lavorano riga per riga. Se c'è il gruppo `v` è il valore del
# segreto: solo quello viene mascherato nell'excerpt e controllato contro i segnaposto.
_PATTERNS = [
    ("ado-pat", re.compile(r"(?<![A-Za-z0-9])(?=[a-z2-7]*[2-7])[a-z2-7]{52}(?![A-Za-z0-9])")),
    ("github-token", re.compile(r"\b(?:gh[po]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.eyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]*")),
    ("chiave-privata", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("password", re.compile(r"password\s*[:=]\s*(?P<v>\S+)", re.IGNORECASE)),
    ("authorization", re.compile(r"Authorization:\s*(?:Basic|Bearer)\s+(?P<v>\S+)", re.IGNORECASE)),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("token", re.compile(r"token\s*[:=]\s*['\"]?(?P<v>[A-Za-z0-9_\-]{20,})", re.IGNORECASE)),
]

# Valori che indicano un segnaposto o un riferimento a una variabile, non un segreto:
# <token>, $TOKEN, ${TOKEN}, $(cmd), %VAR%, [REDACTED], ***, xxxx, ...
def _is_placeholder(value: str) -> bool:
    v = value.strip("`'\"|,;.:)")
    if not v:
        return True
    if v[0] in "<$%{[(*\\":
        return True
    # chiamata di funzione che costruisce il valore: base64(":" + PAT), btoa(...)
    if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*\(", v):
        return True
    # annotazione di tipo (readonly DB_PASSWORD: string) e valori d'esempio dichiarati
    if v.lower() in _EXAMPLE_VALUES:
        return True
    return bool(re.match(r"^[xX*.\-_]+$", v))


_EXAMPLE_VALUES = {
    "string", "number", "boolean", "undefined", "null", "none", "str",
    "foobar", "foo", "bar", "changeme", "example", "esempio", "secret", "password", "redacted",
}


def _mask(value: str) -> str:
    """Tiene al massimo i primi 4 caratteri, il resto diventa asterischi."""
    keep = min(4, max(1, len(value) // 4))
    return value[:keep] + "***"


def _excerpt(line: str, start: int, end: int) -> str:
    masked = line[:start] + _mask(line[start:end]) + line[end:]
    a = max(0, start - 30)
    b = min(len(masked), start + 60)
    out = masked[a:b].strip()
    return ("..." if a > 0 else "") + out + ("..." if b < len(masked) else "")


def scan(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for n, line in enumerate(text.splitlines(), start=1):
        taken = []  # intervalli già segnalati sulla riga: un solo finding per zona
        for kind, rx in _PATTERNS:
            for m in rx.finditer(line):
                if any(m.start() < e and s < m.end() for s, e in taken):
                    continue
                if "v" in rx.groupindex:
                    if _is_placeholder(m.group("v")):
                        continue
                    s0, e0 = m.start("v"), m.end("v")
                else:
                    s0, e0 = m.start(), m.end()
                taken.append((m.start(), m.end()))
                findings.append(Finding(kind, n, _excerpt(line, s0, e0)))
    return findings


def assert_clean(text: str, label: str) -> None:
    findings = scan(text)
    if findings:
        raise RedactionError(label, findings)


if __name__ == "__main__":  # uso manuale: redact.py file...
    rc = 0
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as fh:
            for f in scan(fh.read()):
                print("%s:%d [%s] %s" % (path, f.line, f.kind, f.excerpt))
                rc = 2
    sys.exit(rc)
