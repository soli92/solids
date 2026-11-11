# Input Schema — prototype-generation-protocol

**Ambito**: contratto di input completo del protocollo (tutti i campi accettati dal
caller `prototype-generator` / comando `/prototype`). Questa foglia va letta ogni volta
che si accede alla sezione "Input del protocollo" nel corpo della skill.

---

## Schema YAML di input

Il caller (`prototype-generator` o `/prototype`) passa:

```yaml
input_ref: <US-NNN | TSK-NNN | "stringa libera di intent">
                         # identificativo o descrizione dell'intent
prototyping_config:      # blocco prototyping: di factory.config.yaml (letto dal caller)
  enabled: true
  backend: auto | html | react | figma | penpot
  fallback_chain: [...]
  degrade_policy: notify | strict
  fidelity: interactive | static | animated
  variants: 1            # 1 (default, comportamento invariato) | 2..5; vedi varianti.md
  design_source: auto | <spec-path> | none
  art_director: inherit | on | off
  output_path: "output/prototypes"
  oracle_handoff: true | false
  backends:
    html:
      css_strategy: tailwind-cdn | inline | vanilla
      single_file: true
    react:
      component_lib: shadcn
      storybook: true
      target: ""
    figma:
      mcp_server: "figma"
      file_key: ""
    penpot:
      mcp_server: "penpot"
      instance_url: ""
design_intelligence_config:    # da factory.config.yaml.design_intelligence (EP-019)
  art_director: true | false   # se true: leggi DSL art-director in Fase 1
```

## Note sui campi

- `input_ref`: stringa libera, US-id (`US-NNN`), o TSK-id (`TSK-NNN`). Determina il
  Caso A/B/C in Step 1.1 (detail in `fase1-intent-source-detail.md`).
- `prototyping_config.backend: auto`: il resolver sceglie il backend ottimale via
  `backend-resolver`. Con backend esplicito, il resolver valida solo la disponibilità.
- `prototyping_config.degrade_policy: strict`: se il backend preferito non è disponibile,
  STOP con gate umano invece di degradare silenziosamente.
- `prototyping_config.variants`: intero; `> 1` attiva la modalita' varianti divergenti
  (foglia `varianti.md`); `> 5` rifiuto esplicito. Override one-shot: `--variants N`.
- `prototyping_config.oracle_handoff: false`: Step 4.3 sopprime i suggerimenti downstream;
  il log entry (Step 4.1) viene scritto ugualmente.
- `design_intelligence_config.art_director`: se `true` e `prototyping_config.art_director`
  è `inherit` (default), il DSL art-director viene attivato in Step 1.3.

[^src: management/kanban/EP-035-prototype-generation-layer/US-122-prototype-generation-protocol-agente-comando/US-122.md §Business Rules §Acceptance Criteria]
[^src: .claude/skills/prototype-generation-protocol.md §Input del protocollo]
