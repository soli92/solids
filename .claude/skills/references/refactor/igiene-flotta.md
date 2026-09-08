# Igiene di flotta

Ambito: questa foglia elenca le ottimizzazioni di **flotta** che vanno oltre lo
split del singolo file. Tutte sono **oggettive e conservative del comportamento**:
riducono costo e ambiguità senza cambiare cosa fa la flotta. Ognuna segue lo
schema *rileva → proponi → applica solo se approvato* (fanno parte del piano di
Fase 1.4, non si applicano di sorpresa).

Regola trasversale: nessuna di queste tocca il `name` o la `description` di
un'unità senza dichiararlo, perché sono trigger e contratti (V-3). Le collisioni
di description si **segnalano**; la loro riscrittura è ottimizzazione di
triggering, da fare col loop di skill-creator, non un refactor conservativo.

## 1. Registrati vs specialisti (costo di schema)

Gli agenti registrati (visibili nello schema dell'ambiente) costano token a ogni
turno anche quando non vengono usati; i non registrati costano zero a riposo e si
caricano on-demand. In una flotta grande la regola sana è: **registra solo gli
orchestratori / punti d'ingresso**, tieni gli esecutori come specialisti caricati
su richiesta.

- **Rileva**: dalla topologia (Fase 0), quali agenti sono registrati e quali no;
  quali agenti registrati non sono mai punti d'ingresso (nessuno li invoca
  dall'esterno, servono solo come esecutori).
- **Proponi**: spostare gli esecutori registrati tra i non registrati; stima il
  risparmio di token di schema.
- **Vincolo**: spostare un agente tra registrati e non registrati **cambia come
  viene invocato** (vedi meccanica di dispatch A/B in `topologia-e-dispatch.md`).
  Va quindi trattato come modifica di comportamento: aggiorna l'indice di flotta e
  ogni orchestratore che lo invoca, e coprilo con un caso di routing in Fase 4.

## 2. Collisioni di description (ambiguità di routing)

Con molti agenti, due `description` che si sovrappongono fanno sì che
l'orchestratore (o la piattaforma) instradi in modo non deterministico. Alcune
sovrapposizioni sono **volute** (es. due nomi alias per lo stesso team): vanno
riconosciute e lasciate stare.

- **Rileva**: `mappa_riferimenti.py` segnala coppie di description con forte
  sovrapposizione lessicale. Distingui volute da accidentali leggendo i due
  frontmatter.
- **Proponi**: per le accidentali, segnala la collisione all'utente come debito
  di triggering. **Non** riscrivere le description qui (V-3): annota il caso per
  il passo di description-optimization di skill-creator.

## 3. Agenti orfani e irraggiungibili

Un agente che nessuno cita nell'indice, in nessuna membership e in nessun
orchestratore è contesto morto: occupa spazio nel repo e confonde chi legge.

- **Rileva**: G10 / report della mappa (nessun arco entrante; irraggiungibile dai
  punti d'ingresso).
- **Proponi**: due esiti possibili, mai silenziosi — (a) **collegarlo** se
  l'orfano è un esecutore utile dimenticato (aggiungi membership/handoff
  nell'indice); (b) **segnalarlo per rimozione** se è morto. La rimozione la
  conferma l'utente: cancellare un agente è irreversibile e fuori dal mandato di
  un refactor conservativo.
- **Attenzione**: non introdurre **nuovi** orfani. Se accorpando due agenti ne
  scolleghi un terzo che li citava, è una regressione presa da G10.

## 4. Deduplica in skill condivise

Quando N agenti ripetono le stesse istruzioni (stesse regole di output, stesso
formato di finding, stessa checklist di sicurezza), quel blocco è **contesto
garantito duplicato** in N corpi: costa token N volte e diverge alla prima
modifica. La cura è estrarlo in una **skill condivisa** (o in una foglia comune)
che gli agenti citano.

- **Rileva**: blocchi di testo quasi-identici ripetuti in più corpi (il report
  della mappa evidenzia i candidati; conferma leggendo).
- **Proponi**: estrarre il blocco in una skill condivisa già esistente se c'è
  (l'esempio ne ha: `github-workflow-standards`, `python-development`), altrimenti
  in una nuova foglia comune; nei corpi resta l'enunciato + il trigger (regola
  dell'enunciato, V-7).
- **Vincolo di dispatch (V-9)**: se gli agenti che condividono il blocco sono
  dispatchati per iniezione del corpo, la skill condivisa deve essere leggibile
  dal subagent (ha `Read`, il path risolve) oppure il blocco resta nel corpo. Non
  creare una dipendenza che il subagent non può soddisfare.

## Come entra nel piano (Fase 1.4)

Per ciascuna ottimizzazione applicabile, una riga nel piano: *cosa ho rilevato →
cosa propongo → effetto atteso (token/ambiguità) → è conservativa del
comportamento? se no, quale caso di Fase 4 la copre*. L'utente approva voce per
voce: alcune (deduplica, ricollegare un orfano) sono a basso rischio; altre
(rimozioni, spostamenti registrati↔specialisti) cambiano invocazione o sono
irreversibili e vanno confermate esplicitamente.
