# Skill: Scrivi User Story

> Adapter Cursor della skill `scrivi-user-story` definita in PATTERN.md.

# Procedura per scrivere una User Story

Riferimenti: [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md) (cascade: la US cita la wiki), [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md)
(dettaglio mancante → gap o question).

## Path

`management/kanban/EP-XXX-<slug>/US-YYY-<slug>/US-YYY.md`

## Frontmatter (minimal, v2.11)

```yaml
---
id: US-YYY
title: <titolo>
role: <ruolo utente>
priority: high | medium | low
status: ready | blocked
wiki_page: wiki/<file>.md
blocked_by: []            # solo Q_NNN con Bloccante: hard
pending_clarification: [] # opzionale, v2.6 — Q_NNN soft aperte sulla US
depends_on: []            # v2.11: lista US prerequisite (es. [US-003, US-005]) — hard block
---
```

Note: `epic` non va — deducibile dalla folder padre.

Se aggiungi `risk_classification:`, vedi PATTERN §5 per lo schema completo (opt-in v2.16). Non duplicare qui.

### `depends_on` (v2.11)

- **`depends_on: [US-YYY, ...]`** — User Story prerequisite: l'arch e il TPM
  non taskizzano questa US finché tutte le US in lista non sono almeno in
  `status: ready` con AC stabili. Lo scheduler (PATTERN §18) usa questa lista
  per il DAG L3 (plan-level): US indipendenti possono essere lavorate in
  parallelo da branch di TSK distinti.
- Distinzione con `blocked_by` / `pending_clarification`:
  - `depends_on` = ordering causale fra US (US-005 *dipende* dalla US-003).
  - `blocked_by` / `pending_clarification` = Q aperte verso il dominio.
- Una US con `depends_on` non vuoto e tutte le US referenziate in `done` →
  semaforo verde per Arch/TPM.

### `blocked_by` vs `pending_clarification` (v2.6)

- `blocked_by: [Q_NNN]` → la US ha almeno una Q **hard** aperta che la cita.
  `status: blocked`, Arch/TPM non possono partire sulla US.
- `pending_clarification: [Q_NNN]` → solo Q **soft** aperte. La US resta
  `status: ready`, Arch può progettare annotando l'ADR con la stessa
  `pending_clarification:`, TPM può taskizzare.
- Una US può avere entrambe le liste valorizzate se è impattata sia da hard
  che da soft; in quel caso resta `blocked` finché tutte le hard non sono chiuse.

## Corpo

```markdown
# US-YYY — <Azione + Oggetto>

## Descrizione
Come <ruolo>, voglio <azione>, affinché <valore di business>.

## Business Rules
- Regola 1 (es: "Se il saldo è < 0, blocca l'invio")
- Regola 2

## UI Reference
[^src: wiki/concepts/<concetto>.md §<sez>]

## Acceptance Criteria
- [ ] Criterio oggettivo 1
- [ ] Criterio oggettivo 2

## Fonti
[^src: wiki/<file>.md §<sez>]
```

## Regole

- Tecnologia-agnostico: nessun framework/linguaggio.
- AC verificabili oggettivamente (no "deve essere veloce" → "risposta < 200ms").
- Dettaglio mancante in wiki/ → NON inventare:
  - Non-bloccante → [wiki-gap-protocol](mdc:.cursor/skills/wiki-gap-protocol/SKILL.md) (append a `wiki/gaps.md`)
  - Bloccante hard → [apri-question](mdc:.cursor/skills/apri-question/SKILL.md) con `**Bloccante:** hard`; la storia va in `status: blocked` con `blocked_by: [Q_NNN]`
  - Bloccante soft → [apri-question](mdc:.cursor/skills/apri-question/SKILL.md) con `**Bloccante:** soft`; la storia resta `ready` con `pending_clarification: [Q_NNN]`
- Citazioni: vedi [citation-rules](mdc:.cursor/skills/citation-rules/SKILL.md).
