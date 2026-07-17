---
id: ep019-critic-report-solids
type: critic-report
title: "EP-019 Critic Report Globale — SoliDS"
status: done
created: 2026-06-15
updated: 2026-06-15
---

# EP-019 Critic Report Globale — SoliDS

**Sprint**: EP-001 Design Intelligence Sprint  
**Pattern**: EP-019 Design Intelligence Layer — critic report aggregato  
**Data**: 2026-06-15  
**Framework**: v2.21.0 (Run C)

---

## §1 — Cosa ha funzionato del pattern EP-019 su SoliDS

### 1.1 Art-director DSL come gate intenzionale

Ogni TSK ha iniziato con un ART-DIRECTOR STATEMENT (INTENT/PROBLEM/RATIONALE/CONSTRAINTS).
Il risultato concreto: le wiki pages prodotte hanno una prospettiva dichiarata, non solo
documentazione inerte. La `token-naming-convention.md` include un explicit "perché" per
ogni regola, non solo l'elenco delle regole.

### 1.2 Critic pass ha rilevato ambiguità LLM-silenti

Il critic su TSK-004 ha trovato 3 inconsistenze nel naming (`color.accent` vs `color.secondary`,
`space.md` vs `space.4`, `font.body` eccezione). Nessuna era documentata; un LLM consumer
di SoliDS avrebbe potuto usare token sbagliati silenziosamente.

### 1.3 A11y audit ha trovato coppie a rischio non documentate

TSK-005: `text.tertiary` su `bg.hover` fallisce WCAG AA. `intent.warning` su `intent.warning-bg`
borderline. Entrambe le coppie erano usate implicitamente ma non testate.

### 1.4 Separazione generatore/critico su ogni artefatto

Il flusso "genera → critica" ha prodotto output difendibili: ogni finding ha una severità,
una raccomandazione e un verdict. Nessun finding è rimasto aperto senza giudizio.

---

## §2 — Cosa ha richiesto iterazione / non ha funzionato

### 2.1 Component inventory: 56 componenti difficili da categorizzare automaticamente

**Capability impattata**: TSK-003 component-inventory  
**Sintomo**: 56 componenti con pattern shadcn/ui standard ma con wrapper custom SoliDS.
La categorizzazione (Layout/Form/Overlay/Navigation/Data) è stata soggettiva.  
**Risoluzione**: Usato pattern di categorizzazione Material Design 3 (già familiare al tema).  
**Lezione EP-019**: L'art-director deve pre-dichiarare il sistema di categorizzazione
come un CONSTRAINT, non lasciarlo emergere durante la generazione.

### 2.2 Contrasto colori: calcolo approssimato senza tool

**Capability impattata**: TSK-005 a11y audit  
**Sintomo**: Il critic pass richiede valori di contrasto WCAG precisi, ma l'ambiente
agent non ha accesso a un color contrast checker live. I valori sono stati stimati
dalla formula WCAG con aritmetica manuale.  
**Rischio**: I valori "approx" potrebbero avere errori del 3-5%.  
**Risoluzione**: Marcato come "approx" e raccomandato Storybook story per verifica live.  
**Lezione**: Per audit a11y su token, l'agente dovrebbe invocare un tool esterno
(es. `wcag-contrast` npm package) piuttosto che calcolare manualmente.

### 2.3 Finding non previsto: token semantici non coprono il dark theme per intent.warning

**Capability impattata**: a11y cross-tema  
**Sintomo**: L'audit del tema light ha trovato che `intent.warning` su `intent.warning-bg`
non supera AA. Nel tema dark, i valori cambiano. Non è stato analizzato se il dark theme
risolva o peggiori il problema.  
**Azione**: documentato come TODo per Sprint 2.

---

## §3 — Capability non esercitate in questo run

| Capability | Motivo |
|---|---|
| `visual-oracle` | No build Storybook in env agent |
| `code_quality CQRL` | Sprint knowledge-only, no codice scritto |
| `compression` | Config ON ma non stressata |
| `a11y scanner automatico` | No headless browser; audit manuale |

---

## §4 — Sintesi EP-019 value su SoliDS

SoliDS è un design system maturo (1.14.1, 56 componenti, 12 temi). L'EP-019 su una
base così consolidata ha prodotto:

1. **Documentazione difendibile**: 5 artefatti con rationale esplicito (non solo lista di fatti)
2. **Ambiguità emerse**: 3 inconsistenze naming, 2 coppie a11y a rischio — mai documentate prima
3. **Standard formalizzato**: naming convention con 4 regole (R.N1..R.N4) ora consultabili da LLM

**Finding non previsto EP-019 con più valore**: la scoperta che `color.accent` e `color.secondary`
hanno lo stesso valore nel tema light ma ruoli semantici diversi in shadcn/ui. Questo è
esattamente il tipo di ambiguità che un LLM consumer di SoliDS potrebbe sbagliare.

**Verdict globale EP-019 su SoliDS**: `pass` — pattern applicato integralmente, 2 finding
d'iterazione (categorizzazione + calcolo contrasto), 1 finding non previsto ad alto valore.
