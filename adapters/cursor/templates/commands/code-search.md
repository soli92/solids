# Comando: /code-search

> Equivalente Cursor del comando Claude Code `/code-search` (`.claude/commands/code-search.md`).
> Ricerca semantica L2 su indice codice symbol-level (EP-054, PATTERN §33.3). Richiede code_intelligence.l2_semantic.enabled: true.

> Procedura: [code-chunk-protocol](mdc:.cursor/rules/skills/code-chunk-protocol.mdc)

> **Gate**: `factory.config.yaml.code_intelligence.l2_semantic.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/code-search <query>                              # ricerca semantica (top 5 default)
/code-search <query> --top=<N>                   # top N risultati (max 20)
/code-search <query> --lang=<language>           # filtra per linguaggio (python|typescript|java|go|rust)
/code-search <query> --type=<type>               # filtra per tipo (function|class|interface|method|struct)
/code-search <query> --all                       # merge con wiki_search (RRF)
/code-search reindex [--full] [--slug=<name>]    # ricostruisce indice
```

## Limitazioni Cursor

- L2 e L3 dipendono da tool esterni (LanceDB, graphify) invocati da terminale: **identici** su Cursor. Cio' che cambia e' solo l'agente che li chiama, non il risultato.
