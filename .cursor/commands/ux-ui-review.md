---
description: Invoca ux-ui-reviewer su un target (URL | TSK-id | path mockup | path componente) per review UX/UI contro rubrica + design system (EP-008 US-030). Separazione enforced dal designer (no auto-eval). Flag --ephemeral per non salvare.
argument-hint: <target> [--rubric=strict|loose] [--skip-a11y] [--ephemeral]
allowed-tools: Read, Write, Edit, Glob, Bash
---

Comando della capability [[ux-ui-review-design-capability]] (faccia **Review**, EP-008 US-030).
Delega la review UX/UI end-to-end (capture screenshot → estrazione token → conformità design
system → euristiche + flusso + UI visiva → richiamo a11y → report standard) all'agente
[ux-ui-reviewer](mdc:.cursor/rules/ux-ui-reviewer.mdc); con fallback sulla skill [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md) (US-028) quando l'agente non
è scaffoldato. Thin dispatcher, analogo a `/a11y` (EP-007) e `/review` (CQRL).

Riferimenti architetturali: EP-008 (`management/kanban/EP-008-ux-ui-review-design-capability/EP-008.md`),
ADR-019 (separazione strutturale reviewer/designer, no auto-eval), ADR-020 (storage side-channel +
frontmatter TSK `ux_ui_status:`). PATTERN §3 (operazioni opzionali), R.P3 (opt-in totale).

**Il reviewer non progetta**: per produrre wireframe/spec/flussi/copy usa `/ux-ui-design`
(`ui-designer`). I due agenti sono fisicamente distinti (separazione enforced, US-030 §Business Rules).

## Sintassi

```
/ux-ui-review <target> [--rubric=strict|loose] [--skip-a11y] [--ephemeral]
```

## `<target>` — 4 forme

| Forma | Esempio | Significato |
|---|---|---|
| **URL http/https** | `/ux-ui-review https://app.example.com/checkout` | route/sito live (capture + critica visiva) |
| **TSK-id** | `/ux-ui-review TSK-051` | recupera `code_path` / route dal frontmatter del TSK |
| **path mockup** | `/ux-ui-review designs/checkout-v2.png` | mockup statico (immagine / export Figma) |
| **path componente** | `/ux-ui-review src/components/Cart.tsx` | file componente isolato (harness o review statica) |

Con **TSK-id**: `Glob management/kanban/**/TSK-<id>.md`, leggi il frontmatter e deriva il target
dai `code_path` (o dalla route associata). Se il TSK non esiste → ABORT «TSK non trovato».

## Flag

- `--rubric=strict|loose` — default `strict`. In `strict` il comando è **fail-loud** se un finding
  non ha `rubric_ref` (riferimento alla rubrica anti-soggettività [[ux-ui-rubric-anti-subjectivity]]):
  un finding senza ancora oggettiva è un blocco, non un warning. In `loose` la mancanza di
  `rubric_ref` è un **warning** e la review procede (utile in fase esplorativa).
- `--skip-a11y` — default `false`. Se presente, il reviewer **non** invoca `run_a11y_scan` (utile
  se EP-007 non è attiva, o se l'a11y è già stata coperta in un altro contesto).
- `--ephemeral` — **non scrive** in `code_quality/reports/` (analogo a `/query --ephemeral`):
  il report è restituito solo in chat, non nel side-channel. L'entry su `wiki/log.md` viene
  comunque appesa.

## Comportamento

1. Read `factory.config.yaml.ux_ui`. Se `agents.reviewer: false` (o blocco assente) → la via
   agente è disabilitata; si tenta il fallback skill. Se la capability è interamente spenta →
   ABORT pulito; suggerisci «Abilita con `ux_ui.agents.reviewer: true`».
2. Risolvi `<target>` nelle 4 forme sopra (se `TSK-id`, deriva il target dal frontmatter del TSK).
3. **Invocazione** (con fallback discovery, ADR-019):
   - Se [ux-ui-reviewer](mdc:.cursor/rules/ux-ui-reviewer.mdc) è scaffoldato **e** `ux_ui.agents.reviewer: true` →
     invoca l'agente `ux-ui-reviewer` passando `target`, `rubric`, `skip_a11y`, `ephemeral`.
   - **Fallback** (agente non scaffoldato / `reviewer: false`): se la skill [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md)
     (US-028) è presente → la skill è invocata da fe-dev o qa-dev (chi è attivo nella
     topologia). La capability di review resta disponibile come skill anche senza agente dedicato
     (PATTERN §3, albero Tool/Skill/Agente).
   - Se né agente né skill esistono → fail-loud «Nessun agente disponibile per la review UX/UI;
     topologia non compatibile. Vedi `factory.config.yaml.topology` e `ux_ui.agents.reviewer`.»
4. L'agente/skill produce il report nello schema standard US-028, con ogni finding ancorato a un
   `rubric_ref` (distinzione problema oggettivo vs preferenza), eventuali domande aperte che
   richiedono contesto utente, e il richiamo alla capability a11y (salvo `--skip-a11y`).
5. Mostra in chat il verdict (`pass | conditional | reject`) + summary (finding per severità,
   N domande aperte). Su TSK-id, l'agente può aggiornare il solo campo frontmatter `ux_ui_status:`
   del TSK target (mai il corpo).

## Storage

- **Con TSK-id** → `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.{json,md}` (riuso path CQRL;
  lo slug `uxui-review` distingue dagli iter `a11y` / `visual` / CQRL).
- **Standalone / ad-hoc** (URL, mockup, componente) →
  `code_quality/reports/_adhoc/uxui-review-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`.
- **`--ephemeral`** → **nessuna scrittura** in `code_quality/reports/` (solo chat + log).

## Logging

Ogni invocazione appende a `wiki/log.md` (anche con `--ephemeral`) una entry nel formato canonico,
analogo alle entry `a11y` / `review`:

```
[YYYY-MM-DD HH:MM] ux-ui-review <target> → <verdict>
```

Inoltre l'agente scrive una riga in `memory/episodic/ux-ui-runs.md` (formato:
`YYYY-MM-DD-HH-MM | review | TSK-id|adhoc | verdict | rubric_violations_count`).

## Fallback (agente non scaffoldato)

Se l'agente `ux-ui-reviewer` **non** è scaffoldato ma la skill [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md)
(US-028) **sì**, il comando non fallisce: la skill è invocata da fe-dev o qa-dev attivi nella
topologia. La forma Agente è una comodità di delega, non un prerequisito della capability.

## Vincoli (R.P3 — opt-in totale)

- Comando **opt-in**: la sua assenza non è ERROR di lint (R.P3). Assenza di **entrambi** i file
  (agente + comando) → comportamento orchestrator identico a v2.17 (backward compat, 0 nuove
  ERROR/WARNING).
- **Il reviewer non progetta**: se gli viene chiesto di produrre un'alternativa di design, declina
  con il messaggio standard «Sono il reviewer, non posso progettare. Invocare `/ux-ui-design` o
  l'agente `ui-designer`.» (separazione enforced nel system prompt, ADR-019).
- L'agente non modifica il corpo dei TSK: al massimo il campo frontmatter `ux_ui_status:`
  (`pending|pass|conditional|reject`) del TSK target (single-writer logico, ADR-020).

Vedi l'agente [ux-ui-reviewer](mdc:.cursor/rules/ux-ui-reviewer.mdc), skill [ux-ui-review-protocol](mdc:.cursor/skills/ux-ui-review-protocol/SKILL.md), EP-008, ADR-019/020, e
[[ux-ui-review-design-capability]] per il contratto completo.
