---
name: lint-checks
description: Procedure dei 4 check eseguiti dal wiki-lint.
---
> **Struttura modulare EP-052**: i check dettagliati vivono in 10 file-famiglia
> indicizzati in `.claude/skills/lint-checks-index.md`. Questo file è il punto
> di ingresso (backward compat) e la spina dorsale dei check Class A (Check 1–4 base).
> Per i check di dettaglio ed estensioni opt-in, caricare i moduli tramite
> i trigger vincolanti nella sezione §Famiglie check — trigger vincolanti.

# Check del wiki-lint

Riferimenti: `citation-rules` (per la definizione di "claim non citato"),
`wiki-log-entry` (per il template del log report).

## Check 1 — Orphan + wikilink (scan unico)

1. `Glob wiki/**/*.md` (escludi `log.md`, `index.md`, `query/`, `lint/`).
2. Read `wiki/index.md`, estrai tutti i `[[…]]` e i path linkati.
3. Per ogni file: se non è linkato dall'index → **WARNING orphan**.
4. Read ogni pagina wiki: estrai `\[\[([^\]]+)\]\]`. Per ogni wikilink: verifica
   esista un file con slug corrispondente.
   - Wikilink che non risolve → **ERROR broken-link**.

## Check 2 — Claim senza fonte (sommario)

Per ogni `wiki/**/*.md`, identifica frasi affermative che richiedono citazione
(vedi `citation-rules` per soglia ≥ 20 parole ed esenzioni). Assenza di
`[^src: …]` o `[[…]]` entro 3 righe successive → **WARNING unsourced-claim**.
Dettaglio procedura, citation audit, heal-eligible e output: `lint-checks-citation.md`.

## Check 3 — Integrità kanban

Per ogni `management/kanban/EP-*/EP-*.md`:
- Frontmatter ha `id`, `title`, `status`, `priority`, `confidence`? Altrimenti **ERROR**.
- `id` matcha il pattern `EP-XXX` con XXX = nome cartella? Altrimenti **ERROR**.

Per ogni `US-*.md`:
- Frontmatter ha `id`, `title`, `role`, `priority`, `status`, `wiki_page`?
- `wiki_page` punta a file esistente? Altrimenti **ERROR**.

Per ogni `TSK-*.md` (v2.7):
- Frontmatter ha `id`, `sprint`, `layer`, `consumer`, `priority`, `estimate`, `status`?
- `id` univoco globalmente (cross-cartelle)?
- `layer` ∈ `{be, fe, db, qa, infra}` → altrimenti **ERROR invalid-layer**.
- `consumer` ∈ `{agent, human}` → altrimenti **ERROR invalid-consumer**.
- Campo legacy `team:` ancora presente → **WARNING deprecated-field** (v2.7,
  migrazione manuale a `layer:`).

## Check 4 — Coerenza wiki ↔ kanban

- Ogni US referenzia una pagina wiki: la pagina esiste?
- Ogni `## Storie collegate` in wiki ha solo storie esistenti?

---

## Famiglie check — Trigger vincolanti

> Ogni trigger è **fail-closed**: se il file manca → fermati e segnala. Non procedere
> con i check della famiglia se il modulo non è caricato.

### Always-on (eseguire sempre, indipendentemente dai flag config)

- Prima di eseguire i check di struttura wiki estesi (4ag, 4af, 4an e ext. Check 1),
  leggi obbligatoriamente `.claude/skills/lint-checks-wiki-structure.md`;
  se il file manca → fermati e segnala.
- Prima di eseguire i check kanban estesi (4g, 4b, 4m e ext. Check 3),
  leggi obbligatoriamente `.claude/skills/lint-checks-kanban.md`;
  se il file manca → fermati e segnala.
- Prima di eseguire i check di citazione (Check 2 dettaglio, Citation audit),
  leggi obbligatoriamente `.claude/skills/lint-checks-citation.md`;
  se il file manca → fermati e segnala.
- Prima di eseguire i check agente-QA (4ad, 4ae, 4ai, 4aj),
  leggi obbligatoriamente `.claude/skills/lint-checks-agent-qa.md`;
  se il file manca → fermati e segnala.
- Prima di eseguire i check di governance (4v, 4w, 4x, 4al, 4am),
  leggi obbligatoriamente `.claude/skills/lint-checks-governance.md`;
  se il file manca → fermati e segnala.

### Config opt-in (caricare solo se il flag corrispondente è attivo)

- Se `vcs.branch_awareness.enabled`, `kanban_publish.provider != none`
  o `content_share.enabled`: prima di eseguire i check config (4c, 4d, 4e, 4f, 4ah, 4ak),
  leggi obbligatoriamente `.claude/skills/lint-checks-config.md`;
  se il file manca → fermati e segnala.
- Se un flag `fe_correctness.*` è abilitato (es. `granularity_lint`,
  `a11y.required_on_fe_done`): prima di eseguire i check FE quality (4n, 4o, 4p, 4ac, 4y, 4ao),
  leggi obbligatoriamente `.claude/skills/lint-checks-fe-quality.md`;
  se il file manca → fermati e segnala.
- Se `compression.output.enabled` o `compression.context.enabled`:
  prima di eseguire i check compression (4s, 4u, 4aa, 4ab, 4ab-bis),
  leggi obbligatoriamente `.claude/skills/lint-checks-compression.md`;
  se il file manca → fermati e segnala.
- Se `fe_correctness.functional_oracle.enabled` o task analytics presenti nel kanban:
  prima di eseguire i check oracle-analytics (4z, 4q, 4r),
  leggi obbligatoriamente `.claude/skills/lint-checks-oracle-analytics.md`;
  se il file manca → fermati e segnala.

### EP-065 Fleet Discipline (always-on — Check 4at)

- Prima di eseguire il check disciplina d'ingresso capability (4at),
  leggi obbligatoriamente `.claude/skills/lint-checks-agent-fleet.md`;
  se il file manca → fermati e segnala.

### EP-060 Fleet Health (opt-in `refactor_agent_skills.enabled`)

- Se `refactor_agent_skills.enabled: true`: prima di eseguire il check fleet health (4ap),
  leggi obbligatoriamente `.claude/skills/lint-checks-agent-fleet.md`;
  se il file manca → fermati e segnala.

---

## Check eseguiti da script — si eseguono e si citano, non si stimano

Questi check hanno un'implementazione eseguibile che legge **tutta** la popolazione. Per
loro l'esecutore lancia lo script e ne riporta le righe (`- [SEVERITA][codice][check] ...`)
cosi' come sono: non produce finding propri, non campiona, non stima. Se lo script fallisce
li marca `NON ESEGUITO` con l'errore, senza sostituirli con una stima.

```bash
python3 tools/lint/run-deterministic.py --out wiki/lint/YYYY-MM-DD-deterministic.md
```

| Check | Script (anche singolarmente, `--json`) |
|---|---|
| 1, 4, 4ag | `python3 tools/lint/check-wiki-structure.py [--oggi YYYY-MM-DD]` |
| 3, 4as, 4b | `python3 tools/lint/check-kanban-integrity.py` |
| 4au | `python3 tools/lint/check-status-rollup.py` |
| 4am | `python3 tools/lint/check-version-coherence.py` |
| 4ar | `python3 tools/lint/check-expired-sunset.py .` |
| 4aq | `python3 tools/lint/check-portable-paths.py` |
| 4ax | `python3 tools/lint/check-submodule-ignore.py .` |
| 4bb | `python3 tools/lint/check-log-append-guard.py [--storia N] .` |
| 4bc | `python3 tools/lint/check-gap-closures.py .` |
| 4bd | `python3 tools/lint/check-gaps-append-guard.py [--storia N] .` |
| 4be | `python3 tools/lint/check-date-lavoro.py .` |
| 4bf, 4bg | `python3 tools/lint/check_dati_derivati.py .` |
| 4bh | `python3 tools/lint/check_evidenza_test_be.py --root .` (regola `lint.kanban.be_test_evidence`, default off) |
| 4j | `python3 tools/lint/check_target_tsk.py --root .` (regola `lint.kanban.tsk_target`, default off) |

Gli script applicano le regole di queste skill come sono scritte. Exit 0 sempre (il lint
riporta, non blocca); `--strict` da' exit 1 se c'e' almeno un ERROR. `--root <path>` esegue
su un'altra factory o su uno snapshot. Tutti gli altri check restano a lettura.

Le regole dei Check 1, 3, 4 e 4au che variano per factory (campi obbligatori e raccomandati,
severita' del layer, ID duplicati, scope sui soli aperti, orfani per raggiungibilita', campi data)
si dichiarano nel blocco `lint:` di `factory.config.yaml`; senza blocco valgono quelle del master
(`tools/lint/lint_comune.py`, `REGOLE_DEFAULT`). I check della sola factory si aggiungono in
`tools/lint/checks_locali.py` (lista `CHECKS`, script relativo alla radice): il runner li esegue
dopo i propri e l'upgrade non li tocca. La loro documentazione sta in
`.claude/skills/references/lint-checks-locali/<check>.md` (stessa ragione: cartella che il master non ha).

## Ordine di esecuzione consigliato

0. `tools/lint/run-deterministic.py` — i check della tabella qui sopra, in un colpo
1. Check 1 + `lint-checks-wiki-structure.md` — struttura, wikilink, 4ag/4af/4an
2. Check 2 + `lint-checks-citation.md` — citazioni, citation audit, output report
3. Check 3 + `lint-checks-kanban.md` — kanban integrità, 4g/4b/4m
4. Check 4 (coerenza wiki ↔ kanban, corpo kanban)
5. `lint-checks-governance.md` — 4v/4w/4x/4al/4am (sempre)
6. `lint-checks-agent-qa.md` — 4ad/4ae/4ai/4aj (sempre)
7. `lint-checks-config.md` — 4c/4d/4e/4f/4ah/4ak (se flag config attivi)
8. `lint-checks-fe-quality.md` — 4n/4o/4p/4ac/4y/4ao (se flag FE attivi)
9. `lint-checks-compression.md` — 4s/4u/4aa/4ab/4ab-bis (se compression attivo)
10. `lint-checks-oracle-analytics.md` — 4z/4q/4r (se oracle/analytics attivi)
11. `lint-checks-agent-fleet.md` — 4at (sempre) + 4ap (se `refactor_agent_skills.enabled`)
