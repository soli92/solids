#!/usr/bin/env python3
"""Verifica a un mese del Day 0 per ruolo: cosa hanno fatto le persone registrate dopo una data.

Per ogni operatore il cui file in <promemoria_operatori.dir>/operatori/ e' entrato sul ramo dopo --dal:
data di registrazione, ruolo dichiarato, primo TSK chiuso con il suo nome nel campo «chiuso da»
e prima presa in carico (campo «preso in carico da»), entrambi dalla data di registrazione in poi.
Il TL legge l'elenco e decide se tenere la domanda sul ruolo; il tool non decide nulla.

I nomi dei campi del kanban sono configurabili in onboarding_day0.verify (default: done_by,
preso_in_carico_da, preso_in_carico_il). Un kanban che non li porta da' semplicemente «—».
Richiede l'anagrafica di /promemoria (e quindi promemoria_operatori.enabled true): senza, esce con errore.

  verifica_day0.py --dal AAAA-MM-GG [--ref <ref>] [--json] [--root <path>]

Legge l'anagrafica dalla storia di --ref (default refs/promemoria/<ramo>, aggiornato da /promemoria,
oppure <remote>/<ramo> se quello manca) e il kanban dalla working tree. Nessuna scrittura.
Exit: 0 ok (anche con zero persone: lo dice il campo «persone»); 1 storia git o config non leggibile.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KANBAN = "management/kanban"
GIT_TIMEOUT_S = 60
FM = re.compile(r"^---\n(.*?)\n---", re.S)
CAMPI_DEFAULT = {"done_by": "done_by", "taken_by": "preso_in_carico_da", "taken_at": "preso_in_carico_il"}


def _promemoria(root: Path):
    script = root / "tools/promemoria/promemoria.py"
    if not script.is_file():
        script = ROOT / "tools/promemoria/promemoria.py"
    spec = importlib.util.spec_from_file_location("promemoria", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_S)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: exit {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout


def registrazioni(root: Path, ref: str, operatori: str) -> dict:
    """{slug: data del primo commit che ha aggiunto il file operatore} sulla storia di ref."""
    out = git(root, "log", ref, "--diff-filter=A", "--format=@%cs", "--name-only", "--", operatori)
    found: dict = {}
    current = None
    for line in out.splitlines():
        if line.startswith("@"):
            current = line[1:]
        elif line.endswith(".yaml") and current:
            found[Path(line).stem] = current      # log dal piu' recente: resta il piu' vecchio
    return found


def operatore(root: Path, ref: str, operatori: str, slug: str) -> dict:
    text = git(root, "show", f"{ref}:{operatori}/{slug}.yaml")

    def field(key: str):
        m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
        return m.group(1).strip().strip('"') if m else None
    return {"nome": field("nome") or slug, "ruolo": field("ruolo")}


def names(value: str, following: list) -> list:
    """Campo «chiuso da» in tutte le forme del kanban: "Nome", ["A", "B"], oppure lista YAML a capo."""
    value = value.strip()
    if value.startswith("["):
        return [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
    if value:
        return [value.strip('"\'')]
    return [l.strip()[2:].strip().strip('"\'') for l in following if l.strip().startswith("- ")]


def tsk_index(root: Path, campi: dict) -> list:
    chiave = {campi["done_by"]: "done_by", campi["taken_by"]: "taken_by", campi["taken_at"]: "taken_at",
              "status": "status", "closed_at": "closed_at"}
    pattern = re.compile(r"^(" + "|".join(re.escape(k) for k in chiave) + r"):\s*(.*)$")
    items = []
    for p in sorted((root / KANBAN).rglob("*TSK-*.md")):
        m = FM.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        lines = m.group(1).splitlines()
        data: dict = {"id": p.stem}
        for i, line in enumerate(lines):
            km = pattern.match(line)
            if not km:
                continue
            key, value = chiave[km.group(1)], km.group(2)
            if key == "done_by":
                tail = []
                for nxt in lines[i + 1:]:
                    if not nxt.startswith("  "):
                        break
                    tail.append(nxt)
                data[key] = names(value, tail)
            else:
                data[key] = value.strip().strip('"\'')
        items.append(data)
    return items


def primo(items: list, date_key: str, match):
    hits = sorted((i for i in items if match(i) and i.get(date_key)), key=lambda i: (i[date_key], i["id"]))
    return {"tsk": hits[0]["id"], "data": hits[0][date_key]} if hits else None


def run(argv=None) -> tuple:
    parser = argparse.ArgumentParser(description="Verifica a un mese del Day 0 per ruolo")
    parser.add_argument("--dal", required=True, type=date.fromisoformat)
    parser.add_argument("--ref")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)
    pm = None
    try:
        pm = _promemoria(root)
        if not pm.configure(root):
            return 1, {"errore": "serve l'anagrafica di /promemoria: promemoria_operatori.enabled è false "
                                 "in factory.config.yaml"}
        cfg = pm.load_config(root)
        verify = (cfg.get("onboarding_day0") or {}).get("verify") or {}
        campi = {k: str(verify.get(k) or v) for k, v in CAMPI_DEFAULT.items()}
        ref = args.ref
        if ref is None:
            ha_ref = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", pm.REF],
                                    capture_output=True, timeout=GIT_TIMEOUT_S).returncode == 0
            ref = pm.REF if ha_ref else f"{pm.REMOTE}/{pm.BRANCH}"
        regs = {s: d for s, d in registrazioni(root, ref, pm.OPERATORI_DIR).items()
                if d >= args.dal.isoformat()}
        items = tsk_index(root, campi)
        persone = []
        for slug, dal in sorted(regs.items(), key=lambda kv: (kv[1], kv[0])):
            op = operatore(root, ref, pm.OPERATORI_DIR, slug)
            nome = op["nome"]
            persone.append({
                "slug": slug, "nome": nome, "registrato_il": dal, "ruolo": op["ruolo"],
                "primo_tsk_chiuso": primo(items, "closed_at", lambda i: i.get("status") == "done"
                                          and nome in i.get("done_by", []) and i.get("closed_at", "") >= dal),
                "prima_presa_in_carico": primo(items, "taken_at",
                                               lambda i: i.get("taken_by") == nome
                                               and i.get("taken_at", "") >= dal),
            })
    except (RuntimeError, OSError, subprocess.TimeoutExpired,
            getattr(pm, "Errore", RuntimeError)) as exc:
        return 1, {"errore": str(exc)}
    return 0, {"dal": args.dal.isoformat(), "ref": ref, "persone": persone,
               "con_ruolo": sum(1 for p in persone if p["ruolo"]),
               "con_attivita": sum(1 for p in persone if p["primo_tsk_chiuso"] or p["prima_presa_in_carico"])}


def render(r: dict) -> str:
    if not r["persone"]:
        return (f"Nessuna persona registrata dal {r['dal']} ({r['ref']}): la verifica non dice né sì né no, "
                "conviene rinviarla.")
    righe = [f"Registrati dal {r['dal']}: {len(r['persone'])} · con ruolo {r['con_ruolo']} · "
             f"con attività osservata {r['con_attivita']}"]
    for p in r["persone"]:
        tsk = p["primo_tsk_chiuso"]
        presa = p["prima_presa_in_carico"]
        righe.append(f"- {p['nome']} ({p['registrato_il']}), ruolo {p['ruolo'] or '—'}: "
                     f"primo TSK chiuso {tsk['tsk'] + ' il ' + tsk['data'] if tsk else '—'}; "
                     f"prima presa in carico {presa['tsk'] + ' il ' + presa['data'] if presa else '—'}")
    return "\n".join(righe)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    code, r = run(argv)
    as_json = "--json" in (argv if argv is not None else sys.argv[1:])
    if code:
        print(json.dumps(r, ensure_ascii=False), file=sys.stderr)
    elif as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render(r))
    return code


if __name__ == "__main__":
    sys.exit(main())
