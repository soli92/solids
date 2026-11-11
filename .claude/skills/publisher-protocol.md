---
name: publisher-protocol
description: Protocollo provider-agnostic per i Publisher (PATTERN §17, v2.10). 5 fasi (Bootstrap → Discovery → Plan/Gate → Publish → Log). Invoca una skill PROVIDER-mapping per la traduzione concreta.
---
# Protocollo Publisher (provider-agnostic)

Riferimenti: PATTERN §17 (Publisher adapters), §8 (single source of truth),
§7 r.15 (gate cross-tool), `citation-rules`, `wiki-log-entry`.

Questa skill è **provider-agnostic**: definisce le 5 fasi che ogni
`<provider>-publisher` deve seguire. La traduzione concreta (EP→Milestone,
US→Issue, …) vive in una skill provider-specific `<provider>-mapping`
(es. `github-mapping`).

## Prerequisiti

- `factory.config.yaml.kanban_publish.provider` valorizzato (≠ `none`).
- `target`, `auth_env`, `mapping`, `labels`, `filter` valorizzati.
- Variabile d'ambiente `<auth_env>` settata oppure l'autenticazione del
  provider è già configurata (es. `gh auth status` ritorna OK).
- Il sub-agent invocante (`<provider>-publisher`) DEVE corrispondere a
  `kanban_publish.provider`. Mismatch → ABORT in Fase 1.

## Fase 1 — Bootstrap

- Read `factory.config.yaml.kanban_publish` completo.
- Verifica:
  - `provider` ≠ `none` e ∈ providers supportati (lista in `lint-checks` Check 4f).
  - `target` non vuoto.
  - `auth_env` definita; variabile d'ambiente presente (test via env shell).
    Se assente, ABORT con messaggio: «Setta `<auth_env>` e riprova».
  - Mapping coerente (es. per GitHub: `epic_to ∈ {milestone, issue-label, project-column}`).
- Invoca la sub-skill `<provider>-mapping §Auth check` (es. `gh auth status`
  per GitHub) per verifica end-to-end. ABORT se l'auth fallisce.
- Read ultimo `memory/episodic/*.md` per continuità con run precedente
  (eventuale state di publishing parziale, e.g. interrotto).

## Fase 2 — Discovery

- `Glob management/kanban/EP-*/EP-*.md` → lista epiche.
- `Glob management/kanban/EP-*/US-*/US-*.md` → lista storie.
- `Glob management/kanban/EP-*/US-*/TSK-*.md` → lista task.
- (Opzionale) Read `management/kanban/sprint.md` per mapping `sprint_to`.
- Applica `kanban_publish.filter`:
  - `only_consumer`: skip TSK con `consumer` non corrispondente.
  - `only_status`: skip artefatti con `status` non corrispondente.
- Per ogni artefatto: estrai frontmatter + body. Determina **azione**:
  - `external_id:` assente o vuoto → **CREATE**.
  - `external_id:` con prefisso `<provider>:` → **UPDATE**.
  - `external_id:` con prefisso diverso (altro provider) → **SKIP**
    (conflitto cross-provider; segnala in chat).

## Fase 3 — Plan & Gate (STOP, PATTERN §7 r.15)

Mostra in chat:

```
PIANO PUBBLICAZIONE (provider: <name>, target: <target>)
========================================================
CREATE:
  - EP×<N1>  (esempi: EP-001 "Auth", EP-005 "Reporting")
  - US×<N2>
  - TSK×<N3>
UPDATE:
  - EP×<M1>  (ri-publish per cambio body/label/milestone)
  - US×<M2>
  - TSK×<M3>
SKIP (conflitto cross-provider):
  - <N4>  (lista <file>: <external_id esistente>)
SKIP (filter):
  - <N5>  (lista <file>: <reason>)

Totale operazioni: <N1+N2+N3+M1+M2+M3>
Batch limit (factory.config): <batch_limit>

Procedo? [y/N]
```

**Attendi conferma esplicita** (§7 r.15).

Se `totale > batch_limit`:

```
ATTENZIONE: totale operazioni (<X>) > batch_limit (<batch_limit>).
Conferma SECONDARIA richiesta (digita "publish <X>" per procedere).
```

**Attendi conferma secondaria letterale**. Se assente → ABORT.

Se l'utente vuole filtrare (es. «solo EP, niente TSK»), accetta un override
puntuale prima di procedere.

## Fase 4 — Publish

Per ogni artefatto nel piano confermato:

1. Invoca la sub-skill `<provider>-mapping §Build payload` per produrre il
   payload provider-specific (es. `gh issue create --title ... --body ...`
   per GitHub).
2. Invoca `<provider>-mapping §Execute` per CREATE/UPDATE concreto.
3. Cattura l'identifier ritornato dal provider (issue number, key, UUID, …).
4. **Edit** del frontmatter locale dell'artefatto:
   - Aggiorna `external_id: <provider>:<id>` (mai del corpo).
   - Aggiorna `updated:` con ISO-8601 timestamp corrente.
   - Mai modificare altri campi del frontmatter (`id`, `status`, `layer`,
     `consumer`, `priority`, `estimate`, ecc. restano di proprietà PM/TPM/Dev).
5. Log a chat (1 riga per artefatto):
   ```
   [14:32:01] CREATE EP-001 → <provider>:<id> <url>
   [14:32:03] UPDATE TSK-014 → <provider>:<id> (already linked)
   [14:32:05] SKIP   EP-007  (external_id: jira:PROJ-89 — conflitto cross-provider)
   ```

Errori transitori (network, rate limit): retry max 2 con backoff esponenziale
(base 1500ms). Errore non recuperabile → mark `status: error` nel piano in
memoria, NON cambia il frontmatter locale, continua con il prossimo artefatto.

## Fase 5 — Log entry (OBBLIGATORIA)

Append una sola entry a `wiki/log.md` (template `publish`, vedi `wiki-log-entry`):

```markdown
## 2026-05-22 14:35 — publish github (created=5, updated=12)
**Operatore:** github-publisher
**Provider:** github @ soli92/customer-portal
**Operazioni:**
- CREATE: EP-001, EP-005, US-010, US-011, TSK-014
- UPDATE: EP-002, EP-003, EP-004, US-001..US-009, TSK-001..TSK-003
- SKIP cross-provider: EP-007 (jira:PROJ-89)
- ERROR: TSK-020 (HTTP 422 — title vuoto, da indagare)
**Link al provider:** https://github.com/soli92/customer-portal/issues
```

Riepilogo finale a chat: count operazioni + link al provider + suggerimento
prossimo step («Verifica gli issue creati sul provider; aggiorna `status:`
locale quando li sposti su in-progress/done»).

## Regole anti-corner-case

- **File kanban senza frontmatter completo**: SKIP con WARNING (richiede lint
  pre-publish, vedi `lint-checks` Check 3).
- **Provider down / 5xx persistente**: ABORT dopo 3 retry consecutivi falliti.
  Stato parziale già committato sui frontmatter è OK (idempotente: re-run
  ripartirà da dove si è fermato grazie a `external_id:` già scritto sui
  successful CREATE).
- **Token scaduto / 401**: ABORT immediato Fase 1 (auth check). Suggerisci di
  rinnovare il token.
- **Target inesistente / 404**: ABORT Fase 1. Suggerisci di verificare
  `factory.config.yaml.kanban_publish.target`.
- **Body troppo lungo per il provider** (es. GitHub limit ~65k caratteri):
  troncamento con marker `\n\n---\n[Body troncato — vedi file locale]\n` +
  WARNING in log. **Mai** silenziosamente perdere informazione.
- **Re-publish di un artefatto già pubblicato con `external_id:` mancante sul
  provider** (es. issue cancellata a mano): rileva il 404 sull'UPDATE,
  cancella `external_id:` locale, ricade in CREATE al prossimo run (e segnala
  in chat).

## Non in scope per publisher-protocol

- Decidere quali EP/US/TSK creare a livello di prodotto: questo è scope PM/TPM.
- Modificare il body dei file locali per allinearli a quello che vorresti sul
  provider: il body locale è source-of-truth (§8). Se non ti piace come si
  vede su GitHub, riscrivi il file locale; il prossimo publish lo
  sincronizzerà.
- Sincronizzare commenti, reaction, assignee, project board column,
  custom field: out-of-scope di v2.10 (solo body, label, milestone, title).
- Bidirectional `status:` (issue chiusa → TSK done): candidato v2.11.
