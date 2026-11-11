# code-migration-protocol — assi e artefatti

Foglia della Fase 1. Come leggere i quattro artefatti e come scegliere i parametri.

## Asse A — `import-map.json`

| Campo | Lettura |
|---|---|
| `entries[].imports` / `usedBy` | archi del grafo, solo verso file del repo gestiti dai plugin caricati |
| `entries[].shared` | `usedBy > 1`: una modifica qui ha raggio d'impatto multiplo |
| `bottomUpOrder` | foglie prima: l'ordine in cui portare e verificare |
| `roots` | file senza importatori: entry reali o codice morto (da verificare, non da dedurre) |
| `cycles` | file coinvolti in cicli o self-import: verifica manuale |
| `entries[].unresolved`, `summary.unresolvedImports` | import relativi o alias che non risolvono: file assenti o alias del bundler non letti. **Non** e' rumore da filtrare |
| `summary.edgesOutsidePlugins` | archi verso file che nessun plugin caricato possiede (es. `.ts` importato da `.svelte` con il solo plugin `svelte`): aggiungere il plugin mancante |
| `meta.aliasSource` | `tsconfig:<file>`, `plugin-default` o `relative-only`: con `relative-only` gli alias non sono seguiti |

**Entry.** `full` (default) mette nel grafo ogni file dei plugin sotto `--src`. `dir:<d>` e
`plugin:<kind>` partono da entry point e includono solo il raggiungibile: utile quando il
repo contiene molto codice non servito (story, script). Un entry che non trova nulla e' un
errore d'ingresso, non uno zero.

**Ignore.** `--ignore <regex>` sul relKey toglie codice generato (traduzioni compilate,
client API generati) che altrimenti domina i conteggi. Va dichiarato nel report.

## Asse B — `library-usage.json`

Per ogni simbolo importato dalla libreria (anche da subpath): prop usate nei tag, numero di
tag, riferimenti non-tag, consumatori. Eseguito su A e B con la stessa `--library`, il
confronto per `name` mostra il contratto che cambia: prop presenti in A e assenti in B,
simboli nuovi, file che pesano di piu' (`byFile`). Lo script **misura**; decidere se una
differenza e' voluta resta una voce del registro dei debiti.

## Asse C — `mode-census.json`

| Campo | Lettura |
|---|---|
| `applicable: false` | il linguaggio non ha un concetto di modalita' (es. `js-ts`): asse non applicabile, non pesa sul verdetto |
| `observable: false` + `reason` | il plugin la definisce ma non ha potuto eseguirla (compilatore assente nel repo, Node vecchio, compilatore trovato **sopra** il repo): pesa come «non osservato» |
| `auditors[].authority` | `compiler` = verdetto del compilatore; `heuristic` = marcatori testuali, da verificare prima di fidarsi |
| `entries[].severity` | `error`/`risk` bloccano, `dirty`/`legacy` tengono a conditional, `clean` non certifica il comportamento |

Plugin `svelte`: stati `NON-COMPILA`, `runes-RISCHIOSO`, `runes-sporco`, `legacy`,
`runes-pulito` del compilatore del repo; i marcatori testuali integrano il compilatore
sui residui che accetta in silenzio, su un sorgente privato di commenti e stringhe.

## Asse D — `derivation-matrix.json`

| Partizione | Ramo |
|---|---|
| `onlyInA` | PORTING: esiste nell'oracolo, manca nel target |
| `inBoth` | AUDIT: confrontare comportamento, non testo |
| `divergent` | in entrambi, ma l'oracolo e' cambiato dopo il fork: **gate umano** |
| `onlyInB` | nuovo nel target o orfano: fatto da verificare, non pesa sul verdetto |

`pairs[].contentEqual` dice se il testo e' identico (fine riga normalizzata): identico in una
migrazione significa «non ancora toccato» o «nulla da cambiare», non «verificato».

**Join.** `path` (default) appaia per relKey. Se la migrazione ha riorganizzato il layout
(`lib/Icon.svelte` -> `lib/Icon/Icon.svelte`) il join per path da' `inBoth` vicino a zero:
usare `--join-by=name`. I basename con piu' candidati non vengono appaiati (`ambiguous[]`).

**Fork.** `--fork <commit-ish>` o `--since <data>` attivano la deriva con `git log --relative`
in sola lettura sull'oracolo. Sono input umano: se l'utente non lo conosce, la risposta e'
`driftStatus: gated:fork-point-missing`, non una stima.

## Plugin esterni

Un linguaggio nuovo richiede un file `.mjs` con `name`, `extensions`, `resolveImports`
(interfaccia in `tools/migration/README.md`). `ctx.resolver` fornisce gia' relativo,
estensioni, `index` e alias da tsconfig: il plugin scrive l'estrazione degli specifier e,
se esiste un compilatore che fa da autorita', `modeAudit`.
