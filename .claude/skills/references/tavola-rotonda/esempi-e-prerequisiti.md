# Sintassi, esempi d'uso e prerequisiti — /tavola-rotonda

Ambito: questa foglia raccoglie la tabella dei flag, gli esempi d'uso e i
prerequisiti di configurazione per il comando `/tavola-rotonda`. Non governa il
flusso operativo (Steps 0–5 nel corpo del comando); serve come riferimento rapido
per chi prepara o invoca la sessione. Letta su trigger dal corpo del comando
prima di procedere con la risoluzione dei parametri.

---

## Sintassi

```
/tavola-rotonda <topic>
/tavola-rotonda <topic> --partecipanti=<agent1>,<agent2>,...
/tavola-rotonda <topic> --max-round=<N>
/tavola-rotonda <topic> --partecipanti=<a>,<b> --max-round=<N> --budget=<USD>
```

| Flag | Tipo | Default | Descrizione |
|---|---|---|---|
| `<topic>` | obbligatorio | — | Questione o decisione da deliberare (max 120 caratteri) |
| `--partecipanti=<lista>` | opzionale | da config | Lista slug agenti separati da virgola (es. `be-dev,lead-architect`) |
| `--max-round=<N>` | opzionale | `4` (hardcoded) | Numero massimo di round di convergenza |
| `--budget=<USD>` | opzionale | da config | Tetto di costo USD per la sessione (es. `2.00`) |

---

## Esempi d'uso

```bash
# Delibera su un tema architetturale con config defaults
/tavola-rotonda "Quale pattern di caching adottare per l'API?"

# Specifica i partecipanti inline (override one-shot della config)
/tavola-rotonda "Architettura auth" --partecipanti=be-dev,lead-architect,qa-dev

# Limita i round e imposta il budget esplicitamente
/tavola-rotonda "DB sharding strategy" --max-round=3 --budget=3.00

# Sessione completa con tutti i flag
/tavola-rotonda "Adottare GraphQL o REST?" --partecipanti=be-dev,fe-dev,lead-architect --max-round=5 --budget=5.00
```

---

## Prerequisiti

- `factory.config.yaml.tavola_rotonda.enabled: true` (gate principale, Step 0).
- `factory.config.yaml.tavola_rotonda.budget.max_cost_usd` valorizzato (INV-TR-3),
  oppure flag `--budget=<USD>` passato inline.
- Almeno 2 agenti nella lista `partecipanti` (config o `--partecipanti`).
- `.claude/agents/tavola-rotonda-moderatore.md` presente.
- I file agente per ogni partecipante esistenti in `.claude/agents/`.

Sezione `tavola_rotonda:` minima in `factory.config.yaml`:

```yaml
tavola_rotonda:
  enabled: true
  partecipanti: [be-dev, lead-architect]   # oppure specifica con --partecipanti
  max_round: 4
  budget:
    max_cost_usd: 2.00
```

---

## Cross-link

- **Agente invocato**: `.claude/agents/tavola-rotonda-moderatore.md` (EP-039 TSK-287)
- **Skill eseguita**: `.claude/skills/tavola-rotonda-protocol.md` (EP-039 US-139)
- **ADR normativo blackboard**: `design_&_architecture/decisions/ADR-EP039-001-blackboard-format.md`
- **Config gate**: `factory.config.yaml` blocco `tavola_rotonda:` (R.P3-TR)
- **PATTERN §28** — Tavola Rotonda multi-agente (EP-039)
- **Concept**: `wiki/concepts/tavola-rotonda.md`
- **Analogia strutturale**:
  - `/prototype` (EP-035) — gate config + parse flag + dispatch agente + output artefatto
  - `/review` (v2.12) — gate config + invocazione agente + report finale
  - `/dev` (v2.7) — input identificativo → esecuzione protocollo → output artefatto

[^src: management/kanban/EP-039-tavola-rotonda/US-142-comando-runbook-benchmark/TSK-292.md §Deliverable §Vincoli]
[^src: .claude/agents/tavola-rotonda-moderatore.md §Trigger §Invarianti §Procedura Fase 0]
[^src: factory.config.yaml blocco tavola_rotonda: §partecipanti §budget §max_round]
