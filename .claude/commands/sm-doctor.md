---
description: "Diagnosi + auto-heal NON distruttivo dei submodule dichiarati in factory.config.yaml. Ripara i casi sicuri (init, allinea al puntatore su tree pulito, reinstalla hook §ai_policy se suppress_ai_traces:true) e per il resto stampa il comando esatto. Mai --force, mai clean. Contraltare attivo del read-only /vcs-status."
argument-hint: "[target-name] [--align] [--dry-run]"
version: "1.0"
since: "2026-10-05"
status: active
trigger: /sm-doctor
owner: soli92
epic: EP-069
us: US-311
---

# /sm-doctor -- Diagnosi + auto-heal submodule

Argomenti utente: `$ARGUMENTS`

Comando sicuro e guidato per riportare i submodule dichiarati in
`factory.config.yaml` (code_paths[] con `vcs.mode: submodule`) allo stato
tracciato dalla factory, **senza mai distruggere lavoro non committato**.
Sostituisce la "sequenza reset nucleare" (`reset --hard` + `clean -ffd` +
`submodule update --force`) con un'operazione idempotente e sicura.

E' il contraltare **attivo** di `/vcs-status` (read-only): `/vcs-status` ti
dice cosa non va, `/sm-doctor` lo ripara quando e' sicuro farlo.

**Senza entry submodule in config**: esce 0 con messaggio esplicito.
Non e' un errore -- questa factory potrebbe non avere submodule gestiti.

## Cosa ripara da solo (non distruttivo)

- Submodule **non inizializzato** -> `git submodule update --init`
- **Puntatore out of sync + tree pulito + detached HEAD** -> allinea al commit tracciato
- **Hook §ai_policy mancanti/obsoleti** -> reinstalla `pre-commit` + `commit-msg`
  (SOLO se `ai_attribution_policy.suppress_ai_traces: true` in `factory.config.yaml`)

## Submodule archiviati (`archived = true`)

Un submodule con `archived = true` in `.gitmodules` e' trattato come **sola lettura**:
sm_doctor lo segnala informativamente e non esegue nessuna azione automatica
(nessun healed, nessun needs_human). Come si archivia un submodule:

```ini
# in .gitmodules
[submodule "code_repos/my-repo"]
    path    = code_repos/my-repo
    url     = https://example.com/my-repo.git
    archived = true
```

Effetti sugli altri tool: `sm_checkout`, `sm_commit --coordinated` e `sm_update`
rifiutano con exit 1; `sm_status` mostra l'etichetta `[archiviato (read-only)]`
senza segnalare drift del puntatore. Vedi `tools/vcs/README-submodule.md`
§Submodule archiviati per la tabella completa.

## Cosa segnala soltanto (decisione umana -- R.14)

- **Modifiche non committate** nel submodule -> mai toccate; stampa `stash`/commit + ri-esegui
- **Out of sync su un branch** (clean) -> potrebbe essere lavoro intenzionale; propone
  `--align` (allinea a puntatore) oppure `sm_commit.py --pointer-only` (aggiorna il puntatore)

## Sintassi

```
/sm-doctor                    # tutti i submodule dichiarati in config
/sm-doctor my-repo            # solo un target
/sm-doctor --align            # allinea al puntatore anche i submodule su branch (clean)
/sm-doctor --dry-run          # diagnosi senza modifiche
```

## Procedura

### Step 0 -- Parse argomenti

Da `$ARGUMENTS` rileva:
- `TARGET`: primo token che non inizia con `--` (opzionale)
- `FLAG_ALIGN`: true se `--align` presente
- `FLAG_DRY_RUN`: true se `--dry-run` presente

### Step 1 -- Esecuzione

Esegui dalla root della factory (default: dry-run per sicurezza):

```bash
python3 tools/vcs/sm_doctor.py \
  ${TARGET:+--target "$TARGET"} \
  ${FLAG_ALIGN:+--align} \
  ${FLAG_DRY_RUN:+--dry-run}
```

**Default senza flag**: eseguito SENZA `--dry-run` (ripara effettivamente).
Se l'utente vuole solo diagnosi, deve passare `--dry-run`.

### Step 2 -- Riporta l'esito

Riporta in chat il riepilogo prodotto dallo script:
- **Riparato**: elenco delle azioni auto-eseguite (init / allineamenti / hook)
- **Richiede intervento umano**: per ogni voce, motivo + comando esatto suggerito
- **Nessun submodule dichiarato**: se config non ha entry vcs.mode: submodule

Exit 0 = tutto verde o auto-riparato · Exit 1 = restano azioni umane (avviso, non STOP).

## Vincoli

1. **Mai distruttivo**: nessun `--force`, nessun `git clean`, nessun reset di un
   tree con modifiche non committate.
2. **R.14 gate umano**: i casi ambigui (dirty out-of-sync, branch out-of-sync)
   non vengono risolti in automatico -- solo segnalati con il comando esatto.
3. **Idempotente**: rieseguibile senza effetti collaterali.
4. **§ai_policy condizionale**: la reinstallazione hook e' attiva SOLO se
   `ai_attribution_policy.suppress_ai_traces: true` in `factory.config.yaml`.
5. **Config-driven**: i target vengono da `code_paths[]` con `vcs.mode: submodule`,
   non da un prefisso directory cablato.

## Cross-link

- **Diagnosi read-only**: `/vcs-status`
- **Checkout branch**: `tools/vcs/sm_checkout.py`
- **Update da origin**: `tools/vcs/sm_update.py`
- **Commit coordinato + puntatore**: `tools/vcs/sm_commit.py --coordinated`
- **Auto-align dopo pull/checkout**: `tools/vcs/install_factory_hooks.py`
- **Script**: `tools/vcs/sm_doctor.py`
- **Runbook**: `tools/vcs/README-submodule.md`
