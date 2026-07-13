---
description: Routing in linguaggio naturale verso la capability della factory piu' pertinente alla domanda dell'utente. Legge CAPABILITIES.md come fonte di verita'.
argument-hint: [domanda in linguaggio naturale]
---

# /help — Capability Router in linguaggio naturale

Argomento utente: `$ARGUMENTS`

## Comportamento

### Con argomento (domanda in linguaggio naturale)

Esegui la skill [help-router-protocol](mdc:.cursor/skills/help-router-protocol/SKILL.md) passando l'intero valore di `$ARGUMENTS`
come **query** di input.

La skill eseguira':
1. **Bootstrap** — verifica che `CAPABILITIES.md` esista alla root del repo.
2. **Parse** — legge `CAPABILITIES.md` e costruisce in memoria la lista di
   capability con i loro campi.
3. **Match** — applica matching lessicale pesato tra la query e i campi di ogni
   capability.
4. **Output** — risponde con la capability piu' pertinente (o lista di candidati
   in caso di ambiguita', o lista delle 10 aree se nessun match).

Comportamento completo e invarianti: vedi [help-router-protocol](mdc:.cursor/skills/help-router-protocol/SKILL.md).

### Senza argomento (`/help` invocato senza query)

Leggi `CAPABILITIES.md` ed estrai gli heading `##` (escludi "Come leggere questo
documento" e "Nota: capability sempre attive"). Mostra in chat:

```
Ciao! Queste sono le aree di capability disponibili nella factory:

1. <area 1>
2. <area 2>
3. <area 3>
4. <area 4>
5. <area 5>
6. <area 6>
7. <area 7>
8. <area 8>
9. <area 9>
10. <area 10>

Scrivi /help <domanda> per trovare la capability giusta.
Esempio: /help voglio fare una code review
```

Sostituisci i placeholder con il testo reale degli heading `##` di `CAPABILITIES.md`.

## Note

- **Always-on**: nessun flag config richiesto. Il comando e' disponibile non appena
  `CAPABILITIES.md` e' presente alla root del repo (prodotto dalla sequenza US-110).
- **Read-only**: questa invocazione non modifica nessun file.
- **Fonte di verita'**: `CAPABILITIES.md` (root del repo). Non si basa su
  `CLAUDE.md`, `factory.config.yaml`, o conoscenza pregressa dell'agente.
