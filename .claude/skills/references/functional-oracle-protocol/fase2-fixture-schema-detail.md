# Fase 2 — Load Fixture: path, schema, caricamento

**Ambito**: §2.1 risoluzione path spec, §2.4 validazione schema 4 sezioni obbligatorie,
§2.6 caricamento fixture. Le gate §2.3 (fail-loud spec assente) e §2.5 (verdict skip)
sono nel corpo principale di `functional-oracle-protocol.md`.
Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## §2.1 — Risoluzione path spec (2 modalità)

1. **Modalità frontmatter** (prioritaria): se il frontmatter TSK contiene
   `functional_acceptance_spec: <path>` → usa quel path come percorso assoluto o
   relativo al root del repo factory.
2. **Modalità default glob** (fallback): se `functional_acceptance_spec:` è assente o
   vuoto nel frontmatter TSK → cerca `code_quality/acceptance/<TSK-id>.acceptance.yaml`
   (per-TSK), poi `code_quality/acceptance/<app-slug>.acceptance.yaml` (per-app, dove
   `app-slug` è derivato dal `code_path` risolto).

Se nessuno dei due path produce un file leggibile → applicare la logica §2.3 fail-loud
(nel corpo principale).

[^src: design_&_architecture/decisions/ADR-065.md §B — schema acceptance-spec path]

## §2.4 — Validazione schema (4 sezioni obbligatorie)

Read il file spec trovato al §2.1. Valida che contenga le 4 sezioni obbligatorie
secondo `.claude/schemas/acceptance-spec.schema.yaml` (US-069):

| Sezione | Tipo | Obbligatoria |
|---|---|---|
| `fixtures` | array | SI |
| `scenario` | array | SI (può essere `[]`) |
| `assertions` | array | SI |
| `thresholds` | object con `advisory_max` | SI |

Se una o più sezioni sono assenti o hanno tipo errato → **fail-loud** con messaggio
che elenca le sezioni mancanti/invalide:

> Acceptance-spec `<path>` non valida: sezioni mancanti o mal formate: `<lista>`.
> Schema di riferimento: `.claude/schemas/acceptance-spec.schema.yaml`.
> Correggere il file prima di procedere.

[^src: design_&_architecture/decisions/ADR-065.md §B §C — schema/primitive]
[^src: .claude/schemas/acceptance-spec.schema.yaml]

## §2.6 — Caricamento fixture

Se spec valida e `scenario` non è vuoto: per ogni elemento in `fixtures[]` della spec,
il caricamento effettivo dei file (`set_input_files` e altre action) avviene tramite
`interaction-drive-protocol` (ADR-066 §B), invocato in Fase 3 all'azione `load_fixture`.

In questa fase (Fase 2) si verifica **solo** che i path dichiarati esistano sul filesystem:

```
Per ogni fixture in spec.fixtures:
  Verifica: file esiste al path <fixture.path> (relativo al root del repo/package)
  Se assente → fail-loud:
    "Fixture `<fixture.id>` non trovato al path `<fixture.path>`.
     Il file deve essere presente prima dell'esecuzione del functional oracle."
```

## Output prodotto

Spec letta e validata; `spec_path` risolto; `spec` parsed (oggetto YAML);
`fixture_paths` verificati sul filesystem. Pronto per Fase 3.

**Criterio**: spec valida (4 sezioni presenti), tutti i fixture dichiarati esistono sul
filesystem, `scenario` non vuoto.

[^src: design_&_architecture/decisions/ADR-065.md §B §E]
[^src: design_&_architecture/decisions/ADR-066.md §B — caricamento fixture via interaction-drive-protocol]
[^src: management/kanban/EP-018-fe-functional-oracle/US-068-skill-functional-oracle-protocol/US-068.md §Fase 2]
