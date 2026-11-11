---
name: github-mapping
description: Mapping provider-specific GitHub per il github-publisher (PATTERN §17, v2.10). Definisce come EP/US/TSK/sprint diventano Issue/Milestone/Label e i comandi gh CLI esatti.
---
# Mapping GitHub (provider-specific per github-publisher)

Riferimenti: PATTERN §17 (Publisher adapters), `publisher-protocol` (5 fasi
agnostic), `citation-rules`.

Questa skill è invocata da `publisher-protocol` Fase 4 (Build payload + Execute).
Definisce **come** un artefatto locale diventa un artefatto GitHub.

## Auth check (Fase 1 di publisher-protocol)

```bash
gh auth status
```

Atteso: exit 0 + utente loggato sul target. Se exit ≠ 0 → ABORT con messaggio
«Esegui `gh auth login` e riprova».

Verifica anche permessi su `target`:

```bash
gh repo view <target> --json viewerPermission
```

Atteso: `viewerPermission` ∈ {`ADMIN`, `MAINTAIN`, `WRITE`}. Altrimenti
WARNING «Permessi insufficienti su <target>, le operazioni di CREATE/UPDATE
potrebbero fallire».

## Mapping artefatti

### Epica (`EP-XXX-<slug>/EP-XXX.md`)

Default (`mapping.epic_to: milestone`):

- **Milestone GitHub**: titolo `EP-XXX: <title>`, descrizione = body markdown del file (troncato a ~10k chars se necessario).
- Stato: `open` se `status: in_progress` o `todo`; `closed` se `status: done`.
- Due date: se `EP-*.md` ha campo `due_date:` nel frontmatter (opzionale), passato come `--due-date`. Altrimenti omesso.

Alternativa (`mapping.epic_to: issue-label`):

- **Issue GitHub**: titolo `EP-XXX: <title>`, body markdown, label `kanban:epic` + label specifiche.

### User Story (`US-YYY/US-YYY.md`)

Default (`mapping.story_to: issue-label`):

- **Issue GitHub**: titolo `US-YYY: <title>`, body markdown (vedi §Body sotto).
- Label: `kanban:story` + `role:<role>` (es. `role:cittadino`) + eventuale `priority:<level>` (es. `priority:high`).
- Milestone: link alla milestone dell'epica genitore (lookup via `external_id` dell'EP).
- Stato: `open` (story aperte) / `closed` (story con `status: done`).

### Task (`TSK-ZZZ.md`)

Default (`mapping.task_to: issue-label`):

- **Issue GitHub**: titolo `TSK-ZZZ: <title>`, body markdown.
- Label: `kanban:task` + `layer:<layer>` (es. `layer:be`) + `consumer:<consumer>` + `priority:<level>` + `estimate:<n>`.
- Milestone: come per US (epica genitore).
- Assignee: skip in v2.10 (out-of-scope). Default unassigned.

### Sprint (`sprint.md`)

Default (`mapping.sprint_to: milestone`):

- **Milestone GitHub** dedicata: `Sprint <NN>` con descrizione = sezione del sprint corrente in `sprint.md`.
- Link cross-reference: i TSK appartenenti al sprint sono linkati alla milestone in Fase 4 (oltre a quella dell'epica). Se GitHub permette solo una milestone per issue: priorità all'**epica** (la sprint milestone sarà popolata via Project iteration in una v2.11+).

## §Body — template del body Markdown

Per Epica/Story/Task il body GitHub è il file locale verbatim **eccetto**:

1. **Header in cima**: aggiungi un blockquote di metadati Factory:

   ```
   > **Factory:** llm-wiki++ v2.10 · **Artefatto:** management/kanban/<path>
   > **Layer:** <layer> · **Consumer:** <consumer> · **Priority:** <priority> · **Estimate:** <estimate>
   > **Citazione:** [^src: <relative path nel factory repo>]
   ```

2. **Footer**:

   ```
   ---
   _Mirror push-only generato da `github-publisher` (PATTERN-integration.md §17). Source of truth: `management/kanban/<path>` nel factory repo._
   ```

3. **Wikilink `[[slug]]`**: lasciati testuali (non renderizzati da GitHub). Aggiungi nota al primo wikilink: `<!-- I link [[...]] sono wikilink della knowledge base; risolverli nel factory repo. -->`

4. **Citazioni `[^src: ...]`**: lasciate testuali (non renderizzate da GitHub). Preserva la sintassi originale.

## §Build payload + Execute (Fase 4 di publisher-protocol)

### CREATE — Epica come Milestone

```bash
gh api repos/<target>/milestones --method POST \
   --field title="EP-XXX: <title>" \
   --field description="$(cat /tmp/factory-publish-EP-XXX.md)" \
   --field state="open"
```

Parse della risposta JSON → `number` (es. `5`) → `external_id: github:5`
(prefisso `m` interno per distinguere da issue: in pratica salviamo
`external_id: github:milestone-5` quando l'artefatto è Milestone, e
`external_id: github:1247` quando è Issue. Lint Check 4f valida il prefisso.)

### CREATE — Story/Task come Issue

```bash
gh issue create --repo <target> \
   --title "US-YYY: <title>" \
   --body-file /tmp/factory-publish-US-YYY.md \
   --label "kanban:story,role:cittadino,priority:high" \
   --milestone "<milestone-title>"
```

Parse output → URL formato `https://github.com/<target>/issues/<num>` →
`external_id: github:<num>`.

### UPDATE — Story/Task

```bash
gh issue edit <num> --repo <target> \
   --body-file /tmp/factory-publish-US-YYY.md \
   --add-label "..." --remove-label "..."
```

### UPDATE — Milestone

```bash
gh api repos/<target>/milestones/<num> --method PATCH \
   --field title="EP-XXX: <updated title>" \
   --field description="$(cat /tmp/factory-publish-EP-XXX.md)" \
   --field state="open|closed"
```

### State sync (close on done)

Se `status: done` localmente:

```bash
gh issue close <num> --repo <target> --reason completed
```

```bash
# Per milestone:
gh api repos/<target>/milestones/<num> --method PATCH --field state="closed"
```

**Mai** `close` con `reason: not planned` automaticamente (ambiguo
semanticamente; out-of-scope).

## Idempotenza & corner case

- **Re-publish di un artefatto già `closed` sul provider con `status: todo` locale**: rilancio in `state: open` (re-open). Caso d'uso: l'umano ha chiuso a mano, la factory dice ancora todo. Privilegia il locale.
- **Issue esterna cancellata a mano**: GET `gh issue view <num>` ritorna 404 → cancella `external_id:` locale, ricade in CREATE al prossimo run.
- **Milestone già con stesso titolo ma external_id diverso**: WARNING in chat, SKIP. Risoluzione: l'umano cancella la milestone duplicata o aggiorna manualmente `external_id:`.
- **Label inesistente sul repo**: `gh issue create` con label non esistente fallisce. La skill, prima della prima Fase 4, esegue un pre-flight:
  ```bash
  gh label create "kanban:epic" --color "B60205" --description "Mirror Factory EP-*" --force
  gh label create "kanban:story" --color "0E8A16" --description "Mirror Factory US-*" --force
  gh label create "kanban:task" --color "1D76DB" --description "Mirror Factory TSK-*" --force
  gh label create "layer:be" --color "5319E7" --force
  gh label create "layer:fe" --color "5319E7" --force
  gh label create "layer:db" --color "5319E7" --force
  gh label create "layer:qa" --color "5319E7" --force
  gh label create "layer:infra" --color "5319E7" --force
  ```
  (Solo CREATE; `--force` evita errori su label già esistenti.)

## Rate limit

GitHub REST API: 5000 req/h con token utente. La skill rate-limita a 1 req/s
soft (sleep 1 fra operazioni successive). Su 429 → backoff esponenziale
(base 1500ms, max 3 retry, poi ABORT).

## Sicurezza

- Token (`GH_TOKEN`) **mai loggato** in chat, mai scritto in file.
- Body files temporanei in `/tmp/factory-publish-*.md` cancellati alla fine
  della Fase 4.
- Scope token minimo: `repo:issues:write` + `repo:metadata:read`. Token con
  scope `admin` o `delete` è eccessivo e segnalato come WARNING.

## Non in scope per github-mapping (v2.10)

- GitHub Projects v2 (board column, custom fields): out-of-scope.
- Comment sync, reaction sync: out-of-scope.
- Assignee/Reviewer auto-assignment: out-of-scope.
- Bidirectional `status:`: candidato v2.11.
- Multi-repo target (più target per provider): out-of-scope.
