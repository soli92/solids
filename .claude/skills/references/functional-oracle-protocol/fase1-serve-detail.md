# Fase 1 — Serve: procedura dettagliata

**Ambito**: passi 1-8 dell'avvio server, readiness fail-loud verbatim, Playwright
check, teardown garantito. Foglia di supporto a `functional-oracle-protocol.md` (EP-018).

## Passi 1-8

1. Read `factory.config.yaml.fe_correctness.functional_oracle`. Se `enabled: false` →
   ABORT pulito: log a chat «Functional oracle disabilitato; abilitare con
   `fe_correctness.functional_oracle.enabled: true`». No-op dichiarato (R.P3).

2. Read TSK target: frontmatter (`id`, `layer`, `code_path`/`target`,
   `functional_status`, `functional_acceptance_spec`) + body markdown.

3. Risolve `code_path` dal frontmatter TSK: legacy `code_path:` singolo, oppure
   `target:` → entry in `code_paths`.

4. Calcola `current_iter`: se `functional_status` è assente/`pending` → `N = 1`;
   se è `conditional` (loop in corso) → `N = <ultimo iter> + 1`.

5. **INVOCA ADR-064 Step 1.0** (app-lifecycle serve) con i parametri:

   ```
   ADR-064 Step 1.0:
     code_path = <path risolto al package target>
     mode      = "preview"       # preferisci build esistente (vite preview / npm run preview)
                                 # fallback: "dev" (npm run dev) se nessun build disponibile
     readiness_check = HTTP 200 su <host>:<port>
     timeout_ms = fe_correctness.functional_oracle.serve_timeout_ms  # default 30000
   Output:
     server_url  : string   # es. http://localhost:5173
     server_pid  : int      # PID del processo server, per teardown garantito
     server_port : int      # porta effettiva
   ```

   La CWD di esecuzione è la directory del package target (ADR-064 §D). CWD errata
   → **errore tecnico fail-loud**, mai degrado silenzioso (`Cannot find module` o
   binding-port errati).

6. **Fail-loud su timeout readiness** (ADR-064 §C). Se HTTP 200 non raggiunto entro
   `timeout_ms` → STOP con messaggio azionabile **verbatim**:

   > Functional oracle: il server non ha raggiunto readiness in `<timeout_ms>`ms.
   > Verificare: (1) `npm run build` o `npm run preview` funzionano manualmente nel
   > package `<code_path>`; (2) la porta `<port>` non è occupata; (3) il campo
   > `fe_correctness.functional_oracle.serve_timeout_ms` (default 30000) è sufficiente
   > per il tuo ambiente. Log server: vedi `.factory-runners/<TSK-id>-serve.log`.

   Il teardown del PID registrato è obbligatorio anche in caso di abort.

7. Verifica prerequisito **Playwright** via Bash: `npx playwright --version` dalla CWD
   del package target. Se exit code `!= 0` → **STOP fail-loud verbatim**:

   > Functional oracle richiede Playwright. Eseguire dalla directory `<code_path>`:
   > `npm i -D @playwright/test && npx playwright install --with-deps chromium`.
   > Vedi runbook `wiki/runbooks/visual-oracle-installation.md` se disponibile.

   Nessun degrado silenzioso (ADR-064 §E: `no-visual` è eccezione dichiarata, non default).

8. Crea la cartella side-channel per gli artefatti:
   `code_quality/reports/<TSK-id>-functional-iter-<N>/` (ADR-065 §Storage).

## Teardown garantito

Il `server_pid` registrato al passo 5 **DEVE essere terminato** al termine della skill
(pass, reject, abort, errore — ADR-064 §Conseguenze «Teardown del server obbligatorio»):

```bash
bash: kill <server_pid>      # graceful SIGTERM
# se dopo 5s il processo è ancora vivo:
bash: kill -9 <server_pid>
```

Il blocco di cleanup deve essere eseguito anche se le fasi successive falliscono.

## Output prodotto

`server_url`, `server_pid`, `server_port` registrati; cartella artefatti
`code_quality/reports/<TSK-id>-functional-iter-<N>/` creata; `code_path` risolto;
`current_iter` calcolato.

**Criterio**: `server_url` raggiungibile HTTP 200 **AND** `npx playwright --version`
exit 0 **AND** cartella artefatti creata.

[^src: design_&_architecture/decisions/ADR-064.md §C §D — readiness/CWD/fail-loud]
[^src: design_&_architecture/decisions/ADR-065.md §Storage — side-channel reports]
[^src: management/kanban/EP-018-fe-functional-oracle/US-068-skill-functional-oracle-protocol/US-068.md §Fase 1]
