---
name: pocock-retro
description: Retrospettiva su una sessione chiusa che propone miglioramenti all'ambiente degli agenti, non al codice. Ogni errore meccanico diventa un controllo deterministico. Opt-in engineering_practices. Adattata da mattpocock/skills retro @49dd158.
---
# Retrospettiva sull'ambiente degli agenti

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `retro` di Matt Pocock (MIT,
originale in `vendor/mattpocock-skills/skills/engineering/retro/`). Propone, non applica: ogni
proposta la decide il Tech Lead.

## Fonti

Il report di `/session-analysis` della sessione (anomalie, metriche, dispatch), il report di
chiusura della sessione (`session-close-protocol`) e, se servono, le trascrizioni. Mai la
sessione in corso (R-SAA-8).

## Categorie

| Categoria | Domanda | Quando |
|---|---|---|
| **Navigazione** | L'agente ha trovato in fretta i file giusti? Manca un puntatore? | La sessione ha cercato a lungo un'informazione |
| **Controlli automatici** | Un lint, uno script, un hook avrebbe fermato l'errore? Esiste già ma non è collegato o è rotto? | L'agente ha fatto un errore che un controllo avrebbe preso |
| **Regole di review** | Il code-reviewer doveva avere una regola nuova, o una va tolta o chiarita? | La review non ha visto un difetto |
| **Istruzioni di contorno** | C'è testo in CLAUDE.md, agenti o skill che andrebbe in un controllo o in una regola di review? | I file di istruzioni sono lunghi |
| **Economia degli strumenti** | Chiamate costose che si potevano evitare o accorciare? | Una chiamata ha pesato molto sui token |
| **Istruzioni inerti** | Righe che non cambiano il comportamento dell'agente? | I file sono lunghi e confusi |
| **Accesso alle informazioni** | Mancava un dato decisivo (log del server, stato di un ambiente)? | L'agente ha lavorato alla cieca |

## La regola principale

Prima si classifica la violazione.

- **Meccanica** (uno schema fisso, un'API vietata, una forma di import, un file nel posto
  sbagliato, un file condiviso riscritto invece che aggiornato in coda): diventa un **controllo
  deterministico**, in `tools/lint/` (con `run-deterministic.py`) o in un hook. Si costruisce il
  controllo, non si scrive una regola in più.
- **Di giudizio** (coerenza fra file, aderenza allo stile del codice intorno): diventa una regola
  di review in `code_quality/rules/`, letta dal code-reviewer e non dal dev-agent, che ha già il
  contesto più carico.

Un repository senza controlli automatici è già un risultato.

## Uscita

Le proposte, in ordine di gravità, ognuna con categoria, evidenza (riga del report o della
trascrizione), proposta concreta e file toccato. Vincoli:

- proposte su `CLAUDE.md`, `factory.config.yaml` e `PATTERN.md` solo come modifica con gate
  umano, mai applicate dalla retro;
- proposte su skill e agenti tramite `/refactor` o una modifica normale con review;
- quando un controllo viene costruito, si registra in `analytics/pocock-pilota/controlli.yaml`
  (errore di origine, controllo, path, commit): è l'indicatore 6 del pilota.
