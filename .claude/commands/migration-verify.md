---
name: migration-verify
description: "Verifica di migrazione del codice fra due repo: oracolo (A) e target (B). Mappa a quattro assi (import, libreria, modalita', derivazione), registro dei debiti, KPI parity_ratio, verdetto consolidated|conditional|reject. reject, divergent e ambiguous sono gate umani. Sola lettura sui repo. Funziona anche a code_migration.enabled: false."
argument-hint: "<oracle_repo> <target_repo> [--plugin=js-ts|svelte] [--join-by=path|name] [--fork=<commit>] [--library=<pkg>]"
allowed-tools: Bash, Read, Glob, Write
---

# /migration-verify

Risponde a: **«il target e' una migrazione consolidata dell'oracolo?»** — senza toccare nessuno
dei due repo. Protocollo: skill `code-migration-protocol`. Agenti: `code-cartographer`
(mappa) e `migration-verifier` (verdetto). Tooling e formato degli artefatti:
`tools/migration/README.md`.

**Esplicito = voluto.** Il comando funziona anche a `code_migration.enabled: false` o a
blocco assente in `factory.config.yaml`: il flag governa solo il dispatch automatico.

## Uso

```bash
/migration-verify ../app-legacy ../app-nuova
/migration-verify ../app-legacy ../app-nuova --plugin=svelte,js-ts --library=@org/ui-kit
/migration-verify ../ds-v3 ../ds-v4 --plugin=svelte --join-by=name --fork=v3.5.0
```

| Argomento | Default | Note |
|---|---|---|
| `<oracle_repo>` `<target_repo>` | — | path locali, letti in sola lettura |
| `--plugin` | `js-ts` | `svelte`, composizione `svelte,js-ts`, o path a un plugin `.mjs` |
| `--join-by` | `path` | `name` se la migrazione ha riorganizzato il layout dei file |
| `--fork` / `--since` | — | punto di fork dell'oracolo: **input umano**, mai dedotto |
| `--library` | `code_migration.library_package` | ancoraggio dell'asse B; senza, l'asse B e' saltato |
| `--entry` | `full` | `dir:<d>`, `plugin:astro-pages`, `plugin:storybook-stories` |
| `--src`, `--ignore` | tutto il repo | perimetro; `--ignore` per codice generato |
| `--debt`, `--parity`, `--threshold` | default per slug, nessuno, `0.95` | registro dei debiti, esiti di parita', soglia KPI |

## Esecuzione

1. **Preflight.** `node --version` (>= 18). Se `--fork` manca, chiedi all'utente se conosce il
   punto di fork; se non lo conosce si procede, dichiarando che il verdetto non potra' essere
   `consolidated`.
2. **Esegui** (motore unico):

   ```bash
   node tools/migration/migration-verify.mjs <oracle_repo> <target_repo> [opzioni]
   ```
   Exit `0` consolidated · `1` conditional · `3` reject · `2` errore d'ingresso.
3. **Leggi** `<artifacts_home>/<slug-target>/verdict.md` e riporta, nell'ordine: verdetto con
   la condizione che lo determina, `parity_ratio` con `coverage` (o «non osservato» e
   perche'), osservazioni mancanti per nome, gate aperti.
4. **Gate umani.** Se l'output contiene `GATE UMANI APERTI` (o `verdict.json.gates` non e'
   vuoto): presenta i gate JSON verbatim e **fermati**. Nessuna correzione, nessun rilancio
   automatico. Su `reject` il fix e' di un dev-agent sul target, dopo la decisione dell'utente.
5. Per un verdetto completo servono gli esiti di parita': vedi la Fase 3 della skill
   (`deep-functional-probe` su oracolo e target, raccolti in `parity.json`), poi
   `node tools/migration/verify.mjs --oracle <s-A> --target <s-B> --parity <file>`.

## Output (esempio)

```
Verifica di migrazione app-legacy -> app-nuova  (config: default (blocco code_migration assente))
  A oracolo: 29 file, 0 import non risolti
  A target:  31 file, 0 import non risolti
  B: saltato — nessuna libreria indicata (--library o code_migration.library_package)
  C target: non applicabile — nessun plugin caricato (js-ts) definisce un audit di modalita'
  D: onlyInA 0 · inBoth 29 · divergent 0 · onlyInB 2 · ambigui 0 (deriva computed)

VERDETTO: CONDITIONAL
  parity_ratio: non osservato (nessun esito di parita' fornito)
  [missing] parity_ratio non osservato (nessun esito di parita' fornito)
  [missing] nessun registro dei debiti dichiarato
```

## Vincoli

- **Sola lettura** sui due repo: la guard rifiuta ogni scrittura al loro interno, anche via
  symlink, e rifiuta un `artifacts_home` che vi cada dentro. Unica operazione git: `git log`
  sull'oracolo, solo con `--fork`/`--since`.
- **Artefatti factory-side** in `<artifacts_home>/<slug>/` (default `migration/`).
- Nessun `git add`/`commit`/`push`, nessuna scrittura in `wiki/` o `management/`.

## Diagnostica

| Sintomo | Causa | Rimedio |
|---|---|---|
| `artifacts_home ... cade dentro un repo analizzato` | si sta analizzando la factory stessa | analizzarne una sottodirectory o un worktree |
| `C target: NON OSSERVABILE — svelte/compiler non risolvibile` | dipendenze non installate nel target | installarle nel target, oppure accettare l'asse non osservato |
| `inBoth` vicino a zero con molti `onlyInA`/`onlyInB` | layout riorganizzato | `--join-by=name` |
| conteggi dominati da una cartella | codice generato | `--ignore '<regex>'`, dichiarandolo nel report |
| `fork "<x>" non e' un commit valido` | riferimento assente nell'oracolo | chiedere all'utente il riferimento corretto |
