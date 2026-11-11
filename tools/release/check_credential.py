#!/usr/bin/env python3
"""
check_credential.py -- Verifica permessi della credenziale prima del rilascio.

Legge il token dalla variabile d'ambiente indicata con --auth-env.
Non stampa mai il token.

Esito JSON:
  {"result": "PASS"|"FAIL"|"NON_VERIFICABILE", "provider": ..., "identity": ...,
   "operations": {"<op>": {"result": ..., "detail": ...}, ...}}

Uso:
  python3 tools/release/check_credential.py \\
    --provider github \\
    --auth-env GITHUB_TOKEN \\
    --operations create_tag trigger_pipeline \\
    --pipeline-ref myorg/myrepo/release.yml

  python3 tools/release/check_credential.py \\
    --provider gitlab \\
    --auth-env GITLAB_TOKEN \\
    --operations create_tag trigger_pipeline \\
    --pipeline-ref gitlab.com/42

  python3 tools/release/check_credential.py \\
    --provider ado \\
    --auth-env ADO_TOKEN \\
    --operations create_tag trigger_pipeline \\
    --pipeline-ref myorg/myproject/123

  python3 tools/release/check_credential.py --provider none

Exit code: 0 per PASS/NON_VERIFICABILE, 1 per FAIL.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

# Operazioni attese per profilo (informativa -- la skill le passa esplicitamente).
# ci_provider: none elimina trigger_pipeline dall'elenco.
OPERATIONS_BY_PROFILE = {
    "container-gitops": ["create_tag", "trigger_pipeline", "push_image"],
    "package-registry": ["create_tag", "trigger_pipeline", "publish_package"],
    "manifest-edit": ["create_tag", "edit_manifest"],
}


# ---------------------------------------------------------------------------
# HTTP helper (sostituibile nei test via monkeypatch)
# ---------------------------------------------------------------------------

def _request(url: str, headers: dict) -> tuple:
    """
    GET url con headers.
    Restituisce (status_code: int, body: dict, resp_headers: dict).
    Non propaga eccezioni: errori di rete → (0, {"_error": ...}, {}).
    Non stampa mai il token contenuto negli headers.
    """
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except Exception:
                body = {}
            resp_headers = {}
            if hasattr(resp, "headers"):
                resp_headers = {k: v for k, v in resp.headers.items()}
            return resp.status, body, resp_headers
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body, {}
    except Exception as exc:
        return 0, {"_error": str(exc)}, {}


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def _aggregate(ops: dict) -> str:
    """PASS se tutti PASS; FAIL se almeno uno FAIL; NON_VERIFICABILE altrimenti."""
    results = [v["result"] for v in ops.values()]
    if not results:
        return "NON_VERIFICABILE"
    if "FAIL" in results:
        return "FAIL"
    if all(r == "PASS" for r in results):
        return "PASS"
    return "NON_VERIFICABILE"


# ---------------------------------------------------------------------------
# Provider: GitHub Actions
# ---------------------------------------------------------------------------

def check_github(token: str, operations: list, pipeline_ref: str) -> dict:
    """
    Verifica permessi GitHub tramite:
    - GET /user  → identita' + X-OAuth-Scopes (token classico)
    - GET /repos/{owner}/{repo} → permissions.push/admin/maintain

    Scopes verificabili: repo, workflow (token classico).
    Token fine-grained: X-OAuth-Scopes assente → verifica via repo.permissions.push.

    Riferimento: https://docs.github.com/rest/users/users#get-the-authenticated-user
                 https://docs.github.com/rest/repos/repos#get-a-repository
    """
    if not token:
        return {"result": "FAIL", "provider": "github", "detail": "Token assente (auth_env vuoto)"}

    parts = (pipeline_ref or "").split("/")
    owner = parts[0] if len(parts) > 0 else ""
    repo = parts[1] if len(parts) > 1 else ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Identita' e scopes
    status, body, resp_headers = _request("https://api.github.com/user", headers)
    identity = body.get("login", "unknown")

    if status == 401:
        return {"result": "FAIL", "provider": "github",
                "detail": "Token non valido (401 Unauthorized)", "identity": identity}
    if status == 0:
        err = body.get("_error", "errore di rete")
        return {"result": "NON_VERIFICABILE", "provider": "github",
                "detail": f"Impossibile raggiungere api.github.com: {err}"}

    scopes_raw = resp_headers.get("X-OAuth-Scopes", resp_headers.get("x-oauth-scopes", ""))
    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]

    # Permessi repo
    repo_perms = None  # None = non verificato/non specificato
    if owner and repo:
        s2, b2, _ = _request(f"https://api.github.com/repos/{owner}/{repo}", headers)
        if s2 == 200:
            p = b2.get("permissions", {})
            repo_perms = {
                "push": bool(p.get("push")),
                "admin": bool(p.get("admin")),
                "maintain": bool(p.get("maintain")),
            }
        elif s2 == 404:
            return {"result": "FAIL", "provider": "github",
                    "detail": f"Repo {owner}/{repo} non trovato o non accessibile con questo token",
                    "identity": identity}

    ops_result = {}
    for op in operations:
        if op == "create_tag":
            # Richiede push o admin sul repo (git push refs/tags/*)
            if repo_perms is None:
                ops_result[op] = {"result": "NON_VERIFICABILE",
                                  "detail": "pipeline_ref non specifica owner/repo: impossibile verificare"}
            elif repo_perms["push"] or repo_perms["admin"] or repo_perms["maintain"]:
                ops_result[op] = {"result": "PASS",
                                  "detail": f"token ha permesso push/admin sul repo {owner}/{repo}"}
            else:
                ops_result[op] = {"result": "FAIL",
                                  "detail": f"token privo di permesso push/admin su {owner}/{repo}"}

        elif op == "trigger_pipeline":
            # Richiede scope 'workflow' o 'repo' (token classico)
            # o permesso push sul repo (token fine-grained)
            if scopes:
                has_scope = "workflow" in scopes or "repo" in scopes
                if has_scope:
                    matched = "workflow" if "workflow" in scopes else "repo"
                    ops_result[op] = {"result": "PASS",
                                      "detail": f"token ha scope '{matched}' (workflow dispatch)"}
                else:
                    ops_result[op] = {"result": "FAIL",
                                      "detail": (f"token manca scope 'workflow' per il workflow dispatch. "
                                                 f"Scopes attuali: {scopes or ['(nessuno)']}")}
            else:
                # Token fine-grained: nessun X-OAuth-Scopes; verifica via push
                if repo_perms is None:
                    ops_result[op] = {"result": "NON_VERIFICABILE",
                                      "detail": ("Token fine-grained (nessun X-OAuth-Scopes). "
                                                 "Verificare il permesso 'Actions: Write' sul repo.")}
                elif repo_perms["push"] or repo_perms["admin"]:
                    ops_result[op] = {"result": "PASS",
                                      "detail": f"token fine-grained con push/admin su {owner}/{repo}"}
                else:
                    ops_result[op] = {"result": "FAIL",
                                      "detail": (f"token fine-grained privo di push/admin su {owner}/{repo}. "
                                                 f"Aggiungere il permesso 'Actions: Write'.")}

        elif op in ("push_image", "publish_package", "edit_manifest"):
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": (f"Operazione '{op}': verificabile solo sul registry target, "
                                          f"non tramite GitHub API")}

        else:
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": f"Operazione '{op}' non riconosciuta per provider github"}

    overall = _aggregate(ops_result)
    return {"result": overall, "provider": "github", "identity": identity, "operations": ops_result}


# ---------------------------------------------------------------------------
# Provider: GitLab CI
# ---------------------------------------------------------------------------

def check_gitlab(token: str, operations: list, pipeline_ref: str) -> dict:
    """
    Verifica permessi GitLab tramite:
    - GET /api/v4/personal_access_tokens/self → scopes del PAT
    - GET /api/v4/projects/{id} → permissions.project_access.access_level

    Livelli di accesso: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner.
    create_tag e trigger_pipeline richiedono Developer (30) + scope api o write_repository.

    Riferimento: https://docs.gitlab.com/ee/api/personal_access_tokens.html
                 https://docs.gitlab.com/ee/api/projects.html
    """
    if not token:
        return {"result": "FAIL", "provider": "gitlab", "detail": "Token assente (auth_env vuoto)"}

    parts = (pipeline_ref or "").split("/")
    gl_host = parts[0] if len(parts) > 0 else "gitlab.com"
    project_id = parts[1] if len(parts) > 1 else ""

    headers = {"PRIVATE-TOKEN": token}

    # Identita' e scopes PAT
    status, body, _ = _request(f"https://{gl_host}/api/v4/personal_access_tokens/self", headers)
    identity = "unknown"
    scopes = []

    if status == 200:
        identity = body.get("name") or body.get("username", "unknown")
        scopes = body.get("scopes", [])
    elif status == 401:
        return {"result": "FAIL", "provider": "gitlab",
                "detail": "Token non valido o scaduto (401 Unauthorized)"}
    elif status == 0:
        err = body.get("_error", "errore di rete")
        return {"result": "NON_VERIFICABILE", "provider": "gitlab",
                "detail": f"Impossibile raggiungere {gl_host}: {err}"}
    else:
        return {"result": "NON_VERIFICABILE", "provider": "gitlab",
                "detail": (f"Impossibile verificare il token ({status}). "
                            f"Potrebbe essere un deploy token o un token di gruppo.")}

    # Ruolo nel progetto
    project_access_level = None
    if project_id:
        s2, b2, _ = _request(f"https://{gl_host}/api/v4/projects/{project_id}", headers)
        if s2 == 200:
            perms = b2.get("permissions", {})
            pa = perms.get("project_access") or {}
            ga = perms.get("group_access") or {}
            project_access_level = max(pa.get("access_level", 0), ga.get("access_level", 0))
        elif s2 == 404:
            return {"result": "FAIL", "provider": "gitlab",
                    "detail": f"Progetto {project_id} non trovato su {gl_host} con questo token",
                    "identity": identity}

    ops_result = {}
    for op in operations:
        if op in ("create_tag", "trigger_pipeline"):
            has_scope = "api" in scopes or "write_repository" in scopes
            if not has_scope:
                ops_result[op] = {"result": "FAIL",
                                  "detail": (f"Token manca scope 'api' o 'write_repository' "
                                             f"per {op}. Scopes attuali: {scopes or ['(nessuno)']}")}
            elif project_access_level is None:
                ops_result[op] = {"result": "NON_VERIFICABILE",
                                  "detail": ("pipeline_ref non specifica project_id: "
                                             "impossibile verificare il ruolo nel progetto")}
            elif project_access_level < 30:
                ops_result[op] = {"result": "FAIL",
                                  "detail": (f"Ruolo nel progetto insufficiente "
                                             f"(livello {project_access_level}, richiesto >=30 Developer)")}
            else:
                ops_result[op] = {"result": "PASS",
                                  "detail": (f"scope ok, ruolo={project_access_level} "
                                             f"(>= 30 Developer)")}

        elif op in ("push_image", "publish_package", "edit_manifest"):
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": (f"Operazione '{op}': verificabile solo sul registry target, "
                                          f"non tramite GitLab API")}

        else:
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": f"Operazione '{op}' non riconosciuta per provider gitlab"}

    overall = _aggregate(ops_result)
    return {"result": overall, "provider": "gitlab", "identity": identity, "operations": ops_result}


# ---------------------------------------------------------------------------
# Provider: Azure DevOps
# ---------------------------------------------------------------------------

def check_ado(token: str, operations: list, pipeline_ref: str) -> dict:
    """
    Verifica permessi ADO tramite API pubbliche documentate.

    Verifica di base: GET _apis/projects (200 = PAT valido con accesso all'org).
    Verifica pipeline: GET _apis/pipelines/{id} (200 = accesso in lettura).

    Limitazione: la verifica completa di CreateTag (namespace GitRepositories, bit 16)
    e QueueBuilds (namespace Build, bit 128) richiede la security namespaces API
    (GET _apis/securitynamespaces e GET _apis/accesscontrollists/{namespaceId}).
    Questo endpoint e' documentato pubblicamente ma la struttura e' complessa;
    queste operazioni sono marcate NON_VERIFICABILE con indicazione di cosa controllare.
    da confermare sul provider: https://learn.microsoft.com/rest/api/azure/devops/security

    Riferimento:
      https://learn.microsoft.com/rest/api/azure/devops/core/projects/list
      https://learn.microsoft.com/rest/api/azure/devops/pipelines/pipelines/get
    """
    if not token:
        return {"result": "FAIL", "provider": "ado", "detail": "Token assente (auth_env vuoto)"}

    parts = (pipeline_ref or "").split("/")
    ado_org = parts[0] if len(parts) > 0 else ""
    ado_proj = parts[1] if len(parts) > 1 else ""
    ado_pid = parts[2] if len(parts) > 2 else ""

    if not ado_org:
        return {"result": "NON_VERIFICABILE", "provider": "ado",
                "detail": "pipeline_ref non specificato (formato atteso: org/project/pipeline_id)"}

    b64 = base64.b64encode(f":{token}".encode()).decode()
    headers = {"Authorization": f"Basic {b64}", "Content-Type": "application/json"}

    # Verifica accesso all'org (proxy di validita' PAT)
    # Nota: un PAT scaduto su ADO puo' provocare un redirect a _signin invece di 401.
    # urlopen segue il redirect e restituisce HTML; il parse JSON fallisce → (200, {}, {}).
    # Rilevarlo: la risposta vuota o senza 'value' indica redirect silenzioso.
    identity = "unknown"
    status, body, _ = _request(
        f"https://dev.azure.com/{ado_org}/_apis/projects?api-version=7.1", headers
    )

    if status in (401, 403):
        return {"result": "FAIL", "provider": "ado",
                "detail": f"Token ADO non autorizzato ({status}). Verificare che il PAT non sia scaduto."}
    if status == 0:
        err = body.get("_error", "errore di rete")
        return {"result": "NON_VERIFICABILE", "provider": "ado",
                "detail": f"Impossibile raggiungere dev.azure.com/{ado_org}: {err}"}
    if status != 200 or ("value" not in body and "_error" not in body and not body):
        # Redirect a _signin: corpo HTML, JSON vuoto
        return {"result": "FAIL", "provider": "ado",
                "detail": (f"Token ADO non valido o scaduto (HTTP {status}, "
                            f"possibile redirect a _signin). Rinnovare il PAT.")}

    ops_result = {}
    for op in operations:
        if op == "create_tag":
            # Richiede namespace GitRepositories, bit CreateTag (16).
            # Non verificabile via sola API pubblica senza interrogare security namespaces.
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": (
                                   "Verifica CreateTag richiede la security namespaces API: "
                                   "GET dev.azure.com/{org}/_apis/securitynamespaces (namespace "
                                   "'2e9eb7ed-3c0a-47d4-87c1-0ffdd275fd87', bit 16=CreateTag). "
                                   "da confermare sul provider."
                               )}

        elif op == "trigger_pipeline":
            # GET sulla pipeline: 200 = lettura ok; QueueBuilds non verificabile via GET.
            if ado_proj and ado_pid:
                s2, b2, _ = _request(
                    f"https://dev.azure.com/{ado_org}/{ado_proj}/_apis/pipelines/{ado_pid}?api-version=7.1",
                    headers
                )
                if s2 == 200:
                    ops_result[op] = {"result": "NON_VERIFICABILE",
                                      "detail": (
                                          f"Pipeline {ado_pid} accessibile in lettura (HTTP 200). "
                                          f"Il permesso QueueBuilds richiede la security namespaces API: "
                                          f"namespace '33344d9c-fc72-4d6f-aba5-fa317101a7e9', bit 128=QueueBuilds. "
                                          f"da confermare sul provider."
                                      )}
                elif s2 in (401, 403):
                    ops_result[op] = {"result": "FAIL",
                                      "detail": f"PAT privo di accesso alla pipeline {ado_pid} ({s2})"}
                else:
                    ops_result[op] = {"result": "NON_VERIFICABILE",
                                      "detail": f"Pipeline {ado_pid}: HTTP {s2}"}
            else:
                ops_result[op] = {"result": "NON_VERIFICABILE",
                                   "detail": "pipeline_ref incompleto (serve org/project/pipeline_id)"}

        elif op in ("push_image", "publish_package", "edit_manifest"):
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": (f"Operazione '{op}': verificabile solo sul registry target, "
                                          f"non tramite ADO API")}

        else:
            ops_result[op] = {"result": "NON_VERIFICABILE",
                               "detail": f"Operazione '{op}' non riconosciuta per provider ado"}

    overall = _aggregate(ops_result)
    return {"result": overall, "provider": "ado", "identity": identity, "operations": ops_result}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verifica permessi credenziale pre-release (US-326)"
    )
    parser.add_argument("--provider", required=True,
                        choices=["github", "gitlab", "ado", "none"],
                        help="Provider CI: github | gitlab | ado | none")
    parser.add_argument("--auth-env", default="",
                        help="Nome variabile d'ambiente del token (mai stampato)")
    parser.add_argument("--operations", nargs="*", default=[],
                        help=("Operazioni da verificare: "
                              "create_tag trigger_pipeline push_image "
                              "publish_package edit_manifest"))
    parser.add_argument("--pipeline-ref", default="",
                        help="pipeline_ref della voce release_targets[] (owner/repo, host/proj_id, org/proj/pid)")
    parser.add_argument("--registry", default="",
                        help="Registry URL (informativo per future estensioni)")
    args = parser.parse_args()

    if args.provider == "none":
        out = {"result": "PASS", "provider": "none",
               "detail": "ci_provider: none — nessun permesso CI da verificare"}
        print(json.dumps(out, indent=2))
        return

    token = os.environ.get(args.auth_env, "") if args.auth_env else ""

    if args.provider == "github":
        out = check_github(token, args.operations, args.pipeline_ref)
    elif args.provider == "gitlab":
        out = check_gitlab(token, args.operations, args.pipeline_ref)
    elif args.provider == "ado":
        out = check_ado(token, args.operations, args.pipeline_ref)
    else:
        out = {"result": "NON_VERIFICABILE", "provider": args.provider,
               "detail": f"Provider '{args.provider}' non implementato"}

    print(json.dumps(out, indent=2))

    if out.get("result") == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
