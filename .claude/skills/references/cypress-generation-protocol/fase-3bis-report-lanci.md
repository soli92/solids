# Fase 3-bis — esecuzione degli spec e report dei lanci (opzionale)

Riferimento della skill `cypress-generation-protocol`. Ambito: solo l'esecuzione reale degli spec
con `tools/cypress/run_report.py`, i profili di reporter e cosa si versiona. Si legge solo se
l'operatore chiede l'esecuzione, e sempre dopo la Fase 3. Senza richiesta esplicita non si esegue
nulla e questo file non serve.

Il login dello spec può essere interattivo: per questo l'esecuzione parte solo su richiesta.

```bash
python3 tools/cypress/run_report.py --tsk <TSK-id> --repo <name> \
  --spec "<spec relativo al repo>" [--spec ...] [--headed]
python3 tools/cypress/run_report.py --tsk <TSK-id> --test-path <test_path> \
  --merge-only code_quality/cypress/<TSK-id>/run-<ts>
```

Prerequisiti: `npm ci` nel repo di test (lo decide l'operatore; `node_modules` è fuori da git). Le
shell di VS Code esportano `ELECTRON_RUN_AS_NODE=1`: lo script la toglie al solo processo di
Cypress, altrimenti il binario si ferma con «bad option: --no-sandbox».

## Profili di reporter

Il formato del report è un **profilo** (`reporter:` in `cypress_pipeline` o nella voce del repo,
oppure `--reporter`). Default `generic`.

| Profilo | Risultato in `code_quality/cypress/<TSK-id>/run-<AAAAMMGG_HHMMSS>/` |
|---|---|
| `generic` | reporter `junit` integrato di Cypress: `junit/junit-report-<hash>.xml` per spec, `html_report/junit-report.xml` unito, `screenshots/` e copia in `html_report/screenshots/`, `esito.md` con totali, test falliti e link. Nessun pacchetto npm oltre a Cypress |
| custom | un modulo Python che espone `PROFILE` (sottoclasse di `ReporterProfile`), passato con `--reporter-module`: sceglie gli argomenti del reporter e gli artefatti post-lancio (merge, HTML) per riprodurre il formato di una pipeline CI propria. Esempio in `tools/cypress/README.md` |

Il JUnit unito, gli screenshot e `esito.md` li produce sempre lo script, dai file in
`<run-dir>/junit/`: un profilo custom deve far scrivere lì il JUnit. Se un profilo richiede
strumenti npm (`required_tools`), lo script si ferma e indica `npm ci` nel repo di test.

## Cosa si versiona

Accanto ai file del lancio c'è `esito.md`. Si versiona **solo** `esito.md`: report, JUnit e
screenshot contengono dati dell'ambiente di test e sono esclusi da `.gitignore`. Nel repo di test
non si scrive niente e la sua config di reporter non si modifica: reporter, opzioni e cartella degli
screenshot si passano da riga di comando (`--reporter`, `--reporter-options`,
`--config screenshotsFolder=`). Un hook `after:run` della config del repo può scrivere i propri file
fuori dalla cartella del lancio: non fanno parte del report.

I TSK human di esecuzione registrano l'esito con link a `esito.md`.
