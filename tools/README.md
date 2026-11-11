# tools/

Executable factory tools, **provider-agnostic** (single canonical location).
Accessible from any adapter and runnable manually.

> **R.A6 / Sprint 1:** do not add new scripts under `.claude/tools/`. That
> folder is compatibility shim only — see `.claude/tools/README.md`.
> Adapter registry health check: `python3 tools/adapters/check-adapter-lag.py`.

## Structure

| Folder | Contents |
|---|---|
| `a11y/` | WCAG 2.2 AA accessibility scan via axe-core + Playwright |
| `adapters/` | Registry check (`check-adapter-lag.py`) vs `adapters/capability-matrix.yaml` |
| `analytics/` | Session analytics, cost estimation, Monte Carlo, PERT, token ledger; `team-velocity.py` + `kanban_history.py` (`/velocity`, EP-078) |
| `coordinamento/` | Deterministic PM report (EP-070); `pianifica.py` ranks open TSK and proposes an owner (EP-078) |
| `docs/` | Documentation generated from the wiki (EP-075); `verify_verbatim.py` checks verbatim quotes (EP-078) |
| `kanban/` | Kanban tooling; `date_lavoro_check.py` = work dates on TSK, Check 4be (EP-079) |
| `lint/` | Config/notes consistency checks; `check-log-append-guard.py` (4bb), `check-gap-closures.py` (4bc), `check-gaps-append-guard.py` (4bd), `check-date-lavoro.py` (4be) |
| `pocock/` | Engineering practices, opt-in (EP-077): `verify_vendor.py`, `kpi_pilota.py`, `bilancio_n1.py` |
| `runtime/` | Portable hooks (e.g. `suggest-next.py` EP-033) — primary path for Stop hooks |
| `session-analysis/` | Post-hoc session analysis; `llm-advisory.py` (advisory via `claude -p`) and `redaction.py` (single redaction module, EP-077) |
| `temporal/` | Temporal context: UTC now, rebuild state from events, build temporal context |
| `tutor/` | Formative capability (EP-045) |
| `visual/` | Screenshot, design token extraction, design system conformance, LLM generator |
| `wiki/` | Wiki log and gaps: `log_append_guard.py`, `recover_log_entries.py`, `verify_gap_closures.py`, `gaps_append_guard.py` (EP-077, EP-078) |
| `wiki-search/` | Hybrid wiki search (EP-042) |

## Dependency setup

**Prerequisites:**
- Python 3.10+
- Node 18+
- Playwright (`npx playwright install --with-deps chromium`)
- axe-core (via `npm install` in this folder)

```bash
# Python deps
pip install -r tools/requirements.txt

# Node deps
cd tools && npm install && npx playwright install --with-deps chromium
```

## Variables

Tools assume `FACTORY_ROOT` = repo root. Resolved automatically via:
- `$CLAUDE_PROJECT_DIR` (Claude Code)
- Relative path `./tools/` from CWD (manual launch from repo root)
- Adapter-specific binding (Cursor, Aider)

## Manual launch

```bash
# A11y scan on localhost
bash tools/a11y/a11y-scan.sh --target http://localhost:3000

# Token ledger with full display
python3 tools/analytics/show-session-tokens.py --full

# UTC now (cross-platform Python — preferred)
python3 tools/temporal/utc-now.py
# or via bash shim (backward-compat, bash required)
bash tools/temporal/utc-now.sh

# Temporal Context Injection
python3 tools/temporal/build-temporal-context.py --task-started-at <UTC-ts> --session-id <uuid4>

# Rebuild temporal state from events
python3 tools/temporal/rebuild-state-from-events.py --task-id <TSK-id>

# Commit without AI attribution (ai_attribution_policy.suppress_ai_traces)
python3 tools/vcs/sm_commit.py "messaggio commit" [path]
# or via bash shim (backward-compat, bash required)
bash tools/vcs/sm-commit.sh "messaggio commit" [path]
```

> **Cross-platform (Windows / macOS / Linux):** the `.py` scripts in
> `tools/temporal/` and `tools/vcs/sm_commit.py` run natively on all
> platforms (Python 3.9+, stdlib only). The `.sh` files are retro-compat
> shims that require bash. See [`tools/README-windows.md`](README-windows.md)
> for platform-specific invocation and the `sm_commit.py` non-interactive
> gate.
