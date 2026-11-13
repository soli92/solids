# Deep Functional Probe — Pattern di riferimento e ADR

**Ambito**: pattern architetturali e ADR di riferimento per `deep-functional-probe.md`.
Lettura consigliata per comprendere le scelte progettuali della skill;
non bloccante per l'esecuzione operativa.

---

## Pattern di riferimento

### Separazione spec-generation / runtime-execution

Questa skill incarna la separazione dichiarata in ADR-065 §A (framework vs contenuto
progetto): la generazione della spec (logica di dominio, stati, verifiche) è separata
dal runtime di esecuzione (serve, interazione, asserzioni binarie). Ogni layer è
aggiornabile indipendentemente. Un progetto che cambia framework FE non modifica
questa skill; un aggiornamento al runtime di interazione non modifica la logica di
generazione della spec.

### fail-closed (anti-fabbricazione)

Il verdetto nasce esclusivamente da asserzioni binarie deterministiche eseguite dal
delegato. Nessun LLM determina `PASS` o `FAIL`. Il blocco `evidence` richiede
riferimento obbligatorio a un artefatto reale — nessuna osservazione ammessa senza
provenance (coerente con ADR-063 §B). Un probe senza evidenza deterministica non può
emettere `PASS`.

### una AC per invocazione

Il probe verifica **una sola AC per invocazione**. Questo garantisce che evidenza e
rationale siano sempre riferiti a un singolo criterio osservabile, riducendo ambiguità
e facilitando il tracing dei risultati. Per target con più AC: invocare la skill N volte
e aggregare i verdetti nel chiamante.

---

## ADR di riferimento

| ADR | Rilevanza per questa skill |
|---|---|
| `ADR-065` | Schema acceptance-spec — 4 sezioni obbligatorie; 8 primitive domain-agnostic; semantica blocking/advisory; fail-loud su spec assente |
| `ADR-066` | Delega runtime a `interaction-drive-protocol`; ordering nel cascade |
| `ADR-067` | Verdict deterministico; critic LLM solo advisory; loop bounded |
| `ADR-063` | Evidence-provenance obbligatoria per ogni finding — nessuna osservazione senza artefatto reale |

[^src: design_&_architecture/decisions/ADR-065.md §A §C §E]
[^src: design_&_architecture/decisions/ADR-063.md §B]
[^src: design_&_architecture/decisions/ADR-067.md §B]
