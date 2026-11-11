---
name: kanban-coordination-protocol
description: >-
  Protocollo a 6 fasi per la lettura congiunta dei tre segnali di coordinamento kanban
  multi-utente (EP-064 / US-267) — visibilita' bidirezionale al ciclo di push, igiene del
  campo advisory `assignee:`, misura della contesa con oracolo asimmetrico — e per la
  valutazione della condizione di riapertura dei 43 TSK chiusi con l'arbitro a lease.
  Dice cosa fare **con** i numeri, non solo come ottenerli. Sola osservazione: nessuna
  scrittura, nessun `git push`/`pull`, nessuna modifica di `status:`. Non impedisce la
  doppia presa, non risolve la contesa, non garantisce alcuna latenza — la visibilita'
  e' al ciclo di push, quindi minuti.
version: "1.0"
owner: kanban-coordinator
opt_in: kanban_coordination.enabled
depends_on_tools:
  - tools/kanban-observer/kanban-observe.py
  - tools/kanban-trial/collision-oracle.py
epic: EP-064
pattern_version: "2.42"
traceability_source: management/kanban/EP-064-kanban-multi-user-coordination/EP-064.md#esito-2026-09-18
---

# Kanban Coordination Protocol — leggere tre segnali insieme

## Scopo

Un umano (o un agente) che sta per prendere un TSK ha bisogno di tre risposte, e nessuna
delle tre e' sufficiente da sola:

1. **Cosa non vedo, e cosa di me non vedono gli altri** (visibilita', US-266).
2. **L'annotazione di pianificazione e' ancora vera?** (igiene di `assignee:`, US-253).
3. **La contesa e' misurata o solo temuta?** (oracolo asimmetrico, US-251).

Questa skill le raccoglie e — la parte che conta — **le interpreta insieme** (Fase 4),
poi valuta la **condizione di riapertura** dei 43 TSK chiusi con l'arbitro (Fase 5).

## Cosa questo protocollo non fa — dichiarato qui, non in fondo

- **Non impedisce la doppia presa.** Due attori possono prendere lo stesso TSK, prima e
  dopo questa lettura. Nessuna fase produce un lock.
- **Non risolve la contesa.** Se due attori collidono, il protocollo lo **racconta dopo**.
- **Non garantisce alcuna latenza.** La visibilita' e' al **ciclo di push**: **minuti**, e
  l'eta' del dato e' dichiarata in ogni output. Non esiste una promessa 1-5 s: e' esattamente
  la garanzia che EP-064 ha deciso di **non** costruire.
- **Non chiude il failure mode dell'`assignee:`.** La forma centrale (scambio informale fra
  due attori presenti) non lascia traccia in alcun file.
- **Non e' un demone.** E' on-demand. La forma watcher continuo e' stata uccisa per
  activation gap: introdurre un processo persistente e' un errore di decomposizione.

[^src: management/kanban/EP-064-kanban-multi-user-coordination/EP-064.md §«Esito 2026-09-18»]
[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-266-osservatore-on-demand/US-266.md §AC1 §AC2 §AC7]

---

## Fase 0 — Bootstrap

### Input
- Argomenti del chiamante: `--json` (opzionale), root del repo (default: cwd).
- `factory.config.yaml`, blocco `kanban_coordination:`.

### Output
- `configurazione`: `enabled=true` | `enabled=false` | `blocco assente`.
- `modo_invocazione`: `esplicito` | `automatico`.
- Perimetro: repo root, percorso osservato (`management/kanban`), finestra della misura
  = `kanban_coordination.oracle_window_days` (**default 30**, e' anche la finestra della
  condizione di riapertura — vedi Fase 3).
- Soglia d'igiene di riferimento: `kanban_coordination.stale_assignment_days`
  (**default 7**) — valore **dichiarato** dalla factory, passato come parametro quando si
  delega a `tpm-reconcile` §3.4; questa skill non lo inietta da sola.
- Disponibilita' dei due tool (path esistenti ed eseguibili con `python3`).

### Gate

**Gate di attivazione (R.KC8 — fallback esplicito, mai errore)**:

| `modo_invocazione` | `kanban_coordination.enabled` | Comportamento |
|---|---|---|
| `esplicito` | `true` | Procedi. |
| `esplicito` | `false` o blocco assente | **Procedi comunque** (read-only assoluto), ma il report **apre** con il blocco `CONFIGURAZIONE` che dichiara cosa manca e come abilitarla. Mai un errore, mai exit != 0. |
| `automatico` | `true` | Procedi. |
| `automatico` | `false` o blocco assente | **No-op silenzioso**: nessun output, nessun side-effect. |

Precedente: `/vcs-status` (EP-034) — un osservatore read-only si esegue su invocazione
esplicita anche a flag spento, perche' esecuzione esplicita = volonta' esplicita.

**Gate di disponibilita' tool**: un tool assente **non** interrompe il protocollo. Si
registra `segnale_non_disponibile` con il path atteso e si prosegue con gli altri segnali
(R.KC8). Un segnale mancante non viene mai reso come «nessun problema su quel fronte».

### Invarianti applicabili
- **R.KC1**, **R.KC8** (dichiarazione del degrado), **R.KC7** (la dichiarazione di cio' che
  la capability non fa entra nel report, non nelle note a pie' di pagina).

---

## Fase 1 — Visibilita' bidirezionale

### Input
Repo root; flag `--no-fetch` se il chiamante o l'assenza di rete lo impone.

### Tool invocato

```bash
python3 tools/kanban-observer/kanban-observe.py --json            # con fetch
python3 tools/kanban-observer/kanban-observe.py --json --no-fetch # senza contattare il remote
```

### Output (campi del JSON, da usare per nome)

| Campo | Significato |
|---|---|
| `upstream` | remote osservato; `null` = **non esiste un remoto da osservare** |
| `fetch` | `ok` \| `non riuscito` \| `saltato (--no-fetch)` |
| `staleness.eta` | **eta' del dato**: tempo dall'ultimo commit remoto sul kanban |
| `dagli_altri[]` | transizioni di `status:` sul remote che non hai in locale (`tsk`, `da`, `a`, `autore`, `quando`, `commit`) |
| `tuo_silenzio.non_committato[]` | tue modifiche al kanban non committate |
| `tuo_silenzio.committato_non_pushato[]` | tuoi commit sul kanban non pushati |
| `note[]` | cio' che lo strumento **non ha potuto sapere** (rete, upstream, fetch saltato) |

### Cosa fare con questi numeri

1. **`dagli_altri` vuoto non significa «nessuna novita'»**: significa nessuna novita'
   **all'ultimo fetch riuscito**. Leggilo sempre accanto a `fetch` e a `staleness.eta`:
   `fetch: non riuscito` o `saltato` + lista vuota ⇒ **nessuna informazione sul remoto**,
   e va scritto cosi'.
2. **`tuo_silenzio` non vuoto e' il segnale piu' azionabile dell'intero protocollo.** E' la
   **finestra aperta adesso** in cui puo' nascere la doppia presa: finche' non pushi, per gli
   altri quei TSK sono come li hanno lasciati. Azione raccomandata: **pushare** —
   dall'umano. Il protocollo **non pusha** (R.KC2): lo chiede.
3. **`upstream: null`** ⇒ il segnale 1 e' **strutturalmente indisponibile** (nessun remoto).
   Resta valida la meta' locale (`tuo_silenzio`), che e' calcolata comunque.
4. **Ogni resa in chat riporta `staleness.eta`.** Un output che non dichiara l'eta' del dato
   reintroduce il board «bugiardamente fresco» (US-266 AC2): e' un difetto, non una sintesi.

### Invarianti applicabili
- **R.KC2** (solo `fetch`, mai `pull`/`push`), **R.KC7** (staleness sempre dichiarata),
  **R.KC8** (`note[]` propagate integralmente).

---

## Fase 2 — Igiene di `assignee:`

### Input
Frontmatter dei TSK in `management/kanban/**/TSK-*.md` (campi: `assignee`, `status`,
`consumer`, `updated`, `created`).

### Comando di lettura (bounded, read-only)

```bash
grep -rn "^assignee:[[:space:]]*[^[:space:]]" management/kanban --include="TSK-*.md"
```

### Output
- `tsk_con_campo`: numero di TSK con `assignee:` **valorizzato** (campo vuoto o assente non conta).
- Per ciascuno: `id`, `assignee`, `status`, `consumer`, `updated`.

### Cosa fare con questi numeri

| Condizione osservata | Lettura | Azione |
|---|---|---|
| `tsk_con_campo == 0` | Il segnale **tace**. Non e' «igiene perfetta»: e' **assenza di annotazione** (il campo e' opzionale e additivo) | Nessuna anomalia. Se c'e' lavoro umano pianificato in parallelo, **annotarlo in pianificazione** e' l'unica disgiunzione disponibile |
| `assignee:` su `status: done`/`cancelled` | Forma osservabile di **FM-NEW-4** (riallocazione non tracciata) | **Delega a `/lint`** — Check 4as.1 `stale-assignee-on-closed` (WARNING-only) |
| `assignee:` su `consumer: agent` | Annotazione **senza effetto**: il dispatch non legge il campo, copertura **0%** sul traffico agentico | **Delega a `/lint`** — Check 4as.2 `assignee-on-agent-consumer` |
| `assignee:` su TSK aperto e immobile | **FM-NEW-1** (assegnazione ferma): il board appare pieno e non avanza ⇒ falsa fiducia | **Delega a `tpm-reconcile`** §3.4 `assegnazione-ferma`, passando `assegnazione_ferma_soglia_giorni` = `kanban_coordination.stale_assignment_days` (**default 7**) |

**Regola di non-duplicazione.** I presidi autoritativi sono **Check 4as**
(`.claude/skills/lint-checks-kanban.md`) e **`tpm-reconcile` §3.4**. Questa fase e' una
**vista che correla**, non un terzo presidio con soglie proprie: duplicare le soglie
produrrebbe deriva semantica su tre file. Quando serve un verdetto d'igiene, **delega**.

**Limite dichiarato**: la forma **centrale** di FM-NEW-4 — lo scambio informale fra due
attori entrambi presenti — **non lascia traccia**: il frontmatter resta coerente e ogni
strumento tace. Presentare questa fase come «FM-NEW-4 presidiata» e' l'errore che questa
riga impedisce.

### Invarianti applicabili
- **R.KC1**, **R.KC5** (il campo non viene mai scritto: single-writer = TPM/umano che
  pianifica), **R.KC7** (copertura 0% sul traffico agentico dichiarata, non sottintesa).

[^src: .claude/skills/lint-checks-kanban.md §«4as»]
[^src: .claude/skills/tpm-reconcile.md §3.4]
[^src: .claude/skills/scrivi-task.md §«Campo `assignee:` — opzionale, additivo, advisory»]

---

## Fase 3 — Misura della contesa (oracolo asimmetrico)

### Input
Finestra di osservazione = `kanban_coordination.oracle_window_days` (**default 30**), da
Fase 0. E' **la stessa finestra della condizione di riapertura** dichiarata in EP-064:
allargarla aumenta la sensibilita' e **non cambia l'asimmetria** (lo `0` resta assenza di
informazione). Il comando `/kanban-status` **non** espone un flag per cambiarla: chi vuole
un'altra finestra invoca direttamente il tool, che e' l'oggetto autoritativo.

### Tool invocato

```bash
python3 tools/kanban-trial/collision-oracle.py --days <oracle_window_days> --json
```

### Output (campi del JSON, da usare per nome)

| Campo | Significato |
|---|---|
| `grandezza_a_autori_umani_unici.conteggio` | (a) identita' autrici non-bot — **non** e' la metrica di contesa |
| `grandezza_b_finestre_overlap.conteggio` | (b) finestre da 300s con >=2 autori — **e' LA metrica di contesa** (US-251 BR3) |
| `grandezza_c_collisioni.conteggio` | (c) collisioni «stesso file, autori diversi, delta < 300s» |
| `verdetto` | **una** delle tre stringhe ammesse, **verbatim** |
| `verdetto_nota` | la nota che accompagna il verdetto — si riporta **insieme** al verdetto |
| `cecita_strutturale.oracolo_strutturalmente_cieco` | `true` ⇒ lo `0` e' atteso **per costruzione** |
| `perimetro_non_misurabile[]` | cio' che questa fonte **non puo'** vedere |
| `perimetro_osservato.dati_disponibili` | `false` ⇒ nessuna misura, non «0 collisioni» |

### Le tre uscite ammesse — e nessun'altra

```
>=1 collisione                                   ⇒ PROBLEMA REALE
0 collisioni                                     ⇒ NESSUNA INFORMAZIONE
0 collisioni ma >=3 finestre-5min con >=2 autori ⇒ RISCHIO LATENTE NON MATERIALIZZATO
```

### Gate R.KC3 — l'invariante dell'oracolo asimmetrico

1. **Il verdetto si riporta verbatim** dal campo `verdetto`. Non si riscrive, non si
   riassume, non si «traduce in chiaro».
2. **`>=1` collisione ⇒ il problema e' reale.** **`0` ⇒ nessuna informazione.** La
   conclusione simmetrica — la negazione del problema — **non e' ammessa in nessuna forma**:
   ne' come verdetto, ne' come sintesi, ne' come parafrasi, ne' come implicatura
   («non risultano problemi», «il board e' tranquillo», «la misura e' rassicurante»).
3. Il motivo e' **misurato**: `management/kanban/` ha ~**320 commit da una sola identita'
   autrice** (al 2026-09-18: 65 commit in 30 giorni, 272 file, **1** identita'), quindi ogni
   oracolo basato sugli autori git restituisce `0` **per costruzione**. Quello `0` presentato
   come evidenza negativa e' una **bugia statistica**.
4. Il tool presidia l'invariante su tre livelli — costanti verbatim, un **guard che sopprime
   l'output** (exit 3) su **11 formulazioni vietate**, e un test con blocklist
   (`FORMULAZIONI_VIETATE` in `tools/kanban-trial/collision-oracle.py` e
   `tests/test_kanban_trial_oracle.py`: **fonte autoritativa, non duplicarla qui**). Il
   divieto per chi interpreta e' **sul significato, non sulle stringhe**: aggirare la
   blocklist con un sinonimo e' la stessa violazione.
5. **Se il tool esce con 3**, l'output e' stato soppresso dal guard: si riporta «guard
   dell'asimmetria scattato, output soppresso» come **anomalia dello strumento** e **non** si
   ricostruisce il verdetto per altra via.
6. **`dati_disponibili: false`** ⇒ si dice «nessuna misura possibile», **mai** «0 collisioni».

### Invarianti applicabili
- **R.KC3** (cablata qui), **R.KC7**, **R.KC8**.

---

## Fase 4 — Lettura congiunta: cosa fare **con** i numeri

Le fasi 1-3 producono numeri. Questa fase e' il motivo per cui la capability esiste: un
agente che si limita a stampare tre output non serve a nulla.

### 4a — Cosa e' lecito concludere dal verdetto, e cosa no

| Verdetto (verbatim) | Lecito concludere | **Non** lecito concludere | Azione raccomandata |
|---|---|---|---|
| `>=1 collisione ⇒ PROBLEMA REALE` | La contesa **e' misurata**: esistono file toccati da autori diversi entro 300s | Che l'arbitro sia l'unica risposta (lo scope resta una decisione di pianificazione) | **Raccomanda la riapertura dei 43 TSK** (Fase 5), con i numeri allegati. Gate umano |
| `0 collisioni ⇒ NESSUNA INFORMAZIONE` | **Nulla** sulla contesa: la misura non ha informato | Qualunque conclusione in direzione negativa (R.KC3) | **Nessuna raccomandazione sulla contesa.** Restano azionabili solo Fase 1 (il tuo silenzio) e Fase 2 (annotazione in pianificazione) |
| `0 collisioni ma >=3 finestre-5min con >=2 autori ⇒ RISCHIO LATENTE NON MATERIALIZZATO` | Esiste **overlap temporale** fra autori distinti; la collisione non si e' materializzata **ancora** | Che la collisione stia per avvenire, ne' che non avverra' | **Ripeti la misura** al variare del perimetro e **annota `assignee:`** in pianificazione. Non raccomandare costruzione |

### 4b — Il correttivo obbligatorio: la cecita' strutturale

Se `cecita_strutturale.oracolo_strutturalmente_cieco == true`, **il verdetto va riportato
insieme al motivo della cecita'**: con una sola identita' autrice nel perimetro, (b) e (c)
valgono `0` qualunque sia l'attivita' reale. Riportare il verdetto senza questo campo e' la
via piu' facile per far leggere a un umano la conclusione vietata.

### 4c — Letture composite (le combinazioni che informano davvero)

| Segnale 1 (visibilita') | Segnale 3 (contesa) | Lettura congiunta | Azione |
|---|---|---|---|
| `tuo_silenzio` **non vuoto** | qualunque | La finestra di doppia presa e' **aperta adesso**, indipendentemente dal verdetto | **Pushare** (umano, R.KC2). E' l'azione a ROI piu' alto del protocollo |
| `tuo_silenzio` vuoto | `NESSUNA INFORMAZIONE` + cieco `true` | Non c'e' nulla di azionabile e non c'e' nulla da concludere | Solo igiene di pianificazione (Fase 2). **Nessun verdetto sulla contesa** |
| `dagli_altri` **non vuoto** | `NESSUNA INFORMAZIONE` | Gli altri stanno muovendo `status:` **e** la fonte git non e' in grado di vedere la contesa fra sessioni con la stessa identita' autrice | Allinearsi (`git fetch` gia' fatto; l'integrazione e' dell'umano) + annotare `assignee:` |
| `fetch: non riuscito` | qualunque | **Due** segnali degradati contemporaneamente | Dichiararlo in apertura: la lettura e' parziale, e **quanto** parziale |
| qualunque | `PROBLEMA REALE` | La condizione di riapertura e' **soddisfatta** | Fase 5: raccomandazione formale, gate umano |

### 4d — La sezione che il report deve sempre contenere

`## Cosa questa lettura non puo' dire` — obbligatoria (R.KC7). Contenuto minimo:

- il `perimetro_non_misurabile[]` del tool, integrale;
- le `note[]` dell'osservatore (rete, upstream, fetch);
- il limite di Fase 2 (forma centrale di FM-NEW-4 invisibile; copertura 0% sul traffico agentico);
- la latenza reale: **ciclo di push (minuti)**, non tempo reale;
- se `memory/active-sessions.yaml` e' citato: **0 claim registrati** in 7 settimane su 10
  unita' cablate ⇒ `sessions: []` **non** significa «nessuna sessione attiva».

Un report senza questa sezione e' un difetto (US-267 AC8), non una versione piu' leggibile.

### Invarianti applicabili
- **R.KC3**, **R.KC6** (si raccomanda, non si riapre), **R.KC7**.

---

## Fase 5 — Condizione di riapertura dei 43 TSK e report

### Input
Verdetto e grandezze (Fase 3); stato della **ratifica di US-252**
(`design_&_architecture/proposta-modello-allocazione-kanban-ep064.md` §8).

### La condizione, eseguibile e non discrezionale

```bash
python3 tools/kanban-trial/collision-oracle.py --days 30
```

EP-064 ha chiuso **US-254..US-261 (43 TSK)** — l'arbitro con lease — come **superflue, non
rinviate**. La condizione di riapertura ha **due rami indipendenti**:

| Ramo | Condizione | Esito |
|---|---|---|
| **Misura** | `>=1` collisione | I 43 TSK **si riaprono col loro contenuto tecnico intatto** ⇒ **raccomandazione** al TPM, gate umano |
| **Perimetro** | La **ratifica di US-252** cambia il perimetro del caso residuo | **Rivalutazione** raccomandata, indipendentemente dalla misura |
| — | `0` collisioni | **Nessuna informazione** ⇒ nessuna raccomandazione, in nessuna direzione (R.KC3) |

**L'agente non riapre nulla** (R.KC6): la riapertura e' un atto di pianificazione. La
raccomandazione riporta: verdetto verbatim, le tre grandezze, `cecita_strutturale`, la
finestra osservata, e l'elenco delle US coinvolte (US-254..US-261).

### Output — report in chat (nessuna scrittura su disco)

Struttura fissa, nell'ordine (le sezioni 1 e 6 non sono mai omesse):

```
0. CONFIGURAZIONE            (solo se il blocco manca o e' false — fallback esplicito)
1. COSA QUESTA LETTURA E'    latenza dichiarata: ciclo di push (minuti). Non impedisce la
                             doppia presa, non risolve la contesa, non garantisce latenza
2. VISIBILITA'               dagli altri / il tuo silenzio / staleness / fetch
3. IGIENE assignee:          tsk_con_campo + deleghe (/lint 4as, tpm-reconcile §3.4)
4. CONTESA                   verdetto verbatim + nota + tre grandezze + cecita' strutturale
5. RACCOMANDAZIONI           azioni per un umano, in ordine di ROI
6. COSA QUESTA LETTURA NON   perimetro non misurabile + note + limiti (Fase 4d)
   PUO' DIRE
```

Con `--json`: l'esito strutturato definito in `.claude/agents/kanban-coordinator.md`
§«Output / handoff». Il campo `cosa_questa_lettura_non_puo_dire` non e' opzionale.

### Invarianti applicabili
- **R.KC1**, **R.KC4** (nessuna scrittura in `wiki/**`, incluso `wiki/log.md`), **R.KC5**,
  **R.KC6**, **R.KC7**.

---

## Invarianti (R.KC1–R.KC8)

Referenza rapida; fonte autoritativa: `.claude/agents/kanban-coordinator.md` §Invarianti.

| ID | Sintesi | Fase(i) |
|---|---|---|
| R.KC1 | Read-only sul kanban: nessuna scrittura in `management/kanban/**`, nemmeno `updated:`. | **tutte** |
| R.KC2 | Mai `git push`, mai `git pull` (§7 r.14). Solo `fetch` e letture. Un push necessario si **raccomanda**. | **Fase 1** |
| R.KC3 | Oracolo asimmetrico: `>=1` ⇒ problema reale; **`0` ⇒ nessuna informazione**. La negazione del problema non e' esprimibile, in nessuna forma. | **Fase 3**, **Fase 4** |
| R.KC4 | Mai scrittura in `wiki/**` (§7 r.12), incluso `wiki/log.md`. | **Fase 5** |
| R.KC5 | Mai modifica di `status:`, di `assignee:` o di alcun campo di frontmatter. | **Fase 2**, **Fase 5** |
| R.KC6 | Mai riaprire: la condizione di riapertura si valuta e si **raccomanda**. | **Fase 5** |
| R.KC7 | Nessuna promessa non mantenuta: non impedisce la doppia presa, non risolve la contesa, non garantisce latenza (ciclo di push = minuti). Dichiarato dove il lettore lo incontra. | **Fase 0**, **Fase 4**, **Fase 5** |
| R.KC8 | Degradazione dichiarata, mai silenziosa: tool/rete/upstream/config assenti ⇒ si dice cosa non si e' potuto sapere; exit 0. | **Fase 0**, **Fase 1** |

---

## Cross-link

- **Agente owner**: `.claude/agents/kanban-coordinator.md`
- **Comando**: `/kanban-status` (`.claude/commands/kanban-status.md`)
- **Runbook**: `wiki/runbooks/kanban-coordination.md`
- **Tool**: `tools/kanban-observer/kanban-observe.py` (US-266 / TSK-635),
  `tools/kanban-trial/collision-oracle.py` (US-251 / TSK-573+574)
- **Presidi d'igiene delegati**: `.claude/skills/lint-checks-kanban.md` §«4as»,
  `.claude/skills/tpm-reconcile.md` §3.4, `.claude/skills/scrivi-task.md` §«Campo `assignee:`»
- **Epica**: `management/kanban/EP-064-kanban-multi-user-coordination/EP-064.md` §«Esito 2026-09-18»
- **Deliberazione**: `wiki/decisions/tavola-rotonda-9b4e7c02-5a1d-4f38-8c61-2d7a3e9f5b40-2026-09-17.md`
  §Sintesi + §Addendum
- **Analogia strutturale**: `vcs-preflight-protocol` (EP-034) — protocollo read-only a step con
  verdict e remediation; `session-analysis-protocol` (EP-061) — determinism-first, LLM advisory,
  sezione «limiti» obbligatoria nel report

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-267-capability-packaging/US-267.md §AC2 §AC3 §AC4 §AC8]
