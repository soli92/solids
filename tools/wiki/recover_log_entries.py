#!/usr/bin/env python3
"""
recover_log_entries.py — recupera dalla storia git le entry di wiki/log.md tolte senza archivio.

Per ogni commit che log_append_guard.py segnala (righe tolte senza archivio), legge la versione
del log prima del commit e la divide in entry (stesso criterio di rotate_log.py). Un'entry e'
**persa da quel commit** se c'era prima, manca dai registri subito dopo e, byte per byte, da ogni registro attuale
(wiki/log.md e wiki/log-*.md). Le entry perse si scrivono verbatim, una sola volta anche se
presenti in piu' commit, in un archivio di recupero, raggruppate per il commit che le ha tolte.
Una entry poi riscritta in forma diversa compare come versione precedente: il testo e'
quello che c'era, non una correzione.

Nessuna riga dei registri esistenti viene toccata (R.5). Il wiki-keeper non ha Bash: lo script
lo esegue il coordinatore, come rotate_log.py. Il frontmatter del log non e' mai un'entry.
Con `--commit` si limita il recupero ai commit indicati (le entry riscritte sul posto, che la
guardia segnala come modificate, compaiono altrimenti nella forma precedente).
Provenienza: portale-servizi-factory 29ebdfdf.

Uso:
  python3 tools/wiki/recover_log_entries.py                        # dry-run: cosa recupererebbe
  python3 tools/wiki/recover_log_entries.py --apply --out wiki/log-recuperato-AAAA-MM-GG.md
  python3 tools/wiki/recover_log_entries.py --commit 228bb90 --commit 27ff8cc   # solo questi commit
Exit: 0 ok, 1 file di uscita gia' esistente. Solo stdlib + git.
"""
import argparse
import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
QUI = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, QUI / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


guard = load("log_append_guard")
rotate = load("rotate_log")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True)


def entries(data: bytes):
    lines = data.splitlines(keepends=True)
    starts = [i for i, _ in rotate.find_entries(lines)]
    return [b"".join(lines[s:e]) for s, e in zip(starts, starts[1:] + [len(lines)])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default="wiki/log-recuperato.md")
    ap.add_argument("--commit", action="append", default=[], metavar="SHA",
                    help="solo questo commit (ripetibile, prefisso dello sha)")
    a = ap.parse_args(argv)

    current = b"\n".join(p.read_bytes() for p in sorted((ROOT / "wiki").glob("log*.md")))
    shas = git("log", "--format=%h", "--", "wiki/log.md").stdout.decode().split()
    seen, groups = set(), []
    for sha in reversed(shas):  # dal piu' vecchio: un'entry si attribuisce al primo commit che l'ha tolta
        if a.commit and not any(sha.startswith(c) or c.startswith(sha) for c in a.commit):
            continue
        if not guard.check_commit(sha):
            continue
        before = git("show", f"{sha}^:wiki/log.md").stdout
        names = git("ls-tree", "--name-only", sha, "wiki/").stdout.decode().split()
        after = b"\n".join(git("show", f"{sha}:{n}").stdout for n in names
                            if n.startswith("wiki/log") and n.endswith(".md"))
        lost = []
        for e in entries(before):
            key = e.strip()
            if key and key not in seen and key not in after and key not in current:
                seen.add(key)
                lost.append(e if e.endswith(b"\n") else e + b"\n")
        if lost:
            meta = git("log", "-1", "--format=%h|%ci|%an|%s", sha).stdout.decode().strip().split("|", 3)
            groups.append((meta, lost))

    total = sum(len(l) for _, l in groups)
    for (h, d, au, s), lost in groups:
        print(f"{h} {d[:10]} {au}: {len(lost)} entry — {s[:80]}")
    print(f"recover_log_entries: {total} entry perse in {len(groups)} commit")
    if not a.apply or not total:
        return 0

    out = ROOT / a.out
    if out.exists():
        print(f"{a.out} esiste gia': non lo sovrascrivo", file=sys.stderr)
        return 1
    head = (
        "---\ntype: wiki-log-archive\nappend_only: true\n"
        f"recovered_by: tools/wiki/recover_log_entries.py\nentries: {total}\n---\n\n"
        "# Entry di wiki/log.md recuperate dalla storia git\n\n"
        "> Entry tolte da wiki/log.md senza archivio e assenti, identiche, da ogni registro attuale.\n"
        "> Testo verbatim della versione precedente al commit indicato. Una entry poi riscritta in\n"
        "> forma diversa compare qui nella forma che aveva prima.\n\n"
    ).encode()
    body = b""
    for (h, d, au, s), lost in groups:
        body += f"# Tolte dal commit {h} ({d[:10]}, {au}): {s}\n\n".encode() + b"".join(lost) + b"\n"
    out.write_bytes(head + body)
    print(f"scritto {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
