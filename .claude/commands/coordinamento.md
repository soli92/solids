---
name: coordinamento
description: "Report PM deterministico dal kanban (EP-070): allineamento della config con proposte su conferma, store dei TSK senza owner, misura al commit con verifica L0, vista HTML, narrativa opzionale a citazioni verificate. Nessun numero dal modello, nessuna scrittura nel kanban. A pm_report.enabled false risponde con un fallback esplicito, non con un errore."
argument-hint: "[--operatore=<id>] [--solo-controllo] [--oggi=AAAA-MM-GG] [--ref=<sha>] [--fonte=commit|worktree] [--narrativa=<file>] [--proposte-kanban] [--pianifica]"
allowed-tools: Read, Glob, Bash, Agent, AskUserQuestion
skill: coordinamento-giornaliero
agent: pm-report-coordinator
opt_in: pm_report.enabled
epic: EP-070
pattern_version: "2.43"
---

# /coordinamento

Argomenti utente: `$ARGUMENTS`

Produce il **report PM deterministico**: misura del kanban committato, verifica L0 indipendente,
vista HTML con avvisi a regole e prompt di verifica per ogni voce. Tutti i valori vengono da
`tools/coordinamento/`; il modello li riporta. Si esegue **nella sessione principale**: il Passo 1
lancia un subagente `Explore` e chiede all'operatore, cose che un subagente non puo' fare.
`pm-report-coordinator` serve alle esecuzioni non interattive (es. da `/run`).

**Cosa non da'**: nessuna modifica al kanban (le proposte vanno al `tpm` su gate del PO), nessun
numero stimato, nessun report alternativo se la pipeline fallisce, nessun arbitro fra operatori.

## Sintassi

| Flag | Default | Semantica |
|---|---|---|
| `--operatore=<id>` | da `git config user.name` sul `team` delle config | `analytics/coordinamento/config-<id>.json` |
| `--solo-controllo` | assente | Solo Passo 1 (allineamento), senza report |
| `--oggi=AAAA-MM-GG` | data locale | Data di riferimento, la stessa per store e misura |
| `--ref=<sha>` | `HEAD` | Commit del kanban da misurare |
| `--fonte=commit\|worktree` | `commit` | `worktree` legge il disco: **non riproducibile** |
| `--narrativa=<file>` | assente | Narrativa con citazioni `[F:percorso]` da verificare (Passo 3) |
| `--proposte-kanban` | assente | Mostra le proposte config→kanban per il `tpm` |
| `--pianifica` | assente | Passo 4: `pianifica.py` (classifica di priorita' e proposte di owner); le confermate vanno al `tpm` |

## Procedura

### Step 0 — Gate `pm_report.enabled` (fallback esplicito, non errore)

Leggi il blocco `pm_report:` di `factory.config.yaml`.

```
enabled: false   -> «/coordinamento: capability pm_report spenta (pm_report.enabled: false).
                     Nessun report generato.»  Fine, nessuno script lanciato.
blocco assente   -> «/coordinamento: capability pm_report non configurata. Per accenderla:
                       pm_report:
                         enabled: true
                     in factory.config.yaml.»  Fine.
```

### Step 1 — Argomenti

Estrai i flag della tabella. Argomento non riconosciuto → STOP: «`/coordinamento` non riconosce
`<arg>`. Flag validi: --operatore, --solo-controllo, --oggi, --ref, --fonte, --narrativa,
--proposte-kanban, --pianifica.»

### Step 2 — Operatore e config

- `--operatore` presente: la config e' `analytics/coordinamento/config-<id>.json`; se non esiste →
  STOP con il path atteso e l'istruzione «copia `config-esempio.json` in `config-<id>.json` e
  adatta obiettivi e team».
- assente: cerca `git config user.name` nel `team` (nome o alias) delle `config-*.json`. Una sola
  corrispondenza → quella; nessuna o piu' d'una → chiedi con `AskUserQuestion`, elencando le config
  presenti piu' «altro (indica l'ID)». Mai scegliere a caso.

### Step 3 — Esecuzione

Segui la skill `.claude/skills/coordinamento-giornaliero.md` in questa sessione, con:

```yaml
operatore: <id>
config: analytics/coordinamento/config-<id>.json
ref: <sha|HEAD>
oggi: <AAAA-MM-GG>
fonte: <commit|worktree>
solo_controllo: <true|false>
narrativa: <path|null>
proposte_kanban: <true|false>
pianifica: <true|false>
```

Sequenza: claim advisory → Passo 1 → (se non `--solo-controllo`) Passo 1b
`proponi_kanban.py --ref <ref> --oggi <oggi> --aggiorna-store` **prima** di `run.py` → Passo 2
→ Passo 3 se richiesto → Passo 4 se `--pianifica` → release del claim.

### Step 4 — Output

- Riepilogo in chat (8-12 righe dal `RIEPILOGO`) e path completo dell'HTML.
- `--fonte=worktree`: «lettura dal disco, non riproducibile».
- `--solo-controllo`: candidati per tipo; 0 → «configurazione allineata».
- `--proposte-kanban`: TSK senza owner con `prima_vista` e proposte, dichiarate **per il `tpm`,
  su gate del PO**; nulla viene applicato.
- `--pianifica`: prime voci della classifica, proposte di owner con la motivazione dello script, non
  assegnabili e capacita' per persona. Blocco `pianificazione` assente → lo script esce con 2:
  proponi il blocco, applicalo solo dopo conferma. Le proposte confermate vanno al `tpm`.

## Degradazione

| Condizione | Comportamento |
|---|---|
| `pm_report.enabled` false o assente | Fallback esplicito (Step 0) |
| Config dell'operatore assente | STOP con path atteso e istruzione |
| Exit diverso da 0 di uno script | STOP: passo e messaggio; nessun report alternativo |
| `verifica_l0.py` fallita | Nessuna vista; si riporta lo scostamento |
| Claim di un'altra sessione su `analytics/coordinamento` | Avviso, si prosegue (cooperative locking, EP-053) |

## Vincoli

- Scritture solo tramite gli script: `deliverables/coordinamento/report-pm/`,
  `analytics/coordinamento/<operatore>/da_assegnare.yaml`, `analytics/coordinamento/storico/`
  (dopo conferma) e la config dell'operatore via `applica_config.py` (dopo conferma).
- Mai `management/kanban/`, `wiki/` (§7 r.12), `factory.config.yaml`.

## Cross-link

Agente `.claude/agents/pm-report-coordinator.md` · skill `.claude/skills/coordinamento-giornaliero.md` ·
motore e limiti `tools/coordinamento/README.md` · epica `management/kanban/EP-070-report-pm-deterministico/EP-070.md`.
