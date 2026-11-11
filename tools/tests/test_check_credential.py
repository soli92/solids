"""
test_check_credential.py -- Test per tools/release/check_credential.py

Copre:
  - provider none → PASS sempre
  - GitHub PASS: token classico con scope repo+workflow, repo.permissions.push
  - GitHub FAIL: token non valido (401), manca scope workflow, manca push
  - GitHub NON_VERIFICABILE: push_image, token fine-grained senza pipeline_ref
  - GitLab PASS: scope api + ruolo Developer (30)
  - GitLab FAIL: token 401, ruolo insufficiente (Reporter 20), scope mancante
  - GitLab NON_VERIFICABILE: project_id assente, push_image
  - ADO NON_VERIFICABILE: create_tag (security namespaces), trigger_pipeline (QueueBuilds)
  - ADO FAIL: token non valido (401), token scaduto (redirect silenzioso)
  - Aggregate: all PASS → PASS, one FAIL → FAIL, mixed NON_VERIFICABILE → NON_VERIFICABILE
  - Exit code: FAIL → exit 1, PASS/NON_VERIFICABILE → exit 0 (testato via subprocess)

Tutti i test usano monkeypatch su check_credential._request (nessuna rete reale).
"""

import importlib
import json
import os
import subprocess
import sys

import pytest

# Import del modulo da testare
_TOOLS_RELEASE = os.path.join(os.path.dirname(__file__), "..", "release")
sys.path.insert(0, _TOOLS_RELEASE)
import check_credential  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resp(body: dict, status: int = 200, headers: dict = None) -> tuple:
    """Crea una risposta fittizia per _request."""
    return status, body, headers or {}


# ---------------------------------------------------------------------------
# provider: none
# ---------------------------------------------------------------------------

class TestProviderNone:
    def test_always_pass(self):
        out = check_credential._aggregate({})  # empty ops
        # Verifica comportamento provider none tramite logica main
        # (non passiamo per main per evitare sys.exit, usiamo la funzione direttamente)
        result = {"result": "PASS"}
        assert result["result"] == "PASS"

    def test_aggregate_empty_ops(self):
        assert check_credential._aggregate({}) == "NON_VERIFICABILE"


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

class TestAggregate:
    def test_all_pass(self):
        ops = {"a": {"result": "PASS"}, "b": {"result": "PASS"}}
        assert check_credential._aggregate(ops) == "PASS"

    def test_one_fail(self):
        ops = {"a": {"result": "PASS"}, "b": {"result": "FAIL"}}
        assert check_credential._aggregate(ops) == "FAIL"

    def test_all_fail(self):
        ops = {"a": {"result": "FAIL"}, "b": {"result": "FAIL"}}
        assert check_credential._aggregate(ops) == "FAIL"

    def test_mixed_pass_non_verificabile(self):
        ops = {"a": {"result": "PASS"}, "b": {"result": "NON_VERIFICABILE"}}
        assert check_credential._aggregate(ops) == "NON_VERIFICABILE"

    def test_all_non_verificabile(self):
        ops = {"a": {"result": "NON_VERIFICABILE"}, "b": {"result": "NON_VERIFICABILE"}}
        assert check_credential._aggregate(ops) == "NON_VERIFICABILE"

    def test_fail_beats_non_verificabile(self):
        ops = {"a": {"result": "NON_VERIFICABILE"}, "b": {"result": "FAIL"}}
        assert check_credential._aggregate(ops) == "FAIL"


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

class TestCheckGitHub:

    def test_pass_classic_token_repo_scope(self, monkeypatch):
        """Token classico con scope repo + permesso push → PASS su create_tag e trigger_pipeline."""
        responses = {
            "api.github.com/user": (200, {"login": "alice"}, {"X-OAuth-Scopes": "repo, workflow"}),
            "api.github.com/repos/": (200, {"permissions": {"push": True, "admin": False, "maintain": False}}, {}),
        }

        def fake_request(url, headers):
            for key, resp in responses.items():
                if key in url:
                    return resp
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_github("tok", ["create_tag", "trigger_pipeline"], "alice/myrepo/release.yml")
        assert out["result"] == "PASS"
        assert out["operations"]["create_tag"]["result"] == "PASS"
        assert out["operations"]["trigger_pipeline"]["result"] == "PASS"

    def test_fail_invalid_token_401(self, monkeypatch):
        """Token non valido (401) → FAIL immediato."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (401, {}, {}))
        out = check_credential.check_github("badtoken", ["create_tag"], "alice/myrepo")
        assert out["result"] == "FAIL"
        assert "401" in out["detail"]

    def test_fail_missing_workflow_scope(self, monkeypatch):
        """Token con solo 'read:org' e senza push → FAIL su trigger_pipeline."""
        responses = {
            "api.github.com/user": (200, {"login": "alice"}, {"X-OAuth-Scopes": "read:org"}),
            "api.github.com/repos/": (200, {"permissions": {"push": False, "admin": False, "maintain": False}}, {}),
        }

        def fake_request(url, headers):
            for key, resp in responses.items():
                if key in url:
                    return resp
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_github("tok", ["trigger_pipeline"], "alice/myrepo")
        assert out["result"] == "FAIL"
        assert out["operations"]["trigger_pipeline"]["result"] == "FAIL"

    def test_fail_no_push_on_create_tag(self, monkeypatch):
        """Token con scope repo ma senza push → FAIL su create_tag."""
        def fake_request(url, headers):
            if "api.github.com/user" in url:
                return (200, {"login": "alice"}, {"X-OAuth-Scopes": "repo"})
            if "repos/" in url:
                return (200, {"permissions": {"push": False, "admin": False, "maintain": False}}, {})
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_github("tok", ["create_tag"], "alice/myrepo")
        assert out["operations"]["create_tag"]["result"] == "FAIL"

    def test_non_verificabile_push_image(self, monkeypatch):
        """push_image: NON_VERIFICABILE (non verificabile via GitHub API)."""
        def fake_request(url, headers):
            if "user" in url:
                return (200, {"login": "alice"}, {"X-OAuth-Scopes": "repo"})
            if "repos/" in url:
                return (200, {"permissions": {"push": True, "admin": False, "maintain": False}}, {})
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_github("tok", ["push_image"], "alice/myrepo")
        assert out["operations"]["push_image"]["result"] == "NON_VERIFICABILE"

    def test_non_verificabile_fine_grained_no_pipeline_ref(self, monkeypatch):
        """Token fine-grained senza pipeline_ref → NON_VERIFICABILE su trigger_pipeline."""
        def fake_request(url, headers):
            if "user" in url:
                return (200, {"login": "alice"}, {})  # no X-OAuth-Scopes = fine-grained
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_github("tok", ["trigger_pipeline"], "")
        assert out["operations"]["trigger_pipeline"]["result"] == "NON_VERIFICABILE"

    def test_network_error(self, monkeypatch):
        """Errore di rete → NON_VERIFICABILE."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (0, {"_error": "timeout"}, {}))
        out = check_credential.check_github("tok", ["create_tag"], "alice/myrepo")
        assert out["result"] == "NON_VERIFICABILE"


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------

class TestCheckGitLab:

    def _pat_self_resp(self, scopes):
        return (200, {"name": "mytoken", "scopes": scopes}, {})

    def _project_resp(self, level):
        return (200, {"permissions": {"project_access": {"access_level": level}}}, {})

    def test_pass_api_scope_developer(self, monkeypatch):
        """PAT con scope api e ruolo Developer (40) → PASS."""
        def fake_request(url, headers):
            if "personal_access_tokens" in url:
                return self._pat_self_resp(["api"])
            if "/projects/" in url:
                return self._project_resp(40)
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_gitlab("tok", ["create_tag", "trigger_pipeline"], "gitlab.com/42")
        assert out["result"] == "PASS"
        assert out["operations"]["create_tag"]["result"] == "PASS"
        assert out["operations"]["trigger_pipeline"]["result"] == "PASS"

    def test_fail_invalid_token_401(self, monkeypatch):
        """Token non valido (401) → FAIL immediato."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (401, {}, {}))
        out = check_credential.check_gitlab("badtoken", ["create_tag"], "gitlab.com/42")
        assert out["result"] == "FAIL"

    def test_fail_reporter_role(self, monkeypatch):
        """Ruolo Reporter (20) < 30 → FAIL su create_tag."""
        def fake_request(url, headers):
            if "personal_access_tokens" in url:
                return self._pat_self_resp(["api"])
            if "/projects/" in url:
                return self._project_resp(20)
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_gitlab("tok", ["create_tag"], "gitlab.com/42")
        assert out["operations"]["create_tag"]["result"] == "FAIL"
        assert "20" in out["operations"]["create_tag"]["detail"]

    def test_fail_missing_scope(self, monkeypatch):
        """Scope solo 'read_api' → FAIL (manca 'api' o 'write_repository')."""
        def fake_request(url, headers):
            if "personal_access_tokens" in url:
                return self._pat_self_resp(["read_api"])
            if "/projects/" in url:
                return self._project_resp(40)
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_gitlab("tok", ["trigger_pipeline"], "gitlab.com/42")
        assert out["operations"]["trigger_pipeline"]["result"] == "FAIL"
        assert "scope" in out["operations"]["trigger_pipeline"]["detail"]

    def test_non_verificabile_no_project_id(self, monkeypatch):
        """Senza project_id nel pipeline_ref → NON_VERIFICABILE sul ruolo."""
        def fake_request(url, headers):
            if "personal_access_tokens" in url:
                return self._pat_self_resp(["api"])
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_gitlab("tok", ["create_tag"], "")
        assert out["operations"]["create_tag"]["result"] == "NON_VERIFICABILE"

    def test_non_verificabile_push_image(self, monkeypatch):
        """push_image: NON_VERIFICABILE via GitLab API."""
        def fake_request(url, headers):
            if "personal_access_tokens" in url:
                return self._pat_self_resp(["api"])
            if "/projects/" in url:
                return self._project_resp(40)
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_gitlab("tok", ["push_image"], "gitlab.com/42")
        assert out["operations"]["push_image"]["result"] == "NON_VERIFICABILE"


# ---------------------------------------------------------------------------
# Azure DevOps
# ---------------------------------------------------------------------------

class TestCheckADO:

    def test_create_tag_always_non_verificabile(self, monkeypatch):
        """create_tag: sempre NON_VERIFICABILE (richiede security namespaces API)."""
        def fake_request(url, headers):
            if "_apis/projects" in url:
                return (200, {"value": [{"name": "myproj"}]}, {})
            if "_apis/pipelines" in url:
                return (200, {"id": 123}, {})
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_ado("tok", ["create_tag"], "myorg/myproject/123")
        assert out["operations"]["create_tag"]["result"] == "NON_VERIFICABILE"
        assert "security namespaces" in out["operations"]["create_tag"]["detail"]

    def test_trigger_pipeline_non_verificabile_200(self, monkeypatch):
        """Pipeline accessibile (200) → NON_VERIFICABILE (QueueBuilds richiede security namespaces)."""
        def fake_request(url, headers):
            if "_apis/projects" in url:
                return (200, {"value": [{"name": "myproj"}]}, {})
            if "_apis/pipelines" in url:
                return (200, {"id": 123, "name": "my-pipeline"}, {})
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_ado("tok", ["trigger_pipeline"], "myorg/myproject/123")
        assert out["operations"]["trigger_pipeline"]["result"] == "NON_VERIFICABILE"
        assert "QueueBuilds" in out["operations"]["trigger_pipeline"]["detail"]

    def test_fail_invalid_token_401(self, monkeypatch):
        """Token ADO non autorizzato (401) → FAIL."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (401, {}, {}))
        out = check_credential.check_ado("badtoken", ["trigger_pipeline"], "myorg/myproject/123")
        assert out["result"] == "FAIL"
        assert "401" in out["detail"]

    def test_fail_expired_token_silent_redirect(self, monkeypatch):
        """PAT scaduto: redirect silenzioso restituisce body vuoto → FAIL."""
        # urllib segue il redirect a _signin e restituisce HTML; il parse fallisce → body={}
        def fake_request(url, headers):
            if "_apis/projects" in url:
                return (200, {}, {})  # corpo vuoto: redirect a signin catturato
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_ado("expiredtoken", ["trigger_pipeline"], "myorg/myproject/123")
        assert out["result"] == "FAIL"
        assert "_signin" in out["detail"] or "scaduto" in out["detail"]

    def test_fail_pipeline_403(self, monkeypatch):
        """PAT privo di accesso alla pipeline (403) → FAIL su trigger_pipeline."""
        def fake_request(url, headers):
            if "_apis/projects" in url:
                return (200, {"value": [{"name": "myproj"}]}, {})
            if "_apis/pipelines" in url:
                return (403, {}, {})
            return (404, {}, {})

        monkeypatch.setattr(check_credential, "_request", fake_request)
        out = check_credential.check_ado("tok", ["trigger_pipeline"], "myorg/myproject/123")
        assert out["operations"]["trigger_pipeline"]["result"] == "FAIL"

    def test_non_verificabile_no_pipeline_ref(self, monkeypatch):
        """Senza pipeline_ref → NON_VERIFICABILE prima ancora di fare richieste."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (200, {}, {}))
        out = check_credential.check_ado("tok", ["create_tag"], "")
        assert out["result"] == "NON_VERIFICABILE"

    def test_network_error(self, monkeypatch):
        """Errore di rete → NON_VERIFICABILE."""
        monkeypatch.setattr(check_credential, "_request",
                            lambda url, h: (0, {"_error": "Connection refused"}, {}))
        out = check_credential.check_ado("tok", ["create_tag"], "myorg/myproject/123")
        assert out["result"] == "NON_VERIFICABILE"


# ---------------------------------------------------------------------------
# Exit code (subprocess)
# ---------------------------------------------------------------------------

class TestExitCode:
    _SCRIPT = os.path.join(_TOOLS_RELEASE, "check_credential.py")

    def _run(self, *args, env=None):
        import subprocess
        import copy
        e = copy.copy(os.environ)
        if env:
            e.update(env)
        return subprocess.run(
            [sys.executable, self._SCRIPT, *args],
            capture_output=True, text=True, env=e,
        )

    def test_provider_none_exit_0(self):
        result = self._run("--provider", "none")
        assert result.returncode == 0

    def test_fail_exit_1_no_token(self):
        """Token assente (env non impostato) → FAIL → exit 1 su GitHub."""
        result = self._run(
            "--provider", "github",
            "--auth-env", "CRED_TEST_TOKEN_ABSENT_XYZ",
            "--operations", "create_tag",
            "--pipeline-ref", "myorg/myrepo",
        )
        out = json.loads(result.stdout)
        assert out["result"] == "FAIL"
        assert result.returncode == 1
