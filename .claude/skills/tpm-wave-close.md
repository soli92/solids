---
name: tpm-wave-close
description: 4 check di chiusura wave eseguiti dal tpm prima del report e del push — gate DoD, reconcile git↔status, gap CRITICAL senza bridge, commit atomico del kanban. Propone, non applica — patch e apertura TSK passano da un gate umano. Complementare a tpm-reconcile (riconciliazione periodica, sola lettura).
---
# tpm-wave-close — chiusura wave (4 check)

Invocata dal tpm al termine di ogni wave, prima di emettere il report di chiusura e prima del
push. Eseguire i 4 check nell'ordine (a) → (b) → (c) → (d).

Non confondere con `tpm-reconcile`: quella e' la **riconciliazione periodica** in sola lettura
(dipendenze insoddisfatte, drift temporale, blocco silenzioso, assegnazione ferma); questa e' la
**chiusura di una wave** e prepara il commit del kanban.

Origine: factory derivata portale-servizi-factory (Tavola Rotonda del 2026-08-03 e incidente del
2026-07-30: lavoro committato con il kanban fermo a `todo`, 30 file riconciliati a mano). Nel
master dal 2026-10-08 (EP-073 TSK-792).

---

## Check (a) — Gate DoD

**Obiettivo**: trovare TSK con `status: done` nel frontmatter e checkbox DoD `[ ]` ancora aperti
nel corpo.

### Passi

1. TSK in scope della wave: quelli del piano di wave piu' quelli toccati:
   ```bash
   git status --porcelain management/kanban/ | grep "TSK-.*\.md"
   ```
2. Per ogni TSK con `status: done`, cercare checkbox aperti nel corpo:
   ```bash
   grep -n "^\- \[ \]" management/kanban/<EP>/<US>/<TSK>.md
   ```
3. Esito: **PASS** se nessun `[ ]` (o nessun blocco di checkbox); **FAIL** altrimenti.
4. Lista di blocco:
   ```
   BLOCCO DoD — TSK non promuovibili:
   - TSK-XXX: checkbox aperto alla riga N (campo: "<testo checkbox>")
   ```
5. **Non promuovere** a `done` i TSK nella lista: il gate si sblocca quando chi ne risponde spunta
   i checkbox e aggiorna il file.

### Semantica: «enforce, non abolire»

`status:` e' l'indicatore autorevole per il DAG; i checkbox DoD sono tracking visivo e audit.
`status: done` con checkbox aperti e' un'incoerenza da bloccare, non da silenziare. Con il
protocollo di chiusura (`dev-handoff`) lo stato si deriva dalla tabella AC: questo check ne e' la
verifica a valle, a fine wave.

---

## Check (b) — Reconcile git↔status

**Obiettivo**: trovare TSK toccati nella history recente con `status: todo` o `in_progress`
(lavoro committato, kanban non aggiornato).

### Passi

1. File TSK nella history degli ultimi 7 giorni:
   ```bash
   git log --since="7 days ago" --name-only --pretty=format: \
     | grep "management/kanban/.*TSK-.*\.md" | sort -u
   ```
2. Per ognuno, `status:` dal frontmatter; tenere `todo` e `in_progress` (forma `in-progress`
   equivalente, PATTERN §5).
3. Proporre la patch, senza applicarla:
   ```
   PATCH BATCH proposta — reconcile git↔status:
   - TSK-XXX: status "todo" → proposta "done"
     (commit del lavoro: <hash-short> del YYYY-MM-DD, autore <nome>)
   Applicare? Il tpm valuta e conferma (gate umano light).
   ```
   Le date e l'autore vengono dal **commit del lavoro**, non dal giorno della riconciliazione:
   una riconciliazione in blocco sposterebbe tutte le chiusure sullo stesso giorno. Se la factory
   ha convenzioni sui campi di chiusura (date, autore, commit di riferimento), si applicano qui:
   vedi le sue convenzioni (`management/conventions.md`, se esiste).
4. **Non applicare la patch da solo**: solo dopo conferma esplicita si modificano i frontmatter.

### Note

- Il passo 1 legge solo `management/kanban/`: mai scritture nei `code_path`.
- Se `git log` fallisce (repo non configurato, path fuori scope) → segnalarlo e proseguire con gli
  altri check: questo non blocca la wave.

---

## Check (c) — Gap CRITICAL senza bridge

**Obiettivo**: trovare i gap `severity: CRITICAL` in `wiki/gaps.md` senza `bridge_tsk:` e
proporli alla sprint review.

### Passi

1. Leggere i gap aperti (`memory/gaps-open.md` se aggiornata, altrimenti `wiki/gaps.md`).
2. Tenere i `CRITICAL` con `bridge_tsk:` assente o vuoto.
3. Lista:
   ```
   GAP CRITICAL senza bridge_tsk (candidati sprint review):
   - GAP-NNN: "<titolo>" — area: <area>
   Proposta al Tech Lead: aprire TSK per i candidati prioritari? (gate umano)
   ```
4. **Non aprire TSK da solo**: il tpm propone, il Tech Lead approva un sottoinsieme, poi il tpm apre
   i TSK con `bridge_tsk: GAP-NNN` nel frontmatter.
5. Volume: oltre 5 candidati, mostrare i 5 piu' recenti e il totale.

### Semantica: «bridge con cadenza, non burst»

Il check garantisce che nessun CRITICAL resti invisibile; la cadenza con cui diventano TSK e' una
decisione del Tech Lead in sprint review.

---

## Check (d) — Commit atomico del kanban

**Obiettivo**: committare i file di `management/kanban/` modificati nella wave prima della
chiusura, cosi' il DAG del run successivo parte da uno stato coerente.

### Passi

1. File non committati:
   ```bash
   git status --porcelain management/kanban/
   ```
2. Nessun output → PASS.
3. Altrimenti:
   ```bash
   git add management/kanban/
   git status management/kanban/          # cosa entra nel commit
   git commit -m "chore(kanban): wave-close atomic commit — <EP-ID>"
   ```
   **Gate umano**: mostrare in chat i file inclusi e chiedere conferma prima del commit. Se la
   factory genera `sprint.md` (`tools/kanban/generate_sprint.py`), rigenerarlo prima.
4. Il commit precede il push, compreso il bump di un submodule: vedi `vcs-handoff`
   §Pre-push: verifica commit kanban.

### Motivazione

Il DAG del run successivo si ricostruisce dal filesystem (R.S6). Con i TSK a `todo` su disco e il
lavoro gia' committato, il DAG ripropone lavoro fatto o ignora dipendenze risolte.

---

## Output canonico

```
=== tpm-wave-close — chiusura wave <EP-ID> ===

(a) DoD gate:       [PASS|BLOCCO N TSK]
(b) git↔status:     [PASS|PATCH BATCH N TSK proposta]
(c) CRITICAL gap:   [PASS|N candidati da proporre a sprint review]
(d) Commit kanban:  [PASS|COMMIT ESEGUITO N file]

Wave pronta per push: [SI|NO — sbloccare (a) prima]
```

Con (a) in BLOCCO l'intera wave e' bloccata per il push.

---

## Anti-pattern

| Anti-pattern | Correzione |
|---|---|
| Applicare la patch (b) senza gate umano | Vietato: presentare la lista, attendere conferma |
| Aprire TSK per gap CRITICAL senza il Tech Lead | Vietato: gate umano obbligatorio |
| Saltare (d) per «velocizzare» il push | Vietato: il commit del kanban precede il push |
| Promuovere a `done` un TSK con DoD `[ ]` aperti | Vietato: (a) deve essere PASS |
| Aprire tutti i CRITICAL in burst (> 5 TSK in una wave) | Vietato: cadenza controllata |
