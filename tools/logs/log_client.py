"""Supporto tecnico di log_access.py: credenziali, connessione TLS, login e chiamate in sola lettura.

Qui non ci sono regole di ricerca ne' di mascheramento. L'unica politica e' la sicurezza del canale:
solo le operazioni di lettura in ALLOWED_OPERATIONS, index validato, certificato mai disattivato.

Due modalita' di accesso a un cluster (campo `auth` del registro):
  dashboards-login  login su OpenSearch Dashboards (POST /auth/login, cookie in memoria) e chiamate
                    tramite il proxy della console (/api/console/proxy)
  basic             REST diretto sul cluster con Basic auth
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Le uniche operazioni ammesse verso un cluster, tutte di lettura.
ALLOWED_OPERATIONS = ("_search", "_count", "_field_caps")

INDEX_RE = re.compile(r"^[A-Za-z0-9_.*-]+$")        # niente virgole, slash o query string: nessun path injection

DEFAULT_TIMEOUT = 60
TLS_PAUSE = 2

EXIT_CONNECT = 2
EXIT_QUERY = 5
EXIT_TIMEOUT = 6


class ClientError(Exception):
    """Errore di login o di ricerca. Il testo puo' contenere pezzi di log: chi lo stampa deve mascherarlo."""

    def __init__(self, code: int, error: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.payload = {"ok": False, "error": error, "message": message, **extra}


# --- Credenziali ---------------------------------------------------------------------------------------------

def resolve_credentials(cluster: dict, env_values: dict[str, str],
                        environ: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Prima sorgente completa fra: coppie del registro nel .env, stesse coppie nell'ambiente del processo.
    Ritorna {user, password, source} (source e' solo un'etichetta, mai il valore)."""
    environ = os.environ if environ is None else environ
    cut = cluster.get("username_strip_from")

    def pick(user: str, password: str, source: str) -> dict[str, Any]:
        # username_strip_from: lo username di login e' la parte prima di quel suffisso (es. ".corp")
        if cut and cut in user:
            user = user.split(cut, 1)[0]
        return {"user": user, "password": password, "source": source}

    for user_var, pwd_var in cluster.get("credentials") or []:
        if env_values.get(user_var) and env_values.get(pwd_var):
            return pick(env_values[user_var], env_values[pwd_var], f"env-file:{user_var}")
    for user_var, pwd_var in cluster.get("credentials") or []:
        if environ.get(user_var) and environ.get(pwd_var):
            return pick(environ[user_var], environ[pwd_var], f"environ:{user_var}")
    return None


def credentials_ready(cluster: dict, env_values: dict[str, str],
                      environ: dict[str, str] | None = None) -> str | None:
    """Etichetta della sorgente se le credenziali ci sono, altrimenti None. Non espone valori."""
    found = resolve_credentials(cluster, env_values, environ)
    return found["source"] if found else None


# --- Connessione ---------------------------------------------------------------------------------------------

def _pinned_adapter(cert_file: Path):
    from requests.adapters import HTTPAdapter

    class PinnedCertAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = ssl.create_default_context(cafile=str(cert_file))
            # Il certificato stesso fa da ancora di fiducia: restano verificati hostname e scadenza.
            context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
            kwargs["ssl_context"] = context
            return super().init_poolmanager(*args, **kwargs)

    return PinnedCertAdapter()


def presented_fingerprint(base_url: str) -> str:
    """SHA-256 del certificato presentato ora dal server, letto SENZA verificarlo: solo per la diagnosi."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    host, _, port = base_url.split("//", 1)[1].split("/", 1)[0].partition(":")
    try:
        with socket.create_connection((host, int(port or 443)), timeout=10) as raw, \
                context.wrap_socket(raw, server_hostname=host) as tls:
            return hashlib.sha256(tls.getpeercert(True)).hexdigest()
    except OSError as error:
        return f"non leggibile ({error})"


class Client:
    """Sessione verso un cluster. Creata con `open_client`; i test la sostituiscono con una finta."""

    def __init__(self, cluster: dict, session, timeout: int, attempts: int, cert_file: Path | None) -> None:
        self.cluster = cluster
        self.session = session
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self.cert_file = cert_file
        self.base_url = cluster["base_url"].rstrip("/")
        self.auth = cluster.get("auth", "dashboards-login")

    def _post(self, url: str, **kwargs):
        import requests

        for attempt in range(1, self.attempts + 1):
            try:
                return self.session.post(url, timeout=self.timeout, **kwargs)
            except requests.exceptions.SSLError as error:
                if attempt == self.attempts:
                    extra = {}
                    if self.cert_file:
                        expected = hashlib.sha256(ssl.PEM_cert_to_DER_cert(self.cert_file.read_text())).hexdigest()
                        extra = {"expected_fingerprint": expected,
                                 "presented_fingerprint": presented_fingerprint(self.base_url)}
                    raise ClientError(EXIT_CONNECT, "tls", f"errore TLS dopo {self.attempts} tentativi: "
                                      f"{error.args[0]}", **extra) from None
                time.sleep(TLS_PAUSE)
            except requests.exceptions.Timeout:
                raise ClientError(EXIT_TIMEOUT, "timeout", f"nessuna risposta entro {self.timeout} s") from None
            except requests.exceptions.ConnectionError as error:
                raise ClientError(EXIT_CONNECT, "connection", f"cluster non raggiungibile (VPN?): "
                                  f"{str(error)[:200]}") from None

    def login(self, user: str, password: str) -> None:
        if self.auth == "basic":
            self.session.auth = (user, password)
            return
        response = self._post(f"{self.base_url}/auth/login", json={"username": user, "password": password})
        if response.status_code != 200:
            raise ClientError(EXIT_CONNECT, "login", f"login fallito: HTTP {response.status_code}",
                              detail=response.text[:300])

    def query(self, index: str, operation: str, body: dict, params: str = "") -> dict:
        """POST <index>/<operation>?<params>. Solo ALLOWED_OPERATIONS e index validati."""
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"operazione non ammessa: {operation}")
        if not INDEX_RE.match(index):
            raise ValueError(f"index non ammesso: {index}")
        path = f"{index}/{operation}" + (f"?{params}" if params else "")
        if self.auth == "basic":
            response = self._post(f"{self.base_url}/{path}", data=json.dumps(body))
        else:
            response = self._post(f"{self.base_url}/api/console/proxy?path={quote(path, safe='')}&method=POST",
                                  data=json.dumps(body))
        if response.status_code != 200:
            raise ClientError(EXIT_QUERY, "query", f"ricerca fallita: HTTP {response.status_code}",
                              detail=response.text[:500])
        return response.json()


def open_client(cluster: dict, creds: dict[str, Any], root: Path, timeout: int = DEFAULT_TIMEOUT,
                attempts: int = 3) -> Client:
    """Login sul cluster; il cookie di sessione vive solo in memoria, quindi la scadenza non e' mai un problema."""
    import requests

    session = requests.Session()
    session.trust_env = False       # niente proxy ne' .netrc dall'ambiente
    session.headers.update({"osd-xsrf": "true", "Content-Type": "application/json"})
    cert_file = None
    if cluster.get("cert_file"):
        cert_file = (root / cluster["cert_file"])
        if not cert_file.is_file():
            raise ClientError(EXIT_CONNECT, "cert_missing",
                              f"certificato del cluster non trovato: {cluster['cert_file']}",
                              hint="esportarlo dal browser (formato PEM) e salvarlo in quel percorso")
        session.mount("https://", _pinned_adapter(cert_file))
    client = Client(cluster, session, timeout, attempts, cert_file)
    client.login(creds["user"], creds["password"])
    return client
