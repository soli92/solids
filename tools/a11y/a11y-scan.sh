#!/usr/bin/env bash
# =============================================================================
# a11y-scan.sh — deterministic tool run_a11y_scan (EP-007, US-025, TSK-034)
# =============================================================================
#
# Part of the Accessibility Testing capability (EP-007), instance of the pattern
# [[thin-agents-fat-skills-refactor]]: this is the TOOL (deterministic logic, no LLM).
# The skill `accessibility-testing-protocol` (US-024) and agent `a11y-specialist`
# (US-026) invoke it by name — this file does NOT reason and does NOT declare
# conformance: it only emits pure JSON on stdout.
#
# PATTERN.md §3 — optional «Accessibility Scan» operation.
# Wiki: wiki/concepts/accessibility-testing-capability.md  [[accessibility-testing-capability]]
# Runbook setup: wiki/runbooks/accessibility-testing-runbook.md §Setup dipendenze
# ADR: ADR-014 (3 usage modes, no single owner), ADR-016 §G (neutrality rule),
#      ADR-008 (Playwright via Bash, no MCP — reuses EP-005 install).
#
# Implementation format: Bash (zero-setup, preferred) driving Playwright +
# axe-playwright via an inline Node snippet. Documented alternative:
# an equivalent `.claude/tools/a11y-scan.ts` with the same CLI/JSON contract
# can replace this file in TypeScript-first hosts (logic is identical;
# format choice is at the host project's discretion — ADR-014 §Consequences).
#
# -----------------------------------------------------------------------------
# INPUT CONTRACT (CLI)
#   --target <string>            URL http/https | build file path | build directory
#   --standard <string>          default "wcag22aa"
#   --include-interactive        boolean flag, default false (keyboard/focus/reflow checks)
#
# OUTPUT CONTRACT (stdout, pure JSON)
#   { target, standard, summary{critical,major,minor,manual_checks},
#     automated_findings[{id,severity,wcag,location,description,suggested_fix}],
#     manual_checks[{wcag,item,status}], positive_findings[] }
#
# EXIT CODES
#   0  scan completed (even with a11y findings: findings are not technical errors)
#   1  technical error (missing prerequisite, unreachable target, etc.)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. CLI argument parsing
# ---------------------------------------------------------------------------
TARGET=""
STANDARD="wcag22aa"
INCLUDE_INTERACTIVE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"; shift 2 ;;
    --standard)
      STANDARD="${2:-wcag22aa}"; shift 2 ;;
    --include-interactive)
      INCLUDE_INTERACTIVE="true"; shift ;;
    *)
      echo "ERRORE: argomento sconosciuto '$1'. Uso: a11y-scan.sh --target <url|path> [--standard wcag22aa] [--include-interactive]" >&2
      exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "ERRORE: --target è obbligatorio. Uso: a11y-scan.sh --target <url|path> [--standard wcag22aa] [--include-interactive]" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Prerequisite check — fail-loud, no silent degradation (ADR-008 §Rationale 5)
# ---------------------------------------------------------------------------
if ! npx playwright --version >/dev/null 2>&1; then
  echo "Tool run_a11y_scan richiede Playwright + axe-playwright. Eseguire: npm i -D @playwright/test axe-playwright && npx playwright install chromium. Vedi wiki/runbooks/accessibility-testing-runbook.md §Setup dipendenze." >&2
  exit 1
fi

# axe-playwright must be resolvable from node_modules (separate fail-loud)
if ! node -e "require.resolve('axe-playwright')" >/dev/null 2>&1; then
  echo "Tool run_a11y_scan richiede Playwright + axe-playwright. Eseguire: npm i -D @playwright/test axe-playwright && npx playwright install chromium. Vedi wiki/runbooks/accessibility-testing-runbook.md §Setup dipendenze." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Run scan via Playwright + axe-playwright (inline Node snippet)
#    axe config: runOnly tag = ["wcag2a","wcag2aa","wcag21aa","wcag22aa"]
#    Maps axe output → US-025 standard JSON schema.
#    Invariant (ADR-016 §G): manual_checks NEVER empty → default injection of
#    { wcag:"1.3.1", item:"Verify semantic structure end-to-end", status:"to_verify" }.
#    The tool does NOT declare conformance: no "compliant"/"conforme" string in output.
# ---------------------------------------------------------------------------
TARGET="$TARGET" STANDARD="$STANDARD" INCLUDE_INTERACTIVE="$INCLUDE_INTERACTIVE" node <<'NODE'
const { chromium } = require('playwright');
const { injectAxe, getViolations } = require('axe-playwright');

const target = process.env.TARGET;
const standard = process.env.STANDARD || 'wcag22aa';
const includeInteractive = process.env.INCLUDE_INTERACTIVE === 'true';

// Normalize target → URL navigable by Playwright.
// http/https URL → as-is; local file/dir path → file:// (host resolves the build).
function toUrl(t) {
  if (/^https?:\/\//i.test(t)) return t;
  const path = require('path');
  return 'file://' + path.resolve(t);
}

// axe severity (impact) → Critical/Major/Minor taxonomy per US-025/US-024.
function mapSeverity(impact) {
  switch (impact) {
    case 'critical': return 'Critical';
    case 'serious':  return 'Major';
    case 'moderate': return 'Minor';
    case 'minor':    return 'Minor';
    default:         return 'Minor';
  }
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.goto(toUrl(target), { waitUntil: 'load', timeout: 30000 });
    await injectAxe(page);

    const axeOptions = {
      axeOptions: { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } },
    };
    const violations = await getViolations(page, undefined, axeOptions);

    const automated_findings = [];
    const summary = { critical: 0, major: 0, minor: 0, manual_checks: 0 };

    for (const v of violations) {
      const severity = mapSeverity(v.impact);
      if (severity === 'Critical') summary.critical++;
      else if (severity === 'Major') summary.major++;
      else summary.minor++;
      const wcag = (v.tags.find(t => /^wcag\d/.test(t)) || '').replace(/^wcag/, '') || 'n/a';
      for (const node of (v.nodes.length ? v.nodes : [{ target: ['(document)'] }])) {
        automated_findings.push({
          id: v.id,
          severity,
          wcag,
          location: Array.isArray(node.target) ? node.target.join(' ') : String(node.target),
          description: v.help || v.description || v.id,
          suggested_fix: v.helpUrl ? `Vedi: ${v.helpUrl}` : 'Consultare la documentazione WCAG del criterio.',
        });
      }
    }

    // Manual checks: WCAG 2.2 AA criteria not automatable.
    const manual_checks = [
      { wcag: '1.3.1', item: 'Verify semantic structure end-to-end', status: 'to_verify' },
      { wcag: '1.4.3', item: 'Verify color is not the only means of conveying information', status: 'to_verify' },
    ];
    if (includeInteractive) {
      manual_checks.push(
        { wcag: '2.1.1', item: 'Verify all functionality is operable via keyboard only', status: 'to_verify' },
        { wcag: '2.4.3', item: 'Verify focus order is logical and predictable', status: 'to_verify' },
        { wcag: '1.4.10', item: 'Verify content reflows without loss at 320px width', status: 'to_verify' },
      );
    }
    // Invariant ADR-016 §G: manual_checks never empty.
    if (manual_checks.length === 0) {
      manual_checks.push({ wcag: '1.3.1', item: 'Verify semantic structure end-to-end', status: 'to_verify' });
    }
    summary.manual_checks = manual_checks.length;

    const result = {
      target,
      standard,
      summary,
      automated_findings,
      manual_checks,
      positive_findings: [],
    };
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    await browser.close();
    process.exit(0);
  } catch (err) {
    if (browser) { try { await browser.close(); } catch (_) {} }
    process.stderr.write('ERRORE tecnico durante lo scan a11y: ' + (err && err.message ? err.message : String(err)) + '\n');
    process.exit(1);
  }
})();
NODE
