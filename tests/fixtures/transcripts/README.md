---
schema_version: "2.1.258"
redacted: true
fixture_source: real-session-redacted
ingest_eligible: false
---

# Fixture: Transcripts Claude Code

Questa directory contiene fixture di transcript reali redatte per privacy,
versionati nel repo per i test di regressione di EP-061/EP-062.

## Struttura

```
tests/fixtures/transcripts/
├── README.md                                         # questo file
└── cc-2.1.258-with-subagents/
    ├── main.jsonl                                    # transcript principale (80 righe, redatto)
    ├── main/                                         # session dir per compatibilità script
    │   └── subagents/                               # path risolto da harvest-session-tokens.py
    │       ├── agent-a0857a04a39972c75.jsonl
    │       ├── agent-a0c895ec4cc4b5d79.jsonl
    │       └── agent-a10baa525cd7bda6b.jsonl
    └── subagents/                                   # path "documentato" (spec TSK-547)
        ├── agent-a0857a04a39972c75.jsonl
        ├── agent-a0c895ec4cc4b5d79.jsonl
        └── agent-a10baa525cd7bda6b.jsonl
```

## Fixture `cc-2.1.258-with-subagents`

### Provenienza

- **Sessione reale**: Claude Code 2.1.258, factory `soli-multi-agents-factory`
- **Data acquisizione**: 2026-09-08 (sessione originale: 2026-09-04)
- **Motivazione**: implementazione EP-060 Fleet Health (refactor-agent-skills, fleet-doctor,
  pilot wave D con 134 sub-agenti)
- **ID sessione originale**: `f0f6e13d-cfbe-4daa-968c-02e75a395e15` (non incluso nella fixture)

### Contenuto

| File | Righe | Descrizione |
|---|---|---|
| `main.jsonl` | 80 | Transcript principale (queue-operations, user/assistant, tool_use, Agent call) |
| `subagents/agent-a0857a04a39972c75.jsonl` | 25 | Sub-agente: upgrade soli-boy a v2.41 |
| `subagents/agent-a0c895ec4cc4b5d79.jsonl` | 25 | Sub-agente: catena US-229 fleet-doctor |
| `subagents/agent-a10baa525cd7bda6b.jsonl` | 25 | Sub-agente: catena US-230 skill+foglie |

**Record types in main.jsonl**: `queue-operation` (4), `user` (30), `assistant` (45, tutti con `usage`),
`attachment` (1, `deferred_tools_delta`).

**Modelli presenti**: `claude-opus-4-7` (orchestratore), `claude-sonnet-4-6` (sub-agenti).

**Tool_use presenti**: `Agent` (1 chiamata sub-agente), `Bash`, `Read`, `Skill`.

### Redazioni applicate (R-SAA-3)

1. **Path assoluti personali**: `/Users/simone.olivieri/` → `/Users/USER/`
2. **Email personali**: nessuna trovata nel campione estratto
3. **Credenziali/token**: pattern `sk-`, `Bearer`, API keys → `[REDACTED_SK]` /
   `[REDACTED_TOKEN]`; campo `cwd` e campi `file.filePath` redatti via regola #1
4. **Content di `tool_result`**: testo lungo (>300 caratteri) → `[REDACTED - tool_result text]`
5. **Content di lettura file** (`toolUseResult.file.content`): → `[REDACTED - file content]`
6. **Output bash lungo** (`toolUseResult.stdout/stderr` >500 caratteri): → `[REDACTED - tool stdout/stderr]`
7. **Thinking chains** (`type: thinking`): → `[REDACTED_THINKING]`
8. **Agent description `addedLines`** (`agent_listing_delta`): il record è stato escluso
   perché `addedLines` contiene percorsi di capability wiki come `task-analytics-cost-estimation-capability`
   che contengono la sottostringa `sk-` (falso positivo del grep PII). Non necessario
   per i test di token harvesting.
9. **Session ID**: anonimizzato in `cc-2.1.258-with-subagents` in tutti i record

**Preservati integralmente**: `type`, `isSidechain`, `agentId`, `message.model`,
`message.usage` (input/output/cache_read/cache_creation), `timestamp`, `stop_reason`,
`version`, `diagnostics`, struttura `content[].type`, `tool_use.name`.

### Uso nei test

**Verifica fan-in (harvest-session-tokens.py post-TSK-545):**

```bash
# Dry-run: trova main + 3 subagenti in main/subagents/
python3 tools/analytics/harvest-session-tokens.py \
  tests/fixtures/transcripts/cc-2.1.258-with-subagents/main.jsonl \
  --dry-run

# Output atteso:
# "subagent_files": 3
# "groups": 3
# "status": "ok"
```

**Nota sulla struttura duale `subagents/` vs `main/subagents/`:**
La directory `subagents/` al livello di `cc-2.1.258-with-subagents/` è quella documentata
nella spec TSK-547 e leggibile da umani. La directory `main/subagents/` è richiesta dal
logic corrente di `harvest-session-tokens.py` che calcola il session dir come
`parent(transcript) / stem(transcript)`: poiché il transcript è `main.jsonl`, il session
dir diventa `main/` e il walker cerca `main/subagents/`. Entrambe le directory contengono
gli stessi file. Se TSK-546 aggiorna il walker per usare `parent(transcript)/subagents/`
direttamente, la directory `main/subagents/` diventerà ridondante e potrà essere rimossa.

### Politica di aggiornamento

Aggiornare questa fixture quando:
1. Il formato schema Claude Code cambia in modo incompatibile con il parser di
   `harvest-session-tokens.py` (nuovi campi obbligatori, tipo record rinominato, ecc.)
2. Viene aggiunto un nuovo tipo di record che il contract-test (TSK-548) deve coprire

Non aggiornare per: nuove versioni di CC con schema compatibile, variazioni nei valori
di token (i valori redatti sono già stati anonimizzati).

### Verifica redazione

```bash
# Deve produrre 0 match
grep -r "simone.olivieri\|/Users/simone\|sk-\|Bearer " tests/fixtures/transcripts/
```
