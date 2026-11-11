#!/usr/bin/env python3
"""Accesso ai database PostgreSQL con le credenziali di un file .env locale (capability db_access, opt-in).

Sottocomandi (output JSON su stdout, diagnostica su stderr):

  targets [--env ENV]                       registro + stato credenziali, nessuna connessione
  locate  ENV TERMINE [--live]              dove sta un microservizio, uno schema o una tabella:
                                            mappa del registro e, con --live, cataloghi dei DB
  databases ENV                             database presenti sugli host dell'ambiente
  check   ENV TARGET                        utente, server, privilegi effettivi per schema
  tables  ENV TARGET [PATTERN] [--schema S] tabelle e viste con righe stimate e dimensione
  describe ENV TARGET NOME                  colonne, vincoli, indici (e definizione delle viste)
  query   ENV TARGET (--sql S | --file F) [--explain] [--accept-cost]
                                            lettura: solo SELECT/WITH/TABLE/VALUES, funzioni con
                                            effetti collaterali rifiutate, LIMIT dentro la query,
                                            transazione READ ONLY, sempre ROLLBACK
  write   ENV TARGET (--sql S | --file F) --dry-run
                                            esegue in transazione, conta le righe, ROLLBACK,
                                            registra il dry-run pendente e stampa il token
  write   ENV TARGET (--sql S | --file F) --commit --token T [--confirm-env ENV]
                                            riesegue lo stesso SQL, COMMIT solo se le righe
                                            toccate coincidono con il dry-run

Il percorso di scrittura e' SPENTO per default (`db_access.write.enabled: false`): `write` rifiuta con
`write_disabled` prima di leggere SQL o registro. Gli ambienti in `read_only_envs` (prod) sono in sola lettura
senza eccezioni, anche a scrittura accesa: `write` vi e' rifiutato prima di connettersi, dry-run compreso. Sul percorso di lettura una scrittura e' rifiutata dal tool
prima di connettersi e, se sfugge, dal server (SQLSTATE 25006) -> exit 3. Il gate umano fra dry-run e commit
lo gestisce chi invoca (skill db-access-protocol, gate umano obbligatorio): questo tool garantisce solo che il commit
riguardi esattamente l'SQL provato, entro il TTL, e che i dati non siano cambiati nel mezzo.

Timeout per ambiente: `statement_timeout_ms` e `lock_timeout_ms` valgono per tutti gli ambienti; `env_overrides`
li ristringe per ambiente (default prod 15000/3000). Il valore effettivo e' nell'output di `query` (`timeouts`).

Controllo di costo: sugli ambienti in `cost_gate.envs` (default prod) `query` esegue prima `EXPLAIN (FORMAT JSON)`
(mai ANALYZE) sulla stessa query con il LIMIT. Sopra `cost_gate.max_total_cost` o `cost_gate.max_plan_rows` la query
non parte: exit 4, errore `cost_gate`, costo e righe stimate. `--accept-cost` la fa partire (una sola esecuzione,
registrata nell'audit): si usa solo dopo il si' esplicito dell'utente, mai per default.

Exit code: 0 ok | 1 uso/config | 2 connessione/autenticazione | 3 scrittura su percorso di
lettura | 4 gate (token, TTL, conferma ambiente, righe divergenti) | 5 errore SQL | 6 timeout
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import decimal
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_CONNECT = 2
EXIT_READ_ONLY = 3
EXIT_GATE = 4
EXIT_SQL = 5
EXIT_TIMEOUT = 6

MAX_STDOUT_BYTES = 32 * 1024

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "env_file": ".env.db",
    "registry": "tools/db/db-targets.yaml",
    "protected_envs": ["prod"],
    "read_only_envs": ["prod"],         # nessuna scrittura, nemmeno il dry-run
    "default_limit": 200,
    "max_limit_protected": 500,
    "statement_timeout_ms": 30000,
    "lock_timeout_ms": 5000,
    # Ristringe i timeout globali per ambiente; gli ambienti non indicati ereditano il globale.
    "env_overrides": {"prod": {"statement_timeout_ms": 15000, "lock_timeout_ms": 3000}},
    # Stima di costo (EXPLAIN senza ANALYZE) prima di una lettura: sopra soglia serve la conferma dell'utente.
    "cost_gate": {"envs": ["prod"], "max_total_cost": 1000000, "max_plan_rows": 1000000},
    "connect_timeout_s": 10,
    "pending_ttl_minutes": 30,
    "state_dir": ".db-access-state",
    "audit_log": "deliverables/db-access/audit-scritture.jsonl",
    # verify-full: cifratura + verifica di catena e nome host. Valori piu' deboli (prefer, require, ...) solo se
    # dichiarati ESPLICITAMENTE (qui o con `sslmode:` sull'host del registro) e sempre con un avviso.
    "sslmode": "verify-full",
    # La scrittura e' una scelta esplicita: spenta per default.
    "write": {"enabled": False},
    "application_name": "db-access",
}

SSLMODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
STRONG_SSLMODES = ("verify-ca", "verify-full")
WEAK_SSL_ADVICE = ("sslmode '{mode}' non verifica il certificato del server (nessuna protezione da "
                   "intercettazione): usare verify-full dove possibile")

# Prima parola delle istruzioni che chiudono o aprono transazioni o cambiano la modalita'
# read-only: permetterebbero di uscire dalla transazione di lettura o di rendere permanente
# un dry-run. COPY e' escluso perche' puo' leggere/scrivere file e programmi lato server.
_BLOCKED_FIRST = {"BEGIN", "START", "COMMIT", "END", "ROLLBACK", "ABORT", "SAVEPOINT",
                  "RELEASE", "DISCARD", "RESET", "COPY"}
_BLOCKED_SET_MARKERS = ("TRANSACTION", "SESSION CHARACTERISTICS", "READ_ONLY")


_READ_START = {"SELECT", "WITH", "TABLE", "VALUES"}
_WRITE_WORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "CREATE", "DROP", "ALTER", "GRANT",
                "REVOKE", "COPY", "VACUUM", "REINDEX", "CLUSTER", "REFRESH", "CALL", "DO", "LOCK", "COMMENT",
                "SECURITY", "IMPORT"}
# Funzioni con effetti collaterali o che escono dalla transazione: dblink apre una connessione verso un altro
# DB, dove la sola lettura della sessione non vale. Sul percorso di scrittura nextval/setval restano ammesse.
_SIDE_EFFECT_CALLS = (
    r"dblink\w*|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_rotate_logfile\w*|pg_sleep\w*"
    r"|pg_advisory\w*|pg_try_advisory\w*|lo_\w+|pg_read_\w*file|pg_ls_\w+|pg_stat_file|pg_notify|set_config"
    r"|pg_switch_wal|pg_create_\w+|pg_drop_\w+|pg_logical_\w+|pg_replication_\w+|pg_promote|pg_wal_replay_\w+"
    r"|pg_import_system_collations|query_to_xml\w*|cursor_to_xml\w*")
_DENIED_CALL_WRITE_RE = re.compile(rf"\b({_SIDE_EFFECT_CALLS})\s*\(")
_DENIED_CALL_READ_RE = re.compile(rf"\b({_SIDE_EFFECT_CALLS}|txid_current\w*|pg_current_xact_id\w*|nextval|setval)\s*\(")
_DENIED_PACKAGE_RE = re.compile(r"\b(utl_\w+|dbms_\w+)\s*\.")       # pacchetti in stile Oracle di alcune distribuzioni compatibili: non esistono in PostgreSQL standard
# Anche dove PostgreSQL le rifiuterebbe comunque (CTE che scrivono, FOR UPDATE in sola lettura): fermarle prima
_DENIED_READ_KEYWORD_RE = re.compile(
    r"\b(insert|update|delete|merge|truncate|create|drop|alter|grant|revoke|copy|vacuum|reindex|cluster|refresh"
    r"|commit|rollback|savepoint|prepare|execute|deallocate|discard|listen|unlisten|notify|reset|import|lock)\b")


class ToolError(Exception):
    def __init__(self, code: int, error: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.payload = {"ok": False, "error": error, "message": message, **extra}


# ---------------------------------------------------------------------------
# .env e configurazione
# ---------------------------------------------------------------------------

def parse_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE senza interpretazione shell. Apici singoli o doppi esterni rimossi.

    Nessun taglio dei commenti in linea: le password possono contenere '#'.
    """
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_config(root: Path) -> dict[str, Any]:
    import yaml  # import pigro: il modulo resta leggero all'import

    cfg_path = root / "factory.config.yaml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    cfg = copy.deepcopy(DEFAULTS)
    user = data.get("db_access") or {}
    cfg.update(user)
    # Le chiavi a dizionario si fondono con i default (un override per un ambiente non cancella gli altri).
    overrides = copy.deepcopy(DEFAULTS["env_overrides"])
    for env, values in (user.get("env_overrides") or {}).items():
        overrides[env] = {**overrides.get(env, {}), **(values or {})}
    cfg["env_overrides"] = overrides
    cfg["cost_gate"] = {**DEFAULTS["cost_gate"], **(user.get("cost_gate") or {})}
    cfg["write"] = {**DEFAULTS["write"], **(user.get("write") or {})}
    return cfg


def write_enabled(cfg: dict[str, Any]) -> bool:
    return (cfg.get("write") or {}).get("enabled") is True


def effective_sslmode(cfg: dict[str, Any], host_def: dict[str, Any] | None = None) -> tuple[str, str | None]:
    """(sslmode, avviso). Il default e' verify-full; l'host del registro puo' dichiarare un valore proprio.
    Un valore sconosciuto e' un errore di configurazione; uno debole passa ma con avviso."""
    mode = str((host_def or {}).get("sslmode") or cfg.get("sslmode") or "verify-full").strip().lower()
    if mode not in SSLMODES:
        raise ToolError(EXIT_USAGE, "bad_sslmode", f"sslmode non valido: {mode!r}", allowed=list(SSLMODES))
    return mode, (None if mode in STRONG_SSLMODES else WEAK_SSL_ADVICE.format(mode=mode))


def effective_timeouts(cfg: dict[str, Any], env: str) -> dict[str, int]:
    """Timeout (ms) dell'ambiente: l'override dell'ambiente se c'e', altrimenti il valore globale."""
    override = (cfg.get("env_overrides") or {}).get(env) or {}
    out = {}
    for key in ("statement_timeout_ms", "lock_timeout_ms"):
        value = override.get(key)
        out[key] = int(cfg[key] if value is None else value)
    return out


def enrich_timeout(err: "ToolError", cfg: dict[str, Any], env: str | None) -> "ToolError":
    """Un timeout dice quale limite e' scattato (statement o lock) e per quale ambiente."""
    sqlstate = err.payload.get("sqlstate")
    if err.code != EXIT_TIMEOUT or sqlstate not in ("57014", "55P03") or not env or "timeout" in err.payload:
        return err
    limit = "lock_timeout" if sqlstate == "55P03" else "statement_timeout"
    limit_ms = effective_timeouts(cfg, env)[f"{limit}_ms"]
    err.payload["timeout"] = {"limit": limit, "limit_ms": limit_ms, "env": env}
    err.payload["message"] = f"{err.payload['message']} [{limit} di {limit_ms} ms superato, ambiente {env}]"
    return err


def load_registry(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    import yaml

    path = root / cfg["registry"]
    if not path.is_file():
        raise ToolError(EXIT_USAGE, "registry_missing", f"registro non trovato: {cfg['registry']}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("environments") or {}


def resolve_target(registry: dict[str, Any], env_values: dict[str, str], env: str,
                   target: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Endpoint e credenziali di (env, target). Mai i valori segreti nel dict 'public'."""
    if env not in registry:
        raise ToolError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {env}",
                        available=sorted(registry))
    env_def = registry[env]
    dbs = env_def.get("databases") or {}
    if target not in dbs:
        raise ToolError(EXIT_USAGE, "unknown_target", f"target '{target}' non definito per {env}",
                        available=sorted(dbs))
    db = dbs[target]
    host_def = (env_def.get("hosts") or {}).get(db["host"])
    if host_def is None:
        raise ToolError(EXIT_USAGE, "registry_invalid",
                        f"host '{db['host']}' del target {target} non definito in {env}")

    def pick(field: str) -> Any:
        var = host_def.get(f"{field}_var")
        if var and env_values.get(var):
            return env_values[var]
        return host_def.get(field, host_def.get(f"default_{field}"))

    host = pick("host")
    port = pick("port")
    dbname = db.get("dbname")
    if host_def.get("dbname_var") and env_values.get(host_def["dbname_var"]):
        dbname = env_values[host_def["dbname_var"]]

    cred_pairs = host_def.get("credentials") or []
    chosen: tuple[str, str] | None = None
    for user_var, pwd_var in cred_pairs:
        if env_values.get(user_var) and env_values.get(pwd_var):
            chosen = (user_var, pwd_var)
            break

    sslmode, ssl_warning = effective_sslmode(cfg or DEFAULTS, host_def)
    public = {
        "sslmode": sslmode,
        "ssl_warning": ssl_warning,
        "env": env,
        "env_label": env_def.get("label", env),
        "target": target,
        "host": host,
        "port": int(port) if port is not None else None,
        "dbname": dbname,
        "schemas": db.get("schemas") or [],
        "unverified_endpoint": bool(host_def.get("unverified")),
        "credential_candidates": [list(p) for p in cred_pairs],
        "credential_vars": list(chosen) if chosen else None,
        "credential_source": f"env-file:{chosen[0]}" if chosen else None,
        "read_only": None,                      # valorizzato da chi conosce la config (read_only_envs)
        "unverified_database": bool(db.get("unverified")),
    }
    secret = None
    if chosen:
        secret = {"user": env_values[chosen[0]], "password": env_values[chosen[1]]}
    return {"public": public, "secret": secret}


def load_services(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    import yaml

    path = root / cfg["registry"]
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.is_file() else {}
    return data.get("services") or {}


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

def split_sql(sql: str) -> list[dict[str, str]]:
    """Divide su ';' fuori da stringhe, identificatori quotati, dollar-quote e commenti.

    Ritorna [{"text": istruzione originale, "code": testo senza commenti}].
    """
    out: list[dict[str, str]] = []
    buf: list[str] = []
    code: list[str] = []
    i, n = 0, len(sql)

    def flush() -> None:
        text = "".join(buf).strip()
        c = " ".join("".join(code).split())
        if c:
            out.append({"text": text, "code": c})
        buf.clear()
        code.clear()

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            buf.append(sql[i:j])
            code.append(" ")
            i = j
            continue
        if ch == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if sql.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif sql.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            buf.append(sql[i:j])
            code.append(" ")
            i = j
            continue
        if ch in ("'", '"'):
            escapes = ch == "'" and i > 0 and sql[i - 1] in "eE" and (
                i < 2 or not (sql[i - 2].isalnum() or sql[i - 2] == "_"))
            j = i + 1
            while j < n:
                if escapes and sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            buf.append(sql[i:j])
            code.append(sql[i:j])
            i = j
            continue
        if ch == "$":
            k = i + 1
            while k < n and (sql[k].isalnum() or sql[k] == "_"):
                k += 1
            if k < n and sql[k] == "$" and not (k > i + 1 and sql[i + 1].isdigit()):
                tag = sql[i:k + 1]
                end = sql.find(tag, k + 1)
                j = n if end == -1 else end + len(tag)
                buf.append(sql[i:j])
                code.append(sql[i:j])
                i = j
                continue
        if ch == ";":
            flush()
            i += 1
            continue
        buf.append(ch)
        code.append(ch)
        i += 1
    flush()
    return out


def code_only(sql: str) -> str:
    """La query senza commenti ne' stringhe: resta il codice su cui cercare parole e funzioni vietate.

    Le stringhe ('...', E'...', $tag$...$tag$) diventano ''; gli identificatori tra virgolette doppie restano
    come parola (un "pg_sleep"(1) deve essere riconosciuto).
    """
    result, i, n = [], 0, len(sql)
    while i < n:
        char, pair = sql[i], sql[i:i + 2]
        if pair == "--":
            end = sql.find("\n", i)
            i = n if end < 0 else end
        elif pair == "/*":
            depth, i = 1, i + 2
            while i < n and depth:
                depth += {"/*": 1, "*/": -1}.get(sql[i:i + 2], 0)
                i += 2 if sql[i:i + 2] in ("/*", "*/") else 1
            if depth:
                raise ToolError(EXIT_USAGE, "bad_sql", "commento /* non chiuso")
            result.append(" ")
        elif char == "'":
            escapes = i > 0 and sql[i - 1] in "eE" and (i == 1 or not sql[i - 2].isalnum())
            i += 1
            while i < n:
                if escapes and sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == "'":
                    if sql[i + 1:i + 2] == "'":
                        i += 2
                        continue
                    break
                i += 1
            if i >= n:
                raise ToolError(EXIT_USAGE, "bad_sql", "stringa non chiusa")
            result.append("''")
            i += 1
        elif char == "$" and (match := re.match(r"\$([A-Za-z_]\w*)?\$", sql[i:])):
            delimiter = match.group(0)
            end = sql.find(delimiter, i + len(delimiter))
            if end < 0:
                raise ToolError(EXIT_USAGE, "bad_sql", "stringa $...$ non chiusa")
            result.append("''")
            i = end + len(delimiter)
        elif char == '"':
            end = sql.find('"', i + 1)
            while end >= 0 and sql[end + 1:end + 2] == '"':
                end = sql.find('"', end + 2)
            if end < 0:
                raise ToolError(EXIT_USAGE, "bad_sql", 'identificatore " non chiuso')
            result.append(re.sub(r"\W", "_", sql[i + 1:end]))
            i = end + 1
        else:
            result.append(char)
            i += 1
    return "".join(result)


def validate_read(statements: list[dict[str, str]], env: str, read_only_env: bool) -> None:
    """Solo letture: SELECT/WITH/TABLE/VALUES, senza parole di scrittura ne' funzioni con effetti collaterali."""
    hint = (f"{env} e' in sola lettura: una correzione si prepara come file .sql per chi ne ha titolo" if read_only_env
            else "istruzione di scrittura: usare `write --dry-run` e il gate di conferma")
    for idx, st in enumerate(statements, 1):
        code = code_only(st["text"])
        kw = first_keyword(code)
        if kw not in _READ_START:
            if kw in _WRITE_WORDS:
                raise ToolError(EXIT_READ_ONLY, "read_only_violation", f"istruzione {idx} ({kw}) non e' una lettura",
                                statement_index=idx, hint=hint)
            raise ToolError(EXIT_USAGE, "not_a_read",
                            f"istruzione {idx} ({kw}): sulla lettura sono ammesse solo SELECT, WITH, TABLE, VALUES",
                            statement_index=idx)
        lowered = code.lower()
        if found := _DENIED_READ_KEYWORD_RE.search(lowered):
            raise ToolError(EXIT_READ_ONLY, "read_only_violation",
                            f"istruzione {idx}: {found.group(1).upper()} non e' ammessa in lettura",
                            statement_index=idx, hint=hint)
        for pattern in (_DENIED_CALL_READ_RE, _DENIED_PACKAGE_RE):
            if found := pattern.search(lowered):
                raise ToolError(EXIT_USAGE, "denied_function",
                                f"istruzione {idx}: {found.group(1)} non e' ammessa (effetti collaterali)",
                                statement_index=idx)


def validate_write(statements: list[dict[str, str]]) -> None:
    for idx, st in enumerate(statements, 1):
        lowered = code_only(st["text"]).lower()
        for pattern in (_DENIED_CALL_WRITE_RE, _DENIED_PACKAGE_RE):
            if found := pattern.search(lowered):
                raise ToolError(EXIT_USAGE, "denied_function",
                                f"istruzione {idx}: {found.group(1)} non e' ammessa (effetti collaterali o fuori "
                                "dalla transazione)", statement_index=idx)


def wrap_read(text: str, limit: int) -> str:
    # A capo prima della parentesi: un commento -- in fondo alla query non deve commentare la chiusura.
    # Il LIMIT dentro la query ferma anche il lavoro del server, non solo le righe restituite.
    return f"SELECT * FROM (\n{text}\n) AS q LIMIT {int(limit) + 1}"


def first_keyword(code: str) -> str:
    stripped = code.lstrip("( \t\r\n")
    word = stripped.split(None, 1)[0] if stripped else ""
    return word.upper()


def check_statements(statements: list[dict[str, str]]) -> None:
    if not statements:
        raise ToolError(EXIT_USAGE, "empty_sql", "nessuna istruzione SQL da eseguire")
    for idx, st in enumerate(statements):
        kw = first_keyword(st["code"])
        upper = st["code"].upper()
        blocked = kw in _BLOCKED_FIRST
        if kw == "PREPARE" and " TRANSACTION " in f" {upper} ":
            blocked = True
        if kw == "SET" and any(m in upper for m in _BLOCKED_SET_MARKERS):
            blocked = True
        if blocked:
            raise ToolError(
                EXIT_USAGE, "blocked_statement",
                f"istruzione {idx + 1} ({kw}) non ammessa: il tool gestisce da se' la transazione "
                "e la modalita' read-only",
                statement_index=idx + 1)


def sql_token(env: str, target: str, schema: str, statements: list[dict[str, str]]) -> tuple[str, str]:
    normalized = ";\n".join(s["code"] for s in statements)
    digest = hashlib.sha256(f"{env}\n{target}\n{schema}\n{normalized}".encode("utf-8")).hexdigest()
    return digest[:16], digest


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (decimal.Decimal, uuid.UUID, dt.timedelta)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        return "\\x" + b[:64].hex() + ("..." if len(b) > 64 else "")
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return str(value)


# ---------------------------------------------------------------------------
# Connessione (sostituibile nei test)
# ---------------------------------------------------------------------------

def _connect(params: dict[str, Any]):  # pragma: no cover - sostituita nei test
    try:
        import psycopg
    except ImportError:
        try:
            import psycopg2
        except ImportError:
            raise ToolError(EXIT_USAGE, "driver_missing",
                            "nessun driver PostgreSQL: pip install 'psycopg[binary]' (o psycopg2)") from None
        return psycopg2.connect(**params)
    return psycopg.connect(**params)


def _sqlstate(exc: Exception) -> str | None:
    """psycopg 3 espone sqlstate, psycopg2 pgcode."""
    return getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)


def _error_class(exc: Exception) -> tuple[int, str]:
    sqlstate = _sqlstate(exc)
    if sqlstate == "25006":
        return EXIT_READ_ONLY, "read_only_violation"
    if sqlstate in ("57014", "55P03"):
        return EXIT_TIMEOUT, "timeout"
    if sqlstate and (sqlstate.startswith("28") or sqlstate.startswith("08")):
        return EXIT_CONNECT, "auth_or_connection"
    if sqlstate:
        return EXIT_SQL, "sql_error"
    name = type(exc).__name__
    if name in ("OperationalError", "ConnectionTimeout", "TimeoutError", "OSError"):
        return EXIT_CONNECT, "auth_or_connection"
    return EXIT_SQL, "sql_error"


def _scrub(text: str, secret: dict[str, str] | None) -> str:
    if secret and secret.get("password"):
        text = text.replace(secret["password"], "***")
    return text


def open_connection(cfg: dict[str, Any], resolved: dict[str, Any], schema: str | None,
                    read_only: bool):
    pub, secret = resolved["public"], resolved["secret"]
    if secret is None:
        raise ToolError(EXIT_USAGE, "credentials_missing",
                        f"credenziali assenti nel {cfg['env_file']} per {pub['env']}/{pub['target']}",
                        expected_vars=pub["credential_candidates"])
    timeouts = effective_timeouts(cfg, pub["env"])
    options = [f"-c statement_timeout={timeouts['statement_timeout_ms']}",
               f"-c lock_timeout={timeouts['lock_timeout_ms']}"]
    if read_only:
        options.append("-c default_transaction_read_only=on")
    search_path = schema or (pub["schemas"][0] if pub["schemas"] else None)
    if search_path:
        options.append(f"-c search_path={search_path}")
    params = {
        "host": pub["host"], "port": pub["port"], "dbname": pub["dbname"],
        "user": secret["user"], "password": secret["password"],
        "connect_timeout": int(cfg["connect_timeout_s"]),
        "application_name": cfg["application_name"],
        "sslmode": pub.get("sslmode") or cfg["sslmode"],
        "options": " ".join(options),
    }
    if pub.get("ssl_warning"):
        print(f"db_access: avviso: {pub['env']}/{pub['target']}: {pub['ssl_warning']}", file=sys.stderr)
    try:
        conn = _connect(params)
    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001 - classificato e riportato, non ignorato
        code, kind = _error_class(exc)
        raise ToolError(EXIT_CONNECT if code == EXIT_SQL else code, kind,
                        _scrub(str(exc).strip(), secret),
                        host=pub["host"], port=pub["port"], dbname=pub["dbname"]) from exc
    if read_only:
        try:
            conn.read_only = True               # psycopg 3
        except AttributeError:
            conn.set_session(readonly=True)     # psycopg2
    return conn


def run_statements(conn, statements: list[dict[str, str]], limit: int,
                   secret: dict[str, str] | None) -> list[dict[str, Any]]:
    results = []
    cur = conn.cursor()
    for idx, st in enumerate(statements):
        started = time.monotonic()
        try:
            cur.execute(st["text"])
        except Exception as exc:  # noqa: BLE001 - classificato e riportato
            code, kind = _error_class(exc)
            hint = None
            if code == EXIT_READ_ONLY:
                hint = "istruzione di scrittura: usare `write --dry-run` e il gate di conferma"
            raise ToolError(code, kind, _scrub(str(exc).strip(), secret),
                            statement_index=idx + 1, sqlstate=_sqlstate(exc),
                            hint=hint) from exc
        item: dict[str, Any] = {
            "index": idx + 1,
            "keyword": first_keyword(st["code"]),
            "status": getattr(cur, "statusmessage", None),
            "rowcount": cur.rowcount,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
        if cur.description:
            rows = cur.fetchmany(limit + 1)
            item["columns"] = [d[0] for d in cur.description]
            item["truncated"] = len(rows) > limit
            item["rows"] = [to_jsonable(list(r)) for r in rows[:limit]]
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def emit(payload: dict[str, Any], *, protected: bool, out_path: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(json.dumps({"ok": payload.get("ok", True), "output_file": str(out_path),
                          "summary": _summary(payload)}, ensure_ascii=False))
        return
    if len(text.encode("utf-8")) <= MAX_STDOUT_BYTES:
        print(text)
        return
    if protected:
        # ambiente protetto: i dati non vanno mai su file, si tagliano le righe in chat
        for res in payload.get("results", []):
            rows = res.get("rows")
            while rows and len(json.dumps(payload, ensure_ascii=False, default=str)
                               .encode("utf-8")) > MAX_STDOUT_BYTES:
                rows.pop()
                res["truncated"] = True
                res["truncated_for_size"] = True
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(tempfile.gettempdir()) / "db-access" / (
        f"{stamp}-{payload.get('target', {}).get('env', 'x')}-"
        f"{payload.get('target', {}).get('target', 'x')}.json")
    emit(payload, protected=False, out_path=path)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {"target": payload.get("target"),
            "results": [{k: r.get(k) for k in ("index", "keyword", "rowcount", "truncated")}
                        for r in payload.get("results", [])]}


# ---------------------------------------------------------------------------
# Sottocomandi
# ---------------------------------------------------------------------------

def _read_sql(args) -> str:
    if args.sql is not None:
        return args.sql
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    raise ToolError(EXIT_USAGE, "sql_missing", "serve --sql oppure --file")


def _env_values(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    path = root / cfg["env_file"]
    if not path.is_file():
        raise ToolError(EXIT_USAGE, "env_file_missing", f"file credenziali assente: {cfg['env_file']}")
    return parse_env_file(path)


def cmd_targets(root: Path, cfg: dict[str, Any], args) -> int:
    registry = load_registry(root, cfg)
    env_values = _env_values(root, cfg)
    rows = []
    for env in sorted(registry):
        if args.env and env != args.env:
            continue
        for target in sorted(registry[env].get("databases") or {}):
            pub = resolve_target(registry, env_values, env, target, cfg)["public"]
            pub["protected"] = env in cfg["protected_envs"]
            pub["read_only"] = env in cfg["read_only_envs"]
            pub["credentials_ready"] = pub["credential_source"] is not None
            rows.append(pub)
    print(json.dumps({"ok": True, "env_file": cfg["env_file"], "targets": rows}, ensure_ascii=False))
    return EXIT_OK


_CHECK_SQL = [
    ("identity", "select current_user, session_user, current_database(), "
                 "current_setting('server_version'), pg_is_in_recovery(), "
                 "current_setting('search_path')"),
    ("role", "select rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
             "from pg_roles where rolname = current_user"),
    ("member_of", "select b.rolname from pg_auth_members m "
                  "join pg_roles b on m.roleid = b.oid join pg_roles r on m.member = r.oid "
                  "where r.rolname = current_user order by 1"),
    ("schemas", "select n.nspname, has_schema_privilege(n.oid, 'USAGE'), "
                "has_schema_privilege(n.oid, 'CREATE'), count(c.oid), "
                "count(c.oid) filter (where has_table_privilege(c.oid, 'SELECT')), "
                "count(c.oid) filter (where has_table_privilege(c.oid, 'INSERT')), "
                "count(c.oid) filter (where has_table_privilege(c.oid, 'UPDATE')), "
                "count(c.oid) filter (where has_table_privilege(c.oid, 'DELETE')) "
                "from pg_namespace n left join pg_class c on c.relnamespace = n.oid "
                "and c.relkind in ('r', 'p', 'v', 'm', 'f') "
                "where n.nspname not like 'pg\\_%' and n.nspname <> 'information_schema' "
                "group by n.oid, n.nspname order by 1"),
]


def cmd_check(root: Path, cfg: dict[str, Any], args) -> int:
    resolved = resolve_target(load_registry(root, cfg), _env_values(root, cfg), args.env, args.target, cfg)
    conn = open_connection(cfg, resolved, args.schema, read_only=True)
    try:
        stmts = [{"text": sql, "code": sql} for _, sql in _CHECK_SQL]
        res = run_statements(conn, stmts, 1000, resolved["secret"])
    finally:
        conn.rollback()
        conn.close()
    ident = res[0]["rows"][0]
    role = res[1]["rows"][0] if res[1]["rows"] else [None] * 4
    schemas = [{"schema": r[0], "usage": r[1], "create": r[2], "relations": r[3],
                "select": r[4], "insert": r[5], "update": r[6], "delete": r[7]}
               for r in res[3]["rows"]]
    can_write = (not ident[4]) and any(s["insert"] or s["update"] or s["delete"] for s in schemas)
    print(json.dumps({
        "ok": True, "target": resolved["public"],
        "protected": args.env in cfg["protected_envs"],
        "identity": {"current_user": ident[0], "session_user": ident[1], "database": ident[2],
                     "server_version": ident[3], "in_recovery": ident[4], "search_path": ident[5]},
        "role": {"superuser": role[0], "createrole": role[1], "createdb": role[2],
                 "bypassrls": role[3], "member_of": [r[0] for r in res[2]["rows"]]},
        "schemas": schemas,
        "write_capable": can_write,
    }, ensure_ascii=False, default=str))
    return EXIT_OK


def _plan_estimate(value: Any) -> tuple[float, float]:
    """Costo totale e righe stimate dalla radice del piano di `EXPLAIN (FORMAT JSON)`."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if isinstance(value, str):
        value = json.loads(value)
    plan = value[0]["Plan"] if isinstance(value, list) else value["Plan"]
    return float(plan["Total Cost"]), float(plan["Plan Rows"])


def cost_gate_check(conn, statements: list[dict[str, str]], gate: dict[str, Any],
                    secret: dict[str, str] | None) -> list[dict[str, Any]]:
    """EXPLAIN (FORMAT JSON), senza ANALYZE, di ogni lettura gia' validata e incapsulata con il LIMIT.

    Non esegue mai la query. Un EXPLAIN che fallisce o non e' leggibile ferma tutto: il costo e' ignoto.
    """
    max_cost, max_rows = float(gate["max_total_cost"]), float(gate["max_plan_rows"])
    cur = conn.cursor()
    estimates = []
    for idx, st in enumerate(statements, 1):
        try:
            cur.execute(f"EXPLAIN (FORMAT JSON) {st['text']}")
            row = cur.fetchmany(1)
            total_cost, plan_rows = _plan_estimate(row[0][0])
        except Exception as exc:  # noqa: BLE001 - classificato e riportato: la query non parte
            code, kind = _error_class(exc)
            if isinstance(exc, (KeyError, IndexError, TypeError, ValueError)):
                code, kind = EXIT_SQL, "unreadable_plan"
            raise ToolError(code, "cost_gate_explain_failed",
                            "controllo di costo non riuscito: la query non e' stata eseguita ("
                            f"{kind}: {_scrub(str(exc).strip(), secret)})",
                            statement_index=idx, sqlstate=_sqlstate(exc)) from exc
        exceeded = [name for name, value, cap in (("max_total_cost", total_cost, max_cost),
                                                  ("max_plan_rows", plan_rows, max_rows)) if value > cap]
        estimates.append({"index": idx, "total_cost": total_cost, "plan_rows": plan_rows, "exceeded": exceeded})
    return estimates


def _cost_gate_audit(root: Path, cfg: dict[str, Any], args, resolved: dict[str, Any],
                     statements: list[dict[str, str]], estimates: list[dict[str, Any]],
                     gate: dict[str, Any]) -> None:
    """Registra la conferma del costo (solo hash dell'SQL: l'ambiente e' protetto, niente testo ne' segreti)."""
    _, digest = sql_token(args.env, args.target, args.schema or "", statements)
    pub = resolved["public"]
    entry = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(), "event": "cost_gate_accepted",
        "env": args.env, "target": args.target, "host": pub["host"], "dbname": pub["dbname"],
        "db_user_source": pub["credential_source"],
        "operator": os.environ.get("USER") or os.environ.get("USERNAME"), "sql_sha256": digest,
        "estimates": estimates, "max_total_cost": gate["max_total_cost"], "max_plan_rows": gate["max_plan_rows"],
    }
    audit = root / cfg["audit_log"]
    try:
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        # senza traccia della conferma la lettura su un ambiente protetto non parte
        raise ToolError(EXIT_GATE, "audit_unwritable",
                        f"conferma del costo non registrabile nell'audit, query non eseguita: {exc}") from exc


def cmd_query(root: Path, cfg: dict[str, Any], args) -> int:
    protected = args.env in cfg["protected_envs"]
    if protected and args.out:
        raise ToolError(EXIT_USAGE, "out_forbidden",
                        f"{args.env} e' protetto: i risultati non si salvano su file")
    limit = args.limit or cfg["default_limit"]
    if protected:
        limit = min(limit, int(cfg["max_limit_protected"]))
    statements = split_sql(_read_sql(args))
    check_statements(statements)
    validate_read(statements, args.env, args.env in cfg["read_only_envs"])
    wrapped = [{"text": wrap_read(st["text"], limit), "code": st["code"]} for st in statements]
    if args.explain:
        wrapped = [{"text": f"EXPLAIN {st['text']}", "code": st["code"]} for st in wrapped]
    resolved = resolve_target(load_registry(root, cfg), _env_values(root, cfg), args.env, args.target, cfg)
    gate = cfg["cost_gate"]
    gated = not args.explain and args.env in (gate.get("envs") or [])
    conn = open_connection(cfg, resolved, args.schema, read_only=True)
    gate_info: dict[str, Any] | None = None
    try:
        if gated:
            estimates = cost_gate_check(conn, wrapped, gate, resolved["secret"])
            over = [e for e in estimates if e["exceeded"]]
            gate_info = {"status": "passed", "estimates": estimates, "max_total_cost": gate["max_total_cost"],
                         "max_plan_rows": gate["max_plan_rows"]}
            if over and not args.accept_cost:
                worst = over[0]
                raise ToolError(
                    EXIT_GATE, "cost_gate",
                    f"stima oltre soglia (costo {worst['total_cost']:g}, righe {worst['plan_rows']:g}; soglie "
                    f"{gate['max_total_cost']}/{gate['max_plan_rows']}): la query non e' stata eseguita. "
                    "Chiedere conferma esplicita all'utente e, solo dopo il suo si', rilanciare con --accept-cost",
                    total_cost=worst["total_cost"], plan_rows=worst["plan_rows"], exceeded=worst["exceeded"],
                    estimates=estimates, max_total_cost=gate["max_total_cost"],
                    max_plan_rows=gate["max_plan_rows"], confirm_with="--accept-cost")
            if over:
                _cost_gate_audit(root, cfg, args, resolved, wrapped, estimates, gate)
                gate_info["status"] = "accepted"
        results = run_statements(conn, wrapped, 10000 if args.explain else limit, resolved["secret"])
    finally:
        conn.rollback()  # la lettura non conferma mai nulla
        conn.close()
    payload = {"ok": True, "mode": "explain" if args.explain else "read", "target": resolved["public"],
               "protected": protected, "limit": limit, "timeouts": effective_timeouts(cfg, args.env),
               "results": results}
    if gate_info is not None:
        payload["cost_gate"] = gate_info
    emit(payload, protected=protected, out_path=Path(args.out) if args.out else None)
    return EXIT_OK


def _catalog(conn, sql: str, params: tuple, secret: dict[str, str] | None) -> list[tuple]:
    """Interrogazione dei cataloghi con parametri (mai valori dell'utente concatenati nell'SQL)."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001 - classificato e riportato
        code, kind = _error_class(exc)
        raise ToolError(code, kind, _scrub(str(exc).strip(), secret), sqlstate=_sqlstate(exc)) from exc
    return [tuple(to_jsonable(list(r))) for r in cur.fetchmany(5000)]


_TABLES_SQL = (
    "select n.nspname, c.relname, case c.relkind when 'r' then 'tabella' when 'p' then 'tabella' "
    "when 'v' then 'vista' when 'm' then 'vista mat.' when 'f' then 'esterna' end, "
    "greatest(c.reltuples, 0)::bigint, pg_size_pretty(pg_total_relation_size(c.oid)), "
    "coalesce(obj_description(c.oid, 'pg_class'), '') "
    "from pg_class c join pg_namespace n on n.oid = c.relnamespace "
    "where c.relkind in ('r', 'p', 'v', 'm', 'f') and n.nspname not like 'pg\\_%%' "
    "and n.nspname <> 'information_schema' and c.relname ilike %s and (%s = '' or n.nspname = %s) "
    "order by n.nspname, c.relname")


def _read_conn(root: Path, cfg: dict[str, Any], env: str, target: str, schema: str | None = None):
    resolved = resolve_target(load_registry(root, cfg), _env_values(root, cfg), env, target, cfg)
    return resolved, open_connection(cfg, resolved, schema, read_only=True)


def cmd_tables(root: Path, cfg: dict[str, Any], args) -> int:
    resolved, conn = _read_conn(root, cfg, args.env, args.target)
    try:
        rows = _catalog(conn, _TABLES_SQL, (f"%{args.pattern or ''}%", args.schema or "", args.schema or ""),
                        resolved["secret"])
    finally:
        conn.rollback()
        conn.close()
    emit({"ok": True, "target": resolved["public"], "pattern": args.pattern, "count": len(rows),
          "columns": ["schema", "name", "kind", "estimated_rows", "size", "comment"], "rows": rows},
         protected=args.env in cfg["protected_envs"], out_path=None)
    return EXIT_OK


def cmd_describe(root: Path, cfg: dict[str, Any], args) -> int:
    schema, _, name = args.name.rpartition(".")
    resolved, conn = _read_conn(root, cfg, args.env, args.target)
    secret = resolved["secret"]
    try:
        found = _catalog(conn, "select c.oid::bigint, n.nspname, c.relkind from pg_class c join pg_namespace n "
                               "on n.oid = c.relnamespace where c.relname = %s and (%s = '' or n.nspname = %s) "
                               "and c.relkind in ('r', 'p', 'v', 'm', 'f')", (name, schema, schema), secret)
        if not found:
            raise ToolError(EXIT_USAGE, "not_found", f"oggetto non trovato: {args.name}",
                            hint="`tables <env> <target> <parte del nome>` per cercarlo")
        objects = []
        for oid, nsp, kind in found:
            columns = _catalog(conn, "select a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, "
                                     "coalesce(pg_get_expr(d.adbin, d.adrelid), ''), "
                                     "coalesce(col_description(a.attrelid, a.attnum), '') "
                                     "from pg_attribute a left join pg_attrdef d on d.adrelid = a.attrelid "
                                     "and d.adnum = a.attnum where a.attrelid = %s and a.attnum > 0 "
                                     "and not a.attisdropped order by a.attnum", (oid,), secret)
            constraints = _catalog(conn, "select conname, pg_get_constraintdef(oid) from pg_constraint "
                                         "where conrelid = %s order by contype, conname", (oid,), secret)
            indexes = _catalog(conn, "select indexrelid::regclass::text, pg_get_indexdef(indexrelid) "
                                     "from pg_index where indrelid = %s", (oid,), secret)
            item = {"schema": nsp, "name": name, "kind": "vista" if kind in ("v", "m") else "tabella",
                    "columns": [{"name": c[0], "type": c[1], "not_null": c[2], "default": c[3] or None,
                                 "comment": c[4] or None} for c in columns],
                    "constraints": [{"name": c[0], "definition": c[1]} for c in constraints],
                    "indexes": [{"name": i[0], "definition": i[1].split(" USING ", 1)[-1]} for i in indexes]}
            if kind in ("v", "m"):
                view = _catalog(conn, "select pg_get_viewdef(%s, true)", (oid,), secret)
                item["definition"] = " ".join(str(view[0][0]).split())
            objects.append(item)
    finally:
        conn.rollback()
        conn.close()
    emit({"ok": True, "target": resolved["public"], "objects": objects},
         protected=args.env in cfg["protected_envs"], out_path=None)
    return EXIT_OK


def cmd_databases(root: Path, cfg: dict[str, Any], args) -> int:
    """Database realmente presenti sugli host dell'ambiente, con quelli del registro marcati."""
    registry = load_registry(root, cfg)
    if args.env not in registry:
        raise ToolError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {args.env}", available=sorted(registry))
    databases = registry[args.env].get("databases") or {}
    by_host: dict[str, list[str]] = {}
    for name, db in databases.items():
        by_host.setdefault(db["host"], []).append(name)
    env_values = _env_values(root, cfg)
    hosts, errors = [], []
    for host_id, targets in sorted(by_host.items()):
        resolved = resolve_target(registry, env_values, args.env, targets[0], cfg)
        try:
            conn = open_connection(cfg, resolved, None, read_only=True)
        except ToolError as err:
            errors.append({"host": host_id, **err.payload})
            continue
        try:
            names = [r[0] for r in _catalog(conn, "select datname from pg_database where not datistemplate "
                                                  "order by 1", (), resolved["secret"])]
        finally:
            conn.rollback()
            conn.close()
        registered = {databases[t]["dbname"]: t for t in targets}
        hosts.append({"host": host_id, "address": resolved["public"]["host"], "port": resolved["public"]["port"],
                      "databases": [{"dbname": n, "target": registered.get(n)} for n in names],
                      "registered_missing": sorted(d for d in registered if d not in names)})
    emit({"ok": not errors, "env": args.env, "hosts": hosts, "errors": errors},
         protected=args.env in cfg["protected_envs"], out_path=None)
    return EXIT_CONNECT if errors else EXIT_OK


def cmd_locate(root: Path, cfg: dict[str, Any], args) -> int:
    """Da microservizio, schema, tabella o parola: il target giusto. Prima la mappa del registro, poi
    (--live) i cataloghi dei DB dell'ambiente."""
    registry = load_registry(root, cfg)
    if args.env not in registry:
        raise ToolError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {args.env}", available=sorted(registry))
    term = args.term.lower()
    databases = registry[args.env].get("databases") or {}
    matches = []
    for service, entry in sorted(load_services(root, cfg).items()):
        names = [service, *(entry.get("aliases") or [])]
        if any(term in n.lower() for n in names):
            for use in entry.get("uses") or []:
                matches.append({"via": "servizio", "service": service, "target": use["target"],
                                "schemas": use.get("schemas") or [], "in_env": use["target"] in databases,
                                "source": entry.get("source"), "unverified": bool(entry.get("unverified"))})
    for target, db in sorted(databases.items()):
        words = [target, str(db.get("dbname", "")), *(db.get("aliases") or [])]
        if any(term in w.lower() for w in words):
            matches.append({"via": "database", "target": target, "schemas": db.get("schemas") or [],
                            "unverified": bool(db.get("unverified"))})
        for schema in db.get("schemas") or []:
            if term in schema.lower():
                matches.append({"via": "schema", "target": target, "schemas": [schema]})
    payload: dict[str, Any] = {"ok": True, "env": args.env, "term": args.term, "matches": matches}
    code = EXIT_OK
    if args.live:
        env_values = _env_values(root, cfg)
        live, errors, skipped = [], [], []
        for target in sorted(databases):
            resolved = resolve_target(registry, env_values, args.env, target, cfg)
            if resolved["secret"] is None:
                skipped.append(target)
                continue
            try:
                conn = open_connection(cfg, resolved, None, read_only=True)
            except ToolError as err:
                errors.append({"target": target, **err.payload})
                continue
            try:
                rows = _catalog(conn, "select n.nspname, coalesce(c.relname, ''), "
                                      "case when c.relname is null then 'schema' else 'tabella/vista' end "
                                      "from pg_namespace n left join pg_class c on c.relnamespace = n.oid "
                                      "and c.relkind in ('r', 'p', 'v', 'm', 'f') and c.relname ilike %s "
                                      "where n.nspname not like 'pg\\_%%' and n.nspname <> 'information_schema' "
                                      "and (c.relname is not null or n.nspname ilike %s) order by 1, 2 limit 30",
                                (f"%{args.term}%", f"%{args.term}%"), resolved["secret"])
            finally:
                conn.rollback()
                conn.close()
            if rows:
                live.append({"target": target, "dbname": resolved["public"]["dbname"],
                             "objects": [{"schema": r[0], "name": r[1] or None, "kind": r[2]} for r in rows]})
        payload.update({"live": live, "skipped_no_credentials": skipped, "errors": errors,
                        "complete": not errors and not skipped})
        if errors:
            payload["ok"] = False
            code = EXIT_CONNECT
        elif skipped:
            code = EXIT_USAGE                    # risultato incompleto: alcuni DB non interrogati
    emit(payload, protected=args.env in cfg["protected_envs"], out_path=None)
    return code


def _pending_path(root: Path, cfg: dict[str, Any], token: str) -> Path:
    return root / cfg["state_dir"] / "pending" / f"{token}.json"


def cmd_write(root: Path, cfg: dict[str, Any], args) -> int:
    if not write_enabled(cfg):
        raise ToolError(EXIT_GATE, "write_disabled",
                        "la scrittura e' spenta: db_access.write.enabled e' false (default). Accenderla e' una "
                        "scelta esplicita del maintainer; anche accesa, --commit richiede token e gate umano",
                        hint="per una correzione preparare un file .sql da far eseguire a chi ne ha titolo")
    if args.env in cfg["read_only_envs"]:
        raise ToolError(EXIT_GATE, "read_only_env",
                        f"{args.env} e' in sola lettura: nessuna scrittura, nemmeno il dry-run",
                        hint="per una correzione in questo ambiente preparare un file .sql per chi ha titolo "
                             "di eseguirlo (DBA), in deliverables/")
    if args.dry_run == args.commit:
        raise ToolError(EXIT_USAGE, "mode_missing", "serve esattamente uno fra --dry-run e --commit")
    protected = args.env in cfg["protected_envs"]
    statements = split_sql(_read_sql(args))
    check_statements(statements)
    validate_write(statements)
    schema = args.schema or ""
    token, digest = sql_token(args.env, args.target, schema, statements)

    pending_file = _pending_path(root, cfg, token)
    pending = None
    if args.commit:
        if args.token != token:
            raise ToolError(EXIT_GATE, "token_mismatch",
                            "il token non corrisponde a questo SQL su questo target: rifare il dry-run")
        if not pending_file.is_file():
            raise ToolError(EXIT_GATE, "no_pending_dry_run",
                            "nessun dry-run pendente per questo token (gia' eseguito o mai provato)")
        pending = json.loads(pending_file.read_text(encoding="utf-8"))
        created = dt.datetime.fromisoformat(pending["created_at"])
        age_min = (dt.datetime.now(dt.timezone.utc) - created).total_seconds() / 60
        if age_min > float(cfg["pending_ttl_minutes"]):
            raise ToolError(EXIT_GATE, "dry_run_expired",
                            f"dry-run di {age_min:.0f} minuti fa, oltre il TTL di "
                            f"{cfg['pending_ttl_minutes']}: rifare il dry-run e il gate")
        if protected and args.confirm_env != args.env:
            raise ToolError(EXIT_GATE, "confirm_env_required",
                            f"{args.env} e' protetto: serve --confirm-env {args.env}")

    resolved = resolve_target(load_registry(root, cfg), _env_values(root, cfg), args.env, args.target, cfg)
    conn = open_connection(cfg, resolved, args.schema, read_only=False)
    committed = False
    try:
        results = run_statements(conn, statements, 20, resolved["secret"])
        counts = [r["rowcount"] for r in results]
        if args.dry_run:
            conn.rollback()
        else:
            expected = pending["rowcounts"]
            if counts != expected:
                conn.rollback()
                raise ToolError(EXIT_GATE, "rowcount_drift",
                                "le righe toccate differiscono dal dry-run: annullato, "
                                "rifare dry-run e gate", dry_run_rowcounts=expected,
                                actual_rowcounts=counts)
            conn.commit()
            committed = True
    finally:
        if not committed:
            conn.rollback()
        conn.close()

    pub = resolved["public"]
    now = dt.datetime.now(dt.timezone.utc)
    if args.dry_run:
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        pending_file.write_text(json.dumps({
            "token": token, "sql_sha256": digest, "env": args.env, "target": args.target,
            "schema": schema, "rowcounts": counts, "created_at": now.isoformat(),
        }), encoding="utf-8")
        emit({"ok": True, "mode": "dry_run", "rolled_back": True, "target": pub,
              "protected": protected, "token": token,
              "expires_at": (now + dt.timedelta(minutes=float(cfg["pending_ttl_minutes"]))).isoformat(),
              "statements": len(statements), "results": results,
              "commit_requires": {"token": token,
                                  "confirm_env": args.env if protected else None}},
             protected=protected, out_path=None)
        return EXIT_OK

    pending_file.unlink()
    audit = root / cfg["audit_log"]
    audit.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now.isoformat(), "env": args.env, "target": args.target, "host": pub["host"],
        "dbname": pub["dbname"], "schema": schema or (pub["schemas"][0] if pub["schemas"] else None),
        "db_user_source": pub["credential_source"], "operator": os.environ.get("USER")
        or os.environ.get("USERNAME"), "sql_sha256": digest,
        "statements": [{"keyword": r["keyword"], "rowcount": r["rowcount"]} for r in results],
    }
    if not protected:
        entry["sql"] = ";\n".join(s["text"] for s in statements)
    with audit.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    emit({"ok": True, "mode": "commit", "committed": True, "target": pub, "protected": protected,
          "results": results, "audit_log": cfg["audit_log"]}, protected=protected, out_path=None)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                   help="root della factory (default: dedotta dal path dello script)")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("targets")
    t.add_argument("--env")

    def common(sp, with_sql: bool) -> None:
        sp.add_argument("env")
        sp.add_argument("target")
        sp.add_argument("--schema")
        if with_sql:
            g = sp.add_mutually_exclusive_group(required=True)
            g.add_argument("--sql")
            g.add_argument("--file")

    c = sub.add_parser("check")
    common(c, False)
    q = sub.add_parser("query")
    common(q, True)
    q.add_argument("--limit", type=int)
    q.add_argument("--out")
    q.add_argument("--explain", action="store_true", help="solo il piano stimato (EXPLAIN, niente ANALYZE)")
    q.add_argument("--accept-cost", action="store_true",
                   help="esegue anche se la stima di costo supera la soglia (ambienti in cost_gate.envs); vale per "
                        "questa sola esecuzione e si usa solo dopo il si' esplicito dell'utente, mai per default")
    tb = sub.add_parser("tables")
    tb.add_argument("env")
    tb.add_argument("target")
    tb.add_argument("pattern", nargs="?")
    tb.add_argument("--schema")
    de = sub.add_parser("describe")
    de.add_argument("env")
    de.add_argument("target")
    de.add_argument("name", help="schema.tabella oppure tabella")
    dbs = sub.add_parser("databases")
    dbs.add_argument("env")
    lo = sub.add_parser("locate")
    lo.add_argument("env")
    lo.add_argument("term", help="microservizio, schema, tabella o parte del nome")
    lo.add_argument("--live", action="store_true", help="cerca anche nei cataloghi dei DB dell'ambiente")
    w = sub.add_parser("write")
    common(w, True)
    w.add_argument("--dry-run", action="store_true")
    w.add_argument("--commit", action="store_true")
    w.add_argument("--token")
    w.add_argument("--confirm-env")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    cfg = None
    try:
        cfg = load_config(root)
        if not cfg.get("enabled"):
            raise ToolError(EXIT_USAGE, "capability_disabled",
                            "db_access disabilitata: imposta db_access.enabled: true")
        handler = {"targets": cmd_targets, "check": cmd_check, "query": cmd_query, "write": cmd_write,
                   "tables": cmd_tables, "describe": cmd_describe, "databases": cmd_databases,
                   "locate": cmd_locate}[args.cmd]
        return handler(root, cfg, args)
    except ToolError as err:
        if cfg is not None:
            enrich_timeout(err, cfg, getattr(args, "env", None))
        print(json.dumps(err.payload, ensure_ascii=False, default=str))
        print(f"db_access: {err.payload['error']}: {err.payload['message']}", file=sys.stderr)
        return err.code


if __name__ == "__main__":
    sys.exit(main())
