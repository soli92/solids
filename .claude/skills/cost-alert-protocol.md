---
id: cost-alert-protocol
version: v1.0
opt_in: analytics.cost_alert.enabled
depends_on_skill: token-ledger
tool: tools/analytics/cost_alert.py
agent: cost-alert
command: /cost-alert
---

# Skill: cost-alert-protocol

> Controllo dei costi in token dell'operatore contro regole configurabili, con avviso
> quando una soglia è superata. Il confronto è deterministico (`cost_alert.py`): nessun
> modello LLM fa i conti. Complementa `token-ledger` (display del costo) e
> `cost-and-time-analytics` (report retrospettivi sull'event store).

---

## Componenti

| Pezzo | Ruolo | Scrive |
|---|---|---|
| `analytics/alert-rules.yaml` | regole: `period`, `threshold_usd`, `action`, `notes`, `operator` (regola personale); `plans` (abbonamenti) e `subscriptions` (operatore → piano) | — (solo umano via PR) |
| `tools/analytics/cost_alert.py` | misura il costo, valuta le regole, gestisce i record | `analytics/alerts/` solo con `check --record` e `ack` |
| skill `cost-alert-protocol` (questa) | procedura e punti di integrazione | niente |
| comando `/cost-alert` | controllo on-demand, pendenti, presa in carico | `analytics/alerts/` solo con `--ack` |
| agente `cost-alert` | path `escalate`: analisi breve + record | `analytics/alerts/` (via `check --record`) |
| statusLine (`statusline-ledger.py`) | soglia di sessione e pendenti dopo ogni risposta | niente |

Interruttori in `factory.config.yaml → analytics.cost_alert`: `enabled` (master) e `agent`
(path escalate). Il blocco è indipendente da `token_ledger`.

## Da dove viene il costo

- **Transcript Claude Code di questa macchina** per la cartella del progetto
  (`~/.claude/projects/<cwd>/`): sessione principale + `subagents/agent-*.jsonl`.
  Una risposta API = un `message.id` (`parse_responses` di `harvest-session-tokens.py`).
- **Prezzi**: `analytics/pricing.yaml` (`load_pricing` di `show-session-tokens.py`). Modello
  assente dal listino → prezzo della famiglia, segnalato nelle note.
- **Periodi**: `session` = la chat corrente; `daily` = da mezzanotte locale; `weekly` = dal
  lunedì; `monthly` = dal primo del mese. I transcript sono per macchina, quindi il costo è
  quello dell'operatore.
- **Abbonamento**: se l'operatore è in `subscriptions`, il suo piano genera una regola sulla
  quota inclusa (`included_usd` per `included_period`) e il verdetto riporta la stima di
  addebito sul centro di costo: quota fissa mensile (`license_usd_month` −
  `central_funding_usd_month`) ed eccedenza sulla quota (`excess_usd`). Precedenza per periodo:
  regola personale > piano > regola generale. Chi non è censito resta sulle regole generali.
- L'event store `analytics/events/` non entra nel calcolo: si popola solo con un harvest
  esplicito e resta la fonte dei report di `analytics-reporter`.

## Procedura

### Step 0 — Gate

`cost_alert.py` legge da solo `analytics.cost_alert.enabled`: a flag spento restituisce un
verdetto vuoto con la nota «nessun controllo». Chi integra la skill non deve aggiungere altri
gate e non deve mai bloccarsi su questo passo.

### Step 1 — Verdetto

```bash
python3 tools/analytics/cost_alert.py check --period <session|daily|weekly|monthly|all> [--json]
```

Il verdetto contiene, per ogni regola del periodo: costo, soglia, rapporto, `breached` (e
`excess_usd` per la regola del piano); `plan` (il piano dell'operatore o `null`); poi
`escalations` (regole `escalate` superate), `agent_enabled`, `pending` (record non presi in
carico) e `notes`.

### Step 2 — Presentazione

Riporta il blocco testuale così com'è: righe per periodo e **tutte le note**, senza
riassumerle. Le note dicono cosa il numero non copre (altre macchine e worktree, modelli a
prezzo stimato, versioni di Claude Code non verificate, valuta): togliere le note trasforma
un numero parziale in un semaforo verde.

### Step 3 — Escalation (solo se `escalations` non è vuoto)

- `agent_enabled: true` → lancia l'agente `cost-alert` con `period` delle regole superate e
  l'ora UTC corrente. L'agente esegue `breakdown`, scrive una nota di due righe sulle cause
  e registra con `check --record --note "<nota>"`. Riporta in chat il path del record.
- `agent_enabled: false` → nessun agente: la regola vale come `warn` (il verdetto lo dice in
  nota).

Il record resta in `analytics/alerts/` finché l'operatore non lo prende in carico
(`/cost-alert --ack=<id>` o `--ack-all`); fino ad allora compare a `/session-start`, in `/run`
e nella statusLine.

## Punti di integrazione

Tutti **fail-open**: un errore del controllo diventa una riga di nota, mai uno STOP del
processo che lo ospita.

| Processo | Quando | Comando | Uso |
|---|---|---|---|
| statusLine | dopo ogni risposta | `status_line_suffix(cost.total_cost_usd)` | soglia di sessione (preavviso all'80%) + pendenti |
| `/session-start` | Fase 3f | `check --period daily` (`--auto`/`--quick`) · `check --period all` (manual) | sezione COSTI del briefing; nessuna scrittura, nessun agente |
| `/session-close` | Fase 1h | `harvest-session-tokens.py <transcript>` → `check --period all` | sezione costi del report; Step 3 se ci sono escalation |
| `/run` | dashboard | `check --period daily` | riga COSTI + pendenti; nessun agente |
| `/analytics` | dopo il report | `check --period all` | sezione «Soglie di costo», solo lettura |
| `/session-analysis` | Fase 4 | `check --period session --session-id <id>` | costo e soglia della sessione analizzata |
| prima di lanciare agenti | `/run` dispatch, `/dev` Fase 0, `/review`, `/tavola-rotonda` Step 2-bis | `check --gate` | `dispatch-policy` §13: con una riga `⚠` conferma umana, una volta per sessione e per alert |
| budget della `/tavola-rotonda` | Step 4.0 e 4.4 | `breakdown --period session --json` | costo misurato della tavola (adesso − base) passato al moderatore: la condizione di stop per budget non usa stime |
| wave paralleli | `parallel-scheduling` Fase 4 e Fase 5 punto 9 | `check --gate` | riga nel wave summary; il wave successivo passa dal gate |
| `/token-ledger` | — | rimando | il ledger mostra il costo, `/cost-alert` lo confronta con le soglie |
| `/plancia` | riquadro `cost_alert` | `check --json` | soglie, alert pendenti e note (collettore `visual/collectors/cost_alert.py`) |
| `/run` (Cursor) | punto 3-bis | `check --period daily --compact` | costo Claude Code della macchina (Cursor non è misurato) |
| `/init-check` | riga `pyyaml` | — | senza PyYAML le soglie non vengono valutate |

## Invarianti

- **Nessuna matematica LLM**: costi, soglie e verdetti vengono solo da `cost_alert.py`.
- **Regole single-writer umano**: nessun agente o tool modifica `analytics/alert-rules.yaml`.
- **Valuta**: confronto solo se `pricing.yaml` dichiara `USD`; altrimenti nessun verdetto e
  nota esplicita.
- **Record per operatore e locali**: `analytics/alerts/` è gitignored; ogni record porta
  `operator` e viene mostrato solo a chi lo ha generato.
- **Fail-open**: exit 0 sempre (2 solo per argomenti non validi).

## Limiti

- Sessioni lavorate in un'altra cartella (worktree, altro clone) o su un'altra macchina non
  entrano nel conteggio di questa.
- Claude Code ripulisce i transcript vecchi (`cleanupPeriodDays`): non incide su giorno e
  settimana, ma il tool non serve per periodi lunghi (per quelli: `/analytics`).
- Su versioni di Claude Code non verificate da `harvest-session-tokens.py` l'output dei
  subagenti può risultare sottostimato: il verdetto lo segnala in nota.
- I costi sono equivalenti a listino API, non la fattura di un abbonamento.
- **Cursor non è misurato.** Le sessioni dell'adapter Cursor non scrivono transcript in
  `~/.claude/projects/`: il tool vede solo il lavoro fatto con Claude Code (CLI, VS Code,
  desktop) su quella macchina. In Cursor la riga di `/run` riporta quindi il costo Claude Code
  dell'operatore, non quello della sessione Cursor in corso.
