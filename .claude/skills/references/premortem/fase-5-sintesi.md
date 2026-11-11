# Fase 5 — Sintesi (dettaglio completo)

Ambito: dettaglio della Fase 5 di `premortem-protocol.md`. Leggere prima di eseguire la fase.

Aggrega i mini-dossier di Fase 4 in un output strutturato di **6 sezioni
canoniche in ordine obbligatorio**. Nessuna delle 6 sezioni modifica
automaticamente il target (**R.P1** riaffermato in fondo).

## Le 6 sezioni canoniche (ordine obbligatorio)

1. **`### Most Likely Failure`** — narrativa di **3-7 frasi** + riferimento al
   deep-dive di Fase 4 corrispondente (quale failure reason).
2. **`### Most Dangerous Failure`** — narrativa + giustificazione dell'impatto
   (maggior danno, non necessariamente più probabile).
3. **`### Hidden Assumption`** — l'assunzione root-cause cross-cutting (1-2 frasi).
4. **`### Revised Plan`** — lista di **3-7 azioni** concrete in checkbox markdown
   (`- [ ] …`).
5. **`### Pre-Launch Checklist`** — **3-5 item** verificabili, formato actionable
   («Verifica che X», «Conferma che Y»).
6. **`### Risk Registry`** — header conteggio + tabella a 9 colonne + calibration
   check (schema sotto).

## Schema tabella Risk Registry — 9 colonne

Ordine prescritto delle colonne:

```
# | Risk | Category | Tier | Urgency | Evidence | Mitigation | Owner | Decision
```

Obbligatorietà per campo:

| Classe | Campi |
|---|---|
| **Required** | `risk`, `category`, `tier`, `decision` |
| **Conditional** | `urgency` — solo se `tier=Tiger` (altrimenti `—`) |
| **Raccomandati** | `evidence`, `mitigation`, `owner` |

`category` ∈ {Execution, External, People, Technical, Assumptions} (le 5 di Fase 3).
`tier` ∈ {Tiger, Paper Tiger, Elephant}. Per i Tiger, `urgency` ∈ {LB
(Launch-Blocking), FF (Fast-Follow), Track}.

[^src: wiki/concepts/risk-classification-tigers-paper-tigers-elephants.md]

## Header conteggio

Sopra la tabella, nel formato:

```
Total risks: N
  - Tigers: X (Launch-Blocking: A, Fast-Follow: B, Track: C)
  - Paper Tigers: Y
  - Elephants: Z
```

## Calibration check (WARNING)

Se manca **almeno un tier** (`< 1 Tiger` **o** `< 1 Paper Tiger` **o** `< 1
Elephant`), la calibrazione è degenere → la skill **avvisa esplicitamente**:

> **⚠️ Calibration WARNING: la premortem ha prodotto `<dettaglio>` (es. 0 Elephant). Il frame di Fase 2 potrebbe non aver funzionato. Considera di riemettere con un frame più severo prima di fidarti del Risk Registry.**

Mai output silenzioso su calibrazione degenere.

## Esempio completo (calibration valida)

```markdown
### Risk Registry

Total risks: 4
  - Tigers: 2 (Launch-Blocking: 1, Fast-Follow: 1, Track: 0)
  - Paper Tigers: 1
  - Elephants: 1

| # | Risk | Category | Tier | Urgency | Evidence | Mitigation | Owner | Decision |
|---|------|----------|------|---------|----------|------------|-------|----------|
| 1 | Skill mai invocata in factory derivate | Assumptions | Tiger | LB | nessun deploy ancora | tracking via US-015 telemetria | @soli92 | open |
| 2 | Drift PATTERN v2.16 → adapter Cursor/Aider | Technical | Tiger | FF | adapter v2.13 non aggiornati | release note + tracking | @adapter-team | open |
| 3 | Backward compat parser frontmatter | Technical | Paper Tiger | — | pattern v2.10-v2.14 ok | nessuna | — | dismissed |
| 4 | "Tutti pensano sia utile ma nessuno la userà" | People | Elephant | — | named in self-premortem | runbook + esempi US-011 | @PM | open |
```

## Opt-in append a `management/risk-registry.md`

Se `management/risk-registry.md` **esiste**, la skill **propone** l'append della
sezione pre-mortem (mai auto-applica — **R.P1**). Se non esiste, niente
auto-creazione.

## Output side-effects

| Canale | Sempre attivo | Note |
|---|---|---|
| **Inline in chat** | ✓ | Risk Registry completo + Revised Plan + Pre-Launch Checklist visibili all'utente |
| **Append `wiki/log.md`** | ✓ | Marker `premortem <target> → <tier-counts>` (es. `premortem EP-001 → T:5 LB:2 FF:2 Tr:1 PT:2 E:1`) |
| **Append `memory/episodic/premortem-runs.md`** | ✓ | **Ultimo step di Fase 5**. Metadata only (no body, no contenuto del Risk Registry) — ADR-006, telemetria evolutiva v2.17+. |
| **Append `management/risk-registry.md`** | opt-in | Solo se l'utente lo richiede esplicitamente o il file esiste. Niente auto-creazione (R.P1) |
| **Suggerimento edit frontmatter target** | suggerito | La skill emette in chat «Considera di aggiungere `risk_classification.tier: tiger-launch-blocking` al frontmatter di EP-XXX». Mai applicato in autonomia (R.P1) |

## Telemetria — append a `memory/episodic/premortem-runs.md` (ultimo step Fase 5)

Come **ultimo step della Fase 5**, la skill appende **una riga** di metadati a
`memory/episodic/premortem-runs.md`. Mai il contenuto del Risk Registry (privacy:
solo metadati). Formato riga (ADR-006):

```
[YYYY-MM-DD HH:MM] premortem — <target> — timeframe: <N>{w|mo|y} — risks: <count> (T:<T>, PT:<PT>, E:<E>) — duration: <Ns> — invoker: <PM|Arch|Reviewer|user>
```

- **Lazy creation**: se il file non esiste, la skill lo crea al primo append con il
  frontmatter standard (`type: episodic-log`, `append_only: true`) e l'header
  autodocumentato, poi appende la riga.
- **Single-writer** (R.S1 fine-grained): solo la skill `premortem-protocol` scrive
  in questo file. Mai l'Orchestrator né altri agent.
- **Append-only**: nuove righe in coda alla sezione `## Log`, mai replace di righe
  esistenti.

## R.P1 riaffermato

Nessuna delle 6 sezioni modifica automaticamente il target: `Revised Plan` e
`Pre-Launch Checklist` sono **suggerimenti** per l'utente, emessi inline in chat.
Il body di EP/US/TSK resta invariato; l'edit del frontmatter `risk_classification:`
è solo **suggerito**.

**Criterio di completamento**: tutte e 6 le sezioni prodotte in ordine, header
conteggio presente, tabella a 9 colonne, calibration check eseguito (WARNING se
degenere).

[^src: management/kanban/EP-001-premortem-skill-scaffolding/US-004-output-sintesi-risk-registry/TSK-004.md §Technical Specs]
[^src: design_&_architecture/proposta-premortem-integration-v216.md §5.3]
