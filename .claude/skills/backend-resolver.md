# Skill: Backend Resolver

> Adapter Cursor della skill `backend-resolver` definita in PATTERN.md.
>
> Metadata originale — name: backend-resolver; epic_id: EP-035; pattern_version: 2.25. Descrizione: risolve il backend di prototipazione ottimale in due assi indipendenti — ASSE 1 (intent utente → backend preferito) e ASSE 2 (availability probe a runtime) — percorrendo la fallback_chain da config e scegliendo il primo backend che soddisfa (asse1 ∩ asse2). Single source of truth condivisa da prototype-generation-protocol (Fase 0) e /prototype-status (EP-035, PATTERN §26). Read-only, pura funzione.

**Skill — backend-resolver**

Pura funzione di risoluzione: dato l'intent utente e la configurazione `prototyping:` in
`factory.config.yaml`, ritorna il **backend selezionato** insieme al marker esplicito di
esito (`BACKEND_RESOLVED`, `BACKEND_DEGRADED`, oppure `BACKEND_UNAVAILABLE_STRICT`).
E' la **single source of truth** (analogia R.B9 di EP-034): [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md)
(Fase 0) e `/prototype-status` la invocano entrambi, cosi' non esistono due logiche di
risoluzione divergenti.

**Read-only (INV-2)**: non esegue OAuth, non modifica file di config, non fa checkout,
non scrive su filesystem. Solo legge config, frontmatter e lo stato osservabile degli MCP
server. Non ha side-effect.

**Precondizione `prototyping.enabled`**: se `prototyping.enabled: false` (default R.P3),
la skill non viene invocata da nessun protocollo — nessun comportamento visibile.
La factory v2.25 e' identica a flag spento (backward compat totale, INV-5).

---

## Input

- `intent` — esigenza espressa dall'utente, una stringa tra:
  - `"preview veloce"` (o `"preview veloce condivisibile"`)
  - `"componente production-ready"`
  - `"file di design editabile"`
  - `"auto"` — lascia decidere al resolver senza preferenza espressa
  - oppure il backend esplicitato direttamente (`"html"`, `"react"`, `"figma"`, `"penpot"`)
- `prototyping_config` — blocco `prototyping:` di `factory.config.yaml`:
  - `backend` — `auto | html | react | figma | penpot`
  - `fallback_chain` — lista ordinata di backend, es. `[figma, penpot, react, html]`
  - `degrade_policy` — `notify` (default) | `strict`

## Output

```yaml
selected_backend: <html | react | figma | penpot>
marker: <BACKEND_RESOLVED | BACKEND_DEGRADED | BACKEND_UNAVAILABLE_STRICT>
preferred_backend: <backend>          # backend richiesto da asse1
degraded_from: <backend | null>       # non-null solo se BACKEND_DEGRADED
reason: <stringa motivo>              # es. "MCP figma non autenticato"
asse1_match: <backend | null>         # backend che asse1 avrebbe scelto, null se auto
asse2_probes: {figma: bool, penpot: bool, react: bool, html: true}
```

---

## Step 1 — Guard `prototyping.enabled`

Verifica che `prototyping.enabled: true`. Se `false`:

- Non procedere. Emetti nessun output.
- Il caller (prototype-generation-protocol / /prototype-status) mostra:
  `[backend-resolver] Skipped: prototyping.enabled: false (R.P3 default off)`

## Step 2 — ASSE 1: Intent → backend preferito

Mappa l'intent al backend preferito secondo la tabella seguente:

| Intent (stringa utente o alias) | Backend preferito (ASSE 1) |
|---|---|
| `"preview veloce"` / `"preview veloce condivisibile"` | `html` |
| `"componente production-ready"` | `react` |
| `"file di design editabile"` | `figma` (poi `penpot` come alternativa paritaria) |
| `"auto"` | nessuna preferenza — percorre la `fallback_chain` in ordine |
| backend esplicito (`"html"`, `"react"`, `"figma"`, `"penpot"`) | il backend dichiarato |

Se `prototyping_config.backend` e' un valore esplicito diverso da `auto`, usa quello come
`preferred_backend` (override sul parametro `intent`). Se `backend: auto`, usa la mappa
sopra applicata all'`intent` ricevuto.

Nota: `"file di design editabile"` preferisce `figma` ma accetta `penpot` come equivalente
(entrambi producono un file di design editabile dal designer). Il resolver controlla `figma`
prima se `figma` precede `penpot` nella `fallback_chain`; viceversa se `penpot` e' prima.

Output di questo step: `preferred_backend` (la scelta di ASSE 1, o `null` se `auto` puro
senza preferenza).

## Step 3 — ASSE 2: Availability probe a runtime

Per ciascun backend nella `fallback_chain`, esegui il probe di disponibilita'. I probe
sono **read-only** e non producono side-effect.

| Backend | Probe di disponibilita' | Disponibile se |
|---|---|---|
| `figma` | Controlla se MCP server "figma" e' raggiungibile E autenticato (sessione OAuth attiva) | server raggiungibile AND autenticazione valida. **In sessione non-interattiva**: se non autenticato, tratta come non disponibile (la skill non puo' fare OAuth — INV-2). |
| `penpot` | Controlla se MCP server "penpot" e' raggiungibile (istanza configurata) | server raggiungibile (autenticazione non richiesta per la sola connettivita' iniziale — vedi `penpot-mapping` per i dettagli). |
| `react` | Invoca `stack-detector` sul primo `code_path` con `layers` che include `fe` in `factory.config.yaml` | `stack-detector` trova un framework FE (react, vue, svelte, next, ecc.) in almeno un `code_path`. **Se `code_paths: []` o nessun code_path ha layer `fe`**: `stack-detector` non viene invocato — il probe restituisce `false` (UNAVAILABLE) e il resolver degrada al backend successivo nella `fallback_chain` emettendo `BACKEND_DEGRADED: react→html (nessun code_path configurato — stack-detector non invocato)`. **Nota meta-framework**: in questo repo (`code_paths: []`) il probe react restituisce sempre `false` → `BACKEND_DEGRADED: react→html`. |
| `html` | Nessun probe — sempre disponibile | **SEMPRE true** (fallback terminale, INV-1). |

**Nota provider-agnostic**: la logica MCP-specifica (es. come verificare l'autenticazione
Figma, come testare la connettivita' Penpot) e' delegata ai rispettivi `*-mapping`
(figma-mapping, penpot-mapping). Il resolver riceve dal caller solo il risultato booleano
del probe; non conosce i dettagli di implementazione MCP.

Output di questo step: `asse2_probes` — mappa `{backend: bool}` per ogni backend nella
`fallback_chain` (piu' `html: true` sempre).

## Step 4 — Risoluzione: percorri la `fallback_chain`

Percorri la `fallback_chain` nell'ordine dichiarato in config. Per ciascun backend:

1. Controlla `asse2_probes[backend]` — se `false`, salta al successivo.
2. Se `preferred_backend` e' valorizzato (ASSE 1 ha una preferenza):
   - Se il backend corrente nella chain **coincide** con `preferred_backend` (o e' un
     equivalente accettabile per l'intent "file di design editabile") → **selezionato**.
   - Se il backend corrente e' diverso dal `preferred_backend` ma e' disponibile →
     e' un candidato di degrado (usato solo se `preferred_backend` non e' disponibile).
3. Se `preferred_backend` e' `null` (intent `"auto"` puro) → il primo backend disponibile
   nella chain e' il selezionato.

**Algoritmo completo**:

```
selected = null
preferred_available = false

PER OGNI backend IN fallback_chain:
  SE asse2_probes[backend] == true:
    SE preferred_backend == null:
      # auto puro: prendi il primo disponibile
      selected = backend
      BREAK
    SE backend == preferred_backend (o equivalente per "file di design editabile"):
      selected = backend
      preferred_available = true
      BREAK
    SE selected == null:
      # salva come primo disponibile di fallback (potenziale degrado)
      selected = backend  # ma non fare BREAK — cerca ancora il preferito

SE preferred_backend != null E preferred_available == false:
  # il preferito non era disponibile — selected e' il primo alternativo disponibile
  → degrado (vedi Step 5)
```

`html` e' sempre l'ultimo elemento nella `fallback_chain` per contratto (INV-1). Se non
appare esplicitamente, il resolver lo aggiunge implicitamente in fondo.

## Step 5 — Emissione marker

In base all'esito di Step 4, emetti il marker appropriato. I marker sono espliciti e
testualmente presenti nell'output del resolver — mai fallimento silenzioso (INV-2).

### `BACKEND_RESOLVED`

Il backend preferito (ASSE 1) e' disponibile (ASSE 2) — nessun degrado.

```
BACKEND_RESOLVED: <backend>
```

Esempio:

```
BACKEND_RESOLVED: react
```

### `BACKEND_DEGRADED`

Il backend preferito non e' disponibile — il resolver ha scelto il successivo disponibile
nella `fallback_chain`. Applicabile solo se `degrade_policy: notify` (default).

```
BACKEND_DEGRADED: <preferito>→<selezionato> (<motivo>)
```

Esempi:

```
BACKEND_DEGRADED: figma→html (MCP figma non autenticato — sessione OAuth assente)
BACKEND_DEGRADED: react→html (stack-detector non trova framework FE in nessun code_path)
BACKEND_DEGRADED: penpot→react (MCP penpot non raggiungibile — istanza non configurata)
```

Il motivo deve essere leggibile e orientativo: non un codice interno, ma una stringa
che il caller puo' mostrare all'utente o loggare nel wiki/log.md.

Dopo il marker `BACKEND_DEGRADED`, il resolver procede con il backend selezionato
(non si blocca). Il suggerimento di remediation (es. "per usare figma: autentica il
connettore Figma MCP") e' opzionale ed e' responsabilita' del caller o del
[prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) (Fase 0) includerlo nella risposta all'utente.

### `BACKEND_UNAVAILABLE_STRICT`

Applicabile solo se `degrade_policy: strict` E il backend preferito non e' disponibile.
Il resolver non sceglie un alternativo — STOP con gate umano.

```
BACKEND_UNAVAILABLE_STRICT: <preferito> (<motivo>)
```

Esempio:

```
BACKEND_UNAVAILABLE_STRICT: figma (MCP figma non autenticato — degrade_policy: strict richiede il backend preferito)
```

Il caller deve interrompere l'esecuzione e presentare il gate umano: l'utente sceglie
se (a) autenticare il backend e rilasciare, (b) abbassare `degrade_policy: notify`, o
(c) cambiare `backend:` nella config.

### Nessun backend disponibile (caso degenere)

Solo se `html` non e' nella `fallback_chain` e tutti gli altri backend sono indisponibili
(violazione INV-1). Il resolver emette:

```
BACKEND_UNAVAILABLE_STRICT: (tutti i backend della fallback_chain non disponibili — html assente dalla chain: violazione INV-1)
```

E' un caso di errore di configurazione: il caller deve segnalarlo all'utente.

---

## Vincoli

- **Read-only (INV-2)**: mai eseguire OAuth, mai modificare `factory.config.yaml`, mai
  fare `git checkout`. Solo lettura di config, frontmatter e stato osservabile MCP server.
- **Mai fallimento silenzioso**: ogni percorso di esecuzione emette un marker esplicito
  (`RESOLVED`, `DEGRADED`, o `UNAVAILABLE_STRICT`).
- **`html` sempre disponibile (INV-1)**: il resolver garantisce che `html: true` in
  `asse2_probes` — mai probe per `html`. Se manca dalla `fallback_chain`, viene aggiunto
  implicitamente in fondo.
- **Determinismo**: stesso input (intent + config + stato MCP) → stesso output.
  Nessuna euristica non riproducibile.
- **Provider-agnostic**: la logica MCP-specifica e' nei `*-mapping` (figma-mapping,
  penpot-mapping). Il resolver riceve solo i booleani di disponibilita'.

---

## Esempi di risoluzione

### Esempio 1 — preview veloce, html always-on

```
intent: "preview veloce"
backend: auto
fallback_chain: [figma, penpot, react, html]
degrade_policy: notify

→ ASSE 1: preferito = html
→ ASSE 2: html = true (sempre)
→ Selezione: html disponibile
→ BACKEND_RESOLVED: html
```

### Esempio 2 — componente production-ready, FE stack presente

```
intent: "componente production-ready"
backend: auto
fallback_chain: [figma, penpot, react, html]
degrade_policy: notify

→ ASSE 1: preferito = react
→ ASSE 2: react = true (stack-detector trova Next.js in code_paths)
→ Selezione: react disponibile
→ BACKEND_RESOLVED: react
```

### Esempio 2b — componente production-ready, code_paths vuoto (meta-framework reflexivo)

```
intent: "componente production-ready"
backend: auto
fallback_chain: [react, html]
degrade_policy: notify
code_paths: []

→ ASSE 1: preferito = react
→ ASSE 2: react = false (code_paths vuoto — stack-detector non invocato → UNAVAILABLE)
          html = true (sempre)
→ Selezione: html (primo disponibile — degrado)
→ BACKEND_DEGRADED: react→html (nessun code_path configurato — stack-detector non invocato)
```

### Esempio 3 — file di design editabile, Figma MCP non autenticato

```
intent: "file di design editabile"
backend: auto
fallback_chain: [figma, penpot, react, html]
degrade_policy: notify

→ ASSE 1: preferito = figma (primo nella chain tra figma|penpot)
→ ASSE 2: figma = false (MCP non autenticato), penpot = false (MCP non raggiungibile),
          react = false (no FE stack), html = true
→ Selezione: html (primo disponibile — degrado)
→ BACKEND_DEGRADED: figma→html (MCP figma non autenticato — sessione OAuth assente)
```

### Esempio 4 — backend figma esplicito, strict policy, MCP assente

```
intent: "figma"
backend: figma
fallback_chain: [figma, html]
degrade_policy: strict

→ ASSE 1: preferito = figma (backend esplicito)
→ ASSE 2: figma = false (MCP non autenticato)
→ degrade_policy: strict → STOP
→ BACKEND_UNAVAILABLE_STRICT: figma (MCP figma non autenticato — degrade_policy: strict richiede il backend preferito)
```

### Esempio 5 — auto puro, penpot disponibile

```
intent: "auto"
backend: auto
fallback_chain: [penpot, react, html]
degrade_policy: notify

→ ASSE 1: preferito = null (auto puro)
→ ASSE 2: penpot = true (MCP raggiungibile), react = false, html = true
→ Selezione: penpot (primo disponibile nella chain)
→ BACKEND_RESOLVED: penpot
```

---

## Cross-link

- PATTERN §26 «Prototype Generation Layer» (candidato) — config block `prototyping:`.
- Consumatori: [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 0, `/prototype-status`.
- Analogia strutturale: `branch-resolver` (EP-034, PATTERN §15) — stesso pattern di
  risoluzione adattiva con marker espliciti; `publisher-protocol` (v2.10) — stesso split
  provider-agnostic + `*-mapping` provider-specific.
- Dipendenze read-only: `stack-detector` (probe ASSE 2 per backend `react`),
  `figma-mapping` + `penpot-mapping` (dettagli probe MCP — non invocati direttamente qui,
  il caller li passa come booleani).
- [react-mapping](mdc:.cursor/skills/react-mapping/SKILL.md) (EP-035 US-124) — skill provider-specific per il backend `react`:
  traduce spec/intent in componenti React + storie Storybook + fixture dati.
  Invocata da [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 2 quando `selected_backend == react`.
  In questo meta-framework (`code_paths: []`) non viene mai invocata — il probe ASSE 2
  restituisce `false` e il resolver degrada a `html` prima di raggiungerla.
- Invarianti EP-035: INV-1 (`html` sempre disponibile), INV-2 (read-only, mai bloccare su
  MCP non autenticato), INV-5 (default off R.P3).
- Fonti: `wiki/concepts/backend-adaptive-prototyping.md`, `wiki/concepts/prototype-generation-capability.md`,
  `wiki/sources/2026-07-01-prototype-generation-capability.md §Resolver`.
