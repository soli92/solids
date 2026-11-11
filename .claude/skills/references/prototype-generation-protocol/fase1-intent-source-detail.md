# Fase 1 — Intent & Source: dettaglio Steps 1.1–1.4

**Ambito**: implementazione dettagliata dei 4 step di Fase 1 del protocollo. Il corpo
della skill contiene scopo e criteri di uscita; questa foglia contiene le procedure
operative step-by-step. Va letta prima di eseguire qualsiasi step di Fase 1.

---

## Step 1.1 — Lettura input_ref

Risolvi `input_ref` nel seguente ordine:

**Caso A — US-id (`US-NNN`)**:
- Leggi il file US (`management/kanban/**/US-NNN*/US-NNN.md`) — read-only (INV-3).
- Estrai: `title` (titolo della storia), `role` (per il contesto utente), sezione
  `## Descrizione` (descrizione funzionale), eventuali riferimenti a wireframe/spec.
- Cerca un `design-spec.md` nella stessa directory US o nella directory padre (vedi Step 1.2).
- Costruisci `intent_text` dal titolo + descrizione della US.

**Caso B — TSK-id (`TSK-NNN`)**:
- Leggi il file TSK (`management/kanban/**/TSK-NNN.md`) — read-only (INV-3).
- Estrai: `title`, `us_id`, corpo del TSK.
- Risali alla US (`us_id`) per contesto aggiuntivo (come Caso A).
- Cerca `design-spec.md` (vedi Step 1.2).
- Costruisci `intent_text` dal titolo TSK.

**Caso C — Stringa libera**:
- Usa la stringa direttamente come `intent_text`.
- Non c'è US/TSK di riferimento (`us_id: null`, `tsk_id: null`).
- Cerca `design-spec.md` solo se `prototyping_config.design_source` è un path esplicito.

In tutti i casi, determina:
```yaml
intent_text: <stringa descrittiva>
us_id: <US-NNN | null>
tsk_id: <TSK-NNN | null>
slug: <identificatore slug per il path di output>  # es. "login-form", "dashboard-widget"
```

Il `slug` è derivato da: `us_id` (es. `us-122`) oppure `tsk_id` (es. `tsk-233`) oppure
un slug kebab-case della stringa libera (max 40 char, lowercase, trattini). Se ambiguo,
preferisci il pattern `<data>-<slug>` (es. `2026-07-01-login-form`).

---

## Step 1.2 — Ricerca design-spec.md (INV-3 read-only)

Cerca la spec prodotta da `ui-designer` nell'ordine:

1. Se `prototyping_config.design_source` è un path esplicito (non `auto` o `none`):
   - Usa quel path direttamente. Se il file non esiste: log warning + procedi senza spec.
2. Se `design_source: auto` (default):
   - Cerca `design-spec.md` nelle directory: stessa dir del TSK → stessa dir della US →
     `output/design-specs/<slug>.md` → `output/design-specs/` (glob per slug simile).
   - Se trovato: usa il primo file trovato. Logga il path in chat.
   - Se non trovato: `spec_source: null` — usa `intent_text` come descrizione di alto livello.
3. Se `design_source: none`:
   - `spec_source: null`. Procedi con `intent_text` senza cercare spec.

**Importante (INV-3)**: il file `design-spec.md` è SOLO in lettura. Il protocollo non
modifica, non rinomina, non cancella il file spec sorgente.

---

## Step 1.3 — Art-director DSL (opt-in EP-019)

**Gate**: `prototyping_config.art_director` e `design_intelligence_config.art_director`.

Risolvi il flag art-director:

| `prototyping.art_director` | `design_intelligence.art_director` | Risultato |
|---|---|---|
| `inherit` (default) | `true` | art-director ATTIVO |
| `inherit` | `false` | art-director SPENTO |
| `on` | qualsiasi | art-director ATTIVO |
| `off` | qualsiasi | art-director SPENTO |

Se art-director ATTIVO:
- Leggi il DSL art-director dalla configurazione o dal file `design-spec.md` se contiene
  la sezione `## Art Director Tokens` (oppure dalla fonte configurata in `design_intelligence`).
- Estrai i token:
  ```yaml
  art_director_tokens:
    palette: [...]         # colori primari/secondari/semantici
    font_family: "..."
    spacing_unit: "..."
    border_radius: "..."
    shadow: "..."
  ```
- Questi token saranno passati alla skill `<backend>-mapping` in Fase 2.

Se art-director SPENTO: `art_director_active: false`, `art_director_tokens: null`.

---

## Step 1.4 — Composizione brief

Assembla il brief di generazione:

```yaml
brief:
  intent_text: <stringa>
  us_id: <US-NNN | null>
  tsk_id: <TSK-NNN | null>
  slug: <stringa>
  spec_source: <path | null>
  output_path: <prototyping_config.output_path>
  css_strategy: <prototyping_config.backends.html.css_strategy>  # solo se backend == html
  art_director_active: <bool>
  art_director_tokens: <yaml | null>
  states_hint: [...]   # stati UI esplicitati nella spec o nell'intent (best-effort)
  fidelity: <prototyping_config.fidelity>
  selected_backend: <da Fase 0>
  resolved_marker: <da Fase 0>
```

**Criteri di uscita Fase 1**: `brief` completo; `spec_source` valorizzato o `null`; flag
art-director determinato; `slug` e `output_path` pronti per Fase 2. Nessun file di spec
modificato (INV-3).

[^src: .claude/skills/prototype-generation-protocol.md §Fase 1 — Intent & Source]
[^src: wiki/concepts/prototype-generation-capability.md §Fasi del protocollo]
