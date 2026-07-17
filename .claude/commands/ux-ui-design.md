---
description: Invoca ui-designer su un brief per produrre wireframe/spec/flussi/copy con rationale e assunzioni esplicite (EP-008 US-030). Accessibilità by design; mai auto-valutazione (passa al reviewer). Flag --tsk, --ephemeral.
argument-hint: <brief> [--type=wireframe|component_spec|user_flow|copy] [--tsk=<id>] [--ephemeral]
allowed-tools: Read, Write, Edit, Glob, Bash
---

Comando della capability [[ux-ui-review-design-capability]] (faccia **Design**, EP-008 US-030).
Delega la produzione del deliverable di design end-to-end (obiettivo utente + design system →
wireframe/spec/flusso/copy → rationale + assunzioni esplicite → accessibilità by design)
all'agente [ui-designer](mdc:.cursor/rules/ui-designer.mdc); con fallback sulla skill [ux-ui-design-protocol](mdc:.cursor/skills/ux-ui-design-protocol/SKILL.md) (US-029) quando
l'agente non è scaffoldato. Thin dispatcher, faccia speculare di `/ux-ui-review`.

Riferimenti architetturali: EP-008 (`management/kanban/EP-008-ux-ui-review-design-capability/EP-008.md`),
ADR-019 (separazione strutturale designer/reviewer, no auto-eval), ADR-020 (storage side-channel +
frontmatter TSK `ui_design_spec:`). PATTERN §3 (operazioni opzionali), R.P3 (opt-in totale).

**Il designer non valuta il proprio output**: lo passa obbligatoriamente al reviewer. I due agenti
sono fisicamente distinti (separazione enforced, US-030 §Business Rules).

## Sintassi

```
/ux-ui-design <brief> [--type=wireframe|component_spec|user_flow|copy] [--tsk=<id>] [--ephemeral]
```

## `<brief>` — 2 forme

| Forma | Esempio | Significato |
|---|---|---|
| **stringa descrittiva** | `/ux-ui-design "flusso di onboarding a 3 step per utente mobile"` | brief inline |
| **path file brief.md** | `/ux-ui-design briefs/onboarding.md` | brief strutturato su file |

## Flag

- `--type=wireframe|component_spec|user_flow|copy` — default `wireframe`. Determina il tipo di
  deliverable prodotto dal designer.
- `--tsk=<id>` — collega il deliverable a un TSK FE esistente. Il designer **suggerisce** il campo
  frontmatter `ui_design_spec: <path>` al TPM (handoff), che lo committa; il designer non scrive
  direttamente il frontmatter del TSK. `Glob management/kanban/**/TSK-<id>.md`; se non esiste →
  ABORT «TSK non trovato».
- `--ephemeral` — **non scrive** in `code_quality/reports/` (analogo a `/query --ephemeral`):
  il deliverable è restituito solo in chat. L'entry su `wiki/log.md` viene comunque appesa.

## Comportamento

1. Read `factory.config.yaml.ux_ui`. Se `agents.designer: false` (o blocco assente) → la via
   agente è disabilitata; si tenta il fallback skill. Se la capability è interamente spenta →
   ABORT pulito; suggerisci «Abilita con `ux_ui.agents.designer: true`».
2. Risolvi `<brief>` nelle 2 forme sopra. Se `--tsk=<id>`, valida l'esistenza del TSK.
3. **Invocazione** (con fallback discovery, ADR-019):
   - Se [ui-designer](mdc:.cursor/rules/ui-designer.mdc) è scaffoldato **e** `ux_ui.agents.designer: true` →
     invoca l'agente `ui-designer` passando `brief`, `type`, `tsk`, `ephemeral`.
   - **Fallback** (agente non scaffoldato / `designer: false`): se la skill [ux-ui-design-protocol](mdc:.cursor/skills/ux-ui-design-protocol/SKILL.md)
     (US-029) è presente → la skill è invocata da fe-dev o qa-dev (chi è attivo nella
     topologia). La capability di design resta disponibile come skill anche senza agente dedicato
     (PATTERN §3, albero Tool/Skill/Agente).
   - Se né agente né skill esistono → fail-loud «Nessun agente disponibile per il design UX/UI;
     topologia non compatibile. Vedi `factory.config.yaml.topology` e `ux_ui.agents.designer`.»
4. L'agente/skill produce il deliverable nello schema standard US-029 (deliverable + rationale +
   assunzioni esplicite + note di accessibilità by design).
5. Mostra in chat il deliverable + il tipo prodotto. Su `--tsk=<id>`, l'agente emette il
   suggerimento `ui_design_spec: <path>` per il TPM (mai scrittura diretta del frontmatter TSK).

## Post-condizione (no auto-chain — gate umano)

Al termine, il comando **suggerisce di invocare `/ux-ui-review` sul deliverable prodotto**, ma
**non lo invoca automaticamente**: la review è un gate umano esplicito. Il designer non valuta mai
il proprio output (separazione enforced, ADR-019). Esempio di suggerimento in chat:

```
Deliverable prodotto: code_quality/reports/_adhoc/uxui-design-2026-06-04-12-10-onboarding.md
Prossimo passo suggerito (gate umano, no auto-chain):
  /ux-ui-review code_quality/reports/_adhoc/uxui-design-2026-06-04-12-10-onboarding.md
  # oppure, se collegato a un TSK:  /ux-ui-review --tsk=<id>
```

## Storage

- **Con `--tsk=<id>`** → `code_quality/reports/<TSK-id>-uxui-design.{json,md}` — **single-pass**:
  niente `iter-<N>`; una nuova esecuzione **sovrascrive** il file (versioning via git).
- **Standalone / ad-hoc** (brief inline o file senza `--tsk`) →
  `code_quality/reports/_adhoc/uxui-design-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`.
- **`--ephemeral`** → **nessuna scrittura** in `code_quality/reports/` (solo chat + log).

## Logging

Ogni invocazione appende a `wiki/log.md` (anche con `--ephemeral`) una entry nel formato canonico,
analogo alle entry `ux-ui-review` / `a11y`:

```
[YYYY-MM-DD HH:MM] ux-ui-design <brief> → <deliverable_type>
```

Inoltre l'agente scrive una riga in `memory/episodic/ux-ui-runs.md` (formato:
`YYYY-MM-DD-HH-MM | design | TSK-id|adhoc | deliverable | rubric_violations_count`).

## Fallback (agente non scaffoldato)

Se l'agente `ui-designer` **non** è scaffoldato ma la skill [ux-ui-design-protocol](mdc:.cursor/skills/ux-ui-design-protocol/SKILL.md)
(US-029) **sì**, il comando non fallisce: la skill è invocata da fe-dev o qa-dev attivi nella
topologia. La forma Agente è una comodità di delega, non un prerequisito della capability.

## Vincoli (R.P3 — opt-in totale)

- Comando **opt-in**: la sua assenza non è ERROR di lint (R.P3). Assenza di **entrambi** i file
  (agente + comando) → comportamento orchestrator identico a v2.17 (backward compat, 0 nuove
  ERROR/WARNING).
- **Mai auto-valutazione**: il designer non revisiona il proprio deliverable; lo passa al reviewer
  (post-condizione sopra, separazione enforced nel system prompt, ADR-019).
- L'agente non modifica il corpo dei TSK: al massimo **suggerisce** il campo frontmatter
  `ui_design_spec: <path>` al TPM, che lo committa (designer non è single-writer del frontmatter
  TSK, ADR-020).

Vedi l'agente [ui-designer](mdc:.cursor/rules/ui-designer.mdc), skill [ux-ui-design-protocol](mdc:.cursor/skills/ux-ui-design-protocol/SKILL.md), EP-008, ADR-019/020, e
[[ux-ui-review-design-capability]] per il contratto completo.
