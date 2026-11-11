#!/usr/bin/env python3
"""
gaps_append_guard.py — wiki/gaps.md si scrive solo in coda (R.5), in sola modalita' avviso.

Riusa `removed_without_archive` di log_append_guard.py (senza esenzione delle righe `>` di testa
e senza archivi). Ammesso oltre alle righe aggiunte:
  - il cambio della casella `- [ ]` -> `- [x]` sulla stessa riga;
  - la sostituzione di una riga `**Aggiornamento...**` quando nello stesso commit, nello stesso
    blocco di gap (stessa riga `- [ ]`/`- [x]`), compare una nuova riga `**Risolto:**`.
Ogni altra riga tolta o modificata e' segnalata come avviso. Exit 0 sempre, salvo `--strict`
(exit 1 se ci sono avvisi). Nessuna scrittura, nessun aggancio a hook.

Uso:
  python3 tools/wiki/gaps_append_guard.py                  # sul contenuto in stage
  python3 tools/wiki/gaps_append_guard.py --commit <sha>   # su un commit gia' fatto (sha^ -> sha)
  python3 tools/wiki/gaps_append_guard.py --storia 50      # ultimi N commit che toccano il file
"""
import argparse
import importlib.util
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("log_append_guard", HERE / "log_append_guard.py")
lag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lag)

GAPS = "wiki/gaps.md"
BOX = re.compile(rb"^(\s*[-*]\s)\[ \]")
BULLET = re.compile(rb"^\s*[-*]\s\[[ xX]\]")


def norm(data: bytes) -> bytes:
    """Normalizza `- [ ]` in `- [x]` riga per riga."""
    return b"\n".join(BOX.sub(rb"\1[x]", l) for l in data.split(b"\n"))


def blocks(data: bytes) -> list:
    """Coppie (riga-gap normalizzata, righe del blocco): un blocco parte da una riga `- [ ]`/`- [x]`
    e finisce alla successiva riga di gap o intestazione."""
    out, cur = [], None
    for l in data.split(b"\n"):
        if BULLET.match(l):
            cur = (BOX.sub(rb"\1[x]", l), [])
            out.append(cur)
        elif l.startswith(b"#") or cur is None:
            cur = None
        else:
            cur[1].append(l)
    return out


def d1_replaced(line: bytes, old: bytes, new: bytes) -> bool:
    """La riga `**Aggiornamento...**` tolta sta in un blocco che nel nuovo testo ha un `**Risolto:**` in piu'."""
    for key, body in blocks(old):
        if line not in body:
            continue
        for nkey, nbody in blocks(new):
            if nkey == key and any(b.strip().startswith(b"**Risolto:**") and b not in body for b in nbody):
                return True
    return False


def check_texts(old: bytes, new: bytes) -> list:
    gone = lag.removed_without_archive(norm(old), norm(new), [], exempt_head=False)
    return [l for l in gone
            if not (l.strip().startswith(b"**Aggiornamento") and d1_replaced(l, norm(old), norm(new)))]


def check_commit(sha):
    names = lag.git("diff-tree", "--no-commit-id", "--name-only", "-r", f"{sha}^", sha).stdout.decode().split()
    if GAPS not in names:
        return []
    return check_texts(lag.blob(f"{sha}^:{GAPS}"), lag.blob(f"{sha}:{GAPS}"))


def check_staged():
    names = lag.git("diff", "--cached", "--name-only", "--diff-filter=ACMRD").stdout.decode().split()
    if GAPS not in names:
        return []
    return check_texts(lag.blob(f"HEAD:{GAPS}"), lag.blob(f":{GAPS}"))


def report(label, gone):
    print(f"AVVISO {label}: {len(gone)} righe di {GAPS} rimosse o modificate")
    for l in gone[:5]:
        print("   - " + l.decode("utf-8", "replace")[:150])
    if len(gone) > 5:
        print(f"   ... e altre {len(gone) - 5}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit")
    ap.add_argument("--storia", type=int)
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono avvisi")
    a = ap.parse_args(argv)

    if a.storia:
        shas = lag.git("log", f"-{a.storia}", "--format=%h", "--", GAPS).stdout.decode().split()
        bad = 0
        for sha in shas:
            gone = check_commit(sha)
            if gone:
                bad += 1
                report(sha, gone)
        print(f"gaps_append_guard: {len(shas)} commit esaminati, {bad} con avvisi")
        return 1 if bad and a.strict else 0

    gone = check_commit(a.commit) if a.commit else check_staged()
    if gone:
        report(a.commit or "stage", gone)
        print(f"{GAPS} e' append-only: aggiungi solo in coda. Sono ammessi il cambio `- [ ]` -> `- [x]` "
              "e la sostituzione di una riga `**Aggiornamento...**` con `**Risolto:**` nel commit di chiusura.")
        return 1 if a.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
