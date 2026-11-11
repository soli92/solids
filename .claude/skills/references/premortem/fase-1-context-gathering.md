# Fase 1 — Context Gathering (dettaglio completo)

Ambito: dettaglio della Fase 1 di `premortem-protocol.md`. Leggere prima di eseguire la fase.

Costruisce il **dossier** su cui le fasi 2-5 lavorano. Niente premortem parte
finché il **bar minimo** non è soddisfatto: questo è il punto di applicazione di
**R.P2** (fail-loud su contesto sotto-bar).

## Input e loading strategy per input shape

Il comando `/premortem` passa un singolo argomento. La skill discrimina la shape
(primo match vince) e carica il contesto **prima** di chiedere qualsiasi cosa:

| Input shape | Loading strategy |
|---|---|
| **Artefatto kanban** (`EP-XXX` / `US-YYY` / `TSK-ZZZ`) | Legge frontmatter + body del target, dell'eventuale padre (US→EP, TSK→US→EP) e dei sibling; carica il design doc referenziato in `[^src: …]` se presente. |
| **Pagina wiki** (path `wiki/**/*.md`) | Legge la pagina + i wikilink di primo hop (`[[…]]`). |
| **Descrizione libera** | Nessun file specifico da cui dedurre: carica `wiki/index.md` + le ultime 10 entry di `memory/episodic/` come contesto storico, poi procede al bar minimo. |

In tutti i casi il dossier finale contiene: **target**, **stakeholder**,
**criteri di successo**, contesto storico (`memory/episodic/` ultime 10 entry),
wikilink di primo hop.

## Il bar minimo — 3 domande esatte

La premortem non parte finché non sono note **tutte e tre**:

1. **«Cosa si sta cercando di fare?»** — derivato dal target.
2. **«Per chi?»** — stakeholder / consumer del risultato.
3. **«Come appare il successo?»** — criteri di accettazione.

## Logica di deduzione preventiva (artefatti kanban ben formati)

Su un artefatto kanban la skill **deduce prima di chiedere**: legge frontmatter +
body e prova a rispondere alle 3 domande da sola. La domanda esplicita all'utente
si attiva **solo se la deduzione fallisce** per uno specifico elemento.

- Esempio: `/premortem EP-001` su un'epica con titolo, descrizione e US figlie ben
  formate → tutte e 3 le risposte sono deducibili → la skill **procede senza
  chiedere** e passa direttamente alla Fase 2.
- Su **descrizione libera** la deduzione quasi sempre lascia ≥1 elemento scoperto
  → **quasi sempre ≥1 domanda esplicita**.

## Comportamento: una domanda alla volta

Se mancano elementi, la skill chiede **una sola domanda per volta** (NO batch di 3
domande simultanee). Aspetta la risposta, aggiorna il dossier, e solo allora pone
la successiva — finché il bar è completo.

Esempio di flusso (descrizione libera sotto-bar):

```
Utente: /premortem "vogliamo migrare il DB a Postgres"
Skill:  Bar minimo non soddisfatto: manca «per chi» (stakeholder).
        Chi è impattato da questa migrazione? (utenti finali, team interno, …)
Utente: il team backend, in produzione restano gli stessi utenti
Skill:  Bar minimo non soddisfatto: manca «come appare il successo».
        Come appare il successo di questa migrazione? (criteri di accettazione)
Utente: zero downtime e nessuna query > 50ms di regressione
Skill:  Bar minimo soddisfatto. Procedo. [Fase 2 →]
```

## R.P2 — fail-loud su contesto sotto-bar

Mai output parziale silenzioso. Se il bar non è soddisfatto la skill **rifiuta di
procedere** con messaggio esplicito verbatim:

> **Bar minimo non soddisfatto: manca `<X>`. Rispondi a questa domanda prima di procedere.**

dove `<X>` ∈ {`cosa stai facendo`, `per chi`, `come appare il successo`}. Output
forzato su contesto insufficiente è sanitizzato → produce una premortem inutile,
quindi si preferisce sempre fail-loud, non fail-silent.

**Criterio di completamento**: le 3 domande del bar minimo soddisfatte (per
deduzione o per risposta esplicita).

[^src: management/kanban/EP-001-premortem-skill-scaffolding/US-005-bar-minimo-contesto-fail-loud/TSK-005.md §Technical Specs]
