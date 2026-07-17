# Skill: State Scan

> Adapter Cursor della skill `state-scan` definita in PATTERN.md.

# State scan (canonico)

Riferimenti: `PATTERN.md §8` (state derivation: filesystem + log + episodic),
[wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (per i tipi di operazione loggate).

## Output atteso

Tabella tabellare dei 4 layer + gate + suggerimento next-step.

```
L | Status   | Ultimo update | Conteggio | Note
--|----------|---------------|-----------|----------------------------
L1| green    | YYYY-MM-DD    | N PDF     | manifest sincronizzato
L2| green    | YYYY-MM-DD    | N pagine  | (eventuale "📌 K gap aperti", "✨ M promotion candidates")
L3| amber    | YYYY-MM-DD    | N epiche  | gate: ⛔ hard / ⚠️ soft / ✅ clean (v2.6 graduato)
L4| green    | YYYY-MM-DD    | N task    | sprint corrente: SS (eventuale "🔁 R reconcile-needed")
```

## Procedura (6 passi)

### 1. L1 status

```
Glob raw/*.pdf
Read raw/.extraction-manifest.json
```

- `green` se ogni PDF ha entry nel manifest.
- `amber` se ci sono PDF non ancora estratti (suggerisci `/sync-docs`).
- `red` se il manifest manca.

### 2. L2 status

```
Read wiki/log.md  (ultime entry per tipo: ingest, lint)
Glob wiki/**/*.md  (escludi log.md, gaps.md, query/, lint/)
```

- Conteggio pagine totali, raggruppate per sezione (concepts/entities/...).
- Ultimo ingest e ultimo lint dal log.
- `green` se ingest ha coperto tutti i PDF estratti.
- `amber` se ci sono PDF estratti ma non ingeriti.

### 3. Gap pendenti (segnale per `wiki-keeper`)

```
Read wiki/gaps.md
```

- Conta sezioni `## YYYY-MM-DD HH:MM — <slug>` **senza** riga `**Risolto:**`.
- Se > 0 → aggiungi nota "📌 N gap pendenti — suggerisci wiki-keeper".

### 4. L3 status + gate (graduato, v2.6)

```
Glob management/kanban/EP-*/EP-*.md
Read management/questions.md  (frontmatter status + parse [APERTE])
```

- Conteggio epiche per status (`defined`/`in-progress`/`done`).
- **Gate graduato** (v2.6, vedi `PATTERN.md §7 r.9`): parse di ogni Q in `[APERTE]`
  per il campo `**Bloccante:** hard | soft` (default `hard` se omesso).
  - `hard_open > 0` → segnala in rosso "⛔ L4 hard-bloccato su US dipendenti
    (Q hard: <lista>)". Identifica US impattate via `blocked_by`.
  - `soft_open > 0 && hard_open == 0` → segnala in giallo "⚠️ L4 parziale —
    N Q soft aperte, Arch+TPM possono procedere con `pending_clarification`".
  - Tutte chiuse → segnala in verde "✅ L4 gate clean".

### 5. L4 status

```
Read design_&_architecture/be_architecture.md   (se esiste)
Read design_&_architecture/fe_architecture.md   (se esiste)
Glob management/kanban/**/TSK-*.md
Read management/kanban/sprint.md                (se esiste)
```

- Conteggio task totali e per sprint.
- `green` se architettura + sprint.md presenti e questions chiuse.
- `amber` se architettura presente ma sprint.md non ancora generato.
- `red` se gate questions ancora aperto.

### 6. Reconcile-needed pendenti (v2.6, da operazione `Propagate`)

```
Read wiki/log.md  (filtra entry con "reconcile-needed")
```

- Conta marker `reconcile-needed: US-YYY → Q_NNN closed` ancora attivi.
- Un marker è **attivo** se la US citata ha ancora `Q_NNN` in `blocked_by` o
  `pending_clarification` (read del file US per verifica).
- Se > 0 → aggiungi nota "🔁 N reconcile-needed pendenti (US: <lista>)" come
  **prima** riga della sezione note del dashboard. È il segnale più urgente
  dopo gate hard aperto: indica stato kanban stale rispetto a Q risolte.

### 7. Auto-promotion candidates (v2.6, N4)

```
Glob wiki/concepts/*.md, wiki/entities/*.md, wiki/syntheses/*.md
Grep "wiki_page:" in management/kanban/EP-*/US-*/US-*.md
```

- Per ogni pagina wiki con `status: draft`: conta quante US la citano in
  `wiki_page:` **e** sono in `status: committed | in-progress | done`.
- Se count ≥ 2 → la pagina è **promotion candidate** per `review`.
- Limita la lista a max 5 candidate per dashboard (le altre sono ripetibili
  al run successivo).

### 8.bis Parallel scheduler probe (v2.11)

```
Read factory.config.yaml  (sezione scheduler:)
```

- Se `scheduler.enabled: false` o assente → skip questo step (modalità seriale legacy).
- Se `scheduler.enabled: true` (default in nuovi progetti):
  - `Glob management/kanban/**/TSK-*.md` filtrato per `status: todo` + `consumer: agent`
  - Se conteggio ≥ 2 → segnala in dashboard una nota "⚡ N TSK candidate per wave dispatch — invoca [parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md)".
  - Se conteggio < 2 → nessun parallelismo da proporre, fallback alla heuristica next-step single-step (regole 1–9 sotto).

### 9. Continuità (episodic memory)

```
Read memory/episodic/<ultimo>.md
```

- Confronta lo stato osservato con la decisione precedente.
- Se è cambiato qualcosa di significativo, evidenzialo.

## Suggerimento next-step

Heuristica (in ordine di priorità — v2.11):

0. **⚡ Wave dispatch (v2.11)** → se `scheduler.enabled: true` e ci sono ≥ 2 TSK
   candidati (`status: todo`, `consumer: agent`, dipendenze risolte), invoca
   [parallel-scheduling](mdc:.cursor/skills/parallel-scheduling/SKILL.md) per costruire il DAG e mostrare il wave plan in chat,
   **prima** delle heuristiche single-step sotto. Se il piano contiene > 1
   group parallelo, applica gate §18.4 R.S4 (default ≥ 3 sub-agent).

Heuristiche single-step (fallback se nessun wave dispatch possibile, v2.6):

1. **🔁 Reconcile-needed pendenti > 0** → "Invoca [product-manager](mdc:.cursor/rules/product-manager.mdc) per
   riconciliare le US elencate (Q risolte ma `blocked_by` stale), oppure
   correggi a mano."
2. Gate `hard` aperto → "Rispondi alle Q hard in `management/questions.md`
   (L4 bloccato sulle US dipendenti)."
3. Gap pendenti > 0 → "Invoca [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) per affrontare i gap aperti."
4. L1 ha PDF non estratti → "Invoca `/sync-docs`."
5. L2 stale rispetto a L1 → "Invoca [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) per ingest."
6. **Auto-promotion candidates > 0** → "Considera `/promote <path> review`
   per le pagine citate da ≥ 2 US (lista mostrata sopra)."
7. L3 vuoto → "Invoca [product-manager](mdc:.cursor/rules/product-manager.mdc)."
8. L4 vuoto e L3 OK + nessuna Q hard sulle US target → "Invoca [lead-architect](mdc:.cursor/rules/lead-architect.mdc)
   sulle US sbloccate (eventuali Q soft → `pending_clarification` nell'ADR)."
9. L4 ha architettura ma no task → "Invoca [tpm](mdc:.cursor/rules/tpm.mdc) sulle US sbloccate."

**Mai delegare automaticamente.** Solo suggerire — l'umano decide. In particolare,
auto-promotion (regola 6) è **solo suggerimento**, mai esecuzione: l'orchestrator
può modificare `status:` solo via `/promote` esplicito (§2).

## Episodic memory (output collaterale)

Append a `memory/episodic/<YYYY-MM-DD-HH-MM>-run.md`:

```markdown
---
type: episodic
created: YYYY-MM-DD HH:MM
tags: [run, state-scan]
---

# Run del YYYY-MM-DD HH:MM

## Stato osservato
- L1: <status> (<conteggio>)
- L2: <status> (<conteggio>, gap=<N>, promotion-candidates=<M>)
- L3: <status> (<conteggio>, gate=<hard|soft|clean>, hard_open=<H>, soft_open=<S>)
- L4: <status> (<conteggio>, reconcile-needed=<R>)

## Decisione presa
Next-step suggerito: <agente> per <motivo>.

## Riferimenti
- Run precedente: memory/episodic/<file>.md
- Continuità: <eventuali differenze rilevanti>
```
