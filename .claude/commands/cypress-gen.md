---
description: Esegue la pipeline di generazione dei test Cypress su un TSK qa (analisi, generazione, verifica, chiusura) con gate umano dopo l'analisi e dopo la verifica. Accetta solo TSK layer qa; no-op con cypress_pipeline.enabled false.
argument-hint: <TSK-id> [--with-run]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /cypress-gen — Generazione dei test Cypress su un TSK qa

Comando della capability `cypress_pipeline` (opt-in, `factory.config.yaml → cypress_pipeline.enabled`).
Thin dispatcher: la procedura, gli artefatti e le regole stanno in
[`cypress-generation-protocol`](../skills/cypress-generation-protocol.md); qui si decide solo se
partire, chi invocare e dove fermarsi. Esecuzione esplicita nel thread principale (ha `Bash`).

Argomenti utente: `$ARGUMENTS`

- Primo argomento: **TSK-id** (es. `TSK-123`), obbligatorio.
- `--with-run`: dopo la verifica chiede all'operatore se eseguire anche gli spec (Fase 3-bis).
  Senza il flag la Fase 3-bis non parte.

## Controlli iniziali (in quest'ordine, al primo fallimento STOP)

1. **TSK mancante.** `$ARGUMENTS` vuoto → STOP con:
   > «`/cypress-gen` richiede un TSK: `/cypress-gen <TSK-id>`. Il TSK deve avere `layer: qa`.»
2. **TSK non trovato o ambiguo.** `Glob management/kanban/**/<TSK-id>.md`: 0 o più di 1 risultato →
   STOP «TSK non trovato / ambiguo».
3. **Layer.** Frontmatter `layer:` diverso da `qa` → STOP con:
   > «`<TSK-id>` ha `layer: <x>`: `/cypress-gen` accetta solo TSK `layer: qa`. Per gli altri layer usa `/dev <TSK-id>`.»
   Nessun override: il comando non si forza su altri layer.
4. **Flag.** `python3 tools/cypress/resolve_repo.py --list`: `"enabled": false` → STOP con:
   > «Capability spenta: `cypress_pipeline.enabled` è `false` in `factory.config.yaml`. Nulla è stato letto né scritto.
   > Accenderla è una decisione dell'operatore, con la procedura di revisione della factory per le modifiche di config.»
   Il comando non modifica mai il flag.
5. **Gate del TSK.** `status: todo` (oppure `in-progress` se è una ripresa, vedi §Ripresa), nessun
   `depends_on:` aperto. Altrimenti STOP con il motivo.
6. **Repo di test.** Dal corpo del TSK e dal registro (campi letti: `.claude/skills/references/cypress-generation-protocol/ingresso-tsk-e-tracciabilita.md`).
   Non univoco → STOP e domanda al PM. Poi `python3 tools/cypress/resolve_repo.py <name>`:
   `error` → riporta il comando suggerito dal resolver e fermati; `ok` → prosegui.

Un TSK `consumer: human` può essere eseguito solo come override one-shot esplicito dell'operatore,
come per `/dev`: lo si dichiara in chat e non si modifica il file.

## Procedura

Preflight multiutente (`tools/session/active_sessions.py`: `gc`, `conflicts`, `claim`; `release` a fine
lavoro) su `code_quality/cypress/<TSK-id>` e sul `test_path`. Un claim altrui attivo è un WARN in chat.

1. **Presa in carico.** `status: todo → in-progress` (solo `status:` e `updated:`; mai il corpo).
2. **Analisi (Fasi 0, 0-bis, 1).** Agente `cypress-test-analyst`. Produce `analisi.md`,
   `test-cases.json`, `users.json`, `gaps.json`, `generation-plan.md` in `code_quality/cypress/<TSK-id>/`.
3. **GATE UMANO 1 — dopo l'analisi.** Mostra in chat: repo risolto e fonte (submodule o override),
   casi in perimetro, gap, utenze necessarie (solo riferimenti), spec previsti. Chiedi:
   «Procedo con la generazione? [sì / no / correggi il piano]». Senza un «sì» esplicito non si genera.
   Con «no» il TSK resta `in-progress`, gli artefatti restano per la ripresa.
4. **Generazione (Fase 2).** Agente `qa-dev`, §Modalità Cypress. Scrive solo gli spec del piano nel `test_path`.
5. **Verifica (Fase 3).** Agente `cypress-test-reviewer`, mai lo stesso agente della generazione.
   Un report per spec in `code_quality/cypress/<TSK-id>/review/`.
6. **GATE UMANO 2 — dopo la verifica.** Mostra il verdetto per spec (`pass`, `changes-applied`,
   `issues-found`), le correzioni applicate dal reviewer e i blocker aperti. Chiedi:
   «Chiudo (controlli di Fase 4, commit, handoff)? [sì / no]».
   - **Esito `issues-found` su almeno uno spec: il TSK non avanza.** Non si chiede la chiusura: si
     elencano i finding, il TSK resta `in-progress`, non si esegue la Fase 4 (niente commit, niente
     `status: done`, niente `done_by`). Si corregge (nuovo giro di `qa-dev` sui soli finding, poi
     nuova verifica) oppure si ferma qui su decisione dell'operatore.
   - Tutti `pass` o `changes-applied` → si chiede la chiusura.
7. **Esecuzione degli spec (Fase 3-bis).** Solo con `--with-run` e conferma dell'operatore, perché
   il login può essere interattivo.
8. **Chiusura (Fase 4).** Dopo il «sì» del gate 2: `node --input-type=module --check`, controllo
   §ai_policy con 0 corrispondenze, commit con `tools/vcs/sm-commit.sh` (o controllo equivalente su
   clone personale), `consumo-token.md` dal token ledger, handoff del TSK (`status: done`,
   `dev-handoff`, `wiki/log.md`), gap proposti al wiki-keeper. Il commit nel repo di test è subordinato al
   «sì» del gate 2; `done_by` solo all'autore dei `work_commits`.

## Ripresa

Un TSK `in-progress` con artefatti già in `code_quality/cypress/<TSK-id>/` riparte dalla prima fase
mancante (analisi presente → si riparte dal gate 1; review presente con `issues-found` → si riparte
dalla generazione sui soli finding). Il gate umano si ripresenta sempre.

## Report finale

TSK e repo di test; fasi eseguite; spec toccati; verdetto della verifica; esito dei controlli di
Fase 4 (o motivo per cui non sono partiti); gap proposti al wiki-keeper; cartella degli artefatti.

## Vincoli

- Mai su TSK non `qa`, mai con il flag spento, mai senza TSK.
- Nessun artefatto nel repo di test: analisi, piani, review e report stanno in `code_quality/cypress/<TSK-id>/`.
- Nessuna scrittura in `wiki/` né in `raw/`; i gap si propongono al wiki-keeper.
- Il generatore non scrive la propria review. Nessun `--no-verify`. Operazioni VCS distruttive solo con gate umano.
- Nessun riferimento alla factory, ad AI o a ID kanban negli spec e nei messaggi di commit (§ai_policy).
