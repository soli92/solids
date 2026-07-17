# Skill: Citation Rules

> Adapter Cursor della skill `citation-rules` definita in PATTERN.md.

# Regole di citazione (canoniche)

Questa è la **single source of truth** della grammatica citazioni della factory.
Tutte le altre skill ([scrivi-wiki-page](mdc:.cursor/skills/scrivi-wiki-page/SKILL.md),
[scrivi-epica](mdc:.cursor/skills/scrivi-epica/SKILL.md),
[scrivi-user-story](mdc:.cursor/skills/scrivi-user-story/SKILL.md),
[scrivi-task](mdc:.cursor/skills/scrivi-task/SKILL.md),
[ingest-protocol](mdc:.cursor/skills/ingest-protocol/SKILL.md),
[lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md),
[query-protocol](mdc:.cursor/skills/query-protocol/SKILL.md)) rimandano qui.

## Forme

| Forma | Quando | Esempio |
|---|---|---|
| `[^src: <path>.{md,txt} §<sez>]` | Citazione fonte testuale (raw o wiki) su claim ≥ 20 parole; `<sez>` è un header markdown del file citato | `[^src: raw/2026-05-15-spid.txt §Autenticazione]` |
| `[^src: <path>.kb.json §<dotted-path>]` (v2.9) | Citazione fonte strutturata JSON; `<dotted-path>` segue convenzioni v2.9 (vedi sotto) | `[^src: raw/2026-05-21-figma-ABC.kb.json §screens[0]]` |
| `[[<slug>]]` | Link interno wiki, senza estensione, senza `../` | `[[oidc]]`, `[[circuit-breaker]]` |
| `[^code: <path>:<line>]` | Citazione codice (solo factory, non progetto host) | `[^code: .cursor/rules/wiki-keeper.mdc:15]` |

### Grammatica `<dotted-path>` per JSON (v2.9)

Solo notazioni leggibili a mano; vietato JSONPath complesso (no `$.`), no JMESPath, no
wildcards. Forme ammesse:

- **Chiavi punto-separate**: `§project.name`, `§tokens.colors`, `§extraction_metadata.status`
- **Indice positivo per array**: `§screens[0]`, `§flows[2].steps[0]`
- **Selettore per chiave** (sintassi `[<chiave>=<valore>]`, valore alfanumerico o
  con `-`/`_`): `§components[name=Button]`, `§screens[id=42]`
- **Combinazioni**: `§screens[id=42].components[0]`

Una citazione JSON è considerata valida se: il file esiste; è JSON parsabile;
navigando il path si raggiunge un nodo esistente (verificato dal lint Check 4e
in audit periodico).

## Quando una citazione è obbligatoria

Una citazione è obbligatoria per ogni **claim non triviale**, definito come:

- Frase affermativa di **≥ 20 parole**, oppure
- Frase che asserisce un fatto verificabile (nome, numero, data, standard, decisione)
- Frase che cita uno standard normativo (SPID, OIDC, OAuth2, SAML, eIDAS, FHIR, GDPR, HL7, ISO/IEC, RFC numerati)

**Esenzioni** (non richiedono citazione):

- Header markdown (`#`, `##`, ...)
- Voci di lista TODO o checklist
- Frontmatter YAML
- Blocchi di codice
- Frasi imperative del template (es. "Aggiungi una sezione X")

## Disciplina cascade (per layer)

La citazione segue la cascata dei layer (vedi `PATTERN.md §1`):

| Layer | Cita |
|---|---|
| `wiki/` | `raw/<file>.txt §<sez>` |
| `management/kanban/EP-*/` | `wiki/<file>.md §<sez>` |
| `management/kanban/EP-*/US-*/` | `wiki/<file>.md §<sez>` |
| `design_&_architecture/` | `management/kanban/EP-*/US-*/US-*.md §<sez>` (storie, non concept) |
| `management/kanban/**/TSK-*.md` | `design_&_architecture/<file>.md §<sez>` o US/ADR |

Regola **cascade**: ogni agente cita la layer immediatamente sopra di sé, **anche
se ha letto la wiki** per contesto. [lead-architect](mdc:.cursor/rules/lead-architect.mdc) può aprire `wiki/concepts/oidc.md`
per capire cosa significa OIDC, ma nell'ADR cita la user story, non il concept.

## Wikilink: regole

- Slug **senza estensione** e **senza path**: `[[oidc]]`, mai `[[wiki/concepts/oidc.md]]` né `[[../../concepts/oidc.md]]`.
- Slug case-sensitive, lowercase con `-` come separatore.
- Un wikilink che non risolve a un file esistente = `ERROR broken-link` (rilevato dal [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md) Check 1).

## Anti-pattern (vietati)

| Anti-pattern | Perché vietato | Correzione |
|---|---|---|
| Path relativo `../../concepts/foo.md` | Si rompe al refactor della cartella | Usa `[[foo]]` |
| Citazione su frase < 20 parole non normativa | Rumore, non aggiunge valore | Ometti |
| Citazione fonte inventata | Viola §7 r.2 "zero invenzione" | Usa `wiki/gaps.md` |
| Citazione cross-cascade (es. ADR cita concept) | Rompe la disciplina cascade | Cita la layer sopra (storie, non concept) |
| `[^src: ...]` senza `§<sezione>` | Impossibile verificare il claim | Aggiungi sempre la sezione |

## Verifica

Il [wiki-lint](mdc:.cursor/rules/wiki-lint.mdc) (Check 2 di [lint-checks](mdc:.cursor/skills/lint-checks/SKILL.md)) controlla periodicamente:

1. Ogni claim ≥ 20 parole ha citazione adiacente (entro 3 righe).
2. Il path citato esiste.
3. La sezione `§<sez>` esiste (header markdown matching) nel file citato.

Violazioni: **WARNING unsourced-claim** (Check 2) o **ERROR broken-citation**
(audit periodico in `wiki/lint/YYYY-MM-DD-citation-audit.md`).
