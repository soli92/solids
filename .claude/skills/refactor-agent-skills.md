---
name: refactor-agent-skills
description: Rifattorizza in divulgazione progressiva le unità di contesto agentiche troppo grandi — SKILL.md di skill, file di agenti e sotto-agenti, indice di flotta (AGENTS.md o equivalente) — tenendo snella la spina dorsale (frontmatter, vincoli, fasi, gate) e migrando il dettaglio in references/ con trigger di lettura vincolanti. Su una unità o un'intera flotta: quando splitta il markdown censisce e preserva il grafo dei riferimenti tra file (nomi-agente, handoff, path, ancore, skill) e applica igiene di flotta (registrati vs specialisti, collisioni di description, agenti orfani, deduplica). Usare quando una SKILL.md o un agente supera ~500 righe, o l'utente segnala agenti o skill troppo lunghi, allucinazioni, perdita di aderenza, token, riferimenti rotti, o chiede di spezzare, snellire od ottimizzare una skill, un agente, un AGENTS.md o una flotta. Rileva la topologia senza assumere cartelle fisse. NON per README/doc (usare refactoring-docs) né per creare skill/agenti da zero (usare skill-creator).
---

# Refactoring di skill e flotte di agenti sovradimensionate

## Principio

Un'**unità di contesto** è un file markdown il cui frontmatter `description`/`name`
è un *trigger* e il cui corpo è **contesto garantito**: entra in finestra ogni
volta che l'unità si attiva (o viene dispatchata). Tutto ciò che sta in
`references/` è **contesto opzionale**: viene letto solo se l'agente decide di
leggerlo. Rifattorizzare significa spostare contenuto dal garantito
all'opzionale — e ogni spostamento sbagliato degrada la modalità operativa in
modo silenzioso: l'agente crede di seguire le istruzioni mentre ne ignora pezzi.

La stessa disciplina vale per tre **specie** della stessa struttura:

| Specie | Trigger (frontmatter) | Corpo garantito | Come fallisce se mal fogliata |
|---|---|---|---|
| **Skill** (`SKILL.md`) | `description` | istruzioni operative | agente non conforme |
| **Agente / sotto-agente** | `description` | prompt di sistema dell'agente | agente non conforme *o* mis-routing |
| **Indice di flotta** (`AGENTS.md`/registro) | — (non triggerato) | mappa di team, membership, handoff | sistema multi-agente mal instradato, handoff rotti |

Questa tassonomia descrive **ruoli, non layout su disco**. Rileva la specie dal
frontmatter e dal ruolo, non dalla cartella: non tutti i progetti hanno
`agents/` + `specialists/`, non tutti hanno un `AGENTS.md`, non tutti gli agenti
si dispatchano allo stesso modo. La struttura d'esempio non è la norma: si
**scopre** (Fase 0), non si assume.

La differenza rispetto al refactoring di documentazione: un documento mal
fogliato produce una risposta peggiore; una skill o un agente mal fogliati
producono un'unità non conforme; una **flotta** mal fogliata rompe anche i
legami tra unità (handoff, membership, dispatch). Da qui i vincoli fail-closed,
il gate sul grafo dei riferimenti e il test di equivalenza obbligatorio prima
della sostituzione.

## Soglie di intervento (per unità)

| Righe corpo | Verdetto |
|---|---|
| oltre 500 | refactor raccomandato |
| 300–500 con contenuto misto | valutare: procedure operative mescolate a dettaglio consultivo |
| fino a 300 | non intervenire: riferisci il verdetto e fermati, salvo richiesta esplicita |

Su una flotta la soglia si applica **file per file**: rifattorizza le unità
sopra soglia, lascia stare le altre. Obiettivo post-refactor: corpo entro 250
righe; foglie da 50 a 250 righe ciascuna.

## Vincoli non negoziabili

- **V-1 Spina dorsale inamovibile.** Per ogni unità restano nel corpo:
  frontmatter, scopo e principio, vincoli e policy, sequenza delle fasi con
  condizioni di arresto, gate fail-closed, enunciati dei vocabolari chiusi,
  trigger di lettura. Se un contenuto governa *come* l'unità opera, non migra.
- **V-2 Trigger vincolanti al punto d'uso.** Ogni foglia riceve il trigger nel
  punto esatto del flusso in cui serve: condizione esplicita, lettura
  obbligatoria, arresto se il file manca. Una lista di risorse in coda al file
  non è un trigger: è la via maestra perché la foglia venga ignorata.
- **V-3 Triggering e dispatch invariati.** Il frontmatter di ogni unità toccata
  (`name`, `description`, `tools`, `model`, `maxTurns`, tutto) non cambia
  durante un refactor conservativo: `description` è il meccanismo di attivazione
  e di routing, `name` è il contratto con cui gli altri file la citano.
  Ottimizzarli è un passo separato, dopo, con il loop di skill-creator.
- **V-4 Una sola radice per unità.** Una skill ha una sola `SKILL.md`; un agente
  un solo file di definizione. Le foglie vivono in `references/`, mai come
  radici annidate.
- **V-5 Equivalenza prima della sostituzione.** L'originale non viene sostituito
  finché Fase 3 e Fase 4 non risultano PASS. In difetto: iterare o rollback.
- **V-6 Snapshot prima di toccare.** Copia integrale dell'originale — dell'intera
  flotta se si tocca la flotta — prima di qualunque modifica. È la baseline dei
  test e la via di rollback.
- **V-7 Nessuna duplicazione.** Ogni contenuto vive in un solo posto. Se una
  regola vincolante migra in una foglia, nel corpo resta il suo enunciato
  (massimo 2 righe) più il trigger — mai la copia: due copie divergono.
- **V-8 Integrità del grafo.** Ogni riferimento tra file — nome-agente, handoff
  `A -> B`, membership di team, path, ancora, nome di skill — deve risolvere
  dopo il refactor. Nessun agente orfano o irraggiungibile introdotto. È il
  vincolo che il taglio del markdown non deve mai rompere i legami tra file.
- **V-9 Sicurezza di dispatch.** Una foglia esterna è ammessa solo se l'unità
  che la richiama può davvero leggerla a runtime. Se un agente viene dispatchato
  iniettando il suo corpo in un prompt di Task, il subagent riceve **solo il
  corpo**: il contenuto vincolante resta nel corpo o viaggia nel prompt — mai in
  una foglia che il subagent non leggerà. Violare V-9 è il modo più insidioso di
  degradare la modalità operativa.

## Fase 0.0 — Detection topologia (se mode external, ADR-EP060-003)

Questa fase è **saltata in self mode** (default). Attiva solo se il chiamante
passa `mode: external`.

1. **Precondizioni**:
   - `mode: external` nel payload chiamante
   - `external_path` valorizzato (path assoluto)
   - `adapter` valorizzato (default `claude`)

2. **Guard EP-060 in factory target** (Decisione 4 ADR-EP060-003):
   Se `<external_path>/<adapter-dir>/skills/references/refactor/` non esiste:
   STOP con messaggio strutturato:
   ```
   Factory <external_path> non ha EP-060 installato.
   Azione richiesta:
     /factory-upgrade <external_path> --to=v2-41 --apply
   Poi ri-invoca /refactor --external.
   ```

3. **Classifica Pattern A/B/C in factory target**:
   Usa `INJECTION_HINT_RE` + heuristics (come Fase 0.4 self mode, ma applicato
   a `<external_path>/<adapter-dir>/`).

4. **Rileva convenzioni directory esistenti**:
   La factory target potrebbe differire dalle convenzioni master
   (es. mancare `agents/references/`, avere `specialists/`). Documenta nel
   report.

5. **Snapshot path**:
   `<external_path>/.fleet-health/workspace/<target-slug>-<timestamp>/skill-snapshot/`
   (Decisione 3). NON in factory master (isolamento).

6. **Reporting differenziato** (Decisione 5):
   Payload output includerà `mode: external` + `external_factory` (slug basename) +
   `external_path` + `external_adapter`.

Terminata Fase 0.0, procedi con Fase 0 standard (Ricognizione).

## Fase 0 — Ricognizione e topologia (sola lettura)

1. **Snapshot** (V-6): crea `<nome>-workspace/` accanto al target e copia
   l'originale in `skill-snapshot/`. Se il target è in sola lettura, copia prima
   in area scrivibile e lavora lì. Su una flotta, copia l'intero albero.
2. **Rilevamento topologia e dispatch**: prima di classificare qualunque cosa,
   leggi obbligatoriamente `.claude/skills/references/refactor/topologia-e-dispatch.md`; se il file
   manca, fermati e segnala. Stabilisce di che **specie** è il target (unità
   singola o flotta), dove vivono i file, e con quale **meccanica di dispatch**
   gli agenti vengono invocati — da cui dipende V-9.
3. **Inventario**: esegui `tools/refactor/analizza_target.py <path>` (un file o una
   directory) — outline delle sezioni con conteggio righe, inventario risorse
   con stato citazioni, verdetto soglie per ciascuna unità.
4. **Censimento dei riferimenti**: esegui `tools/refactor/mappa_riferimenti.py <root>`.
   Prima di leggerne l'output, leggi obbligatoriamente
   `.claude/skills/references/refactor/integrita-riferimenti.md`; se il file manca, fermati e segnala.
   Senza la tassonomia delle forme di riferimento la mappa non è interpretabile.
5. **Censimento dei contenuti**: leggi obbligatoriamente
   `.claude/skills/references/refactor/criteri-di-taglio.md`; se manca, fermati e segnala. Classifica
   ogni sezione: spina dorsale, migrabile in foglia, candidata a script, asset.
6. **Precondizioni di test**: individua l'installazione di skill-creator e gli
   eventuali `evals/evals.json`. Registra l'esito: determina la Fase 4.
7. **Condizioni di arresto**: tutto sotto soglia → riferisci il verdetto e
   fermati. Snapshot non riuscito → fermati: senza baseline non c'è rollback.

## Fase 1 — Piano dichiarato (gate di approvazione)

Prima di toccare qualunque file, produci il piano e sottoponilo all'utente:

1. **Criterio di taglio dichiarato**, uno e motivato per ciascuna unità
   rifattorizzata: per fase del flusso, per variante/dominio, o per frequenza
   d'uso. Mai tagli guidati dalla sola dimensione.
2. **Mappa delle destinazioni**: una riga per sezione — destinazione
   (`resta` | `references/<foglia>` | `scripts/` | `assets/`), righe stimate,
   motivazione in una frase.
3. **Tabella dei trigger**: per ogni foglia, punto d'inserzione, condizione di
   lettura, azione fail-closed se manca. Per gli agenti, verifica esplicita di
   V-9: se il corpo è dispatchato per iniezione, la foglia è ammessa?
4. **Piano di flotta** (se il target è una flotta): leggi obbligatoriamente
   `.claude/skills/references/refactor/igiene-flotta.md`; se manca, fermati e segnala. Elenca le
   ottimizzazioni oggettive proposte (registrati vs specialisti, collisioni di
   description, agenti orfani, deduplica in skill condivise), ciascuna come
   *rileva → proponi → applica se approvato*.
5. **Mappa di migrazione dei riferimenti**: per ogni riferimento che cambia
   forma o destinazione, la coppia prima→dopo. È il piano di come V-8 resta
   soddisfatto.
6. **Piano di test per la Fase 4**: prompt (riusa `evals/evals.json` se esiste;
   altrimenti proponi 3–5 prompt realistici, almeno uno per trigger vincolante e
   uno per ogni agente toccato) e le famiglie di asserzioni (funzionali, di
   aderenza ai trigger, e — su flotta — di routing/handoff).
7. **GATE**: procedi alla Fase 2 solo con approvazione esplicita.

## Fase 2 — Esecuzione

1. Crea le foglie in `references/`: 50–250 righe, autonome, con titolo e ambito
   in testa. Niente foglie-ripostiglio. Rispetta V-9 sugli agenti.
2. Riscrivi ogni corpo come spina dorsale: vincoli, fasi, gate, enunciati,
   trigger al punto d'uso (V-1, V-2, V-7).
3. Le procedure deterministiche descritte a parole diventano script in
   `scripts/`, richiamati dal flusso.
4. Applica le ottimizzazioni di flotta approvate in Fase 1.
5. Ricalcola **tutti** i riferimenti secondo la mappa di migrazione: path
   interni, ancore, nomi-agente, handoff, membership, nomi di skill (V-8).
6. Non toccare il frontmatter delle unità (V-3).

## Fase 3 — Verifica strutturale e integrità del grafo (fail-closed)

Esegui, in quest'ordine:

```bash
tools/refactor/verifica_flotta.py <path> --snapshot <workspace>/skill-snapshot
tools/refactor/mappa_riferimenti.py <root> --gate
```

Exit code diverso da 0 = STOP: correggi e rilancia finché non passa. Gate
strutturali per unità: G1 una sola radice; G2 frontmatter valido; G3 frontmatter
identico allo snapshot; G4 ogni path citato esiste; G5 nessuna foglia orfana;
G6 script citati ed eseguibili; G7 righe entro soglia; G8 ancore valide. Gate di
grafo sulla flotta: G9 ogni nome-agente/handoff citato risolve a un file
esistente; G10 nessun agente orfano o irraggiungibile; G11 nessuna foglia
irraggiungibile citata da un corpo dispatchato per iniezione (path non
`.claude/`-ancorato) — violazione di V-9. Se skill-creator
è disponibile, esegui in aggiunta `skill-creator/scripts/quick_validate.py` su
ogni skill/agente come gate di validità per l'upload.

## Fase 4 — Verifica comportamentale mirata (equivalenza)

Prima di iniziare leggi obbligatoriamente
`.claude/skills/references/refactor/protocollo-test-equivalenza.md`; se manca, fermati e segnala. In
sintesi: stessi prompt eseguiti sullo snapshot (baseline) e sulla versione
rifattorizzata, **limitatamente alle unità toccate** e ai flussi che le
attraversano; grading con `skill-creator/agents/grader.md`; accettazione solo
se il pass-rate funzionale è ≥ baseline, l'aderenza ai trigger è al 100% sui casi
applicabili, e — su flotta — le decisioni di routing e il grafo degli handoff
restano invariati. In difetto: itera (`iteration-N`) o rollback.

## Fase 5 — Consegna

1. Reimpacchetta con `package_skill.py` di skill-creator (o zip manuale se
   assente, escludendo workspace ed evals).
2. Riepilogo all'utente: righe prima/dopo per unità, stima dei token risparmiati
   al caricamento, esito dei gate di grafo, esito dei test di equivalenza,
   elenco di foglie/trigger creati e ottimizzazioni di flotta applicate.
3. Conserva lo snapshot finché l'utente non conferma l'adozione.

## Risorse

- `design_&_architecture/decisions/ADR-EP060-003-external-target-foundation.md` — 5 decisioni sblocco external_target. Lettura obbligatoria in Fase 0.0 se mode external.
- `tools/refactor/analizza_target.py` — inventario, outline, verdetto soglie per unità
  o flotta. Fase 0.3.
- `tools/refactor/mappa_riferimenti.py` — grafo dei riferimenti tra file, agenti orfani,
  collisioni di description, gate G9–G11. Fase 0.4 e Fase 3.
- `tools/refactor/verifica_flotta.py` — gate strutturali G1–G8. Fase 3.
- `.claude/skills/references/refactor/topologia-e-dispatch.md` — rilevamento di specie, topologia e
  meccanica di dispatch; la regola di sicurezza V-9. Lettura obbligatoria in
  Fase 0.2.
- `.claude/skills/references/refactor/integrita-riferimenti.md` — tassonomia delle forme di riferimento,
  come censirle e preservarle, i gate di grafo. Lettura obbligatoria in Fase 0.4.
- `.claude/skills/references/refactor/criteri-di-taglio.md` — tassonomia dei contenuti, criteri di taglio,
  anatomia dei trigger, anti-pattern. Lettura obbligatoria in Fase 0.5.
- `.claude/skills/references/refactor/igiene-flotta.md` — ottimizzazioni di flotta oggettive. Lettura
  obbligatoria in Fase 1.4 (solo se il target è una flotta).
- `.claude/skills/references/refactor/protocollo-test-equivalenza.md` — protocollo completo della Fase 4:
  riuso di skill-creator, asserzioni di aderenza e di routing, criteri di
  accettazione. Lettura obbligatoria in Fase 4.

## Owner

L'agente `fleet-doctor` (`.claude/agents/fleet-doctor.md`) è l'owner canonico
della governance G1–G11 di questa capability: mantiene la coerenza tra gli
script (`tools/refactor/*.py`), le foglie (`.claude/skills/references/refactor/`)
e la config (`refactor_agent_skills:` in `factory.config.yaml`). Modifiche
agli script o alle foglie richiedono un aggiornamento coordinato tramite il
suo protocollo (5 fasi).
