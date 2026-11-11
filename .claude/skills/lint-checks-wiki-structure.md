---
skill: lint-checks-wiki-structure
part_of: lint-checks (modular)
family: wiki-structure
parent: lint-checks
description: "Check lint su struttura pagine wiki — check-family wiki-structure"
---

# Lint Checks — Wiki Structure

> Parte del sistema modulare lint-checks. File principale: `.claude/skills/lint-checks.md`
> Contiene: Check 1 (orphan + broken-link), Check 4 base (coerenza wiki ↔ kanban), Check 4ag (staleness, always-on), Check 4af (embedding similarity, INFO/opt-in), Check 4bf/4bg (ordine del log, contatore Sources)

Check ordinati per severità: ERROR → WARNING → INFO.

---

## Check 1 — Orphan + wikilink (scan unico)

**Eseguibile** (anche Check 4 e 4ag): `python3 tools/lint/check-wiki-structure.py [--oggi YYYY-MM-DD]`,
dentro `tools/lint/run-deterministic.py`. Si riportano le righe, non si stimano ne' campionano.
La prima voce di Check 4 (`wiki_page` esistente) e' riportata dal Check 3 (`broken-wiki-page`).

1. `Glob wiki/**/*.md` (escludi `log.md` e i suoi archivi `log-*.md`, `index.md`, `query/`, `lint/`).
2. Read `wiki/index.md`, estrai tutti i `[[…]]` e i path linkati.
3. Per ogni file: se non è linkato dall'index → **WARNING orphan**.
4. Read ogni pagina wiki: estrai `\[\[([^\]]+)\]\]`. Per ogni wikilink: verifica
   esista un file con slug corrispondente.
   - Wikilink che non risolve → **ERROR broken-link**.

## Check 4 — Coerenza wiki ↔ kanban

- Ogni US referenzia una pagina wiki: la pagina esiste?
- Ogni `## Storie collegate` in wiki ha solo storie esistenti?

## Check 4ag — Staleness Threshold Wiki Pages (WARNING, always-on — EP-031 segnale economico)

**Trigger**: sempre attivo — nessun flag richiesto. Segnale economico complementare a Check 4af.
**Severità**: WARNING — blocca lint se sopra threshold critico (> 365 gg), altrimenti INFO.
**Audience**: maintainer che monitorano l'aggiornamento del corpus wiki.

### Razionale (ADR-EP031-001)

Implementa il segnale economico della piramide BM25→dense→LLM-judge: staleness è
gratuito, deterministico, zero falsi positivi del tipo "mapping errato", e scala a corpus
infinito senza costo API. Complementa Check 4af (embedding/LLM-judge) che rileva drift
semantico ma ha costo variabile.

### Algoritmo

1. **Scansiona** `wiki/**/*.md` (escludi `log.md` e i suoi archivi `log-*.md`, `lint/`, `sources/`, `index.md`).
2. **Leggi** il campo `updated:` (o `created:` se `updated:` assente) dal frontmatter YAML.
3. **Calcola** `age_days = today − updated`.
4. **Emetti** in base all'età:
   - `age_days > 365` → **WARNING** `[Check 4ag] STALE: <path> — ultimo aggiornamento <N> giorni fa (soglia: 365)`
   - `age_days > 180` → **INFO** `[Check 4ag] INFO: <path> — non aggiornata da <N> giorni (soglia: 180)`
   - `age_days ≤ 180` → skip silenzioso.
5. **Pagine senza `updated:` e senza `created:`** → **WARNING** `[Check 4ag] MISSING-DATE: <path>`.

### Invarianti

- **Zero API call**: staleness è puro confronto di date — nessuna dipendenza esterna.
- **Deterministico**: stessa wiki + stessa data → stesso output (diversamente da LLM-judge).
- **Non blocca il lint totale**: le WARNING 4ag non impediscono il completamento degli altri check.
- **Esclusione lint/ e sources/**: i report di lint e i sorgenti raw non sono soggetti a staleness check.

### Relazione con Check 4af

Check 4ag e 4af sono complementari, non alternativi:
- **4ag** (staleness) → segnale economico, always-on, rileva pagine non toccate → suggerisce revisione.
- **4af** (embedding/LLM-judge) → segnale semantico, opt-in, rileva contenuto obsoleto anche se recentemente modificato.

## Check 4af — Embedding Similarity Wiki vs PATTERN (INFO only, sperimentale — EP-031 research)

**Trigger**: `wiki_lint.semantic_check.enabled: true` (default: false → skip totale)
**Severità**: INFO — mai WARNING, mai ERROR. Non blocca pipeline. Non è criterio di gate.
**Audience**: maintainer e operatori che vogliono monitorare la deriva semantica della wiki.

### Algoritmo

1. **Scopri pagine candidate**: scansiona `wiki/**/*.md` con frontmatter `pattern_section: "§N"`.
   Pagine senza questo campo → skip silenzioso per quella pagina.
2. **Calcola embedding**: per ogni pagina candidata:
   - Embedding A = embedding del testo completo della pagina wiki.
   - Embedding B = embedding del testo della sezione `§N` estratta da `PATTERN.md`.
3. **Confronta similarità coseno**: `score = cosine_similarity(A, B)`.
4. **Emetti INFO se score < threshold** (default 0.75):
   ```
   INFO [Check 4af] wiki/concepts/compression-layer.md — §20 — score: 0.61 (< 0.75)
   ```
5. **Stima costo**: prima del scan, stima N_pagine × costo_per_embedding e confronta
   con `wiki_lint.semantic_check.cost_warn_usd`. Se costo_stimato > soglia → chiedi
   conferma esplicita (WARNING separato, non bloccante).
6. **Scrivi report** (se `output_report: true`):
   `<output_report_path>/wiki-lint-semantic-<YYYY-MM-DD>.md` — tabella con tutte le
   pagine sotto soglia ordinate per score crescente.

### Invarianti

- **No API call a flag spento**: `enabled: false` → zero chiamate embedding, zero side effect.
- **No ERROR mai**: questo check non cambia severità da INFO a WARNING/ERROR anche in futuro,
  finché EP-031 US-109 ADR non verte a GO con calibrazione validata.
- **Idempotente**: due run sulla stessa wiki e PATTERN.md producono lo stesso report.
- **Skip silenzioso su pagine senza `pattern_section:`**: non è un error, è una scelta del maintainer.

### Dipendenza esterna

Embedding API (Voyage-3 via Anthropic o configurabile via `embedding_model`). Se l'API
non è raggiungibile → WARNING separato + skip del check (graceful degradation, non fail-loud).

---

## Check 4bb — `wiki/log.md` append-only (WARNING, detective, always-on)

`python3 tools/lint/check-log-append-guard.py` (dentro `run-deterministic.py`): lancia
`tools/wiki/log_append_guard.py` sull'ultimo commit che tocca `wiki/log.md` (`--storia N` per gli
ultimi N). Una riga tolta o modificata senza che la stessa riga compaia in un archivio
`wiki/log-*.md` dello stesso commit e' una perdita silenziosa di entry (R.5): **WARNING**, mai
ERROR. Esenti righe vuote, frontmatter YAML e puntatore `> **Archivi:** ...` prima della prima
entry. Misura sulla storia del master (`--storia 400`): 372 commit, 13 segnalati (2 con entry
perse, recuperate in `wiki/log-recuperato-2026-10-16.md`).

- [WARNING][log-righe-rimosse][4bb] wiki/log.md: il commit <sha> ha tolto N righe (M entry) senza archivio ...

Cura: `python3 tools/wiki/recover_log_entries.py --commit <sha>` (dry-run senza `--apply`).
Il blocco *preventivo* e' un altro meccanismo, opt-in: hook `pre-commit` di
`tools/vcs/install_factory_hooks.py` con `wiki_lint.log_append_guard.hook: true`.

## Check 4bc — chiusure dei gap non verificate (WARNING, advisory, always-on)

`python3 tools/lint/check-gap-closures.py` (dentro `run-deterministic.py`): un gap di
`wiki/gaps.md` e' chiuso solo se il testo di chiusura rimanda a una pagina della wiki esistente
che cita una fonte `[^src: raw/...]` presente. Le chiusure «a parole» (senza pagina, pagina
assente, pagina senza fonte) sono **WARNING**, mai ERROR: contano come gap da trattare.
Riconosce i due formati di `gaps.md` (sezioni `## AAAA-MM-GG`, voci `- [ ]`/`- [x]`) e, in lettura,
le forme di chiusura storiche delle derivate: `**Risolto (data, contesto):**`, `**Superato:**`,
`~~CHIUSO~~` nel titolo (EP-084). Un duplicato che rimanda (`gaps.md:<riga>` o ID) a un gap chiuso
e verificato eredita la verifica: un solo passo, un rimando a un rimando non conta.
Dettaglio e filtri (`--tema`, `--check`): `python3 tools/wiki/verify_gap_closures.py`.

- [WARNING][gap-chiuso-non-verificato][4bc] wiki/gaps.md: N gap chiusi con motivo «...»

## Check 4bd — `wiki/gaps.md` append-only (WARNING, detective, advisory)

`python3 tools/lint/check-gaps-append-guard.py` (dentro `run-deterministic.py`): lancia
`tools/wiki/gaps_append_guard.py` sull'ultimo commit che tocca `wiki/gaps.md` (`--storia N` per gli
ultimi N). Ammesse le righe aggiunte, il cambio `- [ ]` -> `- [x]` e la sostituzione di una riga
`**Aggiornamento...**` con `**Risolto:**` nello stesso blocco di gap (regola D1 di
`wiki-gap-protocol`). Ogni altra riga tolta o modificata e' **WARNING**, mai ERROR; a differenza
del log non ha archivi e nessun hook di pre-commit.

- [WARNING][gaps-righe-rimosse][4bd] wiki/gaps.md: il commit <sha> ha tolto o modificato N righe ...

## Check 4bf e 4bg — ordine di `wiki/log.md` e contatore Sources (always-on)

`python3 tools/lint/check_dati_derivati.py .` (dentro `run-deterministic.py`). 4bf (ERROR): una voce del
log piu' vecchia di oltre 7 giorni della piu' recente che la precede. 4bg (WARNING): `## Sources (N)` di
`wiki/index.md` diverso dal numero reale di voci `- [[...]]`; no-op se la sezione manca. Dettaglio:
`references/lint-checks-wiki-structure/check-4bf.md`, `check-4bg.md`.

