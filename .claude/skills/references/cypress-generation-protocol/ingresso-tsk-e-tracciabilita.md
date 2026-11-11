# Ingresso `/cypress-gen` e campi del TSK

Riferimento della skill `cypress-generation-protocol`. Ambito: come il comando di ingresso legge un
TSK `layer: qa` e quali campi usa. Si legge in Fase 0 quando il TSK non indica in modo chiaro repo,
branch o fonte dei casi. Non contiene regole di fase.

## Comando di ingresso e campi del TSK

Si entra con `/cypress-gen <TSK-id>` (`.claude/commands/cypress-gen.md`). Il comando accetta solo TSK
`layer: qa`, si ferma con messaggio esplicito senza TSK, con un TSK di altro layer o con
`cypress_pipeline.enabled: false`, e prevede due gate umani: dopo l'analisi (Fase 1) e dopo la
verifica (Fase 3). Un esito `issues-found` della verifica ferma l'avanzamento: la Fase 4 non parte e
il TSK resta `in-progress`.

**Nessun campo di frontmatter nuovo.** Il comando legge i campi che ogni TSK ha già e il corpo:

| Dato | Dove | Uso |
|---|---|---|
| `layer`, `consumer`, `status`, `depends_on` | frontmatter | gate di ingresso (`layer: qa` obbligatorio) |
| `branch` | frontmatter | branch di lavoro; per il sorgente dell'applicazione vale il registro, salvo indicazione diversa nel TSK (Fase 0 punto 3) |
| Repo di test | corpo del TSK, sezione «Cosa»: il `name` del registro (`cypress_pipeline.repos`) oppure il suo `test_path` | risoluzione con `resolve_repo.py`; se non univoco, STOP e domanda al PM |
| Feature o area, casi in perimetro | corpo del TSK | perimetro dell'analisi |
| Fonte dei casi | corpo del TSK: path in `raw/` (test list, requisito) o spec esistente nel repo di test | citata con `[^src: ...]` negli artefatti |

Il lint del kanban richiede solo i campi obbligatori di ogni TSK (`id`, `layer`, `consumer`,
`priority`, `status`): un TSK `qa` con questi dati lo supera come ogni altro. Se in futuro serve un
campo strutturato (per esempio `cypress_repo:`), si introduce con un TSK dedicato e una voce in
`management/conventions.md`.

## Mappa fasi → sezioni del protocollo

| Esigenza | Sezione |
|---|---|
| Fasi 0..4 con `node --input-type=module --check`, token ledger, aggiornamento TSK | Fasi 0, 1, 2, 3, 4 |
| Onboarding per convenzioni `da_ricavare` | Fase 0-bis |
| Regole comuni dei test robusti | Golden rules |
| Artefatti in `code_quality/cypress/<TSK-id>/`, nessun artefatto nel repo di test | Principio di separazione, Fasi 1, 3, 4 |
| Controllo §ai_policy e commit | Controllo §ai_policy sullo spec e commit |
| Fonti da `raw/`, formati binari non letti direttamente | Fonti |
| Gap al wiki-keeper, non in wiki | Gap dell'applicazione e wiki |
