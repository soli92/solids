# Skill: Apri Question

> Adapter Cursor della skill `apri-question` definita in PATTERN.md.

# Procedura per aprire una question

## Path
`management/questions.md` (file unico, append nella sezione `[APERTE]`).

Se il file non esiste, crealo con header:
```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: open
---
# Questions — <Progetto>

## [APERTE]

## [RISOLTE]
```

## Entry da aggiungere
```markdown
### Q_NNN — <titolo conciso>
**Origine:** [[<pagina-wiki>]]
**Tipo:** Requisito incompleto | Logica ambigua | Conflitto business
**Impatto:** ALTO | MEDIO | BASSO
**Bloccante:** hard | soft   <!-- default hard se omesso -->
**Domanda:** <testo>
**Epiche bloccate:** EP-XXX
**Storie bloccate:** US-YYY
[^src: wiki/<file>.md §<sez>]

---
```

### `Bloccante:` — granularità del gate L4 (v2.6, PATTERN.md §7 r.9)

- **`hard`** (default): blocca l'avvio di Arch+TPM sulle US dipendenti. Usalo
  quando la risposta cambia in modo non-additivo l'architettura, i contratti,
  gli standard normativi, o lo schema dati.
- **`soft`**: Arch può procedere annotando `pending_clarification: [Q_NNN]`
  nell'ADR; TPM può taskizzare le US **non** dipendenti da Q hard aperte.
  Usalo quando la risposta affina una scelta già presa o impatta solo dettagli
  di edge-case che non rompono il design principale.

Regola pratica: se la domanda invalida un ADR già accettato o cambia uno
standard tenant-driven (§11), è `hard`. Altrimenti è `soft`.

## Aggiornamento del file
- ID Q_NNN: sequenziale globale (Q_001, Q_002…).
- Se aggiungi una domanda → set `status: open` nel frontmatter + `updated: YYYY-MM-DD`.
- Frontmatter `status: open` resta finché esiste almeno una Q in `[APERTE]`,
  indipendentemente dal `blocking_level`.
- Quando l'umano risponde → sposta in `[RISOLTE]` con `**Data risoluzione:**`, `**Decisione:**`, `**Epiche/Storie sbloccate:**`. Se `[APERTE]` resta vuota → `status: resolved`.

## Effetti collaterali
- Per ogni storia in `Storie bloccate`: aggiorna il suo `US-YYY.md` con `status: blocked` (se Q è `hard`) e `blocked_by: [Q_NNN]`. Per Q `soft` la storia NON va a `blocked`: aggiungi solo `pending_clarification: [Q_NNN]` al frontmatter US.
- Quando Q passa a `[RISOLTE]`: rimuovi `Q_NNN` da `blocked_by`/`pending_clarification` di tutte le storie impattate e — se la lista resta vuota — riporta `status: ready`.
- Se la riconciliazione downstream non avviene contestualmente alla risposta (es. la Q è risolta tramite chiusura di un gap dal [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc)), il marker `reconcile-needed: US-XXX → Q_NNN closed` viene appeso a `wiki/log.md` dalla skill [propagate-resolution](mdc:.cursor/skills/propagate-resolution/SKILL.md); l'orchestrator lo surfaceizza in `/run`.
