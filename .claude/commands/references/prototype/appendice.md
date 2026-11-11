# appendice.md — /prototype: esempi, prerequisiti e cross-link

**Ambito**: questa foglia raccoglie contenuti consultivi non vincolanti del comando
`/prototype`: esempi d'uso per operatore, prerequisiti di configurazione e cross-link
verso agenti, skill e risorse correlate.

Questa foglia e' referenziata da un trigger SOFT-FAIL nel corpo del comando:
se il file manca, il comando emette un WARNING e prosegue — il flusso di generazione
non dipende da questa foglia (contenuto puramente consultivo).

[^src: .claude/commands/prototype.md §Esempi d'uso + §Prerequisiti + §Cross-link]

---

## §Esempi d'uso

```bash
# Genera un prototipo dalla storia US-122 (backend auto, fidelity da config)
/prototype US-122

# Genera da un TSK specifico con backend HTML esplicito
/prototype TSK-235 --backend=html

# Genera da intent libero (stringa descrittiva diretta)
/prototype "dashboard widget con grafici e stato empty/loading/error"

# Genera con fidelity statica (solo screenshot/wireframe senza interazione JS)
/prototype US-122 --fidelity=static

# Dry-run: mostra quale backend verrebbe selezionato per US-122, senza generare
/prototype US-122 --dry-run

# Dry-run con override backend esplicito: controlla se figma e' disponibile
/prototype "form di checkout" --backend=figma --dry-run
```

---

## §Prerequisiti

- `factory.config.yaml.prototyping.enabled: true` (gate principale, Step 0).
- Blocco `prototyping:` completo in `factory.config.yaml` (schema in
  `agents/prototype-generator.md §Input attesi`).
- `.claude/agents/prototype-generator.md` presente (l'agente viene invocato in Step 5).
- `.claude/skills/prototype-generation-protocol.md` presente (eseguita dall'agente).
- Per backend `html`: nessun prerequisito aggiuntivo (sempre disponibile, INV-1).
- Per backend `react`: stack FE rilevato da `stack-detector` in almeno un `code_path`.
- Per backend `figma`/`penpot`: MCP server corrispondente autenticato e raggiungibile.

Usa `/prototype-status` per verificare la disponibilita' dei backend prima di lanciare
la generazione.

---

## §Cross-link

- **Agente invocato**: `.claude/agents/prototype-generator.md` (US-122, TSK-234)
- **Skill eseguita**: `.claude/skills/prototype-generation-protocol.md` (US-122, TSK-233)
- **Skill Fase 0**: `.claude/skills/backend-resolver.md` (US-120, TSK-229)
- **Skill Fase 2 (html)**: `.claude/skills/html-prototype-mapping.md` (US-121, TSK-231)
- **Snapshot layer**: `/prototype-status` (TSK-230) — dry-run globale, nessun input
- **Config gate**: `factory.config.yaml` blocco `prototyping:` (INV-5, R.P3)
- **PATTERN §26** (candidato) — Prototype Generation Layer (EP-035)
- **Analogia strutturale**:
  - `/dev` (v2.7) — input identificativo → esecuzione protocollo → output artefatto
  - `/review` (v2.12) — gate config + invocazione agente + report finale
  - `/kanban-publish` (v2.10) — gated, provider-agnostic, one-shot override

[^src: management/kanban/EP-035-prototype-generation-layer/US-122-prototype-generation-protocol-agente-comando/US-122.md §Business Rules §Acceptance Criteria]
[^src: .claude/skills/prototype-generation-protocol.md §Precondizione §Invarianti §Cross-link]
[^src: .claude/agents/prototype-generator.md §Gate §Input attesi §Output]
[^src: .claude/skills/backend-resolver.md §Output §Step 5 — Emissione marker]
[^src: wiki/concepts/prototype-generation-capability.md §Artefatti della capability]
