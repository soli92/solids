---
id: test-content-share-smoke
tsk: TSK-403
epic: EP-048
type: integration
skill: content-share-protocol
fixture: tests/content-share/fixtures/small.html
fixture_size_kb: 4
---

# Test Smoke — content-share-protocol

Piano di test manuale per i 3 scenari principali della skill
`.claude/skills/content-share-protocol.md`. Nessun dispatch reale richiesto:
lo Scenario 3 usa `--dry-run` che arresta il flusso prima di Fase 4.

Tutti i test vanno eseguiti dalla root del repo
`soli-multi-agents-factory`. I comandi `/share` invocano la skill
`content-share-protocol` tramite l'adapter Claude Code.

---

## Scenario 1 — R.CS2: flag spento → STOP

**Invariante verificata**: R.CS2 — a `content_share.enabled: false` nessuna
variabile letta, nessuna API invocata.

### Setup

In `factory.config.yaml`, verificare o forzare (default):

```yaml
content_share:
  enabled: false
```

### Azione

```
/share tests/content-share/fixtures/small.html --dry-run
```

### Expected

La skill si arresta in Fase 0, step 2, con messaggio:

```
content_share non abilitato. Imposta `content_share.enabled: true` in
factory.config.yaml e compila source_repo_slug, source_repo. Vedi
wiki/runbooks/content-share-setup.md
```

Nessuna variabile d'ambiente letta. Nessuna chiamata API eseguita.

### Pass criterion

Output contiene la stringa `"content_share non abilitato"` (o equivalente
semantico prodotto dalla skill in Fase 0, step 2). STOP confermato dall'assenza
di output successivo (Fase 1..4 non avviate).

### Verifica negativa

Se il flag venisse ignorato e la skill proseguisse oltre Fase 0 step 2, il test
fallisce — indica una regressione su R.CS2.

---

## Scenario 2 — Fase 0 fail-loud: pat_env vuoto

**Invariante verificata**: fail-loud su variabile d'ambiente mancante (Fase 0,
step 3).

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

Assicurarsi che la variabile d'ambiente `SOLI_FRAMES_PAT` NON sia impostata
nella sessione corrente:

```bash
unset SOLI_FRAMES_PAT
```

### Azione

```
/share tests/content-share/fixtures/small.html --dry-run
```

### Expected

La skill si arresta in Fase 0, step 3, con messaggio fail-loud:

```
SOLI_FRAMES_PAT non configurato. Crea un PAT fine-grained con scope
Contents:write su soli92/soli-frames e aggiungilo come secret. Vedi
wiki/runbooks/content-share-setup.md
```

Le fasi successive (step 4..8, Fase 1..4) non vengono avviate.

### Pass criterion

Output contiene entrambe le stringhe `"SOLI_FRAMES_PAT"` e
`"non configurato"`. STOP confermato dall'assenza di output Fase 1+.

### Verifica negativa

Se la skill proseguisse oltre Fase 0 step 3 con `SOLI_FRAMES_PAT` assente,
il test fallisce — regressione sul gate di fail-loud delle credenziali.

---

## Scenario 3 — Percorso felice dry-run: EGRESS_PASS + gate prompt + NO dispatch

**Invarianti verificate**: R.CS4 (EGRESS_PASS su fixture custom senza dati
sensibili), R.CS3 dry-run bypass gate, dimensione < 80 KB.

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
    analytics_report: false
```

Impostare le variabili d'ambiente (valori dummy — sufficienti per dry-run,
nessuna chiamata API eseguita):

```bash
export SOLI_FRAMES_PAT=ghp_DUMMY_dry_run_value_000000000000
export SOLI_FRAMES_DISPATCH_SECRET=secret-dummy-dry-run
```

### Azione

```
/share tests/content-share/fixtures/small.html --slug=test-smoke --title="Test Smoke" --dry-run
```

### Expected

**Fase 0**:
- Egress classification: `custom` abilitata, nessun dato sensibile rilevato
- Dimensione HTML decoded: ~4 KB (ampiamente sotto 80 KB e 100 KB)
- Output stampato: `EGRESS_PASS`

**Fase 1**:
- Slug composto: `soli-factory-test-smoke`
- Title: `Test Smoke`
- Payload JSON costruito (non inviato)

**Fase 2**:
- Validazione slug regex R.CS1: `^[a-z][a-z0-9-]{1,78}[a-z0-9]$` — conforme
- Validazione source_repo formato org/repo — conforme
- Dimensione payload < 10 MB — conforme

**Fase 3** (gate umano dry-run):
- Riepilogo visibile con:
  - `Slug: soli-factory-test-smoke`
  - `Title: Test Smoke`
  - `Size: ~4 KB`
  - URL target `https://soli-frames.vercel.app/viewer/`
  - `Publish: draft`
  - `EGRESS_PASS`
- Messaggio terminale: `"DRY RUN completato. Nessun dispatch eseguito."`

**Fase 4**: NON avviata. Nessuna chiamata `gh api` eseguita.

### Pass criterion

Output contiene tutte e tre le stringhe:
1. `"EGRESS_PASS"`
2. `"DRY RUN"` (o `"DRY RUN completato"`)
3. `"soli-factory-test-smoke"` (slug composto corretto)

Output NON contiene traccia di `gh api` invocato o risposta HTTP (204/401/404).

### Verifica negativa

Se la skill eseguisse Fase 4 (dispatch) durante `--dry-run`, il test fallisce —
regressione critica sul gate R.CS3. La presenza di `204` o di un URL di Actions
GitHub nell'output indica dispatch involontario.

---

## Note di esecuzione

- I test sono eseguibili manualmente in qualsiasi ordine indipendente.
- Lo Scenario 1 non richiede config aggiuntiva (il default `enabled: false` e'
  sufficiente).
- Lo Scenario 2 richiede `enabled: true` ma variabile env mancante.
- Lo Scenario 3 richiede env vars dummy: non causano chiamate API reali grazie a
  `--dry-run`.
- La fixture `small.html` (4 KB) non contiene dati sensibili, actor_id o
  rate_card: EGRESS_PASS garantito per categoria `custom`.
- Per eseguire i test in serie, ripristinare `factory.config.yaml` tra uno
  scenario e l'altro (o usare un file config di test dedicato).
