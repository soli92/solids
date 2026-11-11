# Layer FE — Functional Oracle (dettaglio completo)

Ambito: dettaglio della sezione Layer FE Functional Oracle di `scrivi-task.md`. Leggere
prima di allegare il campo `functional_acceptance_spec`. Condizionale: solo se esiste
un'acceptance-spec YAML.

---

> Sezione opt-in (US-071, EP-018). Procedura per il **TPM** per allegare al frontmatter di un TSK
> il campo `functional_acceptance_spec: <path>` quando esiste un'`acceptance-spec` YAML.

**Quando suggerirlo.** Se per il TSK esiste (o si intende creare) un'`acceptance-spec` YAML
che descrive fixture + scenario Playwright + asserzioni binarie (ADR-065 §B), la skill suggerisce:

```yaml
functional_acceptance_spec: code_quality/acceptance/<TSK-id>.acceptance.yaml
```

**Single-writer per campo.**

- `functional_acceptance_spec:` — **single-writer: TPM/progetto** (ADR-065 §Storage, ADR-067 §Config).
  Il TPM scrive questo campo al momento della creazione/aggiornamento del TSK.
- `functional_status:` — **single-writer: `functional-oracle-protocol`** (sub-skill di `qa-dev`,
  ADR-067 §A). Solo la skill di esecuzione scrive questo campo. Il TPM lo lascia assente o `pending`.

**Procedura (TPM).**
1. Verifica se esiste (o si intende produrre) un'`acceptance-spec` YAML per il componente/app.
2. Se sì, aggiungi `functional_acceptance_spec: <path>` al frontmatter del TSK.
3. Lascia `functional_status:` assente o a `pending`.
4. Opzionalmente aggiungi una sezione `## Acceptance Spec` nel corpo del TSK.

**Opzionalità e no-op a flag spento.**

- Se `fe_correctness.functional_oracle.enabled: false` (default) → i due campi sono **completamente
  no-op**: nessun agente li legge, nessun lint genera ERROR o WARNING.
- La loro **assenza** non genera mai ERROR di lint, indipendentemente dal flag (ADR-065 §E).
- Se `enabled: true` **e** `functional_acceptance_spec:` valorizzato ma il file non esiste →
  ERROR (spec referenziata assente; ADR-065 §E + Lint Check 4z.1).

**Backward compat.** Un TSK **senza** `functional_status:` e senza `functional_acceptance_spec:`
resta pienamente valido: **0 ERROR di lint** (R.P3 opt-in totale).

[^src: design_&_architecture/decisions/ADR-065.md §Storage §E]
[^src: design_&_architecture/decisions/ADR-067.md §A §Config]
