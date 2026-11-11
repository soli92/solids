#!/usr/bin/env python3
"""
claim-intent-log.py — EP-064/US-251/TSK-576

Registra l'INTENTO DI CLAIM in avanti, e nient'altro: quando una sessione (umana
o agentica) sta per lavorare su un task, annota `{task, attore, timestamp}` in un
log locale append-only. E' la registrazione che il trial usa per misurare cio'
che la storia di git non puo' mostrare — due sessioni indipendenti che
committano con la stessa identita' autrice sono indistinguibili in git.

Cosa NON fa, per disegno (US-251 BR4 — nessun enforcement):
  - non blocca nessuna operazione e non nega nessun claim: a questo stadio
    «claim negato» NON ESISTE come concetto;
  - non attende risposte, non apre socket, non crea processi residenti:
    scrive una riga e termina;
  - non legge ne' scrive `status:` di alcun TSK, non modifica alcun file del
    kanban, non fa git;
  - non restituisce nulla che il chiamante debba interpretare: l'exit code e'
    SEMPRE 0 sul percorso di scrittura (fail-open totale).

A STRUMENTO ASSENTE IL COMPORTAMENTO DELLA FACTORY E' IDENTICO A OGGI: nessun
modulo della factory importa questo file, nessuna skill lo richiede come passo
obbligatorio, nessun percorso critico lo attraversa. Rimuovendolo, niente
smette di funzionare — e' precisamente il motivo per cui il trial precede
l'arbitro e non lo presuppone.

Log: `.kanban-trial/claim-intent.jsonl` (gitignorato), una riga JSON per intento,
apertura in modalita' append (`"a"`): nessuna riscrittura, nessun troncamento.

CLI:
  # registra un intento (l'uso normale)
  python3 tools/kanban-trial/claim-intent-log.py --task TSK-573 [--actor be-dev]
          [--actor-kind agent|human] [--session <id>] [--note "..."]
          [--log PATH] [--json]

  # rilettura in sola lettura (nessuna scrittura)
  python3 tools/kanban-trial/claim-intent-log.py --show [--tail N] [--json] [--log PATH]

Exit code:
  0 = sempre, sul percorso di scrittura (anche in caso di errore: fail-open)
  0 = anche su --show; 1 solo se --show non riesce a leggere ED e' richiesto --strict

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-251-trial-strumentato-collisioni/US-251.md
       §AC5 §BR4 §BR5]
"""

import argparse
import getpass
import hashlib
import json
import os
import pathlib
import socket
import sys
from datetime import datetime, timezone

TOOL_NAME = "claim-intent-log.py"
TOOL_VERSION = "1.0.0"

DEFAULT_STATE_DIR = ".kanban-trial"
DEFAULT_LOG_NAME = "claim-intent.jsonl"

#: Valore costante scritto in ogni riga: rende esplicito nel dato stesso che
#: questo stadio osserva e non impone. Un consumatore futuro del log non puo'
#: confondere un intento registrato con un lease concesso.
ENFORCEMENT = "none"


def _ora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_breve(valore):
    """Hash corto e stabile: distingue macchine/utenti senza esporne il nome."""
    if not valore:
        return None
    return hashlib.sha256(str(valore).encode("utf-8", "replace")).hexdigest()[:8]


def _radice_repo(start="."):
    """Toplevel del repo se individuabile senza invocare git; altrimenti cwd.

    Risalita per presenza di `.git`: nessun sottoprocesso, nessuna dipendenza.
    """
    try:
        corrente = pathlib.Path(start).resolve()
    except OSError:
        return pathlib.Path(".")
    for candidato in [corrente] + list(corrente.parents):
        if (candidato / ".git").exists():
            return candidato
    return corrente


def percorso_log(log=None, start="."):
    if log:
        return pathlib.Path(log).expanduser()
    return _radice_repo(start) / DEFAULT_STATE_DIR / DEFAULT_LOG_NAME


def costruisci_entry(task, actor=None, actor_kind=None, session=None, note=None):
    """Costruisce la riga di intento. Nessun contenuto di file, nessun segreto."""
    attore = actor or os.environ.get("CLAIM_ACTOR") or os.environ.get("USER") or "unknown"
    sessione = session or os.environ.get("CLAUDE_SESSION_ID")
    try:
        host = socket.gethostname()
    except OSError:
        host = None
    try:
        utente = getpass.getuser()
    except Exception:  # getpass puo' fallire senza $USER e senza pwd entry
        utente = None

    entry = {
        "ts": _ora_utc(),
        "task": task,
        "actor": attore,
        "actor_kind": actor_kind or ("agent" if os.environ.get("CLAUDE_SESSION_ID") else "human"),
        "session": sessione,
        "machine_hash": _hash_breve(host),
        "user_hash": _hash_breve(utente),
        "enforcement": ENFORCEMENT,
        "tool_version": TOOL_VERSION,
    }
    if note:
        entry["note"] = str(note)[:300]
    return entry


def registra(entry, log=None, start="."):
    """Append di UNA riga JSON. Fail-open: qualunque errore e' assorbito qui.

    Restituisce `(scritto: bool, percorso: str|None, errore: str|None)` a uso
    diagnostico dello strumento stesso; il CHIAMANTE non deve interpretare
    nulla, e infatti main() esce sempre con 0.
    """
    percorso = None
    try:
        percorso = percorso_log(log, start=start)
        percorso.parent.mkdir(parents=True, exist_ok=True)
        riga = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        # "a" = append-only: mai "w", mai troncamento, mai riscrittura.
        with open(percorso, "a", encoding="utf-8") as fh:
            fh.write(riga + "\n")
            fh.flush()
        return True, str(percorso), None
    except Exception as exc:  # disco pieno, permessi, path invalido, ...
        return False, (str(percorso) if percorso else None), f"{type(exc).__name__}: {exc}"


def leggi(log=None, start=".", tail=None):
    """Rilettura in sola lettura. Righe illeggibili saltate, mai un'eccezione."""
    percorso = percorso_log(log, start=start)
    righe, saltate = [], 0
    try:
        with open(percorso, "r", encoding="utf-8") as fh:
            for riga in fh:
                riga = riga.strip()
                if not riga:
                    continue
                try:
                    righe.append(json.loads(riga))
                except ValueError:
                    saltate += 1
    except OSError:
        return {"log": str(percorso), "esiste": False, "voci": [], "totale": 0, "saltate": 0}
    if tail:
        righe = righe[-int(tail):]
    return {
        "log": str(percorso),
        "esiste": True,
        "voci": righe,
        "totale": len(righe),
        "saltate": saltate,
    }


def _costruisci_parser():
    ap = argparse.ArgumentParser(
        prog="claim-intent-log.py",
        description=(
            "Registra l'intento di claim su un task in un log locale append-only. "
            "Strumento di sola osservazione: nessun enforcement, nessun claim "
            "negato, nessun processo persistente (EP-064/US-251 AC5)."
        ),
    )
    ap.add_argument("--task", default=None, metavar="TSK-NNN",
                    help="Identificativo del task su cui si sta per lavorare.")
    ap.add_argument("--actor", default=None, metavar="SLUG",
                    help="Attore (agente o persona). Default: $CLAIM_ACTOR, poi $USER.")
    ap.add_argument("--actor-kind", default=None, choices=("agent", "human"),
                    help="Tipo di attore. Default: agent se $CLAUDE_SESSION_ID e' presente.")
    ap.add_argument("--session", default=None, metavar="ID",
                    help="Identificativo di sessione. Default: $CLAUDE_SESSION_ID.")
    ap.add_argument("--note", default=None, metavar="TESTO",
                    help="Nota libera breve (max 300 caratteri).")
    ap.add_argument("--log", default=None, metavar="PATH",
                    help=f"Percorso del log (default: <repo>/{DEFAULT_STATE_DIR}/{DEFAULT_LOG_NAME}).")
    ap.add_argument("--show", action="store_true",
                    help="Rilegge il log e termina (sola lettura, nessuna scrittura).")
    ap.add_argument("--tail", type=int, default=None, metavar="N",
                    help="Con --show: mostra le ultime N voci.")
    ap.add_argument("--json", action="store_true",
                    help="Output machine-readable su stdout.")
    return ap


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    # Fail-open anche sul parsing: un errore d'uso non deve interrompere il
    # chiamante (US-251 BR4: nessuna risposta da interpretare).
    try:
        args = _costruisci_parser().parse_args(argv)
    except SystemExit:
        return 0

    if args.show:
        stato = leggi(log=args.log, tail=args.tail)
        if args.json:
            print(json.dumps(stato, indent=2, ensure_ascii=False))
        else:
            print(f"log: {stato['log']}")
            if not stato["esiste"]:
                print("  nessun log presente: nessun intento registrato finora.")
                print("  (assenza di dati, non misura di assenza di contesa)")
            else:
                print(f"  voci: {stato['totale']}  righe illeggibili saltate: {stato['saltate']}")
                for voce in stato["voci"]:
                    print(
                        f"  - {voce.get('ts')}  {voce.get('task')}  "
                        f"{voce.get('actor')} [{voce.get('actor_kind')}]  "
                        f"sessione={voce.get('session')}  macchina={voce.get('machine_hash')}"
                    )
        return 0

    if not args.task:
        # Nessun task: niente da registrare. Non e' un errore del chiamante.
        print(
            "claim-intent-log: nessun --task indicato, nessun intento registrato "
            "(strumento di sola osservazione, nessuna operazione bloccata).",
            file=sys.stderr,
        )
        return 0

    entry = costruisci_entry(
        args.task,
        actor=args.actor,
        actor_kind=args.actor_kind,
        session=args.session,
        note=args.note,
    )
    scritto, percorso, errore = registra(entry, log=args.log)

    if args.json:
        print(json.dumps(
            {"registrato": scritto, "log": percorso, "errore": errore, "entry": entry},
            indent=2, ensure_ascii=False,
        ))
    elif scritto:
        print(f"intento registrato (nessun enforcement): {entry['task']} <- {entry['actor']} @ {entry['ts']}")
    else:
        # Fail-open: si segnala su stderr e si esce comunque con 0.
        print(
            f"claim-intent-log: intento NON registrato ({errore}). "
            "L'operazione chiamante prosegue: questo strumento non blocca nulla.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
