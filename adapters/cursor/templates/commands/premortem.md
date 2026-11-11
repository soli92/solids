# Comando: /premortem

> Equivalente Cursor del comando Claude Code `/premortem` (`.claude/commands/premortem.md`).
> Procedura: vedi [premortem-protocol](mdc:.cursor/rules/skills/premortem-protocol.mdc).

**Sintassi**:
```
/premortem <descrizione>        → input shape: descrizione-libera
/premortem EP-XXX               → input shape: artefatto-kanban (epica)
/premortem US-YYY               → input shape: artefatto-kanban (user story)
/premortem TSK-ZZZ              → input shape: artefatto-kanban (task)
/premortem wiki/<path>.md       → input shape: pagina-wiki
/premortem <X> --timeframe=12mo → override timeframe default
```

**Mai trigger automatico**: solo `/premortem` esplicito. R.P1 — output mai auto-applicato.

## Argument parsing (deterministico)

| # | Pattern | Input shape | Caricamento contesto |
|---|---|---|---|
| 1 | `^(EP|US|TSK)-\d{3}$` | artefatto-kanban | EP padre + sibling US/TSK + design doc |
| 2 | `^wiki/.*\.md$` (esiste) | pagina-wiki | pagina + wikilink 1-hop + `sources:` frontmatter |
| 3 | stringa libera | descrizione-libera | `wiki/index.md` + `memory/episodic/` ultimi 10 entry |

## Flag `--timeframe=<N>{w|mo|y}`

Default per tipo: TSK 2-4w, US 1-3mo, EP 6mo, wiki 6mo, descrizione-libera 6mo.

Esempi: `--timeframe=6mo`, `--timeframe=2w`, `--timeframe=18mo`.

## Procedura

1. Parse argomenti + determina input shape.
2. Esegue [premortem-protocol](mdc:.cursor/rules/skills/premortem-protocol.mdc) 5 fasi (Context Gathering → Frame Setting → Raw Premortem → Deep-Dives → Sintesi).
3. Output Risk Registry (Tigers/Paper Tigers/Elephants) + Revised Plan + Pre-Launch Checklist inline in chat.
4. Side-effect: append `wiki/log.md` + append `memory/episodic/premortem-runs.md`.
5. Se utente conferma → append `management/risk-registry.md` (opt-in, mai automatico).

## Vincoli (R.P1-R.P3)

- **R.P1**: il Revised Plan e' sempre un **suggerimento** — mai auto-applicato.
- **R.P2**: la skill stoppa con domande chiarificatrici se il contesto non e' sufficiente.
- **R.P3**: opt-in totale, mai trigger automatico.

## Limitazioni Cursor

- Le 5 fasi di [premortem-protocol](mdc:.cursor/rules/skills/premortem-protocol.mdc) vanno eseguite sequenzialmente.
- Deep-Dives (Fase 4) per failure mode H+H: eseguire come sotto-sessioni separate se il contesto e' molto lungo.
