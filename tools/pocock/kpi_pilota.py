#!/usr/bin/env python3
"""
kpi_pilota.py — gli 8 indicatori delle pratiche di ingegneria (blocco engineering_practices).

Tutti i numeri vengono da file del repository e, per il costo, dalle trascrizioni Claude Code
di questa macchina. Nessun numero e' stimato. Finestra: dal giorno --dal (incluso) al giorno
--al (escluso, default domani). I path del kanban e dei registri arrivano da
engineering_practices.{kanban_path,analytics_path} in factory.config.yaml, oppure dagli
argomenti --kanban, --registri, --reports.

Definizioni
  1 copertura_cqrl     TSK del layer --layer (default fe), status done e chiusi nella finestra, che
                       hanno un report in code_quality/reports/ o review_status
                       passed|conditional|rejected.
  2 tsk_correzione     TSK creati nella finestra con fix|bug|hotfix|regress|difett|anomali|
                       inciden|rollback|revert nel titolo, sul totale dei TSK creati nella finestra.
  3 first_pass_cqrl    report CQRL iter-1 (JSON) generati nella finestra con verdetto pass,
                       sul totale degli iter-1.
  4 bug_con_regressione TSK di correzione (come al punto 2) chiusi nella finestra con il campo
                       regression_test valorizzato, sul totale dei TSK di correzione chiusi.
  5 parole_dev         parole delle istruzioni che un /dev su un TSK del layer carica prima del TSK
                       (CLAUDE.md, comando, agente, dev-protocol, dev-handoff, shell-portability,
                       PATTERN indice e moduli, foglia fase-0-gate-steps). --memoria aggiunge il
                       MEMORY.md dell'operatore.
  6 controlli          voci di <registri>/controlli.yaml con data nella finestra e path esistente.
  7 invenzioni         voci di <registri>/invenzioni.yaml con data nella finestra.
  8 costo_per_tsk      costo a listino (analytics/pricing.yaml) delle sessioni di questa macchina
                       nella finestra, diviso per i TSK chiusi nella finestra (tutti i layer).
                       Copre una sola postazione: va letto come andamento, non come totale del team.

Uso:
  python3 tools/pocock/kpi_pilota.py --dal 2026-09-04 --al 2026-10-15
  python3 tools/pocock/kpi_pilota.py --dal 2026-10-15 --json --senza-costo
Opzioni: --layer <prefisso> (default fe); --progetto <dir> per le trascrizioni (default
CLAUDE_PROJECT_DIR o la radice); --memoria <MEMORY.md>; --senza-costo; --out <file>.
Dipendenze: pyyaml (tools/requirements.txt). Nessuna scrittura salvo --out.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _config import ROOT, settings  # noqa: E402

CORREZIONE = re.compile(r"fix|bug|hotfix|regress|difett|anomali|inciden|rollback|revert", re.I)
TSK_ID = re.compile(r"(?:[A-Z]+-)?TSK-\d+")
DEV_FILES = [
    "CLAUDE.md", ".claude/commands/dev.md", ".claude/agents/{layer}-dev.md", ".claude/skills/dev-protocol.md",
    ".claude/skills/dev-handoff.md", ".claude/skills/shell-portability.md", "PATTERN.md",
    "PATTERN-integration.md", "PATTERN-runtime.md", "PATTERN-capabilities.md",
    ".claude/skills/references/dev-protocol/fase-0-gate-steps.md",
]


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v or ""))
    return dt.date.fromisoformat(m.group(1)) if m else None


def frontmatter(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def tasks(kanban):
    out = []
    for f in pathlib.Path(kanban).rglob("*.md"):
        if "TSK-" not in f.name:
            continue
        d = frontmatter(f)
        if d.get("type", "task") != "task" or not d.get("id"):
            continue
        d["_closed"] = as_date(d.get("closed_at") or d.get("completed_at") or d.get("completed")
                               or d.get("closed") or d.get("done_at"))
        d["_created"] = as_date(d.get("created"))
        out.append(d)
    return out


def reported_ids(reports):
    ids = set()
    for f in pathlib.Path(reports).glob("*"):
        ids.update(TSK_ID.findall(f.name))
        if f.suffix == ".json":
            try:
                ids.update(TSK_ID.findall(str(json.load(open(f)).get("tsk_id", ""))))
            except (ValueError, OSError, AttributeError):
                pass
    return ids


def pct(num, den):
    return {"valore": round(100 * num / den, 1) if den else None, "num": num, "den": den, "unita": "%"}


def in_window(d, dal, al):
    return d is not None and dal <= d < al


def kpi(dal, al, *, kanban, registri, reports, root=ROOT, layer="fe", progetto=None, memoria=None,
        con_costo=False):
    ts = tasks(kanban)
    res = {}

    done_layer = [t for t in ts if str(t.get("layer", "")).startswith(layer) and t.get("status") == "done"
                  and in_window(t["_closed"], dal, al)]
    rep = reported_ids(reports)
    covered = [t for t in done_layer if t["id"] in rep or
               str(t.get("review_status", "")).lower().startswith(("pass", "conditional", "reject"))]
    res["1_copertura_cqrl"] = pct(len(covered), len(done_layer))

    created = [t for t in ts if in_window(t["_created"], dal, al)]
    res["2_tsk_correzione"] = pct(sum(bool(CORREZIONE.search(str(t.get("title", "")))) for t in created), len(created))

    it1 = []
    for f in pathlib.Path(reports).glob("*-iter-1.json"):
        try:
            d = json.load(open(f))
        except (ValueError, OSError):
            continue
        if in_window(as_date(d.get("generated_at")), dal, al):
            it1.append(str(d.get("verdict", "")).lower())
    res["3_first_pass_cqrl"] = pct(sum(v == "pass" for v in it1), len(it1))

    fixes = [t for t in ts if t.get("status") == "done" and in_window(t["_closed"], dal, al)
             and CORREZIONE.search(str(t.get("title", "")))]
    res["4_bug_con_regressione"] = pct(sum(bool(str(t.get("regression_test") or "").strip()) for t in fixes), len(fixes))

    root = pathlib.Path(root)
    words = sum(len((root / f).read_text(encoding="utf-8", errors="replace").split())
                for f in (x.format(layer=layer) for x in DEV_FILES) if (root / f).exists())
    if memoria:
        words += len(pathlib.Path(memoria).read_text(encoding="utf-8").split())
    res["5_parole_dev"] = {"valore": words, "unita": "parole", "memoria_inclusa": bool(memoria)}

    def registro(nome, chiave):
        p = pathlib.Path(registri) / nome
        if not p.exists():
            return []
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get(chiave) or []
    ctrl = [c for c in registro("controlli.yaml", "controlli")
            if in_window(as_date(c.get("data")), dal, al) and (root / str(c.get("path", ""))).is_file()]
    res["6_controlli"] = {"valore": len(ctrl), "unita": "controlli"}
    inv = [c for c in registro("invenzioni.yaml", "casi") if in_window(as_date(c.get("data")), dal, al)]
    res["7_invenzioni"] = {"valore": len(inv), "unita": "casi"}

    done = [t for t in ts if t.get("status") == "done" and in_window(t["_closed"], dal, al)]
    if con_costo:
        spec = importlib.util.spec_from_file_location("cost_alert", root / "tools" / "analytics" / "cost_alert.py")
        ca = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ca)
        start = dt.datetime.combine(dal, dt.time(), dt.timezone.utc)
        end = dt.datetime.combine(al, dt.time(), dt.timezone.utc)
        tdir = ca.transcripts_dir(progetto or str(root))
        files = ca.window_files(tdir, start)
        m_all = ca.measure(files, ca.Pricer(root), start)["cost_usd"]
        m_after = ca.measure(files, ca.Pricer(root), end)["cost_usd"] if end < dt.datetime.now(dt.timezone.utc) else 0.0
        cost = m_all - m_after
        res["8_costo_per_tsk"] = {"valore": round(cost / len(done), 2) if done else None, "unita": "USD",
                                  "costo_usd": round(cost, 2), "tsk_chiusi": len(done),
                                  "trascrizioni": str(tdir)}
    else:
        res["8_costo_per_tsk"] = {"valore": None, "unita": "USD", "tsk_chiusi": len(done), "nota": "--senza-costo"}
    return res


ETICHETTE = {
    "1_copertura_cqrl": "TSK del layer chiusi con review CQRL",
    "2_tsk_correzione": "TSK di correzione sul totale dei TSK creati",
    "3_first_pass_cqrl": "Review CQRL promosse al primo giro",
    "4_bug_con_regressione": "TSK di correzione chiusi con test di regressione",
    "5_parole_dev": "Parole di istruzioni caricate da /dev",
    "6_controlli": "Errori meccanici diventati controlli automatici",
    "7_invenzioni": "Casi documentati di agenti che inventano",
    "8_costo_per_tsk": "Costo a listino per TSK chiuso (una postazione)",
}


def fmt(v):
    if v.get("valore") is None:
        return "n.d." + (f" (0 su {v['den']})" if "den" in v else "")
    if v["unita"] == "%":
        return f"{v['valore']}% ({v['num']} su {v['den']})"
    if v["unita"] == "USD":
        return f"{v['valore']} USD ({v['costo_usd']} USD / {v['tsk_chiusi']} TSK)"
    return f"{v['valore']:,} {v['unita']}".replace(",", ".")


def main(argv=None):
    cfg = settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dal", required=True, type=dt.date.fromisoformat)
    ap.add_argument("--al", type=dt.date.fromisoformat, default=dt.date.today() + dt.timedelta(days=1))
    ap.add_argument("--kanban", default=str(ROOT / cfg["kanban_path"]))
    ap.add_argument("--registri", default=str(ROOT / cfg["analytics_path"]))
    ap.add_argument("--reports", default=str(ROOT / "code_quality" / "reports"))
    ap.add_argument("--layer", default="fe")
    ap.add_argument("--progetto", default=os.environ.get("CLAUDE_PROJECT_DIR") or str(ROOT))
    ap.add_argument("--memoria")
    ap.add_argument("--senza-costo", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    res = kpi(a.dal, a.al, kanban=a.kanban, registri=a.registri, reports=a.reports, layer=a.layer,
              progetto=a.progetto, memoria=a.memoria, con_costo=not a.senza_costo)
    if a.json:
        print(json.dumps({"dal": str(a.dal), "al": str(a.al), "kpi": res}, ensure_ascii=False, indent=2))
        return 0
    righe = [f"| {i} | {ETICHETTE[k]} | {fmt(v)} |" for i, (k, v) in enumerate(res.items(), 1)]
    testo = (f"Indicatori delle pratiche di ingegneria, finestra dal {a.dal} al {a.al} (escluso)\n\n"
             "| # | Indicatore | Valore |\n|---|---|---|\n" + "\n".join(righe) + "\n")
    print(testo)
    if a.out:
        pathlib.Path(a.out).write_text(testo, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
