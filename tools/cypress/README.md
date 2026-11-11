# tools/cypress — pipeline dei test Cypress

Strumenti della pipeline di generazione dei test Cypress (capability `cypress_pipeline`, opt-in,
spenta per default). Il registro dei repo di test e' il blocco `cypress_pipeline:` di
`factory.config.yaml`; la procedura e' in `.claude/skills/cypress-generation-protocol.md`.

```yaml
cypress_pipeline:
  enabled: false
  reporter: generic            # profilo di run_report.py; sovrascrivibile per repo
  repos: []
  #  - name: mia-app-cypress-test            # identificatore del repo di test
  #    test_path: code_repos/mia-app-cypress-test
  #    layout: root                          # root | <sottocartella> | da_verificare
  #    source: mia-app                       # repo dell'applicazione testata
  #    source_path: code_repos/mia-app
  #    source_branch: develop                # branch su cui si verificano i selettori
  #    conventions_ref: ""                   # path in raw/ o pagina wiki delle convenzioni
  #    conventions_status: da_ricavare       # presenti | da_ricavare
  #    reporter: generic                     # opzionale, per questo repo
```

## resolve_repo.py

Restituisce in JSON i path effettivi di un repo di test e del repo sorgente dell'applicazione,
e la fonte usata per ciascuno: `submodule` (default) o `override` (clone personale).

```bash
python3 tools/cypress/resolve_repo.py --list          # repo registrati, flag e reporter
python3 tools/cypress/resolve_repo.py <name>          # path effettivi
```

| `status` | exit | Quando |
|---|---|---|
| `ok` | 0 | path risolti; avvisi in `warnings` (remote o branch diversi dal registro) |
| `disabled` | 0 | `cypress_pipeline.enabled: false` o blocco assente: nessuna risoluzione |
| `error` | 1 | submodule non inizializzato, override inesistente o non repo, voce incompleta, git in timeout |
| `usage` | 2 | argomenti mancanti o repo non nel registro |

Sola lettura: legge `factory.config.yaml`, `.gitmodules`, `tools/vcs/.env.local-repos` e lo stato
git dei repo (branch, commit, remote). Non scrive nulla. Dipende da `tools/vcs/smlib/factory_config.py`
(`load_env_file`), stessa fonte di `sm_update --from-local`.

### Clone personali (override per operatore)

Chi lavora su un proprio clone invece che sul submodule lo dichiara in
`tools/vcs/.env.local-repos` (gitignored, lo stesso file di `sm_update --from-local`). La chiave e'
`LOCAL_REPO_<NOME>`, con `<NOME>` uguale al `name` del repo di test o al `source` del repo
applicativo, in maiuscolo e con `-` sostituito da `_`. Vale anche una variabile d'ambiente con lo
stesso nome.

```bash
LOCAL_REPO_MIA_APP_CYPRESS_TEST="/percorso/del/clone/mia-app-cypress-test"
LOCAL_REPO_MIA_APP="/percorso/del/clone/mia-app"
```

Il path deve essere la radice del repo git (la cartella che contiene `.git`). Il resolver avvisa se
il remote del clone e' diverso da quello del submodule in `.gitmodules`, o se il sorgente e' su un
branch diverso dal `source_branch` del registro. Un submodule in detached HEAD non produce avvisi:
si riporta il commit.

### Submodule non inizializzato

Il resolver si ferma e indica il comando, per esempio
`python3 tools/vcs/sm_doctor.py --target <nome>`. L'inizializzazione la decide l'operatore.

## run_report.py

Lancia uno o piu' spec con la config del repo di test e scrive il report in
`code_quality/cypress/<TSK-id>/run-<ts>/` (mai nel repo di test), con un `esito.md` di totali, suite,
test falliti e link. Il formato dipende dal **profilo di reporter**.

```bash
python3 tools/cypress/run_report.py --tsk TSK-123 --repo <name> --spec "cypress/e2e/area/x.cy.js" [--headed]
python3 tools/cypress/run_report.py --tsk TSK-123 --test-path <path> --merge-only code_quality/cypress/TSK-123/run-<ts>
python3 tools/cypress/run_report.py ... --dry-run     # solo i comandi
```

| exit | Quando |
|---|---|
| 0 | report prodotto, anche con test falliti (sono nell'esito) |
| 1 | strumenti mancanti nel `node_modules` del repo di test, Cypress senza JUnit |
| 2 | argomenti non validi, config non trovata, profilo sconosciuto, cartella del report dentro il repo di test |

Usa i binari del repo di test (`node_modules/.bin`): se mancano indica `npm ci` nel repo. Non
modifica la config del repo e non scrive nel repo. Si versiona solo `esito.md` (vedi `.gitignore`).
La config di Cypress e' cercata fra `cypress.config.{js,ts,mjs,cjs}`; `--config-file` la forza.

### Profili di reporter

Ordine di scelta: `--reporter-module`, `--reporter`, `reporter:` della voce del repo, `reporter:`
globale del registro, `generic`.

| Profilo | Cosa produce | Dipendenze npm |
|---|---|---|
| `generic` (default) | reporter integrato `junit` di Cypress; JUnit unito, screenshot, `esito.md` markdown neutro | solo Cypress |

**Profilo custom** (per riprodurre il formato di una pipeline CI propria): un file Python che espone
`PROFILE`, istanza di una sottoclasse di `ReporterProfile`, passato con `--reporter-module`.

```python
# mio_profilo.py
from run_report import ReporterProfile

class MioProfilo(ReporterProfile):
    name = "mio-profilo"
    required_tools = ("mochawesome-merge",)          # binari attesi in node_modules/.bin

    def cypress_args(self, run_dir):                 # argomenti del reporter, la config del repo non si tocca
        return ["--reporter", "junit",
                "--reporter-options", f"mochaFile={run_dir}/junit/junit-report-[hash].xml"]

    def finalize(self, test_path, run_dir, stamp, dry):
        # merge, HTML, ecc.; ritorna righe markdown per la sezione «File» di esito.md
        return ["- Report HTML: ..."]

PROFILE = MioProfilo()
```

Il JUnit unito, gli screenshot e `esito.md` li produce sempre lo script dai file in
`<run-dir>/junit/`: il profilo custom deve far scrivere li' il JUnit per avere totali coerenti.

Test: `python3 -m pytest tools/tests/test_cypress_*.py`.
