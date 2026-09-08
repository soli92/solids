# Integrità del grafo dei riferimenti

Ambito: questa foglia definisce le **forme di riferimento** che legano i file di
una flotta, come censirle prima di splittare e come non romperle (vincolo V-8).
È la risposta operativa a "attenzione ai riferimenti tra file quando splitti".

## Perché è la parte più fragile

In una skill isolata i riferimenti sono pochi e locali (`references/…`,
`scripts/…`). In una flotta di agenti i file si citano a vicenda in **molte
forme diverse**, spesso in prosa e dentro il frontmatter. Spezzare o riorganizzare
un file può lasciare un riferimento che punta a un'ancora sparita, a un nome che
non esiste più, o a un path che si è spostato. Il sintomo a runtime è un handoff
che non parte o un orchestratore che non trova lo specialista: il grafo si è
rotto in silenzio.

## Le forme di riferimento

| Forma | Esempio | Dove vive | Si rompe se… |
|---|---|---|---|
| **Path interno** | `references/<foglia>.md`, `scripts/<tool>.py` | corpo, foglie | sposti/rinomini il file |
| **Path di dispatch** | `Read(".claude/specialists/<name>.md")` | orchestratori, indice | rinomini l'agente o sposti la cartella |
| **Nome-agente** | `` `web-accessibility-wizard` `` | prosa, indice, description | rinomini l'agente (V-3 lo vieta nel refactor) |
| **Handoff** | `issue-tracker -> pr-review` | indice, corpi | l'estremo non esiste più |
| **Membership di team** | elenco `Members:` sotto un Lead | indice | l'agente citato è orfano/sparito |
| **"invoked by X"** | dentro la `description` di un helper | frontmatter | il chiamante cambia nome/scompare |
| **Nome di skill** | `` `python-development` `` | corpi, indice | la skill condivisa non esiste |
| **Ancora** | `foo.md#sezione` | ovunque | rinomini/sposti l'intestazione |

Nota critica: il **nome-agente** e la **membership** vivono spesso solo in prosa
e nel frontmatter, dove nessun controllo di link classico li vede. Il censimento
deve leggerli come token, non solo come link markdown.

## Come censire (Fase 0.4)

`tools/refactor/mappa_riferimenti.py <root>` costruisce il grafo:

1. **Nodi**: ogni file `.md` con il suo `name` di frontmatter (o, in assenza, il
   basename). Costruisce l'indice nome→file.
2. **Archi**: per ogni file estrae le forme sopra. I nomi-agente si riconoscono
   incrociando i token in backtick e negli handoff con l'indice dei `name` noti
   (così "python" generico non diventa un falso arco).
3. **Report**: riferimenti non risolti, agenti orfani (nessun arco entrante da
   indice o orchestratore), agenti irraggiungibili dai punti d'ingresso,
   collisioni di `description` (vedi `igiene-flotta.md`), anomalie di frontmatter.

Leggi il report **prima** di progettare i tagli: un file molto citato va spezzato
con più cautela di uno foglia; un file già orfano è un problema da segnalare, non
da propagare.

## Come preservare (Fase 2.5)

La regola operativa è la **mappa di migrazione dei riferimenti** dichiarata in
Fase 1.5: per ogni riferimento che cambia, la coppia prima→dopo. Durante
l'esecuzione:

- **Se sposti contenuto tra file**: l'ancora citata altrove deve seguire il
  contenuto o essere reindirizzata. Non lasciare `#sezione` che punta al vecchio
  file se la sezione è migrata.
- **Se rinomini un'intestazione** verso cui esistono ancore: aggiorna tutte le
  ancore entranti (la mappa te le ha elencate).
- **Nomi-agente e handoff**: durante un refactor conservativo **non cambiano**
  (V-3 blocca il rename del `name`). Se il piano prevede comunque un rename, ogni
  occorrenza — prosa, indice, membership, `description` degli helper, path di
  dispatch — va aggiornata in blocco: è un'operazione di flotta, non locale.
- **Path di dispatch**: se la cartella degli agenti si riorganizza, aggiorna
  l'indice di flotta e ogni orchestratore che fa `Read(...)`.

## I gate di grafo (Fase 3, `--gate`)

Fail-closed, exit ≠ 0 se violati:

- **G9 Riferimenti risolti.** Ogni nome-agente, handoff, membership, path di
  dispatch e path interno citato risolve a un file esistente. Un handoff verso un
  nome ignoto = FAIL.
- **G10 Nessun orfano/irraggiungibile.** Ogni agente è raggiungibile da almeno un
  punto d'ingresso (indice di flotta o orchestratore registrato). Un agente che
  nessuno cita e nessuno dispatcha è contesto morto: se esisteva già prima, si
  segnala; se lo introduce il refactor, è un errore.
- **G11 Sicurezza di dispatch (V-9).** Per un agente dispatchato per iniezione,
  ogni foglia citata dal corpo (in qualunque cartella: `references/`, `assets/`,
  sottocartelle) deve essere **raggiungibile dal subagent iniettato**, la cui
  working directory è la radice: cioè citata con un path `.claude/`-ancorato. Una
  foglia esistente citata solo con path agent-relative (es. `references/<foglia>.md`
  o `specialists/<agente>/<foglia>.md`) e priva di forma `.claude/…` è irraggiungibile →
  G11 fallisce. Riferimenti ad altri agenti (non foglie) non contano. Vedi
  `topologia-e-dispatch.md`.

## Anti-pattern specifici dei riferimenti

- **Ancora orfana**: `#sezione` sopravvissuta al taglio ma il titolo è cambiato.
  G8 la prende dentro la stessa unità; tra file diversi la prende la mappa.
- **Rename strisciante**: cambiare `name` "per chiarezza" durante il refactor.
  Rompe ogni riferimento simbolico entrante e viola V-3. Se serve, è un passo a
  parte, dichiarato, con aggiornamento in blocco.
- **Foglia dispatch-cieca**: spostare istruzioni di un agente-B in una foglia
  esterna. Il subagent non la legge: violazione di V-9, presa da G11.
- **Membership fantasma**: lasciare nell'indice un membro di team il cui file è
  stato accorpato o rimosso. G9/G10 la prendono.
