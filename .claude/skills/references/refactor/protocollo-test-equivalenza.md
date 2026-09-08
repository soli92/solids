# Protocollo di test di equivalenza (Fase 4)

Ambito: come dimostrare che l'unità (o la flotta) rifattorizzata è
comportamentalmente equivalente (o migliore) all'originale, riusando
l'infrastruttura di skill-creator. Prerequisiti: Fase 3 in PASS; snapshot
dell'originale in `<workspace>/skill-snapshot/` creato in Fase 0.

## 0. Scopo mirato

Il test si limita alle **unità toccate** e ai flussi che le attraversano. In una
flotta di 80 agenti non si ri-testa l'intero sistema: si testano gli agenti
effettivamente splittati o modificati, più — se l'igiene di flotta ha toccato
routing/membership/registrazione — i flussi di routing che li coinvolgono. Il
resto della flotta è garantito invariato dai gate di grafo di Fase 3 (G9–G11):
se il grafo non è cambiato, il comportamento di routing non è cambiato.

## 1. Localizzare skill-creator

Percorsi tipici, in ordine di probabilità:

```bash
for radice in /mnt/skills/examples /mnt/skills/public ~/.claude/skills \
              ~/.claude/plugins; do
  find "$radice" -maxdepth 3 -type d -name skill-creator 2>/dev/null
done
```

Da skill-creator si riusano: `skill-creator/agents/grader.md` (grading),
`skill-creator/scripts/aggregate_benchmark.py` (aggregazione in `benchmark.json`
e `benchmark.md`), `skill-creator/references/schemas.md` (schemi esatti dei
JSON), `skill-creator/scripts/quick_validate.py` (già usato in Fase 3) e
`skill-creator/scripts/package_skill.py` (Fase 5). Convenzione: i path interni
all'unità si citano dalla radice (`references/`, `scripts/`, `assets/`); i file
di altre skill sempre qualificati con il nome della skill proprietaria, così i
gate G4/G5 non li scambiano per interni.

**Degradazione controllata**: se skill-creator non è localizzabile, il test si
esegue comunque in forma manuale — stessi prompt su baseline e rifattorizzata,
griglia di asserzioni compilata a mano con campi `text`, `passed`, `evidence`,
confronto presentato all'utente. Ciò che NON è degradabile sono i criteri di
accettazione della sezione 6: valgono identici.

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

Pattern di skill-creator, un'iterazione per ciclo:

```
<nome>-workspace/
├── skill-snapshot/              # baseline: l'originale pre-refactor (intera flotta se serve)
└── iteration-1/
    └── <nome-eval>/
        ├── eval_metadata.json   # eval_id, eval_name, prompt, assertions
        ├── old_skill/outputs/   # esecuzione con lo snapshot
        └── with_skill/outputs/  # esecuzione con la rifattorizzata
```

## 4. Esecuzione

Per ogni prompt, due esecuzioni con gli stessi input: una con lo snapshot
(baseline `old_skill`), una con la rifattorizzata (`with_skill`).

- **Con subagent** (Claude Code, Cowork): lancia tutte le coppie nello stesso
  turno, in parallelo; salva gli output nelle rispettive directory; cattura
  `total_tokens` e `duration_ms` dalle notifiche di completamento in un
  `timing.json` per run — arrivano una sola volta, salvale subito.
- **Senza subagent** (Claude.ai): esegui in serie, un caso alla volta, leggendo
  l'unità in prova e seguendone le istruzioni. Meno rigoroso: compensa con la
  revisione umana degli output.
- Conserva i transcript, non solo gli output finali: servono per le asserzioni di
  aderenza ai trigger e di routing.

## 5. Grading: tre famiglie di asserzioni

Il grading segue `skill-creator/agents/grader.md`; risultati in `grading.json`
per run, campi esatti `text`, `passed`, `evidence` (il viewer e l'aggregatore
dipendono da questi nomi).

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
4. **Fase 3 in PASS** sulla versione finale testata (se hai corretto file dopo
   l'ultima esecuzione dei gate, rilanciali).

Aggrega con `python -m scripts.aggregate_benchmark <workspace>/iteration-N
--skill-name <nome>` dalla directory di skill-creator e riporta anche il delta
token: il refactor deve ridurre i token del caricamento base (corpo dell'unità);
se i token totali per task crescono molto oltre il risparmio al caricamento, le
foglie vengono lette troppo spesso — rivedi il criterio di taglio.

## 7. Esito

- **Accettato**: procedi alla Fase 5. Lo snapshot resta finché l'utente non
  conferma l'adozione.
- **Non accettato**: analizza i fallimenti (per i trigger ignorati la cura è
  quasi sempre riportare l'enunciato nel corpo o spostare il trigger al punto
  d'uso, non aggiungere enfasi; per il routing rotto, ripristinare il nome/arco
  che il refactor ha alterato), applica le correzioni, rilancia in
  `iteration-N+1`. Se dopo iterazioni ragionevoli l'equivalenza non è raggiunta,
  rollback: ripristina lo snapshot e riferisci all'utente cosa non ha retto e
  perché.
