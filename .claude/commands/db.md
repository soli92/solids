---
description: "Interroga i database PostgreSQL degli ambienti del registro (capability opt-in db_access) partendo da ambiente e servizio, schema, tabella o funzionalità, con le credenziali del file env configurato. Letture validate e read-only lato server; ambienti in read_only_envs mai scritti; scrittura spenta per default (db_access.write.enabled) e, se accesa, solo dopo dry-run, token e gate umano."
argument-hint: "<env> <servizio|target> \"<SQL | domanda>\" · locate <env> <termine> · tables|describe <env> <target> · check <env> <target> · catalog-check|catalog-status <env> [<target>] · targets [<env>]"
allowed-tools: Bash, Read, Write, AskUserQuestion
---

# /db

Argomenti utente: `$ARGUMENTS`

Segui `.claude/skills/db-access-protocol.md`. Tool unico: `tools/db/db_access.py`.

## Sintassi

```
/db targets [<env>]                          # registro: endpoint e credenziali pronte o mancanti
/db locate <env> <servizio|schema|tabella>   # dove sta: mappa del registro; --live cerca nei cataloghi
python tools/db/db_map.py map-locate <termine> --env <env>   # funzionalita' -> servizio -> tabella, relazioni tra DB (feature-map)
/db databases <env>                          # database presenti sugli host dell'ambiente
/db tables <env> <target> [<parte del nome>] # tabelle e viste, righe stimate, dimensione
/db describe <env> <target> <schema.tabella> # colonne, vincoli, indici
/db <env> account-service "stato del servizio X"  # partendo dal servizio: locate, poi describe, poi query
/db check <env> <target>                     # utente DB, privilegi per schema, write_capable
/db catalog-check <env> [<target>...]        # catalogo DDL vs server: fresh | drift | missing | inaccessible | stale | unverified
/db catalog-status [<env>]                   # offline: eta' e stato dei cataloghi locali, senza connettersi
/db catalog-scan <env> [<target>...] [--full] [--dry-run]   # rigenera la DDL del catalogo (solo su richiesta; non committa)
/db <env> <target> "select ..."              # lettura (read-only lato server)
/db <env> <target> "quanti ordini in bozza per il cliente X?"   # domanda: l'SQL lo scrivi tu
/db <env> <target> "update ... where ..."    # scrittura (solo con db_access.write.enabled: true): dry-run → gate → commit
```

`<env>`: gli ambienti del registro (esempio: `test` · `staging` · `prod`). Quelli in `read_only_envs` (default
`prod`) sono **in sola lettura**: nessuna scrittura, nemmeno in dry-run; risultati mai su file.
`<target>`: i database logici del registro (elenco aggiornato: `/db targets`). Al posto del target si può dare il
servizio: `/db locate`.

## Comportamento

1. **Boot** (Fase 1): target e credenziali da `targets`, primo `check` della sessione sul target.
   **Catalog gate**: `catalog-check <env> <target>`; se `catalog_warning` non e' vuoto, e' la **prima riga**
   della risposta (per esempio «catalogo test/app: drift su public (serve catalog-scan)»). Non blocca mai la lettura.
2. **Navigazione**: microservizio, schema o funzionalità → `locate` (e la wiki per la funzionalità);
   poi la DDL del catalogo (`<db_access.catalog.dir>/<env>/<db>/<schema>.sql`) e, per conferma o con catalogo
   non fresco, `tables` e `describe` per tabelle e colonne reali. Mai inventare nomi di colonna. Mostra
   l'SQL che esegui.
3. **Lettura**: `query` (solo SELECT/WITH/TABLE/VALUES, LIMIT dentro la query, `--explain` per il piano).
   Exit 3 = scrittura: con `write.enabled: true` e fuori da `read_only_envs` passa alla Fase 4, altrimenti file
   `.sql` per chi ha titolo. Exit 4 `cost_gate` (ambienti in `cost_gate.envs`, stima sopra soglia): mostra costo e righe stimate e chiedi conferma; `--accept-cost` solo dopo il sì
   esplicito dell'utente, altrimenti restringi la query.
4. **Scrittura** (spenta per default: `write` rifiuta con `write_disabled`; mai su `read_only_envs`): `write --dry-run`,
   poi gate umano `AskUserQuestion` con l'SQL completo e le righe toccate, poi `write --commit --token` solo dopo
   il sì esplicito. Il token da solo non basta.
5. **Privilegi insufficienti** (`42501`) o scrittura spenta: file `.sql` per chi ha titolo in `deliverables/`, nessun tentativo con altre utenze.
6. **Catalogo**: `catalog-scan` si esegue solo su richiesta dell'utente e `/db` non committa mai
   la directory del catalogo. `needs_sync` / `needs_commit` del check si riportano all'utente.

## Prerequisiti

- `factory.config.yaml → db_access.enabled: true`
- Python con `pyyaml` e un driver PostgreSQL: `psycopg` 3 oppure `psycopg2`
- Rete raggiungibile (VPN se il proprio ambiente la richiede) e certificato TLS valido (`sslmode` default `verify-full`)
- Registro `tools/db/db-targets.yaml` (copia di `tools/db/db-targets.example.yaml`) e file credenziali
  `db_access.env_file` (default `.env.db`, gitignored) con le variabili citate dal registro

Per indagini lunghe in più passi in sola lettura, delega all'agente `db-operator`. Il gate, il token
e il commit restano sempre nella sessione principale.
