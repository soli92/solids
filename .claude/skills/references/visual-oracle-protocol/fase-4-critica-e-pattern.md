# Fase 4 — Critica visiva e pattern evaluator-optimizer

Ambito: azione del critic, output `critic_findings`, rapporto con code-review-protocol e ordering. Foglia di `.claude/skills/visual-oracle-protocol.md` (testo originale spostato senza modifiche; la spina dorsale resta nella skill e prevale in caso di dubbio).

## Fase 4 — Critica Visiva

**Input atteso**: i PNG della Fase 3 + la specifica del TSK (body + eventuale
`visual_reference:` a frame Figma / screenshot di riferimento, ADR-012 §A).

**Azione**:

1. Il critic è lo **stesso `fe-dev`** che esegue una **passata di review multimodale**,
   **NON un sub-agent dedicato né `qa-dev`** (ADR-009 §Decisione). Tecnicamente è una
   **sub-skill** invocata inline nello stesso turn dell'agente: il fe-dev cambia «modalità
   mentale» da producer a critic tramite il prompt di questa fase.
2. Il fe-dev legge i PNG via **Read tool** (capacità multimodale nativa — nessun MCP
   custom multimodale, ADR-009 §Rationale 4).
3. **Prompt del critic** (verbatim):

   > Confronta il rendering con la specifica del TSK e produce una lista di difetti azionabili.

   Il critic confronta ogni PNG con: (a) il body / Technical Specs del TSK, (b) il
   `visual_reference:` se presente (frame Figma / screenshot reference).
4. Produce una lista preliminare di difetti, ciascuno strutturato (vedi Fase 5 per lo
   schema dei 5 campi).

**Output prodotto**: lista di difetti preliminare (`critic_findings`), uno per ogni
problema rilevato; lista vuota `[]` se nessun difetto.

**Criterio di completamento**: lista difetti prodotta (anche vuota).

Questa fase è un'istanza del pattern **evaluator-optimizer**: il producer (fe-dev) ha
scritto il codice, il critic (stesso fe-dev in review) critica lo screenshot, il producer
itera sul feedback. La fonte del pattern è
[`wiki/syntheses/fe-agent-correctness-strategy.md §Leva 1`](../../../../wiki/syntheses/fe-agent-correctness-strategy.md)
(«È un'istanza del pattern evaluator-optimizer: il producer scrive il codice, il reviewer
critica lo screenshot, il producer itera sul feedback»).

[^src: wiki/syntheses/fe-agent-correctness-strategy.md §Leva 1]
[^src: design_&_architecture/decisions/ADR-009.md §Decisione]

---

## Pattern — evaluator-optimizer

Questa skill è **un'istanza esplicita del pattern `evaluator-optimizer`**: un producer
genera un artefatto (il fe-dev scrive il codice del componente → rendering → screenshot),
un evaluator lo critica (lo stesso fe-dev in modalità review legge i PNG e produce difetti
azionabili), e il producer itera sul feedback in un loop bounded (conditional → re-Develop
→ nuovo visual oracle, max `max_iterations`).

È la **stessa famiglia di pattern** già istanziata da
[`code-review-protocol`](../../code-review-protocol.md) (CQRL v2.12, PATTERN §19): lì il
dev-agent produce, il code-reviewer critica il codice, il dev-agent fixa in loop bounded
da `code_quality.max_iterations`. Differenza chiave: qui producer ed evaluator sono lo
**stesso agente** (`fe-dev`) perché il critic visivo richiede la stessa conoscenza di
dominio del producer (componente FE, spec del TSK, design token) — vedi ADR-009 §Rationale
1. Il `code-review-protocol` invece splitta producer (dev-agent) ed evaluator
(`code-reviewer`) su due agent perché la review del codice è un asse ortogonale al dominio.

Ordering nel pipeline (ADR-013): **develop → visual-oracle → review**. Il rendering è più
fondamentale del codice (un componente con rendering rotto è inutile anche se il codice è
idiomatico), quindi il visual oracle è uno stage upstream rispetto al code review.

[^src: wiki/syntheses/fe-agent-correctness-strategy.md §Leva 1]
[^src: design_&_architecture/decisions/ADR-009.md §Decisione]
[^src: design_&_architecture/decisions/ADR-013.md §Punto 1]
