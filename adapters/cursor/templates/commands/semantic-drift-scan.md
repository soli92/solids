# Comando: /semantic-drift-scan

> Equivalente Cursor del comando Claude Code `/semantic-drift-scan` (`.claude/commands/semantic-drift-scan.md`).
> Procedura: vedi [semantic-drift-scan-protocol](mdc:.cursor/rules/skills/semantic-drift-scan-protocol.mdc).

**Sintassi**: `/semantic-drift-scan`

> **Comando sperimentale EP-031 (US-108). Trigger manuale — mai automatico. Non e' un gate di pipeline.**

> **Gate**: `factory.config.yaml.wiki_lint.semantic_check.enabled: true`. Se `false` → STOP esplicito.

## Comportamento

Esegue [semantic-drift-scan-protocol](mdc:.cursor/rules/skills/semantic-drift-scan-protocol.mdc) 5 step:

1. **Bootstrap check**: verifica `enabled: true` + raggiungibilita' API embedding.
2. **Discovery**: scansiona `wiki/**/*.md` con `pattern_section:` nel frontmatter. Stima costo totale.
3. **Gate costo**: se costo stimato > `cost_warn_usd` (default $1.00) → STOP con stima, chiede conferma.
4. **Calcolo embedding**: per ogni pagina candidata, cosine similarity tra pagina e sezione `PATTERN.md`.
5. **Report**: scrive `<output_report_path>/wiki-lint-semantic-YYYY-MM-DD.md` + append `wiki/log.md`.

## Output

- File: `code_quality/reports/wiki-lint-semantic-YYYY-MM-DD.md`
- Sezioni: Sommario, Top 5 pagine a rischio, tabella completa sotto soglia, non scansionate, raccomandazioni.

## Vincoli

- **Solo INFO**: non altera `status:` di TSK/US/EP, non produce ERROR/WARNING di lint.
- **Sperimentale**: soglia 0.75 richiede calibrazione empirica. Risultati = segnali, non verdetti.
- **No auto-trigger**: mai invocato da `/run`, scheduler, CI/CD.

## Limitazioni Cursor

- L'API embedding richiede `ANTHROPIC_API_KEY` o `OPENAI_API_KEY` settata nel terminal.
- Eseguire via terminal Cursor: `python3 tools/wiki-lint/semantic-drift-scan.py` se lo script esiste.
- In assenza dello script: eseguire la [semantic-drift-scan-protocol](mdc:.cursor/rules/skills/semantic-drift-scan-protocol.mdc) manualmente step by step.
