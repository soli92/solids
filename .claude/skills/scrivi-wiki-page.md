# Skill: Scrivi Wiki Page

> Adapter Cursor della skill `scrivi-wiki-page` definita in PATTERN.md.

# Procedura per scrivere una pagina `wiki/`

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (citazioni e wikilink), [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md)
(informazione assente).

## Path (karpathy-style)

- Source: `wiki/sources/<kebab-slug>.md` (uno per documento raw ingerito)
- Concept: `wiki/concepts/<kebab-slug>.md` (concetto di dominio)
- Entity: `wiki/entities/<kebab-slug>.md` (persona / organizzazione / prodotto)
- Synthesis: `wiki/syntheses/<kebab-question>.md` (risposta cross-source consolidata)
- Runbook: `wiki/runbooks/<kebab-slug>.md` (playbook operativo)
- Incident: `wiki/incidents/YYYY-MM-DD-<kebab-slug>.md` (post-mortem)

## Frontmatter minimo

```yaml
---
type: source | concept | entity | synthesis | runbook | incident | gap
sources: ["raw/YYYY-MM-DD-<slug>.pdf", ...]   # vuoto per syntheses puramente derivate
status: draft | review | approved
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [...]
---
```

## Struttura corpo

```markdown
# <Titolo>
> <Tesi centrale in una riga>

## Contesto
<Perché esiste questa pagina> [^src: raw/<data>-<nome>.txt §<sez>]

## Dettaglio
<Contenuto principale con citazioni>

## Figure e Diagrammi
[FIG-NN](../../raw/images/<data>-<nome>-fig-NN.md) — <didascalia>

## Concetti correlati
[[<concetto-correlato>]]

## Pagine collegate
[[<altra-pagina>]]

## Storie collegate
<!-- Sezione gestita dal product-manager — non modificare se sei wiki-keeper -->
```

## Regole stilistiche

- Citazioni e wikilink: vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (forma, soglia 20 parole, cascade).
- Informazione assente nei `raw/` → apri un gap (vedi [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md)),
  non inventare.
- Update di pagina già `review`: aggiungi `## Aggiornamenti (vYYYY-MM-DD)`,
  non sovrascrivere.
- No emoji nel contenuto wiki.
- No timestamp in prosa (vivono nel frontmatter).
