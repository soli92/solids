---
name: scrivi-purpose
description: Template e regole per scrivere wiki/purpose.md — direttive semantiche di dominio per-factory (EP-055).
---
# Procedura per scrivere `wiki/purpose.md`

`wiki/purpose.md` è il file di **direttive semantiche di dominio** della factory
(PATTERN §34, EP-055). È **maintainer-authored**: lo scrive a mano il maintainer, nessun
agente lo genera o modifica. Guida `wiki-keeper` durante l'ingest e viene controllato da
`wiki-lint`. Opt-in: se assente, la factory funziona identica a prima.

Non duplica `factory.config.yaml` (quello è la config **tecnica**; questo è la dimensione
**semantico-di-dominio**).

## Formato (frontmatter YAML + corpo markdown)

```yaml
---
type: purpose
domain: <stringa — di cosa parla questa wiki, in una frase densa>
priority_entity_types: [<tipi di entità prioritari nell'ingest, in ordine>]
tone: technical-prescriptive         # | narrative | mixed
exclusions: [<argomenti/tipi che NON devono entrare in wiki, può essere vuota>]
---

# Purpose

<corpo markdown libero>
```

## Campi obbligatori

| Campo | Tipo | Significato |
|---|---|---|
| `domain` | stringa | Dominio del progetto in una frase. Es. "meta-framework per factory multi-agente AI". |
| `priority_entity_types` | lista | Tipi di entità che l'ingest deve privilegiare. Es. `[pattern, capability, invariante]`. |
| `tone` | enum | Registro atteso: `technical-prescriptive` (normativo, imperativo), `narrative` (discorsivo), `mixed`. |
| `exclusions` | lista | Cosa tenere fuori dalla wiki (può essere `[]`). Es. `[gossip-organizzativo, roadmap-commerciale]`. |

## Corpo markdown

Testo libero per gli agenti: descrizione estesa del dominio, esempi di entità
prioritarie, note su convenzioni terminologiche, glossario minimo. Nessun vincolo di
struttura — è contesto, non uno schema.

## Regole

- **Contesto, non gate**: `wiki-keeper` usa `purpose.md` per orientare l'analisi, ma il
  maintainer resta sovrano. Le direttive non bloccano mai l'ingest.
- **Read-only per gli agenti**: nessun agente scrive su `purpose.md`. Unico autore = maintainer.
- **`tone` deve essere nell'enum** — valori fuori enum sono flaggati WARNING da `wiki-lint`.
- **Tutti e 4 i campi obbligatori** — un campo mancante è WARNING (non ERROR).

## Check di `wiki-lint` (Check 4an)

- Assenza `wiki/purpose.md` → WARNING (raccomandato, non obbligatorio).
- Frontmatter incompleto → WARNING con nome del campo mancante.
- `tone` fuori enum → WARNING.
- Mai `heal-eligible` (giudizio semantico).

Cross-ref: PATTERN §34, §23.10 (origine pattern-stealing da llm_wiki GPL v3).
