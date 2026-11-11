# `.claude/tools/` — compatibility shim only

**Canonical location:** [`tools/`](../../tools/) at the repository root (R.A6).

Every executable here MUST be a **thin wrapper** (≤20 lines) that `exec`s the
matching script under `tools/…`. Enforced by `tools/adapters/check-adapter-lag.py`.

| Prefer (canonical) | Shim (legacy) |
|---|---|
| `tools/analytics/show-session-tokens.py` | `.claude/tools/analytics/show-session-tokens.py` |
| `tools/analytics/harvest-session-tokens.py` | `.claude/tools/analytics/harvest-session-tokens.py` |
| `tools/runtime/suggest-next.py` | `.claude/tools/suggest-next.py` |
| `tools/a11y/a11y-scan.sh` | `.claude/tools/a11y-scan.sh` |
| `tools/temporal/*.sh` | `.claude/tools/temporal/*.sh` |
| `tools/visual/*.sh` | `.claude/tools/capture_screenshot.sh` etc. |

**Policy**
- New tools → only under `tools/<area>/`.
- New Claude Code hooks → call `tools/…` directly (see `.claude/settings.json`).
- Keep shims for factory upgrades / old docs that still cite `.claude/tools/…`.
