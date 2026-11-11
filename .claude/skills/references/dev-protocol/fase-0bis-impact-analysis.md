# Fase 0.bis — Impact Pre-Analysis (L3, opt-in, R.CI4)

**Ambito**: dettaglio della Fase 0.bis di `dev-protocol.md` per l'analisi dell'impatto
via graphify (L3, opt-in). Leggere obbligatoriamente prima di eseguire questa fase.
Se il gate `code_intelligence.l3_impact.enabled` è `false` → skip silenzioso, questa
foglia non va letta.

---

**Gate**: esegui solo se `code_intelligence.l3_impact.enabled: true` in `factory.config.yaml`.
Se disabled o chiave assente → **skip silenzioso**, procedi direttamente a Fase 1.

## Prerequisiti (R.CI2 — SKIP non STOP)

- `which graphify` → se assente: log `[L3-SKIP] graphify not installed — see wiki/runbooks/code-intelligence.md` e procedi
- Graph costruito: `.graphify-state/code_paths/<slug>/graph.json`
  → se assente: log `[L3-SKIP] graph not built — run /graphify-sync <target> first` e procedi

## Esecuzione (R.CI4 — analysis-only, zero scrittura file in questa fase)

1. Dal frontmatter del TSK, estrai i simboli/moduli principali da modificare
2. Per ogni simbolo: `graphify affected "<symbol>" --format=json --depth=2`
3. Aggrega come `blast_radius`: `{symbol, affected_files, affected_symbols, depth}`

## Output atteso (solo in memoria dell'agente — non scrivere file)

```
[L3] Impact analysis: auth_middleware
  → affected files  (depth 1): middleware/base.py, views/api.py (+3 altri)
  → affected symbols (depth 2): APIView.dispatch, require_auth
  → blast_radius: 7 files, 12 symbols — MEDIUM
```

## Livelli blast_radius

- LOW ≤3 file → procedi
- MEDIUM 4-10 → segnala in TSK Analysis
- HIGH >10 → `[L3-WARN]` + verifica copertura TSK o esplicitazione out-of-scope

## Scope extension check

Se blast_radius include file/moduli fuori scope TSK → segnala
"scope extension rilevata: <lista file>" nella sezione Analysis e attendi conferma umana.

## Note

Step read-only (no modifica al graph).
Se `auto_run_on_dev: false` (default): eseguito solo su richiesta esplicita.
Se `auto_run_on_dev: true`: eseguito automaticamente.
