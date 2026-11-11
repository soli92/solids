# Layer FE — Granularity Rule (dettaglio completo)

Ambito: dettaglio della sezione Layer FE Granularity Rule di `scrivi-task.md`. Leggere
prima di applicare la regola. Condizionale: solo per TSK con `layer: fe`.

---

> Sezione opt-in (US-022, Leva 5). Prompt preventivo di scomposizione per TSK FE troppo grossi.

**Regola (forma OR, VERBATIM).**

> Un TSK con `layer: fe` deve avere `estimate ≤ max_estimate_hours` OPPURE coprire al massimo
> `max_states` stati selezionati. Se ENTRAMBE violate, scomporre.

**Soglie default e configurabilità.** I default sono `{max_estimate_hours: 8, max_states: 3}` e
sono configurabili in `factory.config.yaml.fe_correctness.granularity.{max_estimate_hours, max_states}`.

**Pattern di scomposizione.** Quando la regola scatta, scomporre seguendo uno di questi pattern:

1. **Un componente per TSK** — se il TSK copre più componenti, splittare un TSK per componente.
2. **Stati uno per volta (o per gruppo coeso)** — se il TSK accumula troppi stati della State
   Matrix, verificare gli stati uno alla volta o a gruppi coesi.
3. **Integrazione come TSK separato** — isolare l'integrazione in un TSK dedicato, distinto dai
   TSK di costruzione dei singoli pezzi.

**Nota sulla divergenza OR (prompt) / AND (lint) — intenzionale.** Il prompt qui sopra usa **OR**
(preventivo, fase di scrittura): il TPM deve essere spinto a riflettere se anche solo una dimensione
è alta. Il lint **Check 4n** (US-022) usa invece **AND** (conservativo, fase di review): segnala
solo se ENTRAMBE le dimensioni sono alte. La divergenza è intenzionale: «scrittura strict (OR), lint
forgiving (AND)». Riferimento: ADR-011 §Rationale punto 3.
