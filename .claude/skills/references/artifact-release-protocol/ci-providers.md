---
title: "artifact-release-protocol — Contratto provider CI"
scope: "Contratto trigger/poll/esito per GitHub Actions, GitLab CI, Azure DevOps (API pubbliche). Nessun host privato, nessuna pipeline ID cablata."
part_of: artifact-release-protocol
---
# Contratto provider CI

Foglia della skill `.claude/skills/artifact-release-protocol.md`.
Prerequisito: boot check completato, `TOKEN` e `PY` disponibili.

Ogni provider espone lo stesso contratto logico:
- **trigger**: avvia una pipeline/workflow dato un ref
- **poll**: interroga lo stato di un run finche' non e' `completed`
- **esito**: interpreta `result` (`succeeded` / `success` / `passed`) e propaga lo stato alla skill

---

## Verifica permessi credenziale (Fase 1c)

Fase 1c del preflight (read-only, prima dei gate locali e del gate umano R.14).
Invoca `tools/release/check_credential.py` con `--provider`, `--auth-env`, `--operations`,
`--pipeline-ref`. Esito JSON: `result: PASS | FAIL | NON_VERIFICABILE`.

### GitHub Actions — verifica permessi

**API di riferimento:**
- Identita' e scopes: `GET https://api.github.com/user`
  Header risposta `X-OAuth-Scopes` contiene gli scopes del token classico (PAT legacy).
  Token fine-grained: `X-OAuth-Scopes` assente; usare le repo permissions come proxy.
  Doc: https://docs.github.com/rest/users/users#get-the-authenticated-user
- Permessi sul repo: `GET https://api.github.com/repos/{owner}/{repo}`
  Campo `permissions.push` / `permissions.admin` → capacita' di creare tag (push di refs/tags/*).
  Doc: https://docs.github.com/rest/repos/repos#get-a-repository

| Operazione | Come verificare | Esito se mancante |
|---|---|---|
| `create_tag` | `permissions.push == true` sul repo | FAIL |
| `trigger_pipeline` | scope `workflow` o `repo` (classico); `permissions.push` (fine-grained) | FAIL |
| `push_image` | Non verificabile via GitHub API (dipende dal registry target) | NON_VERIFICABILE |
| `publish_package` | Non verificabile via GitHub API | NON_VERIFICABILE |
| `edit_manifest` | Non verificabile via GitHub API | NON_VERIFICABILE |

> **Token fine-grained**: `X-OAuth-Scopes` e' assente. Verificare invece `permissions.push`
> sul repo; per Actions write, il permesso push e' un proxy ragionevole ma non garantito
> (da confermare sul provider per token con permessi granulari).

### GitLab CI — verifica permessi

**API di riferimento:**
- Scopes PAT: `GET https://{host}/api/v4/personal_access_tokens/self`
  Campo `scopes` (es. `["api"]`, `["write_repository"]`).
  Doc: https://docs.gitlab.com/ee/api/personal_access_tokens.html
- Ruolo nel progetto: `GET https://{host}/api/v4/projects/{project_id}`
  Campo `permissions.project_access.access_level` (10=Guest, 20=Reporter, 30=Developer,
  40=Maintainer, 50=Owner).
  Doc: https://docs.gitlab.com/ee/api/projects.html

| Operazione | Come verificare | Esito se mancante |
|---|---|---|
| `create_tag` | scope `api` o `write_repository` + access_level >= 30 (Developer) | FAIL |
| `trigger_pipeline` | scope `api` + access_level >= 30 | FAIL |
| `push_image` | Non verificabile via GitLab API | NON_VERIFICABILE |
| `publish_package` | Non verificabile via GitLab API | NON_VERIFICABILE |
| `edit_manifest` | Non verificabile via GitLab API | NON_VERIFICABILE |

> `personal_access_tokens/self` funziona solo per PAT personali (non deploy token,
> non token di gruppo). In quei casi l'esito e' NON_VERIFICABILE con indicazione esplicita.

### Azure DevOps — verifica permessi

**API di riferimento:**
- Validita' PAT e accesso org: `GET https://dev.azure.com/{org}/_apis/projects?api-version=7.1`
  200 con body JSON valido = PAT valido con accesso all'organizzazione.
  Doc: https://learn.microsoft.com/rest/api/azure/devops/core/projects/list
- Accesso pipeline (proxy lettura): `GET https://dev.azure.com/{org}/{project}/_apis/pipelines/{id}?api-version=7.1`
  200 = lettura ok. Non implica QueueBuilds.
  Doc: https://learn.microsoft.com/rest/api/azure/devops/pipelines/pipelines/get

| Operazione | Come verificare | Esito |
|---|---|---|
| `create_tag` | Richiede security namespaces API (namespace GitRepositories, bit 16=CreateTag) | NON_VERIFICABILE (da confermare sul provider) |
| `trigger_pipeline` | GET pipeline: 200=lettura ok; QueueBuilds richiede security namespaces (namespace Build, bit 128) | NON_VERIFICABILE (da confermare sul provider) |
| `push_image` | Non verificabile via ADO API | NON_VERIFICABILE |
| `publish_package` | Non verificabile via ADO API | NON_VERIFICABILE |
| `edit_manifest` | Non verificabile via ADO API | NON_VERIFICABILE |

> **Gotcha ADO — PAT scaduto**: un PAT scaduto non produce 401 ma un redirect silenzioso
> a `_signin`. `urllib` segue il redirect e restituisce HTML; il parse JSON produce un
> body vuoto. Rilevabile: body vuoto o privo di `value` dopo una GET `_apis/projects`.
> Verificare prima di procedere con un `GET _apis/projects`; se non e' JSON valido → STOP.
> (Nota gia' presente in §Note comuni a tutti i provider.)

> **Security namespaces API** (informativo, da confermare sul provider):
> `GET https://dev.azure.com/{org}/_apis/securitynamespaces?api-version=7.2-preview.1`
> per elencare i namespace. `GET _apis/accesscontrollists/{namespaceId}?token={token_risorsa}`
> per leggere le ACL. La struttura e' pubblica ma complessa; per semplicita', `create_tag`
> e `trigger_pipeline` su ADO sono marcati NON_VERIFICABILE e richiedono conferma umana nel gate.

---

## GitHub Actions

**Riferimento API:** `https://docs.github.com/rest/actions/workflow-runs`

### Trigger (workflow dispatch)

```bash
# OWNER, REPO, WORKFLOW_ID, REF vengono da release_targets[].pipeline_ref
# pipeline_ref formato: "<owner>/<repo>/<workflow_file_or_id>"
OWNER=$(echo "$PIPELINE_REF" | cut -d/ -f1)
REPO=$(echo "$PIPELINE_REF"  | cut -d/ -f2)
WF=$(echo "$PIPELINE_REF"    | cut -d/ -f3)

RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d "{\"ref\":\"$VERSION_OR_REF\",\"inputs\":{}}" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/workflows/$WF/dispatches")
# 204 = ok; 422 = ref non trovato; altro = errore
HTTP_STATUS=$(echo "$RESP" | $PY -c "import json,sys; print(json.loads(sys.stdin.read() or '{}').get('status',0))" 2>/dev/null || echo "")
# workflow_dispatch restituisce 204 No Content → attendere il run listando i run recenti
sleep 5
RUN_ID=$(curl -s \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?branch=$VERSION_OR_REF&per_page=1" \
  | $PY -c "import json,sys; runs=json.load(sys.stdin).get('workflow_runs',[]); print(runs[0]['id'] if runs else '')")
SE RUN_ID vuoto → STOP fail-loud: "Impossibile trovare il run avviato su GitHub Actions."
```

Output in chat:
```
GitHub Actions avviato.
  Run ID : <RUN_ID>
  Link   : https://github.com/<owner>/<repo>/actions/runs/<RUN_ID>
```

### Polling stato

```bash
for i in $(seq 1 $MAX_ITER); do
  RESP=$(curl -s \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$OWNER/$REPO/actions/runs/$RUN_ID")
  LAST_STATE=$(echo "$RESP"  | $PY -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))")
  LAST_RESULT=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('conclusion') or '')")
  echo "[$(date -u +"%H:%M:%SZ")] iter=$i/$MAX_ITER status=$LAST_STATE conclusion=$LAST_RESULT"
  [ "$LAST_STATE" = "completed" ] && break
  sleep $SLEEP_SEC
done
```

**Valori stato**: `queued` | `in_progress` | `completed`
**Valori conclusione**: `success` | `failure` | `cancelled` | `skipped` | `timed_out` | `action_required`
Esito PASS: `conclusion == "success"`

---

## GitLab CI

**Riferimento API:** `https://docs.gitlab.com/ee/api/pipelines.html`

### Trigger (pipeline trigger o Run pipeline)

```bash
# pipeline_ref formato: "<gitlab_host>/<project_id>"
# es. "gitlab.com/42"
GL_HOST=$(echo "$PIPELINE_REF" | cut -d/ -f1)
PROJECT_ID=$(echo "$PIPELINE_REF" | cut -d/ -f2)

RESP=$(curl -s -X POST \
  -H "PRIVATE-TOKEN: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"ref\":\"$VERSION_OR_REF\"}" \
  "https://$GL_HOST/api/v4/projects/$PROJECT_ID/pipeline")
RUN_ID=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('id',''))")
SE RUN_ID vuoto → STOP fail-loud: "Lancio pipeline GitLab fallito."
```

Output in chat:
```
GitLab CI avviato.
  Pipeline ID : <RUN_ID>
  Link        : https://<gl_host>/<project_path>/-/pipelines/<RUN_ID>
```

### Polling stato

```bash
for i in $(seq 1 $MAX_ITER); do
  RESP=$(curl -s \
    -H "PRIVATE-TOKEN: $TOKEN" \
    "https://$GL_HOST/api/v4/projects/$PROJECT_ID/pipelines/$RUN_ID")
  LAST_STATE=$(echo "$RESP"  | $PY -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))")
  echo "[$(date -u +"%H:%M:%SZ")] iter=$i/$MAX_ITER status=$LAST_STATE"
  case "$LAST_STATE" in
    success|failed|canceled|skipped|blocked) break ;;
  esac
  sleep $SLEEP_SEC
done
```

**Valori stato**: `created` | `waiting_for_resource` | `preparing` | `pending` | `running` |
`success` | `failed` | `canceled` | `skipped` | `blocked` | `manual`
Esito PASS: `status == "success"`

---

## Azure DevOps (API pubbliche)

**Riferimento API:** `https://learn.microsoft.com/rest/api/azure/devops/pipelines`

> Solo endpoint documentati pubblicamente. Nessun host privato cablato nella skill.
> I parametri `ORG`, `PROJECT`, `PIPELINE_ID` vengono da `release_targets[].pipeline_ref`.
> Formato `pipeline_ref`: `"<org>/<project>/<pipeline_id>"`

### Trigger

```bash
ADO_ORG=$(echo "$PIPELINE_REF"  | cut -d/ -f1)
ADO_PROJ=$(echo "$PIPELINE_REF" | cut -d/ -f2)
ADO_PID=$(echo "$PIPELINE_REF"  | cut -d/ -f3)
B64=$(printf ":%s" "$TOKEN" | base64 | tr -d '\n')
HEADER="Authorization: Basic $B64"

RESP=$(curl -s -X POST \
  -H "$HEADER" \
  -H "Content-Type: application/json" \
  -d "{\"resources\":{\"repositories\":{\"self\":{\"refName\":\"refs/heads/$VERSION_OR_REF\"}}}}" \
  "https://dev.azure.com/$ADO_ORG/$ADO_PROJ/_apis/pipelines/$ADO_PID/runs?api-version=7.1")
RUN_ID=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('id',''))")
SE RUN_ID vuoto → STOP fail-loud: "Lancio pipeline ADO fallito."
```

### Polling stato

```bash
for i in $(seq 1 $MAX_ITER); do
  RESP=$(curl -s -H "$HEADER" \
    "https://dev.azure.com/$ADO_ORG/$ADO_PROJ/_apis/pipelines/$ADO_PID/runs/$RUN_ID?api-version=7.1")
  LAST_STATE=$(echo "$RESP"  | $PY -c "import json,sys; print(json.load(sys.stdin).get('state','unknown'))")
  LAST_RESULT=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('result',''))")
  echo "[$(date -u +"%H:%M:%SZ")] iter=$i/$MAX_ITER state=$LAST_STATE result=$LAST_RESULT"
  [ "$LAST_STATE" = "completed" ] && break
  sleep $SLEEP_SEC
done
```

**Valori state**: `unknown` | `inProgress` | `canceling` | `completed`
**Valori result**: `unknown` | `succeeded` | `failed` | `canceled` | `partiallySucceeded`
Esito PASS: `result == "succeeded"`

> **Gotcha ADO**: un PAT scaduto non produce 401 ma un 302 verso `_signin`. Verificare con
> una GET project-scoped prima del trigger; se HTTP != 200 → STOP con messaggio chiaro.

---

## Note comuni a tutti i provider

- **Non usare pipe dopo il comando CI** (`| tail`, `| jq`) per leggere l'exit code:
  la pipe maschera il codice di uscita del comando upstream. Salvare l'output in una
  variabile, poi ispezionarlo con Python.
- **Timeout esplicito**: 60 iter × 30s = 30 min per qualsiasi provider.
  A scadenza: output esplicito dell'ultimo stato, gate umano.
- **Fallimento CI = gate umano**: non riprovare automaticamente; presentare l'output
  all'utente e attendere istruzioni.
