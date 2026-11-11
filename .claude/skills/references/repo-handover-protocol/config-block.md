---
parent: repo-handover-protocol
type: reference
---

# Blocco di config — `repo_handover`

Blocco proposto per `factory.config.yaml`.
**Non modificare `factory.config.yaml` direttamente con questa skill.**
Il blocco è a titolo di riferimento; la configurazione concreta va in `factory.config.yaml`
con una modifica esplicita del manutentore.

```yaml
repo_handover:
  enabled: false       # default: false — a flag spento la skill segnala e si ferma

  # Gate locali (opzionale): comandi eseguiti via worktree-gate sul commit di import
  # prima della conferma push (G3e). Vuoto = nessun gate locale.
  local_gates: []
  # Esempio:
  # local_gates:
  #   - "npm run lint"
  #   - "npm test"

  # Exclude patterns globali (aggiuntivi a quelli passati per singolo travaso).
  # Formato .gitignore-style.
  default_exclude_patterns:
    - ".git/"
    - "node_modules/"
    - "dist/"
    - "*.log"
```

## Campi

| Campo | Tipo | Default | Significato |
|---|---|---|---|
| `enabled` | bool | `false` | Abilita la capability. A `false`: fallback esplicito, nessuna operazione |
| `local_gates` | list[str] | `[]` | Comandi gate locali opzionali (worktree-gate) |
| `default_exclude_patterns` | list[str] | `[]` | Pattern di esclusione globali (aggiuntivi per singolo invocation) |
