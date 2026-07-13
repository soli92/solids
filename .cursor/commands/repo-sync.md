---
description: Estrae un documento di specifiche markdown da un repo locale esistente (PATTERN §16 + §2, v2.12). Read-only verso la sorgente. Output in raw/, da ingestare con wiki-keeper per kick-off pipeline.
argument-hint: <path-locale> [--no-tree] [--depth=N]
allowed-tools: Read, Write, Edit, Bash, Glob
---

Sintassi:

```
/repo-sync <path>              → estrazione standard (5 fasi, gate Fase 1 + Fase 4)
/repo-sync <path> --no-tree    → niente companion tree (solo .md primario)
/repo-sync <path> --depth=4    → companion tree con depth custom (default 3)
/repo-sync show                → mostra ultime estrazioni dal manifest
/repo-sync help                → mostra help inline + esempi
```

## Comportamento per sub-comando

### `/repo-sync <path>`

1. Read `factory.config.yaml` (verifica `pattern_version >= 2.12`, presenza
   dell'agente [repo-sync](mdc:.cursor/rules/repo-sync.mdc)).
2. Invoca l'agente [repo-sync](mdc:.cursor/rules/repo-sync.mdc) passando:
   - `source_path: <path>`
   - `companion_tree: <true|false>` (default `true`; `--no-tree` lo forza `false`)
   - `tree_depth: <N>` (default `3`)
3. L'agent esegue la skill [repo-extraction-protocol](mdc:.cursor/skills/repo-extraction-protocol/SKILL.md) 5 fasi:
   - Fase 0 — Bootstrap (valida path, calcola slug, dedup manifest).
   - Fase 1 — Piano (STOP, attende conferma).
   - Fase 2 — Discovery (git metadata + stack detection + struttura).
   - Fase 3 — Sampling mirato (README, manifest, entrypoint, API, vincoli normativi,
     secret redacted).
   - Fase 4 — Proposta (STOP, attende conferma).
   - Fase 5 — Scrittura (`raw/<data>-repo-<slug>.md` + opzionale companion + manifest).
4. Mostra in chat al termine: path artefatto, statistiche, prossimo step
   («Invoca `wiki-keeper` per l'ingest»).

### `/repo-sync show`

Read-only su `raw/.extraction-manifest.json`, filtra entries con `source: repo`, mostra:

```
REPO EXTRACTIONS (lista da raw/.extraction-manifest.json)
==========================================================
<key>                       <data>    <stack>           <files>  <status>
<YYYY-MM-DD>-repo-<slug-1>  2026-...  python/fastapi    23/127    success
<YYYY-MM-DD>-repo-<slug-2>  2026-...  typescript/react  18/89     partial
```

Nessuna scrittura.

### `/repo-sync help`

Stampa help testuale inline + 3 esempi:

```
ESEMPI

# Estrazione di un repo locale (default: companion tree on, depth 3)
/repo-sync /Users/me/Repos/customer-portal-api/

# Solo documento primario, no companion tree
/repo-sync ./local-clone/ --no-tree

# Tree profondo per repo grandi con layout complesso
/repo-sync /Users/me/monorepo/ --depth=4

DOPO L'ESTRAZIONE
- Invoca wiki-keeper per l'ingest L1→L2:
    Agent(subagent_type=wiki-keeper, prompt="Ingest raw/<file-appena-creato>.md")
- L'ingest produrrà pagine wiki + aprirà gap mirati.
- Poi product-manager per il planning iniziale.
```

## Prerequisiti

- Path locale valido (assoluto o relativo a cwd).
- Read access su tutto il contenuto del repo.
- **Mai write access** richiesto sulla sorgente — la skill è read-only verso il repo
  scansionato (§7 r.17).
- Agente [repo-sync](mdc:.cursor/rules/repo-sync.mdc) presente.
- `raw/` esistente nella factory che invoca.

## Output (artefatti L1)

- `raw/<YYYY-MM-DD>-repo-<slug>.md` (primario, 5-15 KB target)
- `raw/images/<YYYY-MM-DD>-repo-<slug>-tree.md` (opzionale companion)
- `raw/.extraction-manifest.json` (entry appended con `source: repo`)

## Idempotenza

Re-estrazione sullo stesso `<path>` con la stessa data → chiede conferma; se
confermata, scrive `## Aggiornamenti (vYYYY-MM-DD)` in fondo al documento esistente
invece di overwrite completo (analogo §7 r.7).

Re-estrazione con data diversa (giorno successivo) → produce un nuovo file
`<YYYY-MM-DD>-repo-<slug>.md`; il vecchio resta per audit.

## Vincoli (PATTERN §7 r.1 + §7 r.17 + §16)

- **L1 read-only** per la factory (§7 r.1): solo `repo-sync` scrive in `raw/*-repo-*.md`.
- **Sync read-only verso la sorgente** (§7 r.17): mai modificare il repo scansionato.
  In particolare: mai aggiungere `factory.config.yaml`, `CLAUDE.md`, adapter, o
  qualsiasi file infrastrutturale al repo esterno. Una factory che ingerisce sé stessa
  via repo-sync (reflective) resta legittima — la regola distingue *sorgente* da *output*.
- **Mai chiamate network**: la skill è offline. Per repo remoti, clone locale prima e
  poi punta `/repo-sync` al clone.
- **Secret hygiene**: secret rilevati durante il sampling sono **redacted** dal `.md`
  prodotto + contati in `extraction_metadata.secrets_redacted`. Mai trascritti.

## Bootstrap integration (v2.12)

Quando il meta-prompt `factory-bootstrap` raccoglie l'input «wiki feeding source =
existing-repo», il bootstrap stesso (dopo aver scaffoldato la factory) invoca
automaticamente questo comando sul path scelto dall'utente. Il documento prodotto
finisce in `raw/` e il bootstrap suggerisce in chat di invocare `wiki-keeper` per
l'ingest L1→L2 — primo passo della pipeline standard.

Vedi la skill [repo-extraction-protocol](mdc:.cursor/skills/repo-extraction-protocol/SKILL.md) per la procedura completa, l'agente
[repo-sync](mdc:.cursor/rules/repo-sync.mdc) per il contratto, PATTERN §16 «Sync adapters» per la cornice generale.
