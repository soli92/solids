# Onboarding di un repo di test — convenzioni AS-IS (Fase 0-bis)

Riferimento della skill `cypress-generation-protocol`. Si usa per i repo con
`conventions_status: da_ricavare`. Sola lettura sul repo di test; output in
`code_quality/cypress/<TSK-id>/convenzioni-as-is.md`. «AS-IS» = come il repo è oggi, non come
dovrebbe essere. Ogni riga cita `file:riga`; ciò che non si trova si scrive «non presente», mai
dedotto.

## Metodo

1. `python3 tools/cypress/resolve_repo.py <name>`: path, layout, commit del repo.
2. Elenco della struttura (cartelle di primo e secondo livello, conteggio degli spec per cartella).
3. Lettura di config, support e di un campione di spec per area (almeno uno per cartella con spec
   attivi; dichiarare quali).
4. Compilare le sei sezioni sotto.

## Sezioni

| Sezione | Cosa riportare |
|---|---|
| Login | come ci si autentica (comando di supporto, sessione, cookie, login interattivo o programmatico); se lo spec deve o non deve chiamarlo |
| Config | file di config, `baseUrl`, `specPattern`, timeout, reporter, env; file CSV o liste che filtrano gli spec; ambienti raggiunti |
| Utenze | **solo i nomi** delle chiavi o variabili da cui si leggono le utenze, ruoli coperti; mai valori. Credenziali in chiaro trovate nei file: gap, senza ricopiarle |
| Selettori | strategia (`#id`, `data-*`, testo, struttura), comandi di supporto che li incapsulano, selettori fragili ricorrenti |
| Struttura degli spec | albero delle cartelle, convenzione dei nomi, cartelle in dismissione o escluse, dimensione tipica, uso di `describe/it`, hook, fixture |
| Gotcha | comportamenti che rompono i test (componenti con id particolari, attese, popup, ambienti), con il caso in cui si sono visti |

## Chiusura

- Elenco delle righe «non presente» e dei punti non verificabili senza esecuzione.
- Gap proposti al wiki-keeper (credenziali in chiaro, selettori fragili, cartelle morte).
- Testo proposto per la pagina wiki delle convenzioni, che scrive il wiki-keeper; poi
  `conventions_ref` nel registro e `conventions_status: presenti` (modifica a `factory.config.yaml`
  decisa dall'operatore, con la procedura di revisione della factory per le modifiche di config).
