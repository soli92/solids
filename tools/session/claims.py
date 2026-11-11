#!/usr/bin/env python3
"""
claims.py — lettura di `memory/active-sessions.yaml` (cooperative locking, EP-053).

Modulo PURO: nessuna scrittura su disco. Lo usano sia la CLI che scrive
(`tools/session/active_sessions.py`) sia i lettori che non devono poter scrivere
(`visual/collectors/sessions.py`). Stdlib soltanto: PyYAML non e' garantito.

Schema unico (US-316 / TSK-723) — lo schema EP-053 resta valido cosi' com'e':

    sessions:
      - uuid: <8 caratteri>     # obbligatorio — python3 tools/session/session_id.py --short
        agent: <nome>           # obbligatorio — per kind: session vale «session-start»
        domain: <dominio>       # obbligatorio — per kind: session vale «session»
        started_at: <ISO8601>   # obbligatorio
        ttl_min: 30             # obbligatorio
        kind: agent             # opzionale — agent (default) | session
        operator: <user.name>   # opzionale — git config user.name
        last_seen: <ISO8601>    # opzionale — se presente la scadenza parte da qui
        context: "<testo>"      # opzionale — intent della sessione

Scadenza: (last_seen se presente, altrimenti started_at) + ttl_min.

Formati letti per retrocompatibilita':
  - entry di sessione della derivata: {id, operator, opened_at, last_seen,
    ttl_minutes, claims: [{domain, operation}]} — `id`->uuid, `opened_at`->started_at,
    `ttl_minutes`->ttl_min, kind dedotto `session`;
  - `claimed_at` come alias di started_at (vecchi claim di wave).

Scrittura: le entry nuove prendono il formato gia' usato dal file (`dialetto`): in un registro
in forma di derivata si scrive in quella forma, con `kind: agent` esplicito per i claim di agente.

I claim sono ADVISORY: `conflicts()` produce avvisi, mai un blocco. Nessun lock,
nessun lease, nessun arbitro (coerenza con EP-064).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

DEFAULT_TTL = {"agent": 30, "session": 120}
CANONICAL_KEYS = ("uuid", "agent", "domain", "started_at", "ttl_min",
                  "kind", "operator", "last_seen", "context")
_ALIASES = {"id": "uuid", "opened_at": "started_at", "claimed_at": "started_at",
            "ttl_minutes": "ttl_min"}
_KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _scalar(raw: str):
    value = raw.strip()
    if value and value[0] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        return value[1:end] if end > 0 else value[1:]
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if value in ("", "~", "null"):
        return None
    if value == "[]":
        return []
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse(text: str) -> Tuple[List[str], List[dict]]:
    """Ritorna (righe di intestazione prima di `sessions:`, entry grezze).

    Le entry sono dict con le chiavi come scritte nel file; `claims` annidati
    diventano una lista di dict.
    """
    header: List[str] = []
    entries: List[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("sessions:"):
        header.append(lines[i])
        i += 1
    if i >= len(lines):
        return header, entries
    i += 1

    item_indent: Optional[int] = None
    current: Optional[dict] = None
    nested_key: Optional[str] = None
    nested_indent: Optional[int] = None
    nested_item: Optional[dict] = None

    for line in lines[i:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        is_item = stripped.startswith("- ") or stripped == "-"
        if indent == 0 and not is_item:
            break  # chiave di primo livello successiva a `sessions:` (un `- ` a colonna 0 e' un'entry)
        body = stripped[2:].strip() if is_item else stripped

        if is_item and (item_indent is None or indent == item_indent):
            item_indent = indent
            current = {}
            entries.append(current)
            nested_key = nested_indent = nested_item = None
            m = _KV.match(body)
            if m:
                current[m.group(1)] = _scalar(m.group(2))
            continue
        if current is None:
            continue

        if nested_key is not None:
            # lista annidata (`claims:`): item a indent >= quello delle chiavi dell'entry,
            # chiavi dell'item a indent maggiore del suo trattino
            if is_item and indent > (item_indent or 0):
                nested_indent = indent
                nested_item = {}
                current[nested_key].append(nested_item)
                m = _KV.match(body)
                if m:
                    nested_item[m.group(1)] = _scalar(m.group(2))
                continue
            if nested_indent is not None and indent > nested_indent and nested_item is not None:
                m = _KV.match(body)
                if m:
                    nested_item[m.group(1)] = _scalar(m.group(2))
                continue

        m = _KV.match(body)
        if not m:
            continue
        key, raw = m.group(1), m.group(2)
        if raw.strip() == "" and key == "claims":
            current[key] = []
            nested_key, nested_indent, nested_item = key, None, None
        else:
            current[key] = _scalar(raw)
            nested_key = nested_indent = nested_item = None
    return header, entries


# ---------------------------------------------------------------------------
# Normalizzazione e scadenza
# ---------------------------------------------------------------------------

def parse_ts(raw) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        when = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def fmt_ts(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(raw: dict) -> dict:
    """Entry nello schema unico. Le chiavi sconosciute restano; gli alias no."""
    entry: dict = {}
    for key, value in raw.items():
        canon = _ALIASES.get(key, key)
        if canon not in entry or entry[canon] in (None, ""):
            entry[canon] = value
    if not entry.get("kind"):
        legacy_session = "claims" in raw or "opened_at" in raw or (
            "operator" in raw and "agent" not in raw)
        entry["kind"] = "session" if legacy_session else "agent"
    if entry["kind"] == "session":
        entry.setdefault("agent", "session-start")
        entry.setdefault("domain", "session")
    ttl = entry.get("ttl_min")
    if not isinstance(ttl, int):
        try:
            ttl = int(str(ttl))
        except (TypeError, ValueError):
            ttl = DEFAULT_TTL.get(entry["kind"], 30)
    entry["ttl_min"] = ttl
    if entry.get("uuid") is not None:
        entry["uuid"] = str(entry["uuid"]).lower()
    return entry


def expires_at(entry: dict) -> Optional[datetime]:
    base = parse_ts(entry.get("last_seen")) or parse_ts(entry.get("started_at"))
    if base is None:
        return None
    return base + timedelta(minutes=int(entry.get("ttl_min") or 0))


def is_expired(entry: dict, now: Optional[datetime] = None) -> bool:
    """Scaduta = scadenza passata. Senza data leggibile: scaduta (dato storico,
    non una sessione viva — tenerla in vita per sempre e' peggio che rimuoverla)."""
    end = expires_at(entry)
    return True if end is None else end < (now or datetime.now(timezone.utc))


def split_live(entries: Iterable[dict], now: Optional[datetime] = None
               ) -> Tuple[List[dict], List[dict]]:
    live, expired = [], []
    for e in entries:
        (expired if is_expired(e, now) else live).append(e)
    return live, expired


def load_text(text: str) -> Tuple[List[str], List[dict]]:
    header, raw = parse(text)
    return header, [normalize(e) for e in raw]


def same_uuid(a, b) -> bool:
    if not a or not b:
        return False
    a, b = str(a).lower(), str(b).lower()
    return a == b or a[:8] == b[:8]


def domains_of(entry: dict) -> List[str]:
    out = [entry["domain"]] if entry.get("domain") else []
    for c in entry.get("claims") or []:
        if isinstance(c, dict) and c.get("domain"):
            out.append(str(c["domain"]))
    return out


def has_domain(entry: dict, domain: str) -> bool:
    """L'entry e' il claim di `domain`: nel campo `domain`, o come unico claim in `claims:` (forma
    della derivata). Un'entry con piu' claim non e' il claim di uno solo: non si rilascia per uno."""
    return entry.get("domain") == domain or domains_of(entry) == [domain]


def conflicts(entries: Iterable[dict], my_uuid: Optional[str], my_operator: Optional[str],
              domains: Iterable[str] = (), now: Optional[datetime] = None) -> List[dict]:
    """Avvisi, non blocchi. Entry vive di ALTRE sessioni che:
      - dichiarano uno dei `domains` richiesti, oppure
      - sono sessioni aperte (kind: session) di un operatore diverso.
    """
    wanted = {d for d in domains if d}
    out = []
    for e in entries:
        if is_expired(e, now) or same_uuid(e.get("uuid"), my_uuid):
            continue
        shared = sorted(wanted.intersection(domains_of(e)))
        other_op = (e.get("kind") == "session" and e.get("operator")
                    and my_operator and e.get("operator") != my_operator)
        if shared or other_op:
            out.append({"uuid": e.get("uuid"), "operator": e.get("operator"),
                        "agent": e.get("agent"), "kind": e.get("kind"),
                        "domains": shared or domains_of(e),
                        "reason": "stesso dominio" if shared else "altra sessione aperta"})
    return out


# ---------------------------------------------------------------------------
# Resa (testo): la scrittura vera la fa il chiamante
# ---------------------------------------------------------------------------

def _yaml_value(value) -> str:
    if isinstance(value, int):
        return str(value)
    text = "" if value is None else str(value)
    if text == "" or re.search(r"[:#\[\]{}&*!|>'\"%@`]", text) or text != text.strip():
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def render(header: List[str], entries: Iterable[dict]) -> str:
    """Testo del file nello schema unico. Gli alias legacy diventano chiavi canoniche."""
    entries = list(entries)
    lines = list(header)
    if not entries:
        lines.append("sessions: []")
        return "\n".join(lines) + "\n"
    lines.append("sessions:")
    for e in entries:
        keys = [k for k in CANONICAL_KEYS if e.get(k) not in (None, "")]
        if e.get("kind") == "agent" and "kind" in keys:
            keys.remove("kind")  # default: lo schema EP-053 resta identico
        keys += [k for k in e if k not in CANONICAL_KEYS and k != "claims"
                 and e.get(k) not in (None, "")]
        for n, key in enumerate(keys):
            prefix = "  - " if n == 0 else "    "
            lines.append(f"{prefix}{key}: {_yaml_value(e[key])}")
        if e.get("claims"):
            lines.append("    claims:")
            for c in e["claims"]:
                for n, (k, v) in enumerate(c.items()):
                    prefix = "      - " if n == 0 else "        "
                    lines.append(f"{prefix}{k}: {_yaml_value(v)}")
    return "\n".join(lines) + "\n"


def render_derivata(entries: Iterable[dict]) -> List[str]:
    """Righe di entry nella forma di sessione della derivata ({id, operator, opened_at, last_seen,
    ttl_minutes, context, claims: [{domain, operation}]}): in un registro scritto cosi' le entry
    nuove non devono introdurre un secondo formato. `kind: agent` resta esplicito, perche' la
    forma da sola si legge come sessione."""
    lines: List[str] = []
    for e in entries:
        campi = [("id", e.get("uuid")), ("operator", e.get("operator")),
                 ("opened_at", e.get("started_at")), ("last_seen", e.get("last_seen") or e.get("started_at")),
                 ("ttl_minutes", e.get("ttl_min")), ("context", e.get("context"))]
        if e.get("kind") == "agent":
            campi.append(("kind", "agent"))
        campi = [(k, v) for k, v in campi if v not in (None, "")]
        for n, (k, v) in enumerate(campi):
            lines.append(f"{'  - ' if n == 0 else '    '}{k}: "
                         + (str(v) if isinstance(v, int) else '"' + str(v).replace('"', '\\"') + '"'))
        if e.get("domain") and e.get("domain") != "session":
            lines += ["    claims:", f"      - domain: {_yaml_value(e['domain'])}",
                      f"        operation: {_yaml_value(e.get('agent') or '?')}"]
    return lines


def dialetto(lines: List[str]) -> str:
    """`derivata` se le entry del file usano `id:` e nessuna `uuid:`; altrimenti `canonico`."""
    start, spans = _entry_spans(lines)
    primi = [lines[a].strip()[2:].split(":")[0] for a, _ in spans]
    return "derivata" if primi and "id" in primi and "uuid" not in primi else "canonico"


# ---------------------------------------------------------------------------
# Scrittura chirurgica (EP-072): solo le entry toccate cambiano, il resto resta byte per byte
# ---------------------------------------------------------------------------

def _entry_spans(lines: List[str]) -> Tuple[int, List[Tuple[int, int]]]:
    """(indice della riga `sessions:`, [(inizio, fine) di ogni entry]).

    Un'entry va dal suo trattino alla riga prima del trattino successivo, di un commento a
    colonna 0, di una riga vuota o della fine del blocco. Commenti a colonna 0 e righe vuote
    fra le entry (lo storico delle rimozioni di una derivata) non appartengono a nessuna entry.
    """
    start = next((i for i, l in enumerate(lines) if l.startswith("sessions:")), -1)
    spans: List[Tuple[int, int]] = []
    if start < 0:
        return start, spans
    item_indent = None
    cur = None
    for i in range(start + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and indent == 0 and not stripped.startswith(("#", "- ")):
            break                                   # chiave top-level successiva
        boundary = (not stripped) or (indent == 0 and stripped.startswith("#"))
        is_item = stripped.startswith("- ") and (item_indent is None or indent == item_indent)
        if is_item:
            item_indent = indent
            if cur is not None:
                spans.append((cur, i))
            cur = i
        elif boundary and cur is not None:
            spans.append((cur, i))
            cur = None
    if cur is not None:
        end = len(lines)
        while end > cur + 1 and not lines[end - 1].strip():
            end -= 1
        spans.append((cur, end))
    return start, spans


def edit_text(text: str, drop=None, touch=None, add: Iterable[dict] = ()) -> str:
    """Applica al testo del registro le sole modifiche necessarie.

    drop(entry_normalizzata) -> True: l'entry viene tolta (solo le sue righe).
    touch: (predicato, ISO8601) -> `last_seen` dell'entry aggiornato o aggiunto, nient'altro.
    add: entry nuove, subito dopo `sessions:`, nel formato gia' usato dal file (`dialetto`).
    Commenti, righe vuote, entry altrui e loro formato restano come sono.
    """
    lines = text.splitlines()
    start, spans = _entry_spans(lines)
    if start < 0:
        header = lines
        return render(header, list(add))
    if lines[start].strip() == "sessions: []":
        lines[start] = "sessions:"
    out = list(lines)
    rimaste = len(spans)
    for a, b in reversed(spans):
        raw_text = "\n".join(["sessions:"] + lines[a:b])
        parsed = parse(raw_text)[1]
        entry = normalize(parsed[0]) if parsed else {}
        if drop and drop(entry):
            del out[a:b]
            rimaste -= 1
            continue
        if touch and touch[0](entry):
            block = out[a:b]
            idx = next((k for k, l in enumerate(block) if l.strip().startswith("last_seen:")), None)
            ind = " " * (len(block[0]) - len(block[0].lstrip()) + 2)
            new = f'{ind}last_seen: "{touch[1]}"'
            if idx is None:
                block.insert(1, new)
            else:
                block[idx] = new
            out[a:b] = block
    if not add:
        nuove = []
    elif dialetto(lines) == "derivata":
        nuove = render_derivata(add)
    else:
        nuove = render([], list(add)).splitlines()[1:]
    # i renderer rientrano il trattino di 2 spazi: con entry a colonna 0 (YAML valido anche
    # cosi') le nuove si allineano, una lista con due rientri diversi non parsa
    if spans and not lines[spans[0][0]].startswith(" "):
        nuove = [l[2:] if l.startswith("  ") else l for l in nuove]
    out[start + 1:start + 1] = nuove
    if not nuove and rimaste == 0:
        out[start] = "sessions: []"   # `sessions:` senza entry vale null, non una lista vuota
    return "\n".join(out) + "\n"
