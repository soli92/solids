#!/usr/bin/env python3
"""
check-version-coherence.py — Lint Check 4am, eseguibile.

`factory.config.yaml#pattern_version` e' la SSOT della versione della factory.
Ogni altro file che dichiara la versione deve concordare con quel valore.

Perche' questo script esiste: il Check 4am era descritto nella skill di lint come
sempre attivo, ma cercava la versione in punti che non matchavano i file reali.
Il check passava in silenzio anche in presenza di divergenze misurate.

Il difetto non era la severita' del check, era il punto in cui guardava. Da qui
due regole di questo script:

  1. i siti di dichiarazione sono espliciti e versionati insieme al repo (SITES);
  2. un sito dichiarato che NON matcha e' esso stesso un WARNING
     (`version-site-missing`), non uno skip silenzioso: se qualcuno riscrive
     l'intestazione di un file, il check lo dice invece di smettere di guardare.

Severita': WARNING-only, exit 0 sempre (il bump manuale richiede giudizio, non
deve bloccare la factory). Exit 2 solo se la SSOT stessa non e' leggibile.

Profilo: i siti di dichiarazione non sono gli stessi in ogni factory. PATTERN.md e'
copiato identico ovunque (scope `all`); CLAUDE.md, README, sprint.md, dispatcher e
meta-prompts dichiarano la versione nella forma qui controllata solo nel meta-framework
(scope `framework`). Il meta-framework si dichiara con
`version_coherence.profile: framework` in factory.config.yaml; chiave assente = `derived`.
In `derived` un sito di framework assente o senza la riga non e' un finding: e' elencato
come non applicabile nell'output (dichiarato, non saltato). Se e' presente e diverge,
resta un finding.

Uso:
  python3 tools/lint/check-version-coherence.py
  python3 tools/lint/check-version-coherence.py --json
  python3 tools/lint/check-version-coherence.py --root /path/to/other/factory

Siti della sola factory: `tools/lint/version_sites_locali.py` (vedi `sites()`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pattern_modules import missing_modules, pattern_files  # noqa: E402

# Lista dei siti che dichiarano la versione in questa factory.
# Formato: (rel_path, descrizione_sito, regex_con_gruppo_1_XY, scope)
#
# scope="all"       → richiesto in ogni factory: assente o non trovato = version-site-missing
# scope="framework" → richiesto con profile: framework; in derived assente = non applicabile
#                     (elencato), presente e divergente = warning
# scope="optional"  → sito assente = silenzio; presente con versione errata = warning
SITES: list[tuple[str, str, str, str]] = [
    (
        "PATTERN.md",
        "riga `Pattern version: **X.Y**`",
        r"Pattern version:\s*\*\*([0-9]+\.[0-9]+)\*\*",
        "all",
    ),
    (
        "CLAUDE.md",
        "sezione `## Meta-prompt versioning (vX.Y`",
        r"## Meta-prompt versioning \(v([0-9]+\.[0-9]+)",
        "framework",
    ),
    (
        "README.md",
        "riga `> **vX.Y** (current`",
        r">\s*\*\*v([0-9]+\.[0-9]+)\*\*\s*\(current",
        "framework",
    ),
    (
        "management/kanban/sprint.md",
        "frontmatter `pattern_version:`",
        r'^pattern_version:\s*"?([0-9]+\.[0-9]+)"?',
        "framework",
    ),
    (
        ".claude/commands/factory-bootstrap.md",
        "riga `Dispatcher thin → vX.Y`",
        r"Dispatcher thin\s*→\s*v([0-9]+\.[0-9]+)",
        "framework",
    ),
    (
        "meta-prompts/README.md",
        "riga tabella `| **vX.Y** | **current** |`",
        r"\|\s*\*\*v([0-9]+\.[0-9]+)\*\*\s*\|\s*\*\*current\*\*",
        "framework",
    ),
    # Siti opzionali: presenti in alcune factory della stessa famiglia, non qui.
    # Se il file esiste e contiene il pattern, la versione deve concordare.
    # Se il file e' assente, nessun rumore.
    (
        "LAYERS-NOT-USED.md",
        "frontmatter `pattern_version:`",
        r'^pattern_version:\s*"?([0-9]+\.[0-9]+)"?',
        "optional",
    ),
    (
        # EP-082: la base della config degli installer; era ferma a 2.42 senza che nulla lo dicesse
        "factory.starter.config.yaml",
        "riga `pattern_version:`",
        r'^pattern_version:\s*"?([0-9]+\.[0-9]+)"?',
        "optional",
    ),
    (
        "CAPABILITIES.md",
        "link `guides/factory-guide-vX.Y.html`",
        r"factory-guide-v([0-9]+\.[0-9]+)\.html",
        "optional",
    ),
]


SITI_LOCALI = "tools/lint/version_sites_locali.py"


def _locali(root: Path) -> dict:
    p = root / SITI_LOCALI
    if not p.is_file():
        return {}
    ns: dict = {}
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), ns)  # file della factory stessa
    return ns


def sites(root: Path) -> list[tuple[str, str, str, str]]:
    """SITES piu' i siti della sola factory, in `tools/lint/version_sites_locali.py` (lista
    `SITES` nella stessa forma; file che il master non ha, quindi mai in conflitto all'upgrade).
    Un sito locale con lo stesso file e la stessa regex di uno del master ne prende il posto:
    cosi' una factory rende obbligatorio (`all`) un sito che qui e' `optional`."""
    locali = [tuple(x) for x in _locali(root).get("SITES", [])]
    chiavi = {(rel, rx) for rel, _, rx, _ in locali}
    return [x for x in SITES if (x[0], x[2]) not in chiavi] + locali


def read_ssot(root: Path) -> str | None:
    """Legge pattern_version da factory.config.yaml. Restituisce None se assente."""
    cfg = root / "factory.config.yaml"
    if not cfg.exists():
        return None
    m = re.search(
        r'^\s*pattern_version:\s*"?([0-9]+\.[0-9]+)"?',
        cfg.read_text(encoding="utf-8"),
        re.M,
    )
    return m.group(1) if m else None


def read_profile(root: Path) -> str:
    """version_coherence.profile da factory.config.yaml; default `derived`."""
    cfg = root / "factory.config.yaml"
    if not cfg.exists():
        return "derived"
    m = re.search(
        r'^version_coherence:[^\n]*\n(?:[ \t]+[^\n]*\n|[ \t]*\n)*?[ \t]+profile:\s*"?([a-z]+)"?',
        cfg.read_text(encoding="utf-8"),
        re.M,
    )
    return m.group(1) if m else "derived"


def scan(root: Path, expected: str, profile: str = "framework") -> tuple[list[dict], list[str]]:
    """Controlla ogni sito. Restituisce (finding, siti non applicabili al profilo)."""
    findings: list[dict] = []
    not_applicable: list[str] = []

    for rel, site, pattern, scope in sites(root):
        required = scope == "all" or (scope == "framework" and profile == "framework")
        if scope == "framework" and not required:
            # in derived: si registra se manca, cosi' l'output lo dichiara
            path = root / rel
            if not path.exists() or re.search(pattern, path.read_text(encoding="utf-8"), re.M) is None:
                not_applicable.append(rel)
                continue
        path = root / rel
        if not path.exists():
            if required:
                findings.append(
                    {
                        "rule": "version-site-missing",
                        "file": rel,
                        "site": site,
                        "detail": (
                            "file assente: il sito di dichiarazione non e' verificabile"
                        ),
                    }
                )
            continue

        text = path.read_text(encoding="utf-8")
        m = re.search(pattern, text, re.M)
        if m is None:
            if required:
                findings.append(
                    {
                        "rule": "version-site-missing",
                        "file": rel,
                        "site": site,
                        "detail": (
                            "sito di dichiarazione non trovato: il check non ha nulla "
                            "da confrontare (un sito dichiarato che non matcha e' un "
                            "finding, non uno skip silenzioso)"
                        ),
                    }
                )
            continue

        found = m.group(1)
        if found != expected:
            findings.append(
                {
                    "rule": "version-divergent",
                    "file": rel,
                    "site": site,
                    "detail": (
                        f"dichiara versione {found} divergente da "
                        f"factory.config.yaml (pattern_version: {expected})"
                    ),
                }
            )

    # versione nel nome di un file (es. la guida guides/factory-guide-vX.Y.html): `GLOBS` locali,
    # (glob, descrizione, regex sul nome con un gruppo X.Y, obbligatorio)
    for glob, site, pattern, required in _locali(root).get("GLOBS", []):
        trovati = sorted(root.glob(glob))
        if not trovati and required:
            findings.append({"rule": "version-site-missing", "file": glob, "site": site,
                             "detail": "nessun file corrisponde al glob"})
        for f in trovati:
            m = re.search(pattern, f.name)
            if m and m.group(1) != expected:
                findings.append({"rule": "version-divergent", "file": str(f.relative_to(root)), "site": site,
                                 "detail": f"il nome dichiara {m.group(1)}, factory.config.yaml {expected}"})

    findings.extend(scan_pattern_modules(root, expected))
    findings.extend(scan_stale_candidate(root, expected))
    return findings, not_applicable


# sprint.md e' escluso: le intestazioni degli sprint chiusi registrano la versione bersaglio
# di allora («v2.44-candidate»), sono storia e non dichiarazione corrente.
CANDIDATE_ESCLUSI = {"management/kanban/sprint.md"}


def scan_stale_candidate(root: Path, expected: str) -> list[dict]:
    """EP-080 US-350: un sito che dichiara la versione giusta puo' contraddirsi nel testo
    vicino, chiamando «candidate» la versione gia' corrente (dispatcher, 2026-10-18: riga 5
    «v2.44 candidate», riga 14 «v2.44 corrente»). Il check di sito non lo vedeva."""
    rx = re.compile(rf"v{re.escape(expected)}\**[ \t]*[-(]?[ \t]*candidate", re.I)
    out: list[dict] = []
    visti: set[str] = set()
    # ogni sito presente, in ogni profilo: come per version-divergent, un file che c'e' si legge
    for rel, _, _, _ in sites(root):
        if rel in CANDIDATE_ESCLUSI or rel in visti:
            continue
        visti.add(rel)
        path = root / rel
        if not path.is_file():
            continue
        for n, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(riga):
                out.append(
                    {
                        "rule": "version-stale-candidate",
                        "file": f"{rel}:{n}",
                        "site": "testo intorno al sito di versione",
                        "detail": (
                            f"chiama «candidate» la versione {expected}, che "
                            "factory.config.yaml dichiara corrente"
                        ),
                    }
                )
    return out


def scan_pattern_modules(root: Path, expected: str) -> list[dict]:
    """US-319: il PATTERN e' indice + moduli; la versione si dichiara solo nell'indice.

    Due finding: un modulo linkato nella tabella §Moduli ma assente (la derivata ha
    l'indice nuovo e non i moduli: §12+ irraggiungibili), e un modulo che dichiara una
    propria `Pattern version` divergente. Un PATTERN monolitico non produce nulla.
    """
    out: list[dict] = []
    for name in missing_modules(root):
        out.append(
            {
                "rule": "pattern-module-missing",
                "file": name,
                "site": "tabella `## Moduli` di PATTERN.md",
                "detail": "modulo linkato nell'indice ma assente: le sue sezioni sono irraggiungibili",
            }
        )
    rx = re.compile(SITES[0][2], re.M)
    for path in pattern_files(root)[1:]:
        m = rx.search(path.read_text(encoding="utf-8", errors="replace"))
        if m and m.group(1) != expected:
            out.append(
                {
                    "rule": "version-divergent",
                    "file": path.name,
                    "site": SITES[0][1],
                    "detail": (
                        f"il modulo dichiara versione {m.group(1)} divergente da "
                        f"factory.config.yaml (pattern_version: {expected}); "
                        "la versione vive solo in PATTERN.md"
                    ),
                }
            )
    return out


def find_factory_root(start: Path) -> Path:
    """Risale l'albero finche' trova factory.config.yaml. Fallback: cwd."""
    for parent in [start, *start.parents]:
        if (parent / "factory.config.yaml").exists():
            return parent
    return Path.cwd()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Lint Check 4am — coerenza delle versioni dichiarate"
    )
    ap.add_argument(
        "--root",
        metavar="PATH",
        help=(
            "radice della factory da controllare "
            "(default: factory che contiene lo script)"
        ),
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="output JSON invece che testuale",
    )
    args = ap.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    else:
        root = find_factory_root(Path(__file__).resolve().parent)

    expected = read_ssot(root)
    if expected is None:
        msg = (
            "SKIP — factory.config.yaml assente o senza pattern_version "
            "(graceful degradation, Check 4am non applicabile)"
        )
        if args.json:
            print(json.dumps({"error": msg}, ensure_ascii=False))
        else:
            print(msg, file=sys.stderr)
        return 2

    profile = read_profile(root)
    findings, not_applicable = scan(root, expected, profile)

    if args.json:
        print(
            json.dumps(
                {
                    "pattern_version": expected,
                    "root": str(root),
                    "profile": profile,
                    "sites_checked": len(sites(root)) - len(not_applicable),
                    "not_applicable": not_applicable,
                    "findings": findings,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"SSOT factory.config.yaml#pattern_version = {expected}")
    print(f"Root: {root}")
    print(f"Profilo: {profile}")
    if not_applicable:
        print(
            f"Non applicabili al profilo {profile} ({len(not_applicable)}): "
            + ", ".join(not_applicable)
        )
    if not findings:
        print(f"OK — tutti i siti di dichiarazione concordano su {expected}")
        return 0

    print()
    for f in findings:
        print(
            f"- [WARNING][{f['rule']}][4am] {f['file']} ({f['site']}): {f['detail']}"
        )
    print(
        f"\n{len(findings)} WARNING. Check advisory: non blocca, "
        f"il bump richiede giudizio sul repo completo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
