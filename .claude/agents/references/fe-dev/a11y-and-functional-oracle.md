# a11y-and-functional-oracle — fe-dev (EP-007 + EP-018, opt-in)

**Ambito**: procedura dettagliata di (a) Accessibility Scan WCAG 2.2 AA inline e
(b) modalità fallback Functional Oracle per `fe-dev`. Due trigger distinti, aggregati
perché entrambi hanno `fe_correctness.enabled: true` come precondizione comune.
Foglia di dettaglio di `.claude/agents/fe-dev.md §T2`.

---

## Sezione A — Accessibility Scan (EP-007)

### Modalità 1 — inline Fase 4-bis (ADR-014 §Decisione, Trigger 1)

Lo scan a11y WCAG 2.2 AA gira **inline** durante la Visual Verification, riusando
l'infrastruttura di render headless già attiva — costo marginale near-zero.
È il check `axe-a11y` della Fase 3-bis (Structured Checks) di `visual-oracle-protocol`.

### Trigger (opt-in)

```
TSK.layer == 'fe'
AND factory.config.yaml.fe_correctness.enabled == true
AND factory.config.yaml.a11y.enabled == true
```

A queste condizioni il check `axe-a11y` della Fase 3-bis **delega** al tool
`a11y-scan.sh` (US-025, `run_a11y_scan`) usando la skill
`accessibility-testing-protocol` (US-024). Il fe-dev riceve gli `automated_findings`
e li include nei `critic_findings` se severity ≥ `a11y.severity_threshold` con
`wcag:` valorizzato (ADR-014 §File esistenti da estendere → fe-dev.md).

### No-op a flag spento

Se `a11y.enabled: false` (**default**) o il blocco è assente: il check `axe-a11y`
usa il check binario esistente di US-020 (v2.17 invariato). `a11y-scan.sh` non viene
mai invocato, nessun `a11y_status:`/`a11y_report:` è scritto. A
`fe_correctness.enabled: false` non si entra nemmeno in Fase 4-bis → a11y a fortiori no-op.

### Output (single-writer)

Il fe-dev — e solo lui in questo trigger — scrive `a11y_status: pending|pass|major|critical`
e `a11y_report: <path>` nel frontmatter TSK (PATTERN §5, ADR-014 §Schema dati).
Single-writer garantito dall'ordering inline → post-Develop → standalone (ADR-016 §Seriality):
se fe-dev ha già scritto `a11y_status`, qa-dev non lo sovrascrive.
Report side-channel: `code_quality/reports/<TSK-id>-a11y-iter-<N>.{json,md}`.

Cross-link: [ADR-014](../../../design_&_architecture/decisions/ADR-014.md),
[US-024](../../../management/kanban/EP-007-accessibility-testing-capability/US-024-skill-accessibility-testing-protocol/US-024.md),
[US-025](../../../management/kanban/EP-007-accessibility-testing-capability/US-025-tool-run-a11y-scan/US-025.md).

---

## Sezione B — Modalità fallback Functional Oracle (EP-018)

### Fallback se `qa-dev` non in topologia (ADR-067 §A)

Quando `fe_correctness.functional_oracle.enabled: true` ma `qa-dev` non è
scaffoldato nella topologia corrente, il `fe-dev` esegue la skill
`functional-oracle-protocol` come fallback — precedenza analoga ad ADR-014 per a11y.

### Trigger (fallback — opt-in)

```
factory.config.yaml.fe_correctness.functional_oracle.enabled == true
AND qa-dev NON scaffoldato in topologia (assente da .claude/agents/)
AND TSK.functional_acceptance_spec: valorizzato (o invocazione /functional-oracle)
```

Se `qa-dev` è in topologia, la modalità functional-oracle è esclusivamente di sua
competenza (ADR-067 §A): il fe-dev **non** esegue la skill e non scrive `functional_status:`.

### Comportamento

Identico alla modalità qa-dev: il fe-dev invoca `functional-oracle-protocol`,
il verdict è deterministico (asserzioni binarie, ADR-067 §B), il critic LLM è solo
advisory. Single-writer su `functional_status:` durante il fallback: in questo scenario è il fe-dev.

### No-op a flag spento

Se `functional_oracle.enabled: false` (**default**) o il blocco è assente: nessuna
invocazione della skill, nessun `functional_status:` scritto. Comportamento fe-dev
identico a v2.19.

Cross-link: [ADR-067](../../../design_&_architecture/decisions/ADR-067.md),
[ADR-014](../../../design_&_architecture/decisions/ADR-014.md),
[US-071](../../../management/kanban/EP-018-fe-functional-oracle/US-071-integrazione-ordering-qa-dev-config-frontmatter/US-071.md).
