---
name: factory-upgrade-protocol
description: >-
  Skill di UPGRADE incrementale di una factory llm-wiki++ esistente verso una versione target del
  PATTERN (default = ultima). A differenza di factory-bootstrap (greenfield scaffolder), questa
  NON ri-scaffolda da zero: calcola la catena di delta fra la versione corrente e la target,
  produce un piano (report + STOP), e applica SOLO i delta mancanti in modo non distruttivo,
  preservando le personalizzazioni della factory. Default dry-run; --apply per eseguire. Fulfills
  roadmap item `/retrofit-factory`.
---
# Skill — Factory upgrade (incremental, non-destructive)

Riferimenti: i delta seed `meta-prompts/v2-XX/factory-bootstrap.md` (ogni §0 enumera
cosa la versione *Aggiunge / Modifica / Rimuove*), `meta-prompts/README.md` (sezioni
«Diff vX → vY»), PATTERN §0 (versione), §7 (regole inviolabili — in particolare r.7
update non distruttivo, r.14 VCS gate, r.18), §13-§20 (feature per versione).

> **Perché esiste.** I seed `factory-bootstrap` sono greenfield scaffolder: sanno *creare*
> una factory, non *aggiornarne* una esistente. Ri-eseguire un bootstrap su una factory
> reale sovrascriverebbe le personalizzazioni. Questa skill chiude il gap: applica solo i
> **delta** fra versione corrente e target, in modo additivo e non distruttivo.

## Modello mentale: l'upgrade è la catena `extends:` applicata

Ogni release del PATTERN da v2.13 in poi è un **delta additivo** (vedi i seed
`meta-prompts/`). Un upgrade `v_from → v_to` = applicare in sequenza i delta di ogni
versione intermedia, esclusa `v_from`, inclusa `v_to`. Esempio: `v2.14 → v2.18` applica i
delta di v2.15 + v2.16 + v2.17 + v2.18. **Invariante chiave**: tutte le feature da v2.13 in
poi sono **opt-in, no-op a flag spento** → un upgrade è *additivo* e non cambia il
comportamento runtime finché l'utente non accende i nuovi flag.

## Input atteso

- `factory_path` (assoluto) — root della factory da aggiornare. Default: cwd.
- `to` — versione target (`v2-18` default = ultima; accetta anche `v2-18-full` come
  source consolidato del piano, equivalente funzionalmente a `v2-18`).
- `from` — versione corrente (`auto` default → letta da `factory.config.yaml.pattern_version`
  / `PATTERN.md` §0; override solo se la detection fallisce o il file è stato manomesso).
- `mode` — `dry-run` (default: solo piano, report + STOP) | `apply` (esegue, gated).
- `meta_source` — local clone del meta-framework o raw GitHub (per leggere i template
  canonici di ogni versione). Risolto come in factory-bootstrap §«Risoluzione source».

## Fase 0 — Detection

1. Verifica `factory_path` è una factory valida: esiste `factory.config.yaml` + `PATTERN.md`.
   Se no → **STOP**: «<path> non è una factory llm-wiki++ (manca factory.config.yaml/PATTERN.md)».
2. Leggi `v_from`:
   - `factory.config.yaml.pattern_version` (autorità primaria).
   - cross-check con `PATTERN.md` §0 e con la presenza di marker-file (es. esiste
     `.claude/skills/caveman-protocol.md` ⇒ ≥ v2.14; `visual-oracle-protocol.md` ⇒ ≥ v2.17;
     `accessibility-testing-protocol.md` ⇒ ≥ v2.18). Se config e marker divergono, segnala
     l'incoerenza e usa il **minimo** (conservativo) — l'upgrade è idempotente, ri-applicare
     un delta già presente è no-op grazie ai check di Fase 3.
3. Risolvi `v_to` (default ultima). Se `v_from == v_to` → **STOP**: «Factory già a <v_to>,
   nulla da fare» + esegui comunque il self-test target (Fase 4) come health-check.
4. Se `v_from > v_to` (downgrade) → **STOP**: i downgrade non sono supportati (rimuovere
   feature può rompere artefatti già prodotti). Segnala e termina.
5. **Precondizione VCS** (R.14): se `factory_path` è un repo git, verifica
   `git -C <factory_path> status --porcelain` → se working tree sporco, **WARN** e chiedi
   conferma esplicita prima di procedere in `apply` (un backup pulito è la rete di sicurezza).

### Step 0.bis — Adapter Detection

6. Rileva l'adapter della factory target:
   - Se esiste `<factory_path>/adapters/cursor/manifest.yaml` → `detected_adapter=cursor`, imposta `CURSOR_MODE=true`.
   - Altrimenti → `detected_adapter=claude`, `CURSOR_MODE=false`.
   - Se `CURSOR_MODE=true`: stampa avviso «Factory Cursor rilevata — verrà applicata la strategia di traduzione Cursor (§ Strategia Cursor)» e continua.
   - Se la factory ha sia `.claude/` sia `adapters/cursor/` → usa `CURSOR_MODE=true` (Cursor è il runtime primario).

## Fase 1 — Resolve delta chain

Costruisci `chain = [versioni da (v_from esclusa) a (v_to inclusa)]`. Per ciascuna versione
della catena, leggi dal `meta_source`:
- `meta-prompts/<ver>/factory-bootstrap.md` §0 (enumera Aggiunto/Modificato/Rimosso).
- la sezione «Diff» corrispondente in `meta-prompts/README.md`.

Da queste fonti deriva, per ogni versione, tre liste:
- **ADD** — file nuovi introdotti (skill/command/agent/tool/runbook) + blocchi config nuovi.
- **MODIFY** — file esistenti che il delta tocca (es. v2.17 aggiunge Fase 4-bis a
  `dev-protocol`; v2.18 aggiunge Check 4o/4p a `lint-checks`).
- **PATTERN** — l'indice `PATTERN.md` **e i moduli elencati nella sua tabella `## Moduli`**
  (US-319: §12+ vivono in `PATTERN-<nome>.md`) vanno sostituiti verbatim con quelli della
  `v_to` (contratto, mai personalizzato dalla factory). Vedi «PATTERN: indice + moduli» sotto.

### PATTERN: indice + moduli (US-319)

Il PATTERN si copia come **insieme**: indice + ogni modulo linkato nella tabella §Moduli
del master, nell'ordine della tabella. Mai un glob (`PATTERN-historical.md` non e' un
modulo). Tre casi della factory target, nessuno dei quali e' un CONFLICT:

| Target | Azione |
|---|---|
| monolitico (nessuna tabella §Moduli) | REPLACE dell'indice + COPY dei moduli: la factory migra allo split |
| gia' splittato, file identico al master | SKIP (idempotenza) |
| gia' splittato con uno split **proprio** (altri nomi, sezioni in piu') | REPLACE dei file del master; ogni sezione top-level `## §N` **assente nel master** e' **locale**: si riappende in coda al modulo omonimo (o all'ultimo modulo) con il marcatore `<!-- sezione locale della factory, preservata da factory-upgrade (assente nel master) -->`. I file modulo che il master non elenca restano su disco (mai cancellati) e sono riportati come orfani |

Il piano li elenca come riga dedicata: `[PATTERN] <modo> · replace <file> · locali <§N (file)> · orfani <file>`.
Implementazione deterministica: `python3 tools/factory-upgrade-apply.py <factory> --dry-run`
(riga `PATTERN [...]`). Una sezione locale che collide per numero con una sezione del
master **non** e' locale: vince il master (verbatim), e il piano la mostra fra i REPLACE.
Le **note della factory** dentro un file del PATTERN (righe proprie in sezioni comuni) vanno in una
sezione `## Locale — <titolo>`: e' conservata nel suo file come una §N assente nel master. Righe
locali lasciate dentro sezioni comuni il piano le elenca e `--apply` le salva solo nel backup
(`righe-locali-PATTERN.md`): da riunire a mano. Le §N locali collidono con le §N future del master:
una derivata che ne aggiunge le dichiara in `## Locale — …` o si aspetta il conflitto all'upgrade.

**Unita' del solo meta-framework nella derivata** (`META_ONLY_PATHS` di `tools/factory_scope.py`:
`/factory-bootstrap`, `/factory-upgrade`, `/release`, `pattern-b-testbed`, lo strumento di upgrade e i
suoi test). Le portava l'installer fino a v2.46.1, e l'upgrade e' add-only: non le toglie da solo. Il
piano le riporta sempre, divise in identiche al master e modificate nella factory. Con
`--prune-meta-only` (opt-in, solo con `--apply`) si rimuovono le **identiche**, con copia nel backup
(`meta-only/<path>`); le **modificate restano**: sono della factory e si decidono a mano.

> La catena è la stessa documentata nel seed consolidato
> `meta-prompts/v2-18/factory-bootstrap-full.md` (utile come riferimento unico del «cosa
> dovrebbe esserci alla fine»).

### Delta supplementare v2.27-post (EP-040 factory-optimization-2026-07-07)

Ottimizzazioni strutturali non associate a un bump di versione. Applicate **automaticamente**
quando `v_to == v2-27` (o superiore): se i file elencati mancano nella factory target,
trattarli come ADD; se presenti, skip (idempotente).

**ADD — nuovi file:**

| File | Tipo | Nota |
|---|---|---|
| `.claude/skills/dispatch-policy.md` | skill | Contratto dispatch condizionale (8 sezioni) |
| `.claude/skills/wiki-keeper-worker-protocol.md` | skill | Worker sub-agent protocol per ingest parallelo |

**MODIFY — file modificati:**

| File | Modifica attesa |
|---|---|
| `.claude/agents/orchestrator.md` | Ridotto a < 100 righe; body rimanda a `dispatch-policy` |
| `.claude/agents/*.md` (tutti) | Frontmatter `capabilities: [...]` presente |
| `.claude/skills/lint-checks.md` | Check 4ai + Check 4aj presenti |
| `.claude/skills/wiki-log-entry.md` | Template `wave` e `develop` con WAVE_ID presenti |
| `factory.config.yaml` | Blocco `models.routing` (Central Model Registry) presente |
| `PATTERN.md` | §29 (Factory Scalability Patterns) presente |

**Marker di rilevamento** (auto-detect se il delta è già stato applicato):
- `.claude/skills/dispatch-policy.md` esiste → delta già applicato.

### Strategia Cursor (CURSOR_MODE=true)

Quando `CURSOR_MODE=true` la traduzione dei delta segue le **convenzioni Cursor** anziché copiare file `.claude/` raw:

| Tipo sorgente | Path sorgente | Path Cursor target |
|---|---|---|
| Agent | `.claude/agents/<name>.md` | `.cursor/rules/<name>.mdc` |
| Skill | `.claude/skills/<name>.md` | `.cursor/rules/skills/<name>.mdc` |
| Command | `.claude/commands/<name>.md` | `.cursor/commands/<name>.md` |

**Per ogni file ADD della catena delta:**

1. Verifica se esiste il template in `<meta_source>/adapters/cursor/templates/<path-cursor>`.
2. Se il template esiste → azione `CURSOR_COPY` (copia il template Cursor, non il file `.claude/` raw).
3. Se il template manca → log `CURSOR_TEMPLATE_MISSING: <name>` + skip (non copiare il `.claude/` raw in una factory Cursor).

**Per i file MODIFY:** stessa logica — se il template Cursor aggiornato esiste, `CURSOR_PATCH`; altrimenti `CURSOR_TEMPLATE_MISSING`.

**Elementi sempre esclusi dalle factory Cursor** (non traducibili o non rilevanti):
- `voice/` — modulo Python esterno
- `factory-bootstrap.md`, `factory-upgrade.md`, `release.md` — meta-comandi del meta-repo
- `figma-sync.md` (agent) — richiede MCP Figma

**Nessun spawning ricorsivo durante la traduzione**: se viene lanciato un sub-agent per la traduzione Cursor, il brief deve includere esplicitamente: «Nessun spawning ricorsivo. Processa i file in sequenza o in batch deterministico. Max 1 livello di sub-agent.»

**PATTERN.md e factory.config.yaml**: identici alla strategia Claude (REPLACE verbatim + MERGE config).

## Fase 2 — Plan (report + STOP) — *sempre, anche in `apply`*

Per ogni file/blocco nelle liste ADD/MODIFY, classifica lo stato nella factory target e
assegna un'**azione**, confrontando con il template canonico della versione che lo introduce:

| Categoria | Stato nella factory | Azione |
|---|---|---|
| ADD file | assente | **COPY** (sicuro) |
| ADD file | presente, identico al canonico-precedente | **COPY** (overwrite sicuro) |
| ADD file | presente, **diverge** dal canonico | **CONFLICT** → non toccare, elenca per review manuale |
| ADD config block | assente | **MERGE** additivo, tutti i flag `false` (no behavior change) |
| ADD config block | presente | **SKIP** (già lì; non sovrascrivere valori utente) |
| MODIFY file | contiene già la sezione delta (marker) | **SKIP** (idempotente) |
| MODIFY file | assente la sezione + file == canonico-precedente | **PATCH** (inserisci sezione) |
| MODIFY file | assente la sezione + file **diverge** (personalizzato) | **CONFLICT** → suggerisci patch, gate manuale, non auto-merge |
| PATTERN.md + moduli §Moduli | qualsiasi | **REPLACE** verbatim con `v_to`; sezioni locali preservate, orfani mai cancellati (vedi sopra) |

Produci il **piano** in chat e **STOP** (R.6 report preliminare prima di scritture batch):

```
========================================
FACTORY UPGRADE PLAN — <v_from> → <v_to>
========================================
Factory: <factory_path>
Catena delta: <v_from> → [<ver1>, <ver2>, ...] → <v_to>

[COPY]      <N> file nuovi additivi (sicuri)
[MERGE]     <M> blocchi config nuovi (flag tutti false → nessun cambio comportamento)
[PATCH]     <P> sezioni in file esistenti (file == canonico, inserimento sicuro)
[REPLACE]   PATTERN.md + moduli → <v_to> verbatim
[PATTERN]   <monolitico->split|split->split> · locali <§N (file)|-> · orfani <file|->
[SKIP]      <S> già presenti (idempotenza)
[CONFLICT]  <C> file personalizzati toccati dai delta → REVIEW MANUALE (vedi sotto)

[DETTAGLIO CONFLICT]   (richiedono la tua decisione)
- <path>: la factory ha personalizzato questo file; il delta <ver> vorrebbe <cosa>.
  Suggerimento patch: <diff/sezione da inserire>. Azione: applica a mano o approva.

[POST-UPGRADE — opt-in, NON attivati automaticamente]
Le nuove capability restano spente. Per attivarle dopo l'upgrade:
- <ver> <capability>: <flag da accendere> + prerequisito <es. Playwright>.

In dry-run mi fermo qui. Per applicare COPY+MERGE+PATCH+REPLACE (i CONFLICT restano a te):
  /factory-upgrade <factory_path> --to=<v_to> --apply
```

Se `mode == dry-run` → **termina qui** con `status: planned`.

## Fase 3 — Apply (solo se `mode == apply`, gated)

1. **Backup** (rete di sicurezza, mai distruttivo): crea
   `<factory_path>/.factory-upgrade-backup/<v_from>-to-<v_to>-<YYYYMMDD-HHMM>/` con copia
   dei file in MODIFY/REPLACE che verranno toccati. Registra la dir in `.gitignore` se non
   già coperta. (Se la factory è git pulito, il backup è ridondante ma innocuo.)
2. Applica nell'ordine: **COPY** → **MERGE** (config) → **PATCH** → **REPLACE** (PATTERN.md + moduli, poi riappendi le sezioni locali).
   - I **CONFLICT** NON vengono applicati: restano elencati nel report finale per intervento
     manuale (R.7 update non distruttivo su contenuto personalizzato).
   - **MERGE config**: inserisci i blocchi nuovi con tutti i flag al default `false`. Mai
     toccare valori esistenti. Mantieni commenti/ordine il più possibile.
   - **PATCH**: inserisci la sezione delta nel punto documentato dal delta seed (es.
     «Fase 4-bis» in `dev-protocol`), solo se il file è ancora == canonico-precedente.
3. **Bump** `factory.config.yaml.pattern_version` → `<v_to numerico>` (es. `"2.18"`).
4. **VCS gate (R.14)**: **mai** auto-commit / auto-push. Stampa il comando suggerito:
   ```
   git -C <factory_path> add -A && git -C <factory_path> commit -m "chore: upgrade factory <v_from> → <v_to>"
   ```
5. Idempotenza: ri-eseguire l'upgrade alla stessa target dopo un apply ⇒ tutto SKIP.

## Fase 4 — Validate (self-test target)

Esegui la checklist di accettazione della `v_to` (dal seed target / consolidato `-full`
§Self-test). In upgrade, i check «file esiste» valgono come in bootstrap; i check di
attivazione si applicano solo se l'utente ha già acceso i flag (di norma no, subito dopo
l'upgrade). Segnala PASS/FAIL. **Mai dichiarare upgrade completato con check strutturali
falliti** (i CONFLICT non risolti sono `partial`, non `failed`).

## Fase 5 — Report finale

```
========================================
FACTORY UPGRADE <stato> — <v_from> → <v_to>
========================================
Factory: <factory_path>
Backup:  <path backup o "git working tree (clean)">

[APPLICATO]  COPY <N> · MERGE <M> · PATCH <P> · REPLACE PATTERN.md
[SKIP]       <S> (idempotenza)
[CONFLICT]   <C> da risolvere a mano (elenco con suggerimenti patch)

[SELF-TEST <v_to>]  <K>/<K> strutturali PASS

[ATTIVAZIONE OPT-IN — prossimi step facoltativi]
<per ogni capability nuova: flag + prerequisito>

[VCS]  comando commit suggerito (mai eseguito automaticamente, R.14)
```

## Return value

```yaml
status: planned | success | partial | failed
v_from: <ver>
v_to: <ver>
applied: { copy: N, merge: M, patch: P, replace: 1 }
skipped: S
conflicts: [<path>, ...]
self_test: <K>/<K>
backup_path: <path | null>
```

## Vincoli inviolabili

- **Non distruttivo (R.7)**: mai sovrascrivere file personalizzati; i CONFLICT si elencano,
  non si auto-mergiano. Backup obbligatorio prima di ogni write in `apply`.
- **VCS gate (R.14)**: mai `git commit/push/--force/--amend` automatici; solo stampa.
- **Additivo / no behavior change**: i blocchi config nuovi entrano con flag `false`;
  l'upgrade non accende capability né cambia il comportamento runtime senza azione utente.
- **Report + STOP (R.6)**: dry-run è il default; il piano va mostrato prima di scrivere.
- **Idempotente**: ri-applicare alla stessa target è no-op (tutto SKIP).
- **No downgrade**: `v_from > v_to` → STOP.
- **PATTERN.md è il contratto**: indice e moduli sostituiti verbatim, mai patchati; le sole
  sezioni top-level assenti nel master sono preservate (non sono contratto del master).
- **Agent-agnostic**: il piano cita PATTERN.md e i delta seed, non costrutti runtime-specifici.

## Appendice A — Known Local-Diff Files

I seguenti file **differiscono legittimamente tra factory** per contenere path o config locali. Non vanno trattati come errori: segnalarli come `CONFLICT(local-path)` anziché `CONFLICT`, mostrare un diff riassuntivo, ma non bloccare l'upgrade.

| File | Motivo della divergenza |
|---|---|
| `CLAUDE.md` | Path assoluto di `show-session-tokens.py` (diverso per ogni factory) |
| `.claude/skills/token-ledger.md` | Può differire per path locali o script path |
| `.claude/settings.json` | Path hook locali (`CLAUDE_PROJECT_DIR`, `--from-hook`) |
| `factory.config.yaml` | Personalizzazioni utente (flag attivi, model override, path specifici) |

**Distinguere `CONFLICT` da `CONFLICT(local-path)`** nella sezione `[DETTAGLIO CONFLICT]` del piano aiuta l'utente a capire quali diff sono strutturali (richiedono merge ragionato) e quali sono solo path-locali (richiedono solo aggiornare il path).

## Appendice B — Note di ambiente (sandbox / tooling)

- **`git` va invocato flat top-level**: non dentro funzioni shell o loop. In ambiente sandbox Claude Code, `git` dentro costrutti shell (`function f() { git ... }`, `for x in ...; do git ... done`) può risultare «command not found» silenziosamente. Usare sempre comandi `git` diretti a top-level del contesto LLM.
- **Unix tool potenzialmente assenti**: `head`, `tail`, `sed`, `awk`, `comm`, `sort`, `basename` possono uscire con `exit 127` in ambienti sandbox. Usare Python (`python3 -c "..."` o script `.py`) come fallback universale per operazioni su file/diff/config.
