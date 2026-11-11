"""
kanban_history.py — storia delle transizioni di `status:` dei TSK, ricavata da git.

Usato da tools/analytics/team-velocity.py. Solo stdlib + git. Read-only.
Gli ID dei TSK possono avere un prefisso di namespace (`PS-TSK-12`) o no (`TSK-12`) e il
nome file puo' portare uno slug (`TSK-12-titolo.md`). Le funzioni lavorano per percorso:
due file con lo stesso ID (capita nel kanban) restano due TSK distinti.
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TSK_RE = re.compile(r"((?:[A-Z][A-Z0-9]*-)?TSK-\d+)(?:-[^/]*)?\.md$")
STATUS_RE = re.compile(r"^\+status:\s*[\"']?([A-Za-z_-]+)")

# `started_at` e `closed_at` sono i nomi dei campi opzionali; gli altri sono alias gia' in uso
# nei kanban per lo stesso dato.
CLOSED_FIELDS = ("closed_at", "closed", "completed_at", "completed", "done_at")
DONE_BY_FIELDS = ("done_by", "closed_by", "resolved_by")
STARTED_FIELDS = ("started_at",)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def first_field(fm, names, date=False):
    """Primo valore valorizzato fra i campi `names` (con date=True solo valori YYYY-MM-DD...)."""
    for n in names:
        v = (fm.get(n) or "").strip()
        if v and (not date or ISO_DATE.match(v)):
            return v[:10] if date else v
    return None


def frontmatter(text):
    m = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    out = {}
    block = None   # chiave con valore vuoto: le righe «  - x» seguenti sono la sua lista
    for line in m.group(1).splitlines():
        im = re.match(r"^\s+-\s*(.*)$", line)
        if block and im:
            item = re.sub(r"\s+#.*$", "", im.group(1)).strip().strip('"').strip("'")
            if item:
                out[block] = f"{out[block]}, {item}" if out[block] else item
            continue
        block = None
        km = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if km and km.group(1) not in out:
            v = re.sub(r"\s+#.*$", "", km.group(2)).strip()
            out[km.group(1)] = v.strip('"').strip("'")
            if not v:
                block = km.group(1)
    return out


def _git(root, *args, check=False):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check).stdout


def _renames(root, kanban):
    """Mappa percorso nuovo -> percorso precedente per i file rinominati nel kanban."""
    out = _git(root, "log", "-M", "--diff-filter=R", "--name-status", "--format=", "--", kanban)
    prev = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            prev.setdefault(parts[2], parts[1])
    return prev


def _ancestors(path, prev):
    chain, seen = [], {path}
    while path in prev and prev[path] not in seen:
        path = prev[path]
        seen.add(path)
        chain.append(path)
    return chain


def transitions(paths, since=None, root=ROOT, kanban="management/kanban"):
    """
    Per ogni TSK tracciato da git (chiave: percorso), lista cronologica di cambi di stato:
    (status, data, commit, autore). Gli stati sono normalizzati (`in-progress` -> `in_progress`).

    La storia segue le rinomine: un TSK spostato eredita la storia dei suoi percorsi precedenti.
    Uno spostamento che ri-aggiunge lo stesso status non e' un cambio.
    """
    # Repository senza commit (factory appena installata) o fuori da git: nessuna storia.
    # Prima `git log` usciva con 128 e il Check 4be andava in crash (EP-082).
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root,
                      capture_output=True, text=True).returncode != 0:
        return {}
    prev = _renames(root, kanban)
    current = [c for c in _git(root, "ls-files", "--", *paths).split("\n") if c and TSK_RE.search(c)]
    old = sorted({a for c in current for a in _ancestors(c, prev)})
    cmd = ["log", "--reverse", "--no-merges", "-M", "--format=@@C %h %cs %an", "-p", "-U0", "-G^status:"]
    if since:
        cmd.append(f"--since={since} 00:00:00" if len(since) == 10 else f"--since={since}")
    log = _git(root, *cmd, "--", *paths, *old, check=True)
    by_path = {}
    commit = date = author = path = None
    for line in log.splitlines():
        if line.startswith("@@C "):
            _, commit, date, author = line.split(maxsplit=3)
            continue
        if line.startswith("+++ "):
            path = line[6:].strip() if line.startswith("+++ b/") else None
            continue
        m = STATUS_RE.match(line)
        if m and path:
            by_path.setdefault(path, []).append((m.group(1).lower().replace("-", "_"), date, commit, author))
    out = {}
    for c in current:
        events = []
        for p in [*reversed(_ancestors(c, prev)), c]:
            events += by_path.get(p, [])
        events.sort(key=lambda e: e[1])  # sort stabile: a parita' di data resta l'ordine dei commit
        hist = []
        for e in events:
            if not hist or hist[-1][0] != e[0]:
                hist.append(e)
        if hist:
            out[c] = hist
    return out


def transitions_by_id(paths, since=None, root=ROOT, kanban="management/kanban"):
    """
    Come transitions(), con chiave l'ID del TSK invece del percorso. Nessun chiamante nel master:
    la usano i controlli per ID delle derivate (in portale-servizi-factory velocity_fields_check,
    attribution_check del pre-commit, backfill_people_time), che la perderebbero a ogni upgrade se
    vivesse solo da loro. Con due file dello stesso ID vale l'ultimo in ordine di percorso.
    """
    return {TSK_RE.search(p).group(1): h
            for p, h in sorted(transitions(paths, since=since, root=root, kanban=kanban).items())}


def last_entered(hist, status):
    """Ultima transizione verso `status`, oppure None."""
    for h in reversed(hist or []):
        if h[0] == status:
            return h
    return None


def first_entered(hist, status):
    for h in hist or []:
        if h[0] == status:
            return h
    return None
