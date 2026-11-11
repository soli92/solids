---
name: accessibility-testing-protocol
description: Skill procedurale a11y — 5 step (Adapter Detect → run_a11y_scan → Severity+WCAG mapping → Manual Checks → Report Standard). Capability opt-in v2.18, PATTERN §3 Accessibility Scan.
---
# Protocollo Accessibility Testing — scan WCAG 2.2 AA in 5 step

Skill procedurale fondante della capability Accessibility Testing (EP-007): incapsula la
conoscenza operativa per eseguire uno scan WCAG 2.2 AA tramite il tool `run_a11y_scan`
(US-025, `tools/a11y/a11y-scan.sh`). È caricabile al bisogno da `fe-dev`, `qa-dev` e
`a11y-specialist` — istanza del pattern [[thin-agents-fat-skills-refactor]]: la conoscenza vive nella
skill (fat), gli agenti restano thin e non duplicano la procedura.

**Regola di neutralità** (architrave dell'intera skill, ADR-016 §G,
[[wcag-automated-coverage-limit]]): lo scan automatico copre solo una frazione dei criteri
WCAG. Questa skill **non dichiara mai conformità** e **non usa "0 errori" come proxy di
conformità**. La sezione Manual Checks non è **mai** vuota.

È un'**operazione opzionale** (PATTERN §3 «Accessibility Scan»), attiva solo con la
capability EP-007 abilitata. A capability spenta la skill è no-op (R.P3 opt-in totale).

Riferimenti: ADR-014 (3 modalità d'uso: `qa-dev` post-Develop / `fe-dev` inline /
`a11y-specialist` standalone — no owner unico), ADR-015 (fallback mobile/non-web inline),
ADR-016 (regola di neutralità + config block + Check 4o). Runbook narrativo source-of-truth:
[`wiki/runbooks/accessibility-testing-runbook.md`](../../wiki/runbooks/accessibility-testing-runbook.md).
Wiki: [[accessibility-testing-capability]].

[^src: management/kanban/EP-007-accessibility-testing-capability/US-024-skill-accessibility-testing-protocol/US-024.md §Business Rules]
[^src: design_&_architecture/decisions/ADR-014.md §Decisione]
[^src: design_&_architecture/decisions/ADR-015.md §Decisione]

---

## Step 1 — Adapter Detect

**Input**: `target` (URL, path build, file componente, o target non-web), `include_interactive`.

**Azione** — rileva lo stack del target con la cascata (pseudocodice):

```
if target is URL http/https AND server raggiungibile:
    adapter = "live"
elif build/preview disponibile localmente:
    adapter = "local-server"
elif file componente isolato AND harness disponibile:
    adapter = "component-harness"
elif target è mobile / React Native / non-web:
    adapter = "fallback-non-web"        # → vedi sezione «Fallback mobile / non-web»
else:
    adapter = "static-review"           # fallback, coverage ridotta
```

**Output**: `{target, adapter, include_interactive}`.

**Criterio di completamento**: `adapter` risolto a uno dei 5 valori; per gli adapter web
(`live`/`local-server`/`component-harness`/`static-review`) si procede allo Step 2, per
`fallback-non-web` si esegue la sezione dedicata.

---

## Step 2 — Invoke run_a11y_scan

**Input**: `{target, adapter}` dallo Step 1.

**Azione**: invoca il tool `run_a11y_scan` (US-025) con
`{target, standard: "wcag22aa", include_interactive}`.

- **Fail-loud se il tool non è disponibile** (messaggio verbatim):

  > Tool `run_a11y_scan` mancante: vedi US-025 / wiki/runbooks/accessibility-testing-runbook.md §Setup dipendenze

- Riusa l'infrastruttura **Playwright di EP-005** (ADR-008) se già installata: una sola
  install di Playwright serve sia il visual oracle sia lo scan a11y.

**Output**: JSON grezzo del tool (`summary`, `automated_findings`, `manual_checks`,
`positive_findings`).

**Criterio di completamento**: il tool ritorna JSON valido (exit 0), oppure fail-loud sul
prerequisito mancante.

---

## Step 3 — Severity + WCAG mapping

**Input**: `automated_findings` grezzi dello Step 2.

**Azione** — per ogni violazione, assegna la severity secondo la tassonomia:

- **Critical** — blocca l'uso per una categoria di utenti.
  *Esempi*: contenuto non raggiungibile da tastiera; immagine essenziale senza testo
  alternativo; form non completabile da screen reader.
- **Major** — ostacolo serio ma aggirabile.
  *Esempi*: contrasto insufficiente (1.4.3); label di campo mancante; heading di pagina assente.
- **Minor** — attrito o best practice non rispettata.
  *Esempi*: ordine heading non ottimale; ridondanza ARIA; landmark mancante non bloccante.

Ogni finding include il **criterio WCAG** (es. `"1.4.3"`) + un **fix concreto suggerito**.

**Output**: `automated_findings` arricchiti `{id, severity, wcag, location, description, suggested_fix}`.

**Criterio di completamento**: ogni finding ha severity ∈ {Critical, Major, Minor}, criterio
WCAG e fix suggerito.

---

## Step 4 — Manual Checks compilation

**Input**: lista delle verifiche manuali residue per WCAG 2.2 AA.

**Azione** — compila la lista dei check manuali principali (focus order, color meaning,
timing, reflow, target size, ecc.), ciascuno con criterio WCAG di riferimento.

- **INVARIANTE** (ADR-016 §G): anche se `automated_findings` è **vuota**, questa sezione
  **NON è mai vuota**. Lo scan automatico non copre tutti i criteri; ciò che il tool non può
  verificare resta esplicito come verifica manuale.
- Lo `status` di ogni voce è **sempre `to_verify`** — mai inferito come superato. Un check
  manuale non eseguito non è un check passato.

**Output**: `manual_checks: [{wcag, item, status: "to_verify"}, ...]` (lunghezza ≥ 1 sempre).

**Criterio di completamento**: `manual_checks` non vuota, tutti gli `status == "to_verify"`.

---

## Step 5 — Report Standard

**Input**: output arricchito degli Step 3 e 4.

**Azione** — produce il report nello **schema JSON di US-025** + una sintesi leggibile in
Markdown:

```json
{
  "target": "<url o path>",
  "standard": "wcag22aa",
  "summary": { "critical": 0, "major": 0, "minor": 0, "manual_checks": 1 },
  "automated_findings": [
    { "id": "color-contrast", "severity": "Major", "wcag": "1.4.3",
      "location": "...", "description": "...", "suggested_fix": "..." }
  ],
  "manual_checks": [
    { "wcag": "1.3.1", "item": "Verify semantic structure end-to-end", "status": "to_verify" }
  ],
  "positive_findings": []
}
```

- **Formula obbligatoria** (verbatim) quando non emergono errori automatici:

  > Nessun errore automatico rilevato; restano N verifiche manuali

  con **N ≥ 1 sempre** (N = `summary.manual_checks`).
- **Mai** usare "0 errori" come proxy di conformità. Il report descrive cosa è stato
  verificato automaticamente e cosa resta da verificare a mano — non emette un verdetto di
  conformità.

**Output**: report JSON + digest Markdown. Side-channel storage:
`code_quality/reports/<TSK-id>-a11y-iter-<N>.{json,md}` (riuso del path CQRL, ADR-016 §E).

**Criterio di completamento**: report JSON conforme allo schema + digest Markdown con la
formula di neutralità.

---

## Fallback mobile / non-web (ADR-015)

Branch della cascata dello Step 1: quando il target è mobile / React Native / non-web, il
motore di scan web non si applica. Procedura ridotta in 4 sub-step:

1. **Dichiarazione**: il report include
   `summary.coverage_note: "mobile/non-web target — copertura ridotta, motore web non applicato"`.
2. **Review statica** del codice sorgente: label/descrizioni accessibili, `accessibilityRole`,
   ordine di focus (`accessibilityViewIsModal`, `importantForAccessibility`), contrasto da
   design token (se DS disponibile).
3. **Raccomandazione strumenti nativi**: Accessibility Scanner (Android), Accessibility
   Inspector (iOS) — citati nel report come `manual_checks` con criterio WCAG + `status: to_verify`.
4. **`automated_findings: []`** (motore web non applicato), ma **`manual_checks` popolato**
   (caso più estremo della regola di neutralità: copertura automatica 0% → 100% manuale).

Dettaglio narrativo + esempi React Native:
[`wiki/runbooks/accessibility-testing-runbook.md`](../../wiki/runbooks/accessibility-testing-runbook.md).

[^src: design_&_architecture/decisions/ADR-015.md §Decisione]

---

## Fallback contenuto autenticato

Quando il target richiede autenticazione: preferire uno **staging con bypass**; se non
disponibile, usare un utente di test dedicato con step di login nell'adapter Playwright
(`page.fill()` + `page.click()`); riportare nel report
`summary.auth_note: "scan eseguita su sessione autenticata"`. Riferimento operativo nel
[runbook](../../wiki/runbooks/accessibility-testing-runbook.md).

---

## Pattern

- Istanza di [[thin-agents-fat-skills-refactor]]: la procedura vive qui (fat skill), consumata da più
  agenti thin (`fe-dev` inline, `qa-dev` post-Develop, `a11y-specialist` standalone — ADR-014,
  no owner unico).
- PATTERN.md §3 — operazione opzionale «Accessibility Scan».
- Regola di neutralità [[wcag-automated-coverage-limit]] (ADR-016 §G): manual_checks mai
  vuota, status sempre `to_verify`, niente dichiarazioni di conformità.

[^src: design_&_architecture/decisions/ADR-014.md §Decisione]
[^src: design_&_architecture/decisions/ADR-016.md §Decisione]
