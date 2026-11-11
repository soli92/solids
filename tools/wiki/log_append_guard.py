#!/usr/bin/env python3
"""
log_append_guard.py — wiki/log.md si scrive solo in coda (R.5).

Confronta la versione precedente di wiki/log.md con quella nuova: ogni riga che sparisce deve
ricomparire, identica, in un archivio wiki/log-*.md scritto nello stesso commit (e' cio' che fa
tools/wiki/rotate_log.py). Una riga tolta o modificata senza archivio blocca il commit.

Esenti: righe vuote, il frontmatter YAML iniziale (campi come `updated:` si aggiornano a ogni
scrittura e non sono entry) e righe di citazione (`> ...`) prima della prima entry, cioe' il
puntatore agli archivi che la rotazione aggiorna.

Lo lancia il check di lint 4bb (detective, WARNING) e, se attivo, l'hook di pre-commit
installato da tools/vcs/install_factory_hooks.py (`wiki_lint.log_append_guard.hook: true`).
Provenienza: portale-servizi-factory db21bf88; qui in piu' l'esenzione del frontmatter.

Uso:
  python3 tools/wiki/log_append_guard.py                  # sul contenuto in stage (come il gate)
  python3 tools/wiki/log_append_guard.py --commit <sha>   # su un commit gia' fatto (sha^ -> sha)
  python3 tools/wiki/log_append_guard.py --storia 200     # ultimi N commit che toccano il log
Exit: 0 ok, 1 righe rimosse senza archivio. Solo stdlib + git. Nessuna scrittura.
"""
import argparse
import collections
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOG = "wiki/log.md"
ARCHIVE_PREFIX = "wiki/log-"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def blob(ref_path):
    r = git("show", ref_path)
    return r.stdout if r.returncode == 0 else b""


def first_entry_index(lines):
    """Indice della prima entry (`## ...` o blocco `---` seguito da `date:`), frontmatter escluso."""
    start = frontmatter_end(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith(b"## "):
            return i
        if lines[i].rstrip(b"\r\n") == b"---" and i + 1 < len(lines) and lines[i + 1].startswith(b"date:"):
            return i
    return len(lines)


def frontmatter_end(lines):
    """Indice della prima riga dopo il frontmatter YAML iniziale (0 se non c'e')."""
    if lines and lines[0].rstrip(b"\r\n") == b"---" and not (len(lines) > 1 and lines[1].startswith(b"date:")):
        for i in range(1, len(lines)):
            if lines[i].rstrip(b"\r\n") == b"---":
                return i + 1
    return 0


def removed_without_archive(old: bytes, new: bytes, archived: list, exempt_head: bool = True) -> list:
    """Righe di `old` assenti da `new` e non coperte dalle righe aggiunte agli archivi.

    Con `exempt_head=False` le righe `>` prima della prima entry non sono esenti (il frontmatter
    resta esente)."""
    old_lines = old.splitlines(keepends=False)
    head = first_entry_index(old.splitlines(keepends=True))
    fm = frontmatter_end(old.splitlines(keepends=True))
    exempt = set(range(fm))
    if exempt_head:
        exempt |= {i for i, l in enumerate(old_lines[:head]) if l.startswith(b">")}
    counted = collections.Counter(l for i, l in enumerate(old_lines) if i not in exempt and l.strip())
    gone = counted - collections.Counter(new.splitlines())
    gone -= collections.Counter(l for a in archived for l in a.splitlines())
    pos = {}
    for i, l in enumerate(old_lines):
        pos.setdefault(l, i)
    return sorted(gone.elements(), key=pos.__getitem__)


def archive_additions(old_ref, new_ref, paths):
    out = []
    for p in paths:
        before = collections.Counter(blob(f"{old_ref}:{p}").splitlines()) if old_ref else collections.Counter()
        after = collections.Counter(blob(f"{new_ref}{p}" if new_ref == ":" else f"{new_ref}:{p}").splitlines())
        out.append(b"\n".join((after - before).elements()))
    return out


def check_staged():
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMRD").stdout.decode().split()
    if LOG not in names:
        return []
    archives = [n for n in names if n.startswith(ARCHIVE_PREFIX) and n.endswith(".md")]
    return removed_without_archive(blob(f"HEAD:{LOG}"), blob(f":{LOG}"), archive_additions("HEAD", ":", archives))


def check_commit(sha):
    names = git("diff-tree", "--no-commit-id", "--name-only", "-r", f"{sha}^", sha).stdout.decode().split()
    if LOG not in names:
        return []
    archives = [n for n in names if n.startswith(ARCHIVE_PREFIX) and n.endswith(".md")]
    return removed_without_archive(blob(f"{sha}^:{LOG}"), blob(f"{sha}:{LOG}"),
                                   archive_additions(f"{sha}^", sha, archives))


def report(label, gone):
    entries = [l for l in gone if l.startswith(b"## ")]
    print(f"{label}: {len(gone)} righe di {LOG} rimosse o modificate senza archivio "
          f"({len(entries)} intestazioni di entry)")
    for l in gone[:5]:
        print("   - " + l.decode("utf-8", "replace")[:150])
    if len(gone) > 5:
        print(f"   … e altre {len(gone) - 5}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit")
    ap.add_argument("--storia", type=int)
    a = ap.parse_args(argv)

    if a.storia:
        shas = git("log", f"-{a.storia}", "--format=%h", "--", LOG).stdout.decode().split()
        bad = 0
        for sha in shas:
            gone = check_commit(sha)
            if gone:
                bad += 1
                report(sha, gone)
        print(f"log_append_guard: {len(shas)} commit esaminati, {bad} con righe rimosse senza archivio")
        return 1 if bad else 0

    gone = check_commit(a.commit) if a.commit else check_staged()
    if gone:
        report(a.commit or "stage", gone)
        print(f"{LOG} e' append-only (R.5): aggiungi solo in coda. Per accorciarlo usa "
              "`python3 tools/wiki/rotate_log.py --apply`, che sposta le entry in un archivio.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
