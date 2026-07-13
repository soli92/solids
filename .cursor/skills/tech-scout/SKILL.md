# Skill: Tech Scout

> Adapter Cursor della skill `tech-scout` definita in PATTERN.md.

# Procedura — Tech-scout (stack proposal)

Skill invocata quando `factory.config.yaml` ha `stack_mode: auto`, o on-demand
dall'utente quando vuole ri-valutare lo stack a metà progetto.

**Output**: `raw/tech_stack.md.proposal` (effimero, gate umano per promote).
**MAI** scrive direttamente `raw/tech_stack.md` (PATTERN §7 r.1 + §7 r.10).

## Fase 0 — Pre-condizioni

1. `factory.config.yaml.stack_mode` ∈ `{auto}`, oppure richiamo esplicito utente.
2. `wiki/` deve contenere almeno: un'epica con requisiti business chiari, o
   uno o più concept/synthesis che descrivono dominio + vincoli.
3. Standards normativi già presenti in `wiki/` o `raw/`: **trattati verbatim**
   (PATTERN §11). La proposta li adotta; non li sostituisce.

## Fase 1 — Estrazione vincoli

1. Leggi `wiki/syntheses/`, `wiki/concepts/`, `wiki/entities/` per:
   - Dominio del progetto (es. fintech, healthcare, e-commerce)
   - Scala attesa (utenti, throughput, latency budget)
   - Compliance / standards (GDPR, FHIR, OIDC, SPID, eIDAS, ISO 27001, …)
   - Geografia (data residency, multi-region)
   - Vincoli organizzativi (team size, expertise)
2. Leggi `management/kanban/EP-*/` per requisiti non-funzionali estratti.
3. Compila una **shortlist di vincoli** internamente (non scrivere).

## Fase 2 — Ricerca

1. Per ciascun layer (`backend`, `frontend`, `database`, `qa`, `infra`),
   formula 1-2 query web focalizzate (es. *"Python backend framework 2026 LTS
   production-ready healthcare FHIR"*).
2. Usa `WebSearch` / `WebFetch` per recuperare fonti datate **2026** (preferibilmente
   ultimo trimestre). Scarta fonti senza data o pre-2025.
3. Per ogni candidato (es. FastAPI, Django, Express), raccogli:
   - Versione corrente (LTS o stable)
   - Maturità / community / corporate adoption 2026
   - Compatibilità con vincoli normativi del progetto
   - Trade-off principali (un punto pro, un punto contro)

## Fase 3 — Scrittura proposta

**File**: `raw/tech_stack.md.proposal`

**Struttura**:

```markdown
---
type: tech-stack-proposal
created: YYYY-MM-DD
stack_mode: auto
generator: tech-scout skill (PATTERN §14)
status: proposal  # umano deve promuovere a tech_stack.md
---
# Tech stack proposal — YYYY-MM-DD

> Generata automaticamente da `tech-scout` su base `wiki/` + fonti web 2026.
> **NON sovrascrive `raw/tech_stack.md`.** Gate umano per applicare.

## Vincoli rilevati (da wiki/ + raw/)

- <vincolo 1> [^src: wiki/concepts/<page>.md §X]
- <vincolo 2> [^src: raw/<file>.md §Y]
- Standards verbatim: <lista — SAML, OIDC, FHIR, ...>

## Stack proposto

### Backend
**Scelta:** <es. FastAPI 0.115 + Python 3.13>
**Razionale:** <1-2 righe>
**Fonti:**
- [^web: <url> §<sezione>] (accessed YYYY-MM-DD)
- [^web: <url> §<sezione>] (accessed YYYY-MM-DD)
**Alternative considerate:** <X, Y> (pro/contro brevi)

### Frontend
... (stessa struttura)

### Database
...

### QA
...

### Infra
...

## Trade-off complessivi

<3-5 righe: dove la proposta è forte, dove è debole, quali assunzioni stiamo facendo>

## Non scelto verbatim da raw/

Se la proposta diverge da qualcosa già presente in `raw/`, dichiaralo qui
esplicitamente. Standards normativi (PATTERN §11) NON devono mai divergere.
```

## Fase 4 — Handoff

1. Append a `wiki/log.md`:
   ```markdown
   ## YYYY-MM-DD HH:MM — tech-scout proposal
   **Generata:** raw/tech_stack.md.proposal
   **Fonti web:** <count>
   **Standards verbatim adottati:** <lista o "nessuno">
   **Next:** gate umano per promuovere a tech_stack.md
   ```
2. Segnala in chat all'utente: "Proposta scritta in `raw/tech_stack.md.proposal`.
   Reviewala e, se ok, rinominala in `raw/tech_stack.md` (oppure copia i blocchi
   che servono). MAI applicare automaticamente."

## Vincoli inviolabili

- **MAI scrivere `raw/tech_stack.md`** direttamente. Solo `.proposal`.
- **MAI sostituire standards normativi** già citati in raw/wiki.
- **Citazione obbligatoria** su ogni scelta: almeno una fonte web datata 2026.
- **Trasparenza sulle alternative**: l'utente deve vedere cosa è stato scartato e perché.
- **Non promuovere `.proposal` autonomamente** — il file resta sul filesystem
  finché l'umano decide.
