---
name: share
description: "Pubblica un artefatto HTML su soli-frames tramite GitHub repository_dispatch. Invoca content-share-protocol (5 fasi). Gated su content_share.enabled (R.CS2 default off). Supporta --dry-run (Fasi 0-3 incluso gate umano, bypass Fase 4)."
argument-hint: "<html-path> [--slug=<slug>] [--title=<titolo>] [--dry-run]"
allowed-tools: Read, Bash
---

# /share

Argomenti utente: `$ARGUMENTS`

Pubblica un artefatto HTML su soli-frames tramite GitHub `repository_dispatch`.
Il contenuto e' inviato come draft — non e' visibile su soli-frames finche' la PR
generata non viene mergiata (`publish_default: draft`).

Il gate umano in Fase 3 e' obbligatorio prima di qualsiasi dispatch (R.CS3):
il dispatch e' un'azione outward non reversibile.

---

## Sintassi

```
/share <html-path> [--slug=<slug>] [--title=<titolo>] [--dry-run]
```

| Argomento | Tipo | Default | Descrizione |
|---|---|---|---|
| `<html-path>` | obbligatorio | — | Path al file HTML da pubblicare |
| `--slug=<slug>` | opzionale | `{source_repo_slug}-{basename}` | Suffisso content-slug; se assente, auto-derivato da basename del file (senza `.html`) in kebab-case |
| `--title=<titolo>` | opzionale | estratto da `<title>` HTML | Titolo leggibile del contenuto; fallback a slug se `<title>` assente |
| `--dry-run` | flag | off | Esegue Fasi 0-3 incluso gate umano, bypassa Fase 4 (dispatch) |

---

## Procedura

### Step 0 — Gate `content_share.enabled` (precondizione assoluta)

Prima di qualsiasi altra azione, leggi `factory.config.yaml` e controlla il flag:

```
SE factory.config.yaml.content_share.enabled == false (default R.CS2):
  STOP — non invocare il protocollo, nessun side-effect.
  Emetti in chat:
    "[/share] Layer spento: content_share.enabled: false (R.CS2 default off).
     Per abilitare il Content Share Consumer Layer:
       1. Aggiungi / aggiorna factory.config.yaml:
            content_share:
              enabled: true
              source_repo_slug: <slug-repo-corrente>
              source_repo: <org>/<repo>
              publish_default: draft
       2. Configura i secret SOLI_FRAMES_PAT e SOLI_FRAMES_DISPATCH_SECRET.
       3. Vedi wiki/runbooks/content-share-setup.md per la guida completa.
       4. Ri-lancia /share <html-path>."
```

Non emettere un STOP silenzioso: l'errore deve essere esplicito e orientare l'azione.

Se `content_share.enabled: true`, prosegui.

### Step 1 — Parse argomenti

Dall'input `$ARGUMENTS` estrai:

- `html_path` — il primo argomento non-flag (path al file HTML)
- `slug_override` — valore di `--slug` se presente, altrimenti `null`
- `title_override` — valore di `--title` se presente, altrimenti `null`
- `dry_run` — `true` se `--dry-run` e' presente, altrimenti `false`

Se nessun argomento e' stato fornito (stringa vuota):

```
[/share] Argomento obbligatorio mancante: <html-path>.

Utilizzo: /share <html-path> [--slug=<slug>] [--title=<titolo>] [--dry-run]

Esempi:
  /share output/prototype-sprint-5.html --slug=sprint-5-prototype --title="Sprint 5 Prototype"
  /share output/cost-report.html --dry-run
  /share reports/2026-07-17-analytics.html --title="Analytics Report 2026-07-17"

Fornisci il path a un file HTML esistente da pubblicare su soli-frames.
```

### Step 2 — Verifica esistenza `html-path`

Verifica che il file esista (fail-loud se assente):

```
SE <html-path> non esiste sul filesystem:
  STOP — emetti in chat:
    "[/share] File non trovato: <html-path>
     Verificare che il path sia corretto e il file sia stato generato.
     - Per prototipi EP-035: usare il path output di prototype-generator.
     - Per report analytics: verificare il path generato dallo strumento."
```

### Step 3 — Invoca `content-share-protocol`

Con i parametri risolti, esegui il protocollo `content-share-protocol` sequenzialmente:

**Parametri passati alla skill:**

```yaml
html_path: <html_path>          # path assoluto o relativo al file HTML
slug_override: <slug | null>    # null = auto-derivato da basename
title_override: <title | null>  # null = estratto da <title> HTML
dry_run: <true | false>
```

La skill esegue le 5 fasi in sequenza:

| Fase | Nome | Azione |
|---|---|---|
| 0 | Pre-flight + Egress Check | Check `content_share.enabled` + verifica secret + classificazione R.CS4 + check dimensione |
| 1 | Build Payload | Compose slug + valida R.CS1 + estrae title + encode base64 + costruisce JSON annidato |
| 2 | Validate | Doppia verifica slug regex R.CS1 + check formato `source_repo` + check dimensione payload |
| 3 | Gate Umano | Riepilogo dispatch obbligatorio (R.CS3) — `--dry-run` STOP qui con payload stampato |
| 4 | Dispatch + Log | Dispatch via gh CLI + response mapping + log entry in `wiki/log.md` |

Con `--dry-run`: la skill esegue Fasi 0-3 incluso il gate umano interattivo, poi
stampa il payload completo e si ferma senza dispatch (Fase 4 bypassata).

### Step 4 — Output finale

Dopo il completamento del protocollo, riporta in chat:

**Esito positivo (dispatch eseguito, HTTP 204):**

```
/share <html-path> — completato
===============================
Fase 0 — Pre-flight:  EGRESS_PASS | EGRESS_WARN <categoria>
Fase 1 — Payload:     slug: <slug-completo> · title: <title> · size: X KB
Fase 2 — Validate:    OK
Fase 3 — Gate:        confermato
Fase 4 — Dispatch:    204 OK — pending merge PR su soli-frames

Il contenuto sara' disponibile dopo il merge della PR su:
https://github.com/soli92/soli-frames/actions
```

**Esito dry-run:**

```
/share <html-path> --dry-run — completato
==========================================
Fase 0 — Pre-flight:  EGRESS_PASS | EGRESS_WARN <categoria>
Fase 1 — Payload:     slug: <slug-completo> · title: <title> · size: X KB
Fase 2 — Validate:    OK
Fase 3 — Gate:        (dry-run — nessun dispatch eseguito)

DRY RUN completato. Nessun dispatch eseguito.
Per pubblicare: /share <html-path> [stessi flag senza --dry-run]
```

**Esito con STOP (errore o annullamento):**

```
/share <html-path> — STOP
==========================
Fase <N> — <motivo del blocco>
Azione richiesta: <descrizione azione umana>
```

---

## Esempi d'uso

```bash
# Pubblica un prototipo generato da EP-035
/share output/prototype-sprint-5.html --slug=sprint-5-prototype --title="Sprint 5 Prototype"

# Pubblica report analytics con dry-run per ispezionare il payload prima del dispatch
/share output/cost-report.html --dry-run

# Pubblica con slug auto-derivato dal filename e titolo esplicito
/share reports/2026-07-17-analytics.html --title="Analytics Report 2026-07-17"

# Pubblica con slug e title auto-derivati (basename + <title> HTML)
/share output/factory-guide-sprint-49.html
```

---

## Note operative

- **Nessun hook automatico**: il comando e' sempre manuale (deliberazione TR A11).
  Nessun agente lancia `/share` in autonomia.
- **Per prototipi generati da EP-035**: usare il path di output di `prototype-generator`
  (tipicamente `output/<nome>.html`).
- **Per report analytics**: verificare R.CS4 egress classification prima del dispatch.
  Artefatti `analytics_report` con dati per-attore o rate card → EGRESS_BLOCK. Usare
  `--dry-run` per ispezionare la classificazione senza dispatch.
- **`publish_default: draft`**: il contenuto non e' visibile su soli-frames finche'
  la PR generata dal workflow non viene mergiata esplicitamente.
- **Dimensione HTML**: limite hard 100 KB decoded (STOP), warning a 80 KB.
  Per artefatti grandi: rimuovere script inline, immagini base64 embedded.

---

## Prerequisiti

- `content_share.enabled: true` in `factory.config.yaml` (gate principale, Step 0).
- Blocco `content_share:` completo in `factory.config.yaml`:
  `source_repo_slug`, `source_repo` (formato `org/repo`), `publish_default: draft`.
- Secret `SOLI_FRAMES_PAT` configurato (PAT fine-grained, scope `Contents:write`
  su `soli92/soli-frames`).
- Secret `SOLI_FRAMES_DISPATCH_SECRET` configurato.
- `gh` CLI disponibile e autenticato (`gh auth status`).

Vedi `wiki/runbooks/content-share-setup.md` per la guida completa alla configurazione.

---

## Cross-link

- **Skill invocata**: `.claude/skills/content-share-protocol.md` (TSK-400)
- **Setup prerequisiti**: `wiki/runbooks/content-share-setup.md` (TSK-402)
- **Hub destinazione**: `wiki/entities/soli-frames.md`
- **Configurazione**: `factory.config.yaml` blocco `content_share:` (TSK-398)
- **PATTERN §32** — Content Share Consumer Layer (EP-048)
