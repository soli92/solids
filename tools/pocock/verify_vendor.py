#!/usr/bin/env python3
"""
verify_vendor.py — controlla che una copia in vendor/<cartella>/ sia fedele al commit dichiarato.

Per ogni riga di MANIFEST.sha1 ricalcola l'impronta git (blob SHA-1) del file e la confronta.
Segnala file mancanti, file con impronta diversa e file presenti ma non dichiarati.
Con --clone confronta anche il manifest con `git ls-tree` di un clone del repo sorgente
al commit scritto in ORIGINE.md della cartella.

Uso:
  python3 tools/pocock/verify_vendor.py                              # mattpocock-skills (default)
  python3 tools/pocock/verify_vendor.py --vendor emilkowalski-skills
  python3 tools/pocock/verify_vendor.py --all                        # ogni cartella di vendor/ con MANIFEST.sha1
  python3 tools/pocock/verify_vendor.py --clone /percorso/clone
--vendor accetta un nome (sotto vendor/) oppure un percorso di cartella.
Exit: 0 copia fedele, 1 differenze. Solo stdlib (+ git per --clone). Nessuna scrittura.
"""
import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
VENDOR_DIR = ROOT / "vendor"
DEFAULT = "mattpocock-skills"
VENDOR = VENDOR_DIR / DEFAULT
EXTRA_OK = {"LICENSE", "ORIGINE.md", "MANIFEST.sha1"}


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def resolve(name: str) -> pathlib.Path:
    p = pathlib.Path(name)
    return p if (p.is_absolute() or len(p.parts) > 1) else VENDOR_DIR / name


def manifest(vendor=VENDOR):
    rows = {}
    for line in (vendor / "MANIFEST.sha1").read_text(encoding="utf-8").splitlines():
        if line.strip():
            sha, path = line.split(None, 1)
            rows[path.strip()] = sha
    return rows


def verify(vendor, clone=None):
    if not (vendor / "MANIFEST.sha1").is_file():
        print(f"{vendor.name}: MANIFEST.sha1 assente")
        return 1
    rows = manifest(vendor)
    errors = []
    for path, sha in rows.items():
        f = vendor / path
        if not f.is_file():
            errors.append(f"mancante: {path}")
        elif blob_sha(f.read_bytes()) != sha:
            errors.append(f"modificato: {path}")
    present = {str(p.relative_to(vendor)) for p in vendor.rglob("*") if p.is_file()}
    for path in sorted(present - set(rows) - EXTRA_OK):
        errors.append(f"non dichiarato: {path}")

    if clone:
        m = re.search(r"`([0-9a-f]{40})`", (vendor / "ORIGINE.md").read_text(encoding="utf-8"))
        if not m:
            errors.append("ORIGINE.md: commit a 40 caratteri non trovato")
        else:
            commit = m.group(1)
            r = subprocess.run(["git", "-C", clone, "ls-tree", "-r", commit, "--", *rows],
                               capture_output=True, text=True)
            if r.returncode:
                errors.append(f"clone: commit {commit[:7]} non leggibile ({r.stderr.strip()})")
            else:
                upstream = {l.split("\t", 1)[1]: l.split()[2] for l in r.stdout.splitlines()}
                for path, sha in rows.items():
                    if upstream.get(path) != sha:
                        errors.append(f"diverso dal commit {commit[:7]}: {path}")

    for e in errors:
        print(e)
    print(f"verify_vendor [{vendor.name}]: {len(rows)} file dichiarati, {len(errors)} differenze")
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clone", help="clone locale del repo sorgente (con --all non ammesso)")
    ap.add_argument("--vendor", default=DEFAULT, help="cartella in vendor/ (nome o percorso)")
    ap.add_argument("--all", action="store_true", help="verifica ogni cartella di vendor/ con MANIFEST.sha1")
    a = ap.parse_args()
    if a.all:
        if a.clone:
            ap.error("--clone non si combina con --all")
        dirs = sorted(d for d in VENDOR_DIR.iterdir() if (d / "MANIFEST.sha1").is_file())
        return 1 if [d for d in dirs if verify(d)] or not dirs else 0
    return verify(resolve(a.vendor), a.clone)


if __name__ == "__main__":
    sys.exit(main())
