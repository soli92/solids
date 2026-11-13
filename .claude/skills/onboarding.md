---
id: onboarding
version: v1.1
layer: docs
trigger: /onboarding
description: >
  Skill invocabile da un nuovo contributor o agente. Produce un report
  in-chat contestuale (nessun file scritto) con 4 sezioni: factory corrente,
  task onboarding-friendly, 5 invarianti critiche lette da PATTERN.md §7,
  passo successivo statico. Tecnologia-agnostica — legge solo file locali.
  Opt-in (onboarding_day0.enabled): Day 0 per ruolo, report esteso, benvenuto --compact.
---

# Skill: onboarding

> Invocazione: `/onboarding [--compact] [--ruolo=<ruolo>] [--check-env]` (i flag valgono solo con la modalità Day 0)
> Output: esclusivamente in-chat. **Nessun file viene scritto** (`wiki/`,
> `management/`, o qualsiasi altra directory).
> Sorgenti dichiarate: `factory.config.yaml`, `management/kanban/sprint.md`,
> `PATTERN.md`, `.claude/agents/`.

---

## Procedura

Esegui i passi seguenti nell'ordine. Ogni passo legge una sorgente locale;
non inventare mai dati non presenti nelle sorgenti (invariante R.2).

---

### Passo 1 — Leggi `factory.config.yaml`

Leggi il file `factory.config.yaml` dalla root del repo.

Estrai e presenta come **Sezione 1 — Factory corrente**:

1. **Versione factory** → campo `pattern_version` (o `project.pattern_version`).
2. **Capability attive** → tutte le chiavi di primo livello (o sottochiave) che
   contengono `enabled: true`. Presenta come lista compatta `- <nome>: true`.
   Non elencare capability con `enabled: false` o assenti.
3. **Agenti installati** → conta i file `*.md` presenti in `.claude/agents/`.
   Mostra il conteggio numerico (es. "17 agenti").

Formato atteso per la sezione:

```
## Sezione 1 — Factory corrente

| Campo | Valore |
|---|---|
| Pattern version | <pattern_version> |
| Agenti installati | <N> file in .claude/agents/ |

### Capability attive (enabled: true)
- <capability-1>
- <capability-2>
- ...
```

---

### Passo 2 — Leggi `management/kanban/sprint.md`

Leggi il file `management/kanban/sprint.md`.

Presenta come **Sezione 2 — Task onboarding-friendly**:

- **Caso A**: se esistono task con `status: todo` **e** tag `onboarding-friendly`
  (o etichetta equivalente nel frontmatter/testo), mostrali tutti con ID, titolo
  e file sprint di riferimento.
- **Caso B**: se nessun task ha il tag `onboarding-friendly`, mostra i **3 task
  in `status: todo`** con effort stimato più basso (campo `effort:` o `estimate:`
  nel frontmatter; in assenza di campo effort, considera i task più brevi come
  descrizione). Indica esplicitamente «Nessun tag onboarding-friendly trovato —
  mostro i 3 task a minor effort».

Includi sempre il link al file sprint:
`→ Sprint file: management/kanban/sprint.md`

---

### Passo 3 — Leggi `PATTERN.md §7` (live — non hardcodare)

**Leggi il file `PATTERN.md`** dalla root del repo.

Individua la sezione `§7` (titolo esatto: cerca `## §7` o `# §7` o la sezione
intitolata "Invarianti" / "Invarianti inviolabili"). Estrai il testo delle sole
invarianti **R.1, R.2, R.5, R.12, R.14** riassumendole in una riga ciascuna.

> IMPORTANTE: il testo delle invarianti deve provenire dalla lettura diretta di
> `PATTERN.md` — **non hardcodare il testo in questa skill**. Se il testo in
> `PATTERN.md` viene aggiornato, il report si aggiorna automaticamente.

Presenta come **Sezione 3 — 5 invarianti critiche**:

```
## Sezione 3 — 5 invarianti critiche (da PATTERN.md §7)

| Invariante | Sintesi |
|---|---|
| R.1  | <estratto sintetico da PATTERN.md §7> |
| R.2  | <estratto sintetico da PATTERN.md §7> |
| R.5  | <estratto sintetico da PATTERN.md §7> |
| R.12 | <estratto sintetico da PATTERN.md §7> |
| R.14 | <estratto sintetico da PATTERN.md §7> |

_Il testo viene letto da `PATTERN.md §7` — si aggiorna automaticamente._
```

---

### Passo 4 — Sezione statica: passo successivo

Appendi **sempre** questa sezione statica al report. Le righe marcate `[se esiste]` puntano a
documenti del meta-framework (QUICKSTART.md e `wiki/getting-started/` non si copiano nelle
factory derivate, seed v2-45 §2): includile solo se il file esiste, e togli il marcatore.

```
## Sezione 4 — Passo successivo

→ Verifica ambiente: /init-check (PASS/WARN/FAIL — READY/PARTIAL/BLOCKED)
→ Capability router: /help <domanda> (fonte: CAPABILITIES.md)
→ Istruzioni del progetto: CLAUDE.md
→ Quick start: QUICKSTART.md                                                  [se esiste]
→ Pattern in una pagina: wiki/getting-started/pattern-in-one-page.md           [se esiste]
→ Installer / bootstrap: wiki/getting-started/factory-installer-quickstart.md  [se esiste]
```

---

## Modalità Day 0 per ruolo (opt-in)

Si attiva con `onboarding_day0.enabled: true` in `factory.config.yaml` (default `false`: a flag
spento la procedura sopra resta identica e i flag `--compact`/`--ruolo`/`--check-env` non esistono).
Il ruolo sceglie solo il testo del Day 0 e **non dà né toglie permessi**. La dipendenza da
`/promemoria` è opzionale: a `promemoria_operatori.enabled: false` il ruolo arriva da `--ruolo` oppure vale
`generico`, e non si propone la registrazione.

**Prima di eseguirla, leggi** `.claude/skills/references/onboarding/passi-1-4-dettaglio.md`
(sostituisce i Passi 1-4 sopra) e, per comporre il report, `report-errori-sorgenti.md`. Poi:

- **Passo 5 — Day 0 per ruolo**: `python3 tools/onboarding/day0.py [--ruolo <r>]`. I ruoli e le
  etichette sono in `onboarding_day0.roles` (slug: etichetta), il testo in `onboarding_day0.file`
  (default `.claude/skills/references/onboarding/day0-per-ruolo.md`, una sezione `## <ruolo>` a
  ruolo più `## generico`). Exit 2 (ruolo sconosciuto): mostra l'elenco `ruoli` dell'output. Exit 1
  (file o sezione assente): usa le tre azioni del paragrafo «prime azioni» della wiki di onboarding
  se c'è, altrimenti `/query "cosa fa questa factory"`, `sprint.md` e `/dev <id-task>`.
- **Passo 6 — Stato finale**: BLOCKED > PARTIAL > READY secondo la tabella Sorgenti dichiarate;
  lo stato orienta, non ferma.
- **`--compact`**: solo un benvenuto di al massimo 12 righe (versione, stato ambiente se
  `/init-check` è già stato eseguito nella sessione, output di `day0.py`); niente domanda sul
  ruolo (la fa `/promemoria --registrami --ruolo=<r>`, perché la risposta va in anagrafica).
- **`--check-env`**: solo i Passi 2-3 del dettaglio, report ridotto con la sola Sezione 3.

Verifica a un mese (per il Tech Lead, sola lettura): `python3 tools/onboarding/verifica_day0.py --dal AAAA-MM-GG`
elenca chi si è registrato dopo la data, il ruolo e la prima attività osservata nel kanban; non decide
nulla e richiede l'anagrafica di `/promemoria`.

---

## Vincoli

| Vincolo | Dettaglio |
|---|---|
| Nessun file scritto | Output esclusivamente in-chat. Non creare file in `wiki/`, `management/` o altrove. |
| No invenzione (R.2) | Ogni dato mostrato deve provenire da una delle sorgenti dichiarate. Se un file non esiste o un campo è assente, dillo esplicitamente. |
| Lettura live PATTERN.md | Il testo di §7 va letto al momento dell'invocazione — non è hardcodato in questa skill. |
| Comandi ammessi (modalità Day 0) | Solo `day0.py`, `/init-check` già eseguito e il test di presenza del file di ambiente: mai il contenuto di un file di ambiente. |
| Tecnologia-agnostica | La skill usa solo lettura di file locali. Nessun tool esterno, nessuna rete. |
| Self-documenting | Ogni sezione dichiara la propria sorgente (es. «letto da factory.config.yaml»). |

---

## Gestione errori

- **`factory.config.yaml` assente**: segnala «`factory.config.yaml` non trovato —
  verifica di essere nella root della factory». Continua con le sezioni successive.
- **`management/kanban/sprint.md` assente**: segnala «sprint.md non trovato —
  consulta `management/kanban/` per il file sprint attivo». Mostra comunque le
  sezioni 3 e 4.
- **`PATTERN.md` assente o §7 non localizzabile**: segnala «`PATTERN.md §7` non
  trovato — le invarianti non possono essere estratte automaticamente. Leggi
  `PATTERN.md` manualmente». Non hardcodare il testo.
- **`.claude/agents/` assente**: conta = 0, segnala.
