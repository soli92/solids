# Suggerimento post-esecuzione — dettaglio (EP-033, v2.24)

**Ambito**: logica completa del suggerimento post-esecuzione di `dev-handoff.md`.
Leggere obbligatoriamente prima di emettere suggerimenti a fine TSK quando il layer
del TSK ha regole definite nella tabella sotto. Se il layer non ha regole → no-op.

---

> **Trigger**: il dev-agent esegue questa sezione al termine di ogni TSK,
> immediatamente prima di terminare l'handoff. Se il layer del TSK non ha regole
> definite nella tabella sotto → no-op silenzioso; la sezione non compare nell'output.

## Dati letti

1. **Frontmatter TSK** (gia' in contesto): campo `layer` e path/id della US di appartenenza.
2. **`factory.config.yaml`**: flag opt-in capability:
   - `a11y.enabled`
   - `ux_ui.enabled`
   - `fe_correctness.visual_oracle.enabled`
   - `code_quality.enabled`
3. **`wiki/log.md`**: entry recenti sulla stessa US — per deduplication (non suggerire
   una capability gia' registrata nella sessione corrente per la stessa US).

## Regole per layer

| Layer | Suggerimenti (se comando installato + non gia' eseguito per questa US) |
|---|---|
| fe | `/a11y` (se `a11y.enabled: true`), `/ux-ui-review` (se `ux_ui.enabled: true`), `/visual-oracle` (se `fe_correctness.visual_oracle.enabled: true`), `/prototype <US-id>` (se `prototyping.enabled: true` e la US ha design-spec.md ma nessun prototipo recente registrato in `wiki/log.md` per questa US nella sessione corrente) |
| be | `/review` (focus robustezza) |
| db | `/review` (focus robustezza); nota sulla backup strategy se il TSK include migration DDL |
| qa | suggerimento `flakiness-detection-protocol` se il TSK include test asincroni rilevati nel contesto |
| docs | `/lint` per verifica integrazione wiki |

## Gate installazione

Prima di emettere ogni suggerimento, il dev-agent verifica che il file
`.claude/commands/<comando>.md` esista nel repo corrente. Se il file non esiste
→ suggerimento soppresso silenziosamente (nessun WARNING, nessun output aggiuntivo).

Esempio: se `a11y.enabled: true` ma `.claude/commands/a11y.md` non esiste,
il suggerimento `/a11y` e' soppresso.

## Deduplication

Il dev-agent legge le entry recenti di `wiki/log.md` relative alla US corrente
(ricerca per id US nel testo delle entry). Se una capability e' gia' registrata come
eseguita per quella US nella sessione corrente → suggerimento soppresso.

Questo evita di suggerire due volte la stessa cosa sulla stessa US in piu' TSK
consecutivi.

## Formato output (condizionale)

La sezione `## Suggerimento post-esecuzione` appare nell'output dell'handoff
**solo se** almeno un suggerimento supera tutti i gate (installazione + deduplication).

Se 0 suggerimenti rilevanti → la sezione non compare. Comportamento invariato vs v2.23.

Formato (max 3 suggerimenti; se >3 capability rilevanti, priorita' alle capability
gia' installate — always-on prima di opt-in):

```
## Suggerimento post-esecuzione

TSK <LAYER> completato. Potresti considerare:
- `/<comando>` — <motivazione breve, max 1 riga, specifica per il layer>.
- `/<comando>` — <motivazione breve>.
```

Esempio per layer `fe`:

```
## Suggerimento post-esecuzione

TSK FE completato. Potresti considerare:
- `/a11y` — verifica accessibilita' WCAG 2.2 AA sui componenti appena prodotti.
- `/ux-ui-review` — review UX/UI se sono state introdotte nuove interfacce utente.
```

## Tono

Sempre "Potresti considerare", "E' disponibile" — mai imperativo ("Devi", "E' richiesto").
L'handoff e' uno strumento di chiusura, non un gate bloccante.

## Backward compat

Factory senza le capability suggerite (flag spenti, comandi non installati) → tutti
i gate falliscono silenziosamente → nessuna sezione `## Suggerimento post-esecuzione`
nell'output. Comportamento identico a v2.23 (R.P3).

Cross-link: US-115 (EP-033) | [[runtime-suggestions-proposal-comparison]] §Proposta B |
[[capability-map]] | `CAPABILITIES.md` (US-110 EP-032).
