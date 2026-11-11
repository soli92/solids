# Onboarding — Passi 1-4: lettura delle sorgenti

Ambito: dettaglio dei Passi 1-4 della skill `.claude/skills/onboarding.md` nel **report esteso**
(attivo con `onboarding_day0.enabled: true`). Non serve a `--compact`. Ogni passo è read-only e
non inventa dati (R.2). L'effetto di ogni assenza sullo stato finale è nella tabella Sorgenti
dichiarate di `report-errori-sorgenti.md`.

---

### Passo 1 — `CLAUDE.md` e `factory.config.yaml` → Stato factory

- **Versione factory**: `pattern_version` in `factory.config.yaml` (o riga di intestazione di `CLAUDE.md`).
- **Stack** e **`code_path`**: dalle sezioni di progetto di `CLAUDE.md` e dal blocco `vcs:` della config.
- **Agenti installati**: conta i file `*.md` in `.claude/agents/` (directory assente → 0, segnala).

`CLAUDE.md` assente → `[nota] CLAUDE.md non trovato`, contributo PARTIAL. `factory.config.yaml`
assente → contributo BLOCKED.

### Passo 2 — File di ambiente (facoltativo) → Prerequisiti

Solo se `onboarding_day0.env_file` è valorizzato: verifica la sola **presenza** del file, mai il
contenuto né il percorso completo.

```bash
test -f "<env_file>" && echo "PRESENTE" || echo "ASSENTE"
```

| Esito | Impatto sullo stato finale |
|---|---|
| PRESENTE, oppure `env_file` non configurato | nessuno |
| ASSENTE con `--check-env` | BLOCKED |
| ASSENTE senza `--check-env` | PARTIAL |

Se ASSENTE: `⚠ file di ambiente non trovato: copialo dal template e popola le variabili`.

### Passo 3 — Checklist dei prerequisiti (facoltativa)

Solo se `onboarding_day0.prerequisites_file` è valorizzato: leggi il file e riporta la checklist,
indicando per ognuno se è verificabile con `/init-check` o richiede verifica manuale. File
dichiarato ma assente → `[nota]`, contributo PARTIAL.

### Passo 4 — `management/kanban/sprint.md` → Aree attive e prossimi passi

Se `sprint.md` manca: `[nota] sprint.md non trovato`, ometti le sottosezioni che ne dipendono,
contributo PARTIAL.

- **4a. Sprint corrente**: titolo, date e conteggio TSK per `status` (`todo` / `in-progress` / `done`).
- **4b. Aree attive**: raggruppa i TSK dello sprint per prefisso di namespace dell'ID (la parte prima
  di `TSK-`; nessun prefisso = area principale). Per ciascun prefisso presente: l'ultimo TSK
  `in-progress` (ID + titolo breve), altrimenti il primo `todo` di stima più bassa. Prefissi
  assenti dallo sprint: ometti.
- **4c. US ad alta priorità**: in `management/kanban/` (prime due directory di profondità) le US con
  `status: todo` o `open` e `priority: P1`/`HIGH`/`CRITICAL`. Massimo 3: ID, titolo breve, epica.
  Nessuna → `(nessuna US ad alta priorità aperta)`.
