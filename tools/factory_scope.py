#!/usr/bin/env python3
"""factory_scope.py — perimetro di una factory derivata: una sola fonte per installer e upgrade.

Prima c'erano due liste chiuse e indipendenti: `SYNC_PATHS`/`META_ONLY_PATHS` in
`tools/factory-upgrade-apply.py` e `EXTRA_DOCS` nell'installer (ereditata dalla v2.21, prima
che esistesse CAPABILITIES.md). Divergevano: l'installer copiava le unita' del solo
meta-framework e non copiava `visual/`, `schemas/` ne' CAPABILITIES.md, citato da `/help`.

Qui stanno:
  - SYNC_PATHS        cartelle e file del framework che una derivata riceve;
  - META_ONLY_PATHS   unita' del solo meta-framework, mai propagate;
  - is_meta_only()    la regola di esclusione;
  - stacca_link_pendenti()      link markdown verso file assenti -> testo semplice;
  - capabilities_per_derivata() CAPABILITIES.md del master senza le righe dei comandi del
                                meta-framework e senza link pendenti.

Usato da `installers/v2.45/factory_install.py` e da `tools/factory-upgrade-apply.py`. Solo stdlib.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

# Comandi che vivono nel meta-framework: creano, aggiornano o rilasciano factory.
EXCLUDE_COMMANDS = {"factory-bootstrap.md", "factory-upgrade.md", "release.md"}

# Cartelle e file del framework che una derivata riceve (add-only in upgrade).
SYNC_PATHS = [
    ".claude/agents",
    ".claude/skills",
    ".claude/commands",
    ".claude/tools",
    ".claude/schemas",
    "tools",
    "voice",
    "visual",   # runtime di /plancia (EP-067): senza, il comando arriva e il canale no
    "vendor",   # copie fedeli MIT (EP-077, EP-090): le skill adattate vi rimandano e la licenza
                # chiede che copyright e permesso accompagnino ogni copia
    "schemas",  # factory.config.schema.json: validazione della config
    "adapters/cursor/templates",
    # file di framework in analytics/ (seed v2-45 §2 «Framework»); i dati restano della derivata
    "analytics/pricing.yaml",
    "analytics/alert-rules.yaml",           # soglie di esempio: la derivata le tara
    "analytics/velocity/config.example.json",
    "analytics/coordinamento/config-schema.json",
]

# Unita' del solo meta-framework: lo strumento di upgrade, i test della sua struttura, il
# testbed di EP-060, i comandi esclusi con le loro references.
META_ONLY_PATHS = (
    "tools/factory-upgrade-apply.py",
    "tools/tests/test_factory_upgrade_",     # prefisso: i test dello strumento lo seguono
    "tools/tests/test_meta_framework.py",
    "tools/tests/test_installer.py",          # installa dal meta-framework
    ".claude/agents/pattern-b-testbed.md",
    ".claude/agents/references/pattern-b-testbed/",
) + tuple(f".claude/commands/{c}" for c in sorted(EXCLUDE_COMMANDS)) \
  + tuple(f".claude/commands/references/{c[:-3]}/" for c in sorted(EXCLUDE_COMMANDS))


def is_meta_only(rel: str) -> bool:
    """Path esatto, cartella (`.../`) o prefisso di nome (`..._`)."""
    return any(rel == p or (p.endswith(("/", "_")) and rel.startswith(p)) for p in META_ONLY_PATHS)


_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")


def stacca_link_pendenti(testo: str, esiste: Callable[[str], bool]) -> tuple[str, int]:
    """`[label](path)` con `path` locale inesistente -> `label`. URL e ancore restano.

    `esiste(path)` riceve il path senza ancora. Ritorna il testo e il numero di link staccati.
    """
    n = 0

    def _sub(m: re.Match) -> str:
        nonlocal n
        label, dest = m.group(1), m.group(2)
        if dest.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        path = dest.split("#", 1)[0]
        if not path or esiste(path):
            return m.group(0)
        n += 1
        return label

    return _LINK_RE.sub(_sub, testo), n


# Documenti del solo meta-framework che una riga di CAPABILITIES puo' citare come strumento
# (QUICKSTART: percorso per creare una factory, seed v2-45 §2 «presentazione del master»).
_DOC_META = ("installers/", "factory-upgrade-apply.py", "QUICKSTART")


def _comando_meta(riga: str) -> bool:
    """Riga che cita un comando o un documento del meta-framework (`/release`, non `/release-artifact`)."""
    for c in EXCLUDE_COMMANDS:
        if re.search(rf"`/{re.escape(c[:-3])}(?![\w-])", riga):
            return True
    return any(d in riga for d in _DOC_META)


def capabilities_per_derivata(testo: str, esiste: Callable[[str], bool]) -> str:
    """CAPABILITIES.md del master adattato a una derivata.

    Toglie le righe di tabella dei comandi del meta-framework e stacca i link verso file che la
    derivata non ha (wiki, docs e kanban del master). Il resto e' verbatim: la derivata lo
    personalizza, e in upgrade il file si fonde a mano (seed v2-45 §2).
    """
    righe = [r for r in testo.splitlines() if not (r.lstrip().startswith("|") and _comando_meta(r))]
    corpo, _ = stacca_link_pendenti("\n".join(righe), esiste)
    nota = ("> Copia per factory derivata, generata da `tools/factory_scope.py`: senza i comandi del "
            "meta-framework e con i rimandi a pagine che questa factory non ha resi come testo.\n")
    titolo, _, resto = corpo.partition("\n")
    return f"{titolo}\n\n{nota}{resto}".rstrip() + "\n"


def esiste_in(root: Path) -> Callable[[str], bool]:
    """Callback per i link: path relativo alla radice della factory."""
    return lambda p: (root / p.lstrip("/")).exists()
