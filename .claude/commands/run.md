---
description: Mostra dashboard di stato e suggerisce il prossimo agente.
---

Invoca l'agente [orchestrator](mdc:.cursor/rules/orchestrator.mdc) via `Agent`. Passa eventuale argomento come "focus"
(es. `/run l3` per focus L3). L'orchestrator:

1. Scansiona lo stato del filesystem per i 4 layer.
2. Legge l'ultima entry di `memory/episodic/` per continuità.
3. Emette un dashboard tabellare.
4. Suggerisce il prossimo agente da invocare (mai delega automatica).
5. Append a `memory/episodic/<YYYY-MM-DD-HH-MM>-run.md`.
