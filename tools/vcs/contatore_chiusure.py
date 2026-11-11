#!/usr/bin/env python3
"""contatore_chiusure.py — trigger `on_tsk_closed_count` di repo-align e ai_policy_check.

Ogni chiusura di TSK (`status: done`) incrementa un contatore per capability; alla soglia lo
script dice quale verifica eseguire e azzera il contatore. Lo chiama `dev-handoff` a fine TSK.

  capability        blocco di config     contatore                        verifica da eseguire
  repo-align        repo_align           memory/repo-align-counter.yaml   python3 tools/vcs/repo-align.py
  ai-policy-check   ai_policy_check      memory/ai-policy-counter.yaml    python3 tools/vcs/ai-policy-scan.py

Gate per capability: `enabled: true` e `triggers.on_tsk_closed_count` > 0. Altrimenti nulla.

USO:
  python3 tools/vcs/contatore_chiusure.py --tsk <TSK-id> [--root <factory>] [--json] [--now ISO8601]

Solo stdlib, config letta come testo. Mai bloccante: un errore (contatore illeggibile, file non
scrivibile) e' un avviso su stdout, exit 0. Scrive solo i due file di contatore.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

CAPABILITY = (
    ("repo-align", "repo_align", "memory/repo-align-counter.yaml", "python3 tools/vcs/repo-align.py"),
    ("ai-policy-check", "ai_policy_check", "memory/ai-policy-counter.yaml", "python3 tools/vcs/ai-policy-scan.py"),
)


def blocco(testo: str, chiave: str) -> list[str]:
    """Righe del blocco top-level `chiave:` (fino alla chiave top-level successiva)."""
    righe = testo.splitlines()
    for i, r in enumerate(righe):
        if re.match(r"^%s:\s*(#.*)?$" % re.escape(chiave), r):
            out = []
            for s in righe[i + 1:]:
                if s.strip() and not s.startswith((" ", "\t")) and not s.lstrip().startswith("#"):
                    break
                out.append(s)
            return out
    return []


def _valore(righe: list[str], chiave: str, indent: int) -> str | None:
    for r in righe:
        m = re.match(r"^ {%d}%s:\s*([^#\n]*)" % (indent, re.escape(chiave)), r)
        if m:
            return m.group(1).strip().strip("\"'")
    return None


def soglia(testo: str, chiave: str) -> int:
    """0 se la capability e' spenta, assente o senza soglia."""
    righe = blocco(testo, chiave)
    if (_valore(righe, "enabled", 2) or "").lower() != "true":
        return 0
    try:
        trig = blocco("\n".join(r[2:] for r in righe if r.startswith("  ") or not r.strip()), "triggers")
        return max(0, int(_valore(trig, "on_tsk_closed_count", 2) or 0))
    except ValueError:
        return 0


def leggi_contatore(p: Path) -> int:
    if not p.is_file():
        return 0
    m = re.search(r"^count:\s*(\d+)", p.read_text(encoding="utf-8"), re.M)
    if not m:
        raise ValueError("%s senza `count:` leggibile" % p)
    return int(m.group(1))


def scrivi_contatore(p: Path, count: int, tsk: str, ora: str, reset: str | None) -> None:
    """Riscrive i quattro campi; i commenti del file (intestazione della factory) restano."""
    commenti, precedente = [], ""
    if p.is_file():
        testo = p.read_text(encoding="utf-8")
        commenti = [r for r in testo.splitlines() if r.lstrip().startswith("#")]
        m = re.search(r"^last_reset_at:\s*(\S+)", testo, re.M)
        precedente = m.group(1) if m and m.group(1) != "null" else ""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(c + "\n" for c in commenti)
                 + "count: %d\nlast_reset_at: %s\nlast_tsk_id: %s\nlast_seen_at: %s\n"
                 % (count, reset or precedente or "null", tsk, ora), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tsk", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    radice = Path(a.root)
    ora = a.now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cfg = radice / "factory.config.yaml"
    testo = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    esiti = []
    for nome, chiave, rel, comando in CAPABILITY:
        n = soglia(testo, chiave)
        if not n:
            continue
        p = radice / rel
        try:
            count = leggi_contatore(p) + 1
            raggiunta = count >= n
            scrivi_contatore(p, 0 if raggiunta else count, a.tsk, ora, ora if raggiunta else None)
            esiti.append({"capability": nome, "count": count, "soglia": n, "esegui": comando if raggiunta else None})
        except (OSError, ValueError) as e:
            esiti.append({"capability": nome, "errore": str(e)})
    if a.json:
        print(json.dumps(esiti, ensure_ascii=False))
        return 0
    for e in esiti:
        if "errore" in e:
            print("[%s] contatore: errore non fatale — %s. L'handoff prosegue." % (e["capability"], e["errore"]))
        elif e["esegui"]:
            print("[%s] soglia raggiunta (%d/%d TSK chiusi): esegui `%s` e riporta l'output integrale."
                  % (e["capability"], e["count"], e["soglia"], e["esegui"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
