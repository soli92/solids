#!/usr/bin/env python3
"""Day 0 per ruolo, mostrato nel benvenuto di chi apre la factory per la prima volta.

Il testo per ruolo sta nel file indicato da onboarding_day0.file (default
.claude/skills/references/onboarding/day0-per-ruolo.md): una sezione «## <ruolo>» per ruolo,
piu' «## generico» per chi non dichiara il ruolo. I ruoli validi e le loro etichette vengono da
onboarding_day0.roles (slug: etichetta) in factory.config.yaml; senza, dall'elenco neutro di
tools/promemoria/promemoria.py. Il ruolo viene da --ruolo oppure, se /promemoria e' acceso,
dall'anagrafica (campo `ruolo` del file operatore); senza ruolo vale la sezione «generico».

La dipendenza da /promemoria e' opzionale: a promemoria_operatori.enabled false (o modulo assente) il Day 0
funziona lo stesso, con ruolo da --ruolo o «generico».

  day0.py [--ruolo <r>|salta] [--json] [--root <path>]

Exit: 0 ok; 2 ruolo sconosciuto; 1 file del Day 0 assente o senza la sezione richiesta.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAY0 = ".claude/skills/references/onboarding/day0-per-ruolo.md"


def _promemoria(root: Path):
    """Modulo promemoria.py della factory, o None se assente/non caricabile."""
    script = root / "tools/promemoria/promemoria.py"
    if not script.is_file():
        script = ROOT / "tools/promemoria/promemoria.py"
    try:
        spec = importlib.util.spec_from_file_location("promemoria", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (OSError, ImportError, SyntaxError):
        return None


def sections(text: str) -> dict:
    found = {}
    for m in re.finditer(r"^## (\S+)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        found[m.group(1)] = m.group(2).strip()
    return found


def day0_config(root: Path, pm) -> dict:
    """Blocco onboarding_day0 (file, enabled); {} se config assente o senza pyyaml."""
    cfg = pm.load_config(root) if pm else {}
    day0 = cfg.get("onboarding_day0")
    return day0 if isinstance(day0, dict) else {}


def run(argv=None) -> tuple:
    parser = argparse.ArgumentParser(description="Day 0 per ruolo")
    parser.add_argument("--ruolo")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)
    pm = _promemoria(root)
    pm_acceso = False
    if pm is not None:
        try:
            pm_acceso = pm.configure(root)   # imposta anche pm.RUOLI da onboarding_day0.roles
        except pm.Errore as exc:
            print(f"day0: config di /promemoria non valida: {exc}", file=sys.stderr)
    ruoli = dict(pm.RUOLI) if pm is not None else {}
    cfg = day0_config(root, pm)
    day0_file = str(cfg.get("file") or DAY0)
    try:
        testi = sections((root / day0_file).read_text(encoding="utf-8"))
    except OSError as exc:
        return 1, {"errore": f"{day0_file} non leggibile: {exc}"}
    if not ruoli:
        ruoli = {r: r for r in testi if r != "generico"}
    ruolo, fonte = args.ruolo, "--ruolo"
    if ruolo is None:
        op = None
        if pm_acceso:
            try:
                _, op = pm.current_operator(root, pm.load_operatori(root))
            except (pm.Errore, OSError) as exc:
                print(f"day0: anagrafica non letta: {exc}", file=sys.stderr)
        ruolo, fonte = (op or {}).get("ruolo"), "anagrafica" if pm_acceso else "default"
    if ruolo in (None, "salta"):
        ruolo = "generico"
    elif ruolo not in ruoli:
        return 2, {"errore": f"ruolo sconosciuto: {ruolo}", "ruoli": [*ruoli, "salta"]}
    if ruolo not in testi:
        return 1, {"errore": f"{day0_file}: manca la sezione «## {ruolo}»"}
    return 0, {"ruolo": ruolo, "etichetta": ruoli.get(ruolo, "nessun ruolo"), "fonte": fonte,
               "azioni": testi[ruolo],
               # promemoria spento: il ruolo non si puo' registrare, quindi non lo si propone
               "nota_ruolo": "Dichiara il tuo ruolo con /promemoria --registrami --ruolo=<ruolo> "
                             "e /onboarding ti mostra azioni più adatte."
                             if ruolo == "generico" and pm_acceso else None,
               "promemoria_acceso": pm_acceso,
               "onboarding_enabled": bool(cfg.get("enabled"))}


def render(payload: dict) -> str:
    righe = [f"Day 0 — {payload['etichetta']}", payload["azioni"]]
    if payload["nota_ruolo"]:
        righe.append(payload["nota_ruolo"])
    return "\n".join(righe)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    code, payload = run(argv)
    as_json = "--json" in (argv if argv is not None else sys.argv[1:])
    if code != 0 or as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout if as_json else sys.stderr)
    else:
        print(render(payload))
    return code


if __name__ == "__main__":
    sys.exit(main())
