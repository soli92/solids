---
name: wiki-gap-protocol
description: Formato canonico e ciclo di vita di un gap in wiki/gaps.md. Riferimento unico per PM/Arch/TPM/wiki-query (apertura) e wiki-keeper (chiusura).
---
# Protocollo gap (canonico)

`wiki/gaps.md` è il **canale formale del feedback loop** della wiki (vedi
`PATTERN.md §10`). Tutti gli agenti L3+ possono e devono usarlo per segnalare
buchi nella knowledge base scoperti durante il loro lavoro.

## Caratteristiche del file

- **Append-only condiviso in scrittura** fra `product-manager`, `lead-architect`,
  `tpm`, `wiki-query`. Lettura: tutti, ma `wiki-keeper` lo legge **obbligatoriamente
  all'inizio di ogni run** (Fase 0 di `ingest-protocol`).
- **Chiusura riservata a `wiki-keeper`**: solo l'analyst annota `**Risolto:**`.
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

All'inizio di ogni run, `wiki-keeper` legge `wiki/gaps.md`. Per i soli gap aperti
leggi `memory/gaps-open.md` se presente (vista derivata, più leggera); rigenerala con
`python3 tools/wiki/gaps_open_view.py`. La fonte di verità resta `wiki/gaps.md` (R.5).

Per ogni gap aperto:

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

> Precisazione: le sole modifiche ammesse a righe precedenti sono la sostituzione
> D1 e il cambio di checkbox D2, descritti in «Chiusura con evidenza / Effetto».

Append a `wiki/log.md` (vedi `wiki-log-entry`):

```
[YYYY-MM-DD HH:MM] gap-closed — <slug> via [[<pagina>]] — files touched: 1
```

## Chiusura con evidenza / Effetto

Questa sezione dice come si scrive una chiusura. Non cambia chi chiude: restano
`wiki-keeper` (vedi «Chiusura riservata»). Le regole D1 e D2 fissano la prassi esistente e sono
reversibili.

### Forma della chiusura

- **D2 — forma canonica.** Il gap si chiude con la checkbox `- [x]` piu' una riga
  `**Risolto:**` sotto il gap. `[CLOSED]`, `**Risolto (data, contesto):**`, `**Superato:**` e
  `~~CHIUSO~~` nel titolo sono forme storiche: si accettano in lettura
  (`tools/wiki/verify_gap_closures.py` le riconosce), non si usano nelle nuove chiusure.
- **Duplicati.** Un gap gia' chiuso altrove si chiude con `**Risolto:**` che rimanda al gap
  verificato (`wiki/gaps.md:<riga>` o il suo ID): ne eredita la verifica, senza catene.
- **D1 — sostituzione.** Un `**Risolto:**` puo' sostituire una riga
  `**Aggiornamento...**` solo nello stesso commit che chiude il gap, nello stesso blocco.
  Fuori da quel commit le righe esistenti non si riscrivono.
- **Chiusura o riapertura in coda.** Un gap gia' scritto piu' sopra si chiude in coda con una
  voce `- [x]` che ripete l'ID seguita dalla riga `**Risolto:**`; si riapre in coda con una voce
  `- [CONFIRMED OPEN]` che ripete l'ID e dice la prova (pagina con fonte, oppure
  `repo@sha:file:riga`). `verify_gap_closures.py` legge le voci in ordine: dopo una
  `[CONFIRMED OPEN]` le chiusure precedenti non valgono piu', vale solo una chiusura scritta dopo.

### Criterio di chiusura ed evidenza

- Il **criterio di chiusura**, se qualcuno lo ha dichiarato (Tech Lead o chi apre il gap),
  va trascritto nella riga `**Risolto:**` senza parafrasi che ne cambino il senso.
- La riga `**Risolto:**` riporta l'**evidenza**: il rimando `[[pagina]]` (o path
  `wiki/...md`) a una pagina che esiste e cita una fonte `[^src: raw/...]` presente; per un
  gap sul codice, `file:riga` con lo SHA del commit verificato.
- L'evidenza e' **necessaria ma non sufficiente**. Gli script verificano che il rimando
  risolva (la pagina c'e', la fonte c'e'), non che la pagina o il codice sostengano
  l'affermazione: quello lo controlla una persona. Una chiusura senza rimando verificabile
  conta come gap aperto in `verify_gap_closures.py` e il Check 4bc la segnala.

### Rettifiche ed Effetto (append)

- Una rettifica a una chiusura si **accoda** come nuova riga con data. Non
  riscrive la riga `**Risolto:**`.
- L'effetto della chiusura si registra in una riga `**Effetto (YYYY-MM-DD):**`,
  sempre in coda. Ogni nuova data e' una nuova riga.
- Resta valido R.5: `wiki/gaps.md` e' append-only. Le uniche eccezioni sono D1 e il
  cambio di checkbox di D2.

### Controlli a script

`wiki-keeper` non ha Bash. I controlli li lancia la **sessione principale** prima
del commit:

- `python3 tools/wiki/gaps_append_guard.py` sul contenuto in stage (o `--commit <sha>`,
  `--storia N`): segnala le righe tolte o modificate di `wiki/gaps.md`, salvo la
  sostituzione D1 e il cambio di checkbox D2. Solo avviso, exit 0 (`--strict` per exit 1),
  nessun aggancio al pre-commit; lo stesso controllo, sull'ultimo commit, e' il Check 4bd;
- `python3 tools/wiki/verify_gap_closures.py --check` (o `--json`) per lo stato
  delle chiusure (Check 4bc).

### Fuori da questa sezione

La sezione non tocca `functional-oracle-protocol` ne' `deep-functional-probe`:
verificano l'app in esecuzione, non il sorgente.

## Eccezione di scrittura su `wiki/`

Questo è uno dei pochi casi in cui agenti diversi da `wiki-keeper` possono
scrivere in `wiki/` (vedi `PATTERN.md §10`, eccezioni puntuali). L'eccezione è
**append-only e meccanica**: aggiungere una sezione `## YYYY-MM-DD HH:MM — ...`
in coda al file. Mai editare contenuto esistente, mai chiudere gap (riservato a
`wiki-keeper`).

## Anti-pattern (vietati)

| Anti-pattern | Correzione |
|---|---|
| Aprire gap senza specificare l'**Origine** | Aggiungi sempre `<agente> @ <artefatto>` |
| Chiudere un gap senza essere `wiki-keeper` | Solo l'analyst chiude. Altri agenti aspettano il prossimo run. |
| Editare gap aperti da altri agenti | Vietato. Apri un nuovo gap se serve raffinare. |
| Usare `gaps.md` per TODO interni | È un canale formale, non un blocknotes. Usa il proprio scope di scrittura. |
| Cancellare gap risolti per "fare ordine" | Vietato. È archivio storico. |
