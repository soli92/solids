---
name: bootstrap-validation-protocol
description: Skill di validazione e report finale del factory-bootstrap. Esegue 24 check di accettazione (struttura, topology, VCS, scheduler, CQRL, multi-repo, coupling), gestisce wiki feeding source post-scaffolding (PDF / repo-sync / Figma), produce report con prossimi step.
---
# Skill — Bootstrap validation + final report

Riferimenti: PATTERN §13 (topology coherence), §15 (VCS coherence), §16 (sync +
coupling R.B1-R.B6), §17 (publisher), §18 (scheduler), §19 (CQRL).

## Input atteso

Dict completo da tutte le skill precedenti:
- `bootstrap-input-protocol` → input utente
- `bootstrap-multirepo-protocol` → `code_paths`, `factory_dest_path` (se multi-repo)
- `bootstrap-scaffolding-protocol` → `artifact_inventory`, `files_created`
- `bootstrap-vcs-protocol` → `manual_commands`, `factory_lock_created`

## Fase 1 — Wiki feeding source bootstrap (post-scaffolding)

In base a `wiki_feed_source`:

### `empty`
Nessuna operazione. Il report finale ricorderà di popolare `raw/` quando l'utente avrà
materiale.

### `pdf`
**Copia** i PDF dalla `pdf_folder` indicata dentro `<factory_dest_path>/raw/`. Preserva
i nomi originali o normalizzali al pattern `YYYY-MM-DD-<slug>.pdf`. Mai eseguire
`pdf-to-text` automaticamente — scope di `/sync-docs`.

### `figma`
Nessuna copia. Il report finale stamperà:
```
/figma-sync <figma_url-or-file_key>
```
come prossimo step. Non invocare automaticamente.

### `existing-repo` (v2.12 multi-repo)

**Loop** su `code_paths` (N entry):
1. Per ogni entry, invoca `/repo-sync <entry.path>` (NON il `factory_dest_path` —
   protezione anti-self-ingest).
2. `repo-sync` ha il suo gate interno (Fase 1 + Fase 4 di `repo-extraction-protocol`)
   che chiederà conferma per ciascun repo.
3. Al termine N file `raw/YYYY-MM-DD-repo-<name>.md` esistono + N entry in
   `raw/.extraction-manifest.json` con `source: repo`.
4. Se N ≥ 3: suggerisci `wiki-keeper` con fan-out parallelo via `wiki-keeper-worker`
   (PATTERN §3 Ingest).

**Verifica post-loop**:
- Per ciascuna entry con `coupling: monorepo` (al massimo 1, R.B6): segnala in chat
  «Reminder: il repo target ora contiene sia il codice originale sia l'infrastruttura
  factory. Considera un commit dedicato (es. `chore: bootstrap factory v2.12 in
  monorepo`) per isolare l'aggiunta nella storia git».
- Per ciascuna entry con `coupling: sibling|submodule`: verifica `git -C <source-path>
  status` → unchanged (R.B1).

## Fase 2 — Check di accettazione (24 voci)

Itera la checklist e segnala ciascuna PASS / FAIL:

### Versioning
- [ ] `PATTERN.md` esiste e dichiara `v2.12` in §0.
- [ ] `factory.config.yaml` esiste con `pattern_version: "2.12"`.

### Topology + routing
- [ ] `topology:` coerente con i file dev-agent presenti (`<X>-dev.md` esiste ⇔ `routing.X: agent`).
- [ ] `.claude/agents/` contiene esattamente gli agent file attesi (no più, no meno).
- [ ] `.claude/commands/` contiene `/dev` e `/topology` sse topologia include almeno un dev-agent.

### Code path / VCS
- [ ] Single-repo legacy: `code_path:` valorizzato sse topologia include dev-agent; `vcs.mode` coerente con `code_path`.
- [ ] **Multi-repo (v2.12)**: blocco `code_paths:` valorizzato; `name` univoco per ogni entry; ogni entry ha `path`, `layers`, `vcs.mode`.
- [ ] **R.B6 multi-repo**: al massimo **UNA** entry ha `vcs.mode: monorepo`. Se ≥ 2 → ERROR.
- [ ] **Routing↔layers coherence (multi-repo Check 4c esteso)**: per ogni `routing.<X>: agent`, almeno una entry in `code_paths` ha `<X>` in `layers`.

### Wiki feeding source
- [ ] `wiki_feed_source: pdf` ⇒ PDF copiati in `raw/`.
- [ ] `wiki_feed_source: existing-repo` ⇒ N file `raw/<data>-repo-<name>.md` esistono (uno per entry).
- [ ] `wiki_feed_source: existing-repo` + coupling per ciascuna entry verificato:
      - `monorepo` ⇒ R.B2 gate passato (nessun path della factory esisteva nel repo sorgente)
      - `sibling`/`submodule` ⇒ R.B1 verificato (repo sorgente invariato, `git status` unchanged)

### Side-channel
- [ ] Le directory L1-L4 esistono (vuote ok).
- [ ] L5 esiste solo se applicabile.
- [ ] `memory/{episodic,semantic,procedural}/` esistono.

### Skill / VCS
- [ ] Skill `vcs-handoff.md` presente sse almeno una entry ha `vcs.mode != none`.
- [ ] `.factory-lock` presente al root sse almeno una entry ha `commit_coupling: pin`.

### Kanban publish (v2.10)
- [ ] Blocco `kanban_publish:` valorizzato in config (anche se `provider: none`).
- [ ] Se `provider != none`: agent `<provider>-publisher.md`, skill `<provider>-mapping.md` + `publisher-protocol.md`, comando `/kanban-publish` presenti.

### Scheduler (v2.11)
- [ ] Blocco `scheduler:` valorizzato.
- [ ] Skill `parallel-scheduling.md` presente sse `scheduler.enabled: true`.
- [ ] Orchestrator cita `parallel-scheduling` se `scheduler.enabled: true`.

### Code Quality Review Layer (v2.12)
- [ ] Blocco `code_quality:` valorizzato.
- [ ] Se `enabled: true`: agent `code-reviewer.md`, skill `code-review-protocol`/`stack-detector`/`feedback-router`, comando `/review` presenti.
- [ ] Se `enabled: true`: directory `code_quality/rules/{canonical,emergent,team-specific}/` + `code_quality/reports/{,_digests}/` esistono.
- [ ] `scheduler.domains.review` valorizzato (default `true` se CQRL on, ignorato altrimenti).

### Repo-sync (v2.12)
- [ ] Se `wiki_feed_source == existing-repo` OR opt-in: agent `repo-sync.md`, skill `repo-extraction-protocol.md` + `stack-detector.md`, comando `/repo-sync` presenti.

### Skill condivisa
- [ ] Skill `stack-detector.md` presente sse almeno uno fra `code-reviewer` e `repo-sync` agenti sono presenti (skill condivisa; mai duplicata, mai assente quando serve).

## Fase 3 — Fix-up automatico (se piccoli errori meccanici)

Se qualche check fallisce per cause meccaniche (file mancante per typo, directory non
creata), tenta un fix automatico e rilancia il check. Se persiste, **STOP** e segnala
in chat con messaggio chiaro. Mai dichiarare bootstrap completato con check falliti.

## Fase 4 — Report finale

Output strutturato in chat:

```
========================================
BOOTSTRAP COMPLETATO — Agentic Factory llm-wiki++ v2.12
========================================

Progetto: <project_name>
Destinazione: <factory_dest_path>

[ALBERO CREATO]
<output di `find <factory_dest_path> -maxdepth 3 -type d`>

[CONFIGURAZIONE]
Topology: <topology>
Routing: <be: agent|human, fe: ..., ...>
Stack mode: <stack_mode>
Stack scelto: <riassunto>

[MULTI-REPO (se applicabile)]
| name | path | layers | coupling | vcs.mode |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

[FEATURE OPT-IN]
- Wiki feeding source: <empty|pdf|figma|existing-repo>
- External task tracker (kanban_publish): <provider> + target se attivo
- Parallel scheduler (v2.11): <enabled> + cap
- Code Quality Review Layer (v2.12): <enabled> + max_iterations + passate

[STATISTICHE]
- File creati: <N>
- Directory create: <M>
- Comandi VCS manuali stampati: <X>

[PROSSIMI STEP — in base alle scelte]
{condizionale, vedi sotto}

[REMINDER]
- Repo agent-agnostic. PATTERN.md è il contratto; .claude/ è l'adapter di default.
- Altri adapter (.cursor/, .openai/, ...) possono coesistere.
- {se monorepo + existing-repo}: ricorda commit dedicato per isolare l'aggiunta factory.
- {se CQRL on}: popolare code_quality/rules/canonical/ con regole per lo stack prima del primo /review.
- {se submodule presenti}: esegui i comandi `git submodule add` stampati prima di consumare TSK.
```

### Prossimi step (condizionale)

**In base a `wiki_feed_source`**:
- `empty` → drop materiale in `raw/` quando pronto, poi `/sync-docs`/`/figma-sync`/`/repo-sync` a seconda della sorgente
- `pdf` → PDF già copiati; prossimo: `/sync-docs`, poi `wiki-keeper`
- `figma` → `/figma-sync <url>`, poi `wiki-keeper`
- `existing-repo` → file `raw/*-repo-*.md` già creati; prossimo: `wiki-keeper` (batch se N ≥ 3)

**In base a `topology`**:
- `knowledge-only` → la pipeline si ferma a L2 (wiki)
- `plan-only` → dopo ingest, `product-manager` + `lead-architect` + `tpm` per TSK consumer=human
- dev-attiva → ingest + plan + design + TPM produce TSK → `/run` suggerirà `/dev <TSK-id>`
- **Con CQRL on**: dopo ogni `/dev <TSK-id>` chiuso, `/run` suggerirà `/review <TSK-id>` (o auto-dispatch nel wave plan)

## Return value

```yaml
status: success | partial | failed
checks_passed: <N> / 24
checks_failed: [<list>]
report_text: <full chat output>
```

## Vincoli inviolabili

- **Mai dichiarare completato con check falliti**: STOP + segnala.
- **Mai modifiche al repo sorgente in modalità sibling/submodule** (R.B1 verifica post-loop).
- **Output deterministico**: stessi input → stesso report.
- **Agent-agnostic preservato**: il report cita PATTERN.md e adapter, non comandi
  specifici di tool.
