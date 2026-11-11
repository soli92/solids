# session-close-protocol — Fase 2: payload completo e risoluzione outcome

Ambito: template YAML del payload completo, cascata risoluzione outcome, gate schema Fase 2→3.
Caricare quando si compone il payload per session-sync o si verifica l'outcome.

## Payload completo

```yaml
session_label: <SESSION_LABEL>
date: <YYYY-MM-DD>
opened_at: <da active-sessions.yaml (primary) o session-open.yaml (fallback) o approssimato>
closed_at: <CLOSED_AT>
operator: <operator>
context: <context da input o da active-sessions.yaml fallback>
outcome: completed     # vedi §Risoluzione outcome
outcome_source: auto-derived   # auto-derived | manual
factory_version: <project.pattern_version>
active_agents: <lista agenti da log.md se rilevabile>
ingest_hint: full-page  # default; "index-only" se sommario scarno; "skip" su --dry-run

vcs_snapshot:
  factory_commit: <FACTORY_COMMIT>
  code_paths_commits:           # chiavi dinamiche: slug di ogni entry in factory.config.yaml code_paths[]
    <slug1>: <hash o "n/a">    # es. "default" se code_path: "." (reflexive mode)
    <slug2>: <hash o "n/a">    # ogni code_path entry con vcs.mode != none

sommario: |
  <2-3 frasi sintetiche derivate dal context + dai commit + dalle entry log.md>

decisioni: []          # lista da wiki/log.md entry "decision" + da conversazione
artefatti: []          # lista da git diff --name-status + log.md
task_avanzati: []      # lista TSK con stato prima→dopo (da kanban diff)
gap_aperti: []         # lista machine-readable da wiki/gaps.md delta
gap_chiusi: []         # lista machine-readable da wiki/gaps.md delta
insight: []            # da log.md entry "insight" o osservazioni emerse
token_cost:
  total_tokens: ~
  cost_usd: ~            # Fase 1h: costo della sessione da cost_alert.py
  alert: []              # Fase 1h: regole superate e note del verdetto; [] se nessuna
```

**Regola compilazione**: Mai inventare. Sezione senza dati verificabili → `[]` o `null`.

## VCS Snapshot — comandi

```bash
FACTORY_COMMIT=$(git -C <factory_root> rev-parse --short HEAD)

# Loop generico su code_paths[] da factory.config.yaml.
# Per ogni entry {name, path, vcs: {mode: ...}}:
#   - se vcs.mode != none e path != "." (o equivalente al factory_root):
#       slug=<name>
#       HASH=$(git -C <path> rev-parse --short HEAD 2>/dev/null || echo "n/a")
#   - se path == "." (reflexive): slug=<name>, HASH=FACTORY_COMMIT
# Il dict risultante va in vcs_snapshot.code_paths_commits.
#
# Esempio bash per una singola entry (ripetere per ogni code_path):
#   HASH=$(git -C "<path>" rev-parse --short HEAD 2>/dev/null || echo "n/a")
#
# Se code_paths[] è vuoto (factory reflexive pura, code_path: "."):
#   code_paths_commits: {}   # dict vuoto, non assente
```

**Nota**: non usare costanti verticali (nomi di repo, slug fissi). I nomi
delle chiavi in `code_paths_commits` derivano dal campo `name` di ogni entry
in `factory.config.yaml#code_paths[]`.

## Risoluzione `outcome` + provenance

1. **SE `outcome` da input (`--outcome`) è valorizzato**:
   - Valida contro enum `{completed, partial, aborted}`. Fuori enum → STOP `error:invalid_outcome`.
   - `outcome_source: manual`.
   - **Discrepancy check (non bloccante)**: se diverge dall'euristica → warning in chat:
     ```
     [session-close] outcome manuale '<X>' diverge dall'euristica '<Y>'
     (segnale: commit del giorno=N, entry log.md=M). Onoro il valore manuale.
     ```
     Aggiungi nel documento: `<!-- outcome manuale '<X>' diverge dall'euristica '<Y>' -->`.
     Onora sempre il valore umano.

2. **ALTRIMENTI** — euristica automatica:
   - `completed` come default;
   - `partial` se git log del giorno (Fase 1a) è vuoto;
   - `aborted` solo su segnalazione esplicita in `context` o conversazione.
   - `outcome_source: auto-derived`.

## Gate schema Fase 2→3

| Campo | Regola | Azione su fail |
|---|---|---|
| `context` | non vuoto, ≥ 20 char (derivabile dal sommario) | STOP `error:payload_incomplete` + rilascia lock |
| `outcome` | ∈ `{completed, partial, aborted}` | STOP `error:invalid_outcome` (se da `--outcome`) o `error:payload_incomplete` + rilascia lock |
| `outcome_source` | ∈ `{auto-derived, manual}` | STOP `error:payload_incomplete` + rilascia lock |
| `session_label` | match `^session-\d{4}-\d{2}-\d{2}-\d{2}-[a-f0-9]{8}$` | STOP `error:payload_incomplete` + rilascia lock |
| `closed_at > opened_at` | vera se `opened_at` disponibile | warning in chat (non STOP) |

SE `--dry-run` attivo: mostra payload in chat, termina qui (rilascia lock).

[^src: .claude/skills/session-close-protocol.md — Fase 2 payload, outcome, gate schema]
