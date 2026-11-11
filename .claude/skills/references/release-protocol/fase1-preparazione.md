# Fase 1 — Preparazione: dettaglio step 1.1–1.5

**Ambito**: dettaglio dei 5 step di preparazione artefatti release di `release-protocol.md`.
Leggere obbligatoriamente all'ingresso della Fase 1 — se il file manca, STOP e segnala.

> Scopo: aggiornare gli artefatti di release (CHANGELOG, config, meta-prompts, CLAUDE.md)
> prima della validazione. Idempotenza: verifica che ogni artefatto non sia già aggiornato.

---

## Step 1.1 — CHANGELOG.md

```
Azione:
  - Apri CHANGELOG.md.
  - Verifica se esiste già la sezione `## v<version>` (o `## v<X.Y.Z>`).
  - SE già presente → log "CHANGELOG.md: sezione v<version> già presente. Skip." e prosegui.
  - SE assente → aggiungi in testa (dopo header principale) la sezione:

    ## v<version>
    <!-- data: <YYYY-MM-DD> -->

    ### Nuovi EP / feature
    - <EP-NNN> <titolo> — <descrizione breve>

    ### US completate
    - US-NNN <titolo>

    ### Bugfix / tech-debt
    - <descrizione>

    ### Dipendenze e breaking changes
    - <nessuna | descrizione>

    ## Validation evidence (v<version>)
    <!-- sezione compilata dalla release-validation-gate in Fase 2 -->

  Nota: la sezione `## Validation evidence` è richiesta dalla skill `release-validation-gate`
  (Step 5 CHANGELOG validation, ADR-034 §A). Anche se lasciata come placeholder in Fase 1,
  deve essere compilata prima di invocare la validation gate (Fase 2).
```

## Step 1.2 — pattern_version in factory.config.yaml

```
Azione:
  - Leggi factory.config.yaml.pattern_version.
  - SE già impostato a v<version> → log "pattern_version già corretto. Skip." e prosegui.
  - SE assente o impostato a versione diversa:
    - Aggiorna il campo: `pattern_version: v<version>`
    - Log: "factory.config.yaml: pattern_version aggiornato a v<version>."

Nota: SSOT — il campo pattern_version deve essere coerente con il tag che verrà creato.
```

## Step 1.3 — Entry meta-prompts/

```
Azione:
  - Verifica se esiste la directory meta-prompts/v<major>-<minor>/ (es. meta-prompts/v2-40/).
  - SE esiste già → log "meta-prompts/v<X>-<Y>/ già presente. Skip." e prosegui.
  - SE assente:
    - Identifica la directory della versione precedente (ultima presente in meta-prompts/).
    - Crea meta-prompts/v<X>-<Y>/factory-bootstrap.md con il contenuto:
        extends: ../v<prev-X>-<prev-Y>/factory-bootstrap.md
        ## Delta v<version>
        <!-- Lista dei cambiamenti rispetto alla versione precedente: -->
        - EP-NNN <titolo>: <breve descrizione impatto sul bootstrap>
        [Aggiungere una riga per ogni EP incluso in questa release]
    - Log: "meta-prompts/v<X>-<Y>/factory-bootstrap.md creato."

Nota: il file usa il pattern `extends:` della catena delta (CLAUDE.md §Meta-prompt versioning).
```

## Step 1.4 — CLAUDE.md heading + meta-prompts/README.md §Available versions

```
[^src: TSK-651 (commit 5f77b46) ha rimosso il corpo §Meta-prompt versioning da CLAUDE.md.
 La lista delle versioni vive ora in meta-prompts/README.md §Available versions.
 Rimane in CLAUDE.md solo l'heading, che Lint Check 4am legge via regex per il cross-check
 con factory.config.yaml#pattern_version. L'heading si aggiorna in-place; non si aggiungono
 righe sotto (l'asserzione anti-ricrescita US-276 AC5 sarebbe rossa).]

Azione A — Heading CLAUDE.md (sostituzione in-place, nessuna riga aggiunta):
  - Apri CLAUDE.md.
  - Trova la riga `## Meta-prompt versioning (v<prev> — corrente)`.
  - Verifica se già mostra v<version>.
  - SE già aggiornata → log "CLAUDE.md: heading già mostra v<version>. Skip." e prosegui.
  - SE non aggiornata:
    - Sostituisci in-place: `## Meta-prompt versioning (v<prev> — corrente)` →
      `## Meta-prompt versioning (v<version> — corrente)`
    - Non aggiungere righe sotto l'heading.
    - Log: "CLAUDE.md: heading §Meta-prompt versioning aggiornato a v<version>."

Azione B — meta-prompts/README.md §Available versions:
  - Apri meta-prompts/README.md, sezione `## Available versions`.
  - Verifica se esiste già la riga con status **current** per v<version>.
  - SE già presente → log "meta-prompts/README.md: v<version> già corrente. Skip." e prosegui.
  - SE assente:
    - Nella riga attualmente marcata **current**, cambia `current` → `previous`.
    - Inserisci in testa alla tabella (dopo la riga header) la nuova riga:
        | **v<version>** | **current** | [`v<X>-<Y>/`](v<X>-<Y>/factory-bootstrap.md) | <descrizione delta EP inclusi> |
    - Log: "meta-prompts/README.md: riga v<version> aggiunta come current."
```

## Step 1.5 — Checkpoint Fase 1

```
Al termine degli step 1.1..1.4:
  - Verifica che tutti e 4 gli artefatti siano aggiornati (o già corretti).
  - Log complessivo:
    "Fase 1 completata. Artefatti verificati/aggiornati:
     ✓ CHANGELOG.md (sezione v<version>)
     ✓ factory.config.yaml (pattern_version: v<version>)
     ✓ meta-prompts/v<X>-<Y>/factory-bootstrap.md
     ✓ CLAUDE.md (heading §Meta-prompt versioning aggiornato in-place)
     ✓ meta-prompts/README.md (§Available versions: riga v<version> aggiunta)"
  - Procedi a Fase 2.
```
