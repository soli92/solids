---
name: prototype
description: "Genera un prototipo grafico a partire da US-id, TSK-id o intent libero (EP-035, PATTERN §26 candidato). Lancia prototype-generator con il target validato. Gated su prototyping.enabled. Supporta --variants N (2..5, varianti divergenti), --dry-run (backend-resolver Fase 0 senza generazione), --backend esplicito e --fidelity override."
argument-hint: "<US-id|TSK-id|\"intent libero\"> [--backend=html|react|figma|penpot] [--fidelity=static|interactive|animated] [--variants=N] [--dry-run]"
allowed-tools: Read, Write, Edit, Glob, Bash
---

# /prototype

Argomenti utente: `$ARGUMENTS`

Genera un prototipo grafico o funzionale a partire da uno dei seguenti input:

- **US-id** (`US-NNN`) — storia utente come sorgente di intent e spec
- **TSK-id** (`TSK-NNN`) — task kanban come sorgente di intent (risale alla US per contesto)
- **stringa libera** (es. `"form di login con stato errore e loading"`) — intent diretto

Il comando valida l'input, applica i flag opzionali e lancia l'agente `prototype-generator`
che esegue il `prototype-generation-protocol` (5 fasi).

---

## Sintassi

```
/prototype <US-id|TSK-id|"intent"> [--backend=html|react|figma|penpot] [--fidelity=static|interactive|animated] [--variants=N] [--dry-run]
```

| Argomento / Flag | Tipo | Default | Descrizione |
|---|---|---|---|
| `<input>` | obbligatorio | — | US-id, TSK-id o stringa libera di intent |
| `--backend=<b>` | opzionale | `auto` (da config) | Forza un backend specifico per questa invocazione (override one-shot) |
| `--fidelity=<f>` | opzionale | `auto` (da config) | Forza un livello di fedelta' per questa invocazione (override one-shot) |
| `--variants=N` | opzionale | `1` (da config `prototyping.variants`) | N direzioni divergenti (2..5) dietro un selettore neutro; oltre 5 rifiuto esplicito; `1` = comportamento invariato (override one-shot) |
| `--dry-run` | flag | off | Invoca solo la Fase 0 (backend-resolver) senza generare artefatti |

---

## Procedura

### Step 0 — Gate `prototyping.enabled` (precondizione assoluta)

Prima di qualsiasi altra azione, leggi `factory.config.yaml` e controlla il flag:

```
SE factory.config.yaml.prototyping.enabled == false (default R.P3):
  STOP — non invocare l'agente, non generare artefatti, nessun side-effect.
  Emetti in chat:
    "[/prototype] Layer spento: prototyping.enabled: false (R.P3 default off).
     Per abilitare il Prototype Generation Layer:
       1. Aggiungi / aggiorna factory.config.yaml:
            prototyping:
              enabled: true
              backend: auto
              fallback_chain: [figma, penpot, react, html]
              degrade_policy: notify
       2. Esegui /prototype-status per verificare la disponibilita' dei backend.
       3. Ri-lancia /prototype <input>."
```

Non emettere un STOP silenzioso: l'errore deve essere esplicito e orientare l'azione.

Se `prototyping.enabled: true`, prosegui.

### Step 1 — Parse argomenti

Dall'input `$ARGUMENTS` estrai:

- `raw_input` — la stringa grezza (primo argomento non-flag)
- `override_backend` — valore di `--backend` se presente, altrimenti `null`
- `override_fidelity` — valore di `--fidelity` se presente, altrimenti `null`
- `override_variants` — intero di `--variants` se presente, altrimenti `null`
- `dry_run` — `true` se `--dry-run` e' presente, altrimenti `false`

Validazione flag:

- `--backend` deve essere uno tra `html | react | figma | penpot`. Se il valore non e'
  riconosciuto: STOP — «Valore --backend non valido: <v>. Valori ammessi: html, react, figma, penpot.»
- `--fidelity` deve essere uno tra `static | interactive | animated`. Se il valore non e'
  riconosciuto: STOP — «Valore --fidelity non valido: <v>. Valori ammessi: static, interactive, animated.»

- `--variants` (anche `--variants N`) deve essere un intero. Se `N > 5`: STOP —
  «Valore --variants non ammesso: <N>. Massimo 5 (oltre, il confronto si diluisce). Usa un valore 2..5.»
  Se non intero o `< 1`: STOP — «Valore --variants non valido: <v>. Valori ammessi: interi 2..5 (1 = modalita' spenta).»

Se nessun argomento e' stato fornito (stringa vuota):

```
[/prototype] Input mancante.

Utilizzo: /prototype <US-id|TSK-id|"intent"> [--backend=html|react|figma|penpot] [--fidelity=static|interactive|animated] [--variants=N] [--dry-run]

Esempi:
  /prototype US-122
  /prototype TSK-235
  /prototype "form di login con stato errore e loading"
  /prototype US-122 --backend=html --dry-run

Fornisci un US-id, un TSK-id o una descrizione dell'intent da prototipare.
```

### Step 2 — Validazione e risoluzione `raw_input`

Determina il tipo di input e valida:

**Caso A — US-id** (pattern `US-\d+`, es. `US-122`):

1. Cerca il file US con `Glob management/kanban/**/US-<NNN>*/US-<NNN>.md`.
2. Se 0 match: STOP — «US-<NNN> non trovata. Verifica che il file esista in
   management/kanban/** prima di procedere.»
3. Se > 1 match: STOP — «US-<NNN> trovata in piu' path — ambiguita'. Specifica il
   path completo come intent o risolvi l'ambiguita'.»
4. Se 1 match: `input_ref = "US-NNN"` (canonico), `input_type = "us_id"`,
   `input_file = <path trovato>`. Segnala in chat: `[/prototype] Trovata: <path>`.

**Caso B — TSK-id** (pattern `TSK-\d+`, es. `TSK-235`):

1. Cerca il file TSK con `Glob management/kanban/**/TSK-<NNN>.md`.
2. Se 0 match: STOP — «TSK-<NNN> non trovato. Verifica che il file esista in
   management/kanban/** prima di procedere.»
3. Se > 1 match: STOP — «TSK-<NNN> trovato in piu' path — ambiguita'.»
4. Se 1 match: `input_ref = "TSK-NNN"` (canonico), `input_type = "tsk_id"`,
   `input_file = <path trovato>`. Segnala in chat: `[/prototype] Trovato: <path>`.

**Caso C — Stringa libera** (nessun pattern US/TSK riconosciuto):

- `input_ref = <raw_input>` (stringa diretta), `input_type = "free_intent"`,
  `input_file = null`.
- Nessuna ricerca su filesystem.
- La stringa viene passata come intent diretto al generatore.

### Step 3 — Applicazione override one-shot

Se `override_backend`, `override_fidelity` o `override_variants` sono valorizzati, costruisci il blocco
`prototyping_override` da passare all'agente:

```yaml
prototyping_override:
  backend: <override_backend | null>    # null = usa config factory
  fidelity: <override_fidelity | null>  # null = usa config factory
  variants: <override_variants | null>  # null = usa config factory (default 1)
```

Gli override sono **one-shot per questa invocazione**: non modificano
`factory.config.yaml`. Segnala in chat:
`[/prototype] Override one-shot: backend=<b> fidelity=<f> variants=<n>`.
Con `variants` > 1 il protocollo legge `varianti.md` e si ferma alla scelta (INV-4).

### Step 4 — Modalita' `--dry-run`

Se `dry_run: true`:

1. Leggi il blocco `prototyping:` di `factory.config.yaml` (inclusa `fallback_chain`
   e `degrade_policy`).
2. Se `override_backend` e' valorizzato, considera quel backend come preferito
   (ASSE 1 del resolver).
3. Invoca la skill `backend-resolver` in modalita' dry-run:
   - `intent` — derivato da `input_ref` (per US/TSK: usa il titolo; per intent libero:
     usa la stringa direttamente)
   - `prototyping_config` — blocco `prototyping:` di config + eventuale override backend
4. Prima di comporre il display dry-run, leggi obbligatoriamente
   `.claude/commands/references/prototype/output-formats.md` §Dry-run display.
   Se il file manca, STOP e segnala.
5. Termina — nessuna invocazione dell'agente, nessun side-effect.

### Step 5 — Invocazione `prototype-generator`

Se non e' dry-run, lancia l'agente `prototype-generator` passando:

```yaml
input_ref: <input_ref>          # US-NNN | TSK-NNN | "stringa libera"
input_type: <us_id|tsk_id|free_intent>
prototyping_override:           # null se nessun override one-shot
  backend: <override_backend | null>
  fidelity: <override_fidelity | null>
  variants: <override_variants | null>
```

L'agente legge autonomamente da `factory.config.yaml` i blocchi `prototyping:` e
`design_intelligence:` ed esegue il `prototype-generation-protocol` (5 fasi):

| Fase | Nome | Azione |
|---|---|---|
| 0 | Backend Resolve | Invoca `backend-resolver` → `BACKEND_RESOLVED` / `BACKEND_DEGRADED` / `BACKEND_UNAVAILABLE_STRICT` |
| 1 | Intent & Source | Leggi US/TSK/intent + cerca `design-spec.md` + risolvi art-director DSL (EP-019) |
| 2 | Generate | Invoca `<selected_backend>-mapping` con il brief |
| 3 | Self-contain check | Verifica invarianti meccaniche (INV-6 per html; stati coperti; no dipendenze rotte) |
| 4 | Handoff | Append `wiki/log.md`; suggerimenti oracle/reviewer downstream |

### Step 6 — Output finale

Prima di emettere l'output finale (positivo/degrado/STOP), leggi obbligatoriamente
`.claude/commands/references/prototype/output-formats.md` §Output finale + §Suggerimenti handoff.
Se il file manca, STOP e segnala.

---

## Vincoli

- **Gate `prototyping.enabled`** (Step 0): il comando non procede e non e' silenzioso
  a flag spento — emette un errore esplicito con le istruzioni di attivazione (mai STOP
  silenzioso, INV-5 + R.P3).
- **Override one-shot** (Step 3): `--backend`, `--fidelity` e `--variants` non modificano
  `factory.config.yaml`. Per cambiare la config in modo persistente, edita direttamente
  il file.
- **Varianti** (`--variants`): massimo 5, rifiuto esplicito oltre; la scelta fra le varianti
  non e' mai del comando ne' dell'agente (INV-4).
- **Read-only verso spec sorgente** (INV-3): il comando e l'agente invocato non
  modificano `design-spec.md`, file TSK, file US.
- **No auto-eval** (INV-4): il comando non esprime giudizi qualitativi sull'artefatto
  generato. La valutazione e' delegata a oracle/reviewer downstream.
- **Input mancante**: non procede a indovinare l'intent — chiede esplicitamente
  (Step 1).
- **Ambiguita' US/TSK**: se glob trova piu' di un match per lo stesso id, STOP
  con errore — non seleziona arbitrariamente.

---

Contenuti consultivi non vincolanti: esempi d'uso, prerequisiti operatore e cross-link
informativi sono in `.claude/commands/references/prototype/appendice.md`.
Se il file manca: segnala con WARNING e prosegui — il flusso non dipende da questa foglia.
