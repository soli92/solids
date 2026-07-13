# Skill: Prototype Generation Protocol

> Adapter Cursor della skill `prototype-generation-protocol` definita in PATTERN.md.
>
> Metadata originale — name: prototype-generation-protocol; epic_id: EP-035; us_id: US-122; pattern_version: 2.25. Descrizione: protocollo provider-agnostic a 5 fasi per la generazione di prototipi grafici (EP-035, PATTERN §26 candidato). Orchestra resolve → intent+source → generate → self-contain check → handoff delegando la logica backend-specifica alla skill <backend>-mapping corrispondente. Analogia strutturale con publisher-protocol (v2.10): protocollo agnostico + skill provider-specific. Single source of truth per il layer di prototipazione (Prototyper, opzionale gated). Invocata da prototype-generator e dal comando /prototype.

**Protocollo — Prototype Generation (5 fasi)**

Skill condivisa dal ruolo Prototyper (agente `prototype-generator`) e invocata
dal comando `/prototype`. Ogni fase ha criteri di uscita espliciti; nessun fallimento
silenzioso. Analogia strutturale: `publisher-protocol` (v2.10) — stesso split
provider-agnostic + `<backend>-mapping` provider-specific; `dev-protocol` — stessa
spina dorsale a fasi ordinate con gate e handoff.

Sub-skill invocate: [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) (Fase 0), `<backend>-mapping` (Fase 2).

---

## Precondizione assoluta — Guard `prototyping.enabled` (INV-5)

**In testa a qualsiasi esecuzione**, prima della Fase 0:

```
SE factory.config.yaml.prototyping.enabled == false (default R.P3):
  STOP — emetti nessun output, nessun side-effect.
  Il caller mostra:
    "[prototype-generation-protocol] Skipped: prototyping.enabled: false (R.P3 default off)
     Per abilitare: imposta prototyping.enabled: true in factory.config.yaml
     e verifica /prototype-status."
```

A flag spento la factory v2.25 e' identica alla versione precedente (backward compat
totale, INV-5). Nessun agente scaffoldato, nessun artefatto creato.

---

## Input del protocollo

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

---

## Fase 0 — Backend Resolve

**Scopo**: determinare quale backend usare. Single source of truth per la risoluzione:
delegata interamente a [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) (TSK-229) — nessuna logica di risoluzione
duplicata nel protocollo core.

**Azione**:

1. Invoca la skill [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) con:
   - `intent` — derivato da `input_ref`:
     - se `input_ref` e' una stringa libera → passala direttamente come intent
     - se `input_ref` e' un `US-id` o `TSK-id` → leggi il file per estrarre l'intent
       (campo `title`, `role`, o body) e passa `"auto"` se non univocamente mappabile
   - `prototyping_config` — blocco `prototyping:` ricevuto in input

2. Il resolver ritorna:
   ```yaml
   selected_backend: <html | react | figma | penpot>
   marker: <BACKEND_RESOLVED | BACKEND_DEGRADED | BACKEND_UNAVAILABLE_STRICT>
   preferred_backend: <backend>
   degraded_from: <backend | null>
   reason: <stringa motivo>
   asse1_match: <backend | null>
   asse2_probes: {figma: bool, penpot: bool, react: bool, html: true}
   ```

3. Gestione marker:

   **`BACKEND_RESOLVED: <backend>`**
   - Procedi con `selected_backend`.
   - Emetti in chat: `[Fase 0] BACKEND_RESOLVED: <backend>`

   **`BACKEND_DEGRADED: <preferito>→<selezionato> (<motivo>)`**
   - Procedi con `selected_backend` (il resolver ha gia' scelto il fallback).
   - Emetti in chat il marker di degrado + motivo.
   - Se `oracle_handoff: true`, annota in Fase 4 di suggerire la remediation.

   **`BACKEND_UNAVAILABLE_STRICT: <preferito> (<motivo>)`**
   - **STOP con gate umano** (INV-2 + `degrade_policy: strict`).
   - Emetti in chat:
     ```
     [Fase 0] BACKEND_UNAVAILABLE_STRICT: <preferito> (<motivo>)
     Azione richiesta: scegli una delle opzioni:
       (a) Autentica / configura il backend <preferito> e rilancia /prototype
       (b) Abbassa degrade_policy: notify in factory.config.yaml
       (c) Cambia backend: <altro> in factory.config.yaml
     ```
   - Non procedere alle fasi successive.

**Criteri di uscita Fase 0**: marker emesso; `selected_backend` valorizzato (o STOP se
`BACKEND_UNAVAILABLE_STRICT`). Il marker viene propagato come `resolved_marker` alle
fasi successive (presente in ogni log entry e nell'output finale).

---

## Fase 1 — Intent & Source

**Scopo**: costruire il brief di generazione — descrizione dell'artefatto da produrre,
stati UI richiesti, spec sorgente (se presente), token art-director (se abilitati).

**Azione**:

### Step 1.1 — Lettura input_ref

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
- Non c'e' US/TSK di riferimento (`us_id: null`, `tsk_id: null`).
- Cerca `design-spec.md` solo se `prototyping_config.design_source` e' un path esplicito.

In tutti i casi, determina:
```yaml
intent_text: <stringa descrittiva>
us_id: <US-NNN | null>
tsk_id: <TSK-NNN | null>
slug: <identificatore slug per il path di output>  # es. "login-form", "dashboard-widget"
```

Il `slug` e' derivato da: `us_id` (es. `us-122`) oppure `tsk_id` (es. `tsk-233`) oppure
un slug kebab-case della stringa libera (max 40 char, lowercase, trattini). Se ambiguo,
preferisci il pattern `<data>-<slug>` (es. `2026-07-01-login-form`).

### Step 1.2 — Ricerca design-spec.md (INV-3 read-only)

Cerca la spec prodotta da `ui-designer` nell'ordine:

1. Se `prototyping_config.design_source` e' un path esplicito (non `auto` o `none`):
   - Usa quel path direttamente. Se il file non esiste: log warning + procedi senza spec.
2. Se `design_source: auto` (default):
   - Cerca `design-spec.md` nelle directory: stessa dir del TSK → stessa dir della US →
     `output/design-specs/<slug>.md` → `output/design-specs/` (glob per slug simile).
   - Se trovato: usa il primo file trovato. Logga il path in chat.
   - Se non trovato: `spec_source: null` — usa `intent_text` come descrizione di alto livello.
3. Se `design_source: none`:
   - `spec_source: null`. Procedi con `intent_text` senza cercare spec.

**Importante (INV-3)**: il file `design-spec.md` e' SOLO in lettura. Il protocollo non
modifica, non rinomina, non cancella il file spec sorgente.

### Step 1.3 — Art-director DSL (opt-in EP-019)

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

### Step 1.4 — Composizione brief

Assembla il brief di generazione:

```yaml
brief:
  intent_text: <stringa>
  us_id: <US-NNN | null>
  tsk_id: <TSK-NNN | null>
  slug: <stringa>
  spec_source: <path | null>
  output_path: <prototyping_config.output_path>
  css_strategy: <prototyping_config.backends.html.css_strategy>  # passato solo se backend == html
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

---

## Fase 2 — Generate

**Scopo**: produrre l'artefatto di prototipazione delegando interamente alla skill
`<backend>-mapping` corrispondente al `selected_backend`. Il protocollo core non contiene
logica MCP, logica HTML, logica React — la delega e' totale e provider-agnostic.

**Principio (ADR-EP035-003 GO riuso pattern publisher)**:
La Fase 2 e' la stessa indipendentemente dal backend — cambia solo la skill invocata.
Aggiungere un nuovo backend = aggiungere `<backend>-mapping` + voce in `fallback_chain`.
Nessuna modifica al protocollo core.

**Azione**:

1. Identifica la skill da invocare in base a `selected_backend`:

   | `selected_backend` | Skill invocata |
   |---|---|
   | `html` | [html-prototype-mapping](mdc:.cursor/skills/html-prototype-mapping/SKILL.md) (TSK-231) |
   | `react` | `react-prototype-mapping` (US-124, futuro) |
   | `figma` | `figma-mapping` (US-126, futuro) |
   | `penpot` | `penpot-mapping` (US-127, futuro) |

   Se la skill per il `selected_backend` non esiste nell'adapter:
   - **STOP** + segnala in chat: `[Fase 2] Skill <backend>-prototype-mapping non trovata.
     Il backend <backend> richiede la skill <backend>-prototype-mapping — attualmente non
     scaffoldata. Verifica la roadmap US-124/US-126/US-127.`
   - Non procedere. Il caller deve gestire come un errore di configurazione, non come
     un degrado backend (quello e' gia' stato gestito in Fase 0).

2. Invoca la skill `<backend>-mapping` passando il `brief` completo (output Fase 1)
   come input strutturato. La skill riceve:
   - Tutti i campi del `brief` (Step 1.4)
   - Accesso in lettura a `spec_source` se valorizzato (INV-3 e' responsabilita' anche
     della skill mapping — non deve modificare la spec)

3. La skill `<backend>-mapping` ritorna (schema minimo — il dettaglio varia per backend):
   ```yaml
   output_ref: <path del file generato | riferimento artefatto>
                # es. per html: "output/prototypes/login-form/index.html"
                # es. per figma: "figma://file/<key>/frame/<id>"
   backend: <html | react | figma | penpot>
   marker: <backend-specifico>
                # es. per html: HTML_GENERATED
                # per altri backend: marker definito nella loro skill mapping
   artifact_metadata: <yaml — dipende dal backend>
                # es. per html: {single_file_verified, states_covered, css_strategy_used,
                #                art_director_applied, size_bytes}
   ```

4. Se la skill mapping ritorna un errore (file non generato, MCP non risponde, build fallita):
   - Logga l'errore in chat: `[Fase 2] Generazione fallita (backend: <backend>): <motivo>`
   - STOP — non procedere a Fase 3. Il caller deve segnalare all'utente e suggerire
     `/prototype-status` per diagnosticare.

**Criteri di uscita Fase 2**: `output_ref` valorizzato; `marker` emesso dalla skill
mapping; `artifact_metadata` disponibile per Fase 3. Nessuna logica backend-specifica
nel corpo di questa fase (tutto nella skill delegata).

---

## Fase 3 — Self-contain check

**Scopo**: verificare che l'artefatto generato soddisfi le invarianti di self-containment
e completezza prima di emetterlo come output definitivo. La verifica e' backend-dipendente
(regole diverse per html vs figma vs react) ma il check e' sempre responsabilita' del
protocollo core — non della skill mapping (che ha gia' eseguito i propri check interni).

**Importante (INV-4)**: questa fase NON valuta la qualita' estetica o funzionale del
prototipo. Verifica solo invarianti meccaniche (self-containment, completezza strutturale,
assenza di dipendenze rotte). La validazione qualitativa e' delegata a oracle/reviewer in
Fase 4.

**Azione**:

### Per backend `html` (INV-6 non overridabile)

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
      precedentemente alla skill [html-prototype-mapping](mdc:.cursor/skills/html-prototype-mapping/SKILL.md) in Fase D interna).

Se una o piu' verifiche falliscono:
- Logga i check falliti in chat con il dettaglio specifico.
- **STOP** — non emettere `PROTOTYPE_GENERATED`. Il caller deve segnalare all'utente
  che il prototipo non e' self-contained e suggerire di riprovare o verificare la spec.

### Per backend `react`

Verifica (condizioni minime — il dettaglio e' nella skill `react-prototype-mapping`):

- [ ] Il file/directory di output esiste.
- [ ] Nessuna dipendenza non risolta (build non ha emesso errori di import mancante).
- [ ] `artifact_metadata.component_file` valorizzato (o path equivalente).
- [ ] `artifact_metadata.states_covered` non vuoto.

### Per backend `figma` o `penpot`

Verifica:

- [ ] `output_ref` valorizzato e contiene un riferimento valido (URL o ID artefatto).
- [ ] `artifact_metadata` contiene conferma di creazione (es. frame_id, component_id).
- [ ] Nessun errore MCP riportato nella `artifact_metadata` (campo `mcp_error: null`
      o assente).

### Marker di uscita

Se tutti i check passano, emetti il marker di completamento:

```
PROTOTYPE_GENERATED: <output_ref>
```

Esempio per backend html:
```
PROTOTYPE_GENERATED: output/prototypes/login-form/index.html
```

Esempio per backend figma:
```
PROTOTYPE_GENERATED: figma://file/AbCdEf123/frame/42
```

Il marker `PROTOTYPE_GENERATED` e' l'unico marker emesso da questa fase — mai
`PROTOTYPE_GENERATED` se anche uno solo dei check e' fallito.

**Criteri di uscita Fase 3**: `PROTOTYPE_GENERATED: <output_ref>` emesso; tutti i check
di self-containment superati; nessuna auto-valutazione qualitativa (INV-4).

---

## Fase 4 — Handoff

**Scopo**: dopo la generazione riuscita (`PROTOTYPE_GENERATED` emesso in Fase 3),
registrare l'evento nel log, notificare lo stato TSK/US se applicabile, e orientare
l'utente verso i reviewer/oracle downstream rilevanti in funzione del backend risolto.

**INV-4 (enforced in questa fase)**: il protocollo non esprime nessuna valutazione
qualitativa del prototipo generato — ne' in chat ne' nel log. Frasi del tipo
"il prototipo e' ben strutturato", "il design e' adeguato", "buon risultato" sono
vietate. Il ruolo di questa fase e' esclusivamente di routing verso chi valuta.

**Azione**:

### Step 4.1 — Log entry

Determina il path del log:
- Se `prototyping_config.log_path` e' valorizzato → usa quel path.
- Altrimenti → default `wiki/log.md`.

Append al log (append-only, mai editare entry passate):

```
## YYYY-MM-DD HH:MM — prototype <TSK-id | US-id | "intent">
**Backend:** <selected_backend> (<resolved_marker>)
**Artefatto:** <output_ref>
**Spec source:** <spec_source | "none (intent only)">
**Art-director:** <art_director_active>
**States covered:** <states_covered list — da artifact_metadata>
**Suggerimenti emessi:** <N> (elenco comandi, o "nessuno — oracle_handoff: false")
**Files touched:** 1 (<output_ref> [NEW])
```

Usa la data corrente nel formato ISO-8601 locale (YYYY-MM-DD HH:MM). Il log entry
viene scritto **sempre**, indipendentemente dal valore di `oracle_handoff` (il log
non e' condizionato al handoff guidato — registra il fatto produttivo in ogni caso).

### Step 4.2 — Notifica status TSK/US (se applicabile)

Se `tsk_id` e' valorizzato e il TSK e' in stato `in-progress`:
- **Non modificare lo status del TSK** — quello e' responsabilita' del dev-agent o
  dell'orchestrator che ha invocato il protocollo. Il protocollo e' una skill, non un
  agente con ownership sul TSK.
- Segnala in chat: `[Fase 4] Prototipo generato per TSK-NNN. Se la generazione era
  il deliverable principale, aggiorna lo status del TSK.`

Se `tsk_id: null` (input libero o US-id):
- Nessuna notifica di stato TSK. Segnala solo `[Fase 4] Prototipo generato: <output_ref>`.

### Step 4.3 — Guard `oracle_handoff`

**Prima di emettere qualsiasi suggerimento**:

```
SE prototyping_config.oracle_handoff == false:
  STOP questo step — non emettere suggerimenti.
  Log entry gia' scritto al Step 4.1 con "Suggerimenti emessi: nessuno — oracle_handoff: false".
  Emetti in chat: "[Fase 4] oracle_handoff: false — suggerimenti soppressi."
  Procedi ai criteri di uscita.
```

Se `oracle_handoff: true` (default): procedi con Step 4.4.

### Step 4.4 — Gate installazione comandi

Per ogni suggerimento candidato (tabella Step 4.5), esegui il gate prima di emetterlo:

```
SE .claude/commands/<comando>.md NON esiste nel repo corrente:
  sopprimi silenziosamente il suggerimento (nessun WARNING, nessun output aggiuntivo).
```

Esempio: se `a11y.enabled: true` ma `.claude/commands/a11y.md` non esiste → il
suggerimento `/a11y` e' soppresso. Solo i comandi installati vengono proposti.

### Step 4.5 — Suggerimenti per backend

Determina i suggerimenti candidati in funzione del `selected_backend` risolto in Fase 0:

| Backend | Suggerimenti candidati (emessi solo se comando installato e gate config attivo) |
|---|---|
| `html` | `/visual-oracle` (sempre · verifica rendering) · `/functional-oracle` (se il prototipo include stati interattivi, cioe' `artifact_metadata.states_covered` ha piu' di un elemento) · `/ux-ui-review` (sempre) · `/a11y` (sempre) |
| `react` | `/visual-oracle` (sempre) · `/functional-oracle` (sempre) · `/review` (se `code_quality.enabled: true`) · `/a11y` (sempre) · handoff narrativo a `fe-dev` (non un comando — segnala che il componente e' consumabile come scaffold) |
| `figma` | `/ux-ui-review` (sempre) · round-trip `figma-sync` (suggerimento narrativo: "eseguire `/figma-sync` per re-ingest del file Figma aggiornato") · revisione manuale nel file Figma (`output_ref`) |
| `penpot` | `/ux-ui-review` (sempre) · revisione manuale nel file Penpot (`output_ref`) |

**Gate config per suggerimento**: prima di emettere ogni suggerimento legato a una
capability opt-in, verifica il flag corrispondente in `factory.config.yaml`:

| Suggerimento | Flag richiesto |
|---|---|
| `/visual-oracle` | `fe_correctness.enabled: true` |
| `/functional-oracle` | `fe_correctness.functional_oracle.enabled: true` |
| `/ux-ui-review` | `ux_ui.enabled: true` |
| `/a11y` | `a11y.enabled: true` |
| `/review` | `code_quality.enabled: true` |

Se il flag e' `false` (o assente): suggerimento soppresso silenziosamente.
Se il flag e' `true` ma il comando non e' installato (Step 4.4): suggerimento soppresso.
Se entrambi i gate sono superati: suggerimento emesso.

I suggerimenti narrativi (handoff `fe-dev`, round-trip `figma-sync`, revisione manuale)
non sono legati a flag config — vengono emessi se il comando di riferimento e' installato
o se si tratta di un'azione narrativa (non un comando `/`).

### Step 4.6 — Suggerimento push EP-033

Questo step implementa la regola aggiuntiva EP-033 per il `prototype-generation-protocol`
(PATTERN §26 + `wiki/syntheses/ep-035-prototype-generation-integration.md §Runtime suggestions`).

**Trigger** (valutato dall'orchestrator, non da questa skill direttamente — la skill
emette la regola come segnale push leggibile dall'orchestrator):

```
SE prototyping.enabled: true
E lo sprint corrente include TSK con layer=fe
E quei TSK hanno design-spec.md associata (campo design_source valorizzato o
  file design-spec.md presente nella dir US)
E nessun prototipo recente e' registrato in wiki/log.md per quella US nella
  sessione corrente (verifica per us_id)
→ emetti il segnale push:
  "[EP-033 push] Rilevati TSK FE con spec ma senza prototipo recente per <US-id>.
   Considera: /prototype <US-id>"
```

Il segnale e' **non-bloccante e informativo**: non interrompe il flusso, non richiede
conferma, non blocca la chiusura della Fase 4. Viene emesso in chat come suggerimento
(stesso stile EP-033 `## Suggerimento post-esecuzione`), non nel log.

**Gate**: il segnale e' soppresso se `prototyping.enabled: false` (default R.P3) o se
il comando `/prototype` non e' installato (`.claude/commands/prototype.md` assente).

### Step 4.7 — Formato output Fase 4

Emetti in chat il blocco di chiusura Fase 4:

```
[Fase 4] Prototipo registrato: <output_ref>
Log: <log_path> (entry appended)

Passi successivi disponibili:
- `/<comando>` — <motivazione breve, max 1 riga, specifica per il backend>.
[... un suggerimento per riga, solo quelli che hanno superato tutti i gate ...]
```

Se 0 suggerimenti superano i gate (tutti soppressi o `oracle_handoff: false`):

```
[Fase 4] Prototipo registrato: <output_ref>
Log: <log_path> (entry appended)
Nessun suggerimento downstream disponibile (capability non attivate o oracle_handoff: false).
```

Tono: sempre "disponibili", "considera", "potresti" — mai imperativo ("devi", "e' richiesto").
La Fase 4 e' informativa, non e' un gate bloccante.

**Criteri di uscita Fase 4**: log entry appended (sempre, indipendentemente da `oracle_handoff`);
suggerimenti emessi in funzione del backend e dei gate (o silenzio se `oracle_handoff: false`);
segnale push EP-033 emesso se trigger soddisfatto; nessun side-effect sui file spec sorgente
(INV-3); nessuna valutazione qualitativa del prototipo (INV-4).

---

## Output finale del protocollo

Alla conclusione delle 5 fasi (o allo STOP), il protocollo emette un riepilogo
strutturato in chat:

### Esito positivo

```
PROTOTYPE GENERATION — <input_ref>
===================================
Fase 0 — Backend:    <resolved_marker>: <selected_backend>
Fase 1 — Source:     <spec_source | "intent only"> / art-director: <on|off>
Fase 2 — Generate:   <backend>-mapping invocata → <marker-mapping>
Fase 3 — Check:      PROTOTYPE_GENERATED: <output_ref>
Fase 4 — Handoff:    log entry scritto · suggerimenti: <N>
```

### Esito con STOP (gate umano o errore)

```
PROTOTYPE GENERATION — STOP
===========================
Fase <N> — <motivo del blocco>
Azione richiesta: <descrizione azione umana>
```

---

## Invarianti del protocollo

- **INV-1** (`html` sempre disponibile): il protocollo non puo' hard-fail per
  indisponibilita' backend — `html` e' il fallback terminale garantito da [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md).
- **INV-2** (mai bloccare su MCP non autenticato salvo `strict`): la Fase 0 delega
  questa logica al [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) (read-only, nessun OAuth eseguito qui).
- **INV-3** (read-only verso spec sorgente): il protocollo e le skill invocate non
  modificano mai `design-spec.md` o altri file di spec prodotti da `ui-designer`.
- **INV-4** (no self-eval): il protocollo non giudica la qualita' estetica o
  funzionale dell'artefatto generato — ne' in chat ne' nel log. La validazione e'
  delegata a oracle/reviewer (Fase 4). Nessuna frase del tipo "il prototipo e' ben
  strutturato" o "il design e' adeguato".
- **INV-5** (default off): a `prototyping.enabled: false`, la skill non produce
  nessun output, nessun side-effect, nessun artefatto.
- **INV-6** (single_file per html, non overridabile): verificata in Fase 3. Se la
  verifica fallisce, `PROTOTYPE_GENERATED` non viene emesso.

---

## Vincoli di esecuzione

- **Provider-agnostic (Fase 2)**: nessuna logica MCP, nessuna logica HTML, nessuna
  logica React nel corpo di questa skill. Tutto nella `<backend>-mapping` delegata.
- **Nessun design** (regola docs-dev): se la spec e' insufficiente o assente, il
  protocollo procede con `intent_text` — non inventa dettagli architetturali o
  design non specificati. Lo slot `<!-- PLACEHOLDER -->` nella generazione HTML
  e' l'unico meccanismo di "intent aperto" accettato.
- **Criteri di uscita espliciti per fase**: ogni fase ha una condizione di uscita
  documentata. Mai proseguire alla fase successiva senza soddisfare il criterio.
- **Mai fallimento silenzioso**: ogni percorso di esecuzione emette un marker
  (`BACKEND_RESOLVED`, `BACKEND_DEGRADED`, `BACKEND_UNAVAILABLE_STRICT`,
  `PROTOTYPE_GENERATED`, o messaggio di STOP esplicito).

---

## Cross-link

- **Skill invocate**:
  - [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) (TSK-229, Fase 0) — risoluzione backend adattiva
  - [html-prototype-mapping](mdc:.cursor/skills/html-prototype-mapping/SKILL.md) (TSK-231, Fase 2 per backend `html`)
  - `react-prototype-mapping` (US-124, futuro)
  - `figma-mapping` (US-126, futuro)
  - `penpot-mapping` (US-127, futuro)
- **Callers**:
  - agente `prototype-generator` (US-122) — ruolo Prototyper
  - `/prototype` (US-122) — comando `/prototype`
- **Config source**: `factory.config.yaml` blocco `prototyping:` e `design_intelligence:`
- **Analogia strutturale**: `publisher-protocol` (v2.10) — protocollo agnostico + skill
  provider-specific; `dev-protocol` — spina dorsale a fasi con gate e handoff
- **Invarianti EP-035**: INV-1..INV-6 (tutti documentati sopra)
- **PATTERN §26** (candidato) — Prototype Generation Layer
- **Fonti**:

[^src: wiki/concepts/prototype-generation-capability.md §Fasi del protocollo §Invarianti]
[^src: wiki/syntheses/ep-035-prototype-generation-integration.md §Oracle handoff (Fase 4) §Runtime suggestions (EP-033)]
[^src: wiki/sources/2026-07-01-prototype-generation-capability.md §Architettura agent-agnostic §3.3 Fasi]
[^src: management/kanban/EP-035-prototype-generation-layer/US-122-prototype-generation-protocol-agente-comando/US-122.md §Business Rules §Acceptance Criteria]
[^src: management/kanban/EP-035-prototype-generation-layer/US-123-handoff-oracle-fase-4/TSK-236.md §Obiettivo §Deliverable]
[^src: .claude/skills/backend-resolver.md §Output §Step 5 — Emissione marker]
[^src: .claude/skills/html-prototype-mapping.md §Input §Output §Fase D — Self-contain check]
[^src: .claude/skills/dev-handoff.md §Suggerimento post-esecuzione (EP-033) §Gate installazione]
