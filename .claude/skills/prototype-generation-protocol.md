---
name: prototype-generation-protocol
description: >-
  Protocollo provider-agnostic 5 fasi per la generazione di prototipi grafici: resolve → intent+source → generate → self-contain check → handoff. Delega la logica backend-specifica alla skill corrispondente ({backend}-mapping). Invocata da prototype-generator e /prototype.
epic_id: EP-035
us_id: US-122
pattern_version: "2.25"
---
# Protocollo — Prototype Generation (5 fasi)

Skill condivisa da `agents/prototype-generator.md` e dal comando `/prototype`. Ogni fase
ha criteri di uscita espliciti; nessun fallimento silenzioso.
Sub-skill invocate: `backend-resolver` (Fase 0), `<backend>-mapping` (Fase 2).

---

## Precondizione assoluta — Guard `prototyping.enabled` (INV-5)

**In testa a qualsiasi esecuzione**, prima della Fase 0:

```
SE factory.config.yaml.prototyping.enabled == false (default R.P3):
  STOP — nessun output, nessun side-effect.
  Il caller mostra:
    "[prototype-generation-protocol] Skipped: prototyping.enabled: false (R.P3 default off)
     Per abilitare: prototyping.enabled: true in factory.config.yaml + /prototype-status."
```

A flag spento la factory è identica alla versione precedente (backward compat INV-5).

---

## Input del protocollo

Prima di usare il contratto di input, leggi obbligatoriamente
`.claude/skills/references/prototype-generation-protocol/input-schema.md`.
STOP se il file manca. **(T1)**

Il caller passa `input_ref`, `prototyping_config` (da `factory.config.yaml`)
e `design_intelligence_config`. Schema completo dei campi in `input-schema.md`.

---

## Fase 0 — Backend Resolve

**Scopo**: determinare quale backend usare. Logica delegata interamente a `backend-resolver`
(TSK-229) — nessuna logica di risoluzione duplicata nel protocollo core.

1. Invoca `backend-resolver` con `intent` (da `input_ref`) e `prototyping_config`.
   - `input_ref` stringa libera → passala come intent
   - `input_ref` US-id/TSK-id → leggi file, estrai intent; `"auto"` se non univoco

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

   **`BACKEND_RESOLVED`** → procedi con `selected_backend`; emetti `[Fase 0] BACKEND_RESOLVED: <backend>`.

   **`BACKEND_DEGRADED`** → procedi con `selected_backend` (fallback già scelto); emetti
   marker degrado + motivo; se `oracle_handoff: true` annota remediation per Fase 4.

   **`BACKEND_UNAVAILABLE_STRICT`** → **STOP con gate umano** (INV-2 + `degrade_policy: strict`):
   ```
   [Fase 0] BACKEND_UNAVAILABLE_STRICT: <preferito> (<motivo>)
   Azione richiesta:
     (a) Autentica / configura backend <preferito> e rilancia /prototype
     (b) Abbassa degrade_policy: notify in factory.config.yaml
     (c) Cambia backend: <altro> in factory.config.yaml
   ```

**Criteri di uscita Fase 0**: marker emesso; `selected_backend` valorizzato (o STOP).
`resolved_marker` propagato a tutte le fasi successive.

---

## Fase 1 — Intent & Source

**Scopo**: costruire il brief — descrizione artefatto, stati UI, spec sorgente, token
art-director.

Prima di eseguire qualsiasi step, leggi obbligatoriamente
`.claude/skills/references/prototype-generation-protocol/fase1-intent-source-detail.md`.
STOP se il file manca. **(T2)**

Esegui in ordine: Step 1.1 (risolvi `input_ref` → Caso A/B/C), Step 1.2 (ricerca
`design-spec.md` INV-3 read-only), Step 1.3 (art-director DSL opt-in EP-019),
Step 1.4 (assembla `brief`). Dettaglio operativo nella foglia T2.

**Criteri di uscita Fase 1**: `brief` completo; `spec_source` valorizzato o `null`;
art-director determinato; `slug` e `output_path` pronti. Nessun file spec modificato (INV-3).

---

## Fase 2 — Generate

**Scopo**: produrre l'artefatto delegando alla skill `<backend>-mapping` per `selected_backend`.
Nessuna logica MCP, HTML, React nel corpo — delega totale (ADR-EP035-003 GO).

1. Identifica la skill da invocare:

   | `selected_backend` | Skill invocata |
   |---|---|
   | `html` | `.claude/skills/html-prototype-mapping.md` (TSK-231) |
   | `react` | `.claude/skills/react-prototype-mapping.md` (US-124, futuro) |
   | `figma` | `.claude/skills/figma-mapping.md` (US-126, futuro) |
   | `penpot` | `.claude/skills/penpot-mapping.md` (US-127, futuro) |

   Skill non trovata → **STOP**: `[Fase 2] Skill <backend>-prototype-mapping non trovata.`

2. Invoca `<backend>-mapping` con il `brief` completo (output Fase 1) + accesso read-only
   a `spec_source` (INV-3 responsabilità anche della mapping).

3. La skill ritorna (schema minimo):
   ```yaml
   output_ref: <path file generato | riferimento artefatto>
   backend: <html | react | figma | penpot>
   marker: <backend-specifico>
   artifact_metadata: <yaml — dipende dal backend>
   ```

4. Errore mapping → `[Fase 2] Generazione fallita (backend: <backend>): <motivo>` + STOP.

**Criteri di uscita Fase 2**: `output_ref` valorizzato; `marker` emesso; `artifact_metadata`
disponibile. Nessuna logica backend-specifica nel corpo.

---

## Modalità varianti divergenti (opt-in, `variants` > 1)

Con `prototyping.variants` (default 1) o `--variants N` > 1 (ammesso 2..5; oltre 5 rifiuto
esplicito) la Fase 1 chiude con N direzioni nominate su un asse, la Fase 2 genera N
varianti funzionanti dietro un selettore neutro (html: un solo file, INV-6) e la scelta
resta umana o di un reviewer separato (INV-4). Prima di procedere leggi obbligatoriamente
`.claude/skills/references/prototype-generation-protocol/varianti.md`; STOP se manca.
Con `backend: auto` la catena si restringe a `html` (unico backend con selettore) prima della
Fase 0. Con `variants: 1` la foglia non si legge e nulla cambia.

---

## Fase 3 — Self-contain check

**Scopo**: verificare invarianti meccaniche prima dell'emissione definitiva.
Nessuna valutazione qualitativa estetica o funzionale (INV-4).

Per il `selected_backend`, prima di valutare i check leggi obbligatoriamente
`.claude/skills/references/prototype-generation-protocol/fase3-self-contain-checks.md`.
STOP se il file manca; non emettere `PROTOTYPE_GENERATED`. **(T3)**

Se tutti i check passano:
```
PROTOTYPE_GENERATED: <output_ref>
```
Il marker `PROTOTYPE_GENERATED` è l'unico emesso — mai se anche un solo check è fallito.

**Criteri di uscita Fase 3**: `PROTOTYPE_GENERATED` emesso; tutti i check superati; INV-4.

---

## Fase 4 — Handoff

**Scopo**: registrare nel log, notificare stato TSK/US, orientare verso reviewer/oracle.
**INV-4 (enforced)**: nessuna valutazione qualitativa — né in chat né nel log.

### Passo 4.1 — Log entry (INV-4 enforcement)

Scrivi log entry in `wiki/log.md` (o `prototyping_config.log_path`). Template completo in
`.claude/skills/references/prototype-generation-protocol/fase4-handoff-steps.md §Step 4.1`.
Se la foglia manca: usa formato minimo `[prototype-generation-protocol] TSK-<id>` —
**NON saltare l'entry**. Log scritto sempre, indipendentemente da `oracle_handoff`.

### Step 4.2 — Notifica status TSK/US

`tsk_id` valorizzato → non modificare il TSK (ownership dev-agent); segnala:
`[Fase 4] Prototipo generato per TSK-NNN. Aggiorna lo status se era il deliverable.`
`tsk_id: null` → segnala solo `[Fase 4] Prototipo generato: <output_ref>`.

### Step 4.3 — Guard `oracle_handoff`

```
SE oracle_handoff == false:
  Emetti "[Fase 4] oracle_handoff: false — suggerimenti soppressi." → criteri di uscita.
```

### Step 4.4 — Gate installazione comandi

```
SE .claude/commands/<comando>.md non esiste: sopprimi silenziosamente il suggerimento.
```

Prima di emettere suggerimenti downstream, leggi
`.claude/skills/references/prototype-generation-protocol/fase4-handoff-steps.md`.
Se manca: suggerimenti soppressi; Passo 4.1 resta obbligatorio (RR-2 mitigazione). **(T4)**

**Criteri di uscita Fase 4**: log appended (sempre); suggerimenti per backend e gate;
segnale push EP-033 se trigger; INV-3 + INV-4.

---

## Output finale del protocollo

```
PROTOTYPE GENERATION — <input_ref>              (esito positivo)
===================================
Fase 0 — Backend:    <resolved_marker>: <selected_backend>
Fase 1 — Source:     <spec_source | "intent only"> / art-director: <on|off>
Fase 2 — Generate:   <backend>-mapping → <marker-mapping>
Fase 3 — Check:      PROTOTYPE_GENERATED: <output_ref>
Fase 4 — Handoff:    log entry scritto · suggerimenti: <N>
```

```
PROTOTYPE GENERATION — STOP                     (gate umano o errore)
===========================
Fase <N> — <motivo>
Azione richiesta: <descrizione>
```

---

## Invarianti

- **INV-1**: `html` fallback terminale garantito da `backend-resolver` — nessun hard-fail.
- **INV-2**: nessun blocco su MCP non autenticato salvo `degrade_policy: strict`.
- **INV-3**: nessuna modifica a `design-spec.md` o spec sorgente (read-only ovunque).
- **INV-4**: nessuna auto-valutazione qualitativa — né in chat né nel log.
- **INV-5**: `prototyping.enabled: false` → zero output, zero side-effect, zero artefatti.
- **INV-6**: `single_file: true` per html non overridabile; fallisce in Fase 3.

---

## Vincoli di esecuzione

- **Provider-agnostic**: nessuna logica MCP/HTML/React nel corpo; tutto nella skill delegata.
- **Nessun design inventato**: spec insufficiente → `intent_text`; `<!-- PLACEHOLDER -->` unico ok.
- **Criteri di uscita espliciti**: mai proseguire senza condizione documentata soddisfatta.
- **Mai fallimento silenzioso**: ogni percorso emette marker o STOP esplicito.

---

## Cross-link

- **Skill invocate**: `backend-resolver` (Fase 0) · `html-prototype-mapping` · `react-prototype-mapping`
  (US-124) · `figma-mapping` (US-126) · `penpot-mapping` (US-127)
- **Foglie**: `references/prototype-generation-protocol/` — `input-schema.md` (T1) ·
  `fase1-intent-source-detail.md` (T2) · `fase3-self-contain-checks.md` (T3) · `fase4-handoff-steps.md` (T4) ·
  `varianti.md` (solo `variants` > 1)
- **Callers**: `agents/prototype-generator.md` · `commands/prototype.md`
- **Config**: `factory.config.yaml` `prototyping:` + `design_intelligence:`; **PATTERN §26**

[^src: wiki/concepts/prototype-generation-capability.md — wiki/syntheses/ep-035-prototype-generation-integration.md — management/kanban/EP-035/US-122.md — .claude/skills/backend-resolver.md — .claude/skills/html-prototype-mapping.md]
