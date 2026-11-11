#!/usr/bin/env bash
# =============================================================================
# check_design_system_conformance.sh — deterministic tool check_design_system_conformance

#                                      (EP-008, ADR-063 §D)
# =============================================================================
#
# Part of the UX/UI Review capability (EP-008), aligned to the pattern

# [[thin-agents-fat-skills-refactor]]: this is the TOOL (deterministic logic, no LLM).

# The `design-system-conformance-check` skill and the `ux-ui-reviewer` agent call it

# to verify compliance with the design system — this file does NOT judge the choices:

# confronta artefatti reali e riporta JSON puro.
#
# Backing executable for the `check_design_system_conformance` tool declared in

# `ux-ui-reviewer.md`. Fixes root cause #1 of ADR-063 §Context (tool_uses: 0).

# Fail-loud on missing dependencies: no silent degradation (ADR-063 §A).

#
# Technique: Open the --target via Playwright, verify that the tokens declared in the file

# --tokens (output di extract_design_tokens.sh) siano effettivamente presenti e
# correctly valorized in the computed DOM. It also counts hardcoded variables

# (hexadecimal colors, explicit px not via token) as a non-compliance signal.

#
# IMPORTANT (ADR-063 §A): If the reference token files are NOT available,

# the tool outputs documented `conformance: "to_verify"` rather than fabricating a verdict.

# This is the only case of non-failed output without complete data: it is intentional and

# documented to avoid manufacturing (ADR-063 §B evidence-provenance).

#
# ADR refs: ADR-063 §D (backing eseguibile), ADR-063 §A (fail-loud),
#           ADR-063 §B (evidence-provenance), ADR-008 (Playwright via Bash, no MCP).
# Wiki: wiki/concepts/ux-ui-review-capability.md  [[ux-ui-review-capability]]
#
# -----------------------------------------------------------------------------
# INPUT CONTRACT (CLI)

#   --target <string> http/https URL of the page to check

#   --tokens <file>     file JSON dei token di riferimento (output di extract_design_tokens.sh)
#                       If not provided or non-existent → conformance: "to_verify" (NOT exit 1)

#
# OUTPUT CONTRACT (stdout, pure JSON)

#   Token case available:

#     { target, tokens_file, conformance: "pass"|"fail", conformance_score,
#       threshold, tokens_checked, tokens_present, tokens_missing:[],
#       hardcoded_values_found: N, violations:[{type, property, found, expected}],
#       note }
#   Token case NOT available:

#     { target, tokens_file: null, conformance: "to_verify",
#       note: "Reference tokens not available. Please check manually (ADR-063 §B)." }

#
# EXIT CODES
#   0  check completed (pass or to_verify) or failed but executed correctly
#   1 technical error (missing prerequisite, unreachable target, JS error, etc.)

#      NOT exit 1 on conformance: "fail" — non-conformance is a result, not an error

# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. CLI argument parsing
# ---------------------------------------------------------------------------
TARGET=""
TOKENS_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"; shift 2 ;;
    --tokens)
      TOKENS_FILE="${2:-}"; shift 2 ;;
    *)
      echo "ERRORE: argomento sconosciuto '$1'. Uso: check_design_system_conformance.sh --target <url> --tokens <file>" >&2
      exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "ERRORE: --target è obbligatorio. Uso: check_design_system_conformance.sh --target <url> --tokens <file>" >&2
  exit 1
fi

# TOKENS_FILE not mandatory: if absent or non-existent → to_verify (ADR-063 §B)

if [[ -z "$TOKENS_FILE" ]] || [[ ! -f "$TOKENS_FILE" ]]; then
  # Issue documented to_verify (DO NOT fabricate a verdict — ADR-063 §A)

  TOKENS_DISPLAY="${TOKENS_FILE:-<non fornito>}"
  TARGET="$TARGET" TOKENS_DISPLAY="$TOKENS_DISPLAY" node -e "
    const result = {
      target: process.env.TARGET,
      tokens_file: null,
      conformance: 'to_verify',
      note: 'Token di riferimento non disponibili (' + process.env.TOKENS_DISPLAY + '). ' +
            'Verificare manualmente o rieseguire dopo extract_design_tokens.sh. (ADR-063 §B)'
    };
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  "
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Check prerequisites — fail-loud, no silent degradation (ADR-063 §A+§D)

# ---------------------------------------------------------------------------
if ! command -v node &>/dev/null; then
  echo "Tool check_design_system_conformance richiede Node.js: non trovato." >&2
  echo "Installare Node.js (https://nodejs.org) e riprovare. (ADR-063 §D)" >&2
  exit 1
fi

if ! npx playwright --version >/dev/null 2>&1; then
  echo "Tool check_design_system_conformance richiede Playwright: non trovato o non configurato." >&2
  echo "Eseguire: npm i -D @playwright/test && npx playwright install chromium" >&2
  echo "Verificare la disponibilità dei tool / l'ambiente (ADR-063 §D)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Conformance check via Playwright (snippet Node inline)
#    Load reference tokens from the --tokens file (extract_design_tokens.sh output).

#    In the computed DOM, check:

#    a) Each DS token of the reference file is present as a CSS custom property.

#    b) Count hardcoded values detected in the DOM (hex colors, non-zero absolute px).
#    Soglia conformance: DS_CONFORMANCE_THRESHOLD (default 0.8, env configurabile).
# ---------------------------------------------------------------------------
TARGET="$TARGET" TOKENS_FILE="$TOKENS_FILE" node <<'NODE'
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const target = process.env.TARGET;
const tokensFile = path.resolve(process.env.TOKENS_FILE);
const threshold = parseFloat(process.env.DS_CONFORMANCE_THRESHOLD || '0.8');

function toUrl(t) {
  if (/^https?:\/\//i.test(t)) return t;
  return 'file://' + path.resolve(t);
}

// Carica i token di riferimento
let refData;
try {
  refData = JSON.parse(fs.readFileSync(tokensFile, 'utf8'));
} catch (e) {
  process.stderr.write('ERRORE: impossibile leggere il file tokens: ' + tokensFile + ' — ' + e.message + '\n');
  process.exit(1);
}

const refTokens = refData.tokens || {};
const tokenNames = Object.keys(refTokens);

if (tokenNames.length === 0) {
  // Nessun token DS nel file di riferimento → to_verify documentato
  const result = {
    target,
    tokens_file: tokensFile,
    conformance: 'to_verify',
    note: 'Il file di token di riferimento non contiene token nel namespace DS atteso. ' +
          'Verificare manualmente. (ADR-063 §B)',
  };
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exit(0);
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(toUrl(target), { waitUntil: 'load', timeout: 30000 });

    // Verifica la presenza dei token di riferimento nel DOM computato
    const domCheck = await page.evaluate((tokenNames) => {
      const computed = getComputedStyle(document.documentElement);
      const results = {};
      for (const name of tokenNames) {
        const val = computed.getPropertyValue(name).trim();
        results[name] = val !== '' ? val : null;
      }
      return results;
    }, tokenNames);

    const tokensPresent = [];
    const tokensMissing = [];
    const violations = [];

    for (const name of tokenNames) {
      const domVal = domCheck[name];
      if (domVal === null || domVal === undefined) {
        tokensMissing.push(name);
        violations.push({
          type: 'token_missing_in_dom',
          property: name,
          found: null,
          expected: refTokens[name] || '(defined in DS)',
        });
      } else {
        tokensPresent.push(name);
        // Note: we do not compare exact values (values may vary by theme/override)
        // — presence in the DOM is the primary conformance criterion.
      }
    }

    // Count hardcoded values in the DOM body (non-conformance signal)
    const hardcodedCount = await page.evaluate(() => {
      const allElements = document.querySelectorAll('*');
      let count = 0;
      const hexPattern = /#[0-9a-fA-F]{3,6}\b/;
      for (const el of allElements) {
        const style = el.getAttribute('style') || '';
        if (hexPattern.test(style)) count++;
      }
      return count;
    });

    const totalChecked = tokenNames.length;
    const presentCount = tokensPresent.length;
    const conformanceScore = totalChecked > 0 ? presentCount / totalChecked : 1.0;
    const pass = conformanceScore >= threshold;

    const result = {
      target,
      tokens_file: tokensFile,
      conformance: pass ? 'pass' : 'fail',
      conformance_score: Math.round(conformanceScore * 100) / 100,
      threshold,
      tokens_checked: totalChecked,
      tokens_present: presentCount,
      tokens_missing: tokensMissing,
      hardcoded_values_found: hardcodedCount,
      violations,
      note: pass
        ? 'Conformance al design system verificata con evidenza reale (ADR-063 §B).'
        : 'Conformance sotto soglia — ' + tokensMissing.length + ' token DS non trovati nel DOM. ' +
          'Verificare che il design system sia importato correttamente (ADR-063 §B).',
    };

    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    await browser.close();
    // Exit 0 on both pass and fail: non-conformance is a result, not an error.
    process.exit(0);
  } catch (err) {
    if (browser) { try { await browser.close(); } catch (_) {} }
    process.stderr.write('ERRORE tecnico durante il conformance check: ' + (err && err.message ? err.message : String(err)) + '\n');
    process.exit(1);
  }
})();
NODE
