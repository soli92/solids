---
skill: lint-checks-index
part_of: lint-checks (modular)
description: "Indice delle check-family del sistema modulare lint-checks"
---

# Lint Checks — Indice Modulare

> Questo file è l'indice del sistema modulare lint-checks. Per retrocompatibilità, il punto
> di ingresso canonico resta `.claude/skills/lint-checks.md`. Questo indice elenca tutte le
> check-family disponibili e i check che contengono.

Il wiki-lint carica tutti i moduli pertinenti. I file check-family sono autonomi e possono
essere caricati indipendentemente per contesti specializzati.

---

## Registry Check-Family

| File | Check inclusi | Severità principale | Righe |
|---|---|---|---|
| `lint-checks-wiki-structure.md` | Check 1, Check 4 base, 4ag, 4af, 4an, 4bb, 4bc, 4bd, 4bf, 4bg | ERROR/WARNING/INFO | ~90 |
| `lint-checks-kanban.md` | Check 3, 4g, 4b, 4m, 4as, 4be, 4bh, 4j | ERROR/WARNING | ~162 |
| `lint-checks-citation.md` | Check 2, Citation audit, Heal-eligible, Output report, Log entry | WARNING | ~86 |
| `lint-checks-config.md` | 4c, 4d, 4e, 4f, 4ah, 4ak, 4aq | ERROR/WARNING | ~245 |
| `lint-checks-governance.md` | 4v, 4w, 4x + Validation Schema header, 4al, 4am, 4ar | ERROR/WARNING | ~420 |
| `lint-checks-fe-quality.md` | 4n, 4o, 4p, 4ac, 4y, 4ao | WARNING | ~396 |
| `lint-checks-oracle-analytics.md` | 4z, 4q, 4r | ERROR/WARNING | ~206 |
| `lint-checks-compression.md` | 4s, 4u, 4aa, 4ab, 4ab-bis | WARNING | ~288 |
| `lint-checks-agent-qa.md` | 4ad, 4ae, 4ai, 4aj | ERROR/WARNING | ~267 |
| `lint-checks-agent-fleet.md` | 4ap, 4at, 4au | WARNING/ERROR | ~450 |
| `references/lint-checks-agent-fleet/check-4au.md` | Esecuzione 4au (script, G1/G2/G3, regole applicate, limiti) | — (foglia) | ~95 |

### Check eseguibili (EP-071 / US-324)

Si eseguono e si citano, non si stimano: `python3 tools/lint/run-deterministic.py`
(dettaglio e comandi singoli: `lint-checks.md` §Check eseguiti da script).

| Check | Script |
|---|---|
| 1, 4, 4ag | `tools/lint/check-wiki-structure.py` |
| 3, 4as, 4b | `tools/lint/check-kanban-integrity.py` |
| 4au | `tools/lint/check-status-rollup.py` |
| 4am, 4ar, 4aq | `tools/lint/check-version-coherence.py`, `check-expired-sunset.py`, `check-portable-paths.py` |
| 4bb, 4bc, 4bd | `tools/lint/check-log-append-guard.py`, `check-gap-closures.py`, `check-gaps-append-guard.py` |
| 4be | `tools/lint/check-date-lavoro.py` |
| 4bf, 4bg | `tools/lint/check_dati_derivati.py` (foglie `references/lint-checks-wiki-structure/check-4bf.md`, `check-4bg.md`) |
| 4bh, 4j | `tools/lint/check_evidenza_test_be.py`, `check_target_tsk.py` (foglie `references/lint-checks-kanban/check-4bh.md`, `check-4j.md`; default off) |

---

## Stato split

- [x] `lint-checks-wiki-structure.md` — creato (TSK-435)
- [x] `lint-checks-kanban.md` — creato (TSK-435); esteso con 4as (TSK-589, EP-064/US-253 — `assignee:` advisory, WARNING-only)
- [x] `lint-checks-citation.md` — creato (TSK-436)
- [x] `lint-checks-config.md` — creato (TSK-436)
- [x] `lint-checks-governance.md` — creato (TSK-436, include 4al EP-049 + 4am EP-052 + 4ar TR-9b4e7c02)
- [x] `lint-checks-fe-quality.md` — creato (TSK-436)
- [x] `lint-checks-oracle-analytics.md` — creato (TSK-436)
- [x] `lint-checks-compression.md` — creato (TSK-436)
- [x] `lint-checks-agent-qa.md` — creato (TSK-436)
- [x] `lint-checks-agent-fleet.md` — creato (TSK-540, EP-060 fleet health); esteso con 4at (TSK-653, EP-065/US-278 — disciplina d'ingresso capability, ERROR) e 4au (TSK-691, EP-068/US-296 — roll-up di stato TSK→US→epica, WARNING-only, always-on)

---

## Stato spine (EP-060 refactor pilot #8)

- [x] `lint-checks.md` — riscritto come spina dorsale ~119 righe (EP-060 TSK-546); 10 trigger
  vincolanti organizzati in 3 sezioni (always-on / config opt-in / EP-060 fleet); Check 1,
  Check 2 sommario, Check 3 base, Check 4 base conservati come Class A; foglie invariate.

---

## Riferimenti

- Piano modularizzazione: `design_&_architecture/lint-checks-modularization-plan.md`
- File principale (entry point, spine): `.claude/skills/lint-checks.md`
- TSK-434 (piano), TSK-435 (split parte 1), TSK-436 (split parte 2), TSK-437 (aggiornamento wiki-lint)
- TSK-540 (lint-checks-agent-fleet.md, 4ap EP-060), TSK-546 (spine refactor EP-060 pilot #8)
- TSK-589 (Check 4as in `lint-checks-kanban.md`, EP-064/US-253 — coerenza `assignee:` ↔ stato del TSK, WARNING-only)
- TSK-691 (Check 4au in `lint-checks-agent-fleet.md`, EP-068/US-296 — roll-up di stato TSK→US→epica, WARNING-only, always-on, foglia in `.claude/skills/references/lint-checks-agent-fleet/check-4au.md`)
