---
description: Mostra (o modifica) topologia + routing della factory (PATTERN §13).
argument-hint: [show | set <topology>]
---

# /topology — Show / switch factory topology

Argomenti utente: `$ARGUMENTS`

## Sotto-comandi

### `/topology` o `/topology show`

Stampa una tabella read-only con:

1. **Topologia dichiarata** (`factory.config.yaml.topology`)
2. **Dev-agent presenti** (file in `.cursor/rules/*-dev.mdc` esistenti)
3. **Routing attivo** (`factory.config.yaml.routing.{be,fe,db,qa,infra}`)
4. **code_path** (con `(esterno al repo)` se assoluto fuori dal cwd del repo)
5. **stack_mode** + summary di `stack:` (campi non vuoti)
6. **Coerenza**: tre check
   - Tutti i `routing.X: agent` hanno il file `<X>-dev.mdc`? (R1)
   - Tutti i `<X>-dev.mdc` presenti hanno `routing.X: agent`? (R2)
   - `topology:` è coerente con i file presenti? (R3)
   - Se uno fallisce, segnala in rosso e suggerisci fix.

### `/topology set <topology>`

Topologie valide: `knowledge-only | plan-only | full-stack-agents | hybrid-be-agents | hybrid-fe-agents | custom`

Procedura:

1. **Show** la topologia corrente (output del sotto-comando `show`).
2. **Diff proposto**:
   - Quali dev-agent file vanno **creati** (presenti nella nuova, assenti ora)
   - Quali vanno **rimossi** (assenti nella nuova, presenti ora)
   - Routing risultante (`routing:`) per la nuova topologia
3. **STOP per conferma umana** — mostra il diff in chat, attendi OK.
4. Su OK:
   - Crea i file agente mancanti (copia da template; per il template usa i
     file `<X>-dev.mdc` già presenti come baseline, oppure scaffolda minimal).
   - Rimuove (sposta in `.cursor/rules/.archive/`) i file da rimuovere.
     **MAI delete**: rimuovere = archivio, l'umano cancella se vuole.
   - Edita `factory.config.yaml`: `topology:` e `routing:` aggiornati.
   - Append a `wiki/log.md`:
     ```markdown
     ## YYYY-MM-DD HH:MM — topology change
     **Da:** <vecchia>
     **A:** <nuova>
     **Agent file creati:** <lista>
     **Agent file archiviati:** <lista>
     ```
5. **Mai toccare** TSK esistenti per ri-route automatico. Il TPM al prossimo
   run applicherà il nuovo `routing:` ai TSK nuovi. I TSK esistenti restano
   con il loro `consumer:` fissato (umano decide caso per caso).

## Note

- **`custom`**: lascia che l'utente specifichi a la carte quali dev-agent
  attivare (lista in chat). Ammesso anche solo 1 (es. solo `qa-dev`).
- **Persistenza**: la topologia è codificata da (a) presenza file + (b)
  `factory.config.yaml`. Entrambi vanno aggiornati insieme — questo comando
  lo garantisce.
- **Override one-shot di un TSK**: usa `/dev <TSK-id>`, non `/topology` (vedi
  comando `/dev`).
