# Skill: Premortem Protocol

> Adapter Cursor della skill `premortem-protocol` definita in PATTERN.md.

Metadata skill (originale):

```yaml
name: premortem-protocol
description: Protocollo per eseguire una premortem strutturata su un piano/artefatto via prospective hindsight (PATTERN §3 operazione opzionale, v2.16). 5 fasi (Context Gathering → Frame Setting → Raw Premortem → Parallel Deep-Dives → Sintesi). Output Risk Registry con tassonomia Tigers/Paper Tigers/Elephants. Opt-in totale, niente invariante §7 (R.P1-R.P3 vivono qui).
```

# Protocollo Premortem (analisi del rischio via prospective hindsight)

Riferimenti: PATTERN §3 (operazione opzionale `Premortem` v2.16), §5 (frontmatter
opt-in `risk_classification:`), §7 (no nuova invariante — R.P1-R.P3 vivono in
questa skill), [[premortem-skill]] (concept teorico), [[risk-classification-tigers-paper-tigers-elephants]]
(tassonomia output), [[factory-premortem-integration]] (design doc v2.16).

Questa skill è **provider-agnostic**: l'inferenza viene fatta dall'LLM ospitante.
Definisce le 5 fasi che ogni invocazione di premortem deve seguire. È invocata
dal comando `/premortem` (Claude Code), o direttamente come skill da agent che
ne fanno uso esplicito (PM, Arch, Code Reviewer in modalità suggerimento).

## Chi può eseguirla

| Ruolo | Trigger naturale | Note |
|---|---|---|
| **Utente diretto** | `/premortem <descrizione \| EP-XXX \| US-YYY \| TSK-ZZZ \| wiki-page>` | Modalità on-demand, sempre disponibile |
| **PM** ([product-manager](mdc:.cursor/rules/product-manager.mdc)) | prima di `Promote EP draft → review` su epica `high-impact` | Suggerito, mai automatico |
| **Arch** ([lead-architect](mdc:.cursor/rules/lead-architect.mdc)) | prima di `Promote design doc draft → approved` su decisioni cross-cutting | Suggerito, mai automatico |
| **Code Reviewer** (`code-reviewer`) | verdict `conditional` su TSK con `risk_classification.tier: tiger-*` | Solo come suggerimento nel `task_package`; mai esecuzione automatica |
| **Orchestrator** | `/run` su wave con artefatti `risk_classification: high-impact` | Solo come suggerimento in dashboard; mai dispatch automatico |

In tutti i casi: invocazione manuale via `/premortem`. Mai auto-trigger (R.P3 opt-in totale).

## Quando attivarla

**Usare** quando il costo di sbagliare è alto e si può ancora cambiare rotta:

- prima di un PATTERN bump major (es. v2.x → v3.0) o di una nuova invariante §7
- prima di promote di un'**epica `high-impact`** draft → review
- prima di promote di un **design doc** con touchpoint cross-cutting (es. nuova
  operazione canonica §3)
- prima di una migrazione architetturale importante (es. CCL Fase 3b wiki-as-graph
  attivazione, R.K1-type)
- prima di un'assunzione chiave non verificabile a priori
- quando la confidence degli stakeholder è alta e va stress-testata
- quando il team ha una brutta sensazione non articolata

**NON usare** per:
- validazione/feedback generico (usa `/code-review` o discussione libera)
- domande fattuali («come fa X a fare Y?» — usa `/query` su wiki)
- brainstorming creativo (anti-pattern: la premortem è retrospettiva, non
  generativa di alternative)
- decisioni già irrevocabilmente prese (perdita di tempo — la premortem serve a
  cambiare rotta, non a confermare con sensi di colpa)

Regola pratica: invoca premortem **quando hai ancora margine di manovra e la
posta è alta**. [^src: wiki/concepts/premortem-skill.md §Quando usarla]

## Invarianti R.P1-R.P3

Tre regole leggere specifiche di questa skill. **Non sono regole §7 PATTERN** —
vivono qui, possono essere violate in casi specifici senza rompere il framework
(ma con perdita di valore del pattern). [^src: wiki/concepts/factory-premortem-integration.md §5]

- **R.P1 — Output mai auto-applicato**. Il `revised_plan` e la `pre-launch
  checklist` sono **sempre** suggerimenti per l'utente. Mai modifica automatica
  del piano originale (EP/US/TSK body invariato; il frontmatter `risk_classification:`
  può essere suggerito per edit ma mai applicato in autonomia).
- **R.P2 — Bar minimo del contesto**. La skill **non procede** se Fase 1 Context
  Gathering non soddisfa le 3 domande chiave (cosa stai facendo, per chi, come
  appare il successo). Output forzato su contesto insufficiente è sanitizzato →
  preferire fail-loud, non fail-silent. (Logica completa in TSK-005.)
- **R.P3 — Opt-in totale**. Factory v2.15 senza la skill scaffoldata si comporta
  identica. Niente lint ERROR se la skill è assente. Niente trigger automatico
  per parole chiave nel testo (decisione ADR-003: solo `/premortem` esplicito).

## Fase 1 — Context Gathering

Costruisce il **dossier** su cui le fasi 2-5 lavorano. Niente premortem parte
finché il **bar minimo** non è soddisfatto: questo è il punto di applicazione di
**R.P2** (vedi [Invarianti R.P1-R.P3](#invarianti-rp1-rp3)).

### Input e loading strategy per input shape

Il comando `/premortem` passa un singolo argomento. La skill discrimina la shape
(primo match vince) e carica il contesto **prima** di chiedere qualsiasi cosa:

| Input shape | Loading strategy |
|---|---|
| **Artefatto kanban** (`EP-XXX` / `US-YYY` / `TSK-ZZZ`) | Legge frontmatter + body del target, dell'eventuale padre (US→EP, TSK→US→EP) e dei sibling; carica il design doc referenziato in `[^src: …]` se presente. |
| **Pagina wiki** (path `wiki/**/*.md`) | Legge la pagina + i wikilink di primo hop (`[[…]]`). |
| **Descrizione libera** | Nessun file specifico da cui dedurre: carica `wiki/index.md` + le ultime 10 entry di `memory/episodic/` come contesto storico, poi procede al bar minimo. |

In tutti i casi il dossier finale contiene: **target**, **stakeholder**,
**criteri di successo**, contesto storico (`memory/episodic/` ultime 10 entry),
wikilink di primo hop.

### Il bar minimo — 3 domande esatte

La premortem non parte finché non sono note **tutte e tre**:

1. **«Cosa si sta cercando di fare?»** — derivato dal target.
2. **«Per chi?»** — stakeholder / consumer del risultato.
3. **«Come appare il successo?»** — criteri di accettazione.

### Logica di deduzione preventiva (artefatti kanban ben formati)

Su un artefatto kanban la skill **deduce prima di chiedere**: legge frontmatter +
body e prova a rispondere alle 3 domande da sola. La domanda esplicita all'utente
si attiva **solo se la deduzione fallisce** per uno specifico elemento.

- Esempio: `/premortem EP-001` su un'epica con titolo, descrizione e US figlie ben
  formate → tutte e 3 le risposte sono deducibili → la skill **procede senza
  chiedere** e passa direttamente alla Fase 2.
- Su **descrizione libera** la deduzione quasi sempre lascia ≥1 elemento scoperto
  → **quasi sempre ≥1 domanda esplicita**.

### Comportamento: una domanda alla volta

Se mancano elementi, la skill chiede **una sola domanda per volta** (NO batch di 3
domande simultanee). Aspetta la risposta, aggiorna il dossier, e solo allora pone
la successiva — finché il bar è completo.

Esempio di flusso (descrizione libera sotto-bar):

```
Utente: /premortem "vogliamo migrare il DB a Postgres"
Skill:  Bar minimo non soddisfatto: manca «per chi» (stakeholder).
        Chi è impattato da questa migrazione? (utenti finali, team interno, …)
Utente: il team backend, in produzione restano gli stessi utenti
Skill:  Bar minimo non soddisfatto: manca «come appare il successo».
        Come appare il successo di questa migrazione? (criteri di accettazione)
Utente: zero downtime e nessuna query > 50ms di regressione
Skill:  Bar minimo soddisfatto. Procedo. [Fase 2 →]
```

### R.P2 — fail-loud su contesto sotto-bar

Mai output parziale silenzioso. Se il bar non è soddisfatto la skill **rifiuta di
procedere** con messaggio esplicito verbatim:

> **Bar minimo non soddisfatto: manca `<X>`. Rispondi a questa domanda prima di procedere.**

dove `<X>` ∈ {`cosa stai facendo`, `per chi`, `come appare il successo`}. Output
forzato su contesto insufficiente è sanitizzato → produce una premortem inutile,
quindi si preferisce sempre fail-loud, non fail-silent. Cross-link:
[Invarianti R.P1-R.P3 → R.P2](#invarianti-rp1-rp3).

**Criterio di completamento**: le 3 domande del bar minimo soddisfatte (per
deduzione o per risposta esplicita). [^src: management/kanban/EP-001-premortem-skill-scaffolding/US-005-bar-minimo-contesto-fail-loud/TSK-005.md §Technical Specs]

## Fase 2 — Frame Setting

Il **meccanismo psicologico centrale**: la skill enuncia esplicitamente la frase
chiave verbatim:

> «È [N mesi] da oggi. Questo piano è fallito.»

Senza questa frase, il modello LLM resta in modalità ottimistica (pianificazione)
invece di passare in modalità retrospettiva (spiegazione del fallimento come
fatto compiuto). [^src: wiki/concepts/premortem-skill.md §Fase 2]

### Timeframe-default per tipologia di target

| Target | Timeframe default | Override flag |
|---|---|---|
| TSK singolo | 2-4 settimane | `--timeframe=2w` |
| US singola | 1-3 mesi | `--timeframe=2mo` |
| EP completa | 6 mesi | `--timeframe=6mo` |
| PATTERN bump major (R.K1-type) | 12-18 mesi | `--timeframe=12mo` |
| Strategia / nuova adapter | 12-18 mesi | `--timeframe=18mo` |

Il timeframe è inferito automaticamente dal target ma sempre override-abile
inline con `--timeframe=<N>w|<N>mo`. [^src: design_&_architecture/proposta-premortem-integration-v216.md §3.2 Fase 2]

Input atteso: dossier di Fase 1.
Output prodotto: frase verbatim emessa al modello + timeframe selezionato.
Criterio di completamento: la frase è stata enunciata letteralmente nel contesto
dell'inferenza successiva (verifica grep sulla trascrizione interna se necessario).

## Fase 3 — Raw Premortem

Genera failure reasons per categoria. Cinque categorie standard. Numero non
fisso: **completezza, non padding**. Stop quando la skill non genera più
ragioni non-banali. [^src: wiki/concepts/premortem-skill.md §Fase 3]

### Le 5 categorie di failure reasons

#### Execution

Cosa va male nell'esecuzione del piano (risorse, tempo, processo).

- *Esempio 1*: «La timeline di 3 mesi era irrealistica perché abbiamo
  sottostimato il refactor delle dipendenze legacy. A 6 settimane eravamo già
  al 70% del budget di tempo con il 30% del lavoro fatto.»
- *Esempio 2*: «Scope creep silenzioso: ogni sprint il PM ha aggiunto 1-2 US
  "piccole" senza re-stimare. A fine quarter avevamo raddoppiato lo scope
  iniziale senza accorgercene.»

#### External

Eventi esterni alla tua zona di controllo (mercato, normativa, competitor).

- *Esempio 1*: «Un competitor ha rilasciato la stessa feature 2 settimane prima
  di noi, in versione gratis. Il nostro pricing è diventato insostenibile.»
- *Esempio 2*: «Una nuova normativa GDPR-bis ha richiesto un audit obbligatorio
  prima del lancio che non avevamo pianificato. Slittamento di 4 mesi.»

#### People

Disallineamento, key person leaves, skill gap, dynamic interpersonali.

- *Esempio 1*: «Il tech lead che aveva progettato l'architettura ha lasciato
  l'azienda a metà progetto. Nessun altro aveva il mental model completo, e
  abbiamo speso 3 sprint a ricostruirlo.»
- *Esempio 2*: «Gli stakeholder business e tech non hanno mai allineato sulla
  definizione di "MVP". A fine quarter c'erano 2 prodotti diversi nelle teste,
  e il delivery non corrispondeva a nessuno dei due.»

#### Technical

Debito tecnico, dipendenze fragili, scalabilità, sicurezza, integrazione.

- *Esempio 1*: «Il database scelto in fase di design non scalava oltre 10k
  utenti concorrenti. Quando il lancio ha portato 50k al picco, il sistema è
  collassato e abbiamo perso le prime 6 ore di traffico.»
- *Esempio 2*: «Una dipendenza esterna (OAuth provider) ha deprecato l'API che
  usavamo a 3 mesi dalla nostra release. Migrazione non pianificata, debito
  esploso.»

#### Assumptions

Assunzioni implicite sul mercato, costi, comportamento utente, prerequisiti taciti.

- *Esempio 1*: «Assumevamo che gli utenti enterprise volessero SSO. Survey
  post-rilascio: il 70% usa account locali per ragioni di policy IT. Feature
  SSO sviluppata per 2 mesi, usata dal 30%.»
- *Esempio 2*: «Stima costi infrastruttura basata su prezzi cloud 2024 senza
  considerare che il nostro pattern di traffico (bursty) avrebbe fatto scattare
  tariffe premium. Costo reale 3x stimato.»

Input atteso: frase Fase 2 emessa + dossier Fase 1.
Output prodotto: lista di failure reasons per ciascuna categoria, ognuna in
forma narrativa breve (1-3 frasi).
Criterio di completamento: ogni categoria ha ≥ 1 reason esplorata (anche se la
risposta è «non applicabile a questo target» — esplicito > tacito).

## Fase 4 — Parallel Deep-Dives

Ogni failure reason rilevante di Fase 3 viene approfondita in parallelo da un
sub-agent investigatore. È il **fan-out** della premortem, modellato sul pattern
[wiki-keeper-worker](mdc:.cursor/rules/wiki-keeper-worker.mdc) v2.4 (ingest paralleli): sub-agent stateless che ritornano
output al caller, **nessuna scrittura su filesystem dai worker**.

### Cap fan-out — `max_parallel: 8` (HARDCODED)

Il cap è **`max_parallel: 8`**, hardcoded nella skill e **non configurabile** in
v2.16 (ADR-001). Rationale: limite empirico sopra il quale la tassonomia
Tigers/Paper Tigers/Elephants di Fase 5 perde potere discriminante (troppi rischi
indifferenziati → calibrazione degenere). Il numero è fissato verbatim qui, non
deriva da `scheduler.max_parallel` (che vive a un livello diverso — vedi nota DAG).

### Pattern di riuso — `wiki-keeper-worker` v2.4

Non reinventare il fan-out: la Fase 4 riusa lo stesso pattern di
[wiki-keeper-worker](mdc:.cursor/rules/wiki-keeper-worker.mdc) (sub-agent di ingest paralleli, v2.4):

- il caller spawna N sub-agent (uno per failure reason, fino a 8);
- ogni sub-agent **non scrive su disco**: ritorna il proprio output al caller;
- **la scrittura/aggregazione è serializzata sul caller** → nessuna race su
  filesystem (preserva R.S1 single-committer, PATTERN §7 r.12).

### Output per sub-agent — la tripla obbligatoria

Ogni sub-agent ritorna esattamente **tre elementi** per la failure reason assegnata:

1. **Storia del fallimento** — narrazione di **3-7 frasi** (NO bullet list): come,
   in concreto, quella reason ha fatto fallire il piano.
2. **Assunzione nascosta** — l'assunzione che, se falsa, fa crollare lo scenario
   (1-2 frasi).
3. **Early warning signs** — **1-2** segnali osservabili in anticipo che la
   failure si sta materializzando.

Formato di ritorno atteso al caller (narrativo, non tabellare):

```
[Reason: <breve label dalla Fase 3>]
Storia: <3-7 frasi narrative>
Assunzione nascosta: <1-2 frasi>
Early warning: <1-2 segnali osservabili>
```

### Comportamento con > 8 failure reasons

Se Fase 3 ha prodotto **più di 8** reason rilevanti, **niente troncamento
silenzioso**: la skill esegue **2 round serializzati di max 8** ciascuno (es. 11
reason → round 1 di 8 + round 2 di 3), aggregando i risultati di entrambi i round
prima di Fase 5.

### Vincolo di scrittura dei sub-agent

I sub-agent della Fase 4 **non scrivono** in `wiki/`, `management/`,
`code_quality/`, `memory/` né altrove sul filesystem. Il loro unico output è verso
il caller. Ogni side-effect su disco avviene in Fase 5, serializzato dal caller.

### Compatibilità scheduler (PATTERN §18) e OCL (PATTERN §20)

- **DAG / scheduler v2.11**: il cap `max_parallel: 8` della Fase 4 è un **secondo
  livello** di parallelismo, annidato dentro la wave del dominio `premortem`. Con
  `scheduler.max_parallel: 4` e 3 `/premortem` simultanee → fino a 24 sub-agent
  contemporanei nel caso peggiore (composizione N × M — vedi PATTERN §18 e ADR-004).
- **OCL v2.14**: il canale sub-agent → caller è `agent_to_agent`, quindi
  **comprimibile** se l'Output Compression Layer (Caveman) è attivo.

**Criterio di completamento**: ogni failure reason rilevante ha il suo mini-dossier
(tripla) aggregato al caller, entro il cap di 8 per round.
[^src: management/kanban/EP-001-premortem-skill-scaffolding/US-003-parallel-deep-dives-subagent/TSK-003.md §Technical Specs] [^src: design_&_architecture/decisions/ADR-001.md]

## Fase 5 — Sintesi

Aggrega i mini-dossier di Fase 4 in un output strutturato di **6 sezioni
canoniche in ordine obbligatorio**. Nessuna delle 6 sezioni modifica
automaticamente il target (**R.P1** riaffermato in fondo).

### Le 6 sezioni canoniche (ordine obbligatorio)

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

### Schema tabella Risk Registry — 9 colonne

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

### Header conteggio

Sopra la tabella, nel formato:

```
Total risks: N
  - Tigers: X (Launch-Blocking: A, Fast-Follow: B, Track: C)
  - Paper Tigers: Y
  - Elephants: Z
```

### Calibration check (WARNING)

Se manca **almeno un tier** (`< 1 Tiger` **o** `< 1 Paper Tiger` **o** `< 1
Elephant`), la calibrazione è degenere → la skill **avvisa esplicitamente**:

> **⚠️ Calibration WARNING: la premortem ha prodotto `<dettaglio>` (es. 0 Elephant). Il frame di Fase 2 potrebbe non aver funzionato. Considera di riemettere con un frame più severo prima di fidarti del Risk Registry.**

Mai output silenzioso su calibrazione degenere (coerente con l'anti-pattern
«Risk Registry con calibrazione degenere»).

### Esempio completo (calibration valida)

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

### Opt-in append a `management/risk-registry.md`

Se `management/risk-registry.md` **esiste**, la skill **propone** l'append della
sezione pre-mortem (mai auto-applica — **R.P1**). Se non esiste, niente
auto-creazione. Template e schema della sezione: vedi US-013 / TSK-012.

### R.P1 riaffermato

Nessuna delle 6 sezioni modifica automaticamente il target: `Revised Plan` e
`Pre-Launch Checklist` sono **suggerimenti** per l'utente, emessi inline in chat.
Il body di EP/US/TSK resta invariato; l'edit del frontmatter `risk_classification:`
è solo **suggerito**. Vedi [Invarianti R.P1-R.P3 → R.P1](#invarianti-rp1-rp3).

**Criterio di completamento**: tutte e 6 le sezioni prodotte in ordine, header
conteggio presente, tabella a 9 colonne, calibration check eseguito (WARNING se
degenere). [^src: management/kanban/EP-001-premortem-skill-scaffolding/US-004-output-sintesi-risk-registry/TSK-004.md §Technical Specs] [^src: design_&_architecture/proposta-premortem-integration-v216.md §5.3]

## Output side-effects

| Canale | Sempre attivo | Note |
|---|---|---|
| **Inline in chat** | ✓ | Risk Registry completo + Revised Plan + Pre-Launch Checklist visibili all'utente |
| **Append `wiki/log.md`** | ✓ | Marker `premortem <target> → <tier-counts>` (es. `premortem EP-001 → T:5 LB:2 FF:2 Tr:1 PT:2 E:1`) |
| **Append `memory/episodic/premortem-runs.md`** | ✓ | **Ultimo step di Fase 5**. Metadata only (no body, no contenuto del Risk Registry) — ADR-006, telemetria evolutiva v2.17+. Vedi formato e lazy-creation sotto. |
| **Append `management/risk-registry.md`** | opt-in | Solo se l'utente lo richiede esplicitamente o il file esiste. Niente auto-creazione (R.P1) |
| **Suggerimento edit frontmatter target** | suggerito | La skill emette in chat «Considera di aggiungere `risk_classification.tier: tiger-launch-blocking` al frontmatter di EP-XXX». Mai applicato in autonomia (R.P1) |

### Telemetria — append a `memory/episodic/premortem-runs.md` (ultimo step Fase 5)

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
  in questo file. Mai l'Orchestrator né altri agent (pur essendo in `memory/episodic/`,
  è un sotto-file con writer dichiarato unico).
- **Append-only**: nuove righe in coda alla sezione `## Log`, mai replace di righe
  esistenti.

## Anti-pattern

Comportamenti vietati di questa skill:

| Anti-pattern | Motivo | Cosa fare invece |
|---|---|---|
| Auto-apply del `revised_plan` modificando il file target | Viola R.P1 (output mai auto-applicato) | Emetti suggerimenti in chat, lascia all'utente l'edit |
| Output sanitizzato con contesto insufficiente | Viola R.P2 (bar minimo) — produce premortem inutile | Fail-loud, chiedi 1 domanda alla volta finché il bar è soddisfatto |
| Trigger automatico su parole chiave (es. "what could go wrong" nel chat) | Viola R.P3 (opt-in) — ADR-003 ha scartato phrase-trigger v2.16 | Solo `/premortem` esplicito |
| Modifica del body di EP/US/TSK target | Viola R.7 PATTERN (update non-distruttivo su review/approved) | Edita solo frontmatter (e solo se l'utente conferma); body intoccabile |
| Risk Registry con calibrazione degenere (tutto Tiger o tutto Paper Tiger) | Indica che il frame Fase 2 non ha funzionato o che il modello è sotto-calibrato | Riemetti la frase Fase 2 verbatim e richiedi a Fase 3 una passata più severa, oppure fail-loud |
| Premortem su decisione già irrevocabile (es. commit già pushato) | Spreca token e produce ansia inutile | Suggerisci `/premortem` per la prossima decisione, non per quella appena chiusa |
| Sovrapposizione con CQRL (premortem applicata al codice post-merge) | CQRL fa già evaluation post-fact; la premortem è pre-fact (livello decisionale diverso) | Usa CQRL pass `premortem-on-merge` (ADR-005, opt-in v2.16) per integrazione chirurgica; non duplicare |
