"""Test del rilevatore di segreti usato dai generatori di documentazione."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docs"))
import redact  # noqa: E402


@pytest.mark.parametrize("line", [
    'DB_PASSWORD="foobar"',
    "  readonly DB_PASSWORD: string;",
    'Authorization: Basic base64(":" + ACME_TOKEN)',
    "| `http.extraHeader: Authorization: Basic base64(:PAT)` |",
    "Authorization: Bearer $TOKEN",
    "password: <password di test>",
    "ACME_TOKEN",
])
def test_non_sono_segreti(line):
    assert redact.scan(line) == []


@pytest.mark.parametrize("line,kind", [
    ("pass" + "word: " + "Hunter22x", "password"),
    ("GITLAB_AUTH_TOKEN=" + "qw12" * 6 + " npm publish", "token"),
    ("Authorization: " + "Bearer " + "ab12" * 6, "authorization"),
    ("ghp_" + "a" * 36, "github-token"),
])
def test_sono_segreti(line, kind):
    f = redact.scan(line)
    assert [x.kind for x in f] == [kind]
    assert "***" in f[0].excerpt


def test_assert_clean_solleva():
    with pytest.raises(redact.RedactionError):
        redact.assert_clean("password: Hunter22x", "x.md")
