# Comando: /repo-sync

> Equivalente Cursor del comando Claude Code `/repo-sync` (`.claude/commands/repo-sync.md`).
> Procedura: vedi [repo-extraction-protocol](mdc:.cursor/rules/skills/repo-extraction-protocol.mdc).

**Sintassi**:
```
/repo-sync <path>              → estrazione standard (5 fasi, gate Fase 1 + Fase 4)
/repo-sync <path> --no-tree   → senza companion tree
/repo-sync <path> --depth=4   → tree con depth custom (default 3)
/repo-sync show                → mostra ultime estrazioni dal manifest
/repo-sync help                → help inline + esempi
```

## Comportamento

### `/repo-sync <path>`

Esegue [repo-extraction-protocol](mdc:.cursor/rules/skills/repo-extraction-protocol.mdc) 5 fasi:
- Fase 0 — Bootstrap (valida path, calcola slug, dedup manifest)
- Fase 1 — Piano (STOP, attende conferma)
- Fase 2 — Discovery (git metadata + stack detection + struttura)
- Fase 3 — Sampling mirato (README, manifest, entrypoint, API, vincoli normativi; secret redacted)
- Fase 4 — Proposta (STOP, attende conferma)
- Fase 5 — Scrittura (`raw/<data>-repo-<slug>.md` + opzionale companion + manifest)

Output: path artefatto, statistiche, prossimo step («Invoca `wiki-keeper` per l'ingest»).

### `/repo-sync show`

Read-only su `raw/.extraction-manifest.json`, filtra entries con `source: repo`.

## Vincoli

- **Read-only verso la sorgente** (§7 r.17): mai modificare il repo scansionato.
- Mai chiamate network: la skill è offline.
- Secret hygiene: secret rilevati → redacted dal `.md` + contati in metadata.

## Limitazioni Cursor

- Usa `@<path>` mention per includere file del repo sorgente nel contesto.
- Le fasi vanno eseguite sequenzialmente.
- Per repo remoti: clone locale prima e punta `/repo-sync` al clone.
