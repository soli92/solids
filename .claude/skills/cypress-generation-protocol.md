---
name: cypress-generation-protocol
description: "Protocollo della pipeline di generazione dei test Cypress per i repo di test registrati in factory.config.yaml → cypress_pipeline: fase 0 risoluzione del repo e lettura delle convenzioni, 0-bis onboarding del repo con convenzioni da ricavare, 1 analisi, 2 generazione, 3 verifica, 3-bis esecuzione con report (profilo di reporter), 4 chiusura. Golden rules, artefatti in code_quality/cypress/, una cartella per TSK, mai nel repo di test, controllo §ai_policy sullo spec prima del commit, gap proposti al wiki-keeper. Opt-in: no-op con cypress_pipeline.enabled: false."
---

# Protocollo di generazione dei test Cypress — fasi 0..4

Skill procedurale della capability `cypress_pipeline` (`factory.config.yaml → cypress_pipeline`,
opt-in R.P3, spenta per default). Si applica a un TSK `layer: qa` che chiede di scrivere o allineare
spec Cypress in un repo di test registrato. Tutto ciò che non ha fonte è marcato «da confermare».

**Interruttore.** Prima di tutto: `python3 tools/cypress/resolve_repo.py <name>`. Se risponde
`status: disabled` (`cypress_pipeline.enabled: false`) il protocollo è no-op: non si legge nulla,
non si scrive nulla, si dice in chat che la capability è spenta e ci si ferma. Nessuna fase sotto
produce effetti con la capability spenta. Il flag non lo modifica la pipeline: lo accende
l'operatore.

**Perimetro del registro.** Si lavora solo sui repo elencati in `cypress_pipeline.repos[]`. Un repo
non registrato non si usa: lo si aggiunge al registro prima (decisione dell'operatore).

## Principio di separazione

La pipeline produce **due cose in due posti diversi**:

| Cosa | Dove | Contenuto |
|---|---|---|
| Spec (e comandi di supporto) | repo di test (`test_path` del resolver) | solo codice di test, in stile umano, senza tracce factory (§ai_policy) |
| Artefatti di lavoro | `code_quality/cypress/<TSK-id>/` della factory | analisi, piani, review, report dei lanci, consumo token |

Nel repo di test non entra **nessun** artefatto: né cartelle di lavoro, né estrazioni, né file di
istruzioni della factory, né sezioni «consumo token». Niente va escluso con `.git/info/exclude`: non
deve esistere.

## Fonti

| Cosa | Dove |
|---|---|
| Registro dei repo, flag, sorgente e branch | `factory.config.yaml → cypress_pipeline`, letto solo tramite il resolver |
| Path effettivi (submodule o override di operatore) | `python3 tools/cypress/resolve_repo.py <name>`; vedi `tools/cypress/README.md` |
| Requisiti, test list, regole comuni, convenzioni, KB | solo da `raw/` o dalla wiki (`conventions_ref`); mai da path personali dell'operatore |
| Test list (xlsx) e docx dei requisiti | non si leggono direttamente: conversione in testo o `/sync-docs` (che estrae in `raw/`); poi si cita il testo estratto. Il file originale non si modifica mai |
| PDF dei requisiti | `/sync-docs` (agente `sync-docs`): estrae in `raw/` e aggiorna il manifest |
| Selettori e comportamento dell'applicazione | repo sorgente indicato dal resolver (`source_path`) sul `source_branch`: si legge `origin/<source_branch>`, mai un merge fra branch per leggere |

Le citazioni seguono `citation-rules`: ogni caso, utenza e selettore in un artefatto porta
`[^src: ...]` verso `raw/` o verso file e riga del sorgente.

## Fase 0 — risoluzione del repo e convenzioni

1. Leggere il TSK (campi `layer`, `consumer`, `status`, `branch`, `depends_on`) e individuare il
   repo di test dal suo corpo o dal registro. Se il TSK non lo indica in modo univoco: STOP, domanda al PM.
2. `python3 tools/cypress/resolve_repo.py <name>`. Esiti:
   - `disabled` → no-op (vedi sopra).
   - `error` (submodule non inizializzato, override inesistente) → riportare il comando suggerito
     dal resolver; l'inizializzazione la decide l'operatore. Non procedere.
   - `ok` → annotare `test_path`, `source_path`, `source_branch`, fonte (`submodule`|`override`)
     e gli eventuali `warnings` (remote o branch diversi dal registro) nell'`analisi.md`.
3. Verificare il branch del sorgente: i selettori si leggono su `source_branch`. Se il TSK indica un
   branch diverso dal registro, vale il TSK e la differenza si scrive nell'`analisi.md`.
4. Lettura delle convenzioni, secondo `conventions_status`:
   - `presenti` → leggere la copia in `raw/` o la pagina wiki (`conventions_ref`); finché il
     riferimento è vuoto, annotare «da confermare» ogni regola presa dal solo clone locale.
   - `da_ricavare` → Fase 0-bis, prima di qualsiasi generazione.
5. Preflight multiutente sui file che si scriveranno (vedi §Preflight).

## Fase 0-bis — onboarding del repo di test

Si esegue solo per un repo con `conventions_status: da_ricavare`. Obiettivo: produrre il
riferimento delle convenzioni **AS-IS**, cioè ricavate dal repo così com'è, senza correggerlo né
allinearlo a uno stack ideale (la riscrittura delle suite è fuori perimetro).

Output: `code_quality/cypress/<TSK-id>/convenzioni-as-is.md`, con le sei sezioni e il metodo di
[references/cypress-generation-protocol/onboarding-as-is.md](references/cypress-generation-protocol/onboarding-as-is.md):
login, config, utenze, selettori, struttura degli spec, gotcha. Ogni riga cita `file:riga` del repo
di test. Sola lettura sul repo; credenziali eventualmente trovate in chiaro nei config si segnalano
come gap (senza copiarne il valore) e non si riportano in nessun artefatto.

La pagina wiki delle convenzioni la scrive il wiki-keeper; la pipeline propone il testo, non il
file. Finché `conventions_ref` è vuoto, `convenzioni-as-is.md` è la fonte di lavoro del solo TSK
corrente.

## Fase 1 — analisi (sola lettura)

Produce in `code_quality/cypress/<TSK-id>/`:

| File | Contenuto |
|---|---|
| `analisi.md` | repo risolto (Fase 0), fonti lette, casi in perimetro, rischi, scelte di selettore |
| `test-cases.json` | casi estratti da test list e requisiti, ciascuno con citazione |
| `users.json` | utenze necessarie per ruolo e ambiente: **solo riferimenti** (nome della chiave di config o variabile d'ambiente), mai valori di credenziali |
| `gaps.json` | selettori mancanti, utenze mancanti, bug noti dell'applicazione, casi non automatizzabili |
| `generation-plan.md` | per ogni spec: file di destinazione, casi coperti, comandi di supporto da usare o creare, dati |

Schema condiviso: `test-cases.json` (`status: planned|generated|reviewed`), `users.json`, `gaps.json`
(`missingUsers/systemDateDependent/outOfScope/notes` dell'analisi, più
`missingDataCy/infraGaps/kbDivergences` della generazione). L'analisi crea (`planned`), la
generazione aggiorna (`specFile`, `selectors`, `generated`) senza togliere i campi dell'analisi, la
revisione porta a `reviewed` e scrive `review/review-<basename-spec>.json|.md`. Il consumo token
non chiude i Markdown: va in `consumo-token.md` (Fase 4).

I selettori si verificano sul sorgente (`source_path` @ `source_branch`): ogni `#id` usato nel piano
deve comparire in un file del sorgente, citato. Un id non trovato va in `gaps.json`, non nel piano.

## Fase 2 — generazione

1. Scrivere gli spec (e le sole modifiche ai comandi di supporto previste dal piano) nel `test_path`,
   nel layout e con le convenzioni della Fase 0, senza riscrivere ciò che il TSK non tocca.
2. Applicare le golden rules (sotto).
3. Testi nello spec: descrizioni dei test e commenti nella lingua della convenzione del repo,
   identificatori in inglese; i commenti spiegano il *perché* del codice, mai l'origine della richiesta.
4. Un TSK = un cambio coerente: niente fix opportunistici fuori scope; i problemi collaterali
   diventano gap in `gaps.json`.

## Fase 3 — verifica (generatore ≠ critico)

La verifica statica la fa un passaggio separato dalla generazione (`llm-generator-separation-protocol`):
l'agente che ha scritto lo spec non scrive la propria review. Per ogni spec:

- `review/review-<spec>.json` e `review/review-<spec>.md` in `code_quality/cypress/<TSK-id>/`, uno
  per spec (nome dello spec nel nome del file);
- controlli: golden rules, selettori presenti nel sorgente al `source_branch`, coerenza con
  `generation-plan.md` e con `test-cases.json`, assenza di tracce §ai_policy (vedi sotto);
- correzioni ammesse al reviewer: solo quelle sicure e meccaniche (typo, selettore con id verificato,
  import); il resto resta come finding;
- la verifica di questa fase è statica più `node --check` in Fase 4; l'esecuzione reale degli spec è
  la Fase 3-bis, opzionale.

## Fase 3-bis — esecuzione e report dei lanci (opzionale, su richiesta dell'operatore)

Si esegue solo se l'operatore lo chiede, perché il login dello spec può essere interattivo, e
sempre dopo la Fase 3. **Quando l'operatore la chiede, leggere prima**
[`.claude/skills/references/cypress-generation-protocol/fase-3bis-report-lanci.md`](references/cypress-generation-protocol/fase-3bis-report-lanci.md)
(comando `tools/cypress/run_report.py`, profili di reporter, cosa si versiona). Senza richiesta non si
esegue nulla. Vincoli che restano qui: nel repo di test non si scrive niente e la sua config di
reporter non si modifica; si versiona **solo** `esito.md` (report, JUnit e screenshot contengono dati
dell'ambiente di test); i TSK human di esecuzione registrano l'esito con link a `esito.md`.

## Fase 4 — chiusura

1. `node --input-type=module --check < <spec>` per ogni spec generato o modificato (exit 0).
   Nota: `--check` con `--input-type` legge da stdin. Per gli spec CommonJS o TypeScript si usa il
   controllo di sintassi equivalente del repo (da dichiarare nel `generation-plan.md`). Un esito non
   zero blocca la chiusura.
2. Controllo §ai_policy sullo spec (sezione «Controllo §ai_policy sullo spec e commit») con esito 0 violazioni.
3. Commit nel repo di test (stessa sezione).
4. Consumo token: leggere il dato dal token ledger della sessione (`token-ledger`,
   `show-session-tokens.py`) e scriverlo in `code_quality/cypress/<TSK-id>/consumo-token.md`
   (non nel repo di test, non nello spec). Dato reale dal transcript, mai stimato a mano.
5. Aggiornare il TSK per i soli campi ammessi dal proprio protocollo di handoff (`dev-handoff`,
   `vcs-handoff`); `done_by` solo all'autore dei `work_commits`.
6. Gap dell'applicazione: proporli al wiki-keeper (sezione dedicata sotto), poi `release` del claim.

## Golden rules

Regole comuni di «test robusti», valide per ogni repo di test registrato. Le convenzioni specifiche
del repo (strategia dei selettori, login, struttura) prevalgono sulla forma ma non sulla sostanza
di queste sei famiglie.

1. **Dati deterministici.** Lo spec non dipende da dati che cambiano fra esecuzioni (date correnti,
   contatori, ordine di liste non garantito, record creati da altri): o li fissa o li crea e li
   ricava nello spec stesso.
2. **Niente asserzioni a vuoto.** Ogni test asserisce almeno uno stato o un testo osservabile; niente
   `should('exist')` su elementi che esistono comunque, niente test che passano senza verificare.
3. **Niente skip silenziosi.** Se un caso non è automatizzabile o manca un prerequisito, il test
   fallisce in modo esplicito o è escluso con motivazione visibile (`cy.log('SKIP: …')` e
   `this.skip()`) e voce in `gaps.json`; mai un `return` o un `if` che salta l'asserzione senza dirlo.
4. **Attese su eventi.** Si attende una risposta intercettata (`cy.intercept` + `cy.wait('@alias')`)
   o un elemento nello stato atteso; niente `cy.wait(<ms>)` fissi.
5. **Intercept tolleranti.** Gli intercept non dipendono da query string, ordine o campi che non
   fanno parte del caso; si usano pattern di URL che reggono variazioni non rilevanti (per esempio
   il jolly finale sugli URL con query string).
6. **Bug noti nei gap.** Un comportamento errato dell'applicazione non si codifica come atteso e non
   si aggira: va in `gaps.json` con citazione, e lo spec lo dichiara come caso noto.

Regole proprie di un repo di test (per esempio selettori per `#id`, divieto di `cy.login()` nello
spec, selettori con fallback fra due versioni di un design system) non stanno qui: vivono nelle
convenzioni del repo (`conventions_ref` o `convenzioni-as-is.md`). Una KB di best practice, se
presente in `raw/`, descrive lo stack **target**, non lo stato attuale: le differenze diventano
migliorie in `gaps.json → kbDivergences`, mai regole.

## Agenti

| Fase | Agente |
|---|---|
| 0, 0-bis, 1 — analisi | `cypress-test-analyst` (`.claude/agents/cypress-test-analyst.md`) |
| 2, 4 — generazione e chiusura | `qa-dev`, §Modalità Cypress |
| 3 — verifica | `cypress-test-reviewer` (`.claude/agents/cypress-test-reviewer.md`), mai lo stesso agente della generazione |

## Controllo §ai_policy sullo spec e commit

Gli spec entrano nel repo di un cliente (`code_repos/` o un clone che ne fa le veci): valgono le
regole di CLAUDE.md §ai_policy. **Prima di dichiarare lo spec pulito (verifica Fase 3), alla Fase 4
punti 2-3 e prima di ogni commit, leggere**
[`.claude/skills/references/cypress-generation-protocol/controllo-ai-policy-e-commit.md`](references/cypress-generation-protocol/controllo-ai-policy-e-commit.md):
contiene le categorie vietate con le regex, il comando di scansione e le regole di commit.
Esito richiesto: **0 corrispondenze** sui file aggiunti o modificati e sul messaggio di commit; se il
repo non è leggibile, STOP, non si committa. Regole che restano qui: un riscontro si corregge
riscrivendo il commento come spiegazione del *perché*, mai «mascherando» il testo; nessun
`Co-Authored-By`; nessun `--no-verify`; nessuna operazione VCS distruttiva senza gate umano;
nel repo di test si committa con `tools/vcs/sm-commit.sh "messaggio" <test_path>`, mai con
`git commit` diretto; per un override su clone personale il commit lo fa l'operatore e il controllo
va dichiarato nel `generation-plan.md`.

## Comando di ingresso e campi del TSK

Si entra con `/cypress-gen <TSK-id>` (`.claude/commands/cypress-gen.md`). Il comando accetta solo TSK
`layer: qa`, si ferma con messaggio esplicito senza TSK, con un TSK di altro layer o con
`cypress_pipeline.enabled: false`, e prevede due gate umani: dopo l'analisi (Fase 1) e dopo la
verifica (Fase 3). Un esito `issues-found` della verifica ferma l'avanzamento: la Fase 4 non parte e
il TSK resta `in-progress`. Nessun campo di frontmatter nuovo: il comando legge i campi che ogni TSK
ha già e il corpo (repo di test nella sezione «Cosa» del TSK, come `name` del registro o `test_path`;
se non univoco, STOP e domanda al PM). **Leggere**
[`.claude/skills/references/cypress-generation-protocol/ingresso-tsk-e-tracciabilita.md`](references/cypress-generation-protocol/ingresso-tsk-e-tracciabilita.md)
in Fase 0 se i campi del TSK non bastano a risolvere repo, branch o fonte dei casi.

## Preflight multiutente

Chi scrive nel repo di test o in `code_quality/cypress/` fa il preflight con
`tools/session/active_sessions.py`: `gc`; `conflicts --domain <dominio>`; `claim --agent <agente>
--domain <dominio> --uuid <id> --ttl 30`; a fine lavoro `release`. Domini, per convenzione dei
claim esistenti (percorsi): `code_quality/cypress/<TSK-id>` e il `test_path` del repo. Un claim
altrui attivo sullo stesso percorso è un WARN da riportare in chat, non da scavalcare.

## Gap dell'applicazione e wiki

Selettori mancanti, utenze mancanti, bug noti dell'applicazione e strumenti mancanti emersi dalla
pipeline si raccolgono in `code_quality/cypress/<TSK-id>/gaps.json`. La pipeline **non scrive in
`wiki/`**: nel report di chiusura elenca ogni gap con la citazione e propone il testo al wiki-keeper,
che lo registra in `wiki/gaps.md` (append-only). Stesso vale per le convenzioni dei repo di test e
per i gotcha (es. comportamento dei componenti): pagina wiki solo via wiki-keeper.

## Da confermare per ogni installazione

- Strumento di lettura in sola lettura della test list xlsx, se serve (nel master non c'è).
- Nome accettato da `sm-commit.sh` per il repo di test, se è un submodule (modalità `--coordinated --target`).
