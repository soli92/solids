---
description: "Legge i log applicativi su OpenSearch (ambienti e app del registro, capability opt-in log_access) in sola lettura, con dati personali mascherati di default (opzionale con `--no-mask`). Per analizzare un ticket, un errore su una feature o lo stato di un ambiente."
argument-hint: "<env> <app> <domanda | filtri> · check <env> <app> · targets [<env>] · namespaces <env> [<app>] · noise <env> <app>"
allowed-tools: Bash, Read, AskUserQuestion
---

# /log

Argomenti utente: `$ARGUMENTS`

Segui `.claude/skills/log-access-protocol.md`. Tool unico: `tools/logs/log_access.py`.
A `log_access.enabled: false` (default) il comando risponde con un fallback esplicito e si ferma.

## Sintassi

```
/log targets [<env>]                          # registro: cluster, index, namespace, credenziali pronte o mancanti
/log check <env> <app>                        # login, ultimo evento, righe nell'ultima ora
/log namespaces <env> [<app>]                 # namespace realmente presenti nell'index, con conteggio
/log <env> <app> "errori del servizio X dalle 9:00 alle 9:30 di oggi"   # domanda: i filtri li scrivi tu
/log <env> <app> count --since 1d --by <campo livello>
/log <env> <app> search --around 2026-11-05T09:14 --level ERROR --size 30
/log noise <env> <app> --since 1h             # valuta il rumore e propone regole numerate (c1, c2, ...)
/log noise-add <env> <app> --container X ...  # anteprima dell'impatto; con conferma scrive la regola nel profilo
/log handled-add <env> <app> --container X --message "..."  # registra un errore ATTESO (nascosto dall'elenco, riassunto in una riga)
/log search <env> <app> ... --show-handled    # include gli errori gestiti nell'elenco, etichettati
/log search <env> <app> ... --out /tmp/x.txt  # output su file (vietato in raw/, wiki/ per gli ambienti protetti)
```

Il comando traduce in `log_access.py <sottocomando> <env> <app> [filtri]` (`search`, `count`, `noise`,
`fields`, `check`, `namespaces`, `targets`, `guide`); `/log guide` stampa le regole d'uso.

`<env>` e `<app>`: quelli di `/log targets`. Gli ambienti in `log_access.protected_envs` (default `prod`) sono protetti:
mascheramento consigliato, righe mai copiate in `raw/`, `wiki/`, `deliverables/`, kanban o commit (`--out` verso le
cartelle di conoscenza è rifiutato dal codice).

## Comportamento

1. **Boot** (Fase 1): target e credenziali da `targets`, primo `check` della sessione.
2. **Domanda in linguaggio naturale**: traducila in filtri e mostra il comando che esegui. Dal largo
   allo stretto: `count`, poi `search` stretta, poi il trace. Mai inventare container o campi (R.2):
   `fields` e `count --by <campo container>` dicono cosa c'è.
3. **Ticket**: ricetta della Fase 4 del protocollo; ogni affermazione cita ambiente/app, finestra,
   filtri e numero di righe.
4. **Mascheramento**: attivo di default e consigliato, soprattutto sugli ambienti protetti. `--no-mask` solo se lo chiede
   l'utente per quell'indagine; i segreti restano mascherati.
5. **Rumore**: `noise` propone i candidati; per ciascuno scelto dall'utente (`AskUserQuestion`) `noise-add` mostra
   l'impatto, poi la conferma esplicita e solo allora `--confirm <token>` scrive la regola nel profilo.
6. **Errori gestiti**: attesi, mai nell'elenco di default (una riga di riepilogo nell'intestazione). Si registrano
   solo su indicazione dell'utente, con anteprima e conferma. Un volume anomalo va comunque segnalato.
7. **Ambiente non registrato**: non si interroga; si propone la voce da aggiungere al registro.

## Prerequisiti

- `factory.config.yaml → log_access.enabled: true`
- `tools/logs/log-targets.yaml`: copia di `tools/logs/log-targets.example.yaml` con cluster, index, namespace reali
  (la mappa dei campi è per target, default documentati nell'esempio)
- Python 3.9+ con `requests` e `pyyaml` (`python3 -c "import requests, yaml"`) e, per fusi diversi da UTC su Windows, `tzdata`
- Rete/VPN verso il cluster
- Credenziali: nel file `env_file` del target (gitignored), nei nomi di variabile dichiarati dal cluster nel registro
- Certificato del cluster, se dichiarato (`cert_file`), nel percorso indicato dal registro (non versionato)

Per indagini lunghe in più passi, delega all'agente `log-operator`.
