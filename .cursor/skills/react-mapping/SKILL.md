# Skill: React Mapping

> Adapter Cursor della skill `react-mapping` definita in PATTERN.md.
>
> Metadata originale — name: react-mapping; epic_id: EP-035; us_id: US-124; pattern_version: 2.25. Descrizione: mapping provider-specific per il backend react (T1) del Prototype Generation Layer (EP-035, PATTERN §26 candidato). Definisce come generare componenti React (.tsx/.jsx), storie Storybook e fixture dati dato uno spec/intent in input. Invocata da prototype-generation-protocol Fase 2 quando selected_backend == react. Produce artefatti production-ready handoff-ready per fe-dev.

**Mapping React (provider-specific per backend react T1)**

Riferimenti: [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) (probe ASSE 2 per `react` usa `stack-detector`),
[prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) (Fase 2 invoca questa skill), PATTERN §26 candidato
(Prototype Generation Layer), [html-prototype-mapping](mdc:.cursor/skills/html-prototype-mapping/SKILL.md) (analogia strutturale — stesso
pattern provider-specific), `stack-detector` (v2.12, condivisa con code-reviewer).

Questa skill e' **provider-specific per il backend `react`**: definisce come trasformare
uno spec/intent in un componente React (`.tsx`/`.jsx`) con sistema di design, storie
Storybook e fixture dati per ogni stato UI dichiarato nella spec. Il
[prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) non conosce i dettagli di questa skill — la invoca
passando input strutturato e riceve in output i path dei file generati.

---

## Nota meta-framework — Questo repo (code_paths: [])

In questo repository la lista `code_paths` e' vuota (configurazione reflexive
meta-framework senza target FE). Il probe ASSE 2 del [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) per il backend
`react` invoca `stack-detector` su tutti i `code_path` configurati: con lista vuota,
`stack-detector` non trova nessun framework FE — il probe ritorna `false`.

Di conseguenza in questo repo il resolver emette sempre:

```
BACKEND_DEGRADED: react→html (stack-detector non trova framework FE in nessun code_path)
```

e degrada al backend `html`. **Questa skill non viene mai eseguita in questo repo.**
E' un template per factory derivate che configurano uno o piu' `code_path` con stack FE
React/Next.js/Remix/ecc. Il [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) la selezionera' automaticamente quando
`stack-detector` trovera' un framework FE compatibile.

---

## Input

Ricevuto da [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 2 (come brief completo del Step 1.4):

```yaml
spec_source: <path>              # path al design-spec.md dell'ui-designer, oppure null
intent_text: <stringa>           # testo libero dell'utente se spec_source e' null
us_id: <US-NNN | null>           # US di riferimento se presente
tsk_id: <TSK-NNN | null>         # TSK di riferimento se presente
slug: <stringa>                  # identificatore slug per il path di output
output_path: <path>              # prototyping.output_path di factory.config.yaml
component_lib: <stringa>         # shadcn (default) | radix | mui | custom
                                 # letto da prototyping.backends.react.component_lib
storybook: <bool>                # true (default) — da prototyping.backends.react.storybook
target_code_path: <path | null>  # path del code_path target se prototyping.backends.react.target
                                 # e' configurato; null → scrive in output_path
tsx: <bool>                      # true se stack-detector ha rilevato TypeScript nel code_path
art_director_active: <bool>      # true se design_intelligence.art_director: true (EP-019)
art_director_tokens:             # presente solo se art_director_active: true
  palette: [...]
  font_family: "..."
  spacing_unit: "..."
  border_radius: "..."
  shadow: "..."
states_hint: [...]               # lista di stati UI richiesti dalla spec (opzionale)
```

Se `spec_source` e' valorizzato, leggi il file e estrai: nome componente, props attese,
stati UI (default/loading/error/empty/success/ecc.), varianti, layout. Se `spec_source`
e' null, usa `intent_text` come descrizione di alto livello e inferisci stati di default
ragionevoli.

---

## Output

```yaml
output_files:                    # lista path dei file generati
  - <base_path>/<slug>/<ComponentName>.tsx   # o .jsx se tsx: false
  - <base_path>/<slug>/<ComponentName>.stories.tsx  # solo se storybook: true
  - <base_path>/<slug>/<slug>-fixtures.ts    # o .js se tsx: false
backend: react
marker: REACT_GENERATED          # emesso solo dopo verifica invarianti in Fase F
component_lib_used: <stringa>    # shadcn | radix | mui | custom (valore effettivamente usato)
storybook_generated: <bool>      # true se il file .stories.* e' stato scritto
tsx_used: <bool>                 # true se i file sono .tsx/.ts, false se .jsx/.js
states_covered: [...]            # lista degli stati implementati nel componente
target_path_used: <path | null>  # null se output_path, altrimenti path del code_path target
```

Il marker `REACT_GENERATED` e' emesso solo dopo la verifica di tutte le invarianti in
Fase F. In caso di verifica fallita, la skill segnala il check fallito in chat senza
emettere il marker.

---

## Fase A — Lettura spec/intent

1. Se `spec_source` e' valorizzato:
   - Leggi il file `spec_source` (read-only, INV-3 — non modificarlo).
   - Estrai: nome componente/schermata, descrizione funzionale, lista stati UI,
     props attese (parametri di configurazione del componente), varianti di rendering,
     ARIA requirements se presenti, note sul sistema di design (se la spec li dichiara).
   - Se il file non esiste o e' vuoto: procedi con `intent_text` come fallback.
2. Se `spec_source` e' null o mancante:
   - Usa `intent_text` come descrizione del componente.
   - Deriva il nome componente dalla stringa intent o dallo `slug` (PascalCase).
     Esempio: `slug: "login-form"` → `ComponentName: LoginForm`.
   - Inferisci stati di default: `default`, `loading`, `error`, `empty` se non
     diversamente specificato dalla spec o dagli `states_hint`.
3. Combina gli `states_hint` ricevuti con gli stati estratti dallo spec. Deduplica.
   Ordine canonico: `default` → `loading` → `hover` → `active` → `focus` →
   `disabled` → `error` → `empty` → `success` → stati custom dichiarati nello spec.
4. Determina il nome canonico del componente (`ComponentName`) in PascalCase, derivato
   da: `spec_source` (titolo componente dichiarato) → `slug` (kebab-to-PascalCase) →
   `intent_text` (primi 2-3 token significativi in PascalCase).

---

## Fase B — Selezione component library

Scegli la component library in base a `component_lib` ricevuto in input. Il valore e'
gia' stato risolto dal caller ([prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) + [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md)):
riflette `prototyping.backends.react.component_lib` dalla config o il valore rilevato
da `stack-detector` nel `code_path` target se diverso.

| Valore `component_lib` | Comportamento |
|---|---|
| `shadcn` (default) | Importa da `@/components/ui/*` (convenzione shadcn/ui). Usa classi Tailwind CSS per stili. Aggiunge commento `// PROTOTYPE: shadcn/ui — installa con: npx shadcn@latest add <component>` per ogni import shadcn. |
| `radix` | Importa da `@radix-ui/react-*`. Usa stili inline o classi CSS Modules (se rilevati da `stack-detector`). Aggiunge commento `// PROTOTYPE: Radix UI — installa con: npm install @radix-ui/react-<component>`. |
| `mui` | Importa da `@mui/material`. Usa il theme provider se `stack-detector` rileva MUI gia' configurato. Aggiunge commento `// PROTOTYPE: MUI — installa con: npm install @mui/material`. |
| valore custom | Usa il valore as-is come namespace di import. Documenta nel log entry il valore usato. Aggiunge commento `// PROTOTYPE: <custom-lib> — verifica il path di import nel code_path target`. |

Se `art_director_active: true`, i token art-director vengono incorporati come CSS custom
properties (`--color-primary`, `--font-family`, ecc.) nel blocco `<style>` del
Storybook decorator o come overrides Tailwind theme nel componente, secondo il formato:

```typescript
// PROTOTYPE: art-director tokens applicati
// palette: <palette list>
// font: <font_family>
// radius: <border_radius>
// spacing: <spacing_unit>
```

Documenta nel log entry la scelta effettiva di `component_lib` (campo
`component_lib_used` nell'output YAML). Se `stack-detector` ha rilevato un DS diverso
da quello configurato in `component_lib`, la scelta del stack-detector ha priorita' e
viene annotata esplicitamente.

---

## Fase C — Generazione componente React

Genera il file componente (`<ComponentName>.tsx` o `<ComponentName>.jsx` a seconda
di `tsx`). Principi guida:

1. **Estensione file**: `.tsx` se `tsx: true`, `.jsx` se `tsx: false`. Il tipo viene
   determinato dal `stack-detector` che lo ha rilevato nel `code_path`.

2. **Struttura del file**: nell'ordine:
   - Commento di intestazione `// PROTOTYPE: <ComponentName> — generato da react-mapping`
   - Imports React (`useState`, `useEffect` se needed) e dalla component library
   - Definizione tipo `Props` (TypeScript) o JSDoc `@typedef` (se `tsx: false`)
   - Definizione tipo/enum `State` per l'unione degli stati
   - Definizione componente (funzione con named export)
   - Default export

3. **Prop `state`**: il componente accetta una prop `state?: State` (default `'default'`)
   che controlla quale variante viene resa. La prop e' opzionale — lo stato `'default'`
   e' sempre il rendering senza prop esplicita.

   ```typescript
   // PROTOTYPE: Props — adattare all'interfaccia reale del componente
   interface Props {
     state?: 'default' | 'loading' | 'error' | 'empty' | 'success'
     // PROTOTYPE: aggiungere le props reali della spec qui
   }
   ```

4. **Rendering condizionale**: usa `switch` su `state` per il rendering per stato, o
   un pattern di early return se gli stati hanno struttura molto diversa.

   ```typescript
   // PROTOTYPE: rendering condizionale per stato — adattare al layout della spec
   switch (state) {
     case 'loading': return <LoadingState />
     case 'error':   return <ErrorState />
     case 'empty':   return <EmptyState />
     case 'success': return <SuccessState />
     default:        return <DefaultState />
   }
   ```

5. **Placeholder semantici**: usa `{/* PROTOTYPE: <descrizione> */}` per le aree
   che il generatore non puo' riempire con contenuto reale (es. logica di business,
   dati dinamici, icone specifiche, callback reali). Analogia esatta con
   `<!-- PROTOTYPE: ... -->` del template HTML.

6. **ARIA base**: applica gli attributi ARIA minimi per il tipo di componente:
   - `role` appropriato per il tipo di elemento
   - `aria-label` su pulsanti senza testo visibile
   - `aria-live="polite"` sulle aree di feedback asincrono (error, success, loading)
   - `aria-busy={state === 'loading'}` se presente lo stato loading
   - `aria-disabled={state === 'disabled'}` se presente lo stato disabled

7. **No auto-valutazione (INV-4)**: il file generato non include commenti che
   valutano la qualita' del componente (es. "questo e' un buon design", "la
   struttura potrebbe essere migliorata"). I commenti `// PROTOTYPE:` sono
   esclusivamente segnaposto tecnici e istruzioni di adattamento.

8. **No import da URL**: tutti gli import sono relativi o da package npm (es.
   `@/components/ui/button`, `react`). Nessun import da URL `https://`.

---

## Fase D — Generazione storie Storybook

Eseguita solo se `storybook: true` (default).

Genera il file `<ComponentName>.stories.tsx` (o `.stories.jsx`). Struttura canonica:

1. **Meta**: configura il modulo Storybook con `title`, `component`, e `autodocs`.

   ```typescript
   // PROTOTYPE: <ComponentName>.stories — generato da react-mapping
   import type { Meta, StoryObj } from '@storybook/react'
   import { ComponentName } from './<ComponentName>'

   const meta = {
     title: 'Prototypes/<ComponentName>',
     component: ComponentName,
     tags: ['autodocs'],
     // PROTOTYPE: aggiungere decorators se necessario (es. ThemeProvider)
   } satisfies Meta<typeof ComponentName>

   export default meta
   type Story = StoryObj<typeof meta>
   ```

2. **Una storia per ogni stato in `states_covered`**: naming canonico.

   | Stato | Nome storia | Args |
   |---|---|---|
   | `default` | `Default` | `{ state: 'default' }` |
   | `loading` | `Loading` | `{ state: 'loading' }` |
   | `error` | `Error` | `{ state: 'error' }` |
   | `empty` | `Empty` | `{ state: 'empty' }` |
   | `success` | `Success` | `{ state: 'success' }` |
   | stato custom | PascalCase del nome | `{ state: '<nome>' }` |

   ```typescript
   export const Default: Story = {
     args: {
       state: 'default',
       // PROTOTYPE: aggiungere args rappresentativi dalla spec
     },
   }

   export const Loading: Story = {
     args: { state: 'loading' },
   }

   export const Error: Story = {
     args: {
       state: 'error',
       // PROTOTYPE: aggiungere args con dati di errore realistici dalla spec
     },
   }
   // ... una story per ogni stato in states_covered
   ```

3. **Args rappresentativi**: i dati nelle `args` di ogni storia sono derivati dalla
   spec (se presente) o dall'`intent_text`. Per gli stati con dati significativi (es.
   `error` con messaggio specifico, `success` con risultato), usa valori rappresentativi
   della spec — non lorem ipsum se la spec descrive dati reali.

4. **Autodocs**: il commento JSDoc minimale sul componente abilita la generazione
   automatica della documentazione Storybook. Aggiungi una riga di JSDoc nel componente:

   ```typescript
   /**
    * PROTOTYPE: <ComponentName> — <descrizione una riga dalla spec o dall'intent>.
    * @see <spec_source | "intent: <intent_text>">
    */
   ```

---

## Fase E — Fixture dati

Genera il file `<slug>-fixtures.ts` (o `<slug>-fixtures.js`) con dati rappresentativi
per ogni stato in `states_covered`.

Struttura:

```typescript
// PROTOTYPE: fixtures per <ComponentName> — generato da react-mapping
// Dati rappresentativi per ogni stato UI — adattare alla spec reale

export type FixtureState = 'default' | 'loading' | 'error' | 'empty' | 'success'
// PROTOTYPE: aggiungere gli stati custom dichiarati nella spec

export const fixtures: Record<FixtureState, /* PROTOTYPE: tipo dati della spec */> = {
  default: {
    // PROTOTYPE: dati stato default — derivati dalla spec o ragionevoli per il contesto
  },
  loading: {
    // PROTOTYPE: dati stato loading (tipicamente stessi del default + flag isLoading)
  },
  error: {
    // PROTOTYPE: dati stato error — usare messaggio realistico dalla spec
    // es: errorMessage: 'Errore di rete — riprova tra qualche istante'
  },
  empty: {
    // PROTOTYPE: dati stato empty — lista vuota, conteggio zero, ecc.
  },
  success: {
    // PROTOTYPE: dati stato success — risultato operazione completata
  },
}
```

Regole per i dati fixture:

1. **Dati realistici, non lorem ipsum**: se la spec descrive dati concreti (nomi,
   valori, messaggi di errore specifici), usali. Se la spec non li descrive,
   usa placeholder semantici (es. `"Mario Rossi"`, `42`, `"Errore di rete"`).
2. **Nessun dato sensibile o PII**: usa placeholder semantici, non dati reali di
   produzione (no email reali, no numeri di telefono, no codici fiscali).
3. **Tipizzazione TypeScript** (se `tsx: true`): il tipo del record e' derivato
   dalla spec. Se il tipo non e' determinabile, usa `Record<FixtureState, unknown>`
   con un commento `// PROTOTYPE: sostituire unknown con il tipo corretto`.
4. **Riuso nelle stories**: le `args` delle stories possono importare le fixtures
   (`import { fixtures } from './<slug>-fixtures'`) oppure inline i dati direttamente.
   La skill opta per il pattern inline nelle storie (default) per semplicita', ma
   documenta il file fixture come fonte autorevole per test unitari o rendering manuali.

---

## Fase F — Verifica invarianti + scrittura file

Pre-emit check: prima di scrivere i file e di emettere `REACT_GENERATED`, verifica:

- [ ] **INV-3 (read-only spec)**: nessun file `spec_source` e' stato modificato,
      rinominato o cancellato. Il componente non importa `spec_source`.
- [ ] **INV-4 (no self-eval)**: i file generati non contengono commenti che valutano
      la qualita' del prototipo. Solo commenti `// PROTOTYPE:` di tipo tecnico/placeholder.
- [ ] **No import da URL**: nessun `import` da URL `https://`. Tutti gli import sono
      relativi o da package npm.
- [ ] **Copertura stati**: tutti gli stati in `states_covered` hanno un branch di
      rendering esplicito nel componente (almeno un `case` nello `switch`, o un blocco
      condizionale).
- [ ] **Copertura storie** (se `storybook: true`): ogni stato in `states_covered` ha
      una `Story` corrispondente nel file `.stories.*`.
- [ ] **Copertura fixture**: ogni stato in `states_covered` ha una entry nel record
      `fixtures`.
- [ ] **Path output isolato**: i file vengono scritti in `<base_path>/<slug>/` dove
      `base_path` e' `output_path` (default) o `target_code_path/<slug>/` (se
      `target_code_path` e' valorizzato). Il path `<slug>/` dentro il code_path target
      e' sempre una directory dedicata ai prototipi, non mista al codice di produzione.

Se una o piu' verifiche falliscono:

- Logga il check fallito in chat con il dettaglio specifico.
- **Non emettere** `REACT_GENERATED`.
- Il caller ([prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 2) gestisce l'errore come
  generazione fallita e non procede a Fase 3.

Se tutti i check passano:

- Scrivi i file in `<base_path>/<slug>/`:
  - `<ComponentName>.tsx` (o `.jsx`)
  - `<ComponentName>.stories.tsx` (o `.stories.jsx`) — solo se `storybook: true`
  - `<slug>-fixtures.ts` (o `<slug>-fixtures.js`)
- Emetti l'output YAML al caller (vedi §Output).
- Emetti il marker `REACT_GENERATED: <base_path>/<slug>/`.

**Path canonico**: `<base_path>/<slug>/` dove:
- `base_path = output_path` (default) se `target_code_path == null`
- `base_path = target_code_path` se `target_code_path != null`

Esempio con `output_path: "output/prototypes"`, `slug: "login-form"`, `ComponentName: LoginForm`:
- `output/prototypes/login-form/LoginForm.tsx`
- `output/prototypes/login-form/LoginForm.stories.tsx`
- `output/prototypes/login-form/login-form-fixtures.ts`

---

## Vincoli

- **INV-3 (read-only spec)**: il file `spec_source` non viene mai modificato, rinominato
  o cancellato. Il componente generato non importa la spec sorgente.
- **INV-4 (no self-eval)**: i file generati non includono commenti valutativi sulla
  qualita', il design o l'implementazione. Solo placeholder tecnici `// PROTOTYPE:`.
- **INV-5 (default off)**: la skill non viene invocata se `prototyping.enabled: false`.
  Il guard e' nel [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) prima della Fase 0 — la skill non
  duplica il check.
- **No import da URL**: nessun import da `https://`. Tutti i riferimenti sono a package
  npm o path relativi.
- **Path output**: sempre in `<output_path>/<slug>/` (default) o
  `<target_code_path>/<slug>/` (se configurato). La directory `<slug>/` dentro il
  `target_code_path` e' sempre dedicata ai prototipi — non mista al codice di produzione
  (nessun file scritto direttamente in `src/components/` o radice del code_path).
- **Nessun cross-write**: questa skill non conosce la logica di risoluzione backend —
  quella vive in [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md). Riceve solo input gia' risolto dal
  [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 2. Non modifica `factory.config.yaml` ne'
  altri file di configurazione.
- **Placeholder espliciti**: i commenti `// PROTOTYPE:` sono il contratto di
  estensibilita' del componente generato. Vanno sostituiti dal `fe-dev` (handoff) con
  logica reale. Non eliminati silenziosamente.
- **`storybook: false`**: se la config ha `storybook: false`, le fasi D e la parte
  storie di Fase F sono no-op. L'output non include il file `.stories.*`.

---

## Cross-link

- [backend-resolver](mdc:.cursor/skills/backend-resolver/SKILL.md) — probe ASSE 2 per `react` usa `stack-detector`. Se
  `stack-detector` non trova framework FE in nessun `code_path`, il resolver emette
  `BACKEND_DEGRADED: react→html` e questa skill non viene invocata.
- [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) — Fase 2: invoca direttamente questa skill con
  il brief completo (Step 1.4). Fase 3 verifica le condizioni minime sull'output
  della skill (file/directory esistente, `states_covered` non vuoto).
- [html-prototype-mapping](mdc:.cursor/skills/html-prototype-mapping/SKILL.md) — analogia strutturale. Stesso pattern provider-specific,
  stesse sezioni (Input/Output/Fasi A-F/Vincoli/Cross-link), stesso contratto con
  [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md). Il backend `html` e' il fallback terminale quando
  questa skill non e' disponibile (no FE stack in `code_path`).
- `stack-detector` (v2.12) — skill condivisa con `code-reviewer`. Rilevazione
  framework FE nel `code_path` target. Determina `tsx` (TypeScript rilevato),
  `component_lib` (DS rilevato nel code_path se diverso da config).
- `wiki/concepts/backend-adaptive-prototyping.md §I quattro tier di backend` — T1
  react, business rules, posizionamento nella cascata backend.
- Analogia strutturale: `github-mapping` (v2.10) — stesso split protocollo
  provider-agnostic + skill provider-specific. EP-035 replica il pattern publisher
  (ADR-EP035-003 GO).

**Nota sul path dichiarato in [prototype-generation-protocol](mdc:.cursor/skills/prototype-generation-protocol/SKILL.md) Fase 2**: la tabella in
quel file cita `react-prototype-mapping` (convenzione alternativa).
Questa skill vive in `.cursor/skills/react-mapping/SKILL.md` (path canonico dichiarato in
TSK-238 `code_path`). In caso di disambiguazione, questo file e' quello corretto.

[^src: wiki/concepts/backend-adaptive-prototyping.md §I quattro tier di backend]
[^src: wiki/concepts/prototype-generation-capability.md §Configurazione (blocco factory.config.yaml)]
[^src: management/kanban/EP-035-prototype-generation-layer/US-124-backend-react-t1/US-124.md §Business Rules §Acceptance Criteria]
[^src: .claude/skills/html-prototype-mapping.md §Input §Output §Vincoli §Cross-link]
[^src: .claude/skills/backend-resolver.md §Step 3 — ASSE 2 §Step 5 — Emissione marker]
[^src: .claude/skills/prototype-generation-protocol.md §Fase 2 — Generate §Fase 3 — Self-contain check]
