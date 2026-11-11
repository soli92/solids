# Passata 6 — Aderenza alla specifica (dettaglio completo)

Ambito: dettaglio della Passata 6 di `code-review-protocol.md`. Leggere prima di eseguire il
pass. Condizionale: solo se `code_quality.passes.spec_adherence: true` in `factory.config.yaml`.
Origine: asse «Spec» della skill `code-review` di Matt Pocock (MIT, originale in
`vendor/mattpocock-skills/skills/engineering/code-review/`).

Le passate 1-3 chiedono se il codice è scritto bene. Questa chiede se fa **quello che il TSK
chiedeva**. Un cambiamento può superare l'una e fallire l'altra: tenerle separate impedisce che
una nasconda l'altra.

## La specifica

In quest'ordine, e nient'altro:

1. il TSK: `## Context`, `## Technical Specs`, `## Definition of Done`, criteri di accettazione;
2. la US del TSK: criteri di accettazione;
3. i `constraints` dell'epica.

Non si cerca la specifica nei messaggi di commit: nel codice del cliente con
`suppress_ai_traces: true` non contengono ID della factory (§ai_policy). Se il TSK non ha né
criteri né DoD, il pass riporta «specifica assente» e non produce finding.

## Procedura

La passata la esegue il code-reviewer stesso. **Non rilancia `/review` e non avvia altri
agenti**: nel repo di Pocock la review con sotto-agenti si è richiamata da sola fino a oltre 50
agenti.

Sul diff in esame (`files_in_scope` della Fase 0), per ogni requisito della specifica si cerca il
punto del diff che lo realizza. Tre tipi di finding, ognuno con la riga della specifica citata:

| Tipo | Significato | Severity |
|---|---|---|
| `spec.missing` | requisito chiesto e assente, o realizzato solo in parte | high |
| `spec.wrong` | requisito che sembra realizzato ma in modo sbagliato | high |
| `spec.scope-creep` | comportamento nel diff che la specifica non chiede | medium |

Un requisito verificabile solo eseguendo l'app (flusso, aspetto) non si giudica dal diff: si
annota «da verificare con il functional oracle» e non diventa finding.

## Uscita

I finding entrano nell'aggregatore (Fase 3) con `pass: spec` e seguono le stesse regole di
verdetto: `pass`, `conditional` o `reject`, con `reject` gate umano (R.16). Nel report hanno una
sezione propria, `### Aderenza alla specifica`, separata dalle passate di qualità, con in testa
la specifica usata (path e sezioni).
