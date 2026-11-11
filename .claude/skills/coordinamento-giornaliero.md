---
name: coordinamento-giornaliero
description: >-
  Protocollo del report PM deterministico (EP-070): allineamento della config al kanban con
  proposte su conferma, store dei TSK senza owner, misura dal kanban committato con verifica
  L0 indipendente, vista HTML con prompt di verifica, narrativa opzionale a citazioni
  verificate. Con --pianifica: classifica di priorita' dei TSK e proposta di owner da script
  deterministico. Nessun numero dal modello, nessuna scrittura nel kanban. Opt-in pm_report.enabled.
version: "1.1"
owner: pm-report-coordinator
opt_in: pm_report.enabled
depends_on_tools:
  - tools/coordinamento/run.py
  - tools/coordinamento/proponi_kanban.py
  - tools/coordinamento/applica_config.py
  - tools/coordinamento/pianifica.py
pattern_version: "2.43"
---

# Coordinamento giornaliero — protocollo del report PM

Una **misura del kanban**, non un'opinione. Ogni numero viene dal frontmatter dei TSK letto a
un commit fissato, e una seconda implementazione indipendente (`verifica_l0.py`) lo ricalcola
prima dell'impaginazione. Nella pagina non c'e' testo prodotto da un modello: anche i prompt
«Chiedi una verifica» sono template riempiti con i dati della misura. Motore, config e limiti:
`tools/coordinamento/README.md`.

Foglie, da aprire solo al passo che le usa:

| Foglia | Quando |
|---|---|
| `references/coordinamento/agente-allineamento-config.md` | Passo 1, se ci sono candidati: prompt del subagente `Explore` |
| `references/coordinamento/riepilogo-e-regole.md` | Passo 2, per il riepilogo in chat e le regole di calcolo |

## Gate opt-in

Leggi `pm_report.enabled` in `factory.config.yaml`.

```
false            -> STOP: «capability pm_report spenta». Nessuno script, nessuna uscita.
blocco assente   -> STOP: «capability pm_report non configurata». Per accenderla:
                      pm_report:
                        enabled: true
                    in factory.config.yaml (modifica umana, fuori da questa skill).
```

Gli script ripetono il gate (`run.py`, `proponi_kanban.py`: `STOP`, exit 0), ma a flag spento
non si lancia nulla.

## Input

- **operatore** e **config**: `analytics/coordinamento/config-<operatore>.json` (l'operatore e' il
  nome del file). Esempio che misura questa factory: `config-esempio.json`. Config assente → STOP
  con il path atteso: si crea copiando l'esempio, mai inventando obiettivi.
- **commit** (`--ref`, default `HEAD`) e **oggi** (`--oggi`, default la data locale): gli stessi
  per `proponi_kanban.py` e per `run.py`, altrimenti store e misura non sono confrontabili.

Uscite: `deliverables/coordinamento/report-pm/<operatore>/<data>/` (gitignored).

## Claim advisory (cooperative locking, EP-053)

Prima delle scritture factory-side (store, config), **avviso, mai blocco**:

```bash
python3 tools/session/active_sessions.py conflicts --domain analytics/coordinamento
python3 tools/session/active_sessions.py claim --agent pm-report-coordinator \
  --domain analytics/coordinamento --ttl 30 --context "report PM <operatore>"
```

Un conflitto si dice all'operatore e si prosegue: la config e lo store sono per operatore. A fine
passo: `python3 tools/session/active_sessions.py release --domain analytics/coordinamento`.

---

## Passo 1 — Allineamento della configurazione

```bash
python3 tools/coordinamento/run.py --config analytics/coordinamento/config-<operatore>.json \
  --ref <commit> --solo-controllo
```

Ultima riga: `CONTROLLO {json}` con `candidati`, `per_tipo` e i path di `allineamento_<sha8>.json`
e `snapshot_<sha8>.json`. `controlla_config.py` segnala, senza giudicare: US del perimetro che la
config non cita (solo per gli obiettivi che classificano le US: con sezioni o liste `us_*`), US
citate ma assenti o chiuse, sezioni non attribuite, rilascio e calendario incoerenti con la
`window`, owner e status non mappati, epiche aperte fuori da ogni perimetro.

**0 candidati** → Passo 2.

**Candidati > 0** → un solo subagente `Explore` (nessuno strumento di scrittura), in primo piano,
con il prompt della foglia `agente-allineamento-config.md`. Poi, nella sessione principale:

1. salva il JSON in `<uscite>/proposte_<sha8>.json` e valida:
   `python3 tools/coordinamento/applica_config.py --config <config> --snapshot <snapshot> --proposte <proposte> --valida`;
2. mostra le proposte numerate: `n. azione — ID (sintesi) — motivazione — confidenza`;
3. chiedi con `AskUserQuestion`: *Applica tutte* · *Solo quelle ad alta confidenza* ·
   *Scelgo io (numeri)* · *Non applicare e fai il report cosi'*;
4. applica con `--scelte` (copia della config in `analytics/coordinamento/storico/<operatore>/`),
   poi `python3 -m pytest tools/coordinamento/tests -q` e di nuovo `--solo-controllo`.

Il subagente propone, l'operatore decide, lo script scrive. E' l'unico punto in cui un modello
produce qualcosa (proposte, mai numeri). Una mappatura confermata cambia la classificazione dei
report successivi, non i numeri del report in corso.

## Passo 1b — Store dei TSK senza owner e proposte config→kanban

**A ogni report**, prima di `run.py`, con lo stesso commit e la stessa data:

```bash
python3 tools/coordinamento/proponi_kanban.py --config <config> \
  --ref <commit> --oggi <AAAA-MM-GG> --aggiorna-store \
  --out deliverables/coordinamento/report-pm/<operatore>/<data>/proposte-kanban_<sha8>.json
```

- `analytics/coordinamento/<operatore>/da_assegnare.yaml` — forma `{da_assegnare: [...]}`: TSK
  aperti senza owner con `prima_vista`. E' la fonte dell'eta' (soglie
  `pm_report.da_assegnare.stale_alert_days`/`escalation_days`, default 7/14 giorni lavorativi):
  senza store gli avvisi di permanenza non scattano mai. Committabile; single-writer = la
  sessione dell'operatore. **Visibilita'**, mai coda di apply.
- il JSON di `--out`: `proposte` (`window_mancante`, `window_non_allineata`, `owner_suggerito`
  da `epic_owner_default` approvato e non scaduto), `da_assegnare`, `esclusi`.

Con `--proposte-kanban` mostra le proposte e di' che sono **per il `tpm`, su gate del PO**; senza
il flag lo store si aggiorna comunque e le proposte non si presentano.

**Regole inviolabili**:
- mai `owner:` nel kanban, ne' altro campo: le proposte le applica il `tpm` dopo il gate del PO;
- lo script esclude TSK e US in corso, in `review` o `approved`; non legge `assignee:` (lo skip
  dei TSK con `assignee:` valorizzato e' dell'apply del `tpm`).

---

## Passo 2 — Report

```bash
python3 tools/coordinamento/run.py --config <config> --ref <commit> --oggi <AAAA-MM-GG> \
  [--fonte commit|worktree] [--narrativa <file>]
```

Pipeline: `snapshot` → `controlla_config` → `aggrega` → `verifica_l0` → `file_grandi` →
(`verifica_citazioni`) → `vista_pm` → `verifica_vista` → `html_check`. `run.py` passa lo store ad
`aggrega` e `verifica_l0` se esiste.

- `--fonte worktree` legge il disco: **non riproducibile**, solo su richiesta esplicita (banner
  nella pagina).
- **`verifica_l0` fallita → nessuna vista, exit 1.** Riporta il passo e il messaggio; non
  costruire un report a mano.
- Perimetro senza TSK → `snapshot.py` si ferma (exit 2): `factory_root` o `kanban_root` sbagliati.

Uscite: `snapshot_<sha8>.json`, `allineamento_<sha8>.json`, `misura_<sha8>.json` (stessi byte a
parita' di commit, config, store e `--oggi`), `vista-pm_<sha8>_<HHMM>.html`. Ultima riga:
`RIEPILOGO {json}` — cosa dirne in chat e regole di calcolo nella foglia `riepilogo-e-regole.md`.

## Passo 3 — Lettura assistita (opt-in, solo su richiesta)

Nel flusso principale (nessun subagente) scrivi 5-10 frasi in
`<uscite>/narrativa_<sha8>.md`: **una per riga**, ognuna con almeno una citazione `[F:percorso]`
di un campo della misura (es. `[F:obiettivi[id=<obiettivo>].conteggi]`, `[F:obiettivi[0].avvisi[0]]`).
Numeri, ID e date della frase devono comparire nei campi citati; nessun giudizio che i campi non
contengano. Poi `run.py ... --narrativa <file>`: `verifica_citazioni.py` controlla ogni frase; se
fallisce, correggi o togli le frasi indicate. Non forzare.

---

## Passo 4 — Pianificazione (opt-in, `--pianifica`)

Risponde a «cosa va fatto prima» e «chi lo prende». Classifica e proposte vengono da uno script
deterministico; il modello le presenta, non le ricalcola.

```bash
python3 tools/coordinamento/pianifica.py --config <config> --ref <commit, lo stesso del report> \
  --oggi <AAAA-MM-GG> --out <uscite>/pianificazione_<sha8>.json
```

Richiede il blocco `pianificazione` nella config (schema in `analytics/coordinamento/config-schema.json`,
criteri nel README del motore). Senza, lo script esce con codice 2: proponi il blocco all'operatore
e applicalo solo dopo conferma, con `applica_config.py`. In chat, dal JSON: prime voci della
classifica (punteggio, scadenza, owner; i non pronti con il motivo), proposte di owner con la loro
motivazione, non assegnabili, capacita' per persona e avvisi `sovraccarico`.

**Applicazione, mai dentro questo passo**: conferma dell'operatore con `AskUserQuestion`; le proposte
confermate vanno al `tpm`, che prima verifica owner e status del TSK al commit corrente contro
`provenienza.ref_sha`. `assignee:` non si tocca.

## Regole fisse

| Regola | Testo |
|---|---|
| Nessun numero dal modello | Tutti i valori dagli script; il modello non calcola, stima ne' interpola |
| Fonte degli stati: frontmatter | `status:` dei file TSK/US/EP; `sprint.md` diverge e non conta. Appartenenza dai campi `story:`/`us:` e `epic:`/`ep:`, solo in mancanza dal path |
| Lettura dal commit | Default `HEAD`; stesso commit + config + store + `--oggi` = stessi byte |
| Gate L0 | L0 fallita = nessuna vista |
| File grandi: lettura mirata | Elenco misurato a ogni report in `file_grandi.json`: Grep o Read con offset/limit |
| Nessuna scrittura nel kanban | Proposte al `tpm` su gate del PO; mai su lavoro in corso o in revisione |
| Config solo via `applica_config.py` | Dopo conferma, poi la suite `tools/coordinamento/tests` |
| Pianificazione: proposte, mai assegnazioni | Classifica e owner proposti vengono solo da `pianifica.py`, senza ricalcoli o integrazioni a mano; l'applicazione passa da conferma e `tpm` |
| Mai `wiki/` | §7 r.12: il report non scrive in `wiki/`, neppure `wiki/log.md` |

## Degradazione

| Condizione | Comportamento |
|---|---|
| `pm_report.enabled` false o assente | STOP (gate) |
| Config dell'operatore assente | STOP con il path atteso |
| Script con exit diverso da 0 | STOP: passo e messaggio; nessun report alternativo |
| Store assente | Report prodotto; avvisi di permanenza assenti, dichiarato nella `NOTA store` |
| PyYAML assente | `proponi_kanban.py` esce 1 con l'istruzione di installazione; `snapshot.py` registra un errore di frontmatter per file |
