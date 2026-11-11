# code-migration-protocol — verdetto e gate umani

Foglia della Fase 4. Il verdetto e' calcolato da `tools/migration/lib/verdict.mjs`: qui c'e'
come leggerlo e come comunicarlo, non un modo alternativo di calcolarlo.

## Gate per file

| Gate | Verde | Rosso (`reject`) | Non osservato (`conditional`) | Non applicabile |
|---|---|---|---|---|
| debito | nessuna voce bloccante aperta sul file | voce `open`/`in-analysis` con `bloccante: si` | registro non dichiarato o assente al default | — |
| modo | severita' `clean` | `error`, `risk` | asse C non eseguito o non osservabile | `applicable: false`, o file non censito dal plugin |
| parita' | oracolo `pass` e target `pass` | oracolo non `pass`; target non `pass` | file senza esito | file `onlyInA` |

`dirty` e `legacy` nell'asse C sono parziali: tengono il file a `conditional`.

## Aggregazione

```
reject        <=> un gate per file rosso  OR  parity_ratio osservato < soglia
consolidated  <=> ogni file consolidated  AND  nessuna condizione globale
conditional   altrimenti
```

Condizioni globali che impediscono `consolidated`: fork non fornito, `parity_ratio` non
osservato, registro dei debiti non osservato, basename ambigui. Ogni file `onlyInA` e' lavoro
di PORTING residuo: `conditional`. Ogni file `divergent` e' `gated`: `conditional` finche'
l'umano non decide.

**KPI.** `parity_ratio` = coppie con target `pass` / coppie con oracolo `pass`; `coverage` =
quota delle coppie appaiate che ha un esito. Riportali insieme: un ratio di 1.0 su una
copertura del 10% dice poco. Senza esiti il KPI e' `null`, mai 0 e mai 1.

## Gate umani — forma e comportamento

`verdict.json.gates[]` contiene oggetti `{gate, action, payload}`, la stessa forma dei gate
delle altre skill della factory. Il verificatore li presenta verbatim e si ferma.

| `gate` | Quando | Cosa chiede |
|---|---|---|
| `migration-verdict-reject` | verdetto `reject` | correggere (dev-agent sul target) o accettare il debito con una voce motivata nel registro |
| `migration-divergent` | file `divergent` | per ogni file: riportare nel target la modifica che l'oracolo ha avuto dopo il fork, o dichiararla non applicabile (voce nel registro) |
| `migration-ambiguous-pairing` | `ambiguous[]` non vuoto | appaiare a mano i candidati; nessun accoppiamento e' stato inventato |

Il coordinatore riassume il gate per l'utente; la ripresa avviene solo su risposta esplicita
(`confermato` / `annullato` o la decisione nel merito). Un `reject` non si ritenta in loop e
non si riclassifica.

## Cosa dire all'utente

1. Il verdetto e il perche' in una riga (la condizione che lo determina).
2. `parity_ratio` con `coverage`, oppure «non osservato» con la ragione.
3. Le osservazioni mancanti, per nome: sono il lavoro che separa un `conditional` da un
   `consolidated`, e vanno dette anche quando il verdetto e' `reject`.
4. I gate aperti, verbatim.
5. Il path di `verdict.md` (tabella per file in ordine bottom-up).

Da non dire: «nessun problema» quando un asse non e' stato osservato; «migrato» per un file
con `contentEqual: true`; «orfano» per un `onlyInB` senza verifica.
