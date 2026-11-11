---
name: code-migration-protocol
description: "Protocollo di verifica di una migrazione di codice fra due repo, oracolo e target: mappa a quattro assi, registro dei debiti, parita' funzionale, verdetto consolidated|conditional|reject con gate umani. Generico per linguaggio via plugin (js-ts, svelte). Opt-in code_migration."
---
# Skill — code-migration-protocol

Governa la verifica che un **target** (B, codice migrato) sia una migrazione consolidata di un
**oracolo** (A, il codice che funziona). Sequenzia `code-cartographer` (misura) e
`migration-verifier` (verdetto) sul tooling di `tools/migration/`; la correzione resta a un
dev-agent. La skill non contiene algoritmi: li hanno gli script.

**Principio fail-closed.** Nessun verde per assenza di osservazione; nessuna deduzione al
posto di un input umano (punto di fork, appaiamenti ambigui, chiusura di un debito); l'oracolo
e' la fonte di verita' sul comportamento atteso, il target non lo e' mai.

## Quando usarla

| Situazione | Uso |
|---|---|
| riscrittura o upgrade di un'app in un repo nuovo (framework, major di libreria, TS) | completo |
| porting di un sottoalbero verso un altro repo | assi A e D, verdetto senza asse C |
| capire quanto un target si e' allontanato dall'oracolo | solo assi A e D (`code-cartographer`) |
| un solo repo, nessun oracolo | non e' questa skill: code intelligence L1/L2/L3 lavora su un repo |

## Gating

`code_migration.enabled` (default `false`) governa il dispatch automatico da parte
dell'orchestratore. `/migration-verify` e l'invocazione esplicita degli agenti funzionano a
blocco assente (valgono i default). A flag spento la factory e' invariata.

## Parametri

| Parametro | Default | Note |
|---|---|---|
| `oracle_repo`, `target_repo` | — | path locali in sola lettura |
| `plugin` | `code_migration.default_plugin` / `js-ts` | `svelte`, composizione `svelte,js-ts`, o path a un plugin esterno |
| `join_by` | `path` | `name` quando la migrazione ha riorganizzato il layout |
| `fork` / `since` | — | **input umano**, mai dedotto |
| `library` | `code_migration.library_package` | ancoraggio dell'asse B; nessun valore cablato |
| `entry` | `full` | `dir:<d>`, `plugin:astro-pages`, `plugin:storybook-stories` |
| `artifacts_home` | `migration/` | relativa alla factory; mai dentro un repo analizzato |
| `parity_threshold` | `0.95` | soglia del KPI `parity_ratio` |

## Fasi

```
Fase 0  Preflight             node >= 18, path esistenti, slug distinti, fork dichiarato o no
Fase 1  Mappa (cartographer)  A su oracolo e target, B se c'e' una libreria, C sul target, D
Fase 2  Debiti                registro factory-side: init, popolamento umano, check
Fase 3  Parita' funzionale    esiti pass|fail per file su A e B (deep-functional-probe)
Fase 4  Verdetto (verifier)   consolidated | conditional | reject + gate umani JSON
Fase 5  Iterazione            reject/conditional -> dev-agent corregge -> si rilancia da Fase 1
```

### Fase 0 — Preflight

`node --version` >= 18. I due repo esistono e sono distinti. Se oracolo e target hanno lo
stesso basename (due worktree) gli slug diventano `<nome>-oracle`/`<nome>-target`. Chiedi
all'utente il punto di fork se non e' stato dato: senza, il verdetto non puo' essere
`consolidated`, e va detto **prima** di eseguire, non scoperto dopo.

### Fase 1 — Mappa a quattro assi

Delega a `code-cartographer`, o in un colpo solo:

```bash
node tools/migration/migration-verify.mjs <oracle_repo> <target_repo> --plugin=<p> [--join-by=<j>] [--fork=<c>] [--library=<pkg>]
```

> **[TRIGGER VINCOLANTE]** Prima di interpretare un artefatto o di scegliere `--entry`,
> `--join-by`, `--ignore`, leggi `.claude/skills/references/code-migration-protocol/assi-e-artefatti.md`.
> Se manca, fermati e segnala.

Da riportare sempre: import non risolti, archi fuori dai plugin, asse C `applicable` e
`observable` con la ragione, `driftStatus`, ambigui. Se un codice generato domina i conteggi
(es. traduzioni compilate), proponi `--ignore` e rilancia: non filtrare in silenzio.

### Fase 2 — Registro dei debiti

```bash
node tools/migration/debt-registry.mjs init --oracle <s-A> --target <s-B>
node tools/migration/debt-registry.mjs check --target <s-B>
```

Il registro e' versionato e contiene decisioni umane. Voci da proporre (mai da chiudere):
file `risk`/`error` dell'asse C, `divergent` senza decisione, regressioni di parita'. Una voce
`open` o `in-analysis` con `bloccante: si` porta il file a `reject`.

### Fase 3 — Parita' funzionale

Per i file appaiati (`inBoth`, `divergent`) servono esiti eseguiti su **entrambi** i repo.
Il canale e' la skill `deep-functional-probe` (una AC per invocazione, verdetto PASS|FAIL):
eseguila sull'oracolo e sul target per lo stesso scenario e registra
`{ "<relKey>": { "a": "pass", "b": "pass" } }` in `<artifacts_home>/<s-B>/parity.json`.
Un oracolo non `pass` invalida la verifica di quel file (`reject`): la spec e' sbagliata o
l'ambiente non e' quello atteso, non il target.

### Fase 4 — Verdetto

```bash
node tools/migration/verify.mjs --oracle <s-A> --target <s-B> --parity <artifacts_home>/<s-B>/parity.json
```

> **[TRIGGER VINCOLANTE]** Prima di comunicare un verdetto o di presentare un gate, leggi
> `.claude/skills/references/code-migration-protocol/verdetto-e-gate.md`. Se manca, fermati e segnala.

Exit `0` consolidated · `1` conditional · `3` reject · `2` errore d'ingresso. Se
`verdict.json.gates` non e' vuoto: presenta i gate verbatim e **STOP** fino a risposta esplicita.

### Fase 5 — Iterazione

Il fix e' di un dev-agent (`fe-dev`, `be-dev`, ...) sul target, con il report come input.
Poi si rilancia da Fase 1: gli artefatti sono full-scan, nessuna cache. Ordine di lavoro:
`bottomUpOrder` (foglie prima), i `shared` hanno raggio d'impatto maggiore.

## Vincoli

- **Sola lettura sui repo analizzati.** La guard di `tools/migration/lib/paths.mjs` rifiuta
  ogni scrittura dentro di essi (anche via symlink) e rifiuta alla costruzione un
  `artifacts_home` che vi cada dentro. Nessun `git add`/`commit`/`push` sui repo analizzati.
- **Artefatti factory-side** in `<artifacts_home>/<slug>/`. `migration/` non e' ignorata da
  git: registri e verdetti sono evidenza; i JSON si possono escludere a discrezione.
- **Nessun LLM nel percorso pass/fail**: il verdetto e' l'output dello script.
- La skill non scrive `wiki/log.md` e non tocca `factory.config.yaml`.

## Foglie

| Foglia | Contenuto | Trigger |
|---|---|---|
| `references/code-migration-protocol/assi-e-artefatti.md` | i quattro assi, entry point, join, fork, plugin, limiti | Fase 1 |
| `references/code-migration-protocol/verdetto-e-gate.md` | truth-table, KPI, gate JSON, cosa dire all'utente | Fase 4 |

Documentazione del tooling: `tools/migration/README.md`.
