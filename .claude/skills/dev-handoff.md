---
name: dev-handoff
description: Entry per wiki/log.md a chiusura di un TSK consumato da dev-agent (operazione Develop, PATTERN §3).
---
# Procedura — handoff dev-agent → wiki/log.md

Append-only su `wiki/log.md` quando un dev-agent completa un TSK
(status `in-progress` → `done`).

## Formato entry

```markdown
## YYYY-MM-DD HH:MM — develop TSK-ZZZ
**Agente:** <be-dev|fe-dev|db-dev|qa-dev>
**TSK:** [[../management/kanban/EP-XXX-<slug>/US-YYY-<slug>/TSK-ZZZ]]
**Layer:** <be|fe|db|qa|infra>
**Code path:** <code_path da factory.config.yaml — relativo o assoluto>
**Files touched:** <count> (lista compatta solo se ≤ 5; altrimenti "vedi commit")
**Commit:** <hash short se code_path è git tracciato; oppure "n/a">
**DoD:** <pass | partial — descrivi> 
**Note:** <free-form, max 2-3 righe; segnala blocker non-bloccanti rilevati>
```

## Esempi

### Caso normale (DoD pass, code_path interno al repo)

```markdown
## 2026-05-20 14:32 — develop TSK-042
**Agente:** be-dev
**TSK:** [[../management/kanban/EP-003-auth/US-012-login/TSK-042]]
**Layer:** be
**Code path:** ./src/
**Files touched:** 3 (src/auth/login.py, src/auth/router.py, src/tests/test_login.py)
**Commit:** a1b2c3d
**DoD:** pass
**Note:** Implementato OIDC verbatim per coerenza con raw/tech_stack.md.
```

### Caso code_path esterno

```markdown
## 2026-05-20 16:10 — develop TSK-043
**Agente:** fe-dev
**TSK:** [[../management/kanban/EP-003-auth/US-012-login/TSK-043]]
**Layer:** fe
**Code path:** /Users/me/Repos/customer-portal/
**Files touched:** vedi commit
**Commit:** e4f5g6h (su repo esterno customer-portal)
**DoD:** pass
**Note:** —
```

### Caso DoD parziale (blocker)

```markdown
## 2026-05-20 18:00 — develop TSK-044 (PARTIAL)
**Agente:** db-dev
**TSK:** [[../management/kanban/EP-003-auth/US-012-login/TSK-044]]
**Layer:** db
**Code path:** ./src/
**Files touched:** 1 (migrations/004_add_session_table.sql)
**Commit:** —
**DoD:** partial — test integration non disponibile (db test fixture mancante)
**Note:** Status TSK resta `in-progress`. Apro gap "missing-db-test-fixture" in wiki/gaps.md.
```

## Regole

- **Append-only**: mai editare entry passate (PATTERN §7 r.5).
- **Una entry per TSK chiuso**. Se serve correggere, append nuova entry con marker
  `## YYYY-MM-DD HH:MM — develop TSK-ZZZ (correction)`.
- **Mai citare il codice prodotto direttamente in wiki/log.md** (rumore). Cita
  TSK; chi vuole il codice apre il commit / il file.
- **Coerenza con `dev-protocol`**: l'entry si scrive SOLO se `status: done` o
  `status: in-progress (partial)`. Mai per TSK in fase di gate.

## Protocollo di chiusura — verifiche obbligatorie

Le verifiche seguenti si applicano *prima* di scrivere l'entry in `wiki/log.md` e *prima*
di impostare `status: done` sul file TSK. Sono vincolanti per ogni dev-agent che esegua
`dev-handoff`. La regola sulla semantica di `done` vincola anche l'orchestratore quando
propaga lo stato a valle.

### Regola di evidenza sulle affermazioni ambientali

Un dev-agent puo' fare affermazioni sullo stato dell'ambiente — raggiungibilita' di rete,
installabilita' delle dipendenze, disponibilita' di credenziali, esito di build. Queste
affermazioni devono appartenere a una sola delle due classi seguenti:

| Classe | Definizione | Uso consentito |
|---|---|---|
| **Fatto verificato** | Comando eseguito; output citato nel report | Puo' motivare skip; puo' dichiarare AC soddisfatto |
| **Ipotesi** | Nessun comando eseguito; formulata come previsione | Non puo' motivare skip; non puo' dichiarare AC soddisfatto |

Un'affermazione che non cita il comando eseguito e il suo esito e' un'ipotesi — anche se
formulata come certezza.

**Vincolo sull'orchestratore**: un'affermazione ambientale priva di evidenza non va
propagata a valle come fatto. L'orchestratore la etichetta esplicitamente come «ipotesi da
verificare» prima di passarla ad altri agenti o usarla come giustificazione per uno skip.

> **Caso osservato** — post-mortem di sessione su una factory derivata della flotta (2026-09-24, anomalia A1): un'affermazione mai testata sull'indisponibilita' di un
> ambiente di build e' entrata nel contesto dell'orchestratore, e' stata propagata a due
> agenti a valle e ha giustificato lo skip del build per tre task consecutivi; alla verifica
> l'install e' riuscito in sei minuti. Una conclusione negativa non testata rimuove
> l'incentivo a testare — ed e' per questo che e' sopravvissuta a tre task.

### Diff di chiusura: file dichiarati vs file effettivamente modificati

Prima di scrivere il log entry, il dev-agent esegue un confronto meccanico — tramite comando,
non ricostruito a memoria — fra i file dichiarati nel proprio scope e quelli modificati nel
working tree.

Comandi minimi da eseguire e citare nel report:

```bash
git status --short         # file nel working tree (staged e unstaged)
git diff --name-only HEAD  # file modificati rispetto al commit di partenza
```

Il report riporta tre campi distinti:

1. **Dichiarati nel scope** — i file che il task prevedeva di toccare.
2. **Committati** — presenti nel commit del task (o in commit locali non ancora pushati).
3. **Nel working tree** — staged o unstaged, non ancora committati.

Un file toccato e non dichiarato non e' di per se' un errore: l'obbligo e' *riportarlo*, non
renderlo impossibile. La mancata segnalazione e' la violazione.

> **Caso osservato** — stessa sessione, anomalia A8: un dev-agent ha alterato il manifest di progetto di un
> repo — rimuovendo un campo e aggiungendone un altro — senza che il file comparisse nel
> report. La modifica e' stata trovata solo perche' l'orchestratore ha eseguito `git status`
> per altro. Se la sessione fosse finita li', il file sarebbe rimasto nel working tree come
> lavoro non attribuito.

### Semantica di `done` — lo stato si deriva dalla tabella AC

`status: done` non puo' essere scelto indipendentemente dalla tabella degli AC. Il passo di
derivazione e' obbligatorio a ogni chiusura:

```
per ogni AC del task:
  ✓ se verificato
  ✓ se non verificato, ma derogato (motivazione registrata nel file TSK)
  ✗ se non verificato e non derogato → status = in-progress oppure blocked
```

| Condizione | Status corretto |
|---|---|
| Tutti gli AC verificati | `done` |
| Uno o piu' AC derogati con motivazione registrata nel file TSK | `done` |
| Uno o piu' AC «non verificabili» e non derogati | `in-progress` o `blocked` |

**Deroga**: e' una forma prevista e legittima. L'obiettivo non e' rendere impossibile chiudere
un task con AC non verificabili — e' renderlo impossibile **in silenzio**. La deroga viene
registrata nel corpo del file TSK (sezione `## Esito` o nota esplicita) e specifica: quale
AC e' derogato, il motivo tecnico, e l'eventuale autorizzazione di gate umano.

Un agente puo' essere onesto nella tabella degli AC e incoerente nello status. Il board
mostra solo lo status — che e' l'unica cosa che un lettore successivo vede. Questa regola
obbliga lo status a essere *derivato* dalla tabella, non scelto a parte.

Date di lavoro, obbligatorie dal `kanban_dates.required_from` di `factory.config.yaml` (Check 4be, ERROR): chi cambia lo stato scrive nel TSK `started_at` (YYYY-MM-DD) al passaggio a `in-progress` e `closed_at` al passaggio a `done`, con la data del lavoro e non quella della registrazione (`closed_at >= started_at`). Lo stesso vale per l'orchestratore quando propaga lo stato.

> **Caso osservato** — stessa sessione, anomalia A9: un task e' stato marcato `done` dichiarando nella stessa
> tabella due AC come non verificabili, nonostante l'istruzione esplicita nel prompt di
> preferire `in-progress`. L'istruzione nel prompt non e' bastata: il passo di derivazione
> deve stare nel protocollo, non nel prompt.

## Cross-reference

- Cita: `wiki-log-entry` (formato generale log entries)
- Invocata da: `dev-protocol` (Fase 5)

---

## Decision Anchor Propagation (opt-in v2.19, EP-015)

> **Gated**: `factory.config.yaml.compression.output.decision_anchor.enabled: true`.
> A flag spento questa sezione è no-op (R.P3).

Leggi obbligatoriamente `.claude/skills/references/dev-handoff/decision-anchor.md`
prima di emettere l'handoff quando il flag è attivo — se il file manca, STOP e segnala.
Contiene: step pre-handoff (verifica presenza + checksum), struttura handoff arricchita,
errori `anchor-stripped` / `anchor-tampered`.

---

## Temporal Handoff Block (opt-in v2.18+, gated da `temporal.handoff_protocol.enabled`)

Quando `factory.config.yaml.temporal.handoff_protocol.enabled: true`, ogni handoff
include un blocco YAML strutturato `temporal_handoff:` con **5 campi obbligatori**.

Leggi obbligatoriamente `.claude/skills/references/dev-handoff/temporal-handoff.md`
prima di emettere qualsiasi handoff con flag attivo — se il file manca, STOP e segnala.
Contiene: schema canonico, punti di iniezione, calcolo dei campi (ADR-030), esempio
dual-format, proiezione da State Machine, vincoli enforced, backward compat.

A flag spento (`temporal.enabled: false` o `temporal.handoff_protocol.enabled: false`):
skip — comportamento identico a v2.7 (R.P3).

---

## Suggerimento post-esecuzione (EP-033, v2.24)

> **Trigger**: il dev-agent esegue questa sezione al termine di ogni TSK, immediatamente
> prima di terminare l'handoff. Se il layer del TSK non ha regole definite nella tabella
> in foglia → no-op silenzioso.

Leggi obbligatoriamente `.claude/skills/references/dev-handoff/suggerimento-post-exec.md`
se il layer del TSK ha regole definite — se il file manca, STOP e segnala.
Contiene: dati letti, regole per layer (fe/be/db/qa/docs), gate installazione,
deduplication, formato output, tono, backward compat.

Factory senza capability suggerite → gate falliscono silenziosamente → no output (R.P3).

## Contatori a fine TSK — `on_tsk_closed_count` (repo-align, ai_policy_check, opt-in)

Dopo `status: done` (mai su un TSK parziale), esegui:

```bash
python3 tools/vcs/contatore_chiusure.py --tsk <TSK-id>
```

Lo script incrementa i contatori delle capability accese con soglia > 0 (`repo_align`,
`ai_policy_check` in `factory.config.yaml`, `triggers.on_tsk_closed_count`) e, alla soglia, stampa
la verifica da eseguire (`tools/vcs/repo-align.py`, `tools/vcs/ai-policy-scan.py`): eseguila e
riporta l'output **integrale** in chat (R.18). Nessuna riga = nessuna soglia raggiunta. Mai
bloccante: un errore del contatore e' una riga di avviso e l'handoff prosegue. Le verifiche sono
in sola lettura: mai `fetch`, `pull`, `checkout` (R.14, R.B8).
