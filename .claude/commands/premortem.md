---
description: Esegue una premortem strutturata (analisi del rischio via prospective hindsight) su un piano o artefatto. PATTERN §3 operazione opzionale v2.16. Accetta 3 input shape (artefatto kanban / pagina wiki / descrizione libera). Invoca la skill premortem-protocol. Opt-in totale, R.P1 (output mai auto-applicato).
argument-hint: <descrizione | EP-XXX | US-YYY | TSK-ZZZ | wiki-page-path> [--timeframe=Nw|Nmo|Ny]
---

# /premortem — Analisi del rischio via prospective hindsight (PATTERN §3, v2.16)

Argomenti utente: `$ARGUMENTS`

Comando opzionale **opt-in** introdotto in v2.16 (PATTERN §3 operazione
opzionale, non parte del cascade L1→L5). Entry-point unico per invocare la
skill [premortem-protocol](mdc:.cursor/skills/premortem-protocol/SKILL.md) su
un target alto-impatto.

Riferimenti: [[premortem-skill]], [[risk-classification-tigers-paper-tigers-elephants]],
[[factory-premortem-integration]] (design doc), ADR-001..ADR-007.

## Sintassi

```
/premortem <descrizione>             → input shape: descrizione-libera
/premortem EP-XXX                    → input shape: artefatto-kanban (epica)
/premortem US-YYY                    → input shape: artefatto-kanban (user story)
/premortem TSK-ZZZ                   → input shape: artefatto-kanban (task)
/premortem wiki/<path>.md            → input shape: pagina-wiki
/premortem <X> --timeframe=12mo      → override del timeframe default
```

## Argument parsing (ordine di match deterministico)

Il parser applica i pattern in ordine. Il **primo match** vince. Ogni pattern
selezionato determina la strategia di caricamento contesto della skill (Fase 1
Context Gathering).

| # | Pattern (regex) | Input shape | Strategia caricamento contesto |
|---|---|---|---|
| 1 | `^(EP\|US\|TSK)-\d{3}$` | **artefatto-kanban** | EP padre + sibling US/TSK + design doc associati. Glob `management/kanban/**/<ID>.md` |
| 2 | `^wiki/.*\.md$` (path esistente) | **pagina-wiki** | La pagina + wikilinked 1-hop + `sources:` frontmatter. Glob `wiki/<path>` |
| 3 | qualsiasi stringa libera | **descrizione-libera** | `wiki/index.md` + `memory/episodic/` ultimi 10 entry |

Esempi:

```
/premortem EP-001
  → input shape: artefatto-kanban
  → carica: EP-001.md + US-001..005 + design doc proposta-premortem-integration-v216.md

/premortem TSK-018
  → input shape: artefatto-kanban
  → carica: TSK-018.md + US-016 padre + EP-004 padre + sibling TSK-019

/premortem wiki/concepts/factory-premortem-integration.md
  → input shape: pagina-wiki
  → carica: la pagina + wikilink di 1 hop (premortem-skill, risk-classification, ...)
    + sources (raw/premortem-skill-claude.md)

/premortem "stiamo per migrare da Postgres 15 a 17"
  → input shape: descrizione-libera
  → carica: wiki/index.md (per orientamento) + memory/episodic ultimi 10 entry
```

Se il primo argomento non matcha nessuno dei pattern 1-2 e contiene almeno una
parola, fallback automatico a **descrizione-libera** (pattern 3).

## Flag supportato: `--timeframe=<N>{w|mo|y}`

Override del timeframe default della Fase 2 («È [N mesi] da oggi. Questo
piano è fallito.»). Senza flag, il timeframe è inferito dal tipo di target
secondo la tabella standard della skill:

| Tipo target | Default timeframe |
|---|---|
| `TSK-ZZZ` | 2-4 settimane |
| `US-YYY` | 1-3 mesi |
| `EP-XXX` | 6 mesi |
| pagina wiki concept | 6 mesi |
| descrizione libera | 6 mesi (fallback) |
| PATTERN bump major / R.K1-type | 12-18 mesi |

Esempi override:

```
/premortem TSK-014 --timeframe=6mo    # forza orizzonte semestrale (default 2-4w)
/premortem EP-001 --timeframe=18mo    # decisione a lungo termine (default 6mo)
/premortem "v3.0 PATTERN bump major" --timeframe=24mo
```

Formato accettato: `Nw` (settimane), `Nmo` (mesi), `Ny` (anni). Esempi
validi: `2w`, `4w`, `6mo`, `12mo`, `2y`. Esempi non validi (segnalati con
errore): `2m` (ambiguo), `12months` (verbose).

## Procedura

1. **Parse argomenti**
   - Estrai `$ARGUMENTS`.
   - Cerca flag `--timeframe=<X>` (opzionale, rimuovi dalla stringa input).
   - Applica i 3 pattern in ordine sulla stringa residua, determina input shape.
   - Se input shape = `pagina-wiki` ma il path non esiste → STOP con errore.
   - Se input shape = `artefatto-kanban` ma `glob management/kanban/**/<ID>.md`
     restituisce 0 match → STOP con errore.

2. **Invoca skill [premortem-protocol](mdc:.cursor/skills/premortem-protocol/SKILL.md)**
   - Passa alla skill: input shape selezionato, target (string), timeframe
     (esplicito o inferito).
   - La skill esegue le 5 fasi in sequenza (Context Gathering → Frame Setting
     → Raw Premortem → Parallel Deep-Dives → Sintesi).
   - **Single entry-point**: tutta la logica implementativa vive nella skill.
     Il comando è puro dispatcher.

3. **Output al chiamante**
   - Risk Registry inline in chat (Tigers/Paper Tigers/Elephants con
     urgency).
   - Revised Plan (3-7 azioni concrete, **suggerimenti** — vedi R.P1 sotto).
   - Pre-Launch Checklist (3-5 item actionable, **suggerimenti**).
   - Eventuale suggerimento di edit frontmatter `risk_classification:` sul
     target (mai applicato in autonomia — R.P1).

4. **Side-effect canonico**
   - Append a `wiki/log.md` con formato:

     ```
     [YYYY-MM-DD HH:MM] premortem — <target> → <N> risks (T:<X> LB:<a> FF:<b> Tr:<c> PT:<Y> E:<Z>) — files touched: <M>
     ```

     Esempio:

     ```
     [2026-05-29 16:00] premortem — EP-001 → 12 risks (T:7 LB:2 FF:3 Tr:2 PT:3 E:2) — files touched: 1
     ```

   - Append metadata only (timestamp, target, tier counts) a
     `memory/episodic/premortem-runs.md` per telemetria evolutiva (ADR-006).
   - Se l'utente conferma esplicitamente, append a `management/risk-registry.md`
     (opt-in, vedi TSK-012 per template). Niente auto-creazione (R.P1).

## Self-restriction R.P1 — Output mai auto-applicato

**Vincolo non-overridabile** del comando: il `revised_plan` e la
`pre-launch checklist` prodotti dalla Fase 5 della skill sono **sempre**
suggerimenti per l'utente. Il comando **non modifica** in autonomia:

- il body di EP/US/TSK target (R.7 PATTERN: update non-distruttivo);
- il frontmatter del target (proposte di edit `risk_classification:` sono
  emesse in chat come suggerimenti, ma mai scritte direttamente);
- nessun file di filesystem oltre i 2 side-effect canonici (`wiki/log.md` +
  `memory/episodic/premortem-runs.md`).

Se vuoi applicare i suggerimenti del Revised Plan al target, fai gli edit
manualmente (o invoca esplicitamente il PM o il dev-agent appropriato).

## Casi d'uso tipici

| Scenario | Esempio invocazione | Note |
|---|---|---|
| Stress-test di un'epica prima del promote draft → review | `/premortem EP-042` | Suggerito dal PM nei suoi gate. Default 6mo |
| Stress-test di un design doc prima di scrivere TSK | `/premortem wiki/concepts/factory-X.md` | Suggerito dall'Arch sui touchpoint cross-cutting |
| Stress-test di un PATTERN bump major | `/premortem "v3.0 — rimozione retro-compat su §2 ruoli"` | Strategia ad alto rischio. `--timeframe=18mo` consigliato |
| Stress-test di un singolo TSK ad alta criticità | `/premortem TSK-018 --timeframe=6mo` | Es. self-premortem dogfooding pre-release |
| Stress-test di una decisione tecnica esterna (no artefatto) | `/premortem "migrare da Postgres 15 a 17 entro Q2"` | Descrizione libera, contesto minimo |

## Vincoli

- **Mai trigger automatico** su parole chiave nel chat (ADR-003 ha scartato
  phrase-trigger v2.16). Solo `/premortem` esplicito.
- **R.P2 — bar minimo del contesto**: la skill stoppa con domande chiarificatrici
  se Fase 1 non soddisfa il bar (cosa stai facendo / per chi / come appare il
  successo). Non procedere su contesto insufficiente — produce output sanitizzato.
- **R.P3 — opt-in totale**: factory che non ha scaffoldato la skill
  `premortem-protocol` vede questo comando ma riceve errore «skill non
  installata, vedi factory-premortem-integration §Migration».
- **Niente bidirectional con CQRL**: la premortem è pre-fact, CQRL è post-fact.
  Se vuoi premortem on-merge del codice, usa il pass opzionale
  `premortem-on-merge` del CQRL (ADR-005, opt-in default off).

## Test manuali rapidi

Per verifica funzionale post-installazione:

```
# Test 1 — artefatto-kanban (esiste)
/premortem EP-001
  ATTESO: carica EP-001 + US-001..005 + design doc; produce Risk Registry mix calibrato

# Test 2 — pagina-wiki (esiste)
/premortem wiki/concepts/factory-premortem-integration.md
  ATTESO: carica la pagina + wikilink 1-hop (premortem-skill, risk-classification);
          produce Risk Registry calibrato

# Test 3 — descrizione-libera
/premortem "qualcosa di ambiguo che vogliamo stress-testare"
  ATTESO: fallback a descrizione-libera; carica index.md + episodic; bar minimo
          probabilmente non soddisfatto → fail-loud R.P2 con 1 domanda

# Test 4 — override timeframe
/premortem TSK-018 --timeframe=6mo
  ATTESO: applica 6mo invece dei 2-4w default per TSK; visibile nella frase Fase 2

# Test 5 — input shape inesistente
/premortem wiki/inesistente.md
  ATTESO: STOP con errore esplicito (path non trovato)
```

## Riferimenti

- Skill implementativa: [premortem-protocol](mdc:.cursor/skills/premortem-protocol/SKILL.md) (TSK-001)
- Design doc completo: [wiki/concepts/factory-premortem-integration.md](../../wiki/concepts/factory-premortem-integration.md)
- ADR-003: argomento `/premortem` esplicito, no phrase-trigger
- ADR-006: telemetria → `memory/episodic/premortem-runs.md`
- PATTERN §3 (operazione opzionale), §5 (frontmatter opt-in `risk_classification:`),
  §7 (R.P1-R.P3 non sono regole §7, vivono nella skill).
