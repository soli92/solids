# Rilevamento di topologia e meccanica di dispatch

Ambito: questa foglia insegna a **scoprire** con cosa si ha a che fare prima di
rifattorizzare, senza assumere la struttura di cartelle di un esempio
particolare. Da qui dipende la regola V-9 (sicurezza di dispatch), il vincolo
più insidioso quando si tocca un agente.

## Perché non si assume la struttura

La struttura `.claude/agents/` + `.claude/specialists/` + `AGENTS.md` è **una**
configurazione, non la norma. In natura si trovano anche:

- una sola skill isolata, senza flotta né agenti;
- agenti tutti in un'unica cartella (`agents/`), senza distinzione registrati /
  non registrati;
- agenti sparsi (`.claude/agents/`, `~/.claude/agents/`, plugin, `.cursor/`);
- flotte senza `AGENTS.md`: la mappa dei team vive in un README, in un CLAUDE.md,
  o è solo implicita nelle `description`;
- meccaniche di dispatch diverse (vedi sotto).

Regola: **rileva la specie dal frontmatter e dal ruolo, non dal percorso.**
Il percorso è un indizio, non una prova.

## Passo 1 — Specie del target

Per ogni file `.md` in scope, leggi il frontmatter e decidi:

| Indizio | Specie probabile |
|---|---|
| `name: SKILL.md` alla radice di una cartella con `references/`/`scripts/` | **skill** |
| frontmatter con `description` + `tools`/`model`/`maxTurns` | **agente / sotto-agente** |
| nessun frontmatter, contenuto = elenco di team/membri/handoff/regole | **indice di flotta** |
| `description` che dice "internal helper", "invoked by ... via Task", "not user-invokable" | **sotto-agente nascosto** |

Se in scope c'è **più di un'unità** (più agenti, o agenti + indice), il target è
una **flotta**: si applicano anche i gate di grafo G9–G11 e l'eventuale igiene di
flotta.

## Passo 2 — Dove vivono i file

Non dare per scontato `specialists/`. Mappa i percorsi reali:

- quali cartelle contengono definizioni di agenti;
- se esiste una separazione registrati (visibili nello schema dell'ambiente,
  costano token a ogni turno) vs non registrati (caricati on-demand, costo zero
  a riposo). La separazione può essere per cartella, per convenzione di nome, o
  per una lista dentro l'indice di flotta;
- dove vivono le eventuali skill condivise citate dagli agenti.

Registra la mappa: serve alla mappa di migrazione dei riferimenti (Fase 1.5) e ai
gate di grafo.

## Passo 3 — Meccanica di dispatch (determina V-9)

Come viene **realmente invocato** un sotto-agente? Cercalo nell'indice di flotta
e nei corpi degli orchestratori. Tre pattern ricorrenti:

### A. Sottoagente registrato via `Task(subagent_type=...)`

L'orchestratore invoca l'agente per nome; la piattaforma carica la definizione
completa (frontmatter + corpo) e, con essa, l'agente può leggere le proprie
foglie se ha lo strumento `Read` e i path risolvono dalla sua working directory.
→ Le foglie esterne sono **ammesse**, purché il trigger sia vincolante (V-2) e i
path risolvano per il subagent, non solo per l'orchestratore.

### B. Dispatch per **iniezione del corpo**

Pattern visto nell'esempio: l'orchestratore fa `Read(".../<agente>.md")`, estrae
il **corpo** (tutto ciò che segue il frontmatter di chiusura) e lo passa come
`Task(prompt="<corpo>\n\n<compito>")`. Il subagent riceve **solo il corpo**: non
vede il frontmatter, non "è" quell'agente, e **non seguirà** una foglia esterna a
meno che il corpo non contenga un trigger vincolante *e* il subagent abbia `Read`
*e* il path risolva dalla sua working directory.
→ Le foglie esterne sono **pericolose**. Preferisci tenere nel corpo il contenuto
vincolante; se una foglia è indispensabile, il contenuto deve viaggiare nel
prompt di Task (è l'orchestratore a fare la divulgazione progressiva, non il
subagent). Questo è il cuore di **V-9**.

### C. Nessun dispatch (unità autonoma)

Skill o agente invocati direttamente dall'utente/piattaforma. Le foglie esterne
si comportano come in una skill normale: ammesse con trigger vincolante.

## La regola V-9 in pratica

Prima di spostare contenuto di un **agente** in una foglia esterna, rispondi:

1. Con quale meccanica viene dispatchato questo agente? (A, B o C)
2. Se **B (iniezione del corpo)**: il contenuto che sto spostando è vincolante
   (governa *come* opera)? Se sì → **resta nel corpo** o viaggia nel prompt di
   Task; non in una foglia. Se è dettaglio davvero opzionale e il subagent ha
   `Read` con path risolvibile → foglia ammessa con trigger esplicito.
3. Se **A o C**: foglia ammessa con trigger vincolante (V-2) e path verificato
   per chi la legge.

Il gate G11 di Fase 3 lo verifica meccanicamente: per un agente che l'indice
descrive come dispatchato per iniezione, ogni foglia esistente citata dal corpo
deve avere un path **`.claude/`-ancorato** (raggiungibile dalla working directory
del subagent, che è la radice). Una foglia citata solo con path agent-relative è
irraggiungibile e G11 fallisce — indipendentemente dalla cartella in cui vive
(`references/`, `assets/`, o un sottodirectory dello specialista). La via sicura:
citare la foglia con il suo path `.claude/…` completo, oppure far iniettare il
contenuto dall'orchestratore.

## Cosa registrare a fine Fase 0

Un breve **profilo di topologia**, che alimenta il piano di Fase 1:

- specie del target (unità singola | flotta);
- inventario cartelle e separazione registrati/non registrati (se presente);
- per ciascun agente sopra soglia: la sua meccanica di dispatch (A/B/C);
- esistenza e forma dell'indice di flotta (AGENTS.md, README, implicito).
