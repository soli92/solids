# Protocollo di test di equivalenza (Fase 4)

Ambito: come dimostrare che l'unità (o la flotta) rifattorizzata è
comportamentalmente equivalente (o migliore) all'originale. Prerequisiti: Fase 3
in PASS; `baseline_commit` registrato in Fase 0 (V-6), da cui la baseline si
materializza a zero byte (`git worktree add <dir> <baseline_commit>`).

## 0. Scopo mirato

Il test si limita alle **unità toccate** e ai flussi che le attraversano. In una
flotta di 80 agenti non si ri-testa l'intero sistema: si testano gli agenti
effettivamente splittati o modificati, più — se l'igiene di flotta ha toccato
routing/membership/registrazione — i flussi di routing che li coinvolgono. Il
resto della flotta è garantito invariato dai gate di grafo di Fase 3 (G9–G11):
se il grafo non è cambiato, il comportamento di routing non è cambiato.

## 1. Esecutori ammessi e terzo stato del verdetto

Un **esecutore** è valido solo se è **nominato**, **esistente nel repo** e ha un
**exit code**. Validi oggi: `tools/refactor/verifica_flotta.py` e
`tools/refactor/mappa_riferimenti.py --gate` (Fase 3). Per la **verifica
comportamentale** di questa fase **non esiste** un esecutore nel repo —
`ls tools/refactor/` è l'elenco completo: nessun grader, nessun aggregatore di
benchmark, nessun validatore di upload, nessun impacchettatore. Erano citati come
parti di una skill di creazione **mai installata**.

Da qui **tre** verdetti, non due:

| Verdetto | Quando |
|---|---|
| `accept` | tutti i criteri della sezione 6 soddisfatti, payload di evidenza incluso |
| `reject` | un criterio della sezione 6 violato |
| `non valutabile` | nessun esecutore valido, o payload assente, o verdetto emesso da chi ha eseguito il refactor (sezione 1-bis) |

`non valutabile` **non è degradabile**: non diventa `accept` per assenza di
alternative, non diventa `reject` per prudenza, e non si sostituisce con una
verifica «analitica», descrittiva o a mano. In assenza di esecutore valido la
Fase 4 **è** `non valutabile` e la Fase 5 non si esegue (sezione 6). Il divieto
puro, senza terzo stato, si aggira: è così che è nato il verdetto `accept`
dell'unico artefatto di Fase 4 esistente.

## 1-bis. Divieto di self-certification

Un artefatto di Fase 4 prodotto dalla **stessa unità agentica** che ha eseguito
il refactor **non è un'evidenza** e **non può produrre un verdetto**: l'esito è
`non valutabile`. Motivazione, nel repo:
`.fleet-health/reports/tavola-rotonda-protocol-fase4-20260904T130000.md` è
intestato «modalità: analitica» — motivata nel file stesso con l'indisponibilità
dell'esecutore di grading e l'assenza di runtime dispatch — e ha prodotto
`verdetto: accept`: **zero con una firma sopra, che è peggio**. Un exit code
narrato in prosa non è un exit code, è un'affermazione su un exit code.

Convenzione di citazione (perché i gate G4/G5 non confondano i path): i path
interni all'unità si citano dalla radice (`references/`, `scripts/`, `assets/`),
quelli di altre unità sempre qualificati dal nome dell'unità proprietaria.

## 2. Costruire il set di prova

- Se l'unità ha già `evals/evals.json`, riusalo: è la definizione storica di
  comportamento atteso. Puoi estenderlo, non sostituirlo.
- Altrimenti scrivi da 3 a 5 prompt realistici — concreti, con contesto, percorsi
  file, dati verosimili, non richieste astratte.
- Copertura minima obbligatoria:
  - **almeno un prompt per ciascun trigger vincolante** introdotto dal refactor,
    costruito in modo che il ramo di flusso della foglia sia davvero attraversato;
  - **almeno un prompt per ciascun agente toccato**, che eserciti il compito
    principale di quell'agente;
  - **su flotta**, se l'igiene ha cambiato routing/registrazione/membership,
    almeno un prompt che entri dall'orchestratore e debba **instradare** verso
    l'agente coinvolto: serve a verificare la Famiglia 3.
  Un trigger o un percorso di routing mai esercitato è un comportamento non
  verificato.
- Sottoponi i prompt all'utente prima di eseguire (fa parte del piano di Fase 1;
  se emergono nuovi prompt in Fase 4, nuovo passaggio di conferma).

## 3. Struttura del workspace

Un'iterazione per ciclo:

```
<nome>-workspace/
├── baseline/                    # materializzata da git da <baseline_commit> (V-6), non una copia a mano
└── iteration-1/
    └── <nome-eval>/
        ├── eval_metadata.json   # eval_id, eval_name, prompt, assertions
        ├── old_skill/outputs/   # esecuzione con la baseline
        └── with_skill/outputs/  # esecuzione con la rifattorizzata
```

## 4. Esecuzione

Per ogni prompt, due esecuzioni con gli stessi input: una con la baseline
(`old_skill`), una con la rifattorizzata (`with_skill`).

- **Con subagent** (Claude Code, Cowork): lancia tutte le coppie nello stesso
  turno, in parallelo; salva gli output nelle rispettive directory; cattura
  `total_tokens` e `duration_ms` dalle notifiche di completamento in un
  `timing.json` per run — arrivano una sola volta, salvale subito.
- **Senza subagent**: non c'è esecuzione. Leggere l'unità in prova e seguirne le
  istruzioni è autocertificazione (sezione 1-bis): il verdetto è `non
  valutabile`, non una prova «meno rigorosa».
- Conserva i transcript, non solo gli output finali: servono per le asserzioni di
  aderenza ai trigger e di routing.

## 5. Grading: tre famiglie di asserzioni

Il grading richiede un esecutore valido (sezione 1) **diverso** dall'unità che
ha eseguito il refactor; risultati in `grading.json` per run, campi esatti
`text`, `passed`, `evidence`. Senza quell'esecutore il verdetto è `non
valutabile`: una griglia compilata a mano da chi ha rifattorizzato non è un
grading.

**Famiglia 1 — Funzionali (equivalenza di esito).** Le asserzioni dell'eval
originale, o quelle nuove concordate: verificano che l'output sia corretto. Si
applicano identiche a baseline e rifattorizzata: è il confronto che dimostra
l'equivalenza.

**Famiglia 2 — Aderenza ai trigger (solo `with_skill`).** Una asserzione per
ogni trigger vincolante applicabile al prompt:

- il transcript mostra la **lettura della foglia prima** dell'azione che ne
  dipende (non dopo, non mai);
- se il prompt attraversa un gate fail-closed (es. foglia rimossa ad arte in un
  caso negativo), il transcript mostra l'**arresto**, non la prosecuzione a
  memoria;
- l'output non contiene contenuto che esisteva solo nella foglia se la foglia non
  risulta letta (sintomo di ricostruzione a memoria: è il meccanismo che genera
  allucinazioni ed è esattamente ciò che il refactor deve impedire).

**Famiglia 3 — Routing e handoff (solo su flotta, solo `with_skill`).** Quando il
prompt entra da un orchestratore:

- l'orchestratore instrada verso lo **stesso agente** che sceglieva la baseline
  (le decisioni di routing non sono cambiate);
- gli handoff dichiarati nell'indice vengono onorati (il transcript mostra la
  delega attesa, con il contratto di output strutturato al confine);
- se l'igiene ha spostato un agente registrati↔specialisti, il meccanismo di
  invocazione nuovo funziona (l'agente viene comunque raggiunto).

Quando possibile, verifica le asserzioni con script (grep sul transcript per
l'evento di lettura del file o per il nome dell'agente delegato) invece che a
occhio: più affidabile e riusabile tra iterazioni.

## 6. Criteri di accettazione (fail-closed)

Tutti, nessuna eccezione:

1. **Pass-rate funzionale**: `with_skill` ≥ `old_skill` su ogni eval. Una
   regressione anche singola = refactor non accettato.
2. **Aderenza ai trigger**: 100% sui casi applicabili. Un trigger ignorato = la
   modalità operativa è degradata = non accettato.
3. **Routing/handoff invariati** (su flotta): 100% sui casi applicabili. Un
   instradamento cambiato o un handoff rotto = non accettato.
4. **Fase 3 con exit code 0** sulla versione finale testata (se hai corretto file
   dopo l'ultima esecuzione dei gate, rilanciali).
5. **Payload di evidenza presente**, prodotto da un'unità diversa da chi ha
   eseguito il refactor (sezioni 1 e 1-bis). Sedi ammesse: `grading.json` per run
   sotto `<workspace>/iteration-N/` e i trailer del commit che applica il
   refactor. **Non** `wiki/log.md`, **non** un report in prosa.

I cinque criteri sono **precondizione hard della Fase 5**, non un output
auspicabile: se uno qualunque non è verificabile con un esecutore valido, il
verdetto è `non valutabile` e la Fase 5 non parte. Riporta il delta token: il
refactor deve ridurre i token del caricamento base (corpo dell'unità); se i
token totali per task crescono oltre il risparmio al caricamento, le foglie
vengono lette troppo spesso — rivedi il taglio alla luce di **V-10** (corpo
della skill, dove la precondizione di ramificazione è definita).

## 7. Esito

- **`accept`**: procedi alla Fase 5. La baseline resta raggiungibile in git
  (`baseline_commit`), quindi non c'è nulla da conservare fuori da git.
- **`non valutabile`**: **non** procedere alla Fase 5. Riferisci quale delle tre
  condizioni di esecutore (sezione 1) manca, o che il verdetto sarebbe
  un'autocertificazione. Nessuna consegna: il refactor resta non consegnato, che
  è l'esito corretto — non un `accept` con una riserva.
- **`reject`**: analizza i fallimenti (per i trigger ignorati la cura è
  quasi sempre riportare l'enunciato nel corpo o spostare il trigger al punto
  d'uso, non aggiungere enfasi; per il routing rotto, ripristinare il nome/arco
  che il refactor ha alterato), applica le correzioni, rilancia in
  `iteration-N+1`. Se dopo iterazioni ragionevoli l'equivalenza non è raggiunta,
  rollback da git (`git checkout <baseline_commit> -- <target>`) e riferisci cosa
  non ha retto e perché.
