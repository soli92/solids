#!/usr/bin/env python3
"""next-id.py — il prossimo identificativo libero, EP / US / TSK.

    python3 tools/kanban/next-id.py tsk [quanti]
    python3 tools/kanban/next-id.py tsk [quanti] --namespace UP   # factory con piu' code_path

**Perche' esiste.** La numerazione dei TSK e' globale ma viene allocata per-epica, e
quando due epiche si lavorano in parallelo nascono collisioni: nel repo ce ne sono
**19** (TSK-292..295 fra EP-039 ed EP-041, TSK-545..559 fra EP-060, EP-061 ed EP-062).
Due lavori diversi con lo stesso identificativo, per sempre.

Ci si casca in un modo preciso, e il 2026-09-23 ci e' cascato anche un agente: si
prende il massimo fra i TSK **aperti** invece che fra **tutti**, e i `cancelled` — che
in questo repo arrivano fino a TSK-632 — restano invisibili. Il massimo va cercato su
tutto, archivio compreso.

**Flag --namespace PREFIX** (EP-069 US-314, opt-in):
Senza questo flag, e senza il registro `management/kanban/id-registry.yaml`, il
comportamento e' identico a quello pre-US-314. Con il flag, lo script cerca file
`{PREFIX}-{TIPO}-*.md` e rispetta le prenotazioni dichiarate nel registro.

**Remoto.** Prima di calcolare, lo script fa `git fetch origin main` e unisce
agli ID del filesystem quelli presenti in `origin/main` (`git ls-tree`), cosi' un ID creato
da un'altra macchina e non ancora scaricato non viene riassegnato. Se il fetch non riesce
(offline, errore di rete) si continua con il filesystem locale (e con l'ultimo `origin/main`
gia' scaricato, se esiste) e lo si dichiara: su stderr una riga `# AVVISO ...` piu' la riga
leggibile da macchina `# next-id-remote: <stato>`; con `--json` lo stato e' nel documento.
Remote e branch si cambiano con `--remote` e `--branch` (default origin e main).
`--no-remote` (o `NEXT_ID_OFFLINE=1`) salta del tutto la lettura del remoto: stato `disabled`,
nessun avviso, calcolo sul solo filesystem.
Stati: `ok` (fetch riuscito), `disabled` (remoto escluso), `no-fetch` (richiesto con --no-fetch, si legge il ref locale),
`stale` (fetch fallito, ref locale vecchio usato), `unavailable` (nessun origin/main leggibile).
Lo stdout e l'exit code (0) restano quelli di prima; `--strict` esce con 3 se lo stato non
e' `ok`/`no-fetch`/`disabled`. Il registro `tsk-id-registry.yaml` non e' letto da qui.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
PREFISSI = {"tsk": "TSK", "us": "US", "ep": "EP"}
REGISTRY_PATH = RADICE / "management" / "kanban" / "id-registry.yaml"
REMOTE = "origin"
BRANCH = "main"
REMOTE_REF = f"{REMOTE}/{BRANCH}"
KANBAN_REL = "management/kanban"
FETCH_TIMEOUT = 30


# ---------------------------------------------------------------------------
# ID presenti sul branch remoto (default origin/main)
# ---------------------------------------------------------------------------

def _git(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", *args], cwd=RADICE, capture_output=True, text=True,
                          env=env, timeout=timeout)


def stems_remoti() -> list[str] | None:
    """Nomi (senza .md) dei file kanban su origin/main, None se il ref non si legge."""
    try:
        r = _git("ls-tree", "-r", "--name-only", REMOTE_REF, "--", KANBAN_REL)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    return [Path(riga).stem for riga in r.stdout.splitlines() if riga.endswith(".md")]


def carica_remoto(fetch: bool = True, enabled: bool = True) -> tuple[list[str], str, str]:
    """(stems, stato, dettaglio). Mai eccezioni: l'assenza di rete e' uno stato.

    Con enabled=False non tocca ne' la rete ne' il ref: stato `disabled`."""
    if not enabled:
        return [], "disabled", ""
    dettaglio = ""
    stato = "no-fetch"
    if fetch:
        try:
            r = _git("fetch", "-q", REMOTE, BRANCH, timeout=FETCH_TIMEOUT)
            if r.returncode == 0:
                stato = "ok"
            else:
                stato, dettaglio = "stale", (r.stderr.strip().splitlines() or ["fetch fallito"])[-1]
        except subprocess.TimeoutExpired:
            stato, dettaglio = "stale", f"fetch oltre {FETCH_TIMEOUT}s"
        except OSError as e:
            stato, dettaglio = "stale", str(e)
    stems = stems_remoti()
    if stems is None:
        return [], "unavailable", dettaglio or f"{REMOTE_REF} non leggibile"
    return stems, stato, dettaglio


# ---------------------------------------------------------------------------
# Comportamento base (senza namespace) — invariato rispetto a pre-US-314
# ---------------------------------------------------------------------------

def massimo(prefisso: str, remoti: list[str] | None = None) -> int:
    """Il massimo su TUTTI i file, inclusi `cancelled` e archivio (e, se dati, quelli remoti)."""
    trovati = [
        int(m.group(1))
        for percorso in RADICE.joinpath("management/kanban").rglob(f"{prefisso}-*.md")
        for m in [re.match(rf"{prefisso}-(\d+)", percorso.stem)] if m
    ]
    trovati += [int(m.group(1)) for st in remoti or []
                for m in [re.match(rf"{prefisso}-(\d+)", st)] if m]
    return max(trovati, default=0)


def duplicati(prefisso: str) -> dict[str, list[str]]:
    visti: dict[str, list[str]] = {}
    for percorso in RADICE.joinpath("management/kanban").rglob(f"{prefisso}-*.md"):
        visti.setdefault(percorso.stem, []).append(
            str(percorso.relative_to(RADICE / "management/kanban")))
    return {k: v for k, v in visti.items() if len(v) > 1}


# ---------------------------------------------------------------------------
# Comportamento con --namespace (EP-069 US-314)
# ---------------------------------------------------------------------------

def _load_registry() -> dict:
    """Carica il registro YAML. Ritorna {} se assente o malformato (fail-open)."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        import yaml  # PyYAML — gia' usato da altri tool di M
        return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def massimo_con_namespace(prefisso: str, namespace: str,
                          remoti: list[str] | None = None) -> int:
    """Massimo considerando file sul filesystem E prenotazioni nel registro.

    Garantisce che il prossimo ID suggerito non cada in un range gia' prenotato
    da un'altra epica — anche se i file non sono ancora stati creati.
    """
    kanban = RADICE / "management" / "kanban"
    pattern = re.compile(rf"^{re.escape(namespace)}-{prefisso}-(\d+)$")
    fs_max = max(
        (int(m.group(1))
         for percorso in kanban.rglob(f"{namespace}-{prefisso}-*.md")
         for m in [pattern.match(percorso.stem)] if m),
        default=0,
    )

    reg = _load_registry()
    reservations = reg.get("reservations") or []
    kind_lc = prefisso.lower()
    reg_max = max(
        (int(r.get("to", 0))
         for r in reservations
         if r.get("prefix") == namespace and r.get("kind", "").lower() == kind_lc),
        default=0,
    )
    remote_max = max(
        (int(m.group(1)) for st in remoti or [] for m in [pattern.match(st)] if m),
        default=0,
    )
    return max(fs_max, reg_max, remote_max)


def duplicati_con_namespace(prefisso: str, namespace: str) -> dict[str, list[str]]:
    kanban = RADICE / "management" / "kanban"
    pattern = re.compile(rf"^{re.escape(namespace)}-{prefisso}-\d+$")
    visti: dict[str, list[str]] = {}
    for percorso in kanban.rglob(f"{namespace}-{prefisso}-*.md"):
        if pattern.match(percorso.stem):
            visti.setdefault(percorso.stem, []).append(
                str(percorso.relative_to(kanban)))
    return {k: v for k, v in visti.items() if len(v) > 1}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    global REMOTE, BRANCH, REMOTE_REF
    parser = argparse.ArgumentParser(
        description="Prossimo identificativo libero, EP / US / TSK.",
        add_help=True,
    )
    parser.add_argument(
        "tipo", nargs="?", default="tsk",
        help="tipo di artefatto: tsk | us | ep (default: tsk)",
    )
    parser.add_argument(
        "quanti", nargs="?", type=int, default=1,
        help="quanti identificativi consecutivi stampare (default: 1)",
    )
    parser.add_argument(
        "--namespace", metavar="PREFIX",
        help="prefisso namespace (es. UP, FAC) — opt-in, richiede id-registry.yaml",
    )
    parser.add_argument(
        "--no-fetch", action="store_true",
        help="non fa il fetch: legge l'origin/main gia' scaricato",
    )
    parser.add_argument(
        "--remote", default=REMOTE, help=f"remote da cui leggere gli ID (default {REMOTE})",
    )
    parser.add_argument(
        "--branch", default=BRANCH, help=f"branch del remote (default {BRANCH})",
    )
    parser.add_argument(
        "--no-remote", action="store_true",
        help="non legge il remoto (come NEXT_ID_OFFLINE=1): solo filesystem locale",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="stampa un documento JSON (ids, remote, detail) invece degli ID in chiaro",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="esce con 3 se l'origin/main non e' stato aggiornato (offline) invece di 0",
    )
    args = parser.parse_args(argv)

    tipo = args.tipo.lower()
    if tipo not in PREFISSI:
        print(f"tipo sconosciuto: {tipo} (attesi: {', '.join(PREFISSI)})", file=sys.stderr)
        return 2

    prefisso = PREFISSI[tipo]
    REMOTE, BRANCH = args.remote, args.branch
    REMOTE_REF = f"{REMOTE}/{BRANCH}"
    offline = args.no_remote or os.environ.get("NEXT_ID_OFFLINE", "").strip().lower() in (
        "1", "true", "yes", "si")
    remoti, stato, dettaglio = carica_remoto(fetch=not args.no_fetch, enabled=not offline)
    rc = 3 if args.strict and stato in ("stale", "unavailable") else 0
    if args.namespace:
        ns = args.namespace.upper()
        primo = massimo_con_namespace(prefisso, ns, remoti) + 1
        ids = [f"{ns}-{prefisso}-{primo + i:03d}" for i in range(args.quanti)]
    else:
        primo = massimo(prefisso, remoti) + 1
        # Zero-padding a 3 cifre: gli identificativi del repo sono `EP-067`, non `EP-67`.
        # Stamparli senza padding produce un ID che non corrisponde a nessuna convenzione
        # e che il giorno dopo qualcuno copia.
        ids = [f"{prefisso}-{primo + i:03d}" for i in range(args.quanti)]

    if args.json:
        print(json.dumps({"ids": ids, "remote": stato, "detail": dettaglio}))
    else:
        for i in ids:
            print(i)
    if stato in ("stale", "unavailable"):
        quale = ("uso l'ultimo origin/main gia' scaricato, potrebbe essere vecchio"
                 if stato == "stale" else "calcolo sul solo filesystem locale")
        print(f"# AVVISO: {REMOTE_REF} non aggiornato ({dettaglio}): {quale}. "
              "L'ID potrebbe collidere con uno creato altrove.", file=sys.stderr)
        print(f"# next-id-remote: {stato}", file=sys.stderr)

    if args.namespace:
        dup = duplicati_con_namespace(prefisso, ns)
        if dup:
            print(f"\n# {len(dup)} identificativi {ns}-{prefisso} duplicati:", file=sys.stderr)
            for k in sorted(dup)[:5]:
                print(f"#   {k}", file=sys.stderr)
    else:
        esistenti = duplicati(prefisso)
        if esistenti:
            print(f"\n# {len(esistenti)} identificativi {prefisso} duplicati nel repo "
                  f"(storici, vedi tests/test_id_unici.py):", file=sys.stderr)
            for k in sorted(esistenti)[:5]:
                print(f"#   {k}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
