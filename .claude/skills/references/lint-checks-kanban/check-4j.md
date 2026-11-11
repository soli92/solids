---
skill: lint-checks
leaf_of: lint-checks-kanban.md
section: "kanban"
description: "Check 4j: TSK aperti degli agenti senza un repository risolvibile"
---

> Eseguito da `tools/lint/run-deterministic.py` (registrato in `CHECKS`).

# 4j — Repository risolvibile sui TSK aperti degli agenti (default off)

**Eseguibile, non interpretato.**

```bash
python3 tools/lint/check_target_tsk.py --root .
```

Opzioni: `--json`, `--strict` (exit 1 con almeno un ERROR), `--severita warning|error` (misura a
regola spenta).

**Cosa controlla.** PATTERN-integration cita un «Check 4j» sul drift fra `target:` e `code_paths`. Qui
è implementato con la risoluzione dello Step 2-bis del dev-protocol (`fase-0-gate-steps.md`). Per ogni TSK con `consumer: agent`, status `todo`,
`in_progress`, `review` o `blocked`, e layer instradato ad `agent` in `routing:`, il repository si risolve
in quest'ordine:

1. `target:`: nome di una voce di `code_paths`. Se la voce dichiara `layers:`, deve elencare il layer;
2. `code_path:`: `.` o un percorso della factory, o il percorso di una voce di `code_paths`; con
   `tsk_target_gitmodules: true` un percorso sotto `code_repos/` deve essere anche un repository di
   `.gitmodules` (o una sua sottocartella);
3. senza i due campi: le voci di `code_paths` con il layer in `layers:`. Vale solo se ce n'è una.

**Configurazione** (blocco `lint.kanban` di `factory.config.yaml`; default spento):

| Chiave | Valori | Significato |
|---|---|---|
| `tsk_target` | `off` / `warning` / `error` | severità dei finding |
| `tsk_target_gitmodules` | `false` (default) / `true` | richiede che un `code_path` sotto `code_repos/` sia in `.gitmodules` (opzionale) |

**Codici.**

| Codice | Quando |
|---|---|
| `target-sconosciuto` | `target:` non corrisponde a nessuna voce di `code_paths` |
| `target-layer` | la voce di `target:` dichiara `layers:` senza il layer del TSK |
| `code-path-assoluto` | `code_path:` assoluto |
| `code-path-senza-repo` | `code_path:` sotto `code_repos/` non dichiarato (solo con `tsk_target_gitmodules: true`) |
| `senza-repo` | né `target:` né `code_path:`, e nessuna voce per il layer |
| `target-ambiguo` | né `target:` né `code_path:`, e più voci per il layer |

**Correzione.** Si aggiunge `code_path:` al TSK, oppure `target:` se il layer ha più voci in
`code_paths`. Un TSK che non scrive codice (per esempio un monitoraggio) non dovrebbe avere
`consumer: agent` con un layer di codice.

Test: `tools/tests/test_target_tsk.py`.
