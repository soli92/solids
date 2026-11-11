# Fase 3 — Self-contain checks per backend

**Ambito**: checklist operative di self-containment per ogni backend supportato. Va letta
prima di valutare i check Fase 3 per il `selected_backend` corrente. Se il file manca,
non emettere `PROTOTYPE_GENERATED` (STOP — V-5 enforcement).

**Nota (INV-4)**: questi check verificano solo invarianti meccaniche (self-containment,
completezza strutturale, dipendenze rotte). Nessuna valutazione qualitativa estetica o
funzionale — quella è delegata a oracle/reviewer in Fase 4.

---

## Per backend `html` (INV-6 non overridabile)

Verifica le seguenti condizioni sul file `output_ref`:

- [ ] Il file esiste e ha dimensione > 0 bytes.
- [ ] **`single_file: true`** (INV-6): un solo file `index.html`. Nessun file aggiuntivo
      nella stessa directory (eccetto directory create intenzionalmente dalla mapping skill
      con struttura dichiarata).
- [ ] **Nessun asset esterno non consentito**: nessun `<link href="http://...">`,
      nessun `<script src="http://...">`, nessun `@import url("http://...")`, nessun
      `<img src="http://...">` o `<img src="https://...">` — eccetto Tailwind CDN
      (`https://cdn.tailwindcss.com`) se `css_strategy: tailwind-cdn`.
- [ ] **Stati UI principali coperti**: `artifact_metadata.states_covered` non vuoto.
      Almeno lo stato `default` deve essere presente. Se `states_hint` era valorizzato
      in Fase 1, verifica che gli stati dichiarati nell'hint siano in `states_covered`
      (tolleranza: se mancano stati custom non standard, log warning senza bloccare).
- [ ] **`single_file_verified: true`** nel `artifact_metadata` (check delegato
      precedentemente alla skill `html-prototype-mapping` in Fase D interna).

Se una o più verifiche falliscono:
- Logga i check falliti in chat con il dettaglio specifico.
- **STOP** — non emettere `PROTOTYPE_GENERATED`. Il caller deve segnalare all'utente
  che il prototipo non è self-contained e suggerire di riprovare o verificare la spec.

---

## Per backend `react`

Verifica (condizioni minime — il dettaglio è nella skill `react-prototype-mapping`):

- [ ] Il file/directory di output esiste.
- [ ] Nessuna dipendenza non risolta (build non ha emesso errori di import mancante).
- [ ] `artifact_metadata.component_file` valorizzato (o path equivalente).
- [ ] `artifact_metadata.states_covered` non vuoto.

---

## Per backend `figma` o `penpot`

Verifica:

- [ ] `output_ref` valorizzato e contiene un riferimento valido (URL o ID artefatto).
- [ ] `artifact_metadata` contiene conferma di creazione (es. frame_id, component_id).
- [ ] Nessun errore MCP riportato nella `artifact_metadata` (campo `mcp_error: null`
      o assente).

[^src: .claude/skills/prototype-generation-protocol.md §Fase 3 — Self-contain check]
[^src: .claude/skills/html-prototype-mapping.md §Fase D — Self-contain check]
[^src: wiki/sources/2026-07-01-prototype-generation-capability.md §3.3 Fasi]
