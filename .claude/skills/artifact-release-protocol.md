---
name: artifact-release-protocol
description: >-
  Procedura operativa generica di rilascio di artefatti applicativi (container/GitOps,
  package registry npm/pypi/maven, manifest edit). Gate locali su SHA immutabile via
  worktree-gate, gate umano R.14 (JSON payload), polling foreground CI, verifica
  registry/ambiente, log append-only. Parametrica: le fasi non contengono costanti
  verticali. Invocata da artifact-release-manager o via /release-artifact.
---
# Skill: artifact-release-protocol

Procedura canonica di rilascio di artefatti applicativi a profili. Il protocollo e'
**parametrico**: le fasi non contengono nomi di host, pipeline ID, token o portali.
Ogni costante viene dal blocco `release_targets[]` di `factory.config.yaml` e dal
blocco `environment:` del target selezionato.

Aggiungere un target = aggiungere una riga a `release_targets[]`, non modificare le fasi.

## Profili supportati

| Profilo | Artefatto | Foglia |
|---|---|---|
| `container-gitops` | immagine container + manifest GitOps (kustomization o helm) | `references/artifact-release-protocol/container-gitops.md` |
| `package-registry` | pacchetto npm / pypi / maven su registro privato o pubblico | `references/artifact-release-protocol/package-registry.md` |
| `manifest-edit` | modifica diretta di un file manifest nel repo (senza pipeline separata) | `references/artifact-release-protocol/manifest-edit.md` |

Il contratto del provider CI (trigger, poll, esito) e le note per GitHub Actions, GitLab CI
e Azure DevOps Public API sono in `references/artifact-release-protocol/ci-providers.md`.

---

## Boot check

```
0. Leggi factory.config.yaml.
   - release_targets[] presente e non vuoto → prosegui.
   - release_targets[] assente o vuoto → risposta esplicita:
     "Nessun target dichiarato in release_targets[]. Aggiungere almeno una voce prima di
      procedere (vedi commento esempio in factory.config.yaml §release_targets)."
     STOP — non e' un errore tecnico.

1. Risolvi il target:
   - <target> == nome di una voce release_targets[] → carica la voce.
   - <target> non corrisponde a nessuna voce → STOP:
     "Target '<target>' non dichiarato in release_targets[]. Voci disponibili: <lista nomi>."

2. Valida i campi obbligatori della voce:
   name, code_path, profile, ci_provider, pipeline_ref, registry, environments[].
   Almeno un ambiente in environments[]. Voci mancanti → STOP fail-loud per ciascuna.

3. Valida argomenti dell'invocazione:
   version_or_ref : versione o ref da rilasciare  (obbligatorio)
   env            : ambiente target               (obbligatorio)
   dry_run        : flag --dry-run                (default false)
   SE version_or_ref assente → STOP: "version_or_ref obbligatorio."
   SE env non in environments[] → STOP:
     "Ambiente '<env>' non dichiarato per target '<name>'. Validi: <lista>."

4. Seleziona interprete Python cross-OS:
     PY=""
     for c in python3 python py; do
       command -v "$c" >/dev/null 2>&1 || continue
       "$c" -c 'import sys; sys.exit(0)' >/dev/null 2>&1 && { PY="$c"; break; }
     done
     SE PY vuoto → STOP: "Nessun interprete Python funzionante (python3/python/py)."

5. Verifica credenziali:
   Il nome della variabile d'ambiente viene dal campo auth_env della voce.
   TOKEN=$(grep -E "^${AUTH_ENV}=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"' \r")
   SE TOKEN vuoto e auth_env valorizzato → STOP:
     "${AUTH_ENV} non trovato. Imposta la credenziale prima di procedere."
   SE auth_env assente → prosegui (provider senza autenticazione, es. pubblico).

6. Log boot:
   "artifact-release-protocol avviato — target: <name> profile: <profile>
    version: <version_or_ref> env: <env> dry-run: <true|false>"
```

---

## Protocollo handoff gate R.14 — 4 passi

Identico al pattern canonico (release-protocol §Protocollo handoff gate).
**Il sub-agent emette il payload JSON e si ferma. Non aspetta conferma diretta.**

1. **Sub-agent emette payload** (tre campi obbligatori):
   ```json
   {
     "gate": "<identificativo gate>",
     "action": "<operazione da autorizzare>",
     "payload": { ... }
   }
   ```
   Il sub-agent si ferma subito dopo l'emissione (completed).

2. **Coordinator legge il payload** e presenta un riassunto leggibile all'utente.

3. **Utente conferma o rifiuta al coordinator**: `"confermato"` o `"annullato"`.

4. **Coordinator riprende il sub-agent** via `SendMessage("confermato")` o
   `SendMessage("annullato")`.

Con `"annullato"`: abort + entry `wiki/log.md` stato `aborted`, STOP.

> **Prod = doppia conferma.** Se `env == prod` (o se la voce dichiara
> `requires_double_confirm: true`), il coordinator richiede una seconda conferma
> esplicita e separata prima di riprendere. Mai deploy su prod con conferma singola.

---

## Fase 1 — Preflight (read-only)

> Tutti i controlli sono read-only. Nessuna scrittura, nessun tag, nessuna pipeline.
> Se anche un solo controllo fallisce → STOP con messaggio esplicito.
> Trigger: eseguire dopo boot check completato.

Controlla in ordine:

**1a — Branch / ref esiste sul remote**
```bash
git -C "$CODE_PATH" ls-remote origin "$VERSION_OR_REF" | grep -q .
# SE non trovato: versione potrebbe essere un semver → cerca anche refs/tags/$VERSION_OR_REF
git -C "$CODE_PATH" ls-remote origin "refs/tags/$VERSION_OR_REF" | grep -q .
SE entrambi falliscono → STOP: "Ref '$VERSION_OR_REF' non trovato su origin."
MAIN_SHA=$(git -C "$CODE_PATH" ls-remote origin "$VERSION_OR_REF" | awk '{print $1}' | head -1)
```

**1b — Versione assente su registry (idempotenza)**
Vedi foglia del profilo (`references/artifact-release-protocol/<profile>.md` §Preflight 1b).
L'agente carica la foglia prima di eseguire il controllo.

**1c — Verifica permessi credenziale**
Prima dei gate locali e del primo gate umano (R.14): verifica che la credenziale
(`auth_env` del target) abbia i permessi che il rilascio utilizzerà.
Vedi §Fase 1c — Verifica permessi credenziale.

**1d — Gate locali su SHA immutabile**
Eseguiti su worktree temporaneo detached. Vedi skill `worktree-gate` e la sezione
§Gate locali (Fase 1d) di questo protocollo.

---

## Fase 1c — Verifica permessi credenziale

> Trigger: dopo 1a e 1b PASS, prima dei gate locali e del primo gate umano.
> Tutti i controlli sono read-only.
> Vedi `references/artifact-release-protocol/ci-providers.md` §Verifica permessi credenziale.

Le operazioni attese dipendono dal profilo e dal `ci_provider`:

| Profilo | ci_provider != none | ci_provider == none |
|---|---|---|
| `container-gitops` | `create_tag trigger_pipeline push_image` | `create_tag push_image` |
| `package-registry` | `create_tag trigger_pipeline publish_package` | `publish_package` |
| `manifest-edit` | `edit_manifest` | `edit_manifest` |

```bash
# Costruisci OPERATIONS in base a profilo e ci_provider
# (es. container-gitops con github: "create_tag trigger_pipeline push_image")
$PY tools/release/check_credential.py \
  --provider "$CI_PROVIDER" \
  --auth-env "$AUTH_ENV" \
  --operations $OPERATIONS \
  --pipeline-ref "$PIPELINE_REF"

# Leggi il campo "result" dall'output JSON
CRED_RESULT=$($PY -c "import json,sys; print(json.load(sys.stdin).get('result','NON_VERIFICABILE'))" <<< "$CHECK_OUTPUT")
```

Esiti:

| result | Azione |
|---|---|
| `PASS` | Prosegui a 1d (gate locali). |
| `FAIL` | **STOP** prima di qualunque gate. Output: operazione mancante, identita', risorsa, azione richiesta (es. "chiedere all'amministratore il permesso push sul repo"). |
| `NON_VERIFICABILE` | Avviso esplicito in chat. Il rilascio prosegue **solo se l'umano lo accetta esplicitamente** nel gate R.14 (Fase 2); il payload del gate include `"credential_check": "NON_VERIFICABILE"`. Mai trattato come PASS silenzioso. |

Messaggio di STOP (FAIL):
```
PREFLIGHT 1c FAIL — permesso mancante
  Operazione : <operazione>
  Identita'  : <identity dal check>
  Risorsa    : <repo / progetto / pipeline>
  Azione     : <es. assegnare permesso push, aggiungere scope 'workflow'>
```

---

## Fase 1d — Gate locali su SHA immutabile

> Trigger: dopo 1a, 1b e 1c PASS (o 1c NON_VERIFICABILE con accettazione umana esplicita).
> Richiede la skill `worktree-gate`.
> Se `local_gates[]` e' vuoto: skip con log "nessun gate locale dichiarato per <name>."

Il sub-agent invoca la skill `worktree-gate` passando:
- `repo_path`: assoluto del `code_path`
- `sha`: `$MAIN_SHA` (risolto in 1a)
- `commands`: lista `local_gates[]` dalla voce di config
- `node_modules_symlink`: assoluto del path da linkare (se presente in config)

La skill `worktree-gate` gestisce: worktree detached + hooks disabilitati + cleanup garantito.
L'exit code di ogni comando e' letto senza pipe.

In caso di fallimento: output del comando fallito + STOP. Nessun deploy su gate locale fallito.

---

## Fase 2 — Gate R.14 pre-release (output strutturato)

**STOP obbligatorio** (R.14). Il sub-agent emette il payload e si ferma.

```json
{
  "gate": "pre-release",
  "action": "<trigger_pipeline | create_tag | publish_package>",
  "payload": {
    "target": "<name>",
    "profile": "<profile>",
    "version_or_ref": "<version_or_ref>",
    "env": "<env>",
    "sha": "<MAIN_SHA>",
    "registry": "<registry>",
    "dry_run": false,
    "credential_check": "<PASS | NON_VERIFICABILE>"
  }
}
```

> Se `credential_check == "NON_VERIFICABILE"`: il coordinator segnala all'utente che
> la verifica dei permessi non e' stata completata e chiede conferma esplicita prima
> di procedere. L'utente deve dichiarare di aver verificato i permessi manualmente.

Il coordinator presenta il riassunto; utente conferma/annulla; coordinator riprende.

> Se `dry_run: true` → questo gate viene presentato ma l'agente **non esegue** la Fase 3.
> Mostra invece il piano delle operazioni che sarebbero state eseguite, poi STOP.

---

## Fase 3 — Trigger CI e pubblicazione

> Trigger: solo dopo `SendMessage("confermato")` (gate Fase 2).
> Vedi foglia del profilo `references/artifact-release-protocol/<profile>.md` §Fase 3.
> Vedi contratto provider `references/artifact-release-protocol/ci-providers.md`.
> Se foglia non raggiungibile → STOP fail-loud.

---

## Fase 4 — Polling inline (foreground)

```
MAX_ITER=60
SLEEP_SEC=30
# loop foreground — nessun child/background task
for i in $(seq 1 $MAX_ITER); do
  LAST_STATE=$(curl ... | $PY -c "...")   # vedi foglia ci-providers per la query
  echo "[$(date -u +"%H:%M:%SZ")] iter=$i/$MAX_ITER state=$LAST_STATE"
  [ "$LAST_STATE" = "completed" ] && break
  sleep $SLEEP_SEC
done

SE LAST_STATE != "completed" → output esplicito ultimo stato → STOP (gate umano)
SE LAST_RESULT == "failed" | "canceled" → STOP; output result + link; gate umano
SE LAST_RESULT == "succeeded" → prosegui a Fase 5
```

Timeout esplicito: 60 iter × 30s = 30 min.

---

## Fase 5 — Verifica registry/ambiente

> Trigger: dopo Fase 4 `result=succeeded`.
> Vedi foglia del profilo §Fase 5 per la query di verifica.
> SE la versione non e' ancora visibile → WARNING (propagazione lenta); non STOP.

Output in chat:
```
Verifica post-release
  Target    : <name>
  Versione  : <version_or_ref>
  Ambiente  : <env>
  Presente  : <si | no | non verificabile>
```

---

## Fase 6 — Chiusura (log append-only)

Append obbligatorio a `wiki/log.md` (R.5). Se non scrivibile → STOP fail-loud.

```markdown
## YYYY-MM-DD HH:MM — release-artifact <name> <version_or_ref> → <env> — <DONE|ABORTED|DRY-RUN>
**Agente:** artifact-release-manager
**Profilo:** <profile>
**SHA:** <MAIN_SHA>
**CI run:** <RUN_ID | dry-run | —>
**Verifica registry:** <si | no | dry-run>
**Stato:** <done | aborted | dry-run>
```

---

## Regole

- **Verifica permessi prima dei gate** (Fase 1c) — FAIL blocca prima di gate locali e gate umano;
  NON_VERIFICABILE richiede accettazione umana esplicita nel gate R.14. Mai trattato come PASS silenzioso.
- **Mai triggerare CI senza gate locale PASS** — `local_gates[]` vuoto = skip lecito,
  non bypass: l'assenza di gate locali e' una scelta di configurazione, non un errore.
- **Gate umano obbligatorio** (Fase 2) — R.14, via output strutturato JSON. Mai bypassare.
- **Prod richiede doppia conferma esplicita e separata** — mai rilascio prod con conferma singola.
- **Polling sempre inline (foreground)** — nessun child/background task per CI.
- **Timeout esplicito** — 60 iter × 30s = 30 min; a scadenza output esplicito dell'ultimo stato.
- **Nessuna scrittura su `code_path`** dell'artefatto — l'agente non committa nel submodule
  ne' nel code_path target.
- **Append-only su `wiki/log.md`** — una entry per rilascio (incluse le `aborted`).
- **Lista vuota = risposta esplicita** — `release_targets[]` vuoto non e' un errore; l'agente
  risponde con un messaggio chiaro e si ferma.
- **Comandi di shell portabili**: segui `.claude/skills/shell-portability.md` (POSIX, flag
  comuni a GNU e BSD, Python per il parsing; su Windows tool `Bash`, mai PowerShell).

## Foglie

| Foglia | Contenuto | Trigger |
|---|---|---|
| `references/artifact-release-protocol/container-gitops.md` | Preflight 1b (tag/immagine assente), Fase 3 (build+push immagine, update manifest), Fase 5 (verifica deployment) | Profilo `container-gitops` |
| `references/artifact-release-protocol/package-registry.md` | Preflight 1b (versione assente su registro), Fase 3 (publish npm/pypi/maven), Fase 5 (verifica dist-tags / metadata) | Profilo `package-registry` |
| `references/artifact-release-protocol/manifest-edit.md` | Preflight 1b (check versione attuale), Fase 3 (edit YAML inline + commit via API o git), Fase 5 (verifica manifesto aggiornato) | Profilo `manifest-edit` |
| `references/artifact-release-protocol/ci-providers.md` | Contratto provider (trigger, poll, esito) + note GitHub Actions, GitLab CI, Azure DevOps (solo API pubbliche) + verifica permessi (Fase 1c) | Fasi 1c, 3, 4 |
