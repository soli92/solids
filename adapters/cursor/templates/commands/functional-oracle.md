# Comando: /functional-oracle

> Equivalente Cursor del comando Claude Code `/functional-oracle` (`.claude/commands/functional-oracle.md`).
> EP-018, opt-in `fe_correctness.functional_oracle.enabled`.

**Sintassi**:
```
/functional-oracle <TSK-id|app>            → functional oracle standard
/functional-oracle <TSK-id|app> --dry-run  → spec risolta + schema validata senza eseguire scenario
/functional-oracle <TSK-id|app> --ephemeral  → run standard, nessuna scrittura in code_quality/reports/
```

> **Gate**: `fe_correctness.functional_oracle.enabled: true`. Eccezione: invocazione esplicita bypassa il gate (esecuzione esplicita = volonta' esplicita, ADR-067).

## `<target>` — 2 forme

| Forma | Esempio | Risoluzione |
|---|---|---|
| **TSK-id** | `/functional-oracle TSK-042` | Legge `functional_acceptance_spec:` dal frontmatter TSK |
| **app** | `/functional-oracle emulator-gba` | Risolve `code_quality/acceptance/<app>.acceptance.yaml` |

## Comportamento

1. Risolvi target. Se TSK-id: glob `management/kanban/**/TSK-<id>.md`, leggi `functional_acceptance_spec:`.
2. Discovery esecutore: preferenza `qa-dev`, fallback `fe-dev`. Se nessuno → ABORT fail-loud.
3. Esegue `functional-oracle-protocol` (Bootstrap → Preflight → Serve App → Drive Scenario → Valuta asserzioni → Critic Advisory → Verdict + Report).
4. Aggiorna `functional_status:` nel frontmatter TSK (solo senza `--dry-run`/`--ephemeral`).

## Verdict

Basato esclusivamente su asserzioni binarie (ADR-067). Nessun LLM nel path di pass/fail:
- `pass`: tutte le asserzioni `blocking` = true
- `conditional`: asserzione `advisory` fallita (non blocking)
- `reject`: asserzione `blocking` fallita — il LLM non puo' promuovere

## Storage

- Con TSK-id: `code_quality/reports/<TSK-id>-functional-iter-<N>.{json,md}`
- Con app: `code_quality/reports/<app>-functional-iter-<N>.{json,md}`
- `--ephemeral`: nessuna scrittura in `code_quality/reports/`

## Vincoli

- Single-writer: solo `functional-oracle-protocol` scrive `functional_status:`.
- Verdict deterministico: critic LLM e' advisory only.

## Limitazioni Cursor

- Playwright deve essere installato e il browser configurato per l'esecuzione via terminal Cursor.
- Node.js + Playwright sono prerequisiti obbligatori.
- Lo scenario va eseguito dal terminal integrato.
