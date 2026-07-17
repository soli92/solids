---
id: test-content-share-slug-convention
tsk: TSK-405
epic: EP-048
type: integration
skill: content-share-protocol
fixture: tests/content-share/fixtures/small.html
fixture_size_kb: 4
invariant: R.CS1
---

# Test Slug Convention — content-share-protocol (R.CS1)

Piano di test per la validazione del formato slug definito da R.CS1.

**Regola R.CS1**:
```
slug format: {source_repo_slug}-{content_slug}
regex:       ^[a-z][a-z0-9-]{1,78}[a-z0-9]$   (max 80 caratteri totali)
```

R.CS1 è una guard critica: il componente `guard` di `soli-frames` (US-021 lato
target) usa il formato slug come chiave di idempotenza e routing. Uno slug
non conforme causerebbe un 422 lato `soli-frames` o, peggio, un conflitto
silenzioso tra contenuti distinti che condividono una chiave malformata.
La validazione avviene in Fase 1 della skill prima di costruire il payload,
così da non sprecare un gate umano (Fase 3) su input già invalidi.

Tutti i test vanno eseguiti dalla root del repo `soli-multi-agents-factory`.
I comandi `/share` invocano la skill `content-share-protocol` tramite
l'adapter Claude Code. Il flag `--dry-run` garantisce che nessuna chiamata
API venga mai eseguita.

---

## Scenario 1 — Composizione automatica: slug valido post-composizione

**Invariante verificata**: R.CS1 — la skill auto-compone il slug come
`{source_repo_slug}-{basename_senza_estensione}` quando `--slug` non viene
fornito; il risultato deve essere conforme alla regex prima di proseguire.

### Setup

In `factory.config.yaml`:

```yaml
content_share:
  enabled: true
  source_repo_slug: "soli-factory"
  source_repo: "soli92/soli-multi-agents-factory"
  pat_env: SOLI_FRAMES_PAT
  dispatch_secret_env: SOLI_FRAMES_DISPATCH_SECRET
  artifact_categories:
    custom: true
```

Impostare le variabili d'ambiente (valori dummy — sufficienti per dry-run):

```bash
export SOLI_FRAMES_PAT=ghp_DUMMY_dry_run_value_000000000000
export SOLI_FRAMES_DISPATCH_SECRET=secret-dummy-dry-run
```

### Azione

```
/share tests/content-share/fixtures/small.html --title="Test" --dry-run
```

Nessun flag `--slug` fornito: la skill deve derivare `content_slug` dal
basename del file (`small.html` → `small`) e comporre automaticamente
`soli-factory-small`.

### Expected

**Fase 1**:
- La skill legge il basename del file: `small` (da `small.html`)
- Slug auto-composto: `soli-factory-small`
- Verifica regex R.CS1: `^[a-z][a-z0-9-]{1,78}[a-z0-9]$`
  - Lunghezza: 17 caratteri — conforme
  - Carattere iniziale: `s` (`[a-z]`) — conforme
  - Carattere finale: `l` (`[a-z0-9]`) — conforme
- Risultato validazione: EGRESS_PASS (R.CS1 rispettata)

**Fase 3** (gate umano dry-run) — riepilogo visibile con:
- `Slug: soli-factory-small`
- `EGRESS_PASS`
- Messaggio terminale: `"DRY RUN completato. Nessun dispatch eseguito."`

**Fase 4**: NON avviata.

### Pass criterion

Output contiene entrambe le stringhe:
1. `"soli-factory-small"` — slug auto-composto nel riepilogo gate
2. `"EGRESS_PASS"` — validazione R.CS1 superata

Output NON contiene `"R.CS1"` in contesto di errore né `"STOP"`.

### Verifica negativa

Se lo slug nel riepilogo fosse diverso da `soli-factory-small` (es. solo
`small`, o un formato alternativo), il test fallisce — indica che la logica
di composizione non segue il pattern R.CS1. Se la skill emettesse STOP in
Fase 1 su questo input valido, sarebbe una regressione sulla composizione
automatica.

---

## Scenario 2 — Slug esplicito non conforme: carattere iniziale non [a-z]

**Invariante verificata**: R.CS1 — slug esplicito passato via `--slug` che
inizia con un carattere non alfabetico minuscolo deve bloccare la skill in
Fase 1, prima del gate umano (Fase 3) e del dispatch (Fase 4).

### Setup

In `factory.config.yaml` (stesso di Scenario 1):

```yaml
content_share:
  enabled: true
  source_repo_slug: "soli-factory"
  source_repo: "soli92/soli-multi-agents-factory"
  pat_env: SOLI_FRAMES_PAT
  dispatch_secret_env: SOLI_FRAMES_DISPATCH_SECRET
  artifact_categories:
    custom: true
```

```bash
export SOLI_FRAMES_PAT=ghp_DUMMY_dry_run_value_000000000000
export SOLI_FRAMES_DISPATCH_SECRET=secret-dummy-dry-run
```

### Azione

```
/share tests/content-share/fixtures/small.html --slug="_bad-slug" --dry-run
```

Lo slug `_bad-slug` inizia con underscore `_`, che non soddisfa `^[a-z]`
della regex R.CS1.

### Expected

**Fase 1** — STOP con messaggio esplicito:
- La skill rileva che `_bad-slug` non è conforme a R.CS1
- Output di errore che include almeno uno tra:
  - La stringa `"R.CS1"`
  - La stringa `"regex"`
  - La stringa `"^[a-z]"`
- La regex usata per la validazione è riportata nel messaggio di errore
  (per facilitare il debug dell'utente)

**Fase 3** (gate umano): NON raggiunta.
**Fase 4** (dispatch): NON avviata.

### Pass criterion

Output contiene almeno una delle stringhe:
- `"R.CS1"`
- `"regex"`
- `"^[a-z]"`

Output NON contiene il riepilogo del gate umano (Fase 3): assenza di
`"DRY RUN completato"` o `"Slug:"` nel contesto del riepilogo.

### Verifica negativa

Se la skill proseguisse fino a Fase 3 o Fase 4 con `--slug="_bad-slug"`,
il test fallisce — indica che la validazione R.CS1 in Fase 1 non è operativa.
Questo è un bug bloccante: uno slug con carattere iniziale non valido
causerebbe un 422 lato `soli-frames`.

---

## Scenario 3 — Slug troppo lungo: > 80 caratteri totali

**Invariante verificata**: R.CS1 — la regex `^[a-z][a-z0-9-]{1,78}[a-z0-9]$`
impone un massimo di 80 caratteri. Uno slug che supera questo limite deve
bloccare la skill in Fase 1 con un messaggio che indica la lunghezza effettiva
e il limite massimo.

### Setup

In `factory.config.yaml` (stesso di Scenario 1):

```yaml
content_share:
  enabled: true
  source_repo_slug: "soli-factory"
  source_repo: "soli92/soli-multi-agents-factory"
  pat_env: SOLI_FRAMES_PAT
  dispatch_secret_env: SOLI_FRAMES_DISPATCH_SECRET
  artifact_categories:
    custom: true
```

```bash
export SOLI_FRAMES_PAT=ghp_DUMMY_dry_run_value_000000000000
export SOLI_FRAMES_DISPATCH_SECRET=secret-dummy-dry-run
```

### Azione

```
/share tests/content-share/fixtures/small.html --slug="questo-slug-e-talmente-lungo-da-superare-il-limite-massimo-di-ottanta-caratteri" --dry-run
```

Lo slug esplicito `questo-slug-e-talmente-lungo-da-superare-il-limite-massimo-di-ottanta-caratteri`
ha 82 caratteri, che supera il limite di 80 caratteri della regex R.CS1.

### Expected

**Fase 1** — STOP con messaggio che include:
- La lunghezza effettiva dello slug (82 caratteri)
- Il limite massimo consentito (80 caratteri)

**Fase 3** (gate umano): NON raggiunta.
**Fase 4** (dispatch): NON avviata.

### Pass criterion

Output contiene entrambe le stringhe:
1. `"80"` — limite massimo citato nel messaggio di errore
2. La lunghezza effettiva dello slug (es. `"82"`) — lunghezza misurata
   citata nel messaggio di errore

Output NON contiene il riepilogo del gate umano (Fase 3): assenza di
`"DRY RUN completato"` o `"Slug:"` nel contesto del riepilogo.

### Verifica negativa

Se la skill proseguisse fino a Fase 3 con questo slug fuori limite, il test
fallisce — regressione sulla validazione di lunghezza R.CS1. Un payload
con slug > 80 caratteri verrebbe rifiutato da `soli-frames` con 422, dopo
che il gate umano è già stato presentato all'utente, causando un'esperienza
confusa.

---

## Riepilogo scenari

| # | Input slug | Motivo di test | Expected | Pass criterion |
|---|---|---|---|---|
| 1 | *(assente — auto-composizione)* | Composizione automatica da basename `small.html` → `soli-factory-small` (17 chars, regex conforme) | EGRESS_PASS + riepilogo gate con slug corretto | `"soli-factory-small"` visibile nel riepilogo + `"EGRESS_PASS"` |
| 2 | `_bad-slug` | Carattere iniziale `_` non in `[a-z]` — violazione `^[a-z]` | STOP in Fase 1 + messaggio con `"R.CS1"` o `"regex"` o `"^[a-z]"` | Almeno una tra le tre stringhe presente + assenza riepilogo gate |
| 3 | `questo-slug-e-talmente-lungo-da-superare-il-limite-massimo-di-ottanta-caratteri` | 82 chars > 80 chars — violazione lunghezza massima R.CS1 | STOP in Fase 1 + messaggio con `"80"` e lunghezza effettiva | `"80"` + `"82"` (o lunghezza effettiva) presenti + assenza riepilogo gate |

---

## Nota su R.CS1 e impatto downstream

R.CS1 non e' solo un vincolo di formato cosmetic: il componente `guard` di
`soli-frames` (US-021) usa lo slug come chiave primaria per l'idempotenza
del content store e per il routing dei viewer URL
(`https://soli-frames.vercel.app/viewer/<slug>`).

Uno slug non conforme provoca:
- **422 Unprocessable Entity** da `soli-frames` API — l'intera operazione
  di condivisione fallisce dopo che l'utente ha gia' confermato il gate umano.
- **Conflitti di chiave** se due slug invalidi collidono nel content store
  dopo sanitizzazione lato `soli-frames`.

La validazione fail-fast in Fase 1 (prima del gate umano e del dispatch)
garantisce che l'utente riceva feedback immediato e azionabile, senza sprecare
il gate umano (Fase 3) su input gia' invalidi.

---

## Note di esecuzione

- I 3 scenari sono indipendenti e possono essere eseguiti in qualsiasi ordine.
- Tutti usano `--dry-run`: nessuna chiamata API reale viene mai eseguita.
- La fixture `small.html` (4 KB) e' sufficiente per tutti e 3 gli scenari:
  R.CS1 opera sul nome/slug, indipendentemente dal contenuto del file.
- Dopo ogni scenario, non e' necessario ripristinare `factory.config.yaml`
  se si usa la stessa configurazione base (stessa tra i 3 scenari).
