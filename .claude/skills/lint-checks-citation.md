---
skill: lint-checks-citation
part_of: lint-checks (modular)
family: citation
parent: lint-checks
description: "Check lint su citazioni, claim senza fonte, heal-eligible, output report — check-family citation"
---

# Lint Checks — Citation

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 2 (claim senza fonte), Citation audit (periodico), Classificazione heal-eligible, Output report, Log entry

Check ordinati per funzione: verifica citazioni → audit → heal eligibility → output.

---

## Check 2 — Claim senza fonte

Vedi `citation-rules` per la definizione canonica di "claim che richiede
citazione" (≥ 20 parole, esenzioni, ecc).

Procedura:
- Per ogni `wiki/**/*.md`, identifica frasi affermative che secondo
  `citation-rules` devono essere citate.
- Per ognuna: verifica che entro 3 righe successive (o nella stessa riga) ci sia
  un `[^src: …]` o un `[[…]]`.
- Assenza → **WARNING unsourced-claim**.

## Citation audit (periodico)

Per ogni `[^src: <path> §<sez>]` in `wiki/**`:
- Verifica che `<path>` esista.
- Verifica che `<sez>` sia presente (header markdown matching) nel file citato.
- Vedi `citation-rules` per la grammatica completa.

Output separato: `wiki/lint/YYYY-MM-DD-citation-audit.md`.

## Classificazione `heal-eligible` (deterministica)

Per ogni ERROR, marca `heal-eligible: true` SOLO se rientra nella whitelist
`heal-protocol`:

- `broken-wikilink` → eligible iff esiste slug `Y` con `fuzzy(X, Y) ≥ 0.90`.
- `missing-frontmatter-field` → eligible iff il campo è deducibile dal path
  (`type` da `wiki/<kind>/`, `id` da `EP-XXX|US-YYY|TSK-ZZZ`).
- `citation-section-mismatch` → eligible iff esiste header `H` nel file citato
  con `edit_distance(<sez>, H) ≤ 3`.
- `id-duplicate` → **mai** eligible (rischio di rompere riferimenti esterni).
- WARNING / orphan / claim non citato / contradiction / gap / `missing-blocking-level` / `stale-blocked-by` / `orphan-pending-clarification` → mai eligible (richiedono giudizio semantico).

## Output report

Path: `wiki/lint/YYYY-MM-DD-lint-report.md`

```markdown
---
type: lint
date: YYYY-MM-DD
heal_eligible_count: N
heal_eligible_categories: [broken-wikilink, missing-frontmatter-field, citation-section-mismatch]
---
# Lint Report — YYYY-MM-DD

## Riepilogo
| Check | Errors | Warnings |
|---|---|---|
| 1 — Orphan + wikilink | N | N |
| 2 — Claim senza fonte | N | N |
| 3 — Integrità kanban | N | N |
| 4 — Coerenza wiki↔kanban | N | N |
| 4b — Coerenza Q↔kanban (v2.6) | N | N |
| 4c — Coerenza topology (v2.7) | N | N |
| 4d — Coerenza VCS (v2.8) | N | N |
| 4e — Coerenza manifest↔raw (v2.9) | N | N |
| 4f — Coerenza Publisher (v2.10) | N | N |
| 4g — Coerenza scheduler/depends_on (v2.11) | N | N |
| 4ac — no-auto-eval UX/UI (v2.22, EP-024) | N | N |
| 4ad — TSK QA failed no classification (v2.22, EP-029) | N | N |
| 4ae — Quarantena stale QA (v2.22, EP-027) | N | N |
| 4ag — Staleness wiki pages (EP-031) | — | N |
| 4ah — Branch Awareness config coherence (EP-034) | — | N |
| 4ai — Agent Infrastructure Integrity | — | N |
| 4aj — Model Registry Consistency (INFO) | — | — |
| 4ak — content_share config integrity (EP-048) | — | N |
| 4al — CHANGELOG↔GATE-REPORT coerenza (EP-049) | N | N |

## ERROR meccanici (heal-eligible)
- [ERROR][broken-wikilink][heal-eligible] wiki/concepts/foo.md: `[[oidc-flow]]` → suggerito `[[oidc-flows]]` (fuzzy 0.95)
- [ERROR][missing-frontmatter-field][heal-eligible] wiki/sources/bar.md: manca `type`, deducibile da path → `source`

## ERROR non meccanici (manuali)
- [ERROR][id-duplicate] management/kanban/EP-002/US-013/US-013.md: id duplicato di US-007 (NON heal-eligible)

## WARNING (igiene, mai heal-eligible)
- [WARNING] wiki/concepts/orphan.md: pagina non linkata dall'index.
- [WARNING][missing-blocking-level] management/questions.md Q_003: campo `**Bloccante:**` assente, applico default `hard`.
- [WARNING][stale-blocked-by] management/kanban/EP-001/US-017/US-017.md: `blocked_by: [Q_001]` ma Q_001 è in `[RISOLTE]` dal 2026-05-19. Vedi `reconcile-needed` in `wiki/log.md`.
- [WARNING][orphan-pending-clarification] management/kanban/.../US-024.md: `pending_clarification: [Q_005]` ma nessun ADR cita Q_005.
```

## Log entry

Append a `wiki/log.md` secondo `wiki-log-entry` (template `lint`).
