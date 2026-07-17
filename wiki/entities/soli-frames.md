---
id: soli-frames
type: entity
title: "soli-frames — Piattaforma hosting artefatti HTML"
status: stable
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/bonifica-repo-2026-07-17.txt §Sezione 6 — v2.33 gap closure"
  - "wiki/runbooks/content-share-setup.md"
pattern_section: "§32"
tags: [soli-frames, content-share, ep-048, hosting, artefatti]
---

# soli-frames

Piattaforma di hosting per artefatti HTML condivisi dalla factory tramite il
Content Share Consumer Layer (EP-048, PATTERN §32).[^src: docs/raw/bonifica-repo-2026-07-17.txt §Sezione 6 — v2.33 gap closure]

## Descrizione

`soli-frames` è il repository hub `soli92/soli-frames` che riceve e pubblica artefatti
HTML prodotti dalle factory derivate (prototipi, report analytics, artefatti custom)
tramite il meccanismo di dispatch fire-and-forget definito in PATTERN §32 (EP-048).

## Integrazione con le factory

Le factory derivate pubblicano artefatti via il comando `/share <html-path>`.
Il dispatch è fire-and-forget verso l'API GitHub Repository Dispatch di `soli92/soli-frames`.

Il flusso è:
1. `/share` classifica l'artefatto (egress class, size check, slug validation)
2. Gate umano R.CS3: conferma esplicita richiesta prima del dispatch
3. POST a `repos/soli92/soli-frames/dispatches` autenticata con `SOLI_FRAMES_PAT`
4. soli-frames riceve il payload, verifica `SOLI_FRAMES_DISPATCH_SECRET`, avvia pipeline GHA

## Configurazione nelle factory

La capability è opt-in. Richiede nel `factory.config.yaml` del progetto:

```yaml
content_share:
  enabled: true
  target_repo: "soli92/soli-frames"
  source_repo_slug: "<repo-slug>"
  source_repo: "soli92/<repo>"
  pat_env: SOLI_FRAMES_PAT
  secret_env: SOLI_FRAMES_DISPATCH_SECRET
```

Per il setup completo: [[content-share-setup]] (`wiki/runbooks/content-share-setup.md`).

## Invarianti (R.CS1..R.CS4)

| Invariante | Descrizione |
|------------|-------------|
| R.CS1 | Slug obbligatorio nel formato `{source_repo_slug}-{content_slug}` |
| R.CS2 | Size limit: 100 KB (hard cap, default fino a US-024) |
| R.CS3 | Gate umano: conferma esplicita prima di ogni dispatch reale |
| R.CS4 | Dispatch fire-and-forget: la factory non attende la pipeline GHA |

## Stato della factory corrente (solids)

Per il progetto `@soli92/solids` la capability è attualmente **disabilitata**
(`content_share.enabled: false` in `factory.config.yaml`). Attivare seguendo il
runbook [[content-share-setup]].

## Riferimenti

- PATTERN.md §32 — architettura dispatch, invarianti R.CS1..R.CS4
- [[content-share-setup]] — `wiki/runbooks/content-share-setup.md`
- Incident [[bonifica-2026-07-17]] — §Gap 4 (creazione originale di questa pagina)
