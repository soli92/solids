# Campo `assignee:` — advisory, mai vincolante sul dispatch (normativa)

Ambito: sezione normativa del campo `assignee:` di `scrivi-task.md`. Leggere prima di
introdurre il campo `assignee:` in un TSK. Contiene ciò che il campo **non fa** e perché.

---

> Chi introduce `assignee:` in una factory senza leggere questa sezione
> compra l'impressione di un presidio al posto del presidio.

## 1 — Perché non deve MAI diventare un filtro di dispatch

È il vincolo portante di US-253 (BR1): **se cade, il campo ha fatto danno invece di igiene.**
Rendere `assignee:` vincolante nella Fase 0 di `parallel-scheduling` produce quattro effetti,
tutti indesiderati e già congelati come decisione:

1. **Annulla R.S2.** R.S2 (§18.4) garantisce conflict-free **solo dentro il set `V` di una
   singola wave**, confrontando `intersect(code_path)` fra i candidati. Se il set viene
   pre-filtrato per attore, due TSK con `intersect(code_path) ≠ ∅` in mano a due attori
   diversi **non vengono più confrontati da nessuno**.
2. **Converte un conflitto *rilevato* in uno *non rilevato*.** Il conflitto non sparisce:
   sparisce il rilevatore. `code_path` conflict-detection è l'**unico** meccanismo di
   rilevazione conflitti su file che la factory possiede.
3. **Cappa `max_parallel` alla dotazione personale.**
4. **Apre un failure mode silenzioso di prima classe.** Identità assente ⇒ insieme candidati
   vuoto ⇒ «nulla da fare» con il board pieno.

**Forma esatta del dispatch oggi** (verificata): la Fase 0 di `parallel-scheduling` filtra
su `status: todo`, `consumer: agent`, presenza dell'agente di layer e dominio scheduler
abilitato — **nessun campo attore**, né nell'output né nel filtro. Aggiungere `assignee:` allo
schema del TSK **non** lo rende visibile al dispatch, **e così deve restare**.

Il vincolo è **falsificabile**: `tests/test_assignee_not_binding.py` fallisce se `assignee`
compare come criterio di selezione in `parallel-scheduling`, `dispatch-policy` o `/run`.

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/US-253.md §AC2 + §AC3 + §BR1]

## 2 — I due fallimenti silenziosi, per nome

Non sono un effetto collaterale scoperto dopo: sono il **prezzo dichiarato** del campo.

- **FM-NEW-1 — stale assignment.** L'attore è assente; i suoi task restano assegnati; il
  board appare «pieno» ma non avanza ⇒ **falsa fiducia**.
- **FM-NEW-4 — riallocazione non tracciata.** Scambio informale fra due attori,
  frontmatter non aggiornato, **divergenza silenziosa** fra il campo e la realtà.

US-253 aggiunge due presidi **parziali**:

| Fallimento | Presidio aggiunto | Cosa copre | Residuo **non** coperto |
|---|---|---|---|
| FM-NEW-1 | `tpm-reconcile` §3.4 `assegnazione-ferma` (TSK-588) | il **sintomo**: `assignee:` valorizzato e nessun avanzamento oltre la soglia | non distingue «attore assente» da «attore lento» |
| FM-NEW-4 | Check 4as (TSK-589), **WARNING-only** | la **forma osservabile**: campo valorizzato su stato in cui l'assegnazione non ha significato | lo **scambio fra due attori entrambi presenti** non lascia traccia — il caso centrale di FM-NEW-4 **resta silenzioso** |

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/US-253.md §AC4 + §AC5 + §AC6 + §BR5]

## 3 — La prelazione in questo modello: «il TPM edita il campo e committa»

Togliere un task a chi lo tiene fermo è un'operazione a **costo zero di codice**: il
TPM edita `assignee:` e committa. Proprietà, tutte verificate:
- **zero codice** e nessun nuovo attore scrivente;
- funziona **con il canale giù, offline, e su Windows con GPO restrittivi**;
- la riassegnazione è il **caso normale, non raro**: misurata al ~20% dei TSK/sprint.

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/US-253.md §AC7]

## 4 — Copertura reale: **0% del traffico di claim agentico**

Il campo copre il **lavoro umano pianificato**. Sul traffico agentico la copertura è **0%**:
la Fase 0 non ha un campo attore. Due sessioni della stessa persona hanno lo **stesso** valore
di `assignee:`, quindi il campo non le separa.

> **Presentare `assignee:` come una risposta alla contesa a runtime è un errore che questa
> sezione deve impedire.**

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-253-assignee-advisory/US-253.md §AC8 + §BR3]

## 5 — Stato della decisione a monte (cautela dichiarata)

In tre dei quattro esiti possibili dell'istruttoria — (i), (ii-a), (iii) — questa sezione resta
valida invariata. Nell'unico esito che cambierebbe la natura del campo — **(ii-b), assegnato
*vincolante* sul dispatch** — va riscritta, e va riaperto esplicitamente l'Accordo 32.
Quell'esito è **non raccomandato** dall'istruttoria.

[^src: design_&_architecture/proposta-modello-allocazione-kanban-ep064.md §6 + §7 scenario (iii)]

## 6 — Emendamento a `PATTERN.md` §5: **pendente, non applicato**

`PATTERN.md` §5 enumera i campi opzionali del TSK; `assignee:` **non è ancora elencato** lì.
Il campo resta pienamente valido — il contratto è silenzioso, non contrario — ma la sua
documentazione normativa vive **solo** in questa skill.

Testo pronto per l'emendamento, da appendere al bullet **Task:** di §5:

> **opzionale (v2.43, EP-064/US-253)**: `assignee` (identità umana; **advisory**: mai letto
> dal dispatch — §18 R.S2 resta l'unico meccanismo di conflict-detection su file; single-writer:
> TPM; campo assente = comportamento invariato, 0 ERROR di lint) — documentazione normativa
> in `.claude/skills/scrivi-task.md` §«Campo `assignee:` — advisory, mai vincolante sul dispatch»
