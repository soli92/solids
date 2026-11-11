#!/usr/bin/env python3
"""Osservatore on-demand dello stato kanban remoto (EP-064 US-266 TSK-635).

Risponde a due domande, non una:

  1. Cosa hanno fatto gli altri che tu non vedi  — transizioni di `status:` nei TSK
     presenti sul remote e assenti nel tuo checkout.
  2. Cosa hai fatto tu che gli altri non vedono  — tue modifiche al kanban non
     ancora pushate. E' la meta' che previene la collisione: rende visibile
     all'autore il proprio silenzio.

Cosa NON fa, per contratto (US-266 AC7): non impedisce la doppia presa, non risolve
la contesa, non garantisce alcuna latenza. Mostra lo stato *all'ultimo push*, e
dichiara quanto e' vecchio. Un osservatore che non dichiara la propria staleness
reintroduce il board «bugiardamente fresco».

Non e' un demone (AC1): la forma watcher continuo e' stata scartata per activation
gap — nessuno la tiene accesa. Va invocato, o innestato in un'azione che l'utente
compie comunque (TSK-636).

Read-only assoluto (AC4): esegue `git fetch` e legge. Mai `push`, mai `pull`, mai
una scrittura in `management/kanban/`.

Uso:
    python3 tools/kanban-observer/kanban-observe.py [--json] [--no-fetch] [<root>]
Exit: 0 sempre, salvo errore d'uso. L'assenza di rete non e' un fallimento.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import subprocess
import sys

KANBAN = "management/kanban"
STATUS_RE = re.compile(r"^[+-]status:\s*(\S+)", re.M)
TSK_PATH_RE = re.compile(r"(TSK-\d+)\.md$")


def git(root: pathlib.Path, *args: str, timeout: int = 30):
    """Esegue git e ritorna (ok, stdout). Mai solleva: l'assenza di rete e' un esito."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode == 0, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False, ""


def upstream(root: pathlib.Path) -> str | None:
    ok, out = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return out if ok and out else None


def transitions(root: pathlib.Path, rev_range: str) -> list[dict]:
    """Transizioni di `status:` sui TSK nel range, piu' recenti prima."""
    ok, out = git(
        root, "log", rev_range, "--no-merges",
        "--format=%x00%H%x1f%an%x1f%aI%x1f%s", "--unified=0", "-p", "--", KANBAN,
    )
    if not ok or not out:
        return []
    found = []
    for block in out.split("\x00"):
        if not block.strip():
            continue
        header, _, body = block.partition("\n")
        parts = header.split("\x1f")
        if len(parts) < 4:
            continue
        sha, author, when, subject = parts[0][:8], parts[1], parts[2], parts[3]
        for chunk in body.split("diff --git ")[1:]:
            first = chunk.split("\n", 1)[0]
            m = TSK_PATH_RE.search(first.split(" b/")[-1].strip())
            if not m:
                continue
            states = STATUS_RE.findall(chunk)
            # -old poi +new: interessa solo se lo status cambia davvero
            old = [s for s, line in zip(states, STATUS_RE.finditer(chunk)) if line.group(0).startswith("-")]
            new = [s for s, line in zip(states, STATUS_RE.finditer(chunk)) if line.group(0).startswith("+")]
            if not new:
                continue
            found.append({
                "tsk": m.group(1), "da": (old or ["(nuovo)"])[0], "a": new[0],
                "autore": author, "quando": when, "commit": sha, "subject": subject,
            })
    return found


def local_unpushed(root: pathlib.Path) -> dict:
    """Cosa gli altri non possono vedere di te: non committato + committato non pushato."""
    ok, out = git(root, "status", "--porcelain", "--", KANBAN)
    # porcelain v1 e' `XY<spazio>PATH`, ma un rename e' `R  old -> new` e uno
    # stato staged+dirty puo' avere due lettere: affettare a indice fisso sbaglia.
    dirty = ([l[2:].strip() for l in out.splitlines() if l.strip()] if ok else [])
    ahead = []
    if upstream(root):
        ok2, out2 = git(root, "log", "@{u}..HEAD", "--format=%h %s", "--", KANBAN)
        if ok2 and out2:
            ahead = out2.splitlines()
    return {"non_committato": dirty, "committato_non_pushato": ahead}


def age(iso: str | None) -> str:
    if not iso:
        return "sconosciuta"
    try:
        ts = _dt.datetime.fromisoformat(iso)
    except ValueError:
        return "sconosciuta"
    delta = _dt.datetime.now(_dt.timezone.utc) - ts.astimezone(_dt.timezone.utc)
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "meno di un minuto"
    if mins < 60:
        return f"{mins} min"
    if mins < 60 * 24:
        return f"{mins // 60} h {mins % 60} min"
    return f"{mins // (60 * 24)} giorni"


def observe(root: pathlib.Path, do_fetch: bool = True) -> dict:
    res: dict = {
        "fetch": None, "upstream": None, "staleness": None,
        "dagli_altri": [], "tuo_silenzio": {}, "note": [],
    }
    if not (root / ".git").exists():
        res["note"].append("non e' un repo git: nessuna osservazione possibile")
        return res

    up = upstream(root)
    res["upstream"] = up
    if up is None:
        res["note"].append(
            "il branch corrente non ha un upstream: non esiste un «remoto» da osservare"
        )
        res["tuo_silenzio"] = local_unpushed(root)
        return res

    if do_fetch:
        ok, _ = git(root, "fetch", "--quiet", timeout=60)
        res["fetch"] = "ok" if ok else "non riuscito"
        if not ok:
            res["note"].append(
                "fetch non riuscito (rete assente o remote irraggiungibile): "
                "lo stato mostrato e' quello dell'ultimo fetch riuscito, non quello attuale"
            )
    else:
        res["fetch"] = "saltato (--no-fetch)"
        res["note"].append("fetch saltato: lo stato puo' essere piu' vecchio di quanto sembri")

    res["dagli_altri"] = transitions(root, f"HEAD..{up}")
    res["tuo_silenzio"] = local_unpushed(root)

    ok, out = git(root, "log", "-1", "--format=%aI", up)
    res["staleness"] = {"ultimo_commit_remoto": out if ok and out else None}
    res["staleness"]["eta"] = age(out if ok and out else None)
    return res


def render(res: dict) -> str:
    L = []
    W = 78
    L.append("=" * W)
    L.append("OSSERVATORE KANBAN — stato all'ultimo push, non in tempo reale")
    L.append("=" * W)

    st = res.get("staleness") or {}
    up = res.get("upstream")
    if up:
        L.append(f"remoto osservato : {up}   (fetch: {res.get('fetch')})")
        L.append(f"eta' del dato    : {st.get('eta', 'sconosciuta')} "
                 f"dall'ultimo commit remoto sul kanban")
    L.append("")

    altri = res.get("dagli_altri") or []
    L.append(f"-- DAGLI ALTRI, che tu non vedi ancora ({len(altri)}) " + "-" * 24)
    if not altri:
        L.append("   nessuna transizione di status sul remoto che non hai gia'.")
    for e in altri[:20]:
        L.append(f"   {e['tsk']}: {e['da']} -> {e['a']}   [{e['autore']}, "
                 f"{age(e['quando'])} fa, {e['commit']}]")
    if len(altri) > 20:
        L.append(f"   ... e altre {len(altri) - 20}")
    L.append("")

    mio = res.get("tuo_silenzio") or {}
    nc, cnp = mio.get("non_committato") or [], mio.get("committato_non_pushato") or []
    L.append(f"-- IL TUO SILENZIO, che gli altri non vedono ({len(nc) + len(cnp)}) " + "-" * 14)
    if not nc and not cnp:
        L.append("   niente: quello che hai fatto sul kanban e' visibile a tutti.")
    for f in nc[:12]:
        L.append(f"   non committato      : {f}")
    for c in cnp[:12]:
        L.append(f"   committato non push.: {c}")
    if nc or cnp:
        L.append("   ^ finche' non pushi, per gli altri questi task sono come li hanno")
        L.append("     lasciati: e' la finestra in cui puo' nascere una doppia presa.")
    L.append("")

    for n in res.get("note") or []:
        L.append(f"   nota: {n}")
    if res.get("note"):
        L.append("")

    L.append("-- COSA QUESTO STRUMENTO NON FA " + "-" * 45)
    L.append("   Non impedisce la doppia presa, non risolve la contesa e non garantisce")
    L.append("   alcuna latenza. Mostra lo stato all'ultimo push e ne dichiara l'eta'.")
    L.append("   Per non collidere: `assignee:` in pianificazione (EP-064 US-253).")
    L.append("=" * W)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Osservatore on-demand dello stato kanban remoto")
    ap.add_argument("root", nargs="?", default=".", help="root del repo (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--no-fetch", action="store_true", help="non contattare il remote")
    args = ap.parse_args()

    res = observe(pathlib.Path(args.root).resolve(), do_fetch=not args.no_fetch)
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
