---
id: functional-docs-protocol
version: v1.0
opt_in: documentation.enabled
tool: tools/docs/build_functional_docs.py
command: /doc-funzionale
templates: .claude/skills/references/functional-docs/
---

# Skill: functional-docs-protocol

> Protocollo per scrivere la documentazione funzionale di un servizio del prodotto
> (manuale per il cliente, guida per l'utente finale) a partire dalla sola wiki. La scrittura
> la fa la sessione principale; il render in HTML e Word è deterministico
> (`tools/docs/build_functional_docs.py`). Vincoli: R.2 (zero invenzione) e R.3 (citazione).

## Uscite

`deliverables/doc-funzionale/<servizio>/` (cartella da `documentation.functional_docs.output_dir`):

| File | Pubblico | Template |
|---|---|---|
| `manuale-cliente.md` | cliente / committente | `references/functional-docs/manuale-cliente.md` |
| `guida-utente.md` | utente finale | `references/functional-docs/guida-utente.md` |

Accanto a ogni `.md` il render produce `.html` e, se `python-docx` è installato, `.docx`.

## Fase A — Raccolta delle fonti

1. Parti da `wiki/user-flows/<servizio>.md` (o dalle pagine indicate in
   `documentation.functional_docs.services.<servizio>.sources`). Leggila per intero.
2. Segui i wikilink `[[...]]` della pagina verso `entities/`, `concepts/`, `decisions/`,
   `be-services/`, `design-system/` e leggi le pagine pertinenti.
3. Completa con la ricerca fts5:

   ```bash
   python3 tools/wiki-search/fts_index.py search "<termine>" --top 10 --json
   ```

   La ricerca è in AND: usa pochi termini per volta (nomi di stati, ruoli, nomi del
   servizio). Considera solo i risultati in `entities`, `concepts`, `decisions`,
   `be-services`, `design-system`, `user-flows`; ignora `log.md`, `gaps.md`, `sessions`.
4. Scrivi in chat (o in cima al lavoro) l'**elenco esplicito delle fonti usate**: path wiki,
   una per riga, con una nota su cosa ne hai preso. Solo queste fonti possono sostenere
   affermazioni nel documento.
5. Annota data e versione della specifica quando la pagina le dichiara: una pagina può
   descrivere una versione superata dell'interfaccia.

## Fase B — Scrittura

Copia il template del pubblico richiesto e compila ogni sezione. Frontmatter obbligatorio:

```yaml
---
title: "<Titolo del documento>"
servizio: <chiave-servizio>
pubblico: cliente | utente
stato: bozza
aggiornata: YYYY-MM-DD
---
```

Con `--pubblico=entrambi` scrivi entrambi i file, partendo dallo stesso elenco di fonti.

## Fase C — Regole (non derogabili)

1. **Ogni sezione termina con «Fonti:»** seguita dai path wiki in codice, per esempio
   `` Fonti: `wiki/user-flows/x.md`, `wiki/entities/y.md` ``. Una sezione senza fonte non si
   scrive: si sposta in «Lacune».
2. **Nessuna affermazione senza fonte.** Non completare con ciò che «di solito» fa un
   servizio simile, né con buon senso. Cifre, limiti, nomi di pulsanti, stati e termini
   si riportano come stanno nella fonte.
3. **Ciò che manca va in «Lacune»** (una voce per punto: cosa manca e dove era atteso) e
   non si riempie. Le lacune non si nascondono nel testo con formule vaghe.
4. **I conflitti tra fonti si dichiarano**: indica le due versioni, le fonti, e quale hai
   adottato nel testo e perché (la più recente per data o versione dichiarata). Se non si
   può decidere, adotta nessuna e porta il punto in «Lacune».
5. **Stato del flusso**: se la fonte avverte che i contenuti sono aspettative di collaudo o
   bozze, riportalo nel documento.
6. **Guida utente**: nessuna route o URL interno, nessuna API, nessun nome di componente o
   di codice, nessun nome di feature flag, nessun identificativo di task, gap, epica,
   domanda o decisione. Linguaggio semplice, rivolto a chi usa il servizio. Se per dire una
   cosa servirebbe un termine tecnico, la cosa non entra nella guida.
7. **Manuale cliente**: niente identificativi di task, gap, epica nel testo (le fonti sono
   path wiki). Termini tecnici solo se la fonte li usa e servono al committente.
8. Nessun riferimento alla factory, a Claude o ad agenti nei testi prodotti. Nessun segreto
   (il render lo verifica con `redact.py`).
9. Italiano semplice e professionale, frasi corte, un concetto per frase.

## Fase D — Render

```bash
python3 tools/docs/build_functional_docs.py <servizio>
python3 tools/docs/build_functional_docs.py --tutti
```

Il render: HTML autocontenuto con banner «BOZZA — da revisionare prima della consegna» se
lo stato è `bozza`, fonti come link al sito tecnico (`deliverables/doc-tecnica/<ultima data>/`)
quando la pagina esiste, altrimenti testo; Word con intestazione di stato e data. Prima di
scrivere passa dal controllo di redazione: con finding termina con codice 2 e non scrive.
`python-docx` assente: il Word è saltato con un avviso, exit 0.

## Fase E — Stato e approvazione

- Ogni documento nasce con `stato: bozza`.
- Il passaggio a `approvata` è **solo umano**: la persona che rivede aggiunge al frontmatter
  `stato: approvata`, `approvata_da: <nome>`, `approvata_il: YYYY-MM-DD`. L'agente non
  modifica mai `stato`, `approvata_da`, `approvata_il`.
- Se rigenera un documento già approvato, scrive come `bozza` in una copia e lo segnala:
  non sovrascrive un'approvazione.
- Consegnare al cliente documenti in `bozza` non è consentito: il banner lo ricorda.

## Verifica finale (consigliata)

Prendi 10 affermazioni a caso per documento e controlla che la fonte citata nella sezione
le contenga davvero; correggi o sposta in «Lacune» quelle non confermate.

## Estensione ad altri servizi

Aggiungi la voce in `documentation.functional_docs.services` (chiave, `title`, `sources`).
Estendere oltre i servizi pilota richiede l'ok del Tech Lead.
