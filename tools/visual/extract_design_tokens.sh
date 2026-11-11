#!/usr/bin/env bash
# =============================================================================
# extract_design_tokens.sh — deterministic tool extract_design_tokens (EP-008, ADR-063 §D)

# =============================================================================
#
# Part of the UX/UI Review capability (EP-008), aligned to the pattern

# [[thin-agents-fat-skills-refactor]]: this is the TOOL (deterministic logic, no LLM).

# The `design-tokens-extraction` skill and the `ux-ui-reviewer` agent call it

# to collect CSS tokens computed by the DOM — this file does NOT judge: it outputs pure JSON.

#
# Backing executable for the `extract_design_tokens` tool declared in `ux-ui-reviewer.md`.

# Resolves root cause #1 of ADR-063 §Context (tool_uses: 0 from no backing

# executable). Fail-loud on missing dependencies: no silent degradation (ADR-063 §A).

#
# Technique: Playwright opens the target, injects JS that reads the CSS custom properties

# computed from the DOM (:root and variants). Extracts variables with DS namespace (`--sd-*`,

# `--color-*`, `--spacing-*`, `--radius-*`, `--font-*`, `--shadow-*`, `--motion-*`).
# If the namespace is not known a priori, extract ALL custom properties and leave al

# calling agent for classification.
#
# ADR refs: ADR-063 §D (backing eseguibile), ADR-063 §A (fail-loud),
#           ADR-008 (Playwright via Bash, no MCP).
# Wiki: wiki/concepts/ux-ui-review-capability.md  [[ux-ui-review-capability]]
#
# -----------------------------------------------------------------------------
# INPUT CONTRACT (CLI)

#   --target <string> http/https URL of the page to inspect

#   --out <file>        file di output JSON (default: stdout)
#
# OUTPUT CONTRACT (JSON)

#   { target, tokens: { "<property-name>": "<computed-value>", ... } }
#
# EXIT CODES
#   0 extraction completed (tokens can be {} if target does not use custom properties)

#   1 technical error (missing prerequisite, target not reachable, etc.)

# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. CLI argument parsing
# ---------------------------------------------------------------------------
TARGET=""
OUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"; shift 2 ;;
    --out)
      OUT_FILE="${2:-}"; shift 2 ;;
    *)
      echo "ERRORE: argomento sconosciuto '$1'. Uso: extract_design_tokens.sh --target <url> [--out <file>]" >&2
      exit 1 ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "ERRORE: --target è obbligatorio. Uso: extract_design_tokens.sh --target <url> [--out <file>]" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Check prerequisites — fail-loud, no silent degradation (ADR-063 §A+§D)

# ---------------------------------------------------------------------------
if ! command -v node &>/dev/null; then
  echo "Tool extract_design_tokens richiede Node.js: non trovato." >&2
  echo "Installare Node.js (https://nodejs.org) e riprovare. (ADR-063 §D)" >&2
  exit 1
fi

if ! npx playwright --version >/dev/null 2>&1; then
  echo "Tool extract_design_tokens richiede Playwright: non trovato o non configurato." >&2
  echo "Eseguire: npm i -D @playwright/test && npx playwright install chromium" >&2
  echo "Verificare la disponibilità dei tool / l'ambiente (ADR-063 §D)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. CSS custom properties extraction via Playwright (Node inline snippet)

#    Reads the custom properties computed on :root and on document.documentElement.

#    Namespace DS riconosciuti: --sd-*, --color-*, --spacing-*, --radius-*,
#    --font-*, --shadow-*, --motion-*, --z-*, --size-*, --border-*.
#    Also extracts all properties not in known namespace (complete_dump = true).
# ---------------------------------------------------------------------------
TARGET="$TARGET" OUT_FILE="$OUT_FILE" node <<'NODE'
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const target = process.env.TARGET;
const outFile = process.env.OUT_FILE || '';

// Namespace DS attesi (pattern prefix): estesi dall'ADR-018 schema EP-008 soli-boy.
const DS_PREFIXES = ['--sd-', '--color-', '--spacing-', '--radius-', '--font-',
                     '--shadow-', '--motion-', '--z-', '--size-', '--border-'];

function toUrl(t) {
  if (/^https?:\/\//i.test(t)) return t;
  return 'file://' + path.resolve(t);
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(toUrl(target), { waitUntil: 'load', timeout: 30000 });

    // Inietta JS per leggere le custom properties computate dal DOM.
    const tokens = await page.evaluate((dsPrefixes) => {
      const result = {};
      const styles = document.styleSheets;
      const seen = new Set();

      // Metodo 1: scansione CSSStyleSheet rules
      for (const sheet of styles) {
        let rules;
        try { rules = sheet.cssRules; } catch (_) { continue; }
        for (const rule of rules || []) {
          if (rule.style) {
            for (let i = 0; i < rule.style.length; i++) {
              const prop = rule.style[i];
              if (prop.startsWith('--') && !seen.has(prop)) {
                seen.add(prop);
                const value = getComputedStyle(document.documentElement).getPropertyValue(prop).trim();
                result[prop] = value || rule.style.getPropertyValue(prop).trim();
              }
            }
          }
        }
      }

      // Metodo 2: computed style su documentElement (cattura variabili non in regole esplicite)
      const computed = getComputedStyle(document.documentElement);
      for (let i = 0; i < computed.length; i++) {
        const prop = computed[i];
        if (prop.startsWith('--') && !seen.has(prop)) {
          seen.add(prop);
          result[prop] = computed.getPropertyValue(prop).trim();
        }
      }

      return result;
    }, DS_PREFIXES);

    // Separate DS tokens from others (for traceability)
    const dsTokens = {};
    const otherTokens = {};
    for (const [k, v] of Object.entries(tokens)) {
      if (DS_PREFIXES.some(p => k.startsWith(p))) {
        dsTokens[k] = v;
      } else {
        otherTokens[k] = v;
      }
    }

    const result = {
      target,
      // Token in namespace DS noti — primo cittadino per check_design_system_conformance.sh
      tokens: dsTokens,
      // Token extra-namespace (utili per indagine manuale)
      tokens_other: otherTokens,
      ds_prefixes_checked: DS_PREFIXES,
    };

    const json = JSON.stringify(result, null, 2) + '\n';
    if (outFile) {
      fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
      fs.writeFileSync(path.resolve(outFile), json, 'utf8');
    } else {
      process.stdout.write(json);
    }

    await browser.close();
    process.exit(0);
  } catch (err) {
    if (browser) { try { await browser.close(); } catch (_) {} }
    process.stderr.write('ERRORE tecnico durante l\'estrazione dei token: ' + (err && err.message ? err.message : String(err)) + '\n');
    process.exit(1);
  }
})();
NODE
