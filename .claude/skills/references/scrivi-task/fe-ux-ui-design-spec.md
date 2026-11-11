# Layer FE — UX/UI Design Spec (dettaglio completo)

Ambito: dettaglio della sezione Layer FE UX/UI Design Spec di `scrivi-task.md`. Leggere
prima di allegare il campo `ui_design_spec`. Condizionale: solo se esiste un deliverable Design.

---

> Sezione opt-in (US-032, capability EP-008). Procedura per il **TPM** per allegare al frontmatter
> di un TSK FE il campo `ui_design_spec: <path>` quando esiste un deliverable di Design.

**Quando suggerirlo.** Se per il componente target del TSK FE esiste un deliverable di Design
prodotto da `/ux-ui-design` (agente `ui-designer`) — tipicamente in
`code_quality/reports/<TSK-id>-uxui-design.json` o `code_quality/reports/_adhoc/uxui-design-<...>`.

**Single-writer: il TPM (ADR-020 §A/§F).** Il `ui-designer` **suggerisce** il path nel proprio
output, ma NON modifica il frontmatter né il corpo del TSK. Evita race condition e mantiene il
TPM come owner del TSK schema.

**Procedura.**
1. Verifica se esiste un deliverable Design per il componente.
2. Se sì, aggiungi `ui_design_spec: <path>` al frontmatter del TSK FE.
3. Se il deliverable è adhoc e copre più componenti/TSK, scelta del TPM: può citarlo in più TSK.
4. Opzionalmente aggiungi una sezione `## Design Reference` nel corpo del TSK.

**Schema deliverable single-shot.** Il deliverable Design è **single-shot** per TSK (no iter-N).
Eventuali ridisegni sovrascrivono il file; il versioning vive in git. Il path resta stabile.

**Backward compat.** Un TSK FE **senza** `ui_design_spec:` resta pienamente valido: **0 ERROR di lint**.

[^src: design_&_architecture/decisions/ADR-020.md §A/§F]
