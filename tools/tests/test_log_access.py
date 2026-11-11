"""
Test di tools/logs/log_access.py (+ log_mask.py, log_client.py).

Nessun cluster reale: `log_access.open_client` e' sostituita da un client finto che registra le
chiamate e risponde con documenti di prova. La factory di prova (config, registro, rumore, .env)
vive in tmp_path. Compatibile con Python 3.9+.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOGS = _REPO_ROOT / "tools" / "logs"
sys.path.insert(0, str(_LOGS))


# Token finto composto a runtime: nessun segreto letterale nel sorgente (scanner di segreti).
_FAKE_JWT = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiIxMjM0NTYifQ", "abcdefghij"])

def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _LOGS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mask_mod = _load("log_mask")
client_mod = _load("log_client")
la = _load("log_access")

CONFIG = """
log_access:
  enabled: true
  env_file: .env.test
  timezone: Europe/Rome
  mask_patterns: [it-codice-fiscale, it-partita-iva]
  app_package: com.example
  protected_envs: [prod]
  max_output_chars: 30000
"""

REGISTRY = """
version: 1
clusters:
  c1:
    base_url: https://logs.one.local
    credentials:
      - [ONE_USER, ONE_PWD]
      - [FALLBACK_USER, FALLBACK_PWD]
  c2:
    base_url: https://logs.two.local
    auth: basic
    credentials:
      - [TWO_USER, TWO_PWD]
environments:
  prod:
    label: Produzione
    apps:
      alpha: {cluster: c1, index: "idx*", namespace: alpha-prod, noise: alpha, data_from: "2026-07-07"}
      beta:  {cluster: c1, index: "idx*", namespace: beta-prod, unverified: true, note: da confermare}
  val:
    label: Validazione
    apps:
      alpha: {cluster: c2, index: idx-val, namespace: alpha-val, noise: alpha}
"""

NOISE = {"rules": [{"name": "health", "container": "gateway", "message": "GET /health", "reason": "probe"}]}

ENV = "ONE_USER=me\nONE_" + "PWD='" + "p#" + "ss'\n"


def make_root(tmp_path: Path, config: str = CONFIG, env: str = ENV, registry: str = REGISTRY) -> Path:
    root = tmp_path / "factory"
    (root / "tools" / "logs" / "noise").mkdir(parents=True, exist_ok=True)
    (root / "factory.config.yaml").write_text(config, encoding="utf-8")
    (root / "tools" / "logs" / "log-targets.yaml").write_text(registry, encoding="utf-8")
    noise = root / "tools" / "logs" / "noise" / "alpha.json"
    if not noise.exists():                      # le chiamate successive di un test non azzerano le regole aggiunte
        noise.write_text(json.dumps(NOISE), encoding="utf-8")
    (root / ".env.test").write_text(env, encoding="utf-8")
    return root


class FakeClient:
    def __init__(self, responses=None, error: Exception | None = None):
        self.calls: list[tuple[str, str, dict, str]] = []
        self.responses = list(responses or [])
        self.error = error

    def query(self, index, operation, body, params=""):
        self.calls.append((index, operation, body, params))
        if self.error:
            raise self.error
        return self.responses.pop(0) if self.responses else {"hits": {"total": {"value": 0}, "hits": []}}


@pytest.fixture(autouse=True)
def _reset_masking():
    """log_mask tiene la configurazione in memoria: ogni test riparte dai default (nessun pattern opt-in)."""
    mask_mod.configure()
    yield
    mask_mod.configure()


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    """Esegue main() con un client finto; ritorna (exit, stdout, client)."""
    def _run(argv, responses=None, error=None, config=CONFIG, env=ENV):
        root = make_root(tmp_path, config=config, env=env)
        fake = FakeClient(responses, error)
        monkeypatch.setattr(la, "open_client", lambda cluster, creds, root_, cfg: fake)
        monkeypatch.delenv("OPENSEARCH_USER", raising=False)
        code = la.main(argv, root=root)
        return code, capsys.readouterr().out, fake
    return _run


def hit(**source):
    base = {"@timestamp": "2026-11-05T08:00:00.123Z", "kubernetes.container_name": "svc",
            "kubernetes.pod_name": "svc-abc-123", "logLevel": "ERROR", "loggerName": "com.example.Foo",
            "dt.trace_id": "b4857c0f1ff7135fda399b8f0c40fdf8", "message": "boom"}
    base.update(source)
    return {"_source": base}


def result(hits, total=None):
    return {"hits": {"total": {"value": total if total is not None else len(hits)}, "hits": hits}}


# ---------------------------------------------------------------------------
# mascheramento
# ---------------------------------------------------------------------------

def test_mask_cf_email_and_stable_hash():
    mask_mod.configure(["it-codice-fiscale"])
    text = "utente RSSMRA80A01H501U mail mario.rossi@example.it di nuovo rssmra80a01h501u"
    out = mask_mod.mask(text)
    assert "RSSMRA80A01H501U" not in out.upper()
    assert "mario.rossi@example.it" not in out
    tags = [t for t in out.split() if t.startswith("<CF#")]
    assert len(tags) == 2 and tags[0] == tags[1]          # stesso soggetto, stesso hash nella stessa esecuzione


def test_mask_piva_only_with_valid_check_digit():
    mask_mod.configure(["it-partita-iva"])
    assert "<PIVA#" in mask_mod.mask("piva 12345678903")             # cifra di controllo valida
    assert mask_mod.mask("numero 12345678900") == "numero 12345678900"   # 11 cifre qualsiasi: non toccate


def test_mask_secrets_and_tokens():
    jwt = _FAKE_JWT
    out = mask_mod.mask(f"Authorization: Bearer {jwt} password=hunter2 client_secret: abc123xyz")
    assert jwt not in out and "hunter2" not in out and "abc123xyz" not in out
    assert "<SECRET>" in out
    ado = "a" * 25 + "2" + "b" * 26                                    # 52 caratteri base32 con una cifra
    assert "<TOKEN>" in mask_mod.mask(f"token ado {ado}")
    assert "<CHIAVE-PRIVATA>" in mask_mod.mask("-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----")
    assert "<TOKEN>" in mask_mod.mask("ghp_" + "A1" * 15)


def test_mask_person_keys_and_name_only_with_surname():
    out = mask_mod.mask('{"firstName":"Mario","lastName":"Rossi"}')
    assert "Mario" not in out and "Rossi" not in out
    assert mask_mod.mask('{"name":"checkout-service"}') == '{"name":"checkout-service"}'
    assert "Mario" not in mask_mod.mask('{"name":"Mario","surname":"Rossi"}')


def test_mask_leaves_trace_ids_and_uuid_alone():
    text = "trace b4857c0f1ff7135fda399b8f0c40fdf8 id 123e4567-e89b-12d3-a456-426614174000"
    assert mask_mod.mask(text) == text


def test_template_strips_personal_data_before_numbers():
    mask_mod.configure(["it-codice-fiscale"])
    schema = mask_mod.template("login RSSMRA80A01H501U da 10.0.0.1 id 123e4567-e89b-12d3-a456-426614174000")
    assert "RSSMRA" not in schema and "<cf>" in schema and "<id>" in schema


def test_trim_stack_keeps_exception_first_frame_and_app_frames():
    frames = [f"\tat org.lib.Cls{i}.run(Cls.java:{i})" for i in range(8)]
    frames.insert(3, "\tat com.example.Service.call(Service.java:10)")
    message = "java.lang.IllegalStateException: x\n" + "\n".join(frames)
    out = mask_mod.trim_stack(message, "com.example")
    assert "IllegalStateException" in out and "com.example.Service.call" in out
    assert "frame omessi" in out and len(out) < len(message)
    no_pkg = mask_mod.trim_stack(message)                      # app_package vuoto di default: solo il primo frame
    assert "com.example.Service.call" not in no_pkg and "IllegalStateException" in no_pkg
    short = "Ex: y\n\tat a.B.c(B.java:1)"
    assert mask_mod.trim_stack(short) == short


# ---------------------------------------------------------------------------
# tempo e query
# ---------------------------------------------------------------------------

def test_time_bound_relative_iso_and_invalid():
    assert la.time_bound("2h") == "now-2h"
    assert la.time_bound("now") == "now"
    assert la.time_bound("2026-10-22T09:00") == "2026-10-22T09:00"
    with pytest.raises(client_mod.ClientError) as err:
        la.time_bound("ieri")
    assert err.value.code == 1


def test_around_window_naive_uses_the_configured_timezone():
    # 11:00 a Europe/Rome a novembre (CET, UTC+1) = 10:00Z; finestra 15m
    since, until = la.around_window("2026-11-05T11:00", "15m", "Europe/Rome")
    assert (since, until) == ("2026-11-05T09:45:00Z", "2026-11-05T10:15:00Z")
    assert la.around_window("2026-11-05T11:00", "15m") == ("2026-11-05T10:45:00Z", "2026-11-05T11:15:00Z")   # default UTC
    since, until = la.around_window("2026-11-05T11:00:00+00:00", "1h")
    assert (since, until) == ("2026-11-05T10:00:00Z", "2026-11-05T12:00:00Z")
    with pytest.raises(client_mod.ClientError):
        la.around_window("2026-11-05T11:00", "boh")
    with pytest.raises(client_mod.ClientError) as err:
        la.zone("Nowhere/Land")
    assert err.value.payload["error"] == "tzdata_missing"


def test_build_query_filters_and_namespace():
    args = la.build_parser().parse_args(
        ["search", "prod", "alpha", "--since", "2h", "--level", "ERROR", "--level", "WARN",
         "--container", "svc", "--message", "timeout", "--exclude", "health", "--filter", "url=/x"])
    target = {"namespace": "alpha-prod"}
    query = la.build_query(args, target)
    must = query["bool"]["filter"]
    assert {"match_phrase": {la.NAMESPACE: "alpha-prod"}} in must
    assert {"match_phrase": {la.MESSAGE: "timeout"}} in must
    assert {"match_phrase": {"url": "/x"}} in must
    level = next(c for c in must if "bool" in c and any(la.LEVEL in s["match_phrase"] for s in c["bool"]["should"]))
    assert len(level["bool"]["should"]) == 2
    assert query["bool"]["must_not"] == [{"match_phrase": {la.MESSAGE: "health"}}]
    bad = la.build_parser().parse_args(["search", "prod", "alpha", "--since", "1h", "--filter", "senzauguale"])
    with pytest.raises(client_mod.ClientError):
        la.build_query(bad, target)


def test_apply_noise_excludes_and_counts_rules():
    body: dict = {}
    la.apply_noise(body, {"bool": {}}, NOISE["rules"])
    assert body["query"]["bool"]["must_not"][0]["bool"]["filter"][0] == {"term": {f"{la.CONTAINER}.raw": "gateway"}}
    assert "health" in body["aggs"]["noise"]["aggs"]["rules"]["filters"]["filters"]
    plain: dict = {}
    la.apply_noise(plain, {"bool": {}}, [])
    assert plain == {"query": {"bool": {}}}


# ---------------------------------------------------------------------------
# registro, credenziali, client
# ---------------------------------------------------------------------------

def test_targets_reports_status_without_secrets(run):
    code, out, fake = run(["targets"])
    data = json.loads(out)
    assert code == 0 and fake.calls == []                   # nessuna connessione
    rows = {(r["env"], r["app"]): r for r in data["targets"]}
    assert rows[("prod", "alpha")]["credentials_ready"] is True
    assert rows[("prod", "alpha")]["protected"] is True and rows[("val", "alpha")]["protected"] is False
    assert rows[("prod", "beta")]["unverified"] is True
    assert rows[("val", "alpha")]["credentials_ready"] is False       # cluster c2: variabili assenti
    assert "p#ss" not in out and "me" not in out.split("credential_source")[0].replace("namespace", "")
    assert rows[("prod", "alpha")]["env_file"] == ".env.test"


def test_targets_unknown_env_is_usage_error(run):
    code, out, _ = run(["targets", "--env", "nope"])
    assert code == 1 and json.loads(out)["error"] == "unknown_env"


def test_resolve_target_errors_list_alternatives(run):
    code, out, _ = run(["count", "prod", "gamma"])
    payload = json.loads(out)
    assert code == 1 and payload["error"] == "unknown_app" and payload["available"] == ["alpha", "beta"]


def test_credentials_missing_is_exit_1_with_expected_vars(run):
    code, out, fake = run(["count", "val", "alpha"])
    payload = json.loads(out)
    assert code == 1 and payload["error"] == "credentials_missing"
    assert payload["expected_vars"] == [["TWO_USER", "TWO_PWD"]] and fake.calls == []


def test_resolve_credentials_order_env_file_then_environ_only():
    cluster = {"credentials": [["A_U", "A_P"], ["B_U", "B_P"]]}
    assert client_mod.resolve_credentials(cluster, {"A_U": "u", "A_P": "p"}, {})["source"] == "env-file:A_U"
    assert client_mod.resolve_credentials(cluster, {}, {"B_U": "u", "B_P": "p"})["source"] == "environ:B_U"
    assert client_mod.resolve_credentials(cluster, {"A_U": "u"}, {}) is None      # coppia incompleta: nessun ripiego
    assert not hasattr(client_mod, "read_windows_credential")


def test_example_registry_has_no_windows_credential():
    import yaml as _yaml
    reg = _yaml.safe_load((_LOGS / "log-targets.example.yaml").read_text(encoding="utf-8"))
    assert all("windows_credential" not in c for c in reg["clusters"].values())


def test_username_strip_from_cuts_the_suffix_from_any_source():
    cluster = {"credentials": [["S_U", "S_P"]], "username_strip_from": ".corp"}
    got = client_mod.resolve_credentials(cluster, {"S_U": "jdoe.corp@example.com", "S_P": "pw"}, {})
    assert got["user"] == "jdoe" and got["password"] == "pw" and got["source"] == "env-file:S_U"
    got = client_mod.resolve_credentials(cluster, {}, {"S_U": "jdoe.corp@example.com", "S_P": "pw"})
    assert got["user"] == "jdoe"
    plain = client_mod.resolve_credentials({"credentials": [["S_U", "S_P"]]}, {"S_U": "a.corp", "S_P": "p"}, {})
    assert plain["user"] == "a.corp"                         # senza l'opzione lo username non si tocca


def test_disabled_capability_is_exit_1(run):
    code, out, fake = run(["targets"], config="log_access:\n  enabled: false\n")
    assert code == 1 and json.loads(out)["error"] == "disabled" and fake.calls == []


def test_client_rejects_non_read_operations_and_bad_index():
    client = client_mod.Client({"base_url": "https://x.local"}, session=None, timeout=1, attempts=1, cert_file=None)
    with pytest.raises(ValueError):
        client.query("idx*", "_delete_by_query", {})
    with pytest.raises(ValueError):
        client.query("idx*,other", "_search", {})
    with pytest.raises(ValueError):
        client.query("idx/../_all", "_search", {})


def test_client_timeout_and_connection_errors_map_to_exit_codes():
    pytest.importorskip("requests")  # dipendenza runtime di log_access, non della CI
    import requests

    class Session:
        def __init__(self, exc):
            self.exc = exc

        def post(self, *a, **k):
            raise self.exc

    cluster = {"base_url": "https://x.local"}
    timeout = client_mod.Client(cluster, Session(requests.exceptions.Timeout()), 1, 1, None)
    with pytest.raises(client_mod.ClientError) as err:
        timeout.query("idx", "_search", {})
    assert err.value.code == 6
    down = client_mod.Client(cluster, Session(requests.exceptions.ConnectionError("no route")), 1, 1, None)
    with pytest.raises(client_mod.ClientError) as err:
        down.query("idx", "_search", {})
    assert err.value.code == 2


def test_client_http_error_is_exit_5_and_basic_auth_skips_console_proxy():
    pytest.importorskip("requests")  # dipendenza runtime di log_access, non della CI
    class Resp:
        status_code = 500
        text = "boom"

    class Session:
        urls: list[str] = []

        def post(self, url, **k):
            self.urls.append(url)
            return Resp()

    session = Session()
    proxy = client_mod.Client({"base_url": "https://x.local"}, session, 1, 1, None)
    with pytest.raises(client_mod.ClientError) as err:
        proxy.query("idx*", "_search", {})
    assert err.value.code == 5 and "/api/console/proxy?path=idx%2A%2F_search&method=POST" in session.urls[0]
    direct = client_mod.Client({"base_url": "https://x.local", "auth": "basic"}, session, 1, 1, None)
    with pytest.raises(client_mod.ClientError):
        direct.query("idx*", "_search", {})
    assert session.urls[1] == "https://x.local/idx*/_search"


def test_open_client_missing_cert_is_actionable(tmp_path):
    pytest.importorskip("requests")  # dipendenza runtime di log_access, non della CI
    cluster = {"base_url": "https://x.local", "cert_file": "tools/logs/certs/none.pem"}
    with pytest.raises(client_mod.ClientError) as err:
        client_mod.open_client(cluster, {"user": "u", "password": "p"}, tmp_path)
    assert err.value.code == 2 and err.value.payload["error"] == "cert_missing"


# ---------------------------------------------------------------------------
# comandi
# ---------------------------------------------------------------------------

def test_search_dry_run_makes_no_connection_and_applies_noise(run):
    code, out, fake = run(["search", "prod", "alpha", "--dry-run", "--level", "ERROR"])
    body = json.loads(out)
    assert code == 0 and fake.calls == []
    assert body["size"] == 50 and "must_not" in body["query"]["bool"]          # rumore del profilo alpha
    code, out, _ = run(["search", "prod", "alpha", "--dry-run", "--with-noise"])
    assert "aggs" not in json.loads(out)


def test_search_masks_output_collapses_and_shows_stack(run):
    hits = [hit(message="login RSSMRA80A01H501U fallito"),
            hit(message="login RSSMRA80A01H501U fallito", **{"@timestamp": "2026-11-05T08:00:01.000Z"}),
            hit(message="altro", stack_trace="java.lang.RuntimeException: x\n\tat a.B.c(B.java:1)")]
    code, out, fake = run(["search", "prod", "alpha", "--since", "1h"], [result(hits, total=3)])
    assert code == 0
    assert "RSSMRA80A01H501U" not in out.upper() and "<CF#" in out
    assert "x2" in out and "stack: java.lang.RuntimeException" in out
    assert "# prod/alpha cluster=c1 index=idx* namespace=alpha-prod" in out
    assert "# PROTETTO" in out                                         # prod: avviso sul divieto di copia
    index, operation, body, _ = fake.calls[0]
    assert (index, operation) == ("idx*", "_search")
    assert "stack_trace" in body["_source"]


def test_unverified_target_is_flagged_in_header(run):
    _, out, _ = run(["search", "prod", "beta"], [result([])])
    assert "ATTENZIONE: target non verificato: da confermare" in out


def test_around_replaces_since_until_and_excludes_since(run):
    code, out, fake = run(["search", "val", "alpha", "--dry-run", "--with-noise", "--around", "2026-11-05T11:00"], env=ENV)
    rng = next(c for c in json.loads(out)["query"]["bool"]["filter"] if "range" in c)["range"][la.TIMESTAMP]
    assert (rng["gte"], rng["lte"]) == ("2026-11-05T09:45:00Z", "2026-11-05T10:15:00Z")
    code, out, _ = run(["search", "val", "alpha", "--dry-run", "--around", "2026-11-05T11:00", "--since", "2h"])
    assert code == 1 and json.loads(out)["error"] == "bad_window"


def test_count_by_resolves_aggregatable_field_and_prints_buckets(run):
    caps = {"fields": {"kubernetes.container_name": {"text": {"aggregatable": False}},
                       "kubernetes.container_name.raw": {"keyword": {"aggregatable": True}}}}
    agg = {"hits": {"total": {"value": 7}, "hits": []},
           "aggregations": {"by": {"buckets": [{"key": "svc", "doc_count": 5}], "sum_other_doc_count": 2},
                            "noise": {"rules": {"buckets": {"health": {"doc_count": 40}}}}}}
    code, out, fake = run(["count", "prod", "alpha", "--by", "kubernetes.container_name"], [caps, agg])
    assert code == 0 and "# totale: 7" in out and "svc" in out and "(altri)" in out
    assert "rumore escluso" in out and "health 40" in out
    assert fake.calls[1][2]["aggs"]["by"]["terms"]["field"] == "kubernetes.container_name.raw"


def test_cluster_error_is_exit_5_json_masked(run):
    error = client_mod.ClientError(5, "query", "ricerca fallita: HTTP 400",
                                   detail="parse error near RSSMRA80A01H501U")
    code, out, _ = run(["search", "prod", "alpha"], error=error)
    assert code == 5 and "RSSMRA80A01H501U" not in out.upper()


def test_timeout_is_exit_6_and_connection_exit_2(run):
    code, out, _ = run(["search", "prod", "alpha"], error=client_mod.ClientError(6, "timeout", "lento"))
    assert code == 6 and json.loads(out)["error"] == "timeout"
    code, _, _ = run(["search", "prod", "alpha"], error=client_mod.ClientError(2, "connection", "VPN?"))
    assert code == 2


def test_output_is_capped_with_notice(run):
    hits = [hit(message=f"messaggio lungo numero {i} " + "x" * 700) for i in range(60)]
    config = CONFIG.replace("max_output_chars: 30000", "max_output_chars: 3000")
    code, out, _ = run(["search", "prod", "alpha", "--size", "60", "--no-collapse"], [result(hits)], config=config)
    assert code == 0 and "output troncato a 3000 caratteri" in out
    assert len(out) < 3600


def test_check_reports_last_event_and_warns_on_empty_namespace(run):
    ok = {"hits": {"total": {"value": 100}}, "aggregations": {
        "last": {"value": 1793865600000}, "last_hour": {"doc_count": 12}}}
    code, out, _ = run(["check", "prod", "alpha"], [ok])
    payload = json.loads(out)
    assert code == 0 and payload["rows_last_hour"] == 12 and payload["last_event"].startswith("2026-11-05")
    assert payload["credential_source"] == "env-file:ONE_USER" and payload["data_from"] == "2026-07-07"
    empty = {"hits": {"total": {"value": 0}}, "aggregations": {"last": {"value": None}, "last_hour": {"doc_count": 0}}}
    _, out, _ = run(["check", "prod", "alpha"], [empty])
    assert "warning" in json.loads(out) and json.loads(out)["last_event"] is None


def test_namespaces_marks_registered_and_queries_each_cluster_index_once(run):
    caps = {"fields": {"kubernetes.namespace_name": {"keyword": {"aggregatable": True}}}}
    agg = {"hits": {"total": {"value": 9}}, "aggregations": {"by": {"buckets": [
        {"key": "alpha-prod", "doc_count": 6}, {"key": "gamma-prod", "doc_count": 3}]}}}
    code, out, fake = run(["namespaces", "prod"], [caps, agg])
    assert code == 0 and "alpha-prod  <- registrato" in out and "gamma-prod\n" in out + "\n"
    searches = [c for c in fake.calls if c[1] == "_search"]
    assert len(searches) == 1                          # alpha e beta stanno sullo stesso (cluster, index)


def test_noise_proposes_candidates_without_writing_files(run, tmp_path):
    groups = {"hits": {"total": {"value": 100}, "hits": []}, "aggregations": {"container": {"buckets": [
        {"key": "svc", "logger": {"buckets": [{"key": "com.example.Chatty", "level": {"buckets": [
            {"key": "DEBUG", "doc_count": 60, "example": {"hits": {"hits": [{"_source": {"message": "Entering filter 42"}}]}}}]}}]}}]}}}
    sample = result([hit(message="Entering filter 42", loggerName="com.example.Chatty", logLevel="DEBUG")] * 5)
    root_noise = tmp_path / "factory" / "tools" / "logs" / "noise" / "alpha.json"
    code, out, _ = run(["noise", "prod", "alpha"], [groups, sample])
    assert code == 0 and "regole candidate" in out and '"container": "svc"' in out
    assert json.loads(root_noise.read_text(encoding="utf-8")) == NOISE      # le regole si aggiungono a mano


def test_guide_lists_active_noise_rules(run):
    code, out, fake = run(["guide", "prod", "alpha"])
    assert code == 0 and "GUIDA RAPIDA" in out and "health: probe" in out and fake.calls == []


def test_example_registry_is_consistent_neutral_and_resolvable():
    import yaml

    text = (_LOGS / "log-targets.example.yaml").read_text(encoding="utf-8")
    assert "example.internal" in text
    registry = yaml.safe_load(text)
    for cluster in registry["clusters"].values():
        assert cluster["base_url"].startswith("https://") and cluster["credentials"]
    for env in registry["environments"].values():
        for app in env["apps"].values():
            assert app["cluster"] in registry["clusters"]
            assert client_mod.INDEX_RE.match(app["index"]) and app["namespace"]
            if app.get("noise"):
                assert (_LOGS / "noise" / f"{app['noise']}.example.json").is_file()
                assert (_LOGS / "handled" / f"{app['noise']}.example.json").is_file()
    for env_name, env_def in registry["environments"].items():     # ogni target dell'esempio si risolve senza errori
        for app_name in env_def["apps"]:
            la.resolve_target(registry, env_name, app_name, la.DEFAULTS)


# ---------------------------------------------------------------------------
# mascheramento opzionale
# ---------------------------------------------------------------------------

def test_mask_personal_off_keeps_personal_data_but_still_masks_secrets():
    jwt = _FAKE_JWT
    text = f"CF RSSMRA80A01H501U mail mario@example.it Bearer {jwt} password=hunter2"
    out = mask_mod.mask(text, personal=False)
    assert "RSSMRA80A01H501U" in out and "mario@example.it" in out
    assert jwt not in out and "hunter2" not in out


def test_no_mask_flag_shows_personal_data_and_warns_in_header(run):
    hits = [hit(message="login RSSMRA80A01H501U token Bearer " + _FAKE_JWT)]
    code, out, _ = run(["search", "prod", "alpha", "--no-mask"], [result(hits)])
    assert code == 0 and "RSSMRA80A01H501U" in out
    assert "eyJhbGci" not in out                                     # i segreti restano mascherati
    assert "mascheramento dei dati personali DISATTIVATO" in out and "consigliato rieseguire senza --no-mask" in out


def test_masking_is_default_and_no_warning_when_on(run):
    code, out, _ = run(["search", "prod", "alpha"], [result([hit(message="login RSSMRA80A01H501U")])])
    assert "RSSMRA80A01H501U" not in out.upper() and "DISATTIVATO" not in out


def test_config_can_flip_the_default_and_unprotected_env_has_no_prod_hint(run):
    config = CONFIG + "  mask_personal_data: false\n"
    code, out, _ = run(["search", "prod", "alpha"], [result([hit(message="login RSSMRA80A01H501U")])], config=config)
    assert "RSSMRA80A01H501U" in out and "DISATTIVATO" in out
    env = "TWO_USER=u\nTWO_PWD=p\n"
    code, out, _ = run(["search", "val", "alpha", "--no-mask"], [result([hit()])], env=env)
    assert "DISATTIVATO" in out and "consigliato rieseguire" not in out


# ---------------------------------------------------------------------------
# rumore: anteprima e conferma (noise-add)
# ---------------------------------------------------------------------------

def impact(total, matched, levels):
    return {"hits": {"total": {"value": total}}, "aggregations": {"matched": {
        "doc_count": matched, "by_level": {"buckets": [{"key": k, "doc_count": n} for k, n in levels.items()]}}}}


def noise_file(tmp_path):
    return tmp_path / "factory" / "tools" / "logs" / "noise" / "alpha.json"


def test_noise_add_dry_run_reports_impact_and_token_without_writing(run, tmp_path):
    code, out, fake = run(["noise-add", "prod", "alpha", "--container", "chatty", "--level", "DEBUG"],
                          [impact(1000, 400, {"DEBUG": 400})])
    payload = json.loads(out)
    assert code == 0 and payload["status"] == "dry_run" and payload["rows_matched"] == 400
    assert payload["share"] == 0.4 and payload["applies_to"] == ["prod/alpha", "val/alpha"]
    assert payload["token"] and payload["token_expires_at"] and "--confirm" in payload["next"]
    assert json.loads(noise_file(tmp_path).read_text(encoding="utf-8")) == NOISE          # nulla scritto
    body = fake.calls[0][2]
    assert body["aggs"]["matched"]["filter"]["bool"]["filter"][0] == {"term": {f"{la.CONTAINER}.raw": "chatty"}}


def test_noise_add_confirm_writes_rule_offline_and_is_idempotent(run, tmp_path):
    args = ["noise-add", "prod", "alpha", "--container", "chatty", "--level", "DEBUG"]
    _, out, _ = run(args, [impact(1000, 400, {"DEBUG": 400})])
    token = json.loads(out)["token"]
    code, out, fake = run(args + ["--reason", "un DEBUG per richiesta", "--confirm", token])
    payload = json.loads(out)
    assert code == 0 and payload["status"] == "added" and fake.calls == []                 # nessuna connessione
    rules = json.loads(noise_file(tmp_path).read_text(encoding="utf-8"))["rules"]
    added = rules[-1]
    assert added["container"] == "chatty" and added["level"] == "DEBUG" and added["reason"] == "un DEBUG per richiesta"
    assert added["name"] == "chatty-debug" and added["added"] and len(rules) == 2
    code, out, _ = run(args + ["--reason", "x", "--confirm", token])                       # stessa regola: nessun doppione
    assert code == 0 and json.loads(out)["status"] == "already_present"
    assert len(json.loads(noise_file(tmp_path).read_text(encoding="utf-8"))["rules"]) == 2


def test_noise_add_rejects_wrong_token_missing_reason_and_empty_rule(run, tmp_path):
    base = ["noise-add", "prod", "alpha", "--container", "chatty"]
    code, out, _ = run(base + ["--reason", "r", "--confirm", "000000000000"])
    assert code == 4 and json.loads(out)["error"] == "bad_token"
    forged = la.rule_token("alpha", {"container": "chatty"}, "chatty", False)    # hash giusto, ma nessuna anteprima
    code, out, _ = run(base + ["--reason", "r", "--confirm", forged])
    assert code == 4 and json.loads(out)["error"] == "bad_token"
    _, out, _ = run(base, [impact(100, 10, {"DEBUG": 10})])
    token = json.loads(out)["token"]
    assert token == forged
    code, out, _ = run(base + ["--confirm", token])
    assert code == 1 and json.loads(out)["error"] == "reason_missing"
    code, out, _ = run(["noise-add", "prod", "alpha"])
    assert code == 1 and json.loads(out)["error"] == "empty_rule"
    assert json.loads(noise_file(tmp_path).read_text(encoding="utf-8")) == NOISE


def test_noise_add_token_is_single_use_and_expires(run, tmp_path):
    base = ["noise-add", "prod", "alpha", "--container", "chatty", "--reason", "r"]
    _, out, _ = run(base[:-2], [impact(100, 10, {"DEBUG": 10})])
    token = json.loads(out)["token"]
    pending = tmp_path / "factory" / ".log-access-state" / "noise-pending.json"
    assert token in json.loads(pending.read_text(encoding="utf-8"))
    pending.write_text(json.dumps({token: "2000-01-01T00:00:00+00:00"}), encoding="utf-8")      # scaduto
    code, out, _ = run(base + ["--confirm", token])
    assert code == 4 and json.loads(out)["error"] == "bad_token"
    _, out, _ = run(base[:-2], [impact(100, 10, {"DEBUG": 10})])                                 # nuova anteprima
    code, out, _ = run(base + ["--confirm", json.loads(out)["token"]])
    assert code == 0 and json.loads(out)["status"] == "added"
    assert json.loads(pending.read_text(encoding="utf-8")) == {}                                 # consumato


def test_noise_add_error_levels_need_explicit_allow_and_token_binds_it(run):
    args = ["noise-add", "prod", "alpha", "--container", "svc", "--message", "timeout"]
    conditions = {"container": "svc", "message": "timeout"}
    code, out, _ = run(args, [impact(100, 30, {"ERROR": 20, "INFO": 10})])
    payload = json.loads(out)
    assert code == 0 and payload["status"] == "needs_allow_error_level" and "token" not in payload
    assert any("ERROR/WARN" in w for w in payload["warnings"])
    # senza anteprima con --allow-error-level non esiste alcun token valido, nemmeno calcolato a mano
    code, out, _ = run(args + ["--reason", "r", "--confirm", la.rule_token("alpha", conditions, "svc-timeout", False)])
    assert code == 4
    code, out, _ = run(args + ["--allow-error-level"], [impact(100, 30, {"ERROR": 20, "INFO": 10})])
    token = json.loads(out)["token"]
    assert token == la.rule_token("alpha", conditions, "svc-timeout", True)
    code, out, _ = run(args + ["--reason", "r", "--confirm", token])           # manca --allow-error-level: token diverso
    assert code == 4
    code, out, _ = run(args + ["--allow-error-level", "--reason", "innocuo", "--confirm", token])
    assert code == 0 and json.loads(out)["status"] == "added"


def test_noise_add_warns_on_broad_empty_and_shared_profile(run):
    code, out, _ = run(["noise-add", "prod", "alpha", "--level", "INFO"], [impact(100, 80, {"INFO": 80})])
    warnings = json.loads(out)["warnings"]
    assert any("80%" in w for w in warnings) and any("condiviso" in w for w in warnings)
    code, out, _ = run(["noise-add", "prod", "alpha", "--container", "nope"], [impact(100, 0, {})])
    assert any("nessuna riga" in w for w in json.loads(out)["warnings"])


def test_noise_add_without_profile_and_name_clash(run):
    code, out, _ = run(["noise-add", "prod", "beta", "--container", "x"])
    assert code == 1 and json.loads(out)["error"] == "no_profile"
    code, out, _ = run(["noise-add", "prod", "alpha", "--container", "other", "--name", "health"])
    assert code == 1 and json.loads(out)["error"] == "name_taken"


def test_noise_candidates_are_numbered_with_ready_noise_add_command(run):
    groups = {"hits": {"total": {"value": 100}, "hits": []}, "aggregations": {"container": {"buckets": [
        {"key": "svc", "logger": {"buckets": [{"key": "com.example.Chatty", "level": {"buckets": [
            {"key": "DEBUG", "doc_count": 60, "example": {"hits": {"hits": [{"_source": {"message": "Entering filter 42"}}]}}}]}}]}}]}}}
    sample = result([hit(message="Entering filter 42", loggerName="com.example.Chatty", logLevel="DEBUG")] * 5)
    _, out, _ = run(["noise", "prod", "alpha"], [groups, sample])
    assert "c1 " in out and "log_access.py noise-add prod alpha --container svc --logger com.example.Chatty --level DEBUG" in out


def test_count_by_numeric_field_does_not_send_a_text_placeholder(run):
    caps = {"fields": {"status-code": {"long": {"aggregatable": True}}}}
    agg = {"hits": {"total": {"value": 3}, "hits": []},
           "aggregations": {"by": {"buckets": [{"key": 200, "doc_count": 2}, {"key": 401, "doc_count": 1}]}}}
    code, out, fake = run(["count", "prod", "alpha", "--by", "status-code"], [caps, agg])
    assert code == 0 and "401" in out
    assert "missing" not in fake.calls[1][2]["aggs"]["by"]["terms"]          # un numerico non accetta "(assente)"


# ---------------------------------------------------------------------------
# errori gestiti: nascosti dall'elenco, riassunti in una riga, --show-handled
# ---------------------------------------------------------------------------

HANDLED = {"rules": [{"name": "tenant-ambiguo", "container": "svc", "message": "AmbiguousTenant",
                      "reason": "il frontend lo usa per la scelta del tenant"}]}


def put_handled(tmp_path, data=HANDLED):
    folder = tmp_path / "factory" / "tools" / "logs" / "handled"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "alpha.json").write_text(json.dumps(data), encoding="utf-8")


def handled_agg(count, first_ms=1793865600000, last_ms=1793869200000):
    return {"handled": {"rules": {"buckets": {"tenant-ambiguo": {
        "doc_count": count, "first": {"value": first_ms}, "last": {"value": last_ms}}}}}}


def test_handled_errors_are_hidden_from_the_list_and_summarized_in_one_line(run, tmp_path):
    put_handled(tmp_path)
    response = result([hit(message="altro errore")], total=1)
    response["aggregations"] = handled_agg(412)
    code, out, fake = run(["search", "prod", "alpha", "--level", "ERROR"], [response])
    assert code == 0
    body = fake.calls[0][2]
    excluded = body["query"]["bool"]["must_not"]
    assert any(c["bool"]["filter"][0] == {"term": {f"{la.CONTAINER}.raw": "svc"}} for c in excluded)   # fuori dall'elenco
    assert "global" in body["aggs"]["handled"]
    assert "# errori gestiti (attesi, non guasti; nascosti dall'elenco, --show-handled per vederli): tenant-ambiguo x412 (" in out
    assert "2026-11-0" in out and "altro errore" in out and "[gestito" not in out


def test_show_handled_keeps_them_in_the_list_with_a_label(run, tmp_path):
    put_handled(tmp_path)
    hits = [hit(message="Error during request: AmbiguousTenantException"), hit(message="altro errore")]
    response = result(hits, total=2)
    response["aggregations"] = {"handled": {"buckets": {"tenant-ambiguo": {"doc_count": 1}}}}
    code, out, fake = run(["search", "prod", "alpha", "--show-handled", "--with-noise"], [response])
    assert code == 0 and "[gestito: tenant-ambiguo]" in out and out.count("[gestito") == 1
    assert "inclusi nell'elenco" in out and "tenant-ambiguo x1" in out
    body = fake.calls[0][2]
    assert "must_not" not in body["query"]["bool"] or body["query"]["bool"]["must_not"] == []     # non esclusi
    assert body["aggs"]["handled"]["filters"]["filters"]["tenant-ambiguo"]["bool"]["filter"]


def test_count_reports_handled_summary_and_hides_them_by_default(run, tmp_path):
    put_handled(tmp_path)
    agg = {"hits": {"total": {"value": 10}, "hits": []}, "aggregations": handled_agg(7)}
    code, out, fake = run(["count", "prod", "alpha"], [agg])
    assert code == 0 and "tenant-ambiguo x7" in out and "# totale: 10" in out
    assert "handled" in fake.calls[0][2]["aggs"]


def test_handled_rule_matching_needs_all_conditions():
    rules = HANDLED["rules"]
    base = {"kubernetes.container_name": "svc", "message": "x AmbiguousTenantException y"}
    assert la.handled_name(base, rules) == "tenant-ambiguo"
    assert la.handled_name({**base, "kubernetes.container_name": "other"}, rules) is None
    assert la.handled_name({**base, "message": "altro"}, rules) is None
    assert la.handled_name({**base, "message": "AMBIGUOUSTENANT"}, rules) == "tenant-ambiguo"


def test_handled_add_previews_then_writes_to_the_handled_dir_not_the_noise_one(run, tmp_path):
    args = ["handled-add", "prod", "alpha", "--container", "svc", "--message", "Ambiguous"]
    code, out, _ = run(args, [impact(1000, 20, {"ERROR": 20})])
    payload = json.loads(out)
    assert code == 0 and payload["kind"] == "handled" and payload["status"] == "dry_run"
    assert "token" in payload                              # ERROR/WARN non servono --allow-error-level per un errore gestito
    token = payload["token"]
    code, out, fake = run(args + ["--reason", "atteso", "--confirm", token])
    assert code == 0 and json.loads(out)["status"] == "added" and fake.calls == []
    written = json.loads((tmp_path / "factory" / "tools" / "logs" / "handled" / "alpha.json").read_text(encoding="utf-8"))
    assert written["rules"][-1]["container"] == "svc" and written["rules"][-1]["reason"] == "atteso"
    assert json.loads(noise_file(tmp_path).read_text(encoding="utf-8")) == NOISE            # il rumore non e' toccato


def test_noise_token_cannot_confirm_a_handled_rule(run):
    noise_args = ["noise-add", "prod", "alpha", "--container", "svc", "--message", "Ambiguous"]
    _, out, _ = run(noise_args, [impact(100, 10, {"DEBUG": 10})])
    token = json.loads(out)["token"]
    code, out, _ = run(["handled-add", "prod", "alpha", "--container", "svc", "--message", "Ambiguous",
                        "--reason", "r", "--confirm", token])
    assert code == 4 and json.loads(out)["error"] == "bad_token"


def test_guide_lists_registered_handled_errors(run, tmp_path):
    put_handled(tmp_path)
    _, out, _ = run(["guide", "prod", "alpha"])
    assert "Errori gestiti registrati per prod/alpha: 1" in out and "tenant-ambiguo" in out


# ---------------------------------------------------------------------------
# parametrizzazione: mappa dei campi, env_file, app_package, pattern opt-in, fuso
# ---------------------------------------------------------------------------

FIELDS_REGISTRY = """
version: 1
defaults:
  fields: {trace: trace_id}
clusters:
  c1:
    base_url: https://logs.example.internal
    credentials: [[ONE_USER, ONE_PWD]]
    env_file: .env.cluster
    fields: {raw_suffix: ".keyword"}
environments:
  prod:
    apps:
      alpha:
        cluster: c1
        index: "idx*"
        namespace: alpha-prod
        noise: alpha
        fields: {level: level, container: k8s.container, namespace: k8s.ns, stack: [exception]}
      plain: {cluster: c1, index: "idx*", namespace: plain-prod, env_file: .env.app}
"""


def test_default_fields_are_the_documented_ones_and_registry_can_override_them(tmp_path):
    registry = {"clusters": {"c": {"base_url": "https://x"}}, "defaults": {},
                "environments": {"e": {"apps": {"a": {"cluster": "c", "index": "i", "namespace": "n"}}}}}
    target = la.resolve_target(registry, "e", "a", la.DEFAULTS)
    assert target["fields"] == la.DEFAULT_FIELDS and target["fields"]["level"] == "logLevel"
    assert target["env_file"] == ".env" and target["app_package"] == "" and target["timezone"] == "UTC"


def test_fields_precedence_defaults_then_cluster_then_app(run, tmp_path):
    import yaml
    registry = yaml.safe_load(FIELDS_REGISTRY)
    target = la.resolve_target({**registry, "defaults": registry["defaults"]}, "prod", "alpha", la.DEFAULTS)
    f = target["fields"]
    assert f["trace"] == "trace_id" and f["raw_suffix"] == ".keyword"          # defaults e cluster
    assert f["level"] == "level" and f["container"] == "k8s.container" and f["stack"] == ["exception"]   # app
    assert f["logger"] == "loggerName"                                         # non toccato: default documentato
    assert target["env_file"] == ".env.cluster"
    assert la.resolve_target(registry, "prod", "plain", la.DEFAULTS)["env_file"] == ".env.app"   # app > cluster


def test_registry_rejects_unknown_or_unsafe_fields():
    base = {"clusters": {"c": {"base_url": "https://x"}}, "defaults": {}}
    for fields in ({"nope": "x"}, {"level": "a b"}, {"level": 'x"y'}, {"raw_suffix": "raw"}):
        registry = {**base, "environments": {"e": {"apps": {"a": {"cluster": "c", "index": "i", "namespace": "n",
                                                                    "fields": fields}}}}}
        with pytest.raises(client_mod.ClientError) as err:
            la.resolve_target(registry, "e", "a", la.DEFAULTS)
        assert err.value.payload["error"] == "registry_invalid"


def test_custom_fields_drive_query_source_noise_and_count(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, registry=FIELDS_REGISTRY, env="ONE_USER=u\nONE_PWD=p\n")
    (root / ".env.cluster").write_text("ONE_USER=u\nONE_PWD=p\n", encoding="utf-8")
    fake = FakeClient([result([{"_source": {"@timestamp": "2026-11-05T08:00:00Z", "k8s": {"container": "svc"},
                                            "level": "ERROR", "trace_id": "t1", "message": "boom",
                                            "exception": "java.lang.X: y\n\tat a.B.c(B.java:1)"}}])])
    monkeypatch.setattr(la, "open_client", lambda cluster, creds, root_, cfg: fake)
    code = la.main(["search", "prod", "alpha", "--level", "ERROR", "--container", "svc", "--trace", "t1"], root=root)
    out = capsys.readouterr().out
    body = fake.calls[0][2]
    assert code == 0 and "stack: java.lang.X" in out and "| svc/" in out and "trace=t1" in out
    assert {"match_phrase": {"k8s.ns": "alpha-prod"}} in body["query"]["bool"]["filter"][0]["bool"]["filter"]
    assert "k8s.container" in body["_source"] and "exception" in body["_source"] and "logLevel" not in body["_source"]
    # il suffisso aggregabile del cluster si vede nelle regole di rumore (profilo alpha: container gateway)
    clause = body["query"]["bool"]["must_not"][0]["bool"]["filter"][0]
    assert clause == {"term": {"k8s.container.keyword": "gateway"}}


def test_env_file_is_per_cluster_and_has_no_customer_default(run, tmp_path):
    assert la.DEFAULTS["env_file"] == ".env"
    root = make_root(tmp_path, registry=FIELDS_REGISTRY, env="")          # il file del cfg e' vuoto
    (root / ".env.cluster").write_text("ONE_USER=u\nONE_PWD=p\n", encoding="utf-8")
    (root / ".env.app").write_text("", encoding="utf-8")
    code = la.main(["targets"], root=root)
    assert code == 0


def test_targets_report_uses_the_env_file_of_each_target(tmp_path, capsys):
    root = make_root(tmp_path, registry=FIELDS_REGISTRY, env="")
    (root / ".env.cluster").write_text("ONE_USER=u\nONE_PWD=p\n", encoding="utf-8")
    assert la.main(["targets"], root=root) == 0
    rows = {r["app"]: r for r in json.loads(capsys.readouterr().out)["targets"]}
    assert rows["alpha"]["credentials_ready"] is True and rows["alpha"]["env_file"] == ".env.cluster"
    assert rows["plain"]["credentials_ready"] is False and rows["plain"]["env_file"] == ".env.app"


def test_personal_patterns_are_opt_in_and_named(run):
    plain = CONFIG.replace("  mask_patterns: [it-codice-fiscale, it-partita-iva]\n", "")
    hits = [hit(message="login RSSMRA80A01H501U piva 12345678903 mail a.b@example.com")]
    _, out, _ = run(["search", "prod", "alpha"], [result(hits)], config=plain)
    assert "RSSMRA80A01H501U" in out and "12345678903" in out and "<EMAIL#" in out     # email sempre, CF/PIVA no
    _, out, _ = run(["search", "prod", "alpha"], [result(hits)])
    assert "RSSMRA80A01H501U" not in out.upper() and "<CF#" in out and "<PIVA#" in out
    only_cf = CONFIG.replace("[it-codice-fiscale, it-partita-iva]", "[it-codice-fiscale]")
    _, out, _ = run(["search", "prod", "alpha"], [result(hits)], config=only_cf)
    assert "<CF#" in out and "12345678903" in out


def test_custom_mask_pattern_and_person_keys_from_config(run):
    config = CONFIG + '  mask_custom_patterns: {ticket: "TCK-[0-9]{6}"}\n  mask_person_keys: [referente]\n'
    hits = [hit(message='aperto TCK-123456 referente="Anna Neri"')]
    _, out, _ = run(["search", "prod", "alpha"], [result(hits)], config=config)
    assert "TCK-123456" not in out and "<TICKET#" in out and "Anna Neri" not in out


def test_bad_mask_config_is_a_usage_error(run):
    for extra in ("  mask_patterns: [nope]\n", '  mask_custom_patterns: {Bad Name: "x"}\n',
                  '  mask_custom_patterns: {ok: "("}\n'):
        code, out, fake = run(["targets"], config=CONFIG + extra)
        assert code == 1 and json.loads(out)["error"] == "bad_config" and fake.calls == []


def test_timezone_defaults_to_utc_and_is_used_in_query_and_output(run):
    config = "log_access:\n  enabled: true\n  env_file: .env.test\n"
    _, out, _ = run(["search", "prod", "alpha", "--dry-run", "--with-noise"], config=config)
    assert next(c for c in json.loads(out)["query"]["bool"]["filter"] if "range" in c)["range"][la.TIMESTAMP]["time_zone"] == "UTC"
    _, out, _ = run(["search", "prod", "alpha", "--with-noise"], [result([hit()])], config=config)
    assert "2026-11-05 08:00:00.123" in out and "orari UTC" in out
    _, out, _ = run(["search", "prod", "alpha", "--with-noise"], [result([hit()])])
    assert "2026-11-05 09:00:00.123" in out and "orari Europe/Rome" in out


# ---------------------------------------------------------------------------
# --out: divieto di scrivere l'output di un ambiente protetto in raw/ e wiki/
# ---------------------------------------------------------------------------

def test_out_into_raw_or_wiki_is_refused_for_protected_env_before_any_connection(run, tmp_path):
    root = tmp_path / "factory"
    for folder in ("raw", "wiki", "deliverables", "management"):
        target = root / folder / "log.txt"
        code, out, fake = run(["search", "prod", "alpha", "--out", str(target)], [result([hit()])])
        payload = json.loads(out)
        assert code == 1 and payload["error"] == "protected_out_forbidden" and fake.calls == []
        assert not target.exists()


def test_out_refusal_resists_dotdot_symlink_and_relative_paths(run, tmp_path, monkeypatch):
    root = tmp_path / "factory"
    (root / "wiki").mkdir(parents=True)
    (root / "tmp").mkdir()
    sneaky = root / "tmp" / ".." / "wiki" / "x.txt"
    code, out, _ = run(["count", "prod", "alpha", "--out", str(sneaky)], [result([])])
    assert code == 1 and json.loads(out)["error"] == "protected_out_forbidden"
    link = root / "tmp" / "link"
    link.symlink_to(root / "wiki", target_is_directory=True)
    code, out, _ = run(["count", "prod", "alpha", "--out", str(link / "x.txt")], [result([])])
    assert code == 1 and json.loads(out)["error"] == "protected_out_forbidden"
    monkeypatch.chdir(root)
    code, out, _ = run(["count", "prod", "alpha", "--out", "wiki/x.txt"], [result([])])
    assert code == 1 and json.loads(out)["error"] == "protected_out_forbidden"
    assert not (root / "wiki" / "x.txt").exists()


def test_out_elsewhere_is_allowed_for_protected_and_anywhere_for_unprotected(run, tmp_path):
    scratch = tmp_path / "scratch" / "out.txt"
    code, out, fake = run(["search", "prod", "alpha", "--out", str(scratch)], [result([hit()])])
    assert code == 0 and out == "" and "# PROTETTO" in scratch.read_text(encoding="utf-8")    # stdout vuoto: tutto nel file
    env = "TWO_USER=u\nTWO_PWD=p\n"
    free = tmp_path / "factory" / "raw" / "val.txt"
    code, _, _ = run(["search", "val", "alpha", "--out", str(free)], [result([hit()])], env=env)
    assert code == 0 and "# val/alpha" in free.read_text(encoding="utf-8")


def test_out_forbidden_dirs_are_configurable(run, tmp_path):
    config = CONFIG + "  protected_out_forbidden_dirs: [secret]\n"
    root = tmp_path / "factory"
    code, out, _ = run(["count", "prod", "alpha", "--out", str(root / "secret" / "a.txt")], [result([])], config=config)
    assert code == 1 and json.loads(out)["forbidden_dirs"] == ["secret"]
    code, _, _ = run(["count", "prod", "alpha", "--out", str(root / "raw" / "a.txt")], [result([hit()])], config=config)
    assert code == 0                                                       # raw non e' piu' vietata in questa config
