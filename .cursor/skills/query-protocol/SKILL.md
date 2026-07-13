# Skill: Query Protocol

> Adapter Cursor della skill `query-protocol` definita in PATTERN.md.

# Protocollo di Query

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (ogni risposta è citata), [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md)
(template `query`).

## Fase 0 — Bootstrap

- Read `wiki/index.md` per la mappa delle sezioni.
- Identifica entità chiave della domanda + tipo risposta atteso + 3-6 keyword.
- Read ultimo `wiki/log.md` (sezione `query`) per evitare duplicati.

## Fase 1 — Candidate pages

Ordine di priorità (dal più sintetico al più granulare):

1. `wiki/syntheses/` — risposte già consolidate cross-source
2. `wiki/concepts/` — concetti di dominio
3. `wiki/entities/` — persone, organizzazioni, prodotti
4. `wiki/sources/` — documenti raw ingeriti
5. `wiki/runbooks/` — playbook operativi
6. `wiki/incidents/` — post-mortem (solo se la domanda è operativa/storica)

Per ogni keyword, fai `Glob wiki/**/*<keyword>*.md` e raccogli i path
candidati. Read solo le pagine plausibili (max 6-8).

## Fase 2 — Sintesi

Componi la risposta seguendo questa struttura:

```markdown
# Risposta: <domanda riformulata>

<Risposta in 1-3 paragrafi>

## Fonti
- [[<pagina-1>]] §<sez>
- [[<pagina-2>]] §<sez>
[^src: wiki/<file>.md §<sez>]
```

Regole:
- Ogni asserzione cita secondo [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (`[^src: wiki/<file>.md §<sez>]`
  o `[[<pagina>]]`).
- **Se l'informazione non è in `wiki/`**: dillo esplicitamente. Mai inventare,
  mai cercare in `raw/` o altrove (il wiki-query ha scope di lettura ristretto
  a `wiki/**`).

## Fase 3 — Persistenza

Default: salva la risposta in `wiki/query/YYYY-MM-DD-<slug>.md`.

Con flag `--ephemeral`: rispondi solo in chat, **non** scrivere alcun file
(neanche `log.md`).

## Fase 4 — Log entry

Append a `wiki/log.md` secondo [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template `query`). Skippa se
`--ephemeral`.

## Fase 5 — Proposta synthesis (opzionale)

Se la risposta è candidata a essere **ri-asked** (domanda ricorrente, risposta
stabile cross-source) → proponi all'umano di promuoverla:

```
Questa risposta sembra una synthesis candidata. Vuoi promuoverla a
wiki/syntheses/<question-slug>.md? (Richiede invocazione di wiki-keeper.)
```

**Non promuovere mai autonomamente.** La promozione query → synthesis è
operazione semantica e va eseguita dal [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc).

## Scope di lettura (inviolabile)

[wiki-query](mdc:.cursor/rules/wiki-query.mdc) legge **solo** `wiki/**/*.md`. Mai:

- `raw/**` (rompe il grounding sulla wiki)
- `management/**` (rompe la cascade)
- `design_&_architecture/**` (rompe la cascade)
- `memory/**` (memoria è per orchestrator/altri)

Se la domanda richiede informazione fuori scope → rispondi:
"L'informazione richiesta vive fuori da `wiki/`. Posso solo dirti quello che
la wiki documenta su <topic>: ..."

## Anti-pattern (vietati)

| Anti-pattern | Correzione |
|---|---|
| Leggere `raw/` per "verificare" la wiki | Vietato. Se la wiki ha un gap, segnalalo via [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md). |
| Rispondere senza citazione | Vietato. Vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md). |
| Promuovere query → synthesis autonomamente | Vietato. Proponi all'umano, lascia agire [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc). |
| Inventare la risposta se la wiki tace | Vietato. Dillo esplicitamente. |
