# tools/migration — verifica di migrazione del codice fra due repo

Confronta un **oracolo** (A, il codice che funziona) con un **target** (B, il codice
migrato) e restituisce un verdetto `consolidated | conditional | reject`. Il tooling
**osserva e misura**: non corregge nulla, e non scrive mai nei repo che legge.

Node ESM (`.mjs`), nessuna dipendenza npm. Richiede Node >= 18.

```bash
node tools/migration/migration-verify.mjs <oracle_repo> <target_repo> [--plugin=js-ts|svelte|svelte,js-ts] [--join-by=path|name]
node --test "tools/migration/**/*.test.mjs"
```

La forma `node --test tools/migration/` non funziona su Node 24: una directory passata
a `--test` viene trattata come un file. Il glob fra virgolette lo espande Node stesso,
quindi vale uguale su bash, zsh e Git Bash.

## Architettura: core e plugin

| | Core (`lib/` + script d'asse) | Plugin (`plugins/`) |
|---|---|---|
| Cosa sa | file, grafi, hash, partizioni, debiti, verdetto | sintassi degli import di un linguaggio, entry point, compilatore |
| Cosa non sa | nessun linguaggio, nessun framework, nessun nome di repo o di libreria | nulla del verdetto |

| File | Ruolo |
|---|---|
| `lib/paths.mjs` | **guard**: ogni scrittura passa da qui. I repo analizzati sono destinazioni vietate, confrontate sui path reali (symlink risolti). Una configurazione insicura viene rifiutata alla costruzione |
| `lib/schema.mjs` | contratti degli artefatti (`SCHEMA_VERSION 2.0.0`) e validatori |
| `lib/walk.mjs`, `lib/resolve.mjs` | walker in sola lettura; risoluzione degli specifier: relativo, estensioni, `index`, alias da `tsconfig`/`jsconfig` `paths` (con `extends` relativi), `.js` -> `.ts` |
| `lib/plugins.mjs` | registro e composizione dei plugin (`--plugin=svelte,js-ts`) |
| `lib/graph.mjs` | cicli, profondita' (cammino piu' lungo), ordine bottom-up |
| `lib/debt.mjs` | registro dei debiti: parser, gate, template |
| `lib/verdict.mjs`, `lib/report.mjs` | verdetto fail-closed e rendering `verdict.md` |
| `map-architecture.mjs` | **asse A** — albero degli import |
| `map-library-usage.mjs` | **asse B** — superficie consumata di una libreria (`--library`) |
| `audit-mode.mjs` | **asse C** — modalita' di compilazione, delegata al plugin |
| `derivation-matrix.mjs` | **asse D** — matrice di derivazione A <-> B |
| `verify.mjs` | verdetto sugli artefatti gia' prodotti |
| `migration-verify.mjs` | esecuzione completa A, B, C, D, verdetto |
| `debt-registry.mjs` | `init` (template, mai sovrascrive) e `check` del registro |

### Interfaccia di un plugin

```js
export default {
  name: 'mio-linguaggio',
  extensions: ['.ext'],                         // file di cui il plugin e' proprietario
  accept(absFile) {},                           // opzionale: filtro fine
  prepare(repoRoot) { return { extraAliases } },// opzionale: alias di default del framework
  resolveImports(file, src, ctx) {              // obbligatorio
    return { files: [/* assoluti */], unresolved: [/* specifier */], externals: [/* pacchetti */] };
  },
  entryPoints(repoRoot, kind) {},               // opzionale: --entry=plugin:<kind>
  modeAudit(files, repoRoot) {},                // opzionale: asse C
  usageExtras(src) {},                          // opzionale: asse B
};
```

Un plugin esterno si passa per path: `--plugin=./mio-plugin.mjs`. `ctx.resolver.resolve(spec, file)`
offre la risoluzione condivisa, cosi' un plugin nuovo scrive solo l'estrazione degli specifier.

| Plugin | Estensioni | Asse C | Entry point |
|---|---|---|---|
| `js-ts` (default) | `.ts .tsx .mts .cts .js .jsx .mjs .cjs` (esclusi `.d.ts`) | non applicabile | — |
| `svelte` | `.svelte .astro` | compilatore Svelte **del repo analizzato**; se non risolvibile, «non osservabile» con la ragione | `astro-pages`, `storybook-stories` |

## Artefatti

In `<artifacts_home>/<slug>/` (default `migration/<slug>/`), mai dentro i repo analizzati.
Lo slug di default e' il basename del repo; se oracolo e target hanno lo stesso basename
(due worktree) diventano `<nome>-oracle` e `<nome>-target`.

| Artefatto | Contenuto |
|---|---|
| `import-map.json` (A) | per file: importati, importatori, `shared`, profondita', hash; radici, cicli, `bottomUpOrder`, **import non risolti**, pacchetti esterni |
| `library-usage.json` (B) | per simbolo della libreria: prop, tag, riferimenti, consumatori; peso per file |
| `mode-census.json` (C) | per file: stato del plugin + severita' normalizzata (`error risk dirty legacy clean`); `applicable`, `observable`, `reason` |
| `derivation-matrix.json` (D) | partizione `onlyInA` (PORTING), `inBoth` (AUDIT), `divergent` (gate umano), `onlyInB` (nuovo o orfano); coppie con `contentEqual`; `ambiguous[]` |
| `verdict.json`, `verdict.md` | verdetto per file e globale, KPI, gate umani in JSON |

Chiave di join: path relativo POSIX. Con `--join-by=name` si appaia per basename quando la
migrazione ha riorganizzato il layout; un basename con piu' candidati **non** viene appaiato:
va in `ambiguous[]` e diventa un gate umano.

**Punto di fork.** `--fork <commit-ish>` o `--since <data>` sono **input umano**: il tool non
li deduce mai (nessun `merge-base`). Con il fork, `git log --relative <fork>..HEAD` in sola
lettura sull'oracolo dice quali file l'oracolo ha cambiato dopo che il target se ne e'
staccato: quelli appaiati sono `divergent`. Senza fork la deriva e' `gated:fork-point-missing`.

## Verdetto

| Gate per file | Fonte | Rosso (reject) | Non osservato |
|---|---|---|---|
| debito | registro dei debiti | voce `open`/`in-analysis` e `bloccante: si` sul file | registro non dichiarato |
| modo | asse C del target | severita' `error` o `risk` | asse C non eseguito o non osservabile |
| parita' | `--parity <esiti.json>` | oracolo non `pass` (verifica invalida) o target non `pass` dove l'oracolo e' `pass` | file senza esito |

- `consolidated` solo se ogni gate e' verde **o non applicabile**, nulla da portare, nessun
  gate umano aperto, fork fornito, `parity_ratio` osservato e sopra soglia.
- Un gate **non osservato non e' mai un verde**: tiene il verdetto a `conditional`.
- `reject` se un gate e' rosso o se `parity_ratio` < soglia. `reject`, `divergent` e `ambiguous`
  producono **gate umani** `{gate, action, payload}` in `verdict.json`.
- KPI `parity_ratio` = coppie con target `pass` / coppie con oracolo `pass`; `coverage` =
  quota di coppie con un esito. Senza esiti: `null`, mai zero.
- Exit: `0` consolidated · `1` conditional · `3` reject · `2` errore d'ingresso (fail-closed:
  registro dichiarato ma assente, fork non valido, artefatto non conforme).

Esiti di parita': `{ "src/a.tsx": { "a": "pass", "b": "fail" } }`, chiave lato target (o oracolo).
Li produce chi esegue i test funzionali sui due repo, tipicamente la skill `deep-functional-probe`.

## Registro dei debiti

Markdown factory-side e **versionato**: contiene decisioni umane, non si rigenera.
`node tools/migration/debt-registry.mjs init --oracle <A> --target <B>` crea il template in
`<artifacts_home>/<B>/debt-registry.md`; il formato delle voci e' nel template. Una voce si
chiude solo con `decisione` e `verifica` compilate, da un umano.

## Configurazione

Blocco opzionale `code_migration:` in `factory.config.yaml` (flag CLI > config > default):
`artifacts_home`, `default_plugin`, `join_by`, `library_package`, `parity_threshold`,
`debt_registry` (`{target}` sostituito con lo slug). A blocco assente valgono i default; gli
script funzionano comunque quando invocati esplicitamente.

**`migration/` non e' in `.gitignore`.** Nella derivata d'origine la cartella era ignorata in
blocco e la scelta e' stata rovesciata: nascondeva registri, verdetti e analisi scritte a
mano, che servono come evidenza di un gate. Una factory che vuole tenere fuori solo i JSON
rigenerabili aggiunga `migration/**/*.json`, lasciando versionati `verdict.md` e
`debt-registry.md`.

## Limiti dichiarati

- Estrazione degli import a regex sul sorgente privato dei commenti: non segue specifier
  calcolati, `package.json#imports`, alias definiti solo nel bundler, `extends` da pacchetto.
- Il compilatore Svelte viene caricato dal `node_modules` del repo analizzato: e' codice di
  quel repo che gira. Uno trovato **sopra** il repo (hoisting) viene rifiutato.
- Full-scan a ogni esecuzione: nessuna cache, per non introdurre difetti silenziosi.

## Cosa non e' stato portato dalla derivata

| Elemento | Perche' |
|---|---|
| `storybook-probe.mjs` + registro dei controlli | e' un probe di rendering a runtime (Playwright contro uno Storybook buildato) con controlli scritti per componenti specifici: e' il dominio dei probe funzionali, non dell'analisi statica. Il motore non conosce i componenti, ma senza registro non verifica nulla. L'ingresso dalle story resta come entry point del plugin `svelte` |
| orchestratore a «scheda componente» unificata | fondeva i quattro assi in una vista per un DS specifico; qui la fusione e' il verdetto per file |
| tassonomia delle categorie di debito e mapping DS v3 -> v4 | erano il dominio di quella migrazione; il registro qui ha `categoria` libera |
