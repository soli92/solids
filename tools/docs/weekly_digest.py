#!/usr/bin/env python3
"""
weekly_digest.py — digest settimanale per il management.

Raccoglie in modo deterministico i dati di una settimana ISO (lunedi-domenica, fuso
Europe/Rome per le date con ora) da kanban, log della wiki, gap, incidenti, event store dei
costi e cartella deliverables, e li rende in una pagina HTML autocontenuta e in un file Word
(python-docx facoltativo). Tutti i numeri vengono dallo script.

USO:
  python3 tools/docs/weekly_digest.py [--settimana 2026-W41] [--json] [--out DIR]
                                      [--commento FILE.md]

Solo libreria standard (PyYAML e python-docx facoltativi). Read-only su kanban e wiki.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent


def find_root(start: Path = HERE) -> Path:
    for p in [start, *start.parents]:
        if (p / "factory.config.yaml").is_file():
            return p
    return start.parents[1]


ROOT = find_root()

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CLOSED_STATUSES = ("done", "completed")
CLOSED_FIELDS = ("closed_at", "closed", "completed_at", "completed", "done_at")
DONE_BY_FIELDS = ("done_by", "closed_by", "resolved_by")
TSK_FILE = re.compile(r"(?:^|-)TSK-\d+\.md$")
EPIC_IN_PATH = re.compile(r"^[A-Z]+-EP-\d+$")

DEFAULT_CONFIG = {"output_dir": "deliverables/digest", "redaction": True, "enabled": True, "release_kinds": []}


# ---------------------------------------------------------------------------
# Settimana e fuso
# ---------------------------------------------------------------------------

def parse_week(week: str):
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week or "")
    if not m:
        raise ValueError(f"settimana non valida: {week!r} (formato atteso YYYY-Www)")
    start = dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    return start, start + dt.timedelta(days=6)


def current_week(today: dt.date | None = None) -> str:
    y, w, _ = (today or dt.date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def _last_sunday(year: int, month: int) -> dt.date:
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def rome_offset(utc: dt.datetime) -> int:
    """Ore di scarto di Europe/Rome rispetto a UTC (regola UE: ultima domenica di marzo/ottobre, 01:00 UTC)."""
    y = utc.year
    begin = dt.datetime.combine(_last_sunday(y, 3), dt.time(1))
    end = dt.datetime.combine(_last_sunday(y, 10), dt.time(1))
    return 2 if begin <= utc.replace(tzinfo=None) < end else 1


def utc_to_rome_date(value: str) -> dt.date | None:
    """Data locale (Europe/Rome) di un timestamp ISO; con 'Z' o offset e' convertita, senza ora e' la data stessa."""
    value = (value or "").strip().strip('"').strip("'")
    if not ISO_DATE.match(value):
        return None
    if len(value) <= 10:
        return dt.date.fromisoformat(value)
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return dt.date.fromisoformat(value[:10])
    if t.tzinfo is None:
        return t.date()
    utc = (t - t.utcoffset()).replace(tzinfo=None)
    return (utc + dt.timedelta(hours=rome_offset(utc))).date()


def in_week(d: dt.date | None, start: dt.date, end: dt.date) -> bool:
    return d is not None and start <= d <= end


# ---------------------------------------------------------------------------
# Riuso dei moduli esistenti
# ---------------------------------------------------------------------------

def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_reuse(root_tools: Path, notes: list):
    """Carica kanban_history, team-velocity e cost_alert dalla cartella tools/analytics di questa factory."""
    out = {"history": None, "velocity": None, "cost": None}
    an = root_tools / "analytics"
    sys.path.insert(0, str(an))
    try:
        out["history"] = _load("kanban_history", an / "kanban_history.py")
        notes.append("Lettura dei campi kanban (frontmatter, alias di data e di autore): "
                     "riuso di tools/analytics/kanban_history.py, lo stesso modulo di /velocity.")
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente
        notes.append(f"kanban_history.py non importabile ({exc}): lettura del frontmatter con codice proprio.")
    try:
        out["velocity"] = _load("team_velocity", an / "team-velocity.py")
        notes.append("Attribuzione delle persone (alias): riuso di "
                     "resolve_persona di tools/analytics/team-velocity.py.")
    except Exception as exc:  # pragma: no cover
        notes.append(f"team-velocity.py non importabile ({exc}): nomi delle persone non normalizzati.")
    try:
        out["cost"] = _load("cost_alert", an / "cost_alert.py")
        notes.append("Prezzi e calcolo del costo: riuso di Pricer di tools/analytics/cost_alert.py "
                     "con il listino analytics/pricing.yaml.")
    except Exception as exc:  # pragma: no cover
        notes.append(f"cost_alert.py non importabile ({exc}): costo non calcolato.")
    return out


COST_RULE = (
    "Costo token: gli eventi dell'event store di tipo session-aggregate sono istantanee cumulative della "
    "stessa sessione (stesso task_id, hash diverso). Per ogni sessione si prende l'ultima istantanea con data "
    "nella settimana e si sottrae l'ultima istantanea della stessa sessione precedente all'inizio della "
    "settimana (se c'e'), contatore per contatore (mai sotto zero); gli altri eventi sono sommati uno per uno.")

NOT_REUSED = [
    "Il comando /velocity (team-velocity.py compute) non e' riusato per il conteggio dei TSK chiusi: "
    "copre solo tre epiche configurate e ricava la data di chiusura anche dalla storia git, mentre il "
    "digest conta tutte le epiche e usa solo la data scritta nel TSK. Dove le due letture coincidono "
    "(TSK con closed_at) il criterio di data e' lo stesso; la scala dei punti e' quella di "
    "analytics/velocity/config.json.",
    "Il report PM (tools/coordinamento/aggrega.py) e' una procedura a riga di comando con un proprio "
    "archivio di misure, non una libreria: non ha funzioni per settimana, quindi non e' usato.",
]


# ---------------------------------------------------------------------------
# Kanban
# ---------------------------------------------------------------------------

def _fm_fallback(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            km = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if km and km.group(1) not in out:
                out[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return out


def _names(raw: str) -> list:
    """done_by: 'Nome', "Nome", oppure lista ["A", "B"]."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        parts = re.findall(r"""["']([^"']+)["']""", raw) or [p.strip() for p in raw.strip("[]").split(",")]
    else:
        parts = [raw.strip('"').strip("'")]
    return [p.strip() for p in parts if p.strip()]


def load_points(root: Path) -> dict:
    cfg = root / "analytics" / "velocity" / "config.json"
    try:
        return json.loads(cfg.read_text(encoding="utf-8")).get("punti", {})
    except (OSError, ValueError):
        return {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}


def _team(root: Path, reuse: dict):
    """Resolver che riporta done_by a un nome; None se manca la configurazione del team.

    Il team viene da load_config di team-velocity.py (team, agenti, team_config, alias_extra), cosi'
    la firma resta quella di resolve_persona(raw, team, agenti): un owner agente diventa «agente»,
    un nome fuori dal team resta com'e'."""
    velocity = reuse.get("velocity")
    if velocity is None:
        return None
    try:
        vcfg = velocity.load_config("analytics/velocity/config.json", root)
    except (OSError, ValueError, KeyError):
        return None
    team, agenti = vcfg.get("team") or [], vcfg.get("agenti") or []
    if not team:
        return None
    nomi = {p["id"]: p.get("nome") or p["id"] for p in team}

    def resolve(raw: str) -> str:
        pid = velocity.resolve_persona(raw, team, agenti)
        if pid is None:
            return "agente" if raw.strip() else ""
        return nomi.get(pid, pid)
    return resolve


def _epic_titles(root: Path) -> dict:
    out = {}
    kb = root / "management" / "kanban"
    if not kb.is_dir():
        return out
    for d in sorted(kb.iterdir()):
        f = d / f"{d.name}.md"
        if d.is_dir() and EPIC_IN_PATH.match(d.name) and f.is_file():
            title = _fm_fallback(f.read_text(encoding="utf-8", errors="replace")).get("title", "")
            out[d.name] = title
    return out


def collect_kanban(root: Path, start: dt.date, end: dt.date, reuse: dict) -> dict:
    kb = root / "management" / "kanban"
    hist = reuse.get("history")
    frontmatter = hist.frontmatter if hist else _fm_fallback
    points = load_points(root)
    resolve = _team(root, reuse)
    epic_titles = _epic_titles(root)

    closed, in_progress, blocked = [], [], []
    done_total = done_no_date = 0
    n_files = 0
    files = sorted(kb.rglob("*.md")) if kb.is_dir() else []
    for f in files:
        if not TSK_FILE.search(f.name):
            continue
        fm = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not fm:
            continue
        n_files += 1
        status = (fm.get("status") or "").replace("-", "_")
        rel = f.relative_to(kb).parts
        epic = fm.get("epic") or (rel[0] if EPIC_IN_PATH.match(rel[0]) else "senza epica")
        tid = fm.get("id") or f.stem
        title = fm.get("title", "")
        size = (fm.get("estimate") or fm.get("size") or "").upper() or None
        pts = points.get(size) if size else None
        if status in CLOSED_STATUSES:
            done_total += 1
            when = None
            for name in CLOSED_FIELDS:
                when = utc_to_rome_date(fm.get(name, ""))
                if when:
                    break
            if when is None:
                done_no_date += 1
            elif in_week(when, start, end):
                raw_by = ""
                for name in DONE_BY_FIELDS:
                    if (fm.get(name) or "").strip():
                        raw_by = fm[name]
                        break
                people = [resolve(n) if resolve else n for n in _names(raw_by)]
                closed.append({"id": tid, "epica": epic, "titolo": title, "data": when.isoformat(),
                               "persone": people, "taglia": size, "punti": pts})
        elif status == "in_progress":
            in_progress.append({"id": tid, "epica": epic, "titolo": title, "owner": fm.get("owner", "")})
        elif status == "blocked":
            blocked.append({"id": tid, "epica": epic, "titolo": title, "owner": fm.get("owner", ""),
                            "blocked_by": fm.get("blocked_by", "")})

    closed.sort(key=lambda t: (t["data"], t["id"]))
    per_epic, per_person = {}, {}
    for t in closed:
        e = per_epic.setdefault(t["epica"], {"epica": t["epica"], "titolo": epic_titles.get(t["epica"], ""),
                                             "tsk": 0, "punti": 0})
        e["tsk"] += 1
        e["punti"] += t["punti"] or 0
        for p in (t["persone"] or ["senza done_by"]):
            q = per_person.setdefault(p, {"persona": p, "tsk": 0, "punti": 0})
            q["tsk"] += 1
            q["punti"] += t["punti"] or 0
    by_count = lambda d: sorted(d.values(), key=lambda x: (-x["tsk"], x["epica" if "epica" in x else "persona"]))
    key = lambda x: x["id"]
    return {
        "chiusi": {
            "totale": len(closed),
            "punti": sum(t["punti"] or 0 for t in closed),
            "senza_taglia": sum(1 for t in closed if t["punti"] is None),
            "senza_done_by": sum(1 for t in closed if not t["persone"]),
            "per_epica": by_count(per_epic),
            "per_persona": by_count(per_person),
            "elenco": closed,
            "fonte": "management/kanban/**/*TSK-*.md: status done/completed e data di chiusura (closed_at) nella settimana",
        },
        "stato_attuale": {
            "nota": "Fotografia dello stato dei TSK al momento della generazione, non alla data di fine settimana: "
                    "i TSK non conservano la storia degli stati.",
            "in_corso": sorted(in_progress, key=key),
            "bloccati": sorted(blocked, key=key),
            "fonte": "management/kanban/**/*TSK-*.md: campo status",
        },
        "qualita_dati": {
            "tsk_letti": n_files,
            "tsk_chiusi_totali": done_total,
            "tsk_chiusi_senza_data": done_no_date,
        },
    }


# ---------------------------------------------------------------------------
# Rilasci (wiki/log*.md)
# ---------------------------------------------------------------------------

RELEASE_RE = re.compile(
    r"^##\s+(\d{4}-\d{2}-\d{2})(?:[T ]~?(\d{2}:\d{2})(?::\d{2})?(Z)?)?\s*(?:\(.*?\)\s*)?"
    r"[—-]\s+(release|promozione)\s+(.+?)\s*$", re.I)
# Forma di wiki/log.md di questa factory: «## [2026-10-07] release | v2.44.0 — titolo»
RELEASE_RE_BRACKET = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+(release|promozione)\s*\|\s*(.+?)\s*$", re.I)


def _match_release(line: str):
    """(data, ora, z, tipo, resto) se la riga e' un'intestazione di rilascio, altrimenti None."""
    m = RELEASE_RE.match(line)
    if m:
        return m.groups()
    m = RELEASE_RE_BRACKET.match(line)
    if m:
        d, kind, rest = m.groups()
        return d, None, None, kind, rest
    return None


def _release_kind(what: str, kinds: Optional[list] = None) -> str:
    """Etichetta del rilascio dai prefissi di documentation.weekly_digest.release_kinds."""
    low = what.lower()
    for k in kinds or []:
        prefix = str(k.get("prefix", "")).lower() if isinstance(k, dict) else ""
        if prefix and low.startswith(prefix):
            return str(k.get("label") or "altro")
    return "altro"


def collect_releases(root: Path, start: dt.date, end: dt.date, kinds: Optional[list] = None) -> dict:
    items, seen = [], set()
    logs = sorted((root / "wiki").glob("log*.md")) if (root / "wiki").is_dir() else []
    for f in logs:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _match_release(line)
            if not m or line in seen:
                continue
            seen.add(line)
            date_s, time_s, z, _kind, rest = m
            day = dt.date.fromisoformat(date_s)
            if time_s and z:  # orario in UTC: la data locale puo' cambiare
                h, mi = map(int, time_s.split(":"))
                utc = dt.datetime.combine(day, dt.time(h, mi))
                loc = utc + dt.timedelta(hours=rome_offset(utc))
                day, time_s = loc.date(), loc.strftime("%H:%M")
            if not in_week(day, start, end):
                continue
            parts = [p.strip() for p in re.split(r"\s+—\s+", rest)]
            what, outcome = (parts[0], parts[-1]) if len(parts) > 1 else (rest, "")
            esito = "completato" if outcome.upper().startswith("DONE") else (
                "fallito" if outcome.upper().startswith("FAILED") else (
                    "da completare" if outcome.upper().startswith(("GATE", "PARTIAL")) else (outcome or "n.d.")))
            items.append({"data": day.isoformat(), "ora": time_s or "", "tipo": _release_kind(what, kinds),
                          "oggetto": what, "esito": esito, "dettaglio_esito": outcome, "fonte": f.name})
    items.sort(key=lambda r: (r["data"], r["ora"], r["oggetto"]))
    return {
        "totale": len(items),
        "completati": sum(1 for r in items if r["esito"] == "completato"),
        "elenco": items,
        "fonte": "wiki/log.md e wiki/log-*.md: intestazioni «release …» e «promozione …»",
    }


# ---------------------------------------------------------------------------
# Gap e incidenti
# ---------------------------------------------------------------------------

GAP_BULLET = re.compile(r"^\s*-\s*\[(?: |x|X|CLOSED|CONFIRMED OPEN)\]\s*\*{0,2}(G-[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])")
GAP_ID = re.compile(r"G-[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]")
RISOLTO = re.compile(r"\*\*(?:Risolto|Chiuso):\*\*\s*(\d{4}-\d{2}-\d{2})")
CLOSED_INLINE = re.compile(r"\[CLOSED\]\s*\*{0,2}(G-[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])\*{0,2}.*?(\d{4}-\d{2}-\d{2})\s*$")


def parse_gaps(text: str) -> tuple:
    """(aperti: {id: prima data}, chiusi: {id: prima data di chiusura})."""
    opened, closed = {}, {}
    section_date, current = None, None
    for line in text.splitlines():
        if line.startswith("## "):
            dates = ISO_DATE.findall(line)
            section_date = dates[0] if dates else None
            current = None
            continue
        m = GAP_BULLET.match(line)
        if m:
            current = m.group(1)
            if section_date and (current not in opened or section_date < opened[current]):
                opened[current] = section_date
        m2 = CLOSED_INLINE.search(line)
        if m2 and m2.group(1) not in closed:
            closed[m2.group(1)] = m2.group(2)
        m3 = RISOLTO.search(line)
        if m3:
            gid = current if line[:1] in (" ", "\t") else None
            if gid is None:
                ids = GAP_ID.findall(line)
                gid = ids[0] if ids else None
            if gid and (gid not in closed or m3.group(1) < closed[gid]):
                closed[gid] = m3.group(1)
    return opened, closed


def collect_gaps(root: Path, start: dt.date, end: dt.date) -> dict:
    f = root / "wiki" / "gaps.md"
    if not f.is_file():
        return {"disponibile": False, "motivo": "wiki/gaps.md assente"}
    opened, closed = parse_gaps(f.read_text(encoding="utf-8", errors="replace"))
    s, e = start.isoformat(), end.isoformat()
    reg = sorted(g for g, d in opened.items() if s <= d <= e)
    chi = sorted(g for g, d in closed.items() if s <= d <= e)
    ancora_aperti = [g for g in reg if g not in closed or closed[g] > e]
    return {
        "disponibile": True,
        "registrati": reg, "chiusi": chi,
        "registrati_e_chiusi_nella_settimana": [g for g in reg if g in chi],
        "ancora_aperti_fra_i_registrati": ancora_aperti,
        "fonte": "wiki/gaps.md: gap con identificativo G-… in una sezione datata della settimana; "
                 "chiusura = data di «Risolto» / «Chiuso» / «[CLOSED]»",
    }


def collect_incidents(root: Path, start: dt.date, end: dt.date) -> dict:
    d = root / "wiki" / "incidents"
    aperti, chiusi = [], []
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            fm = _fm_fallback(f.read_text(encoding="utf-8", errors="replace"))
            if fm.get("type") != "wiki-incident":
                continue
            opened = None
            for k in ("incident_date", "date_detected", "created"):
                if ISO_DATE.match(fm.get(k, "")):
                    opened = dt.date.fromisoformat(fm[k][:10])
                    break
            resolved = None
            if ISO_DATE.match(fm.get("date_resolved", "")):
                resolved = dt.date.fromisoformat(fm["date_resolved"][:10])
            rec = {"file": f.name, "stato": fm.get("status", ""), "data": opened.isoformat() if opened else ""}
            if in_week(opened, start, end):
                aperti.append(rec)
            if in_week(resolved, start, end):
                chiusi.append({**rec, "data": resolved.isoformat()})
    return {"aperti": aperti, "chiusi": chiusi,
            "fonte": "wiki/incidents/*.md: data dell'incidente (incident_date, altrimenti date_detected o created); "
                     "chiusura = date_resolved"}


# ---------------------------------------------------------------------------
# Costo token
# ---------------------------------------------------------------------------

def collect_cost(root: Path, start: dt.date, end: dt.date, reuse: dict) -> dict:
    fonte = "analytics/events/*.jsonl (event store) con i prezzi di analytics/pricing.yaml"
    mod = reuse.get("cost")
    if mod is None:
        return {"disponibile": False, "motivo": "cost_alert.py non importabile", "fonte": fonte}
    events_dir = root / "analytics" / "events"
    files = sorted(events_dir.glob("*.jsonl")) if events_dir.is_dir() else []
    if not files:
        return {"disponibile": False, "motivo": "event store assente (analytics/events/)", "fonte": fonte}
    pricer = mod.Pricer(root)
    total, tok = 0.0, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    by_model, days, n = {}, set(), 0
    seen = set()
    # Gli eventi «session-aggregate» sono istantanee CUMULATIVE della stessa sessione (stesso task_id,
    # hash diverso): per ogni sessione conta l'ultima istantanea della settimana meno l'ultima
    # precedente alla settimana (se esiste), contatore per contatore. Gli altri eventi sono singoli.
    snaps_in, snaps_before = {}, {}
    singles = []
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            day = utc_to_rome_date(ev.get("ts", ""))
            if day is None:
                continue
            key = ev.get("hash") or line
            if ev.get("task_type") == "session-aggregate":
                if day > end:
                    continue
                bucket = snaps_in if day >= start else snaps_before
                cur = bucket.get(ev.get("task_id"))
                if cur is None or str(ev.get("ts", "")) >= str(cur.get("ts", "")):
                    bucket[ev.get("task_id")] = ev
                if day >= start:
                    days.add(day.isoformat())
                    n += 1 if key not in seen else 0
                    seen.add(key)
            elif in_week(day, start, end) and key not in seen:
                seen.add(key)
                singles.append((day, ev))

    def vec(ev):
        t = ev.get("tokens") or {}
        return [int(t.get("input", 0)), int(t.get("output", 0)), int(t.get("cache_read", 0)),
                int(t.get("cache_write", 0)), int(t.get("cache_write_1h", 0))]

    def add(ev, vals):
        nonlocal total
        c = pricer.cost(ev.get("model", ""), tuple(vals))
        total += c
        m = ev.get("model", "?")
        by_model[m] = by_model.get(m, 0.0) + c
        for k, v in zip(("input", "output", "cache_read", "cache_write"), vals):
            tok[k] += v

    for tid, ev in snaps_in.items():
        cur = vec(ev)
        prev = vec(snaps_before[tid]) if tid in snaps_before else [0] * 5
        add(ev, [max(0, a - b) for a, b in zip(cur, prev)])
    for day, ev in singles:
        add(ev, vec(ev))
        days.add(day.isoformat())
        n += 1
    ndays = (end - start).days + 1
    if n == 0:
        return {"disponibile": False, "fonte": fonte,
                "motivo": "l'event store non contiene eventi nella settimana "
                          f"(file letti: {', '.join(f.name for f in files)})"}
    parziale = len(days) < ndays
    return {
        "disponibile": True, "usd": round(total, 2), "eventi": n, "sessioni": len(snaps_in), "token": tok,
        "giorni_con_eventi": sorted(days), "giorni_settimana": ndays,
        "parziale": parziale,
        "nota": (f"Copertura parziale: l'event store ha eventi in {len(days)} giorni su {ndays} "
                 f"({', '.join(sorted(days))}); il costo reale della settimana e' almeno questo."
                 if parziale else "L'event store ha eventi in tutti i giorni della settimana."),
        "per_modello": {k: round(v, 2) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
        "modelli_con_prezzo_di_ripiego": sorted(pricer.fallback_models),
        "fonte": fonte,
    }


# ---------------------------------------------------------------------------
# Deliverable
# ---------------------------------------------------------------------------

def collect_deliverables(root: Path, start: dt.date, end: dt.date, exclude_dir: str) -> dict:
    base = root / "deliverables"
    items = []
    skip = (root / exclude_dir).resolve() if exclude_dir else None

    def walk(d: Path, depth: int):
        for p in sorted(d.iterdir()):
            if skip is not None and p.resolve() == skip:
                continue
            m = ISO_DATE.search(p.name)
            if m:
                try:
                    day = dt.date.fromisoformat(m.group(0))
                except ValueError:
                    continue  # data non valida nel nome (2026-13-01, 0000-00-00): salta solo questo nome
                if in_week(day, start, end):
                    items.append({"nome": p.relative_to(base).as_posix() + ("/" if p.is_dir() else ""),
                                  "data": day.isoformat()})
            elif p.is_dir() and depth < 2:
                walk(p, depth + 1)
    if base.is_dir():
        try:
            walk(base, 0)
        except (OSError, ValueError):
            pass
    items.sort(key=lambda x: (x["data"], x["nome"]))
    return {"totale": len(items), "elenco": items,
            "fonte": "deliverables/: file e cartelle con la data della settimana nel nome "
                     "(cartelle datate contate una volta, senza entrare)"}


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

def load_doc_config(root: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    f = root / "factory.config.yaml"
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        doc = data.get("documentation") or {}
        cfg["output_dir"] = ((doc.get("weekly_digest") or {}).get("output_dir")) or cfg["output_dir"]
        kinds = (doc.get("weekly_digest") or {}).get("release_kinds")
        cfg["release_kinds"] = [k for k in kinds if isinstance(k, dict)] if isinstance(kinds, list) else []
        cfg["enabled"] = doc.get("enabled") is not False
        red = doc.get("redaction")
        cfg["redaction"] = not (isinstance(red, dict) and red.get("enabled") is False)
    except Exception:
        pass
    return cfg


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

def collect(week: str, root: Path) -> dict:
    """Dati del digest per la settimana ISO `week`. Deterministico: nessuna data corrente nel risultato."""
    root = Path(root).resolve()
    start, end = parse_week(week)
    notes: list = []
    reuse = _load_reuse(root / "tools" if (root / "tools" / "analytics").is_dir() else HERE.parent, notes)
    notes.extend(NOT_REUSED)
    notes.append(COST_RULE)
    kanban = collect_kanban(root, start, end, reuse)
    releases = collect_releases(root, start, end, load_doc_config(root)["release_kinds"])
    gaps = collect_gaps(root, start, end)
    incidents = collect_incidents(root, start, end)
    cost = collect_cost(root, start, end, reuse)
    out_dir = load_doc_config(root)["output_dir"]
    deliverables = collect_deliverables(root, start, end, out_dir)

    data = {
        "settimana": week, "dal": start.isoformat(), "al": end.isoformat(), "fuso": "Europe/Rome",
        "tsk_chiusi": kanban["chiusi"],
        "tsk_stato_attuale": kanban["stato_attuale"],
        "rilasci": releases,
        "gap": gaps,
        "incidenti": incidents,
        "costo_token": cost,
        "deliverable": deliverables,
        "qualita_dati": kanban["qualita_dati"],
        "riuso": notes,
        "commento": None,
    }
    data["sintesi"] = _summary(data)
    data["limiti"] = _limits(data)
    return data


def _summary(d: dict) -> list:
    c = d["tsk_chiusi"]
    s = [
        {"etichetta": "Attività chiuse (TSK)", "valore": str(c["totale"]),
         "fonte": "kanban, data di chiusura nella settimana"},
        {"etichetta": "Punti stimati chiusi", "valore": str(c["punti"]),
         "fonte": "taglia stimata delle attività, scala di analytics/velocity/config.json"},
        {"etichetta": "Persone con attività chiuse",
         "valore": str(sum(1 for p in c["per_persona"] if p["persona"] != "senza done_by")),
         "fonte": "kanban, campo done_by"},
        {"etichetta": "Rilasci completati", "valore": str(d["rilasci"]["completati"]),
         "fonte": "registro della wiki (wiki/log*.md)"},
    ]
    g = d["gap"]
    if g.get("disponibile"):
        s.append({"etichetta": "Lacune registrate / chiuse",
                  "valore": f"{len(g['registrati'])} / {len(g['chiusi'])}", "fonte": "wiki/gaps.md"})
    k = d["costo_token"]
    s.append({"etichetta": "Costo token (USD)",
              "valore": (f"{k['usd']:.2f}" + (" (parziale)" if k["parziale"] else "")) if k["disponibile"]
              else "non disponibile",
              "fonte": "event store analytics/events"})
    return s


def _limits(d: dict) -> list:
    q = d["qualita_dati"]
    lim = [
        "Le attività «chiuse» sono quelle con data di chiusura scritta nel TSK; "
        f"{q['tsk_chiusi_senza_data']} TSK chiusi su {q['tsk_chiusi_totali']} non hanno data e non sono "
        "attribuiti a nessuna settimana.",
        "Le attività in corso e bloccate sono lo stato al momento della generazione, non a fine settimana.",
        "Un'attività con più autori è contata per ciascuno nella tabella per persona, una sola volta nel totale.",
        "Le lacune (gap) sono riconosciute dalle sezioni datate di wiki/gaps.md: le sezioni senza data nel "
        "titolo non sono attribuite a una settimana.",
    ]
    k = d["costo_token"]
    if k.get("disponibile") and k.get("parziale"):
        lim.append(k["nota"])
    elif not k.get("disponibile"):
        lim.append("Costo token non disponibile: " + k.get("motivo", ""))
    return lim


# ---------------------------------------------------------------------------
# Rendering HTML
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#fff;--fg:#1c1f24;--mut:#5b6470;--line:#d9dde3;--acc:#0b5cab;--box:#f3f6fa;--warn:#fff4d6;--warnb:#d9a400}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e6e9ee;--mut:#9aa4b2;--line:#2c333d;--acc:#6db3f2;--box:#1c2128;--warn:#3a3112;--warnb:#b88a00}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 20px 60px}
h1{font-size:1.7rem;margin:.2em 0}h2{font-size:1.25rem;margin:2em 0 .5em;border-bottom:2px solid var(--line);padding-bottom:.2em}
.sub{color:var(--mut);margin:0 0 1.2em}.src{color:var(--mut);font-size:.78rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:1em 0}
.kpi{background:var(--box);border:1px solid var(--line);border-radius:8px;padding:12px}
.kpi b{display:block;font-size:1.7rem;color:var(--acc)}.kpi span{display:block;font-size:.9rem}
table{border-collapse:collapse;width:100%;margin:.5em 0;font-size:.92rem}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--box)}td.n,th.n{text-align:right;white-space:nowrap}
.comm{background:var(--warn);border-left:5px solid var(--warnb);padding:10px 14px;margin:1.2em 0;border-radius:4px}
.comm h3{margin:.1em 0 .4em;font-size:1rem}
.note{background:var(--box);border-radius:6px;padding:8px 12px;font-size:.9rem}
details{margin:.5em 0}summary{cursor:pointer;color:var(--acc)}
@media print{body{background:#fff;color:#000}details[open] summary{display:none}.kpi{break-inside:avoid}}
"""


def _e(x) -> str:
    return html.escape(str(x))


def _table(headers, rows, num_cols=()) -> str:
    th = "".join(f'<th class="n">{_e(h)}</th>' if i in num_cols else f"<th>{_e(h)}</th>"
                 for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(
        f'<td class="n">{_e(c)}</td>' if i in num_cols else f"<td>{_e(c)}</td>" for i, c in enumerate(r)) + "</tr>"
        for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _comment_html(text: str) -> str:
    out, bullets = [], []
    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_e(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        if all(l.lstrip().startswith(("- ", "* ")) for l in lines if l.strip()):
            bullets.extend(l.lstrip()[2:] for l in lines if l.strip())
            flush()
        else:
            out.append(f"<p>{_e(' '.join(l.strip() for l in lines))}</p>")
    return "".join(out)


def _src(text: str) -> str:
    return f'<p class="src">Fonte: {_e(text)}</p>'


def render_html(data: dict) -> str:
    d = data
    p = []
    p.append(f'<h1>Digest settimanale {_e(d["settimana"])}</h1>')
    gen = f" · generato il {_e(d['generato_il'])}" if d.get("generato_il") else ""
    p.append(f'<p class="sub">Dal {_e(d["dal"])} al {_e(d["al"])} (lunedì-domenica, fuso Europe/Rome){gen}. '
             "I numeri sono calcolati da script sui dati del progetto; non sono stime.</p>")
    p.append('<div class="kpis">' + "".join(
        f'<div class="kpi"><b>{_e(k["valore"])}</b><span>{_e(k["etichetta"])}</span>'
        f'<span class="src">{_e(k["fonte"])}</span></div>' for k in d["sintesi"]) + "</div>")
    if d.get("commento"):
        p.append('<div class="comm"><h3>Commento dell\'autore</h3>' + _comment_html(d["commento"]) + "</div>")

    c = d["tsk_chiusi"]
    p.append("<h2>Attività chiuse nella settimana</h2>")
    p.append(f'<p>{c["totale"]} attività chiuse, per {c["punti"]} punti stimati '
             f'(un punto misura la complessità stimata prima del lavoro: da 1 per le più piccole a 8 per le più grandi).'
             + (f' {c["senza_taglia"]} non hanno una taglia e valgono 0 punti.' if c["senza_taglia"] else "") + "</p>")
    if c["per_epica"]:
        p.append("<h3>Per iniziativa (epica)</h3>")
        p.append(_table(["Iniziativa", "Descrizione", "Attività", "Punti"],
                        [(e["epica"], e["titolo"], e["tsk"], e["punti"]) for e in c["per_epica"]], (2, 3)))
        p.append("<h3>Per persona</h3>")
        p.append(_table(["Persona", "Attività", "Punti"],
                        [(x["persona"], x["tsk"], x["punti"]) for x in c["per_persona"]], (1, 2)))
        if c["senza_done_by"]:
            p.append(f'<p class="note">{c["senza_done_by"]} attività chiuse non dichiarano chi le ha '
                     "svolte (campo done_by): sono nella riga «senza done_by» e non sono attribuite a nessuno.</p>")
        rows = [(t["id"], t["data"], t["epica"], ", ".join(t["persone"]) or "senza done_by", t["titolo"])
                for t in c["elenco"]]
        p.append(f'<details><summary>Elenco completo ({len(rows)})</summary>'
                 + _table(["Attività", "Chiusa il", "Iniziativa", "Chi", "Titolo"], rows) + "</details>")
    p.append(_src(c["fonte"]))

    s = d["tsk_stato_attuale"]
    p.append("<h2>Attività in corso e bloccate</h2>")
    p.append(f'<p class="note">{_e(s["nota"])}</p>')
    p.append(f'<p>In corso: {len(s["in_corso"])}. Bloccate: {len(s["bloccati"])}.</p>')
    if s["in_corso"]:
        p.append("<details><summary>In corso</summary>" + _table(
            ["Attività", "Iniziativa", "Responsabile", "Titolo"],
            [(t["id"], t["epica"], t["owner"], t["titolo"]) for t in s["in_corso"]]) + "</details>")
    if s["bloccati"]:
        p.append("<details open><summary>Bloccate</summary>" + _table(
            ["Attività", "Iniziativa", "Responsabile", "Titolo"],
            [(t["id"], t["epica"], t["owner"], t["titolo"]) for t in s["bloccati"]]) + "</details>")
    p.append(_src(s["fonte"]))

    r = d["rilasci"]
    p.append("<h2>Rilasci</h2>")
    if r["elenco"]:
        p.append(f'<p>{r["totale"]} rilasci registrati, {r["completati"]} completati.</p>')
        p.append(_table(["Data", "Ora", "Ambito", "Cosa", "Esito"],
                        [(x["data"], x["ora"], x["tipo"], x["oggetto"], x["esito"]) for x in r["elenco"]]))
    else:
        p.append("<p>Nessun rilascio registrato nella settimana.</p>")
    p.append(_src(r["fonte"]))

    g = d["gap"]
    p.append("<h2>Lacune di conoscenza (gap)</h2>")
    p.append("<p class=\"note\">Un gap è una lacuna o un difetto noto, registrato con un identificativo nel registro della wiki.</p>")
    if g.get("disponibile"):
        p.append(f'<p>Registrati nella settimana: {len(g["registrati"])}. Chiusi nella settimana: {len(g["chiusi"])}. '
                 f'Fra i registrati, ancora aperti: {len(g["ancora_aperti_fra_i_registrati"])}.</p>')
        for label, ids in (("Registrati", g["registrati"]), ("Chiusi", g["chiusi"])):
            if ids:
                p.append(f"<details><summary>{label} ({len(ids)})</summary><p>{_e(', '.join(ids))}</p></details>")
        p.append(_src(g["fonte"]))
    else:
        p.append(f'<p>Non disponibile: {_e(g.get("motivo", ""))}.</p>')

    i = d["incidenti"]
    p.append("<h2>Incidenti</h2>")
    if i["aperti"] or i["chiusi"]:
        p.append(_table(["Evento", "Incidente", "Data", "Stato"],
                        [("aperto", x["file"], x["data"], x["stato"]) for x in i["aperti"]]
                        + [("chiuso", x["file"], x["data"], x["stato"]) for x in i["chiusi"]]))
    else:
        p.append("<p>Nessun incidente aperto o chiuso nella settimana.</p>")
    p.append(_src(i["fonte"]))

    k = d["costo_token"]
    p.append("<h2>Costo token</h2>")
    if k["disponibile"]:
        p.append(f'<p>{k["usd"]:.2f} USD su {k["eventi"]} eventi registrati.</p>')
        if k["parziale"]:
            p.append(f'<p class="note">{_e(k["nota"])}</p>')
        p.append(_table(["Modello", "USD"], [(m, f"{v:.2f}") for m, v in k["per_modello"].items()], (1,)))
        if k["modelli_con_prezzo_di_ripiego"]:
            p.append(f'<p class="note">Prezzo di ripiego (modello non in listino): '
                     f'{_e(", ".join(k["modelli_con_prezzo_di_ripiego"]))}.</p>')
    else:
        p.append(f'<p>Non disponibile: {_e(k["motivo"])}.</p>')
    p.append(_src(k["fonte"]))

    dl = d["deliverable"]
    p.append("<h2>Documenti prodotti</h2>")
    if dl["elenco"]:
        p.append(f'<p>{dl["totale"]} documenti con la data della settimana nel nome.</p>')
        p.append(_table(["Data", "Documento"], [(x["data"], x["nome"]) for x in dl["elenco"]]))
    else:
        p.append("<p>Nessun documento datato nella settimana.</p>")
    p.append(_src(dl["fonte"]))

    p.append("<h2>Limiti dei dati</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in d["limiti"]) + "</ul>")
    p.append("<details><summary>Come sono calcolati i numeri</summary><ul>"
             + "".join(f"<li>{_e(x)}</li>" for x in d["riuso"]) + "</ul></details>")
    return ('<!DOCTYPE html>\n<html lang="it"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Digest settimanale {_e(d["settimana"])}</title><style>{CSS}</style></head>'
            f'<body><main>{"".join(p)}</main></body></html>\n')


# ---------------------------------------------------------------------------
# Rendering Word
# ---------------------------------------------------------------------------

def render_docx(data: dict, path) -> bool:
    """Scrive il Word. Ritorna False (con avviso su stderr) se python-docx non e' installato."""
    try:
        import docx  # type: ignore
    except ImportError:
        print("avviso: python-docx non installato, file Word non generato "
              "(pip install python-docx)", file=sys.stderr)
        return False
    d = data
    doc = docx.Document()
    doc.add_heading(f'Digest settimanale {d["settimana"]}', 0)
    doc.add_paragraph(f'Dal {d["dal"]} al {d["al"]} (lunedì-domenica, fuso Europe/Rome). '
                      "I numeri sono calcolati da script sui dati del progetto.")

    def table(headers, rows):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Grid Accent 1"
        for i, h in enumerate(headers):
            t.rows[0].cells[i].text = str(h)
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = str(v)

    table(["Indicatore", "Valore", "Fonte"], [(k["etichetta"], k["valore"], k["fonte"]) for k in d["sintesi"]])
    if d.get("commento"):
        doc.add_heading("Commento dell'autore", 1)
        for block in re.split(r"\n\s*\n", d["commento"].strip()):
            doc.add_paragraph(" ".join(l.strip() for l in block.splitlines()))
    c = d["tsk_chiusi"]
    doc.add_heading("Attività chiuse nella settimana", 1)
    doc.add_paragraph(f'{c["totale"]} attività chiuse, {c["punti"]} punti stimati. Fonte: {c["fonte"]}.')
    if c["per_epica"]:
        doc.add_heading("Per iniziativa", 2)
        table(["Iniziativa", "Descrizione", "Attività", "Punti"],
              [(e["epica"], e["titolo"], e["tsk"], e["punti"]) for e in c["per_epica"]])
        doc.add_heading("Per persona", 2)
        table(["Persona", "Attività", "Punti"], [(x["persona"], x["tsk"], x["punti"]) for x in c["per_persona"]])
    s = d["tsk_stato_attuale"]
    doc.add_heading("Attività in corso e bloccate", 1)
    doc.add_paragraph(s["nota"])
    doc.add_paragraph(f'In corso: {len(s["in_corso"])}. Bloccate: {len(s["bloccati"])}.')
    if s["bloccati"]:
        table(["Attività", "Iniziativa", "Responsabile", "Titolo"],
              [(t["id"], t["epica"], t["owner"], t["titolo"]) for t in s["bloccati"]])
    r = d["rilasci"]
    doc.add_heading("Rilasci", 1)
    if r["elenco"]:
        table(["Data", "Ora", "Ambito", "Cosa", "Esito"],
              [(x["data"], x["ora"], x["tipo"], x["oggetto"], x["esito"]) for x in r["elenco"]])
    else:
        doc.add_paragraph("Nessun rilascio registrato nella settimana.")
    g = d["gap"]
    doc.add_heading("Lacune di conoscenza (gap)", 1)
    if g.get("disponibile"):
        doc.add_paragraph(f'Registrati: {len(g["registrati"])}. Chiusi: {len(g["chiusi"])}. '
                          f'Fra i registrati, ancora aperti: {len(g["ancora_aperti_fra_i_registrati"])}.')
    else:
        doc.add_paragraph(f'Non disponibile: {g.get("motivo", "")}.')
    i = d["incidenti"]
    doc.add_heading("Incidenti", 1)
    if i["aperti"] or i["chiusi"]:
        table(["Evento", "Incidente", "Data", "Stato"],
              [("aperto", x["file"], x["data"], x["stato"]) for x in i["aperti"]]
              + [("chiuso", x["file"], x["data"], x["stato"]) for x in i["chiusi"]])
    else:
        doc.add_paragraph("Nessun incidente aperto o chiuso nella settimana.")
    k = d["costo_token"]
    doc.add_heading("Costo token", 1)
    if k["disponibile"]:
        doc.add_paragraph(f'{k["usd"]:.2f} USD su {k["eventi"]} eventi. ' + (k["nota"] if k["parziale"] else ""))
    else:
        doc.add_paragraph(f'Non disponibile: {k["motivo"]}.')
    dl = d["deliverable"]
    doc.add_heading("Documenti prodotti", 1)
    if dl["elenco"]:
        table(["Data", "Documento"], [(x["data"], x["nome"]) for x in dl["elenco"]])
    else:
        doc.add_paragraph("Nessun documento datato nella settimana.")
    doc.add_heading("Limiti dei dati", 1)
    for x in d["limiti"]:
        doc.add_paragraph(x, style="List Bullet")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _redact_module(root: Path):
    sys.path.insert(0, str(root / "tools" / "docs"))
    try:
        import redact  # type: ignore
        return redact
    except ImportError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Digest settimanale per il management.")
    ap.add_argument("--settimana", help="settimana ISO YYYY-Www (default: corrente)")
    ap.add_argument("--json", action="store_true", help="stampa i dati in JSON e non scrive file")
    ap.add_argument("--out", help="cartella di uscita (default: documentation.weekly_digest.output_dir)")
    ap.add_argument("--commento", help="file markdown con il commento dell'autore")
    ap.add_argument("--root", help="radice della factory (default: ricavata da __file__)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else ROOT
    cfg = load_doc_config(root)
    if not cfg["enabled"]:
        print("documentazione disattivata (documentation.enabled: false in factory.config.yaml): "
              "nessun file generato")
        return 0
    week = args.settimana or current_week()
    try:
        data = collect(week, root)
    except ValueError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 2
    if args.commento:
        cpath = Path(args.commento)
        if not cpath.is_file():
            print(f"errore: file di commento non trovato: {cpath}", file=sys.stderr)
            return 2
        data["commento"] = cpath.read_text(encoding="utf-8")
    data["generato_il"] = dt.date.today().isoformat()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if cfg["redaction"]:
        # il controllo gira sui dati sorgente (JSON dei dati + testo del commento) prima di qualsiasi
        # render: copre HTML e Word, e non e' alterato dall'escape dell'HTML
        redact = _redact_module(root)
        if redact is None:
            print("errore: tools/docs/redact.py non trovato: controllo dei segreti non eseguibile, "
                  "nessun file scritto", file=sys.stderr)
            return 3
        try:
            redact.assert_clean(json.dumps(data, ensure_ascii=False, indent=2), f"digest {week} (dati)")
            if data.get("commento"):
                redact.assert_clean(data["commento"], f"digest {week} (commento)")
        except redact.RedactionError as exc:
            print(f"errore: possibili segreti nel digest, nessun file scritto:\n{exc}", file=sys.stderr)
            return 3
    page = render_html(data)
    out_dir = Path(args.out) if args.out else root / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{week}.html"
    html_path.write_text(page, encoding="utf-8")
    print(f"scritto {html_path}")
    docx_path = out_dir / f"{week}.docx"
    if render_docx(data, docx_path):
        print(f"scritto {docx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
