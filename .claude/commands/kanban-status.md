---
name: kanban-status
description: "Lettura congiunta dei tre segnali di coordinamento kanban multi-utente (EP-064 / US-267): visibilita' bidirezionale al ciclo di push, igiene del campo advisory `assignee:`, misura della contesa con oracolo asimmetrico — piu' la valutazione della condizione di riapertura dei 43 TSK chiusi. Read-only assoluto: mai push/pull, mai scrittura, mai modifica di `status:`. Non impedisce la doppia presa, non risolve la contesa, non garantisce alcuna latenza: la visibilita' e' al ciclo di push, quindi minuti. Funziona anche a capability non configurata (fallback esplicito, non errore)."
argument-hint: "[--json]"
allowed-tools: Read, Glob, Bash
skill: kanban-coordination-protocol
opt_in: kanban_coordination.enabled
epic: EP-064
pattern_version: "2.42"
---

# /kanban-status

Argomenti utente: `$ARGUMENTS`

Invoca la capability di coordinamento kanban multi-utente e produce un **report in chat**.
Non e' un gate: **informa, non blocca**. Non muta nulla — nessun file scritto, nessun
`git push`, nessun `git pull`, nessun `status:` toccato.

**Cosa il report da'**: cosa hanno fatto gli altri che non vedi, **cosa hai fatto tu che gli
altri non vedono**, lo stato dell'igiene di `assignee:`, il verdetto della misura di contesa,
e la valutazione della condizione di riapertura dei 43 TSK chiusi con l'arbitro a lease.

**Cosa il report non da'** — dichiarato qui perche' e' la parte che si dimentica:

- **non impedisce la doppia presa** (nessun lock, ne' prima ne' dopo la lettura);
- **non risolve la contesa** (se due attori collidono, il report lo racconta dopo);
- **non garantisce alcuna latenza**: la visibilita' e' al **ciclo di push**, quindi **minuti**,
  e l'eta' del dato e' dichiarata in ogni esecuzione.

---

## Sintassi

```
/kanban-status            # report in chat
/kanban-status --json     # esito strutturato su stdout (machine-readable)
```

| Flag | Tipo | Default | Semantica |
|---|---|---|---|
| `--json` | flag | assente | Emette l'esito strutturato invece del report human-readable |

**Nessun altro flag, per scelta.** La finestra della misura di contesa viene da
`kanban_coordination.oracle_window_days` (**default 30**), che e' anche la finestra della
**condizione di riapertura** dichiarata in EP-064 §«Esito 2026-09-18»: esporla come flag
farebbe divergere l'invocazione occasionale dalla condizione che deve valutare. Per una
misura su altra finestra si usa direttamente il tool
(`python3 tools/kanban-trial/collision-oracle.py --days N`), che e' l'oggetto autoritativo.
Allargare la finestra aumenta la sensibilita' e **non cambia l'asimmetria** (vedi §Vincoli).

---

## Procedura

### Step 0 — Gate `kanban_coordination.enabled` (fallback esplicito, mai errore)

Leggi `factory.config.yaml`, blocco `kanban_coordination:`. **Invocazione esplicita del
comando = volonta' esplicita**: il comando e' read-only assoluto, quindi si esegue anche a
flag spento o a blocco assente — ma **dichiara** lo stato della configurazione in apertura.

```
SE blocco `kanban_coordination:` assente OPPURE enabled == false:
  → NON e' un errore. Esegui comunque e apri il report con:

    CONFIGURAZIONE
    Capability `kanban_coordination` non configurata — lettura eseguita comunque (read-only).
    Manca: blocco `kanban_coordination:` in factory.config.yaml
      kanban_coordination:
        enabled: true
    Effetto dell'assenza: nessun innesto automatico della lettura; solo invocazione esplicita.
    Vedi wiki/runbooks/kanban-coordination.md e EP-064 §«Esito 2026-09-18».
```

Precedente: `/vcs-status` (EP-034) funziona anche a `branch_awareness.enabled: false`, per la
stessa ragione. Il gate automatico (innesto in un'azione che l'utente compie comunque) e'
separato e **richiede** il flag: vedi `.claude/agents/kanban-coordinator.md` §«Gate config».

### Step 1 — Parse argomenti

- `flag_json` — `true` se `--json` presente, altrimenti `false`.
- Argomento non riconosciuto → **STOP** con: «`/kanban-status` accetta solo `--json`.
  Ricevuto: `<arg>`.»

### Step 2 — Invocazione della capability

Invoca la skill `.claude/skills/kanban-coordination-protocol.md` (owner:
`kanban-coordinator`) con il payload:

```yaml
modo_invocazione: esplicito
output:
  json: <true|false>
config:
  enabled: <kanban_coordination.enabled | assente>
  oracle_window_days: <kanban_coordination.oracle_window_days | 30>
  stale_assignment_days: <kanban_coordination.stale_assignment_days | 7>
```

La skill esegue:

| Fase | Nome | Azione |
|---|---|---|
| 0 | Bootstrap | Gate config, perimetro, disponibilita' tool |
| 1 | Visibilita' | `kanban-observe.py --json` — le due direzioni + staleness |
| 2 | Igiene `assignee:` | Lettura frontmatter + delega a `/lint` (4as) e `tpm-reconcile` §3.4 (`stale_assignment_days`) |
| 3 | Misura contesa | `collision-oracle.py --days <oracle_window_days> --json` — verdetto **verbatim** |
| 4 | Lettura congiunta | Matrice di interpretazione: cosa fare **con** i numeri |
| 5 | Riapertura + report | Valutazione della condizione dei 43 TSK; nessuna scrittura |

### Step 3 — Output

**Se `--json`**: esito strutturato come da `.claude/agents/kanban-coordinator.md`
§«Output / handoff». Il campo `cosa_questa_lettura_non_puo_dire` e' sempre presente.

**Altrimenti (default)**: report in chat con sezioni in ordine fisso. Esempio con i **numeri
reali** misurati sul meta-framework il 2026-09-18 (esecuzione con `--no-fetch`, quindi con la
nota di degrado in chiaro):

```
KANBAN STATUS — stato al ciclo di push, non in tempo reale
==========================================================
COSA QUESTA LETTURA E'
  Visibilita' al ciclo di push (minuti). Non impedisce la doppia presa, non risolve
  la contesa, non garantisce alcuna latenza.

VISIBILITA'                       remoto: origin/main  (fetch: saltato (--no-fetch))
  eta' del dato        : 20 h 32 min dall'ultimo commit remoto sul kanban
  dagli altri (0)      : nessuna transizione di status che non hai gia'
  il tuo silenzio (5)  : 1 modifica non committata + 4 commit non pushati
                         ^ e' la finestra aperta adesso in cui nasce la doppia presa
  nota                 : fetch saltato — lo stato puo' essere piu' vecchio di quanto sembri,
                         e `dagli altri (0)` non e' «nessuna novita'»: e' nessuna
                         informazione sul remoto

IGIENE assignee:
  TSK con il campo valorizzato : 0 — il segnale tace (assenza di annotazione, non igiene)
  presidi autoritativi         : /lint (Check 4as) · tpm-reconcile §3.4
                                 (soglia: stale_assignment_days = 7 giorni)

CONTESA (finestra: oracle_window_days = 30 giorni)
  verdetto  : 0 collisioni ⇒ NESSUNA INFORMAZIONE
  nota      : 0 collisioni su questa fonte NON e' evidenza in direzione opposta.
  grandezze : (a) autori umani unici 1 · (b) finestre-300s con >=2 autori 0 (su 60
              finestre attive) · (c) collisioni 0 (su 272 file)
  cecita'   : oracolo strutturalmente cieco — una sola identita' autrice su 65 commit
              non-bot: (b) e (c) valgono 0 PER COSTRUZIONE

RIAPERTURA DEI 43 TSK (US-254..US-261)
  non raccomandata — e non sconsigliata: la misura non ha informato.
  Si riapre con >=1 collisione, oppure se la ratifica di US-252 cambia il perimetro.
  Stato ratifica US-252: bozza pronta (proposta-modello-allocazione-kanban-ep064.md §8)

RACCOMANDAZIONI (per un umano, in ordine di ROI)
  1. Pushare i 4 commit sul kanban: finche' restano locali, per gli altri quei TSK
     sono come li hanno lasciati. (Il comando non pusha — §7 r.14.)
  2. Se c'e' lavoro umano pianificato in parallelo, annotare `assignee:` in
     pianificazione: e' l'unica disgiunzione disponibile, e copre 0% del traffico agentico.

COSA QUESTA LETTURA NON PUO' DIRE
  - due sessioni indipendenti che committano con la stessa identita' autrice sono
    indistinguibili in git: la contesa fra loro e' invisibile a questa fonte;
  - il lavoro non committato non esiste nella storia git e non entra nelle tre grandezze;
  - la forma centrale della riallocazione non tracciata (scambio informale fra due attori
    presenti) non lascia traccia in alcun file: nessuno strumento della factory la vede;
  - `memory/active-sessions.yaml` con `sessions: []` non significa «nessuna sessione
    attiva»: significa nessun claim registrato (0 claim in 7 settimane su 10 unita' cablate).
```

Le sezioni **COSA QUESTA LETTURA E'** e **COSA QUESTA LETTURA NON PUO' DIRE** non sono mai
omesse, nemmeno in caso di lettura degradata (R.KC7).

---

## Degradazione — cosa succede quando un segnale manca

Nessuno di questi casi e' un errore: exit 0, e il report **dichiara cosa non ha potuto
sapere** (R.KC8). Un segnale mancante **non** viene mai reso come «nessun problema su quel
fronte».

| Condizione | Comportamento |
|---|---|
| Blocco `kanban_coordination:` assente o `false` | Esegue; apre con la sezione `CONFIGURAZIONE` (Step 0) |
| `tools/kanban-observer/kanban-observe.py` assente | Segnale 1 non disponibile, path atteso dichiarato; prosegue con 2 e 3 |
| `tools/kanban-trial/collision-oracle.py` assente | Segnale 3 non disponibile: **nessun verdetto sulla contesa**, in nessuna direzione |
| Rete assente / `fetch` non riuscito | Stato = ultimo fetch riuscito; lo dichiara, e con `dagli_altri` vuoto scrive «nessuna informazione sul remoto» |
| Branch senza upstream | Non esiste un remoto da osservare; resta valida la meta' locale (`tuo_silenzio`) |
| Non e' un repo git | Nessuna osservazione possibile; lo dichiara |
| `collision-oracle.py` esce con **3** | Guard dell'asimmetria scattato, output soppresso: riportato come **anomalia dello strumento**; il verdetto **non** viene ricostruito per altra via |

---

## Vincoli

- **Read-only assoluto (R.KC1)**: nessuna scrittura in `management/kanban/**`, in `wiki/**`
  (incluso `wiki/log.md`, R.KC4), in `factory.config.yaml` o in `memory/`. Nessun file prodotto.
- **Mai `git push`, mai `git pull` (R.KC2, §7 r.14)**: solo `git fetch` e letture. Quando un
  push e' l'azione giusta, il comando **lo raccomanda** e si ferma.
- **Mai modifica di `status:` o `assignee:` (R.KC5)**: il single-writer di `assignee:` e' il
  TPM/umano che pianifica; il campo resta **advisory** e non entra nel dispatch (US-253 BR1).
- **Mai riaprire (R.KC6)**: la condizione di riapertura dei 43 TSK si **valuta e si
  raccomanda**; la riapertura e' un atto di pianificazione con gate umano.
- **Oracolo asimmetrico (R.KC3)**: `>=1` collisione ⇒ il problema e' reale; **`0` ⇒ nessuna
  informazione**. Il report non conclude mai che la contesa non esiste — ne' come verdetto,
  ne' come parafrasi, ne' come implicatura. Il motivo e' misurato: `management/kanban/` ha
  ~320 commit da **una sola** identita' autrice, quindi ogni oracolo basato sugli autori git
  restituisce `0` **per costruzione**, e quello `0` come evidenza negativa e' una bugia
  statistica.
- **Nessuna promessa non mantenuta (R.KC7)**: non impedisce la doppia presa, non risolve la
  contesa, non garantisce latenza. Dichiarato in apertura del report, non in coda.
- **Non e' un demone**: on-demand. La forma watcher continuo e' stata scartata per activation
  gap («nessuno la tiene accesa»).

---

## Prerequisiti

- Nessun prerequisito **bloccante**: il comando funziona a capability non configurata
  (fallback esplicito) e con i tool assenti (degradazione dichiarata).
- Per la lettura completa:
  - `kanban_coordination.enabled: true` in `factory.config.yaml` (default `false`, opt-in) —
    necessario solo per l'**innesto automatico**, non per l'invocazione esplicita;
  - `kanban_coordination.oracle_window_days` (default `30`) e
    `kanban_coordination.stale_assignment_days` (default `7`) — letti, mai scritti; a campo
    assente si applica il default e lo si dichiara nel report;
  - `tools/kanban-observer/kanban-observe.py` (EP-064 US-266 / TSK-635, done);
  - `tools/kanban-trial/collision-oracle.py` (EP-064 US-251 / TSK-573+574, done);
  - `.claude/skills/kanban-coordination-protocol.md` + `.claude/agents/kanban-coordinator.md`;
  - Python 3.9+ stdlib (zero dipendenze esterne), `git` nel PATH.

---

## Esempi d'uso

```bash
# Prima di prendere un TSK: cosa non vedo, e cosa di me non vedono gli altri
/kanban-status

# Esito strutturato (machine-readable) per un altro agente o per uno script
/kanban-status --json

# Valutare la condizione di riapertura dei 43 TSK chiusi con l'arbitro:
# e' la sezione RIAPERTURA del report — la misura sottostante e' questa, ed e' autoritativa
python3 tools/kanban-trial/collision-oracle.py --days 30
```

---

## Cross-link

- **Skill**: `.claude/skills/kanban-coordination-protocol.md` (6 fasi, R.KC1–R.KC8)
- **Agente**: `.claude/agents/kanban-coordinator.md` (owner della capability)
- **Runbook**: `wiki/runbooks/kanban-coordination.md` — il problema, cosa si e' scelto di
  **non** costruire e perche', come si usa, condizione di riapertura
- **Tool**: `tools/kanban-observer/kanban-observe.py`, `tools/kanban-trial/collision-oracle.py`
- **Presidi d'igiene delegati**: `/lint` (Check 4as in
  `.claude/skills/lint-checks-kanban.md`), `.claude/skills/tpm-reconcile.md` §3.4
- **Config block**: `factory.config.yaml` → `kanban_coordination:`
- **Epica**: `management/kanban/EP-064-kanban-multi-user-coordination/EP-064.md`
  §«Esito 2026-09-18»
- **Deliberazione**: `wiki/decisions/tavola-rotonda-9b4e7c02-5a1d-4f38-8c61-2d7a3e9f5b40-2026-09-17.md`
  §Sintesi + §Addendum
- **Analogia strutturale**: `/vcs-status` (EP-034) — snapshot read-only, mai un gate, eseguibile
  a flag spento; `/session-analysis` (EP-061) — gate config + skill a fasi + output dual

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-267-capability-packaging/US-267.md §AC3 §AC4 §AC5 §AC8]
