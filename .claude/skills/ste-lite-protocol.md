---
id: ste-lite-protocol
version: v1.0
opt_in: ste_lite.enabled
tool: tools/lint/ste_lite.py
command: /ste-lite
---

# Skill: ste-lite-protocol

> Scrittura controllata per i testi che legge una persona: le regole **strutturali** di
> ASD-STE100 (Issue 9, 2025), senza il dizionario. Il verdetto di conformità è di
> `tools/lint/ste_lite.py`, mai di chi scrive: i modelli sovrastimano quanto rispettano i
> vincoli. Origine e limiti: `wiki/sources/2026-10-15-karpathy-comprensione-output-llm.md`.

---

## Dove si applica

| Canale | Grammatica |
|---|---|
| agente → agente, agente → tool | caveman (`caveman-protocol`), se `compression.output.enabled` |
| agente → persona, agente → artefatto | STE-lite, questa skill |

I due canali non si sovrappongono: caveman è già spento verso l'utente e verso gli artefatti
(PATTERN §20.2, R.C1). Le due grammatiche sono opposte: caveman toglie articoli e verbi, STE-lite
vieta di toglierli.

## Regole

Le regole marcate **L** le controlla il linter. Le altre restano a chi scrive.

| # | Regola | L |
|---|---|---|
| 1 | Frase procedurale: massimo 20 parole. Frase descrittiva: massimo 25 | L |
| 2 | Un'istruzione per frase, salvo azioni simultanee | L |
| 3 | Procedure all'imperativo e in voce attiva. Nelle descrizioni il passivo solo se chi agisce non è noto | L (procedure) |
| 4 | Paragrafo: massimo 6 frasi, un argomento | L |
| 5 | Un termine, un significato: la stessa cosa si chiama sempre allo stesso modo (`ste_lite.glossary`) | L (glossario) |
| 6 | Non togliere articoli, preposizioni, verbi. Niente frecce né abbreviazioni nella prosa | L |
| 7 | Niente punto e virgola: due frasi | L |
| 8 | Elenco numerato per le sequenze, elenco puntato per i testi complessi | — |
| 9 | Massimo 3 parole in un gruppo nominale (in italiano: niente catene di «di») | — |
| 10 | L'avvertenza precede l'istruzione a cui si riferisce, e dice il rischio | — |

## Cosa non si trasferisce

- **Il dizionario** (circa 900 parole approvate, una parte del discorso e un significato
  ciascuna): esiste solo in inglese. In italiano lo sostituisce il glossario di regola 5.
- **Le categorie di nomi e verbi tecnici**: sono della manutenzione aeronautica.
- **Il cheat sheet allegato al post di Karpathy** non è un riferimento. Almeno quattro righe
  sono sbagliate (approximately, TEST come verbo, «in order to», passivo): il dettaglio è nella
  pagina sorgente citata sopra.

## Riscrittura

La semplificazione toglie contenuto, e il testo scorrevole nasconde quello che manca. Ogni
riscrittura segue questi passi.

1. Esegui `python3 tools/lint/ste_lite.py <file> --json` sull'originale. Annota la baseline.
2. Riscrivi applicando le regole. Tieni tutti i numeri, i nomi, gli identificativi, le
   condizioni, le eccezioni e le riserve. Non aggiungere fatti.
3. Chiudi con la sezione `## Omesso`. Elenca ogni informazione tolta, o scrivi «Nessuna
   omissione». La sezione è obbligatoria.
4. Esegui il linter sulla riscrittura. Riporta conformità prima e dopo, e le violazioni rimaste.
5. Non sovrascrivere l'originale. Scrivi la riscrittura nel file indicato da `--out`, o mostrala
   in chat.

## Varianti

| Variante | Regole | Uso |
|---|---|---|
| `lite` (default) | la tabella sopra | italiano e inglese |
| `stretta` | tutte le regole, vocabolario ristretto | **sconsigliata**: solo per riprodurre il run di US-339. Perde i connettivi e le sfumature |

## Stato

La capability è spenta (`ste_lite.enabled: false`) per decisione del manutentore (TSK-809,
2026-10-15). Si usa su richiesta, con `/ste-lite <file>`, in variante lite.

Dalla misura (`validation/runs/ste-lite-fact-loss-2026-10-15/REPORT.md`):

- i fatti si conservano, se si segue §Riscrittura;
- il testo si allunga, da +1% a +23%: STE-lite non serve a risparmiare spazio;
- la conformità al linter è facile da raggiungere, quindi da sola non è una misura di chiarezza.

Si riaccende su `targets[]` solo dopo una lettura umana che dica che le riscritture si capiscono
meglio.
