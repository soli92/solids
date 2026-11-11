# Subagente: allineamento della configurazione al kanban

> Foglia di [`coordinamento-giornaliero`](../../coordinamento-giornaliero.md), Passo 1.

Si lancia **solo** se `run.py --solo-controllo` ha trovato candidati (`CONTROLLO {json}` con
`candidati > 0`). Tipo `Explore`, che non ha strumenti di scrittura: la sola lettura e' garantita
per costruzione. In primo piano, uno solo. Restituisce JSON e non scrive file: il JSON lo salva
la sessione principale.

## Prompt da passare (sostituisci i segnaposto)

```
Sei il revisore dell'allineamento fra la configurazione del report PM e il kanban della factory <FACTORY_ROOT>, al commit <SHA>.
SOLA LETTURA: non modificare nulla. Per leggere un file del kanban usa `git -C <FACTORY_ROOT> show <SHA>:<path>`,
oppure Read se `git status` dice che il file non e' modificato.
Non lanciare /session-start, pull, fetch o sync dei submodule. Per gli stati usa il frontmatter dei file, non sprint.md,
che diverge. L'appartenenza di un TSK sta nei campi story/us ed epic/ep del frontmatter; il path conta solo se mancano.
Le cartelle del kanban possono avere uno slug dopo l'ID (EP-064-kanban-multi-user-coordination): l'ID e' l'inizio del nome.
File grandi: l'elenco aggiornato e' in <PATH file_grandi.json>. Non leggerli per intero: Grep o Read con offset/limit.
Bastano il frontmatter e l'intestazione delle US e delle epiche candidate.

Input:
- candidati: <PATH allineamento_<sha8>.json>, campo `candidati`;
- configurazione attuale: <PATH analytics/coordinamento/config-<operatore>.json>. Leggi `obiettivi[].sezioni`
  (id, nome, us, tsk, sottoperimetro, stato, ondata), `obiettivi[].perimetro[]` (progetto_id, selettore.epiche, sotto_obiettivi.sezioni),
  `us_ricetta`, `us_fuori_sezione`, `stati`, `team`, `owner_non_persona`, `epiche_escluse`.

Per OGNI candidato proponi UNA azione, scelta solo fra queste:
- us_non_mappata  → aggiungi_a_sezione {us, sezione}: la US lavora su una sezione gia' in config;
                    nuova_sezione {us, sezione, nome, stato: attiva|anticipabile|congelata, ondata?, progetto_id}:
                    US di una sezione nuova; progetto_id = il progetto del perimetro la cui epica contiene la US;
                    l'ondata solo se il kanban la indica;
                    us_fuori_sezione {us}: lavoro reale ma non legato a una sezione (trasversale, infrastruttura, gate);
                    us_ricetta {us}: istruzioni per tipo di intervento, non un deliverable;
                    ignora {}: non pertinente all'obiettivo (spiega perche').
- us_config_assente → rimuovi_us {us}, oppure sostituisci_us {vecchia, nuova} se trovi la US che la sostituisce (con fonte).
- us_config_chiusa  → sostituisci_us {vecchia, nuova} se esiste la US sostitutiva; altrimenti rimuovi_us {us}.
- sezione_non_attribuita → attribuisci_sezione {sezione, progetto_id}: il progetto del perimetro le cui epiche contengono
                    le US della sezione (campo `epiche_delle_us`); ignora {} se la sezione e' citata nei sotto_obiettivi
                    ma non definita (va corretta a mano: dillo).
- rilascio_non_coerente → imposta_rilascio {sezione, data: AAAA-MM-GG, tsk}: la data scritta nel titolo del TSK di rilascio
                    o nella window della US (campi `titolo_tsk` e `window_us`); ignora {} se il kanban non indica una data.
- calendario_non_coerente → imposta_calendario {sezione, avvio, pronta_entro}: le date scritte nella window della US
                    (campo `window_us`); lascia vuota la data che la window non indica; ignora {} se la window non ha date.
- owner_non_mappato → mappa_owner {valore, persona_id}: il valore indica una persona del `team` (variante del nome);
                    mappa_owner {valore, non_persona: true}: tipo di agente, ruolo, «da designare» e simili.
                    Una persona nuova non va inventata: ignora {} e dillo, la aggiunge l'operatore al `team`.
- stato_non_mappato → mappa_stato {valore, categoria}, con categoria fra le chiavi di `stati`.
- epica_candidata   → aggiungi_epica {epica, progetto_id} se il suo contenuto rientra nell'obiettivo; altrimenti escludi_epica {epica}.
- tsk_fuori_sottoperimetro → aggiungi_tsk {tsk, sezione}: il sotto-perimetro (sezione con `tsk`, campo `sottoperimetro`,
                    es. sviluppo, configurazione, test) che corrisponde al tipo di lavoro del TSK e alla sua ondata di rilascio.
                    Sviluppo = modifica del codice del prodotto; configurazione = rilascio, ambiente, utenze, allineamento
                    dei branch, config di rilascio; test = verifiche (smoke, ratchet, oracle, probe, a11y, E2E, verifica a schermo).
- tsk_config_assente → rimuovi_tsk {tsk, sezione}.
- tsk_in_piu_sottoperimetri → rimuovi_tsk {tsk, sezione} dal sotto-perimetro che non corrisponde al tipo di lavoro.

Regole:
- Basati solo su quanto e' scritto nei file (titolo, frontmatter, testo, note datate). Niente deduzioni dal codice.
- Ogni proposta ha `fonte`: path del file del kanban e campo o riga che la giustifica.
- `confidenza`: alta = il file lo dice esplicitamente; media = lo si ricava dal testo; bassa = incerto.
  Con confidenza bassa preferisci `us_fuori_sezione` o `ignora` e spiega cosa servirebbe per decidere.
- Nella motivazione cita gli ID sempre con una sintesi tra parentesi.

Rispondi SOLO con un blocco ```json:
{"proposte": [{"candidato": <indice 0-based nel file dei candidati>, "azione": "...", "parametri": {...},
  "motivazione": "...", "fonte": "...", "confidenza": "alta|media|bassa"}]}
```

## Azioni ammesse da `applica_config.py`

Fuori da questo elenco lo script rifiuta la proposta gia' in `--valida`.

| Tipo candidato | Azioni ammesse |
|---|---|
| `us_non_mappata` | `aggiungi_a_sezione`, `nuova_sezione`, `us_fuori_sezione`, `us_ricetta`, `ignora` |
| `us_config_assente` | `rimuovi_us`, `sostituisci_us` |
| `us_config_chiusa` | `sostituisci_us`, `rimuovi_us` |
| `sezione_non_attribuita` | `attribuisci_sezione`, `ignora` |
| `rilascio_non_coerente` | `imposta_rilascio`, `ignora` |
| `calendario_non_coerente` | `imposta_calendario`, `ignora` |
| `owner_non_mappato` | `mappa_owner`, `ignora` |
| `stato_non_mappato` | `mappa_stato` |
| `epica_candidata` | `aggiungi_epica`, `escludi_epica` |
| `tsk_fuori_sottoperimetro` | `aggiungi_tsk`, `ignora` |
| `tsk_config_assente` | `rimuovi_tsk` |
| `tsk_in_piu_sottoperimetri` | `rimuovi_tsk`, `ignora` |

## Esempio di proposta

```json
{"proposte": [{"candidato": 0, "azione": "escludi_epica", "parametri": {"epica": "EP-007"},
  "motivazione": "EP-007 (capability di accessibility testing): epica chiusa nei fatti, senza status nel frontmatter; non rientra nell'obiettivo.",
  "fonte": "management/kanban/EP-007-accessibility-testing-capability/EP-007.md frontmatter", "confidenza": "media"}]}
```

Campi obbligatori: `candidato` (indice 0-based), `azione`, `parametri`, `motivazione` (ID con
sintesi e campo del file), `fonte` (path e campo o riga), `confidenza` (`alta|media|bassa`).

## Dopo il subagente

Validazione, scelta dell'operatore con `AskUserQuestion`, applicazione con `--scelte`, suite e
nuovo `--solo-controllo`: Passo 1 della skill. Se l'operatore sceglie «non applicare», il report
si genera comunque e mostra il riquadro «configurazione non allineata».
