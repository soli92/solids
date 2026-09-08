---
name: tpm-reconcile
description: Riconciliazione periodica tra stato dichiarato nel kanban e stato reale dell'esecuzione. 5 passi — Bootstrap, Discovery, Riconciliazione, Report, Vincolo sola-lettura. Produce conteggio TSK per stato, lista anomalie (dipendenze insoddisfatte, drift temporale, blocco silenzioso) e raccomandazione per ciascuna. Non scrive in management/kanban/ — gli aggiornamenti sono demandati al TPM o all'orchestrator dopo conferma umana.
---
# tpm-reconcile — riconciliazione kanban canonico

Riferimenti:
- `PATTERN.md §18` (parallel scheduling e kanban state)
- `PATTERN.md §7 r.6` (gate STOP)
- `.claude/skills/vcs-handoff.md` (dipendenza opzionale per check VCS)

Invocata dal tpm-agent su richiesta esplicita dell'umano o al termine di ogni wave
come passo pre-report. Produce un report in-chat; **non modifica** `management/kanban/`.

---

## Passo 1 — Bootstrap

**Obiettivo**: inizializzare lo scope della riconciliazione.

1. Ricevere il parametro opzionale `ep_filter` (es. `EP-059`). Può essere passato
   come argomento della skill o come istruzione in-chat.
2. Se `ep_filter` è assente → scope globale: `management/kanban/EP-*/US-*/TSK-*.md`.
3. Se `ep_filter` è presente → scope ristretto: `management/kanban/<ep_filter>/US-*/TSK-*.md`.
4. Verificare che la directory di scope esista. Se assente o vuota → STOP, segnalare
   in chat.
5. Inizializzare i contatori: `todo=0`, `in_progress=0`, `done=0`, `blocked=0`,
   `anomalie=[]`.

---

## Passo 2 — Discovery

**Obiettivo**: costruire la lista completa dei TSK in scope.

1. Enumerare ricorsivamente tutti i file che rispettano il glob:
   ```bash
   find management/kanban/<scope> -name "TSK-*.md" -type f | sort
   ```
   dove `<scope>` è `EP-*/US-*` (globale) o `<ep_filter>/US-*` (filtrato).

2. Per ogni file trovato, leggere il frontmatter YAML e estrarre:
   - `id`
   - `status` (`todo` | `in-progress` | `done` | `blocked`)
   - `depends_on` (lista di ID prerequisiti; può essere `[]`)
   - `updated` (data ultima modifica dichiarata nel frontmatter, se presente)

3. Aggiornare i contatori in base al valore di `status` letto.

4. Se il frontmatter è malformato o il campo `status` è assente → classificare il TSK
   come anomalia di tipo `frontmatter-invalido` e proseguire (non bloccare la discovery).

---

## Passo 3 — Riconciliazione

**Obiettivo**: rilevare anomalie di coerenza per ogni TSK in scope.

Per ogni TSK con `status != done`, eseguire le verifiche seguenti nell'ordine.

### 3.1 — Dipendenze insoddisfatte

1. Per ogni ID in `depends_on`, cercare il file corrispondente nella directory scope
   (e, se non trovato, nella directory globale `management/kanban/`).
2. Leggere il `status` del predecessore.
3. Se il predecessore ha `status != done` → registrare anomalia:
   ```
   tipo: dipendenza-insoddisfatta
   tsk:  <ID>
   desc: dipende da <PRED-ID> (status: <status-predecessore>)
   rac:  Verificare se <PRED-ID> è bloccato o richiede escalate.
   ```
4. Se il file predecessore non esiste → registrare anomalia:
   ```
   tipo: dipendenza-mancante
   tsk:  <ID>
   desc: depends_on cita <PRED-ID> non trovato in kanban
   rac:  Verificare se <PRED-ID> è stato rinominato o rimosso.
   ```

### 3.2 — Drift temporale (predecessori done da >7 giorni)

1. Applicabile solo a TSK con `status: todo` che hanno **tutti** i predecessori in
   `status: done`.
2. Per ogni predecessore done, leggere il campo `updated` dal frontmatter.
3. Se `updated` è valorizzato e la data è antecedente a oggi di più di 7 giorni →
   registrare anomalia:
   ```
   tipo: drift-temporale
   tsk:  <ID>
   desc: status todo con tutti i predecessori done da <N> giorni (ultimo: <PRED-ID>, done il <DATA>)
   rac:  Verificare se il TSK è stato dimenticato o se ci sono impedimenti non dichiarati.
   ```
4. Se `updated` è assente nei predecessori → saltare il controllo di drift per quel TSK
   (dato insufficiente; non registrare anomalia).

### 3.3 — Blocco silenzioso (in-progress senza aggiornamenti)

1. Applicabile solo a TSK con `status: in-progress`.
2. Leggere il campo `updated` dal frontmatter del TSK.
3. Se `updated` è valorizzato e la data è antecedente a oggi di più di **3 giorni**
   (soglia configurabile inline, default 3) → registrare anomalia:
   ```
   tipo: blocco-silenzioso
   tsk:  <ID>
   desc: in-progress da <N> giorni senza aggiornamenti dichiarati (updated: <DATA>)
   rac:  Chiedere all'agente/persona responsabile un aggiornamento di stato o escalate.
   ```
4. Se `updated` è assente → registrare anomalia con descrizione `updated assente`:
   ```
   tipo: blocco-silenzioso
   tsk:  <ID>
   desc: in-progress — campo updated assente, impossibile stimare la durata
   rac:  Aggiungere updated al frontmatter e verificare il blocco.
   ```

---

## Passo 4 — Report output

**Obiettivo**: produrre il report in-chat in formato strutturato.

Il report è sempre emesso in-chat. Non viene scritto su file a meno che l'umano
non lo richieda esplicitamente (in quel caso l'umano decide il path).

### Formato canonico

```
=== tpm-reconcile — scope: <SCOPE> (ep_filter: <EP-ID|globale>) ===
Data: <YYYY-MM-DD>

--- Conteggio TSK per stato ---
todo:        <N>
in-progress: <N>
done:        <N>
blocked:     <N>
TOTALE:      <N>

--- Anomalie rilevate (<TOT> totale) ---

[<N>] dipendenza-insoddisfatta
  - <TSK-ID>: dipende da <PRED-ID> (status: <stato>)
    rac: <raccomandazione>

[<N>] dipendenza-mancante
  - <TSK-ID>: depends_on cita <PRED-ID> non trovato
    rac: <raccomandazione>

[<N>] drift-temporale
  - <TSK-ID>: todo con predecessori done da <N> giorni
    rac: <raccomandazione>

[<N>] blocco-silenzioso
  - <TSK-ID>: in-progress da <N> giorni (o updated assente)
    rac: <raccomandazione>

[<N>] frontmatter-invalido
  - <TSK-ID>: <descrizione problema>
    rac: correggere il frontmatter manualmente

--- Stato complessivo ---
Anomalie bloccanti (dipendenze insoddisfatte + mancanti): <N>
Anomalie di attenzione (drift + blocco + frontmatter):    <N>
Azione richiesta: [NESSUNA | REVISIONE UMANA RACCOMANDATA]
```

Se non ci sono anomalie di nessun tipo:

```
=== tpm-reconcile — scope: <SCOPE> ===
Kanban coerente. Nessuna anomalia rilevata.
```

### Soglie di escalate

- Se anomalie bloccanti > 0 → la riga finale riporta `REVISIONE UMANA RACCOMANDATA`.
- Se anomalie di attenzione > 5 → aggiungere nota: `Volume anomalie elevato — considerare
  una wave di manutenzione kanban`.

---

## Passo 5 — Vincolo sola-lettura

**La skill non scrive in `management/kanban/`.**

Tutte le operazioni dei passi 1-4 sono di sola lettura (Read + comandi bash read-only).
Nessun `Edit`, `Write` o `git add/commit` è eseguito dalla skill.

Gli aggiornamenti di stato (es. promuovere un TSK da `todo` a `in-progress`, correggere
un `updated`, risolvere una dipendenza mancante) sono **demandati al TPM o all'orchestrator**
dopo conferma esplicita dell'umano.

Flusso atteso post-report:

1. tpm-reconcile emette il report in-chat.
2. L'umano (o il TPM su istruzione umana) decide quali anomalie risolvere.
3. Il TPM esegue gli aggiornamenti necessari (Edit frontmatter, rimozione da `depends_on`,
   aggiornamento `updated`) con gate umano per ogni batch di modifiche.
4. Se opportuno, ri-eseguire tpm-reconcile per verificare che le anomalie siano risolte.

---

## Input

| Parametro | Tipo | Default | Descrizione |
|---|---|---|---|
| `ep_filter` | stringa opzionale | assente | Restringe lo scope a `management/kanban/<EP-ID>/`. Se assente → scope globale su tutto `management/kanban/`. |
| `blocco_soglia_giorni` | intero opzionale | 3 | Soglia in giorni per rilevare blocco silenzioso (passo 3.3). |

---

## Anti-pattern (vietati)

| Anti-pattern | Correzione |
|---|---|
| Scrivere o aggiornare file in `management/kanban/` | Vietato. La skill è read-only. Presentare il report, lasciare l'aggiornamento al TPM con gate umano. |
| Modificare il `status` di un TSK senza istruzione umana esplicita | Vietato. Ogni modifica al kanban richiede conferma. |
| Saltare i TSK con frontmatter malformato | Vietato. Classificarli come `frontmatter-invalido` e includerli nel report. |
| Emettere il report su file senza richiesta esplicita dell'umano | Vietato. Default in-chat. Il path del file è a scelta dell'umano. |
| Applicare `ep_filter` anche al check delle dipendenze dei predecessori | Errato. I predecessori vanno cercati anche fuori dallo scope filtrato (la dipendenza può attraversare epiche). |
| Interpretare `updated` assente come "aggiornato oggi" | Errato. `updated` assente è dato mancante — classificare come blocco-silenzioso con nota. |
