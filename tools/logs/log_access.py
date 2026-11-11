#!/usr/bin/env python3
"""Lettura dei log applicativi su OpenSearch, in sola lettura, multi-ambiente e multi-cluster.

Sottocomandi:

  targets [--env ENV]            registro + stato credenziali, nessuna connessione   (JSON)
  check   ENV APP                login, ultimo evento e conteggio dell'ultima ora    (JSON)
  search  ENV APP [filtri]       righe di log (mascherate, compattate)               (testo)
  count   ENV APP [filtri]       conteggi, raggruppamenti, istogramma                (testo)
  noise   ENV APP [filtri]       gruppi che inondano il log + regole candidate       (testo)
  noise-add ENV APP --container/--logger/--level/--message --reason R
                                 anteprima dell'impatto di una regola di rumore e, con
                                 --confirm <token>, scrittura nel profilo               (JSON)
  handled-add ENV APP ...        come noise-add, per gli ERRORI GESTITI (attesi: nascosti
                                 dall'elenco e riassunti in una riga; --show-handled li mostra)
  fields  ENV APP [pattern]      campi dell'index con tipo e aggregabilita'          (testo)
  namespaces ENV [APP]           namespace presenti nell'index, con conteggio        (testo)
  guide   [ENV APP]              regole d'uso e regole di rumore attive              (testo)

Opzione comune --out PATH: scrive l'output su file invece che su stdout. Per gli ambienti PROTETTI
(`protected_envs`) il percorso dentro le cartelle di `protected_out_forbidden_dirs` (default raw, wiki,
deliverables, management) e' RIFIUTATO dal codice, prima di ogni connessione (exit 1, `protected_out_forbidden`).

ENV e APP risolvono cluster, index, namespace e mappa dei campi dal registro (tools/logs/log-targets.yaml): non
esistono --index o --namespace liberi. Le uniche operazioni verso il cluster sono _search, _count e
_field_caps. Tutto l'output passa da log_mask.mask(): i segreti sono sempre mascherati, i dati
personali di default (consigliato soprattutto sugli ambienti protetti) e in chiaro solo con --no-mask.

Exit code: 0 ok | 1 uso/config (target ignoto, credenziali assenti, capability spenta)
           | 2 connessione/autenticazione/TLS | 4 noise-add: token di conferma non valido
           | 5 errore del cluster sulla ricerca | 6 timeout
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log_client  # noqa: E402
import log_mask  # noqa: E402
from log_client import ClientError  # noqa: E402
from log_mask import nested, template  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_GATE = 4                       # noise-add: token di conferma non valido

RULE_KEYS = ("container", "logger", "level", "message")     # condizioni di una regola di rumore, in AND

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "env_file": ".env",             # file delle credenziali (nomi delle variabili nel registro); sovrascrivibile per cluster/app
    "registry": "tools/logs/log-targets.yaml",
    "noise_dir": "tools/logs/noise",
    "handled_dir": "tools/logs/handled",    # errori gestiti: attesi, visibili ma etichettati
    "protected_envs": ["prod"],
    "protected_out_forbidden_dirs": ["raw", "wiki", "deliverables", "management"],  # --out vietato qui per gli ambienti protetti
    "timezone": "UTC",              # fuso degli orari in ingresso (--since/--around ISO senza offset) e in uscita
    "app_package": "",              # prefisso dei frame applicativi tenuti negli stack trace accorciati (vuoto: solo il primo)
    "mask_patterns": [],            # insiemi nominati di dati personali da mascherare (es. it-codice-fiscale, it-partita-iva)
    "mask_custom_patterns": {},     # {nome: regex} propri
    "mask_person_keys": [],         # nomi di chiave in piu' i cui valori sono nomi di persona
    "default_since": "1h",
    "default_size": 50,
    "max_size": 500,
    "max_sample": 5000,
    "max_chars": 800,
    "max_stack": 1200,
    "mask_personal_data": True,     # False: dati personali in chiaro di default (--no-mask lo fa per una sola esecuzione)
    "max_output_chars": 30000,      # ~32 KiB: oltre, l'output si ferma con un avviso
    "timeout_s": 60,
    "tls_attempts": 3,
    "state_dir": ".log-access-state",   # anteprime di noise-add in attesa di conferma (non versionato)
    "pending_ttl_minutes": 30,
}

# Mappa dei campi dell'index. Ogni target puo' sovrascriverla (registro: `fields:` in `defaults`, nel cluster o
# nell'app, in quest'ordine di precedenza crescente); questi sono i DEFAULT (log di pod Kubernetes con logback/pino).
# Il timestamp e' un campo data in UTC. I campi testuali hanno la variante aggregabile `raw_suffix` (".raw";
# negli index con mapping dinamico di Elasticsearch/OpenSearch e' tipicamente ".keyword").
DEFAULT_FIELDS: dict[str, Any] = {
    "timestamp": "@timestamp",
    "namespace": "kubernetes.namespace_name",
    "container": "kubernetes.container_name",
    "pod": "kubernetes.pod_name",
    "level": "logLevel",            # ERROR, WARN, INFO, DEBUG
    "logger": "loggerName",
    "trace": "dt.trace_id",         # lo stesso id segue la richiesta tra i servizi (qualunque APM)
    "message": "message",
    "stack": ["stack_trace", "err.stack"],  # stack trace (logback JSON, pino): NON sono nel message
    "raw_suffix": ".raw",
}
FIELD_RE = re.compile(r"^[A-Za-z0-9_.@-]+$")
SUFFIX_RE = re.compile(r"^(\.[A-Za-z0-9_-]+)?$")

# Costanti dei nomi di campo di default: restano per i chiamanti e i test che non leggono il registro.
TIMESTAMP = DEFAULT_FIELDS["timestamp"]
NAMESPACE = DEFAULT_FIELDS["namespace"]
CONTAINER = DEFAULT_FIELDS["container"]
POD = DEFAULT_FIELDS["pod"]
LEVEL = DEFAULT_FIELDS["level"]
LOGGER = DEFAULT_FIELDS["logger"]
TRACE = DEFAULT_FIELDS["trace"]
MESSAGE = DEFAULT_FIELDS["message"]
STACK_FIELDS = tuple(DEFAULT_FIELDS["stack"])
ERROR_LEVELS = ("ERROR", "WARN")

NOISE_THRESHOLD = 0.05  # quota oltre la quale `noise` propone una regola
HINT_THRESHOLD = 0.4    # quota di righe con lo stesso schema oltre la quale `search` suggerisce `noise`

GUIDE = """\
GUIDA RAPIDA di log_access.py (vale per chiunque lo usi, Claude compreso)

Lancio: python3 tools/logs/log_access.py <comando> <env> <app> ... (rete/VPN del cluster attiva). Ambienti e app: `targets`.
I nomi dei campi citati sotto (container, livello, logger, trace, message, stack) sono i DEFAULT: ogni target puo' mapparli
su altri nomi nel registro (`fields:`); `fields <env> <app>` mostra quelli realmente presenti nell'index.

Dal largo allo stretto, per non riempire il contesto:
 1. count prima di search: --by <campo container>, --by <campo livello>, --histogram 10m
 2. finestra breve: --since 15m..2h, oppure --since/--until ISO (nel fuso configurato), oppure
    --around <ora evento> [--window 15m] per un ticket con un orario preciso
 3. search con filtri stretti: --container, --level ERROR --level WARN, --message, --size 20-50
 4. trovato l'evento, si segue la richiesta tra i servizi con il trace della riga: --trace <id> --asc
 5. --max-chars 0, --full-stack, --raw solo sulle poche righe che servono davvero

Rumore:
 - le regole del profilo dell'app (tools/logs/noise/<profilo>.json) sono escluse di default; l'intestazione
   dice quante righe ha tolto ciascuna. --with-noise le include (ad esempio seguendo un trace)
 - se l'output e' dominato da uno schema ripetuto lo script lo segnala: lanciare `noise` sulla stessa finestra
   e PROPORRE all'utente le regole candidate (numerate c1, c2, ...). Per aggiungerne una: `noise-add` con le
   condizioni della candidata mostra l'impatto (righe tolte, per livello, avvisi, app che condividono il profilo)
   e un token; si chiede all'utente conferma esplicita e SOLO DOPO si riesegue con --reason e --confirm <token>.
   Una regola che toglie righe ERROR/WARN richiede in piu' --allow-error-level
 - le righe consecutive con stesso container, livello, logger e schema sono compattate in "xN"
   (si vede la prima); --no-collapse le mostra tutte

Errori gestiti (profilo handled, per app):
 - sono errori ATTESI che l'applicazione usa di proposito (es. un 409 che il frontend usa per mostrare una scelta
   all'utente). Non sono guasti e, se ripetuti, saturerebbero il contesto: di default NON compaiono
   nell'elenco, ma l'intestazione di search/count ne riassume una riga ciascuno (nome, conteggio, primo e ultimo
   orario). --show-handled li include nell'elenco, con l'etichetta [gestito: nome]
 - un errore gestito che cresce in modo anomalo va comunque guardato: confrontare il conteggio fra finestre
   (count --message <frase> --histogram 1h). Per registrarne uno: `handled-add` (anteprima, conferma dell'utente,
   poi --confirm <token>), come per il rumore

Query:
 - --message/--exclude sono frasi sulle parole del message: un identificatore con i punti (es.
   "Filter.doFilterInternal()") e' UNA parola sola, quindi va scritto per intero. Vale per le eccezioni Java:
   --message DateTimeParseException trova 0 righe, serve java.time.format.DateTimeParseException
   (oppure --query 'message:*DateTimeParseException*', piu' lento)
 - smistamento degli errori di un servizio: noise --container X --level ERROR --since 30d raggruppa per
   logger e per schema di messaggio (le "regole candidate" in quel caso non vanno proposte)
 - niente virgolette doppie dentro gli argomenti (su Windows con pyenv-win vanno perse). Per i message JSON
   basta la frase senza simboli: --message "resp_status 500", --exclude "req_path /health"
 - ogni app puo' dichiarare da quando ci sono log (data_from in `targets`): prima di quella data non c'e' nulla,
   e una finestra senza righe non prova che l'evento non sia avvenuto

Lettura:
 - un livello ERROR non e' per forza un guasto: alcuni filtri di logging scrivono richieste/risposte a livello ERROR
   anche per i 4xx
 - la causa vera di un ERROR e' quasi sempre nello stack trace, che spesso NON sta nel message ma in un campo
   dedicato (fields.stack): search lo mostra sotto il message ("stack:"), accorciato a righe d'eccezione,
   Caused by/Wrapped by, primo frame di ogni blocco e frame del pacchetto applicativo (app_package) (--max-stack, --full-stack)
 - per i message JSON gli schemi usano msg, err.*, metodo e URL invece del JSON grezzo
 - alcuni servizi scrivono testo semplice: livello e trace id possono stare DENTRO il message (campi livello e trace
   vuoti). Per seguire una loro richiesta: --message <trace_id>, non --trace
 - orari in ingresso e in uscita: nel fuso configurato (`timezone`, default UTC); il timestamp e' salvato in UTC

Dati personali:
 - di default email e nomi nei campi strutturati, piu' i pattern attivati in configurazione (mask_patterns, ad esempio
   it-codice-fiscale, it-partita-iva), sono mascherati con hash validi solo nella stessa
   esecuzione: per riconoscere lo stesso soggetto su piu' righe bisogna restare in UNA esecuzione
 - il mascheramento e' CONSIGLIATO, in particolare sugli ambienti protetti; --no-mask lascia i dati personali in chiaro per
   quell'esecuzione (serve quando il dato stesso e' l'oggetto dell'analisi). Token, JWT, password e chiavi
   restano mascherati anche con --no-mask. Il tool lo dichiara nell'intestazione dell'output
 - per cercare un soggetto lo si passa a --message: con il mascheramento attivo il valore compare nel comando,
   mai nell'output
 - su ambienti protetti l'output non va copiato in raw/, wiki/, deliverables/, kanban, log o commit: --out dentro
   quelle cartelle e' rifiutato dal codice (protected_out_forbidden_dirs)
"""


# --- Configurazione e registro -------------------------------------------------------------------------------

def parse_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE senza interpretazione shell. Apici esterni rimossi, nessun taglio dei commenti in linea
    (le password possono contenere '#')."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_config(root: Path) -> dict[str, Any]:
    import yaml

    data = yaml.safe_load((root / "factory.config.yaml").read_text(encoding="utf-8")) or {}
    cfg = dict(DEFAULTS)
    cfg.update(data.get("log_access") or {})
    return cfg


def configure_masking(cfg: dict[str, Any]) -> None:
    """Applica a log_mask i pattern di dati personali scelti in configurazione."""
    try:
        log_mask.configure(cfg["mask_patterns"], cfg["mask_custom_patterns"], cfg["mask_person_keys"])
    except ValueError as error:
        raise ClientError(EXIT_USAGE, "bad_config", str(error)) from None


def load_registry(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    import yaml

    path = root / cfg["registry"]
    if not path.is_file():
        raise ClientError(EXIT_USAGE, "registry_missing", f"registro non trovato: {cfg['registry']}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {"clusters": data.get("clusters") or {}, "environments": data.get("environments") or {},
            "defaults": data.get("defaults") or {}}


def load_env_values(root: Path, env_file: str) -> dict[str, str]:
    if not env_file:
        return {}
    path = root / env_file          # un percorso assoluto resta tale
    return parse_env_file(path) if path.is_file() else {}


def resolve_fields(registry: dict[str, Any], cluster: dict, definition: dict, label: str) -> dict[str, Any]:
    """Mappa dei campi: default documentati < registry.defaults.fields < cluster.fields < app.fields."""
    fields = dict(DEFAULT_FIELDS)
    for source in (registry.get("defaults") or {}, cluster, definition):
        override = source.get("fields") or {}
        if not isinstance(override, dict):
            raise ClientError(EXIT_USAGE, "registry_invalid", f"{label}: 'fields' deve essere una mappa")
        for key, value in override.items():
            if key not in DEFAULT_FIELDS:
                raise ClientError(EXIT_USAGE, "registry_invalid", f"{label}: campo sconosciuto in fields: {key}",
                                  available=sorted(DEFAULT_FIELDS))
            fields[key] = value
    names = fields["stack"] if isinstance(fields["stack"], list) else [fields["stack"]]
    fields["stack"] = names
    checks = [fields[k] for k in DEFAULT_FIELDS if k not in ("stack", "raw_suffix")] + names
    if not all(isinstance(v, str) and FIELD_RE.match(v) for v in checks) or not SUFFIX_RE.match(str(fields["raw_suffix"])):
        raise ClientError(EXIT_USAGE, "registry_invalid", f"{label}: nome di campo non ammesso in fields")
    return fields


def resolve_target(registry: dict[str, Any], env: str, app: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cluster, index, namespace, campi e parametri di (env, app). Nessun valore segreto."""
    cfg = cfg or DEFAULTS
    envs = registry["environments"]
    if env not in envs:
        raise ClientError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {env}", available=sorted(envs))
    apps = envs[env].get("apps") or {}
    if app not in apps:
        raise ClientError(EXIT_USAGE, "unknown_app", f"app '{app}' non definita per {env}", available=sorted(apps))
    definition = apps[app]
    cluster_id = definition.get("cluster")
    cluster = registry["clusters"].get(cluster_id)
    if cluster is None:
        raise ClientError(EXIT_USAGE, "registry_invalid", f"cluster '{cluster_id}' di {env}/{app} non definito",
                          available=sorted(registry["clusters"]))
    for field in ("index", "namespace"):
        if not definition.get(field):
            raise ClientError(EXIT_USAGE, "registry_invalid", f"{env}/{app}: manca '{field}'")
    if not log_client.INDEX_RE.match(definition["index"]):
        raise ClientError(EXIT_USAGE, "registry_invalid", f"index non ammesso: {definition['index']}")
    defaults = registry.get("defaults") or {}

    def pick(key: str, fallback: Any) -> Any:
        for source in (definition, cluster, defaults):
            if source.get(key) not in (None, ""):
                return source[key]
        return fallback

    return {"env": env, "env_label": envs[env].get("label", env), "app": app, "cluster_id": cluster_id,
            "cluster": cluster, "index": definition["index"], "namespace": definition["namespace"],
            "noise": definition.get("noise"), "unverified": bool(definition.get("unverified")),
            "note": definition.get("note"), "data_from": definition.get("data_from"),
            "fields": resolve_fields(registry, cluster, definition, f"{env}/{app}"),
            "env_file": pick("env_file", cfg["env_file"]), "app_package": pick("app_package", cfg["app_package"]),
            "timezone": cfg["timezone"]}


def noise_rules(root: Path, cfg: dict[str, Any], target: dict[str, Any], with_noise: bool) -> list[dict]:
    if with_noise or not target["noise"]:
        return []
    path = root / cfg["noise_dir"] / f"{target['noise']}.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("rules") or []


# --- Output --------------------------------------------------------------------------------------------------

class Printer:
    """Stampa solo testo mascherato, entro un tetto di caratteri: oltre, avvisa una volta e smette."""

    def __init__(self, max_chars: int, personal: bool = True) -> None:
        self.max_chars = max_chars
        self.personal = personal
        self.used = 0
        self.truncated = False

    def __call__(self, text: Any = "") -> None:
        masked = log_mask.mask(str(text), self.personal)
        if self.truncated:
            return
        if self.used + len(masked) > self.max_chars:
            self.truncated = True
            print(f"# output troncato a {self.max_chars} caratteri: restringere i filtri o ridurre --size")
            return
        self.used += len(masked) + 1
        print(masked)


def emit_json(payload: dict) -> None:
    print(log_mask.mask(json.dumps(payload, ensure_ascii=False, indent=2)))


# --- Tempo ---------------------------------------------------------------------------------------------------

def zone(name: str = "UTC"):
    """Fuso configurato (`timezone`): UTC senza tzdata, gli altri via zoneinfo (Python 3.9+)."""
    if name.upper() == "UTC":
        return dt.timezone.utc
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ClientError(EXIT_USAGE, "tzdata_missing", f"fuso {name} non disponibile: pip install tzdata") from None


def parse_iso(value: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ClientError(EXIT_USAGE, "bad_time", f"data/ora non valida (ISO, fuso configurato se senza offset): {value}") from None


def time_bound(value: str) -> str:
    """'15m', '2h', '3d' -> date math relativa a adesso; altrimenti data/ora ISO (fuso configurato se senza offset)."""
    if re.fullmatch(r"\d+[smhdw]", value):
        return f"now-{value}"
    if value == "now":
        return value
    parse_iso(value)        # solo validazione: il valore va al cluster cosi' com'e'
    return value


def around_window(around: str, window: str, tz: str = "UTC") -> tuple[str, str]:
    """Finestra simmetrica attorno a un orario (fuso `tz` se senza offset), in UTC con suffisso Z."""
    match = re.fullmatch(r"(\d+)([smhdw])", window)
    if not match:
        raise ClientError(EXIT_USAGE, "bad_window", f"--window va scritto come 15m, 2h, 1d: {window}")
    seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[match.group(2)]
    moment = parse_iso(around)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone(tz))
    delta = dt.timedelta(seconds=seconds)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    utc = dt.timezone.utc
    return (moment - delta).astimezone(utc).strftime(fmt), (moment + delta).astimezone(utc).strftime(fmt)


def local_time(value: Any, tz: str = "UTC") -> str:
    """@timestamp (UTC, con o senza fuso, millisecondi con la virgola o nanosecondi) -> ora nel fuso `tz`."""
    normalized = re.sub(r"(\.\d{6})\d+", r"\1", str(value).replace(",", ".").replace("Z", "+00:00"))
    try:
        moment = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return str(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    return moment.astimezone(zone(tz)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# --- Query ---------------------------------------------------------------------------------------------------

def fields_of(target: dict[str, Any]) -> dict[str, Any]:
    return target.get("fields") or DEFAULT_FIELDS


def build_query(args, target: dict[str, Any]) -> dict:
    f = fields_of(target)
    # match_phrase e non term: funziona sia con campi keyword sia con campi text, qualunque sia il mapping
    must: list[dict] = [{"match_phrase": {f["namespace"]: target["namespace"]}}]
    must_not: list[dict] = []
    must.append({"range": {f["timestamp"]: {"gte": time_bound(args.since), "lte": time_bound(args.until),
                                            "time_zone": target.get("timezone", "UTC")}}})
    for field, values in ((f["level"], args.level), (f["trace"], args.trace), (f["container"], args.container)):
        if values:
            must.append({"bool": {"should": [{"match_phrase": {field: v}} for v in values],
                                  "minimum_should_match": 1}})
    for phrase in args.message or []:
        must.append({"match_phrase": {f["message"]: phrase}})
    for phrase in args.exclude or []:
        must_not.append({"match_phrase": {f["message"]: phrase}})
    for condition in args.filter or []:
        field, _, value = condition.partition("=")
        if not field or not value:
            raise ClientError(EXIT_USAGE, "bad_filter", f"--filter va scritto campo=valore: {condition}")
        must.append({"match_phrase": {field: value}})
    if args.query:
        must.append({"query_string": {"query": args.query, "default_field": f["message"]}})
    return {"bool": {"filter": must, "must_not": must_not}}


def rule_query(rule: dict, fields: dict[str, Any] = DEFAULT_FIELDS) -> dict:
    """Le condizioni di una regola sono in AND: container, logger e livello esatti, message come frase."""
    suffix = fields["raw_suffix"]
    clauses = [{"term": {f"{fields[key]}{suffix}": rule[key]}}
               for key in ("container", "logger", "level") if rule.get(key)]
    if rule.get("message"):
        clauses.append({"match_phrase": {fields["message"]: rule["message"]}})
    return {"bool": {"filter": clauses}}


def handled_rules(root: Path, cfg: dict[str, Any], target: dict[str, Any]) -> list[dict]:
    if not target["noise"]:
        return []
    path = root / cfg["handled_dir"] / f"{target['noise']}.json"
    return (json.loads(path.read_text(encoding="utf-8")).get("rules") or []) if path.is_file() else []


def apply_handled(body: dict, rules: list[dict], fields: dict[str, Any] = DEFAULT_FIELDS) -> None:
    """Con --show-handled: conta nel risultato della ricerca le righe di ogni errore gestito (restano nell'elenco)."""
    if rules:
        body.setdefault("aggs", {})["handled"] = {"filters": {"filters": {r["name"]: rule_query(r, fields) for r in rules}}}


def apply_handled_hidden(body: dict, base: dict, noise: list[dict], handled: list[dict],
                         fields: dict[str, Any] = DEFAULT_FIELDS) -> None:
    """Default: rumore e errori gestiti fuori dall'elenco; degli errori gestiti si contano righe, primo e ultimo orario."""
    apply_noise(body, base, noise, fields)
    if not handled:
        return
    ts = fields["timestamp"]
    body["query"] = {"bool": {"filter": [body["query"]], "must_not": [rule_query(r, fields) for r in handled]}}
    body.setdefault("aggs", {})["handled"] = {"global": {}, "aggs": {"rules": {
        "filters": {"filters": {r["name"]: {"bool": {"filter": [base, rule_query(r, fields)]}} for r in handled}},
        "aggs": {"first": {"min": {"field": ts}}, "last": {"max": {"field": ts}}}}}}


def _ms_to_local(value: Any, tz: str = "UTC") -> str:
    return local_time(dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).isoformat(), tz)[:19]


def handled_header(out: Printer, result: dict, tz: str = "UTC") -> None:
    node = result.get("aggregations", {}).get("handled", {})
    buckets = node.get("rules", node).get("buckets", {})
    present = {name: b for name, b in buckets.items() if b["doc_count"]}
    if not present:
        return
    parts = []
    for name, bucket in sorted(present.items(), key=lambda kv: -kv[1]["doc_count"]):
        span = ""
        if bucket.get("first", {}).get("value") and bucket.get("last", {}).get("value"):
            span = f" ({_ms_to_local(bucket['first']['value'], tz)} -> {_ms_to_local(bucket['last']['value'], tz)})"
        parts.append(f"{name} x{bucket['doc_count']}{span}")
    shown = "inclusi nell'elenco" if "rules" not in node else "nascosti dall'elenco, --show-handled per vederli"
    out(f"# errori gestiti (attesi, non guasti; {shown}): " + "; ".join(parts))


def handled_name(source: dict, rules: list[dict], fields: dict[str, Any] = DEFAULT_FIELDS) -> str | None:
    """Nome della prima regola di errore gestito che corrisponde alla riga (stesse condizioni di rule_query)."""
    message = str(source.get(fields["message"], "")).lower()
    for rule in rules:
        if any(rule.get(key) and nested(source, fields[key]) != rule[key]
               for key in ("container", "logger", "level")):
            continue
        if rule.get("message") and rule["message"].lower() not in message:
            continue
        return rule["name"]
    return None


def apply_noise(body: dict, base: dict, rules: list[dict], fields: dict[str, Any] = DEFAULT_FIELDS) -> None:
    """Esclude il rumore dalla query e conta, con un'aggregazione globale, quante righe toglie ogni regola."""
    if not rules:
        body["query"] = base
        return
    body["query"] = {"bool": {"filter": [base], "must_not": [rule_query(r, fields) for r in rules]}}
    body.setdefault("aggs", {})["noise"] = {"global": {}, "aggs": {"rules": {"filters": {"filters": {
        r["name"]: {"bool": {"filter": [base, rule_query(r, fields)]}} for r in rules}}}}}


def noise_header(out: Printer, result: dict) -> None:
    buckets = result.get("aggregations", {}).get("noise", {}).get("rules", {}).get("buckets", {})
    removed = {name: b["doc_count"] for name, b in buckets.items() if b["doc_count"]}
    if removed:
        listed = ", ".join(f"{name} {n}" for name, n in sorted(removed.items(), key=lambda kv: -kv[1]))
        out(f"# rumore escluso (profilo di rumore dell'app): {listed}  [--with-noise per includerlo]")


NON_STRING_TYPES = {"long", "integer", "short", "byte", "double", "float", "half_float", "scaled_float",
                    "unsigned_long", "date", "date_nanos", "boolean"}


def aggregatable_info(client, target: dict[str, Any], field: str) -> tuple[str, bool]:
    """(campo aggregabile, e' una stringa). Il campo stesso se aggregabile, altrimenti la variante `raw_suffix`."""
    suffix = fields_of(target)["raw_suffix"]
    caps = client.query(target["index"], "_field_caps", {}, f"fields={field},{field}{suffix}")["fields"]
    for candidate in (field, f"{field}{suffix}"):
        types = caps.get(candidate, {})
        if any(t.get("aggregatable") for t in types.values()):
            return candidate, not set(types) <= NON_STRING_TYPES
    raise ClientError(EXIT_USAGE, "not_aggregatable", f"campo non aggregabile: {field}")


def aggregatable(client, target: dict[str, Any], field: str) -> str:
    return aggregatable_info(client, target, field)[0]


def short(value: Any, separator: str) -> str:
    return str(value or "").rsplit(separator, 1)[-1]


def percent(part: float, whole: float) -> str:
    return f"{100 * part / whole:5.1f}%" if whole else "    -"


def header(out: Printer, target: dict[str, Any], protected: bool) -> None:
    out(f"# {target['env']}/{target['app']} cluster={target['cluster_id']} index={target['index']} "
        f"namespace={target['namespace']}")
    if target["unverified"]:
        out(f"# ATTENZIONE: target non verificato{': ' + target['note'] if target['note'] else ''}")
    if not out.personal:
        out("# ATTENZIONE: mascheramento dei dati personali DISATTIVATO (--no-mask); segreti comunque mascherati"
            + ("; ambiente PROTETTO, consigliato rieseguire senza --no-mask" if protected else ""))
    if protected:
        out("# PROTETTO: non copiare l'output in raw/, wiki/, deliverables/, kanban, log o commit "
            "(--out in quelle cartelle e' rifiutato)")


# --- Comandi -------------------------------------------------------------------------------------------------

def cmd_search(ctx, args) -> None:
    out, client, target = ctx["out"], ctx.get("client"), ctx["target"]
    f, tz = fields_of(target), target.get("timezone", "UTC")
    body = {"size": min(args.size, ctx["cfg"]["max_size"]),
            "sort": [{f["timestamp"]: {"order": "asc" if args.asc else "desc"}}], "track_total_hits": True}
    base_query = build_query(args, target)
    if getattr(args, "show_handled", False):
        apply_noise(body, base_query, ctx["rules"], f)
        apply_handled(body, ctx["handled"], f)
    else:
        apply_handled_hidden(body, base_query, ctx["rules"], ctx["handled"], f)
    if not args.raw:
        body["_source"] = [f["timestamp"], f["container"], f["pod"], f["level"], f["logger"], f["trace"], f["message"],
                           *f["stack"]] + (args.fields or [])
    if args.dry_run:
        return out(json.dumps(body, indent=2, ensure_ascii=False))

    result = client.query(target["index"], "_search", body)
    hits = result["hits"]["hits"]
    header(out, target, ctx["protected"])
    out(f"# {result['hits']['total']['value']} righe trovate, mostrate {len(hits)} "
        f"({'dalla piu vecchia' if args.asc else 'dalla piu recente'}; orari {tz})")
    noise_header(out, result)
    handled_header(out, result, tz)

    if args.raw:
        for hit in hits:
            out(json.dumps(hit["_source"], indent=2, ensure_ascii=False))
            out("-" * 80)
        return

    # Righe consecutive con stesso container, livello, logger e schema: si mostra la prima con il conteggio
    groups: list[dict] = []
    for hit in hits:
        source = hit["_source"]
        key = (nested(source, f["container"]), nested(source, f["level"]), nested(source, f["logger"]),
               template(source.get(f["message"], "")))
        if groups and not args.no_collapse and groups[-1]["key"] == key:
            groups[-1]["count"] += 1
            groups[-1]["last"] = source.get(f["timestamp"])
        else:
            groups.append({"key": key, "source": source, "count": 1, "last": None})

    for group in groups:
        source = group["source"]
        message = str(source.get(f["message"], "")).rstrip()
        if not args.full_stack:
            message = log_mask.trim_stack(message, target.get("app_package", ""))
        if args.max_chars and len(message) > args.max_chars:
            message = message[:args.max_chars] + f" ...[+{len(message) - args.max_chars} caratteri]"
        extra = " ".join(f"{name}={nested(source, name)}" for name in args.fields or [])
        first = local_time(source.get(f["timestamp"]), tz)
        repeated = ""
        if group["count"] > 1:
            last = local_time(group["last"], tz)
            until = last[11:] if last[:10] == first[:10] else last     # la data solo se cambia giorno
            repeated = f" | x{group['count']}, l'altro estremo: {until}"
        label = handled_name(source, ctx["handled"], f)
        out(f"{first} | {nested(source, f['container'])}/{short(nested(source, f['pod']), '-')}"
            f" | {nested(source, f['level'])}{f' [gestito: {label}]' if label else ''}"
            f" | {short(nested(source, f['logger']), '.')}"
            f" | trace={nested(source, f['trace'])}"
            f"{' | ' + extra if extra else ''}{repeated}")
        out("  " + message.replace("\n", "\n  "))
        stack = next((str(nested(source, name)) for name in f["stack"] if nested(source, name)), "")
        if stack and args.max_stack:
            stack = stack if args.full_stack else log_mask.trim_stack(stack, target.get("app_package", ""))
            if len(stack) > args.max_stack:
                stack = stack[:args.max_stack] + f" ...[+{len(stack) - args.max_stack} caratteri]"
            out("  stack: " + stack.strip().replace("\n", "\n    "))

    schemas: Counter = Counter()
    for group in groups:
        schemas[group["key"][3]] += group["count"]
    if len(hits) >= 20 and schemas:
        schema, n = schemas.most_common(1)[0]
        if n / len(hits) >= HINT_THRESHOLD:
            out(f"# suggerimento: {percent(n, len(hits)).strip()} delle righe ha lo schema \"{schema[:100]}\": "
                f"restringere (--exclude, --level) o valutare `noise` sulla stessa finestra")


def cmd_count(ctx, args) -> None:
    out, client, target = ctx["out"], ctx.get("client"), ctx["target"]
    f, tz = fields_of(target), target.get("timezone", "UTC")
    body: dict[str, Any] = {"size": 0, "track_total_hits": True, "aggs": {}}
    base_query = build_query(args, target)
    if getattr(args, "show_handled", False):
        apply_noise(body, base_query, ctx["rules"], f)
        apply_handled(body, ctx["handled"], f)
    else:
        apply_handled_hidden(body, base_query, ctx["rules"], ctx["handled"], f)
    by = None
    if args.by:
        by, textual = (args.by, True) if args.dry_run else aggregatable_info(client, target, args.by)
        body["aggs"]["by"] = {"terms": {"field": by, "size": args.top}}
        if textual:
            # missing: senza, le righe prive del campo (es. log strutturati senza livello) sparirebbero.
            # Non vale per i campi numerici o data, che non accettano un segnaposto testuale.
            body["aggs"]["by"]["terms"]["missing"] = "(assente)"
    if args.histogram:
        body["aggs"]["histogram"] = {"date_histogram": {"field": f["timestamp"], "fixed_interval": args.histogram,
                                                        "time_zone": tz, "min_doc_count": 1}}
    if args.dry_run:
        return out(json.dumps(body, indent=2, ensure_ascii=False))

    result = client.query(target["index"], "_search", body)
    header(out, target, ctx["protected"])
    out(f"# totale: {result['hits']['total']['value']}")
    noise_header(out, result)
    handled_header(out, result, tz)
    aggregations = result.get("aggregations", {})
    if "by" in aggregations:
        out(f"\n## per {by} (primi {args.top})")
        for bucket in aggregations["by"]["buckets"]:
            out(f"{bucket['doc_count']:>8}  {bucket['key']}")
        if aggregations["by"].get("sum_other_doc_count"):
            out(f"{aggregations['by']['sum_other_doc_count']:>8}  (altri)")
    if "histogram" in aggregations:
        out(f"\n## per intervallo di {args.histogram} ({tz})")
        for bucket in aggregations["histogram"]["buckets"]:
            out(f"{bucket['doc_count']:>8}  {bucket['key_as_string']}")


def cmd_noise(ctx, args) -> None:
    """Valuta la finestra (rumore gia' noto escluso) e propone regole per i gruppi che pesano troppo."""
    out, client, target, rules = ctx["out"], ctx.get("client"), ctx["target"], ctx["rules"]
    f, tz = fields_of(target), target.get("timezone", "UTC")
    sfx = f["raw_suffix"]
    base = build_query(args, target)
    groups_agg = {"terms": {"field": f"{f['container']}{sfx}", "size": 15}, "aggs": {
        "logger": {"terms": {"field": f"{f['logger']}{sfx}", "size": 8, "missing": "-"}, "aggs": {
            "level": {"terms": {"field": f"{f['level']}{sfx}", "size": 4, "missing": "-"}, "aggs": {
                "example": {"top_hits": {"size": 1, "_source": [f["message"]]}}}}}}}}
    body: dict[str, Any] = {"size": 0, "track_total_hits": True, "aggs": {"container": groups_agg}}
    apply_noise(body, base, rules, f)
    sample = {"size": min(args.sample, ctx["cfg"]["max_sample"]), "sort": [{f["timestamp"]: {"order": "desc"}}],
              "_source": [f["container"], f["logger"], f["level"], f["message"]]}
    apply_noise(sample, base, rules, f)
    if args.dry_run:
        return out(json.dumps({"gruppi": body, "campione": sample}, indent=2, ensure_ascii=False))

    result = client.query(target["index"], "_search", body)
    total = result["hits"]["total"]["value"]
    header(out, target, ctx["protected"])
    out(f"# finestra {args.since} -> {args.until}: {total} righe, rumore noto escluso ({len(rules)} regole)")
    noise_header(out, result)

    candidates: list[tuple[dict, float]] = []
    groups = []
    for container in result["aggregations"]["container"]["buckets"]:
        for logger in container["logger"]["buckets"]:
            for level in logger["level"]["buckets"]:
                example = nested(level["example"]["hits"]["hits"][0]["_source"], f["message"]) or ""
                groups.append((level["doc_count"], container["key"], logger["key"], level["key"], example))
    groups.sort(key=lambda g: g[0], reverse=True)

    out("\n## gruppi container | logger | livello (almeno 1%)")
    for n, container, logger, level, example in groups:
        if n / max(total, 1) < 0.01:
            break
        out(f"{percent(n, total)} {n:>8}  {container} | {short(logger, '.')} | {level}  es: {template(example)[:90]}")
        if n / total >= NOISE_THRESHOLD and "-" not in (logger, level):
            candidates.append(({"container": container, "logger": logger, "level": level}, n / total))
    proposed_groups = {(c["container"], c["logger"], c["level"]) for c, _ in candidates}

    hits = client.query(target["index"], "_search", sample)["hits"]["hits"]
    schemas: Counter = Counter()
    covered: Counter = Counter()
    for hit in hits:
        source = hit["_source"]
        key = (nested(source, f["container"]), template(nested(source, f["message"]) or ""))
        schemas[key] += 1
        covered[key] += (key[0], nested(source, f["logger"]), nested(source, f["level"])) in proposed_groups
    out(f"\n## messaggi ricorrenti (campione delle {len(hits)} righe piu recenti)")
    for (container, schema), n in schemas.most_common(10):
        already = "  [gia nel gruppo candidato]" if covered[(container, schema)] >= 0.9 * n else ""
        out(f"{percent(n, len(hits))} {n:>8}  {container}  \"{schema[:110]}\"{already}")
        phrase = log_mask.literal(schema)
        if n / max(len(hits), 1) >= NOISE_THRESHOLD and len(phrase) >= 12 and not already:
            candidates.append(({"container": container, "message": phrase}, n / len(hits)))

    out(f"\n## regole candidate (almeno {NOISE_THRESHOLD:.0%}): da PROPORRE all'utente, nel profilo solo dopo conferma")
    if not candidates:
        out("nessuna")
    today = dt.datetime.now(zone(tz)).date().isoformat()
    for number, (condition, share) in enumerate(candidates, 1):
        warning = "  # ATTENZIONE: livello ERROR/WARN, escludere solo se innocuo" \
            if condition.get("level") in ERROR_LEVELS else ""
        rule = {"name": default_rule_name(condition), **condition, "reason": "<perche e rumore>", "added": today}
        out(f"c{number} {percent(share, 1)}  {json.dumps(rule, ensure_ascii=False)}{warning}")
        flags = " ".join(f"--{key} {shlex.quote(condition[key])}" for key in RULE_KEYS if condition.get(key))
        out(f"     per escluderla (anteprima, poi conferma): log_access.py noise-add {target['env']} {target['app']} "
            f"{flags} --reason '<perche e rumore>'")


# --- Rumore: aggiunta di una regola, con anteprima e conferma -------------------------------------------------

def default_rule_name(condition: dict) -> str:
    parts = [condition.get("container"), short(condition.get("logger"), "."), condition.get("level"),
             (condition.get("message") or "")[:40]]
    return re.sub(r"[^a-z0-9]+", "-", "-".join(p for p in parts if p).lower()).strip("-")[:60]


def rule_token(profile: str, conditions: dict, name: str, allow_error: bool, kind: str = "noise") -> str:
    """Impronta della regola: la conferma vale solo per questa regola, in questo profilo, con questo nome."""
    canonical = json.dumps({"profile": profile, "name": name, "rule": conditions, "allow_error": allow_error,
                            "kind": kind}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _pending_file(root: Path, cfg: dict[str, Any]) -> Path:
    return root / cfg["state_dir"] / "noise-pending.json"


def _load_pending(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    """Token emessi dalle anteprime e non ancora scaduti: {token: scadenza ISO UTC}."""
    path = _pending_file(root, cfg)
    if not path.is_file():
        return {}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    return {token: expires for token, expires in json.loads(path.read_text(encoding="utf-8")).items() if expires > now}


def _save_pending(root: Path, cfg: dict[str, Any], pending: dict[str, str]) -> None:
    path = _pending_file(root, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, indent=2), encoding="utf-8")


KINDS = {
    "noise": {"dir": "noise_dir", "hint": "perche e rumore", "what": "gruppo e' rumore"},
    "handled": {"dir": "handled_dir", "hint": "perche e un errore atteso", "what": "errore e' atteso e gestito"},
}


def cmd_noise_add(ctx, args) -> None:
    _manage_rule(ctx, args, "noise")


def cmd_handled_add(ctx, args) -> None:
    _manage_rule(ctx, args, "handled")


def _manage_rule(ctx, args, kind: str) -> None:
    """Senza --confirm: anteprima dell'impatto e token, nessuna scrittura. Con --confirm <token>: scrive nel
    profilo (file versionato). La conferma dell'utente la raccoglie chi invoca, tra i due passi.

    kind noise: la regola ESCLUDE le righe. kind handled: le righe restano visibili ed etichettate.
    """
    spec = KINDS[kind]
    target, root, cfg = ctx["target"], ctx["root"], ctx["cfg"]
    profile = target["noise"]
    if not profile:
        raise ClientError(EXIT_USAGE, "no_profile", f"{target['env']}/{target['app']} non ha un profilo")
    conditions = {key: getattr(args, key) for key in RULE_KEYS if getattr(args, key)}
    if not conditions:
        raise ClientError(EXIT_USAGE, "empty_rule", "serve almeno una condizione: --container, --logger, --level, --message")
    allow_error = bool(getattr(args, "allow_error_level", False))
    name = args.name or default_rule_name(conditions)
    path = root / cfg[spec["dir"]] / f"{profile}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"rules": []}
    for existing in data.get("rules") or []:
        if {key: existing.get(key) for key in RULE_KEYS if existing.get(key)} == conditions:
            return emit_json({"ok": True, "status": "already_present", "kind": kind, "profile": profile,
                              "rule": existing["name"]})
        if existing["name"] == name:
            raise ClientError(EXIT_USAGE, "name_taken", f"esiste gia' una regola '{name}' con condizioni diverse: --name")
    shared = sorted(f"{env}/{app}" for env, env_def in ctx["registry"]["environments"].items()
                    for app, definition in (env_def.get("apps") or {}).items() if definition.get("noise") == profile)
    token = rule_token(profile, conditions, name, allow_error, kind)

    if args.confirm:
        # Il token vale solo se l'anteprima di QUESTA regola l'ha emesso (e se non e' scaduto): una regola di rumore
        # che tocca ERROR/WARN ha il token solo con --allow-error-level, quindi non si aggira calcolandolo a mano.
        pending = _load_pending(root, cfg)
        if args.confirm != token or token not in pending:
            raise ClientError(EXIT_GATE, "bad_token",
                              "token non valido, scaduto o gia usato per questa regola: rifare l'anteprima e la conferma")
        if not args.reason:
            raise ClientError(EXIT_USAGE, "reason_missing", f"--reason e' obbligatorio: perche questo {spec['what']}")
        data.setdefault("rules", []).append({"name": name, **conditions, "reason": args.reason,
                                             "added": dt.datetime.now(zone(cfg["timezone"])).date().isoformat()})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pending.pop(token)                                  # monouso
        _save_pending(root, cfg, pending)
        return emit_json({"ok": True, "status": "added", "kind": kind, "profile": profile, "rule": name,
                          "file": f"{cfg[spec['dir']]}/{profile}.json", "applies_to": shared})

    f = fields_of(target)
    window = {"range": {f["timestamp"]: {"gte": time_bound(args.since), "lte": time_bound(args.until),
                                         "time_zone": cfg["timezone"]}}}
    body = {"size": 0, "track_total_hits": True,
            "query": {"bool": {"filter": [{"match_phrase": {f["namespace"]: target["namespace"]}}, window]}},
            "aggs": {"matched": {"filter": rule_query(conditions, f), "aggs": {
                "by_level": {"terms": {"field": f"{f['level']}{f['raw_suffix']}", "size": 6, "missing": "-"}}}}}}
    result = ctx["client"].query(target["index"], "_search", body)
    total = result["hits"]["total"]["value"]
    matched = result["aggregations"]["matched"]["doc_count"]
    by_level = {b["key"]: b["doc_count"] for b in result["aggregations"]["matched"]["by_level"]["buckets"]}
    errors = sum(n for level, n in by_level.items() if level in ERROR_LEVELS)
    warnings = []
    if kind == "noise" and errors:
        warnings.append(f"la regola toglie {errors} righe ERROR/WARN: escluderle solo se innocue (--allow-error-level)")
    if not matched:
        warnings.append("la regola non corrisponde a nessuna riga nella finestra: condizioni o finestra sbagliate?")
    if total and matched / total > 0.5:
        warnings.append(f"la regola toglie {matched / total:.0%} della finestra: controllare che non sia troppo ampia"
                        if kind == "noise" else
                        f"la regola riguarda il {matched / total:.0%} della finestra: a questo volume e' ancora un errore atteso?")
    if len(shared) > 1:
        warnings.append(f"il profilo '{profile}' e' condiviso da {len(shared)} app: la regola vale per tutte")
    payload: dict[str, Any] = {
        "ok": True, "status": "dry_run", "kind": kind, "profile": profile, "applies_to": shared,
        "rule": {"name": name, **conditions, "reason": args.reason or f"<{spec['hint']}>"},
        "window": {"since": args.since, "until": args.until}, "rows_in_window": total, "rows_matched": matched,
        "share": round(matched / total, 4) if total else None, "matched_by_level": by_level, "warnings": warnings}
    if kind == "noise" and errors and not allow_error:
        payload["status"] = "needs_allow_error_level"
        payload["next"] = "nessun token: la regola tocca ERROR/WARN. Se l'utente li ritiene innocui, rifare con --allow-error-level"
    else:
        pending = _load_pending(root, cfg)
        expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=cfg["pending_ttl_minutes"])
        pending[token] = expires.isoformat()
        _save_pending(root, cfg, pending)
        payload["token"] = token
        payload["token_expires_at"] = expires.isoformat()
        payload["next"] = ("mostrare all'utente regola, impatto e avvisi; solo dopo la sua conferma esplicita rieseguire "
                           f"lo stesso comando con --reason '<motivo>' --confirm {token} (nessuna connessione)")
    emit_json(payload)


def cmd_fields(ctx, args) -> None:
    out, client, target = ctx["out"], ctx.get("client"), ctx["target"]
    caps = client.query(target["index"], "_field_caps", {}, f"fields={args.pattern}")["fields"]
    header(out, target, ctx["protected"])
    for name, types in sorted(caps.items()):
        if all(t in ("object", "nested") for t in types):
            continue
        described = ", ".join(f"{t}{' (aggregabile)' if v.get('aggregatable') else ''}" for t, v in types.items())
        out(f"{name}: {described}")


def cmd_namespaces(ctx, args) -> None:
    """Namespace presenti nell'index (solo conteggi): serve a confermare o scoprire i target di un cluster."""
    out, client = ctx["out"], ctx["client"]
    for target in ctx["targets"]:
        f = fields_of(target)
        body = {"size": 0, "track_total_hits": True,
                "query": {"range": {f["timestamp"]: {"gte": time_bound(args.since), "lte": time_bound(args.until),
                                                     "time_zone": target.get("timezone", "UTC")}}},
                "aggs": {"by": {"terms": {"field": aggregatable(client, target, f["namespace"]), "size": args.top}}}}
        result = client.query(target["index"], "_search", body)
        out(f"# {target['env']} cluster={target['cluster_id']} index={target['index']} "
            f"finestra {args.since} -> {args.until}: {result['hits']['total']['value']} righe")
        for bucket in result["aggregations"]["by"]["buckets"]:
            mark = "  <- registrato" if bucket["key"] in ctx["registered"][target["env"]] else ""
            out(f"{bucket['doc_count']:>10}  {bucket['key']}{mark}")


def cmd_check(ctx) -> dict:
    client, target = ctx["client"], ctx["target"]
    f, tz = fields_of(target), target.get("timezone", "UTC")
    body = {"size": 0, "track_total_hits": True,
            "query": {"match_phrase": {f["namespace"]: target["namespace"]}},
            "aggs": {"last": {"max": {"field": f["timestamp"]}},
                     "last_hour": {"filter": {"range": {f["timestamp"]: {"gte": "now-1h"}}}}}}
    result = client.query(target["index"], "_search", body)
    last = result["aggregations"]["last"].get("value")
    total = result["hits"]["total"]["value"]
    last_hour = result["aggregations"]["last_hour"]["doc_count"]
    payload = {"ok": True, "env": target["env"], "app": target["app"], "cluster": target["cluster_id"],
               "index": target["index"], "namespace": target["namespace"],
               "credential_source": ctx["credential_source"], "total_rows": total, "rows_last_hour": last_hour,
               "last_event": local_time(dt.datetime.fromtimestamp(last / 1000, dt.timezone.utc).isoformat(), tz)
               if last else None,
               "unverified": target["unverified"], "data_from": target["data_from"]}
    if not total:
        payload["warning"] = "nessuna riga per questo namespace nell'index: verificare namespace/index con `namespaces`"
    return payload


# --- CLI -----------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lettura in sola lettura dei log applicativi su OpenSearch",
                                     epilog="Prima di usarlo: log_access.py guide")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("env", help="ambiente del registro (es. prod, staging)")
    common.add_argument("app", help="app del registro (es. checkout, billing)")
    common.add_argument("--out", metavar="PATH", help="scrive l'output su file (rifiutato in raw/ e wiki/ per gli ambienti protetti)")
    window = argparse.ArgumentParser(add_help=False)
    window.add_argument("--since", help="inizio: 15m, 2h, 3d, oppure ISO (default da config, 1h)")
    window.add_argument("--until", default="now", help="fine: come --since (default now)")
    window.add_argument("--around", help="orario dell'evento (ISO, fuso configurato): finestra simmetrica, al posto di --since/--until")
    window.add_argument("--window", default="15m", help="mezza ampiezza di --around (default 15m)")
    filters = argparse.ArgumentParser(add_help=False, parents=[window])
    filters.add_argument("--container", action="append", help="campo container (fields.container; ripetibile: OR)")
    filters.add_argument("--level", action="append", help="campo livello (fields.level): ERROR, WARN, INFO, DEBUG (ripetibile: OR)")
    filters.add_argument("--trace", action="append", help="campo trace (fields.trace; ripetibile: OR)")
    filters.add_argument("--message", action="append", help="frase contenuta nel message (ripetibile: AND)")
    filters.add_argument("--exclude", action="append", help="frase da escludere dal message (ripetibile)")
    filters.add_argument("--filter", action="append", help="campo=valore, match di frase (ripetibile: AND)")
    filters.add_argument("--query", help="query Lucene (query_string), campo di default message")
    filters.add_argument("--no-mask", action="store_true",
                         help="dati personali in chiaro (consigliato il contrario, soprattutto su prod); segreti sempre mascherati")
    filters.add_argument("--with-noise", action="store_true", help="include le righe escluse dal profilo di rumore")
    filters.add_argument("--show-handled", action="store_true",
                         help="include nell'elenco gli errori gestiti (di default nascosti e riassunti in una riga)")
    filters.add_argument("--dry-run", action="store_true", help="stampa la query senza eseguirla (nessuna connessione)")

    commands = parser.add_subparsers(dest="command", required=True)
    targets = commands.add_parser("targets", help="registro e stato credenziali")
    targets.add_argument("--env")
    check = commands.add_parser("check", parents=[common], help="login, ultimo evento, conteggio ultima ora")
    check.set_defaults(dry_run=False)
    search = commands.add_parser("search", parents=[common, filters], help="righe di log")
    search.add_argument("--size", type=int, help="righe da leggere (default da config, max da config)")
    search.add_argument("--max-chars", type=int, help="tronca il message (0 = intero)")
    search.add_argument("--asc", action="store_true", help="dalla piu vecchia (default dalla piu recente)")
    search.add_argument("--fields", action="append", help="campi in piu da mostrare (ripetibile)")
    search.add_argument("--raw", action="store_true", help="documento intero (mascherato)")
    search.add_argument("--no-collapse", action="store_true", help="non compattare le righe ripetute")
    search.add_argument("--full-stack", action="store_true", help="stack trace interi")
    search.add_argument("--max-stack", type=int, help="tronca lo stack trace (stack_trace/err.stack); 0 = non mostrarlo")
    count = commands.add_parser("count", parents=[common, filters], help="conteggi e raggruppamenti")
    count.add_argument("--by", help="campo per cui raggruppare (es. il campo container del target)")
    count.add_argument("--top", type=int, default=20)
    count.add_argument("--histogram", help="distribuzione nel tempo, es. 10m, 1h")
    noise = commands.add_parser("noise", parents=[common, filters], help="valuta il rumore e propone regole")
    noise.add_argument("--sample", type=int, default=2000, help="righe del campione (max da config)")
    noise_add = commands.add_parser("noise-add", parents=[common, window],
                                    help="anteprima e, con conferma, aggiunta di una regola di rumore al profilo")
    noise_add.add_argument("--container", help="condizione: campo container esatto")
    noise_add.add_argument("--logger", help="condizione: campo logger esatto")
    noise_add.add_argument("--level", help="condizione: campo livello esatto")
    noise_add.add_argument("--message", help="condizione: frase nel message")
    noise_add.add_argument("--name", help="nome della regola (default ricavato dalle condizioni)")
    noise_add.add_argument("--reason", help="perche e' rumore (obbligatorio con --confirm)")
    noise_add.add_argument("--allow-error-level", action="store_true",
                           help="consente una regola che toglie righe ERROR/WARN (solo se innocue)")
    noise_add.add_argument("--confirm", metavar="TOKEN", help="token dell'anteprima: scrive la regola nel profilo")
    noise_add.set_defaults(dry_run=False)
    handled_add = commands.add_parser("handled-add", parents=[common, window],
                                      help="anteprima e, con conferma, registrazione di un errore gestito (atteso)")
    for flag, help_text in (("--container", "condizione: campo container esatto"),
                            ("--logger", "condizione: campo logger esatto"), ("--level", "condizione: campo livello esatto"),
                            ("--message", "condizione: frase nel message"),
                            ("--name", "nome della regola (default ricavato dalle condizioni)"),
                            ("--reason", "perche e' un errore atteso (obbligatorio con --confirm)")):
        handled_add.add_argument(flag, help=help_text)
    handled_add.add_argument("--confirm", metavar="TOKEN", help="token dell'anteprima: scrive la regola nel profilo")
    handled_add.set_defaults(dry_run=False)
    fields = commands.add_parser("fields", parents=[common], help="campi dell'index, con tipo e aggregabilita'")
    fields.add_argument("pattern", nargs="?", default="*", help="es. kubernetes.*, *trace*")
    fields.set_defaults(dry_run=False)
    namespaces = commands.add_parser("namespaces", parents=[window], help="namespace presenti nell'index")
    namespaces.add_argument("env")
    namespaces.add_argument("app", nargs="?")
    namespaces.add_argument("--top", type=int, default=30)
    namespaces.add_argument("--out", metavar="PATH", help="scrive l'output su file (rifiutato in raw/ e wiki/ per gli ambienti protetti)")
    namespaces.set_defaults(dry_run=False)
    guide = commands.add_parser("guide", help="regole d'uso e regole di rumore attive")
    guide.add_argument("env", nargs="?")
    guide.add_argument("app", nargs="?")
    guide.add_argument("--out", metavar="PATH", help="scrive l'output su file")
    return parser


def apply_defaults(args, cfg: dict[str, Any]) -> None:
    if getattr(args, "around", None):
        if args.since:
            raise ClientError(EXIT_USAGE, "bad_window", "--around esclude --since")
        args.since, args.until = around_window(args.around, args.window, cfg["timezone"])
    elif hasattr(args, "since"):
        args.since = args.since or cfg["default_since"]
    for name, key in (("size", "default_size"), ("max_chars", "max_chars"), ("max_stack", "max_stack")):
        if hasattr(args, name) and getattr(args, name) is None:
            setattr(args, name, cfg[key])


def targets_report(ctx_cfg, registry, env_values_for, only_env) -> dict:
    """env_values_for(env_file) -> variabili del file indicato (cache a carico del chiamante)."""
    rows = []
    for env, env_def in registry["environments"].items():
        if only_env and env != only_env:
            continue
        for app, definition in (env_def.get("apps") or {}).items():
            cluster = registry["clusters"].get(definition.get("cluster"), {})
            defaults = registry.get("defaults") or {}
            env_file = next((src[k] for src in (definition, cluster, defaults) for k in ("env_file",) if src.get(k)),
                            ctx_cfg["env_file"])
            ready = log_client.credentials_ready(cluster, env_values_for(env_file)) if cluster else None
            rows.append({"env": env, "label": env_def.get("label", env), "app": app,
                         "cluster": definition.get("cluster"), "base_url": cluster.get("base_url"),
                         "index": definition.get("index"), "namespace": definition.get("namespace"),
                         "protected": env in ctx_cfg["protected_envs"],
                         "unverified": bool(definition.get("unverified")), "note": definition.get("note"),
                         "data_from": definition.get("data_from"), "noise_profile": definition.get("noise"),
                         "env_file": env_file, "credentials_ready": ready is not None, "credential_source": ready,
                         "credential_candidates": [list(p) for p in cluster.get("credentials") or []]})
    if only_env and not rows:
        raise ClientError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {only_env}",
                          available=sorted(registry["environments"]))
    return {"ok": True, "targets": rows}


def check_out_path(args, cfg: dict[str, Any], root: Path, protected: bool) -> Path | None:
    """--out: per gli ambienti protetti il file non puo' stare nelle cartelle di `protected_out_forbidden_dirs`
    (default raw, wiki, deliverables, management). Controllo nel codice, prima di ogni connessione, sul percorso reale
    (link simbolici e `..` compresi)."""
    raw = getattr(args, "out", None)
    if not raw:
        return None
    path = Path(raw)
    path = path if path.is_absolute() else Path.cwd() / path
    resolved = path.resolve()
    if protected:
        for name in cfg["protected_out_forbidden_dirs"]:
            folder = (root / name).resolve()
            if resolved == folder or folder in resolved.parents:
                raise ClientError(EXIT_USAGE, "protected_out_forbidden",
                                  f"--out dentro {name}/ e' vietato per l'ambiente protetto {args.env}: "
                                  "l'output di un ambiente protetto non si copia nel repository di conoscenza",
                                  forbidden_dirs=list(cfg["protected_out_forbidden_dirs"]))
    return resolved


def run(args, root: Path) -> int:
    cfg = load_config(root)
    if not cfg["enabled"]:
        raise ClientError(EXIT_USAGE, "disabled", "capability spenta: log_access.enabled e' false in factory.config.yaml")
    configure_masking(cfg)
    out_path = check_out_path(args, cfg, root, getattr(args, "env", None) in cfg["protected_envs"])
    if out_path is None:
        return _run(args, root, cfg)
    import contextlib
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        return _run(args, root, cfg)


def _run(args, root: Path, cfg: dict[str, Any]) -> int:
    registry = load_registry(root, cfg)
    env_cache: dict[str, dict[str, str]] = {}

    def env_values_for(env_file: str) -> dict[str, str]:
        if env_file not in env_cache:
            env_cache[env_file] = load_env_values(root, env_file)
        return env_cache[env_file]

    out = Printer(cfg["max_output_chars"], cfg["mask_personal_data"] and not getattr(args, "no_mask", False))

    if args.command == "targets":
        emit_json(targets_report(cfg, registry, env_values_for, args.env))
        return EXIT_OK
    if args.command == "guide":
        out(GUIDE)
        if args.env and args.app:
            target = resolve_target(registry, args.env, args.app, cfg)
            rules = noise_rules(root, cfg, target, False)
            out(f"Regole di rumore attive per {args.env}/{args.app}: {len(rules)}")
            for rule in rules:
                out(f"  - {rule['name']}: {rule.get('reason', '')}")
            handled = handled_rules(root, cfg, target)
            out(f"Errori gestiti registrati per {args.env}/{args.app}: {len(handled)}")
            for rule in handled:
                out(f"  - {rule['name']}: {rule.get('reason', '')}")
        return EXIT_OK

    apply_defaults(args, cfg)
    if args.command == "namespaces":
        apps = [args.app] if args.app else None
        if args.env not in registry["environments"]:
            raise ClientError(EXIT_USAGE, "unknown_env", f"ambiente sconosciuto: {args.env}",
                              available=sorted(registry["environments"]))
        env_apps = registry["environments"][args.env].get("apps") or {}
        names = apps or sorted(env_apps)
        resolved = [resolve_target(registry, args.env, name, cfg) for name in names]
        seen, targets = set(), []
        for target in resolved:                 # una sola interrogazione per coppia (cluster, index)
            if (target["cluster_id"], target["index"]) not in seen:
                seen.add((target["cluster_id"], target["index"]))
                targets.append(target)
        registered = {args.env: {t["namespace"] for t in resolved}}
        ctx: dict[str, Any] = {"cfg": cfg, "out": out, "targets": targets, "registered": registered,
                               "protected": args.env in cfg["protected_envs"]}
        clusters = {t["cluster_id"]: t for t in targets}
    else:
        target = resolve_target(registry, args.env, args.app, cfg)
        ctx = {"cfg": cfg, "out": out, "target": target, "protected": args.env in cfg["protected_envs"],
               "rules": noise_rules(root, cfg, target, getattr(args, "with_noise", False)),
               "handled": handled_rules(root, cfg, target), "root": root, "registry": registry}
        clusters = {target["cluster_id"]: target}

    if args.command in ("noise-add", "handled-add") and args.confirm:   # la scrittura non tocca il cluster
        {"noise-add": cmd_noise_add, "handled-add": cmd_handled_add}[args.command](ctx, args)
        return EXIT_OK
    if getattr(args, "dry_run", False):                 # nessuna connessione: solo la query
        {"search": cmd_search, "count": cmd_count, "noise": cmd_noise}[args.command](ctx, args)
        return EXIT_OK

    clients = {}
    for cluster_id, member in clusters.items():
        cluster = member["cluster"]
        creds = log_client.resolve_credentials(cluster, env_values_for(member["env_file"]))
        if creds is None:
            raise ClientError(EXIT_USAGE, "credentials_missing",
                              f"credenziali assenti per il cluster {cluster_id}",
                              expected_vars=[list(p) for p in cluster.get("credentials") or []])
        ctx["credential_source"] = creds["source"]
        clients[cluster_id] = open_client(cluster, creds, root, cfg)
    if args.command == "namespaces":
        for target in ctx["targets"]:
            ctx["client"] = clients[target["cluster_id"]]
            cmd_namespaces({**ctx, "targets": [target]}, args)
    else:
        ctx["client"] = clients[ctx["target"]["cluster_id"]]
        if args.command == "check":
            emit_json(cmd_check(ctx))
        else:
            {"search": cmd_search, "count": cmd_count, "noise": cmd_noise, "fields": cmd_fields,
             "noise-add": cmd_noise_add, "handled-add": cmd_handled_add}[args.command](ctx, args)
    return EXIT_OK


def open_client(cluster, creds, root, cfg):
    """Punto di innesto per i test: crea il client verso il cluster."""
    return log_client.open_client(cluster, creds, root, cfg["timeout_s"], cfg["tls_attempts"])


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = root or Path(__file__).resolve().parents[2]
    args = build_parser().parse_args(argv)
    try:
        return run(args, root)
    except ClientError as error:
        emit_json(error.payload)
        print(f"log_access: {error.payload['error']}", file=sys.stderr)
        return error.code


if __name__ == "__main__":
    sys.exit(main())
