# Skill: Scrivi Epica

> Adapter Cursor della skill `scrivi-epica` definita in PATTERN.md.

# Procedura per scrivere un'epica

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (cascade: l'epica cita la wiki).

## Path

`management/kanban/EP-XXX-<slug>/EP-XXX.md`

Slug: lowercase, spazi→`-`, rimuovi `()/'`, max 40 char.

## Frontmatter (minimal — ID e stato sempre, v2.11)

```yaml
---
id: EP-XXX
title: <titolo>
status: defined | in-progress | done
priority: high | medium | low
confidence: XX%
confidence_rationale: <1-2 frasi>
wiki_pages: [wiki/<file>.md]
created: YYYY-MM-DD
depends_on: []   # v2.11: lista EP prerequisite (es. [EP-001, EP-003])
---
```

Note: `stories` non va nel frontmatter — si deduce dalle sotto-cartelle `US-*/`.

Se aggiungi `risk_classification:`, vedi PATTERN §5 per lo schema completo (opt-in v2.16). Non duplicare qui.

### `depends_on` (v2.11)

- **`depends_on: [EP-XXX, ...]`** — Epiche prerequisite: input per il parallel
  scheduler a livello roadmap (PATTERN §18). Due epiche con `depends_on`
  disgiunti possono essere lavorate da team/agenti diversi in parallelo.
  Una epica con `depends_on` non vuoto e qualche EP referenziata `defined` o
  `in-progress` resta `defined`; transita a `in-progress` quando le sue
  prerequisite sono almeno `in-progress`.

## Corpo

```markdown
# EP-XXX — <Titolo>
> <Obiettivo in una riga>

## Obiettivo
<Cosa risolve, per chi, perché ora>
[^src: wiki/<file>.md §<sez>]

## Valore di business
<Outcome misurabile>

## Storie incluse
- [US-YYY](US-YYY-<slug>/US-YYY.md) — <titolo>
- ...

## Confidence: XX%
<Razionale: cosa abbiamo, cosa ci manca, perché lo score>

## Dipendenze
<EP-/US- bloccanti, gap aperti>
```

## Regole

- Confidence è obbligatorio. Score < 50% → epica in `roadmap.md` come Release 1.1+.
- Nessun tech detail: niente "Spring Boot", "PostgreSQL". Quella è materia di
  `lead-architect`.
- Citazioni: vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (cascade L3 → wiki).
