---
id: content-share-setup
type: runbook
title: "Content Share — Setup capability nelle factory derivate (EP-048)"
status: current
created: 2026-07-17
updated: 2026-07-17
sources:
  - "raw/content-share-integration-spec.md (SPEC-001)"
  - "wiki/sources/soli-frames-integration.md"
  - "management/kanban/EP-048-content-share-consumer-layer/US-176-content-share-core/TSK-399.md"
  - "wiki/decisions/tavola-rotonda-e9d3b7f1-2c4a-4e8b-9f6d-3a5c7b1e2f8d-2026-07-17.md (A4/A8/A10)"
related:
  - content-share-hub-pattern
  - soli-frames
  - soli-frames-integration
tags: [content-share, runbook, setup, ep-048, pat, security, soli-frames]
pattern_section: "§32"
---

# Content Share — Setup capability nelle factory derivate

> Runbook operativo per abilitare la capability `content-share` (EP-048, v2.33 opt-in)
> in una factory derivata. Copre: creazione PAT fine-grained, configurazione
> `factory.config.yaml`, aggiunta secret al repo e verifica end-to-end.
>
> Per il contratto di dispatch e l'architettura del hub vedere
> [[content-share-hub-pattern]] (`wiki/concepts/content-share-hub-pattern.md`).
> Per i dettagli tecnici dell'integrazione soli-frames vedere
> [[soli-frames-integration]] (`wiki/sources/soli-frames-integration.md`).

---

## Prerequisiti

Prima di procedere verificare che siano soddisfatte tutte le condizioni:

| Prerequisito | Verifica |
|---|---|
| `gh` CLI installata e autenticata | `gh auth status` deve restituire `Logged in to github.com` |
| Account membro dell'organizzazione `soli92` | Visibile su https://github.com/orgs/soli92/members |
| `SOLI_FRAMES_DISPATCH_SECRET` disponibile come org secret in `soli92` | Verificabile via `gh secret list --org soli92` (richiede permessi org) |
| Repository della factory esistente su `github.com/soli92/<repo>` | Necessario per impostare i secret del repo |
| `factory.config.yaml` con blocco `content_share:` presente | Scaffoldato da TSK-398; se assente, applicare prima TSK-398 |

> **Nota**: se la factory risiede fuori dall'organizzazione `soli92`, il secret
> `SOLI_FRAMES_DISPATCH_SECRET` non viene ereditato automaticamente dall'org.
> In questo caso seguire la sezione §4 per impostarlo manualmente.

---

## §1 — Distinzione tra i due secret

La capability richiede **due secret con ruoli completamente diversi**. Confonderli
causa errori silenziosi (dispatch accettato ma contenuto rifiutato, o 401 sull'API).

| Secret | Nome env | Ruolo | Scope |
|---|---|---|---|
| `SOLI_FRAMES_PAT` | `pat_env` in config | **Autentica la POST all'API GitHub** — va nell'header `Authorization: Bearer <token>` della chiamata a `repos/soli92/soli-frames/dispatches` | PAT fine-grained con `Contents: write` su `soli92/soli-frames` SOLO |
| `SOLI_FRAMES_DISPATCH_SECRET` | `secret_env` in config | **Autentica il dispatch** — viene passato come campo `dispatch_secret` nel payload JSON; soli-frames lo confronta con `CONTENT_DISPATCH_SECRET` per accettare o rifiutare l'ingest | Valore noto all'hub soli-frames; non ha scope GitHub — e' una stringa condivisa |

`SOLI_FRAMES_PAT` e' **per-progetto** (PAT legato all'account del maintainer della factory,
con scope minimo, non org secret). La revoca e' chirurgica: revocare il PAT di un progetto
non impatta le altre factory.

`SOLI_FRAMES_DISPATCH_SECRET` e' tipicamente un **org secret** `soli92` e viene ereditato
automaticamente dai repo dell'organizzazione. Se la factory e' in un repo privato fuori
dall'org, va impostato manualmente (vedi §4).

---

## §2 — Creazione del PAT fine-grained

### 2.1 — Perche' PAT fine-grained e non PAT classic

Un PAT classic con scope `repo` ha accesso in scrittura a **tutti i repository
dell'account**. Se compromesso, un attaccante puo' modificare qualsiasi repo della
flotta factory. Un PAT fine-grained con scope `Contents: write` su `soli92/soli-frames`
SOLO limita il blast radius: in caso di compromissione, solo quel repo e' a rischio.

**Regola**: NON usare un PAT classic con scope `repo` per questa capability.

### 2.2 — Procedura di creazione

1. Andare su https://github.com/settings/personal-access-tokens/new
2. Compilare i campi:
   - **Token name**: `soli-frames-dispatch-<progetto>` (es. `soli-frames-dispatch-soli-prof`)
   - **Expiration**: 90 giorni (allineare con la policy di rotazione §6)
   - **Resource owner**: `soli92` (l'organizzazione che ospita `soli-frames`)
3. Nella sezione **Repository access**: selezionare "Only select repositories"
   e scegliere **esclusivamente** `soli92/soli-frames`
4. Nella sezione **Permissions** espandere **Repository permissions** e impostare:
   - `Contents`: **Read and write**
   - Tutti gli altri permessi: lasciare a "No access"
5. Cliccare **Generate token** e copiare immediatamente il valore (non sara' piu' visibile)

> Il permesso `Contents: write` consente la POST all'endpoint
> `repos/soli92/soli-frames/dispatches` (GitHub Repository Dispatch API).
> Non concede accesso ad altri endpoint ne' ad altri repository.

---

## §3 — Configurazione factory.config.yaml

Aprire `factory.config.yaml` del progetto e compilare il blocco `content_share:`
(scaffoldato da TSK-398 con tutti i campi a default):

```yaml
content_share:
  enabled: true                               # attivare dopo aver completato §2 e §4
  target_repo: "soli92/soli-frames"
  source_repo_slug: "soli-prof"              # COMPILARE: slug kebab-case del repo corrente
  source_repo: "soli92/soli-prof"            # COMPILARE: org/repo del repo corrente
  pat_env: SOLI_FRAMES_PAT                   # PAT fine-grained (Contents:write su soli-frames)
  secret_env: SOLI_FRAMES_DISPATCH_SECRET
  publish_default: draft                      # sicuro: mai publish automatico (R.CS3)
  size_limit_kb: 100                          # hard limit HTML decoded (default fino a US-024)
  size_warn_kb: 80
  artifact_categories:
    prototype: true
    analytics_report: true
    custom: true
```

**Campi obbligatori da compilare** (non auto-derivati — decisione TR A8):

- `source_repo_slug`: lo slug kebab-case del repository della factory corrente.
  Esempio: se il repo e' `soli92/soli-prof`, il valore e' `"soli-prof"`.
  Questo slug viene usato come prefisso obbligatorio dei `slug` dei contenuti
  pubblicati (invariante R.CS1: `{source_repo_slug}-{content_slug}`).
- `source_repo`: il riferimento completo `org/repo` del repository della factory.
  Viene scritto nel campo `source.sourceRepo` del manifest soli-frames per tracciabilita'.

> **Perche' espliciti e non auto-derivati**: la factory puo' girare in ambienti
> con `GITHUB_REPOSITORY` non disponibile (locale, CI non-GitHub). La dichiarazione
> esplicita rende il valore stabile e auditabile (accordo TR A8).

---

## §4 — Aggiunta dei secret al repository

Nella directory radice del repository della factory eseguire:

```bash
# PAT fine-grained creato in §2 — specifico per questa factory
gh secret set SOLI_FRAMES_PAT
# Incollare il valore del PAT quando richiesto (input mascherato)

# Dispatch secret — valore gia' noto all'hub soli-frames
gh secret set SOLI_FRAMES_DISPATCH_SECRET
# Incollare il valore quando richiesto
```

**Nota su `SOLI_FRAMES_DISPATCH_SECRET`**:
- Se il repository della factory e' sotto l'organizzazione `soli92` e l'org secret
  `SOLI_FRAMES_DISPATCH_SECRET` e' gia' configurato, potrebbe essere ereditato
  automaticamente. Verificare con `gh secret list` (se il secret non compare,
  e' necessario impostarlo manualmente come sopra).
- Il valore di `SOLI_FRAMES_DISPATCH_SECRET` si ottiene dal maintainer dell'hub
  soli-frames o dall'org secret `soli92`. Non va generato: e' un segreto condiviso
  pre-configurato sull'hub.

Verificare che i secret siano presenti:

```bash
gh secret list
# Output atteso: SOLI_FRAMES_PAT e SOLI_FRAMES_DISPATCH_SECRET visibili nella lista
```

---

## §5 — Verifica

Eseguire una verifica dry-run prima del primo dispatch reale:

```bash
/share --dry-run tests/content-share/fixtures/small.html
```

Output atteso in caso di configurazione corretta:

```
[content-share] Fase 0 — EGRESS classification
  file: tests/content-share/fixtures/small.html
  size: 4.2 KB (limit 100 KB) — OK
  egress_class: EGRESS_PASS
  slug-candidate: soli-prof-small  (prefisso: soli-prof)

[content-share] --dry-run: gate umano non visualizzato (nessun dispatch)
  Configurazione: OK
  PAT env (SOLI_FRAMES_PAT): presente
  Secret env (SOLI_FRAMES_DISPATCH_SECRET): presente
  target_repo: soli92/soli-frames
  source_repo: soli92/soli-prof
```

**Condizioni di errore comuni**:

| Sintomo | Causa | Soluzione |
|---|---|---|
| `EGRESS_BLOCK — size > 100 KB` | File HTML troppo grande | Ridurre le dimensioni del file o attendere US-024 per il limite 512 KB |
| `PAT env non trovato` | Secret `SOLI_FRAMES_PAT` non impostato | Ripetere §4 |
| `source_repo_slug vuoto` | Campo non compilato in config | Compilare `source_repo_slug` in `factory.config.yaml` |
| `401 Unauthorized` in dispatch reale | PAT scaduto o scope insufficiente | Rigenerare il PAT con scope `Contents: write` su `soli-frames` |
| `dispatch_secret non valido` in GHA log | Valore errato di `SOLI_FRAMES_DISPATCH_SECRET` | Verificare il valore con il maintainer soli-frames |

**Prima del dispatch reale** — il comando `/share <html-path>` senza `--dry-run`
presenta sempre un gate umano (R.CS3) che richiede conferma esplicita prima di
inviare il payload. Leggere attentamente il riepilogo proposto (slug, title, size,
target) prima di confermare.

---

## §6 — Sicurezza e rotazione dei secret

### 6.1 — Policy di rotazione

| Secret | Frequenza di rotazione | Responsabile |
|---|---|---|
| `SOLI_FRAMES_PAT` | **≤ 90 giorni** (impostare la scadenza in fase di creazione) | Maintainer della factory |
| `SOLI_FRAMES_DISPATCH_SECRET` | Su richiesta del maintainer hub soli-frames | Maintainer soli-frames (coordina con le factory) |

Per non perdere track della scadenza: al momento della creazione del PAT, aggiungere
un promemoria nel proprio calendario a 80 giorni (10 giorni di anticipo rispetto
alla scadenza di 90 giorni).

### 6.2 — Procedura di rotazione di SOLI_FRAMES_PAT

1. Andare su https://github.com/settings/personal-access-tokens
2. Trovare il token `soli-frames-dispatch-<progetto>` e cliccare **Regenerate**
   (o **Delete** + creare un nuovo token da §2)
3. Copiare il nuovo valore
4. Aggiornare il secret nel repository della factory:
   ```bash
   gh secret set SOLI_FRAMES_PAT
   # Incollare il nuovo valore
   ```
5. Verificare con `/share --dry-run tests/content-share/fixtures/small.html`

### 6.3 — Procedura di revoca immediata (compromissione)

Se il PAT `SOLI_FRAMES_PAT` e' stato esposto accidentalmente (log, commit, chat):

1. **Revocare immediatamente** su https://github.com/settings/tokens
   (o https://github.com/settings/personal-access-tokens per i fine-grained)
2. Verificare i dispatch recenti su https://github.com/soli92/soli-frames/actions
   per rilevare eventuali usi non autorizzati
3. Segnalare l'incidente al maintainer soli-frames per verifica del manifest
4. Rigenerare un nuovo PAT da §2 e aggiornare il secret del repo da §4

> Se il PAT revocato era condiviso tra piu' progetti (pratica sconsigliata),
> aggiornare i secret di tutti i repository coinvolti.

Se `SOLI_FRAMES_DISPATCH_SECRET` e' stato esposto, contattare il maintainer
soli-frames: la rotazione del dispatch secret richiede aggiornamento coordinato
sia sull'hub che su tutte le factory consumatrici.

### 6.4 — Principi di sicurezza

- **Non inserire i secret nel codice sorgente** o nei file di configurazione
  versionati. Usare esclusivamente i secret del repository GitHub.
- **Non condividere il PAT tra piu' factory**: se un progetto viene compromesso,
  la revoca del suo PAT non impatta le altre factory.
- **Non usare PAT classic con scope `repo`**: il blast radius in caso di
  compromissione include tutti i repository dell'account.
- **Non loggare i valori dei secret** negli script di dispatch. Il workflow
  GHA di soli-frames non logga il payload; le factory devono seguire la stessa
  policy nei propri script.

---

## §7 — Riferimenti correlati

- [[content-share-hub-pattern]] — `wiki/concepts/content-share-hub-pattern.md`:
  architettura del pattern hub, pipeline dispatch→GHA→PR→Vercel, invarianti R.CS1-R.CS4
- [[soli-frames]] — `wiki/entities/soli-frames.md`:
  entita' soli-frames, feature status US-021..025, URL viewer di produzione
- [[soli-frames-integration]] — `wiki/sources/soli-frames-integration.md`:
  contratto pubblico di integrazione (INTEGRATION.md US-025), payload schema completo,
  esempi shell, risposta attesa 204 No Content
