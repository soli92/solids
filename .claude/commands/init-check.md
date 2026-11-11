---
description: Diagnostica ambiente locale — verifica python3/git, shell, submodule, variabili e probe di rete opzionali. Produce tabella PASS/WARN/FAIL con esito READY/PARTIAL/BLOCKED.
argument-hint: "[--probes] [--json]"
version: "1.0"
since: "2026-10-05"
status: active
trigger: /init-check
owner: soli92
---

# /init-check — Diagnostica ambiente

Argomenti utente: `$ARGUMENTS`

Esegue check locali sull'ambiente di sviluppo e produce una tabella PASS / WARN / FAIL
in chat. Nessun endpoint esterno viene contattato in scope default.

Stato finale: **READY** se tutti i FAIL = 0 e WARN = 0; **PARTIAL** se FAIL = 0 ma
WARN > 0; **BLOCKED** se FAIL >= 1.

## Scopo

Il comando è diagnostico, non gatekeeping. Comunica la situazione dell'ambiente prima
di iniziare a lavorare, segnalando:
- cosa è sicuramente pronto (PASS)
- cosa manca ma non è bloccante per tutte le attività (WARN)
- cosa impedisce operazioni fondamentali e va risolto (FAIL)

## Sintassi

```
/init-check [--probes] [--json]
```

- `--probes`: attiva le probe di rete dichiarate in `environment.probes` di
  `factory.config.yaml` (opt-in). Le probe sono WARN o FAIL secondo il campo
  `required:` di ciascuna. In scope default nessun traffico di rete viene generato.
- `--json`: output JSON machine-readable invece della tabella.

## Procedura

### Step 0 — Parse argomenti

Costruisci la lista di argomenti da passare al tool:

```
args = ["python3", "tools/env/init_check.py"]
```

- Se `--probes` presente in `$ARGUMENTS`: aggiungi `--probes`
- Se `--json` presente in `$ARGUMENTS`: aggiungi `--json`

### Step 1 — Esegui il tool

```bash
python3 tools/env/init_check.py [<args>]
```

Il tool legge `factory.config.yaml` dalla root della factory (CWD). Se il blocco
`environment:` è assente, esegue solo i controlli base e dichiara
«environment non configurato».

### Step 2 — Output in chat

Mostra l'output del tool verbatim in chat, in un blocco di codice o come testo
preformattato. Non aggiungere sezioni extra o testo narrativo attorno all'output.

Le spiegazioni aggiuntive vanno nella sezione "Passo successivo" già inclusa
nell'output del tool (solo se stato != READY).

## Stato finale

```
Stato: READY       — 0 FAIL, 0 WARN
Stato: PARTIAL     — 0 FAIL, N WARN
Stato: BLOCKED     — N FAIL, M WARN
```

| Stato | Condizione | Exit code |
|---|---|---|
| READY | fail=0, warn=0 | 0 |
| PARTIAL | fail=0, warn>0 | 1 |
| BLOCKED | fail>=1 | 2 |

## Controlli sempre presenti (indipendentemente dalla config)

| Check | Stato se ko |
|---|---|
| python3 nel PATH | FAIL |
| PyYAML importabile | WARN: `/cost-alert` e la statusLine non valutano le soglie |
| git >= 2.40 | FAIL |
| shell (linux/macos/wsl/wsl-mnt/gitbash/unknown) | WARN su wsl-mnt e Windows nativo |
| git core.autocrlf | WARN se `true` |
| code_paths dichiarati esistono e sono repo git | FAIL se non trovati |
| submodule in-perimetro inizializzati | FAIL se non inizializzati; WARN se divergenti |

## Controlli da `environment:` in factory.config.yaml

Il blocco `environment:` è opzionale. Con blocco assente il tool dichiara
«environment non configurato» ed esce con lo stato derivato dai soli controlli base.

```yaml
environment:
  binaries:
    - name: node
      min_version: "20.0.0"
      version_cmd: "node --version"
      required: true
    - any_of:                 # basta uno: una sola riga, WARN se mancano tutti
        - {name: nvm, paths: ["$NVM_DIR/nvm.sh", "~/.nvm/nvm.sh"]}   # nvm e' una funzione di shell
        - fnm
      required: false
  env_files:
    - .env.local
  variables:
    source_file: .env.local   # opzionale: le chiavi si cercano nel file, non nell'ambiente
    required:
      - MY_API_KEY
    optional:
      - name: MY_OPTIONAL_VAR
        tied_to_capability: "feature_xyz"
  node_version_file: .nvmrc   # nella root e in ogni code_path che lo contiene
  probes:
    - name: my-service
      kind: http           # http | tcp | cmd
      target: "https://api.example.com/health"
      timeout_s: 5
      required: false      # false = WARN; true = FAIL
```

**Regola privacy (inviolabile)**: il tool non stampa mai il VALORE delle variabili
d'ambiente — solo nome e stato PASS/FAIL/WARN.

## Cross-link

- **Configurazione ambiente**: `factory.config.yaml` blocco `environment:`
- **Configurazione**: blocco `environment:` di `factory.config.yaml` (template commentato in fondo al file)
- **Comandi correlati**: `/run`, `/onboarding`
- **Tool**: `tools/env/init_check.py`
