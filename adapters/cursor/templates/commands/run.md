# /run — Cursor adapter

Sintassi:
```
/run
```

Equivalente Claude Code: `.claude/commands/run.md`.

## Comportamento

Invoca l'orchestrator (rule [`orchestrator.mdc`](mdc:.cursor/rules/orchestrator.mdc)):
1. Esegue `state-scan` (filesystem + wiki/log.md + memory/episodic/ ultima entry).
2. Mostra in chat la dashboard:
   ```
   FACTORY STATE — <progetto>
   ==========================
   Pattern: v2.42
   Topology: <topology>
   Adapter attivi: <lista da factory.config.yaml.adapters>
   Sprint corrente: <NN>
   TSK status: <todo: N | in-progress: M | done: K>
   Review status (CQRL v2.12 se on): <pending: P | passed: Q | reject: R>
   Wiki: <N pagine concepts | M entities | K syntheses>
   Gap aperti: <N>
   Q aperti: <N>
   Ultimo ingest: <data>
   Ultimo /run: <data>
   ```
3. Calcola il wave plan (PATTERN §18 se scheduler.enabled):
   - Antichain di TSK paralleli (conflict-free su (target, code_path)).
   - Cap a `scheduler.max_parallel` (default 4).
   - Gate umano se `len(group) >= parallel_gate_threshold` (default 3).
3-bis. Riga dei costi in token (capability cost-alert, sola lettura, silenziosa se spenta):
   `python3 tools/analytics/cost_alert.py check --period daily --compact`. Misura le sessioni
   Claude Code di questa macchina, non quelle Cursor (vedi skill `cost-alert-protocol` §Limiti).
4. Suggerisce next-step:
   - `/dev <TSK-id>` per i TSK con `consumer: agent`.
   - `/review <TSK-id>` per i TSK con `review_status: pending` (CQRL v2.12).
   - `/promote <path>` se ci sono pagine wiki da promuovere.
   - `/sync-docs` / `/figma-sync` / `/repo-sync` se ci sono raw da ingerire.

## Limitazioni Cursor

In Claude Code, `/run` può dispatchare in parallelo N sub-agent in una singola response.
In Cursor, il wave plan è presentato in chat e l'utente invoca sequenzialmente (o apre
N tab Cursor / usa Compose). Vedi `runtime_overrides.parallel_dispatch` nel manifest.

## Output

Append entry `run` a `wiki/log.md`:
```
- YYYY-MM-DD HH:MM — `run` (cursor adapter)
  - Wave plan: <N candidati>, dispatch sequenziale (Cursor)
  - Suggerito: <next-step>
```

E in `memory/episodic/<YYYY-MM-DD-HH-MM>-run.md` (Orchestrator scrive).
