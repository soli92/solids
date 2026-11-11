#!/usr/bin/env python3
"""
team-velocity.py — velocity settimanale sul kanban: punti e TSK chiusi per settimana ISO,
proiezione sul backlog, tempo di attraversamento. Funziona anche senza campi di data nei TSK.

La data di completamento e' `closed_at` del TSK; in assenza, la data del commit che porta
`status:` a `done`. La data di inizio e' `started_at`; in assenza, il primo passaggio a
`in_progress` nella storia git. Il dimensionamento viene da `estimate` (o `size`) convertito
in punti; i giorni stimati da `estimated_days` o dalla tabella `giorni`.

Epiche: tutte quelle sotto la cartella kanban, oppure quelle in `epiche` (config o --epiche).
Archivio: le cartelle `archive/` non contano, salvo `includi_archivio: true`.
La vista per persona esiste solo con --per-persona.

USO:
  python3 tools/analytics/team-velocity.py [--config PATH] [--root PATH] [--epiche A,B]
        [--settimane N] [--dal YYYY-MM-DD] [--per-persona] [--json] [--out PATH]

Senza config valgono i default (tutte le epiche, scala XS=1 S=2 M=3 L=5 XL=8).
DIPENDENZE: solo stdlib Python + git. Read-only: scrive solo il file indicato da --out.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kanban_history import (  # noqa: E402
    CLOSED_FIELDS, DONE_BY_FIELDS, ROOT, STARTED_FIELDS, TSK_RE,
    first_entered, first_field, frontmatter, last_entered, transitions,
)

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
DEFAULTS = {
    "kanban": "management/kanban",
    "epiche": [],  # vuoto = tutte
    "punti": {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8},
    "giorni": {"XS": 0.25, "S": 0.5, "M": 1.0, "L": 2.0, "XL": 4.0},
    "stati_chiusi_esclusi": ["superseded", "cancelled", "on_hold"],
    "finestra_settimane": 3,
    "soglia_chiusura_in_blocco": 5,
    "includi_archivio": False,
    "team": [],      # [{id, nome, alias: []}] — solo per la vista per persona
    "agenti": [],    # owner che sono agenti, non persone
    "obiettivo": None,  # {nome, data_target}
}


def load_config(path, root=ROOT):
    cfg = dict(DEFAULTS)
    p = pathlib.Path(path) if path else None
    if p and not p.is_absolute():
        p = root / p
    if p and p.exists():
        cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")})
    return cfg


def epic_list(cfg, kanban_dir, epic_filter):
    """[(dir_name, id, gruppo)]: le epiche configurate, oppure tutte quelle presenti."""
    dirs = sorted(d.name for d in kanban_dir.iterdir() if d.is_dir() and d.name != "archive") \
        if kanban_dir.is_dir() else []
    conf = [e if isinstance(e, dict) else {"id": e} for e in cfg["epiche"]]
    if not conf:
        pairs = [(d, d.split("-")[0] + "-" + d.split("-")[1] if d.count("-") > 1 else d, "tutte") for d in dirs]
    else:
        pairs = []
        for e in conf:
            for d in dirs:
                if d == e["id"] or d.startswith(e["id"] + "-"):
                    pairs.append((d, e["id"], e.get("gruppo") or e["id"]))
    if epic_filter:
        pairs = [p for p in pairs if p[1] in epic_filter or p[0] in epic_filter]
    return pairs


def load_tasks(cfg, root, epics):
    tasks = {}
    kanban = cfg["kanban"].rstrip("/")
    for d, eid, gruppo in epics:
        for f in sorted((root / kanban / d).rglob("*TSK-*.md")):
            if not cfg["includi_archivio"] and "archive" in f.relative_to(root / kanban).parts:
                continue
            m = TSK_RE.search(f.name)
            if not m:
                continue
            fm = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            rel = f.relative_to(root).as_posix()
            tasks[rel] = {
                "id": m.group(1), "path": rel, "epic": eid, "gruppo": gruppo,
                "status": (fm.get("status") or "").lower().replace("-", "_"),
                "size": (fm.get("estimate") or fm.get("size") or "").upper() or None,
                "estimated_days": fm.get("estimated_days"),
                "persona_raw": fm.get("assignee") or fm.get("owner") or "",
                "done_by": first_field(fm, DONE_BY_FIELDS) or "",
                "started_at": first_field(fm, STARTED_FIELDS, date=True),
                "closed_at": first_field(fm, CLOSED_FIELDS, date=True),
            }
    return tasks


def resolve_persona(raw, team, agenti):
    s = (raw or "").strip().lower()
    if not s:
        return None
    for p in team:
        for name in [p.get("nome"), p["id"], *p.get("alias", [])]:
            if name and name.lower() in s:
                return p["id"]
    if any(a.lower() == s for a in agenti):
        return None
    return raw.strip()


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def week_label(m):
    y, w, _ = m.isocalendar()
    return f"{y}-W{w:02d}"


def working_days(start, end):
    """Giorni lavorativi da start a end, estremi inclusi (un TSK chiuso in giornata vale 1)."""
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if d1 < d0:
        return None
    return sum(1 for i in range((d1 - d0).days + 1) if (d0 + dt.timedelta(days=i)).weekday() < 5) or 1


def percentile(values, q):
    """Percentile nearest-rank: con pochi dati non interpola valori mai osservati."""
    v = sorted(values)
    return v[max(0, -(-len(v) * q // 100) - 1)]


def _tabella(t):
    return " · ".join(f"{k} {v}" for k, v in t.items())


def legenda(cfg, settimane=None):
    finestra = settimane or cfg["finestra_settimane"]
    return [
        f"Punti di un TSK: taglia stimata (`estimate`, altrimenti `size`) con la scala {_tabella(cfg['punti'])}. "
        "Misurano la complessità stimata prima del lavoro, non lo sforzo effettivo. Un TSK senza taglia "
        "conta fra i TSK ma vale 0 punti.",
        f"Velocity: punti dei TSK chiusi per settimana ISO (lunedì-domenica), media sulle ultime {finestra} "
        "settimane concluse; la settimana in corso non entra nella media.",
        "Data di chiusura: `closed_at`, altrimenti la data del commit che porta il TSK a done. Un commit che "
        f"chiude almeno {cfg['soglia_chiusura_in_blocco']} TSK è una registrazione in blocco: la data è quella "
        "della registrazione, non del lavoro.",
        "Ritmo della settimana in corso: punti della settimana × 5 / giorni lavorativi trascorsi.",
        "Proiezione: settimane al completamento = backlog in punti / velocity.",
        "Tempo di attraversamento: giorni lavorativi dall'inizio alla chiusura, confrontati con i giorni "
        f"stimati per taglia ({_tabella(cfg['giorni'])}).",
    ]


def compute(cfg, root=ROOT, epic_filter=None, settimane=None, dal=None, today=None, per_persona=False):
    today = today or dt.date.today()
    kanban = cfg["kanban"].rstrip("/")
    epics = epic_list(cfg, root / kanban, epic_filter)
    gruppi = sorted({g for _, _, g in epics})
    finestra = settimane or cfg["finestra_settimane"]
    punti_tab, giorni_tab = cfg["punti"], cfg["giorni"]
    esclusi = set(cfg["stati_chiusi_esclusi"])
    team, agenti = cfg["team"], cfg["agenti"]

    tasks = load_tasks(cfg, root, epics)
    history = transitions([f"{kanban}/{d}" for d, _, _ in epics], root=root, kanban=kanban) if epics else {}
    per_commit = defaultdict(int)
    events = {}
    for path, hist in history.items():
        h = last_entered(hist, "done")
        if h and path in tasks and tasks[path]["status"] == "done":
            events[path] = (h[1], h[2], h[3])
            per_commit[h[2]] += 1
    soglia = cfg["soglia_chiusura_in_blocco"]
    id_count = defaultdict(int)
    for t in tasks.values():
        id_count[t["id"]] += 1

    done, backlog, senza_stima, senza_data = [], [], [], []
    for path, t in tasks.items():
        t["punti"] = punti_tab.get(t["size"]) if t["size"] else None
        try:
            t["giorni"] = float(t["estimated_days"]) if t["estimated_days"] else giorni_tab.get(t["size"])
        except ValueError:
            t["giorni"] = giorni_tab.get(t["size"])
        if t["punti"] is None and t["status"] not in esclusi and t["status"] != "done":
            senza_stima.append(t["id"])
        if t["status"] == "done":
            ev = events.get(path)
            if t["closed_at"]:
                t["data_done"], t["fonte_data"], t["in_blocco"] = t["closed_at"], "closed_at", False
            elif ev:
                t["data_done"], t["fonte_data"] = ev[0], "git"
                t["in_blocco"] = per_commit[ev[1]] >= soglia
            else:
                senza_data.append(t["id"])
                continue
            if t["started_at"]:
                t["data_inizio"], t["fonte_inizio"] = t["started_at"], "started_at"
            else:
                h = first_entered(history.get(path), "in_progress")
                t["data_inizio"], t["fonte_inizio"] = (h[1], "git") if h else (None, None)
            if per_persona:
                p = resolve_persona(t["done_by"], team, agenti) or resolve_persona(t["persona_raw"], team, agenti)
                t["persona"] = p or (resolve_persona(ev[2], team, agenti) if ev else None) or "non attribuito"
            done.append(t)
        elif t["status"] not in esclusi:
            backlog.append(t)

    if dal:
        done = [t for t in done if t["data_done"] >= dal]
    # con una data di riferimento nel passato, i TSK chiusi dopo non sono ancora done a quella data
    dopo_oggi = sorted(t["id"] for t in done if t["data_done"] > today.isoformat())
    done = [t for t in done if t["data_done"] <= today.isoformat()]

    cur = monday(today)
    first = min((monday(dt.date.fromisoformat(t["data_done"])) for t in done), default=cur)
    weeks, w = [], first
    while w <= cur:
        weeks.append(w)
        w += dt.timedelta(days=7)

    def empty():
        return {"tsk": 0, "punti": 0, "giorni": 0.0, "in_blocco": 0}

    serie = {week_label(w): {"totale": empty(), **{g: empty() for g in gruppi}} for w in weeks}
    persone = defaultdict(lambda: defaultdict(empty))
    for t in done:
        lab = week_label(monday(dt.date.fromisoformat(t["data_done"])))
        buckets = [serie[lab]["totale"], serie[lab][t["gruppo"]]]
        if per_persona:
            buckets.append(persone[t["persona"]][lab])
        for b in buckets:
            b["tsk"] += 1
            b["punti"] += t["punti"] or 0
            b["giorni"] += t["giorni"] or 0
            b["in_blocco"] += int(t["in_blocco"])

    # la media usa solo settimane concluse: quella in corso e' parziale
    concluse = [week_label(w) for w in weeks if w < cur][-finestra:]

    def media(key, gruppo="totale"):
        return sum(serie[l][gruppo][key] for l in concluse) / len(concluse) if concluse else 0.0

    gg_lav = min(today.weekday() + 1, 5)
    in_corso = {g: round(v["punti"] * 5 / gg_lav, 1) for g, v in serie[week_label(cur)].items()}

    ob = cfg.get("obiettivo")
    target = dt.date.fromisoformat(ob["data_target"]) if ob else None
    proiezioni = {}
    for g in ["totale", *(gruppi if len(gruppi) > 1 else [])]:
        rest = [t for t in backlog if g == "totale" or t["gruppo"] == g]
        rest_punti = sum(t["punti"] or 0 for t in rest)
        v = media("punti", g)
        p = {
            "backlog_tsk": len(rest), "backlog_punti": rest_punti,
            "backlog_in_progress": sum(1 for t in rest if t["status"] == "in_progress"),
            "velocity_punti_sett": round(v, 1), "velocity_tsk_sett": round(media("tsk", g), 1),
            "settimane_al_completamento": round(rest_punti / v, 1) if v else None,
            "ritmo_settimana_in_corso": in_corso.get(g, 0.0),
        }
        if v:
            p["data_completamento_stimata"] = (today + dt.timedelta(days=7 * rest_punti / v)).isoformat()
        if target:
            sett = max((target - today).days, 0) / 7
            cap = v * sett
            p.update(settimane_al_target=round(sett, 1), capacita_al_target_punti=round(cap, 1),
                     copertura_backlog_pct=round(100 * cap / rest_punti) if rest_punti else 100)
        proiezioni[g] = p

    durate = defaultdict(list)
    senza_inizio = 0
    for t in done:
        gg = working_days(t["data_inizio"], t["data_done"]) if t.get("data_inizio") else None
        if gg is None:
            senza_inizio += 1
            continue
        durate[t["size"] or "?"].append(gg)
        durate["totale"].append(gg)
    ordine = [k for k in [*punti_tab, "?"] if k in durate] + ["totale"]
    attraversamento = {
        k: {"n": len(durate[k]), "mediana": statistics.median(durate[k]),
            "p85": percentile(durate[k], 85), "stima_giorni": giorni_tab.get(k)}
        for k in ordine if durate.get(k)
    }

    out = {
        "generato": today.isoformat(),
        "epiche": [{"id": e, "gruppo": g} for _, e, g in epics],
        "finestra_settimane": concluse,
        "obiettivo": ob,
        "serie": serie,
        "proiezioni": proiezioni,
        "attraversamento": attraversamento,
        "legenda": legenda(cfg, finestra),
        "qualita_dati": {
            "done_totali": len(done),
            "done_con_closed_at": sum(1 for t in done if t["fonte_data"] == "closed_at"),
            "done_con_data_git": sum(1 for t in done if t["fonte_data"] == "git"),
            "done_registrati_in_blocco": sum(1 for t in done if t["in_blocco"]),
            "done_con_started_at": sum(1 for t in done if t.get("fonte_inizio") == "started_at"),
            "done_con_inizio_da_git": sum(1 for t in done if t.get("fonte_inizio") == "git"),
            "done_senza_inizio": senza_inizio,
            "done_senza_data": sorted(senza_data),
            "done_dopo_riferimento": dopo_oggi,
            "done_senza_taglia": sum(1 for t in done if t["punti"] is None),
            "aperti_senza_stima": sorted(senza_stima),
            "id_duplicati": sorted(i for i, n in id_count.items() if n > 1),
            "archivio_incluso": bool(cfg["includi_archivio"]),
        },
    }
    if per_persona:
        pers = {}
        for pid, by_week in persone.items():
            tot = sum(by_week[l]["punti"] for l in concluse)
            pers[pid] = {
                "punti_finestra": tot, "tsk_finestra": sum(by_week[l]["tsk"] for l in concluse),
                "punti_sett": round(tot / len(concluse), 1) if concluse else 0.0,
                "settimana_in_corso": dict(by_week.get(week_label(cur), empty())),
            }
        out["persone"] = dict(sorted(pers.items(), key=lambda kv: -kv[1]["punti_finestra"]))
    return out


def render(r):
    gruppi = sorted({e["gruppo"] for e in r["epiche"]}) if len({e["gruppo"] for e in r["epiche"]}) > 1 else []
    eps = [e["id"] for e in r["epiche"]]
    titolo = ", ".join(eps) if len(eps) <= 6 else f"{len(eps)} epiche"
    out = [f"# Velocity — {titolo}", "",
           f"Generato il {r['generato']}. Media su {len(r['finestra_settimane'])} settimane concluse: "
           f"{', '.join(r['finestra_settimane']) or 'nessuna'}.", "",
           "## Andamento settimanale (punti / TSK)", "",
           "| Settimana | Totale | " + "".join(f"{g} | " for g in gruppi) + "di cui in blocco |",
           "|---|---|" + "---|" * len(gruppi) + "---|"]
    last = list(r["serie"])[-1] if r["serie"] else None
    for lab, s in r["serie"].items():
        cells = "".join(f"{s[g]['punti']} / {s[g]['tsk']} | " for g in gruppi)
        flag = " (in corso)" if lab == last else ""
        out.append(f"| {lab}{flag} | **{s['totale']['punti']} / {s['totale']['tsk']}** | {cells}"
                   f"{s['totale']['in_blocco']} |")

    out += ["", "## Proiezione", ""]
    ob = r.get("obiettivo")
    head = "| Ambito | Velocity (pt/sett) | TSK/sett | Ritmo sett. in corso | Backlog (pt / TSK) | Fine stimata |"
    sep = "|---|---|---|---|---|---|"
    if ob:
        head += f" Copertura al {ob['data_target']} |"
        sep += "---|"
    out += [head, sep]
    for g, p in r["proiezioni"].items():
        fine = p.get("data_completamento_stimata", "n/d (velocity 0)")
        row = (f"| {g} | {p['velocity_punti_sett']} | {p['velocity_tsk_sett']} | {p['ritmo_settimana_in_corso']} | "
               f"{p['backlog_punti']} / {p['backlog_tsk']} ({p['backlog_in_progress']} in corso) | {fine} |")
        if ob:
            row += f" {p['copertura_backlog_pct']}% ({p['capacita_al_target_punti']} pt) |"
        out.append(row)

    if "persone" in r:
        out += ["", "## Per persona (finestra di media)", "",
                "| Persona | Punti | TSK | Punti/sett | Sett. in corso (pt / TSK) |", "|---|---|---|---|---|"]
        for name, p in r["persone"].items():
            ic = p["settimana_in_corso"]
            if p["tsk_finestra"] or ic["tsk"]:
                out.append(f"| {name} | {p['punti_finestra']} | {p['tsk_finestra']} | {p['punti_sett']} | "
                           f"{ic['punti']} / {ic['tsk']} |")

    if r["attraversamento"]:
        out += ["", "## Tempo di attraversamento (giorni lavorativi, inizio → chiusura)", "",
                "| Taglia | TSK | Mediana | 85° percentile | Stima da tabella |", "|---|---|---|---|---|"]
        for k, a in r["attraversamento"].items():
            stima = a["stima_giorni"] if a["stima_giorni"] is not None else "—"
            out.append(f"| {k} | {a['n']} | {a['mediana']} | {a['p85']} | {stima} |")

    q = r["qualita_dati"]
    out += ["", "## Qualità dei dati", "",
            f"- TSK done considerati: {q['done_totali']} (data da git: {q['done_con_data_git']}, "
            f"da closed_at: {q['done_con_closed_at']}).",
            f"- Inizio: da started_at {q['done_con_started_at']}, da git {q['done_con_inizio_da_git']}, "
            f"non ricavabile {q['done_senza_inizio']} (passati a done senza in_progress registrato).",
            f"- Registrati in blocco: {q['done_registrati_in_blocco']} — la data è quella della "
            "registrazione, non dell'esecuzione: la settimana relativa può risultare gonfiata.",
            f"- Archivio: {'incluso' if q['archivio_incluso'] else 'escluso'}.",
            "- Ritmo settimana in corso: segnale precoce, instabile a inizio settimana."]
    out.append(f"- Done senza taglia (0 punti): {q['done_senza_taglia']}.")
    if q["aperti_senza_stima"]:
        out.append(f"- Aperti senza size/estimate (0 punti nel backlog): {', '.join(q['aperti_senza_stima'])}.")
    if q["done_senza_data"]:
        out.append(f"- Done senza data ricavabile (esclusi): {', '.join(q['done_senza_data'])}.")
    if q.get("done_dopo_riferimento"):
        out.append(f"- Chiusi dopo la data di riferimento (esclusi): {', '.join(q['done_dopo_riferimento'])}.")
    if q["id_duplicati"]:
        out.append(f"- ID presenti in più file (contati come TSK distinti): {', '.join(q['id_duplicati'])}.")
    out += ["", "## Legenda: come si calcolano punti e velocity", ""] + [f"- {riga}" for riga in r["legenda"]]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="analytics/velocity/config.json",
                    help="config JSON (opzionale: se manca valgono i default)")
    ap.add_argument("--root", default=str(ROOT), help="radice del repo git col kanban")
    ap.add_argument("--epiche", help="sottoinsieme di epiche, separate da virgola")
    ap.add_argument("--settimane", type=int, help="finestra di media in settimane concluse")
    ap.add_argument("--dal", help="considera solo i done da questa data (YYYY-MM-DD)")
    ap.add_argument("--per-persona", action="store_true", help="aggiunge la vista per persona (esplicita)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="salva l'output anche su file")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root).resolve()
    cfg = load_config(a.config, root)
    r = compute(cfg, root, a.epiche.split(",") if a.epiche else None, a.settimane, a.dal,
                per_persona=a.per_persona)
    text = json.dumps(r, indent=2, ensure_ascii=False) if a.json else render(r)
    sys.stdout.write(text)
    if a.out:
        p = root / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
