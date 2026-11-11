---
title: "artifact-release-protocol — Profilo container-gitops"
scope: "Preflight (immagine assente su registry), Fase 3 (build+push immagine, update manifest GitOps), Fase 5 (verifica deployment). Nessun host privato cablato."
part_of: artifact-release-protocol
---
# Profilo container-gitops

Foglia della skill `.claude/skills/artifact-release-protocol.md`.
Prerequisito: boot check completato, variabili `TOKEN`, `PY`, `MAIN_SHA` disponibili.

Costanti dal blocco `release_targets[]`:
- `registry`: URL del container registry (es. `ghcr.io/org/image`, `registry.gitlab.com/group/project`)
- `manifest_path`: path relativo al file kustomization/helm da aggiornare nel repo manifest
- `image_tag_field`: campo YAML da aggiornare (default: `newTag`)

---

## Preflight 1b — Immagine/tag assente su registry

> Verificare che il tag non esista gia' sul registry. Le immagini container taggiate con
> un semver sono de-facto immutabili per la maggior parte dei registry.

Approccio generico (HTTP HEAD, non richiede docker CLI):

```bash
# Esempio per registry OCI compatibile (Docker Hub, GHCR, GitLab Registry)
# Il token potrebbe richiedere uno scambio OAuth — vedere docs del registry specifico.
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  "https://$REGISTRY/v2/$IMAGE_NAME/manifests/$VERSION_OR_REF")

case "$HTTP_CODE" in
  200|301) echo "STOP 1b: il tag '$VERSION_OR_REF' esiste gia' su '$REGISTRY'. \
                 Le immagini taggiate sono immutabili. Usare un nuovo tag." ; exit 1 ;;
  404) echo "1b OK: tag '$VERSION_OR_REF' non presente su registry." ;;
  *) echo "WARN 1b: verifica registry non conclusiva (HTTP $HTTP_CODE). Prosegui con cautela." ;;
esac
```

> Se l'autenticazione del registry usa flow OAuth o credenziali diverse dal campo `auth_env`,
> documentarlo in `factory.config.yaml` sotto `release_targets[].registry_auth_notes`
> e adattare il check.

---

## Fase 3 — Build immagine + push + update manifest

> Trigger: solo dopo gate R.14 Fase 2 confermato.
> La logica e' divisa in due sottofasi: CI pipeline (build/push) e aggiornamento manifest.

### 3a — Trigger pipeline CI (build + push)

Delega alla foglia `ci-providers.md` per il provider dichiarato in `ci_provider`.
Al termine del polling (Fase 4), se `result=succeeded`:
- L'immagine e' disponibile su `registry` con tag `version_or_ref`.
- Il `RUN_ID` del build e' disponibile per il log.

### 3b — Aggiornamento manifest GitOps (gate R.14 pre-manifest)

**STOP obbligatorio** (R.14). Il sub-agent emette il payload e si ferma:

```json
{
  "gate": "pre-manifest",
  "action": "update_gitops_manifest",
  "payload": {
    "manifest_path": "<manifest_path>",
    "image_tag_field": "<image_tag_field>",
    "old_tag": "<current tag letto dal manifest>",
    "new_tag": "<version_or_ref>",
    "env": "<env>"
  }
}
```

Il coordinator raccoglie la conferma; su `"annullato"` → abort + log, STOP.

### 3c — Scrittura manifest (dopo conferma 3b)

L'aggiornamento avviene preferibilmente via API REST del VCS (per evitare scritture
locali su `code_path`). Se non disponibile, via `git` sul repo manifest:

```bash
# Lettura valore corrente (best-effort, non bloccante)
OLD_TAG=$(grep "$IMAGE_TAG_FIELD" "$MANIFEST_PATH" | $PY -c "
import sys, re
m = re.search(r'newTag:\s*(\S+)', sys.stdin.read())
print(m.group(1) if m else 'sconosciuto')
")

# Sostituzione POSIX-portabile (Edit tool preferito per file locali)
# Su macOS: sed -i.bak; su Linux: sed -i
sed -i.bak "s|${IMAGE_TAG_FIELD}:.*|${IMAGE_TAG_FIELD}: ${VERSION_OR_REF}|" "$MANIFEST_PATH" \
  && rm "${MANIFEST_PATH}.bak"

# Verifica che la sostituzione sia avvenuta
grep -q "$VERSION_OR_REF" "$MANIFEST_PATH" \
  || { echo "STOP: aggiornamento manifest fallito."; exit 1; }
```

> Preferire il tool `Edit` per la scrittura locale (evita differenze GNU/BSD in sed).
> La scrittura via API REST del VCS non lascia file locali modificati (preferibile per
> repo che usano §ai_policy o che hanno core.hooksPath configurato).

---

## Fase 5 — Verifica deployment

```bash
# Verifica che il deployment sia attivo nell'ambiente target.
# Approccio generico: interroga l'endpoint di health/readiness dell'applicazione.
# I dettagli (URL, metodo, campo da ispezionare) vengono da release_targets[].registry.

HEALTH_URL=$(echo "$REGISTRY" | $PY -c "
import sys
# Interpreta registry come 'host/app/env-health' oppure usa un campo dedicato
# Se non configurato, skip con warning
line = sys.stdin.read().strip()
print(line if line.startswith('http') else '')
")

if [ -z "$HEALTH_URL" ]; then
  echo "WARN Fase 5: nessun endpoint di verifica configurato per '$TARGET_NAME'. Skip."
else
  RESP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
  case "$RESP_CODE" in
    200|204) echo "Verifica deployment OK (HTTP $RESP_CODE)" ;;
    *) echo "WARN deployment: health check risponde HTTP $RESP_CODE (potrebbe essere in propagazione)" ;;
  esac
fi
```

> La verifica deployment e' best-effort (non bloccante). Un warning non interrompe il protocollo
> ma viene incluso nel log di chiusura.
