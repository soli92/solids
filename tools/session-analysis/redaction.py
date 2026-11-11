"""
redaction.py — R-SAA-3 redaction patterns shared by generate-report.py and llm-advisory.py.

Single source for the regexes that anonymize report content and for the leak check run
before anything leaves the pipeline (report write, LLM advisory call).

  redact_str / redact_value   anonymize paths, emails, credentials
  REPORT_STOP_PATTERNS        leak patterns of the generate-report.py final gate
  find_leaks(text, strict)    leak kinds found in text; strict adds the checks used
                              before an LLM call (slugged home paths, /home, Windows
                              profiles, unredacted *_TOKEN= assignments)

parse-transcript.py and detect-anomalies.py keep their own variants (they redact at
parse time with a different placeholder); this module does not change them.

stdlib-only: re
"""

import re

EMAIL_PLACEHOLDER = "user@example.com"

PATH_RE = re.compile(r"/Users/[^/\s\"'<>]+/")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
CRED_RE = re.compile(
    r"(sk-[A-Za-z0-9\-]+|Bearer [A-Za-z0-9._\-]+|[A-Z_]{4,}_TOKEN=[^\s\"']+)"
)

# Final gate of generate-report.py: none of these may survive redaction.
REPORT_STOP_PATTERNS = [
    re.compile(r"/Users/(?!USER/)"),
    re.compile(r"sk-[A-Za-z0-9\-]{10,}"),
    re.compile(r"Bearer [A-Za-z0-9._\-]{10,}"),
]

# Extra checks before sending text to an LLM. They catch user names that the
# path regex above does not see: project slugs such as "-Users-<name>-Documents"
# (Claude Code project directories), Linux homes and Windows profiles.
STRICT_EXTRA_PATTERNS = [
    ("slugged-home-path", re.compile(r"-Users-(?!USER-)[A-Za-z0-9._]+")),
    ("linux-home-path", re.compile(r"/home/(?!USER/)[^/\s\"'<>]+")),
    ("windows-profile-path", re.compile(r"[A-Za-z]:\\+Users\\+(?!USER\\)[^\\\s\"'<>]+", re.I)),
    ("token-assignment", re.compile(r"[A-Z_]{4,}_TOKEN=(?!\[REDACTED)[^\s\"']+")),
]


def redact_str(s):
    """Apply R-SAA-3 redaction to a single string."""
    if not isinstance(s, str):
        return s
    s = PATH_RE.sub("/Users/USER/", s)
    s = EMAIL_RE.sub(EMAIL_PLACEHOLDER, s)
    s = CRED_RE.sub("[REDACTED_CREDENTIAL]", s)
    return s


def redact_value(v):
    """Recursively redact string values in any JSON-compatible structure."""
    if isinstance(v, str):
        return redact_str(v)
    if isinstance(v, dict):
        return {k: redact_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [redact_value(item) for item in v]
    return v


def find_leaks(text, strict=False):
    """
    Return the kinds of leak found in text (empty list = clean).

    Only the kind is returned, never the matched value, so the caller can report
    the finding without echoing the secret.
    """
    kinds = []
    labels = ["user-path", "credential-sk", "credential-bearer"]
    for label, pat in zip(labels, REPORT_STOP_PATTERNS):
        if pat.search(text):
            kinds.append(label)
    if any(e != EMAIL_PLACEHOLDER for e in EMAIL_RE.findall(text)):
        kinds.append("email")
    if strict:
        for label, pat in STRICT_EXTRA_PATTERNS:
            if pat.search(text):
                kinds.append(label)
    return kinds
