# Skill: Wiki Gap Protocol

> Adapter Cursor della skill `wiki-gap-protocol` definita in PATTERN.md.

# Protocollo gap (canonico)

`wiki/gaps.md` è il **canale formale del feedback loop** della wiki (vedi
`PATTERN.md §10`). Tutti gli agenti L3+ possono e devono usarlo per segnalare
buchi nella knowledge base scoperti durante il loro lavoro.

## Caratteristiche del file

- **Append-only condiviso in scrittura** fra [product-manager](mdc:.cursor/rules/product-manager.mdc), [lead-architect](mdc:.cursor/rules/lead-architect.mdc),
  [tpm](mdc:.cursor/rules/tpm.mdc), [wiki-query](mdc:.cursor/rules/wiki-query.mdc). Lettura: tutti, ma [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) lo legge **obbligatoriamente
  all'inizio di ogni run** (Fase 0 di [ingest-protocol](mdc:.cursor/skills/ingest-protocol/SKILL.md)).
- **Chiusura riservata a [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc)**: solo l'analyst annota `**Risolto:**`.
- Vietato editare gap altrui, vietato cancellare gap risolti (resta storia).

## Formato gap (apertura)

Append a `wiki/gaps.md`:

```markdown
## YYYY-MM-DD HH:MM — <slug-gap>
**Origine:** <agente> @ <artefatto in lavorazione>
**Gap:** <cosa manca in wiki/>
**Sospetta fonte:** <raw da ingerire | "nessuna fonte chiara, serve nuovo raw">
**Impatto:** <quale produzione è frenata>
```

Esempio:

```markdown
## 2026-05-18 14:23 — payment-flow-3ds
**Origine:** lead-architect @ ADR-007-payment-gateway
**Gap:** wiki/ non ha pagina su 3D Secure 2.0. Serve descrizione flusso challenge/frictionless.
**Sospetta fonte:** raw/2026-04-20-emv-3ds-spec.txt (presente, mai ingerito)
**Impatto:** blocca scelta auth flow nell'ADR-007
```

## Slug

Il `<slug-gap>` segue la stessa regola dei wikilink: lowercase, `-` separatore,
max 40 char. Univoco fra i gap aperti (può ripetersi fra aperti e risolti).

## Bloccante vs non-bloccante

| Tipo | Azione apertura | Azione lavoro |
|---|---|---|
| **Non-bloccante** | Append a `gaps.md` | Continua il run citando lo stato corrente della wiki |
| **Bloccante** | Append a `gaps.md` + apri `Q_NNN` in `management/questions.md` con `/apri-question` | STOP: la storia/ADR/task impattato passa in `status: blocked` con `blocked_by: [Q_NNN]` |

La distinzione è giudiziaria, non automatica. Regola pratica: se l'agente può
produrre il proprio artefatto **citando l'assenza** (es: "Il flusso 3DS non è
documentato in wiki/; assumiamo redirect-based per ora"), il gap è non-bloccante.
Se l'artefatto **non può procedere** senza l'informazione, è bloccante.

## Chiusura (riservata a wiki-keeper)

All'inizio di ogni run, [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) legge `wiki/gaps.md`. Per ogni gap aperto:

1. **Coperto da raw esistente** → ingerisci il raw, scrivi le pagine, chiudi il gap.
2. **Richiede nuovo raw** → segnala in chat all'umano. Il gap **resta aperto**.
3. **Risolvibile con synthesis** → crea `wiki/syntheses/<question-slug>.md`
   cross-source, chiudi il gap.

Per chiudere un gap, **aggiungi una sola riga** alla sezione del gap:

```markdown
**Risolto:** YYYY-MM-DD — [[<pagina-nuova-o-aggiornata>]]
```

Mai cancellare il gap. Mai modificare le righe precedenti. L'entry diventa
storica.

Append a `wiki/log.md` (vedi [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md)):

```
[YYYY-MM-DD HH:MM] gap-closed — <slug> via [[<pagina>]] — files touched: 1
```

## Eccezione di scrittura su `wiki/`

Questo è uno dei pochi casi in cui agenti diversi da [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) possono
scrivere in `wiki/` (vedi `PATTERN.md §10`, eccezioni puntuali). L'eccezione è
**append-only e meccanica**: aggiungere una sezione `## YYYY-MM-DD HH:MM — ...`
in coda al file. Mai editare contenuto esistente, mai chiudere gap (riservato a
[wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc)).

## Anti-pattern (vietati)

| Anti-pattern | Correzione |
|---|---|
| Aprire gap senza specificare l'**Origine** | Aggiungi sempre `<agente> @ <artefatto>` |
| Chiudere un gap senza essere `wiki-keeper` | Solo l'analyst chiude. Altri agenti aspettano il prossimo run. |
| Editare gap aperti da altri agenti | Vietato. Apri un nuovo gap se serve raffinare. |
| Usare `gaps.md` per TODO interni | È un canale formale, non un blocknotes. Usa il proprio scope di scrittura. |
| Cancellare gap risolti per "fare ordine" | Vietato. È archivio storico. |
