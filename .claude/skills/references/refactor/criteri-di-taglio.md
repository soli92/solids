# Criteri di taglio per il refactoring di un'unità di contesto

Ambito: questa foglia definisce la tassonomia con cui classificare le sezioni del
corpo di un'unità — sia essa una `SKILL.md`, un file di agente, o un indice di
flotta (Fase 0.5) — e i criteri con cui progettare il taglio (Fase 1). Vale
identica per tutte le specie: cambia il tipo di corpo, non la disciplina.

## Tassonomia dei contenuti

Classifica ogni sezione in una delle quattro classi. In caso di dubbio tra A e B,
scegli A: il costo di qualche riga in più nel contesto garantito è sempre
inferiore al costo di una regola operativa ignorata.

### Classe A — Spina dorsale (resta nel corpo)

Tutto ciò che governa *come* l'unità opera:

- frontmatter (`name`, `description`, `tools`, `model`, `maxTurns`, ...);
- scopo e principio: il "perché" che orienta le decisioni;
- vincoli, policy, prescrizioni e divieti;
- la sequenza delle fasi con le condizioni di arresto e i gate;
- gli **enunciati** dei vocabolari chiusi (es. severità
  `critical | serious | moderate | minor`; verdetti `success | failure |
  skipped`): l'elenco dei valori ammessi resta nel corpo anche se la semantica
  dettagliata di ciascuno migra;
- per un **agente**: la sua identità operativa, i confini d'azione
  (read-only vs state-changing), il contratto di output strutturato all'handoff;
- per un **indice di flotta**: la mappa dei team, la membership, il grafo degli
  handoff, gli standard di affidabilità condivisi. Sono la spina dorsale della
  *flotta* e non migrano in foglia.
- i trigger di lettura verso le foglie.

Segnale di riconoscimento: se l'agente ignorasse questa sezione, produrrebbe un
output *non conforme* (non solo meno ricco) o instraderebbe male un handoff.

### Classe B — Dettaglio consultivo (migra in `references/`)

Contenuto che serve solo in certi rami del flusso o per certi input:

- guide per variante o dominio (un file per variante: `aws.md`, `word.md`);
- tabelle lunghe, schemi e formati completi, specifiche di output estese;
- **template di output** lunghi (il report completo, il VPAT, il boilerplate di
  audit): appaiono nell'output, non governano il flusso → foglia o asset;
- esempi estesi, casi limite, troubleshooting;
- razionali storici, background, confronti tra alternative.

Per gli agenti vale la cautela **V-9**: se l'agente è dispatchato per iniezione
del corpo, anche il dettaglio "opzionale" potrebbe non essere raggiungibile dal
subagent. Vedi `topologia-e-dispatch.md` prima di migrarlo.

Segnale di riconoscimento: se l'agente ignorasse questa sezione in un ramo che
non la riguarda, l'output non cambierebbe.

### Classe C — Procedura deterministica (diventa `scripts/`)

Il corpo descrive a parole un algoritmo passo-passo che l'agente riscriverebbe a
ogni invocazione: conteggi, validazioni, trasformazioni, census, scansioni.
Scrivilo una volta come script eseguibile e fai richiamare lo script dal flusso.
Uno script non consuma contesto per essere eseguito: è la forma più forte di
divulgazione progressiva.

### Classe D — Materiale d'output (diventa `assets/`)

Template, boilerplate, file che finiscono nell'output dell'unità e non nelle
istruzioni.

## Criteri di taglio dichiarabili

Il piano di Fase 1 dichiara **un** criterio dominante per unità e lo motiva. Mai
tagliare per sola dimensione: la dimensione indica *che* bisogna tagliare, il
criterio decide *dove* passano i confini.

| Criterio | Quando è il migliore | Foglie risultanti |
|---|---|---|
| Per fase del flusso | l'unità è un procedimento sequenziale con fasi ricche (tipico dei "wizard"/orchestratori) | una foglia per fase pesante, la sequenza resta nel corpo |
| Per variante o dominio | l'unità copre più tecnologie, formati o contesti alternativi | una foglia per variante; l'agente ne legge una sola |
| Per frequenza d'uso | poche sezioni servono sempre, molte di rado (es. template di report finale) | il "sempre" resta, il "di rado" migra con trigger condizionali |

I criteri si possono comporre (dominante + secondario), ma il dominante va
dichiarato e il piano deve essere leggibile alla sua luce.

## Anatomia del trigger vincolante

Un trigger vincolante ha tre parti, tutte obbligatorie, e sta **nel punto del
flusso in cui la foglia serve** — non in una lista a fine file:

1. **Condizione**: quando scatta ("prima di generare il report", "se il target
   è AWS").
2. **Obbligo di lettura**: "leggi obbligatoriamente `references/<foglia>.md`".
3. **Azione fail-closed**: "se il file manca, fermati e segnala" — mai proseguire
   ricostruendo il contenuto a memoria.

Esempio buono:

> Prima di compilare la tabella degli esiti, leggi obbligatoriamente
> `references/formato-esiti.md`; se il file manca, fermati e segnala. Gli esiti
> ammessi sono: Soddisfatto, Non soddisfatto, Non applicabile, Non testato.

Convenzione per gli esempi: i path illustrativi vivono in blockquote — i gate
G4/G8 di `tools/refactor/verifica_flotta.py` ignorano le righe in blockquote, mentre
G5/G6 (citazioni) leggono tutto il file.

Esempio cattivo (foglia destinata a essere ignorata):

> Risorse: `references/formato-esiti.md` — dettagli sul formato degli esiti.

Nota il pattern del buon esempio: l'enunciato del vocabolario chiuso resta nel
corpo (classe A), il dettaglio semantico sta nella foglia (classe B), il trigger
li collega. È la "regola dell'enunciato": per ogni regola vincolante migrata, nel
corpo restano enunciato (massimo 2 righe) e trigger.

## Anti-pattern

- **Gate in foglia**: spostare una condizione di arresto, un vocabolario chiuso o
  una policy in `references/`. Se l'agente non legge la foglia, il gate non
  esiste più. Violazione di V-1.
- **Duplicazione prudenziale**: tenere il contenuto sia nel corpo sia nella foglia
  "per sicurezza". Le due copie divergeranno alla prima modifica. Violazione di
  V-7. (Su una flotta, la cura per la duplicazione *tra* agenti è la deduplica in
  skill condivise — vedi `igiene-flotta.md`.)
- **Foglia-ripostiglio**: una foglia `varie.md` senza ambito dichiarato. Se non
  sai intitolarla, il criterio di taglio è sbagliato.
- **Trigger decorativo**: "vedi anche...", "per approfondire...". Senza condizione
  e senza obbligo, la lettura non avverrà sotto pressione di contesto.
- **Catene di foglie**: foglia che per essere capita obbliga a leggerne un'altra.
  Ogni foglia deve essere autonoma dato il corpo dell'unità.
- **Micro-foglie**: file sotto le ~50 righe. Il costo di orientamento supera il
  risparmio; accorpa nel corpo o in una foglia affine.
- **Foglia dispatch-cieca** (specifica degli agenti): migrare contenuto di un
  agente dispatchato per iniezione in una foglia esterna che il subagent non
  leggerà. Violazione di V-9, presa da G11.

## Casi particolari

- **Unità con una sola sezione enorme** (es. un unico elenco di 700 regole, o un
  agente con un solo blocco-workflow monolitico): il criterio è dentro la
  sezione, non tra le sezioni — cerca la partizione naturale (per dominio, per
  severità, per fase in cui si applica).
- **Unità già parzialmente fogliata**: rispetta la struttura esistente; verifica
  che le foglie abbiano trigger vincolanti e, se non li hanno, aggiungerli è parte
  del refactor.
- **Contenuto normativo esterno** (leggi, standard, WCAG): non incorporarlo mai
  per copia estesa; la foglia cita la fonte e il punto esatto, l'enunciato resta
  nel corpo se vincolante.
- **Template di report molto lungo dentro un orchestratore**: è quasi sempre
  classe B o D. Migralo in una foglia/asset con trigger "prima di comporre il
  report finale, leggi...", verificando V-9 se l'agente è dispatchato per
  iniezione.
