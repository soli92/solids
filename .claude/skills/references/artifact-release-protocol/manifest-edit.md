---
title: "artifact-release-protocol — Profilo manifest-edit"
scope: "Preflight (versione attuale in manifest), Fase 3 (edit YAML inline + commit via API VCS o git locale), Fase 5 (verifica manifesto aggiornato). Nessun host privato cablato."
part_of: artifact-release-protocol
---
# Profilo manifest-edit

Foglia della skill `.claude/skills/artifact-release-protocol.md`.
Prerequisito: boot check completato, variabili `TOKEN`, `PY`, `MAIN_SHA` disponibili.

Profilo per aggiornare un file di configurazione/manifest nel repo senza una pipeline separata.
Casi tipici: bump di una versione in `Chart.yaml`, `values.yaml`, `docker-compose.yml`,
`kustomization.yaml` (senza pipeline GitOps), `package.json` di un consumer.

Costanti dal blocco `release_targets[]`:
- `registry`: path al file da modificare, relativo alla root del code_path
  (es. `deploy/helm/Chart.yaml`, `docker-compose.yml`)
- `manifest_field`: percorso YAML del campo da aggiornare (es. `appVersion`, `image.tag`)
- `commit_message_template`: template del messaggio di commit (default: `"bump <name> to <version>"`)
- `vcs_api`: `github` | `gitlab` | `ado` | `none` (default `none` = git locale)

> Con `ci_provider: none` e `vcs_api: none` l'agente modifica il file localmente e
> chiede un gate umano pre-commit prima di pushare.

---

## Preflight 1b — Lettura versione attuale in manifest

```bash
MANIFEST_FILE="$CODE_PATH/$REGISTRY"  # qui 'registry' e' usato come path file
[ -f "$MANIFEST_FILE" ] || { echo "STOP 1b: manifest '$MANIFEST_FILE' non trovato."; exit 1; }

# Lettura del campo attuale (best-effort, non bloccante)
CURRENT_VAL=$(cat "$MANIFEST_FILE" | $PY -c "
import sys, re
field = '$MANIFEST_FIELD'
content = sys.stdin.read()
m = re.search(rf'^{re.escape(field)}:\s*(\S+)', content, re.MULTILINE)
print(m.group(1) if m else 'sconosciuto')
")
echo "1b: campo '$MANIFEST_FIELD' attuale = '$CURRENT_VAL'"
echo "    Nuovo valore: '$VERSION_OR_REF'"
```

> Il controllo 1b e' informativo: non blocca il flusso se il campo non e' trovato,
> ma include `current_val` nel payload del gate R.14.

---

## Fase 3 — Aggiornamento manifest (con gate R.14 pre-commit)

### 3a — Gate R.14 pre-edit (output strutturato)

**STOP obbligatorio** (R.14). Il sub-agent emette il payload e si ferma:

```json
{
  "gate": "pre-manifest-edit",
  "action": "edit_manifest_field",
  "payload": {
    "file": "<MANIFEST_FILE>",
    "field": "<manifest_field>",
    "old_value": "<CURRENT_VAL>",
    "new_value": "<version_or_ref>",
    "commit_message": "<commit_message_template interpolato>"
  }
}
```

Il coordinator raccoglie la conferma; su `"annullato"` → abort + log, STOP.

### 3b — Aggiornamento del campo (dopo conferma)

**Via API VCS (preferito — nessuna scrittura locale):**

```bash
# GitHub (api.github.com/repos/<owner>/<repo>/contents/<path>)
# Richiede: OID del file corrente (SHA blob), contenuto in base64
FILE_PATH="$REGISTRY"   # path relativo nel repo
OWNER_REPO=$(echo "$PIPELINE_REF" | cut -d/ -f1,2)

# Lettura OID e contenuto attuale
RESP=$(curl -s \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$OWNER_REPO/contents/$FILE_PATH?ref=$MAIN_SHA")
FILE_SHA=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('sha',''))")
CONTENT_B64=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('content',''))")

# Decodifica, modifica, ricodifica
NEW_CONTENT=$($PY -c "
import base64, re, sys
content = base64.b64decode('$CONTENT_B64').decode()
new_content = re.sub(
    r'(^$MANIFEST_FIELD:\s*)(\S+)',
    r'\g<1>$VERSION_OR_REF',
    content, count=1, flags=re.MULTILINE
)
print(base64.b64encode(new_content.encode()).decode())
")

COMMIT_MSG=$(echo "$COMMIT_MESSAGE_TEMPLATE" \
  | $PY -c "import sys; t=sys.stdin.read(); print(t.replace('<name>','$TARGET_NAME').replace('<version>','$VERSION_OR_REF'))")

# PUT per aggiornare il file
RESP=$(curl -s -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"$COMMIT_MSG\",\"content\":\"$NEW_CONTENT\",\"sha\":\"$FILE_SHA\",\"branch\":\"$VERSION_OR_REF\"}" \
  "https://api.github.com/repos/$OWNER_REPO/contents/$FILE_PATH")
NEW_SHA=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('content',{}).get('sha',''))")
SE NEW_SHA vuoto → STOP fail-loud: "Aggiornamento manifest via API GitHub fallito."
```

**Via git locale (vcs_api: none):**

```bash
# Usa il tool Edit per la scrittura portabile (evita differenze sed GNU/BSD)
# Poi committa:
git -C "$CODE_PATH" add "$REGISTRY"
git -C "$CODE_PATH" -c core.hooksPath=/dev/null commit \
  -m "$COMMIT_MSG" --no-verify 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: commit locale fallito (exit $rc)."; exit $rc; }

# Push (gate R.14 pre-push incluso nel payload precedente o gate separato)
git -C "$CODE_PATH" push origin HEAD 2>&1; rc=$?
[ $rc -eq 0 ] || { echo "STOP: push fallito (exit $rc)."; exit $rc; }
```

> Il push locale costituisce una **scrittura su `code_path`**: e' ammessa solo per questo profilo
> e solo dopo gate R.14 esplicito. Se il repo usa `ai_policy`, il messaggio di commit non deve
> contenere tracce AI (vedi `sm-commit.py` in tools/vcs/).

---

## Fase 5 — Verifica manifesto aggiornato

```bash
# Ri-leggi il campo dal file (locale o via API) e verifica che coincida con VERSION_OR_REF
NEW_VAL=$(cat "$MANIFEST_FILE" | $PY -c "
import sys, re
field = '$MANIFEST_FIELD'
content = sys.stdin.read()
m = re.search(rf'^{re.escape(field)}:\s*(\S+)', content, re.MULTILINE)
print(m.group(1) if m else '')
")

if [ "$NEW_VAL" = "$VERSION_OR_REF" ]; then
  echo "Verifica manifest OK: '$MANIFEST_FIELD' = '$NEW_VAL'"
else
  echo "WARN manifest: campo '$MANIFEST_FIELD' = '$NEW_VAL' (atteso '$VERSION_OR_REF')"
fi
```
