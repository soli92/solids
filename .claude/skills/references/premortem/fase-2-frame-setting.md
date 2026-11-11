# Fase 2 — Frame Setting (dettaglio completo)

Ambito: dettaglio della Fase 2 di `premortem-protocol.md`. Leggere prima di eseguire la fase.

Il **meccanismo psicologico centrale**: la skill enuncia esplicitamente la frase
chiave verbatim:

> «È [N mesi] da oggi. Questo piano è fallito.»

Senza questa frase, il modello LLM resta in modalità ottimistica (pianificazione)
invece di passare in modalità retrospettiva (spiegazione del fallimento come
fatto compiuto).

[^src: wiki/concepts/premortem-skill.md §Fase 2]

## Timeframe-default per tipologia di target

| Target | Timeframe default | Override flag |
|---|---|---|
| TSK singolo | 2-4 settimane | `--timeframe=2w` |
| US singola | 1-3 mesi | `--timeframe=2mo` |
| EP completa | 6 mesi | `--timeframe=6mo` |
| PATTERN bump major (R.K1-type) | 12-18 mesi | `--timeframe=12mo` |
| Strategia / nuova adapter | 12-18 mesi | `--timeframe=18mo` |

Il timeframe è inferito automaticamente dal target ma sempre override-abile
inline con `--timeframe=<N>w|<N>mo`.

[^src: design_&_architecture/proposta-premortem-integration-v216.md §3.2 Fase 2]

**Input atteso**: dossier di Fase 1.

**Output prodotto**: frase verbatim emessa al modello + timeframe selezionato.

**Criterio di completamento**: la frase è stata enunciata letteralmente nel contesto
dell'inferenza successiva (verifica grep sulla trascrizione interna se necessario).
