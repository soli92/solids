---
name: oracle-precheck
description: >-
  Skill interna (PATTERN §16/§19, EP-006 US-023, ADR-010 + ADR-012 §C) — gate deterministico
  pre-dispatch per TSK FE. Verifica le 4 condizioni (a)-(d) OR-aggregate (no LLM runtime) e
  ritorna {passed, satisfied_by, message}. Invocata dall'orchestrator solo con
  fe_correctness.dispatch_gate: true.
---
# Skill — Oracle Pre-Check

Riferimenti: ADR-010 §Decisione (euristica 4 segnali per la condizione (d), schema output,
logging), ADR-012 §C (skill path) + §A (frontmatter `interaction_test_spec` / `visual_reference`)
+ §E (config block `fe_correctness`), EP-006 US-023 (Orchestrator Oracle Gate).

Gate **deterministico** (grep / pattern matching, **no LLM judgment runtime**) che attesta la
presenza di **almeno un** oracolo per un TSK `layer: fe` prima del dispatch. È la skill interna
invocata dall'orchestrator (sezione «Oracle Pre-Check FE»). Verifica TUTTE e 4 le condizioni
(a)-(d), non solo la (d) — il nome riflette l'intero scope di pre-check oracolo (ADR-010
Rationale §6).

## Trigger

La skill viene invocata dall'orchestrator **se e solo se** entrambe le condizioni sono vere:

1. `factory.config.yaml.fe_correctness.dispatch_gate: true`, **AND**
2. il TSK target ha `layer: fe` nel frontmatter.

Input: il TSK-id (l'orchestrator passa il path/identità del TSK; la skill legge frontmatter +
body + `factory.config.yaml` + verifica presenza file su filesystem).

Se anche una sola delle due condizioni di trigger non è soddisfatta, la skill **non viene
invocata** (vedi «Backward compat»).

## 4 condizioni verificate (a)-(d) — OR aggregato

Le 4 condizioni sono valutate **in OR**: basta soddisfarne **una sola** perché `passed: true`.
La valutazione è ordinata (a) → (b) → (c) → (d) e si **short-circuita** al primo match (la prima
condizione soddisfatta determina `satisfied_by`). La (d) è la terza linea di difesa (dopo a-c) e
ha al suo interno 4 segnali a loro volta OR-aggregati (ADR-010 §Decisione).

### Condizione (a) — config flag + skill scaffoldata

`factory.config.yaml.fe_correctness.enabled: true` **AND** il file
`.claude/skills/visual-oracle-protocol.md` è presente sul filesystem.

→ `satisfied_by: "cond:a"`.

### Condizione (b) — DoD FE checklist

Il body del TSK contiene una sezione con header H2 esatto `## DoD FE — stati obbligatori` che
ha **almeno una riga** checkbox checked, ossia che matcha `^\s*-\s+\[x\]\s+` (case-insensitive
su `x`).

→ `satisfied_by: "cond:b"`.

### Condizione (c) — interaction_test_spec valorizzato

Il frontmatter del TSK ha il campo `interaction_test_spec:` **valorizzato** — non assente, non
vuoto (`""` / solo whitespace), non `null`.

→ `satisfied_by: "cond:c"`.

### Condizione (d) — pattern matching deterministico a 4 segnali (ADR-010)

«AC con almeno un criterio visivo misurabile», implementata come **4 segnali OR-aggregati**.
Basta che **uno solo** dei 4 segnali matchi perché (d) sia soddisfatta. La valutazione dei
segnali è ordinata 1 → 2 → 3 → 4 e si short-circuita al primo match (il primo segnale determina
`signal:N=desc`).

- **Segnale 1 — wikilink design-token / componenti / source Figma**: presenza in qualunque
  parte del file TSK (body **o** frontmatter `wiki_page:`) di un wikilink che matcha uno dei
  pattern:
  - `wiki/concepts/design-token*` (concept design token specifico)
  - `wiki/entities/*` (entity di componente UI)
  - `wiki/sources/*figma*` (page sorgente Figma)
  → desc: `wikilink-design-token`.
- **Segnale 2 — path raw/images Figma frame**: presenza nel body del TSK di un riferimento a
  path `raw/images/*-figma-*-frame-*.md` (artefatto prodotto da `figma-sync` v2.9 per il
  frame-level capture).
  → desc: `figma-frame-path`.
- **Segnale 3 — block Visual Acceptance / Design Reference**: presenza di una sezione con
  header H2 esatto `## Visual Acceptance` **oppure** `## Design Reference` nel body del TSK.
  → desc: `visual-acceptance-section`.
- **Segnale 4 — frontmatter visual fields**: il frontmatter del TSK contiene
  `interaction_test_spec:` **o** `visual_reference:` **valorizzato** (non vuoto, non null).
  → desc: `frontmatter-visual-field`.

→ `satisfied_by: "cond:d, signal:N=desc"` (N ∈ {1,2,3,4}, desc come sopra).

> Nota: il segnale 4 può sovrapporsi alla condizione (c) (entrambi leggono
> `interaction_test_spec`). Per via dello short-circuit ordinato, se (c) matcha la skill ritorna
> `cond:c` e non raggiunge mai la (d). La (d)/signal:4 resta utile quando è valorizzato solo
> `visual_reference:` (che la (c) non considera). **Falsi negativi accettabili**: la (d) è
> l'ultima linea prima del fail-loud (ADR-010 Rationale §3).

## Schema output

La skill ritorna **sempre** un singolo oggetto JSON con questa forma verbatim:

```json
{
  "passed": true|false,
  "satisfied_by": "cond:a" | "cond:b" | "cond:c" | "cond:d, signal:N=desc" | null,
  "message": "<stringa>"
}
```

Valori possibili di `satisfied_by`:

- `"cond:a"` — soddisfatta dalla condizione (a).
- `"cond:b"` — soddisfatta dalla condizione (b).
- `"cond:c"` — soddisfatta dalla condizione (c).
- `"cond:d, signal:N=desc"` — soddisfatta dalla condizione (d), con `N` ∈ {1,2,3,4} e `desc`
  la descrizione del segnale: `signal:1=wikilink-design-token`, `signal:2=figma-frame-path`,
  `signal:3=visual-acceptance-section`, `signal:4=frontmatter-visual-field`.
- `null` — **nessuna** delle 4 condizioni soddisfatta (`passed: false`).

Esempio pass:

```json
{
  "passed": true,
  "satisfied_by": "cond:d, signal:3=visual-acceptance-section",
  "message": "Visual oracle implicito tramite block ## Visual Acceptance"
}
```

Esempio blocked:

```json
{
  "passed": false,
  "satisfied_by": null,
  "message": "Nessuna delle 4 condizioni (a)-(d) soddisfatta. Aggiungi: ..."
}
```

Gestione lato orchestrator: `passed: true` → procedi al dispatch del fe-dev;
`passed: false` → **fail-loud**, mostra `message` all'utente, non dispatchare.

## Messaggio di blocco

Quando `passed: false`, il campo `message` enumera le **4 strade** per aggiungere un oracolo al
TSK (una per ciascuna condizione). Forma verbatim:

```
Nessuna delle 4 condizioni (a)-(d) soddisfatta per <TSK-id> (layer: fe). Aggiungi un oracolo in uno dei 4 modi:
  (a) Abilita fe_correctness.enabled: true in factory.config.yaml (richiede .claude/skills/visual-oracle-protocol.md presente).
  (b) Aggiungi al TSK la sezione "## DoD FE — stati obbligatori" con almeno una riga checkata "- [x]".
  (c) Valorizza il frontmatter interaction_test_spec: <path al test Playwright>.
  (d) Aggiungi un criterio visivo misurabile: wikilink a wiki/concepts/design-token* | wiki/entities/<componente> | wiki/sources/*figma*, oppure un path raw/images/*-figma-*-frame-*.md, oppure una sezione "## Visual Acceptance" / "## Design Reference", oppure il frontmatter visual_reference: valorizzato.
```

## Logging

Ogni invocazione (sia pass che blocked) viene loggata con **una riga append-only** in
`memory/episodic/oracle-gate.md` (creare il file se assente). Formato riga:

```
YYYY-MM-DD | TSK-id | passed|blocked (cond:X, signal:N=desc) | message
```

- `YYYY-MM-DD` — data dell'invocazione.
- `TSK-id` — id del TSK valutato.
- `passed (cond:X)` su esito positivo, dove `cond:X` ∈ `{cond:a, cond:b, cond:c, cond:d}`; per
  la (d) si aggiunge `, signal:N=desc` (es. `passed (cond:d, signal:1=wikilink-design-token)`).
- `blocked` su esito negativo (`satisfied_by: null`, niente `cond:`/`signal:`).
- `message` — la stringa del campo `message` dell'output (su esito blocked, può essere troncata
  alla prima riga per leggibilità del log).

Esempi:

```
2026-06-03 | TSK-042 | passed (cond:d, signal:3=visual-acceptance-section) | Visual oracle implicito tramite block ## Visual Acceptance
2026-06-03 | TSK-043 | passed (cond:c) | interaction_test_spec valorizzato
2026-06-03 | TSK-044 | blocked | Nessuna delle 4 condizioni (a)-(d) soddisfatta. Aggiungi: ...
```

Il log abilita telemetria/calibrazione (ADR-010 Rationale §4): es. segnale mai usato → candidato
deprecation; segnale dominante → candidato a promozione a condizione (c).

## Backward compat

Con `fe_correctness.dispatch_gate: false` (**default**, opt-in totale ADR-012 §E) la skill
`oracle-precheck` **non viene mai invocata** dall'orchestrator → comportamento identico a
v2.16 (nessun gate, dispatch FE diretto). Lo stesso vale se il blocco `fe_correctness` è
del tutto assente da `factory.config.yaml`. Nessun campo frontmatter TSK nuovo è reso
obbligatorio. La skill è puramente additiva.

## Test coverage suggerita

Da US-023 §DoD + ADR-010 §Conseguenze:

- **4 TSK FE con un solo segnale (d) ciascuno** → tutti `passed: true`, con
  `satisfied_by` rispettivamente `cond:d, signal:1=...`, `signal:2=...`, `signal:3=...`,
  `signal:4=...` (un TSK per segnale, gli altri 3 segnali assenti).
- **1 TSK FE senza alcun segnale** (né a, b, c, d) → `passed: false`, `satisfied_by: null`,
  `message` con le 4 strade.

Casi addizionali consigliati per robustezza:

- TSK con condizione (a) attiva (`enabled: true` + skill presente) → `cond:a`.
- TSK con `enabled: true` ma `visual-oracle-protocol.md` assente → (a) NON soddisfatta
  (richiede entrambi); fallback alle altre condizioni.
- TSK con sezione `## DoD FE — stati obbligatori` ma **tutte righe unchecked** `- [ ]` →
  (b) NON soddisfatta.
- TSK con `interaction_test_spec: ""` (vuoto) o `null` → (c) NON soddisfatta.
- Short-circuit: TSK che soddisfa sia (c) che (d)/signal:4 → ritorna `cond:c` (ordine
  a → b → c → d).
- Backward compat: `dispatch_gate: false` → skill non invocata (verifica a livello orchestrator,
  non della skill).
- Idempotenza: stessa coppia (TSK immutato, config immutata) → stesso output (gate deterministico,
  no LLM).
- Logging: ogni invocazione produce **esattamente una** riga append in
  `memory/episodic/oracle-gate.md` nel formato dichiarato.

## Non in scope per questa skill

- **Eseguire il visual oracle** (render headless, screenshot, critic) — scope di
  `visual-oracle-protocol` (US-017). `oracle-precheck` è solo un gate pre-dispatch.
- **Dispatchare il fe-dev** — la skill ritorna `{passed, satisfied_by, message}`; è
  l'orchestrator che decide (procedi / fail-loud).
- **Modificare il TSK o la config** — read-only su frontmatter, body, `factory.config.yaml` e
  filesystem; l'unico side effect è l'append al log `memory/episodic/oracle-gate.md`.
- **LLM judgment** — l'euristica è interamente deterministica (grep / pattern matching),
  ripetibile e auditabile (ADR-010 Rationale §1).
