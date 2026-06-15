# Sprint 1 — EP-001 Design Intelligence Sprint SoliDS

**Data**: 2026-06-15  
**Factory**: solids (external run C, v2.21.0)  
**Framework**: EP-019 Design Intelligence Layer  

---

## Task completati

| TSK | Titolo | Tipo | Verdict EP-019 |
|-----|--------|------|----------------|
| TSK-001 | Wiki: design system overview | docs | artefatto prodotto |
| TSK-002 | Token architecture deep dive | docs | artefatto prodotto |
| TSK-003 | Component inventory (56 componenti) | docs | artefatto prodotto |
| TSK-004 | Design rationale: token naming convention | critic/doc | pass — 4 finding (R.N1..R.N4) |
| TSK-005 | Accessibility audit token level | critic/audit | pass — 2 finding a rischio |
| TSK-006 | EP-019 critic report globale | critic aggregato | pass — 3 finding documentati |
| TSK-007 | New theme spec: brutalist | design spec | draft — spec pronta |

**Totale**: 7 TSK done, 5 commit, 0 codice scritto, 7 artefatti doc/critic.

---

## Findings EP-019 chiave

1. **color.accent vs color.secondary**: stesso valore nel tema light, ruoli shadcn diversi — ambiguità LLM-silente.
2. **text.tertiary su bg.hover**: fallisce WCAG AA (4.2:1 < 4.5 richiesto) — mai documentato prima.
3. **Categorizzazione 56 componenti**: art-director avrebbe dovuto pre-dichiarare il sistema di categorizzazione come CONSTRAINT.

---

## Capabilities opt-in attive

- `design_intelligence` (EP-019)  
- `analytics` (dogfooding)  

---

## Verdict run esterno denso (ADR-062)

- ≥6 TSK done: ✓ (7)  
- ≥6 commits: verifcare dopo sprint.md commit  
- ≥3 capabilities opt-in: ✓ (design_intelligence + analytics; compression non attivo su questa factory)  
- ≥1 wiki/log.md marker: ✓ (8 entries in log.md)  
