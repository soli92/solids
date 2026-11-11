# tools/coordinamento — report PM deterministico dal kanban

Misura l'avanzamento di uno o piu' obiettivi leggendo il **frontmatter del kanban a un commit
fissato**, ricalcola ogni numero con una **seconda implementazione indipendente** (L0) prima di
mostrarlo, e impagina una vista HTML autosufficiente con avvisi a regole, TSK senza owner con
la loro eta' e un prompt «Chiedi una verifica» per ogni voce dubbia. Capability opt-in
(`pm_report.enabled`), EP-070. Protocollo agentico: skill `coordinamento-giornaliero`, comando
`/coordinamento`, agente `pm-report-coordinator`.

## Cosa non fa

- **Non scrive mai nel kanban.** Legge `management/kanban/` da git; le proposte config→kanban
  (`proponi_kanban.py`) sono un JSON per il `tpm`, che le applica solo dopo il gate del PO.
- **Non e' un arbitro.** Non assegna, non blocca, non risolve la contesa fra operatori: la config
  e lo store sono per operatore, e i claim sono advisory (cooperative locking, EP-053).
- **Non produce numeri propri.** I numeri vengono solo dagli script; un modello puo' proporre
  correzioni alla config (passo 1) o scrivere una narrativa le cui frasi `verifica_citazioni.py`
  controlla campo per campo. Niente stime, niente previsioni, niente giudizi di rischio.
- **Uno zero non e' un'assenza.** Un perimetro senza TSK ferma `snapshot.py` (exit 2).

## Pipeline

```
proponi_kanban.py --ref C --oggi D --aggiorna-store     store dei TSK senza owner (prima_vista)
pianifica.py --ref C --oggi D                           (opt-in) classifica di priorita' e proposte di owner
run.py --ref C --oggi D:
  snapshot.py          una riga per EP/US/TSK, con provenienza (sha256, git)        -> snapshot_<sha8>.json
  controlla_config.py  cio' che la config non conosce o ha superato (misura, exit 0) -> allineamento_<sha8>.json
  aggrega.py           misura per obiettivo: epiche, sezioni, persone, avvisi        -> misura_<sha8>.json
  verifica_l0.py       ricalcolo indipendente; scostamento = exit 1, nessuna vista
  file_grandi.py       file di testo oltre soglia, citati nei prompt
  verifica_citazioni.py  (con --narrativa) ogni frase cita i campi da cui viene
  vista_pm.py          pagina a tre schede (Vista PM, Piano operativo, Qualita' dato) -> vista-pm_<sha8>_<HHMM>.html
  verifica_vista.py    ogni elemento della misura e' visibile nella pagina
  html_check.py        niente caratteri di controllo, HTML dei prompt escapato
applica_config.py      applica alla config le proposte confermate, con copia in storico/
```

Stesso commit + stessa config + stesso store + stesso `--oggi` = stessi byte nella misura.

## Uso

```bash
python3 tools/coordinamento/proponi_kanban.py --config analytics/coordinamento/config-<operatore>.json \
  --ref HEAD --oggi 2026-10-05 --aggiorna-store --out <uscite>/proposte-kanban.json
python3 tools/coordinamento/run.py --config analytics/coordinamento/config-<operatore>.json \
  --ref HEAD --oggi 2026-10-05 [--uscite <cartella>] [--fonte worktree] [--narrativa <file>]
python3 tools/coordinamento/run.py --config ... --solo-controllo
python3 tools/coordinamento/pianifica.py --config analytics/coordinamento/config-<operatore>.json \
  --ref HEAD --oggi 2026-10-05 [--out <file>.json]
python3 -m pytest tools/coordinamento/tests -q
```

Uscite di default in `deliverables/coordinamento/report-pm/<operatore>/<data>/` (gitignored).
Ultima riga di `run.py`: `RIEPILOGO {json}` (o `CONTROLLO {json}`).

**Gate**: `run.py` e `proponi_kanban.py` leggono `pm_report.enabled` da `factory.config.yaml`
della `factory_root`. `false` → `STOP`, exit 0, nessuna uscita. File o chiave assenti → non
governato, si procede (e' il caso dei kanban sintetici dei test). Soglie d'eta' dei TSK senza
owner: `pm_report.da_assegnare.stale_alert_days` / `escalation_days` (default 7 / 14 giorni
lavorativi).

## Pianificazione (opt-in)

`pianifica.py` classifica i TSK da fare o bloccati del perimetro con
`(punti priorita' + punti urgenza + punti sblocco) / giorni` e propone un owner ai TSK pronti e
senza owner persona, per competenze dichiarate, capacita' residua nell'orizzonte e affinita'
storica. Solo stdlib e PyYAML. Legge il kanban dal commit `--ref`; `--oggi` e' obbligatorio; stesso
commit + config + `--oggi` = stessi byte. **Non scrive mai nel kanban**: le proposte hanno la forma
di quelle di `proponi_kanban.py` e le applica il `tpm` dopo conferma. Esce con 2 se la config non ha
il blocco `pianificazione` (o e' incompleto): nessun default implicito sui pesi. Taglie in giorni
da `pianificazione.dimensioni_giorni`; criteri e regole di calcolo nella docstring e nella
`legenda` dell'output. Esempio di blocco (valori inventati):

```json
"pianificazione": {
  "persone_assegnabili": ["a", "b"], "orizzonte_giorni_lavorativi": 10,
  "dimensioni_giorni": {"S": 1, "M": 2, "L": 4}, "dimensione_predefinita": "M",
  "punti_priorita": {"P0": 8, "P1": 5, "P2": 3, "P3": 1},
  "fasce_urgenza": [{"entro_giorni": 3, "punti": 4}, {"entro_giorni": 10, "punti": 2}],
  "punti_sblocco_per_tsk": 1
}
```

Campi opzionali del `team`: `competenze.layer`, `assenze[{dal, al}]`, `impegno_pct`.

**Velocity misurata (opzionale).** Con `pianificazione.velocity_config` (path, dalla radice della
factory, di una config di `/velocity`, es. `analytics/velocity/config.example.json`) la tabella
taglia -> giorni viene dalla chiave `giorni` di quella config se il blocco non dichiara
`dimensioni_giorni`, e per ogni persona l'output riporta punti e TSK chiusi a settimana
(`tools/analytics/team-velocity.py`), il carico nell'orizzonte in punti e le settimane al ritmo
misurato. E' un dato di confronto: le proposte restano sulla capacita' nominale. Le persone si
associano per `id` del `team` di `/velocity` o, in mancanza, per nome. `velocity_misurata: false`
tiene solo la tabella. **Determinismo**: la velocity legge il kanban del working tree e la storia
git corrente, non `--ref`; per questo `provenienza` riporta `velocity_config`,
`velocity_config_sha256` e `velocity_misurata`. Stesso commit + config + `--oggi` + stessa storia
git = stessi byte. Senza `velocity_config` nulla cambia: output identico.

## Config

Una per operatore: `analytics/coordinamento/config-<operatore>.json` (l'operatore e' il nome del
file). Senza `--operatore`, il comando cerca `git config user.name` fra nomi e alias del `team`:
se il tuo nome git (es. un handle come `soli92`) non coincide col nome nel team, aggiungilo come
alias, altrimenti il comando chiede. Schema: `analytics/coordinamento/config-schema.json`. Esempio che misura il kanban di
questa factory: `analytics/coordinamento/config-esempio.json`.

Tutto il dominio sta nella config: obiettivi e perimetro (epiche per ID), tabella `stati`, `team`
e alias, `owner_non_persona`, `owner_agente`, progetti e loro `tono` (colore della palette
neutra; `vista_pm.palette` ne aggiunge), strumenti citati nei prompt (`prompt_verifica`), file
grandi (`file_grandi`). **Sezioni, ondate e window sono opzionali**: un obiettivo senza sezioni si
misura per epica, e il controllo non chiede di classificarne le US (`classifica_us` per forzarlo).

**Perimetro per US** (opzionale): `perimetro[].selettore.us` elenca le US del perimetro dentro le
`epiche` del selettore. Se c'e', di quelle epiche contano solo i TSK delle US elencate: conteggi
dell'obiettivo e del progetto, blocchi per epica, persone, TSK aperti, lavoro non legato a una sezione,
copertura, classifica di `pianifica.py` e store di `proponi_kanban.py`; `controlla_config.py` non chiede
di classificare le US fuori dal selettore e segnala le sezioni con US fuori. Senza il campo conta l'epica
intera, come prima (stessi byte nella misura). Serve quando un obiettivo e' una parte di un'epica piu'
grande (es. le US di collaudo dentro l'epica di una migrazione, con una config dedicata). La data di inizio
dell'obiettivo resta quella di creazione delle epiche, salvo `data_inizio`. L0 ricalcola con lo stesso
filtro, riscritto in `verifica_l0.py`, e confronta le US del selettore con la config.

**Sottoperimetri e ambiente di rilascio** (opzionali):
- `sezioni[].sottoperimetro` ∈ `sviluppo`, `configurazione` (TSK di rilascio, ambiente, utenze,
  allineamento), `test`. La misura lo copia in ogni sezione (null se assente) e calcola per
  obiettivo `per_sottoperimetro`: i conteggi dei TSK delle sezioni di quel sottoperimetro, con la
  regola dell'avanzamento; un TSK in piu' sezioni dello stesso sottoperimetro conta una volta, in
  sottoperimetri diversi una volta in ciascuno; le sezioni senza campo stanno sotto `non_indicato`.
  Assente se nessuna sezione dell'obiettivo indica il campo. Nel JSON le chiavi sono in ordine
  alfabetico (`sort_keys`): l'ordine sviluppo, configurazione, test lo applica la vista.
- `obiettivi[].ambiente_rilascio` (es. `preprod`, default `test`): copiato nella misura; la vista
  scrive «rilascio in <ambiente>» al posto del testo fisso.

Nella vista le sezioni `configurazione` portano l'etichetta **«Infra · rilascio»** (testo e classe
`sp-configurazione`, non solo colore) ovunque compaiono: albero e rete del dettaglio, gruppi del
Piano operativo, righe dei TSK aperti e dei bloccanti che vi appartengono, sezioni in «Persone e
carico», tabella dei conteggi. `sviluppo` e `test` hanno l'etichetta «Sviluppo» / «Test», sobria.
Il riepilogo dell'obiettivo mostra l'avanzamento per sottoperimetro (fatti/base, %). L0 ricalcola
`per_sottoperimetro` (anche senza config) e, con la config, confronta sottoperimetri e ambiente;
`verifica_vista.py` cerca etichette e avanzamento per sottoperimetro nella pagina.

**Milestone dei sotto-obiettivi** (opzionali): `perimetro[].sotto_obiettivi.milestone` è una lista di
`{data: AAAA-MM-GG, etichetta, descrizione}`. Nel Gantt ad albero la riga del sotto-obiettivo porta un
marcatore per ogni milestone («etichetta gg/mm», descrizione al passaggio del mouse) e la sua barra va
dalla prima data delle sue sezioni all'ultima milestone o scadenza, invece della finestra
dell'obiettivo. Le voci senza una data valida sono ignorate. Sono date di piano copiate dalla config:
non entrano nella misura e non cambiano i conteggi.

Store dei TSK senza owner: `analytics/coordinamento/<operatore>/da_assegnare.yaml`, forma
`{da_assegnare: [...]}` (letta anche la lista nuda delle versioni precedenti), committabile,
single-writer = la sessione dell'operatore. Storico della config: `analytics/coordinamento/storico/<operatore>/`.

## Forme del kanban

Il motore legge entrambe le forme della flotta (`kanban_ids.py`):

| | ID | Cartelle |
|---|---|---|
| derivate | con prefisso di namespace (`XX-TSK-541`) | senza slug (`XX-EP-020/XX-US-172/`) |
| questa factory | senza prefisso (`TSK-635`) | con slug (`EP-064-kanban-multi-user-coordination/US-251-…/`) |

Il prefisso e' opzionale (`(?:[A-Z]{2,4}-)?`, come `tools/vcs/ai_policy.py`). L'appartenenza
TSK → US → EP viene dal frontmatter (`story:`/`us:`/`story_id:`/`parent:`, `epic:`/`ep:`/`epic_id:`);
solo in mancanza dal path, riconoscendo la cartella dall'ID con cui comincia. Un TSK senza `epic:`
eredita l'epica della sua US. Frontmatter e path discordanti: vale il frontmatter, e la
discordanza e' un'anomalia di qualita' del dato. `verifica_l0.py` ha la propria espressione per
gli ID e non importa nulla del motore (test statico).

Le stringhe di calendario (giorni, mesi, regex «mer 06/10») stanno solo in `calendario.py`.

**Roll-up delle US** (`us-non-aggiornata`): contano i TSK della US per frontmatter/path **piu'**
quelli che la US dichiara in `tsk_ids` o `tsk_range` — ID singoli, elenchi, intervalli completi o
abbreviati (`XX-TSK-561..563`) — anche se stanno in un'altra cartella. Un `tsk_range` illeggibile
(testo libero, intervallo rovesciato o oltre 500) non aggiunge nulla. Nella derivata da cui viene il
motore era un limite noto: la US che elencava TSK di altre US risultava incoerente a torto.

## Test

`python3 -m pytest tools/coordinamento/tests -q`: kanban sintetici in repo git temporanei, nelle
due forme. La misura della forma senza prefisso con slug e' verificata **identica** a quella della
forma con prefisso, a meno del prefisso. Casi: regole di calcolo, anti-allucinazione, prerequisiti,
riproducibilita' al byte, ~20 manomissioni che L0 deve bloccare, un bug iniettato in `aggrega.py`
che L0 deve rilevare, controllo e applicazione della config, vista e prompt, obiettivo senza
sezioni, store nelle due forme, gate, assenza di costanti di dominio della derivata nel motore,
avanzamento per sottoperimetro (TSK condivisi fra sezioni) e ambiente di rilascio.

## Provenienza

Porting generalizzato del report PM di portale-servizi-factory: epica **FAC-EP-064**, decisioni
**ADR-089** (capability, agente owner leggero, config per operatore) e **ADR-090** (governance
degli owner: single-writer = `tpm` su gate del PO, store per operatore), Tavola Rotonda
**f3a8e2b9** del 2026-10-05; sorgente al commit 09c48a9 (main 15dd843f + correzioni 795cc598).
Gli ADR e la Tavola Rotonda restano nella derivata: qui sono citati, non importati.

Cambiamenti rispetto alla sorgente, oltre alle generalizzazioni sopra:
- i claim passano da preflight bloccante ad **advisory** (`tools/session/active_sessions.py`);
- lo store era scritto come lista e letto come mappa da `aggrega.py`/`verifica_l0.py`: con lo
  store presente L0 sarebbe fallita. Ora si scrive `{da_assegnare: [...]}` e si leggono entrambe;
- `proponi_kanban.py` legge il perimetro con un solo `git cat-file --batch` e considera «in
  lavorazione» anche la categoria `in_corso` della config, oltre ai valori grezzi;
- nessuna baseline sha256 dei file: proteggeva le copie esatte, qui i file non lo sono.

Smoke del 2026-10-05 con la config della derivata, in sola lettura: misura identica a quella del
motore sorgente (unica differenza: lo sha256 dello snapshot, che ha un campo in piu'), L0 PASS.

## Cosa non e' stato portato

- **`verifica_parita.py` e le fixture `misura-skill.json`**: confrontavano il motore con la skill
  locale da cui la derivata era partita, su commit e postazioni della derivata. Fuori scope: qui
  non c'e' una skill da cui migrare, e la parita' fra le due forme del kanban e' coperta dai test.
- **`config-musio.json`, `config-olivieri.json`**: dati di operatori della derivata.
- **Runbook, sezione PATTERN, lint check**: §23.8, nessuna cerimonia prima dell'esercizio.
- **Asset `vendor/`** della skill locale: gia' non usati dalla vista nella sorgente.
