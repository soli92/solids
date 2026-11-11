---
name: caveman-protocol
description: Protocollo per comprimere payload messaging agent-to-agent / agent-to-tool via Caveman skill (PATTERN §20, v2.14). 5 fasi (Bootstrap → Identify Channel → Apply Compression → Drift Check → Log). Allow-list channel-aware enforced da invarianti R.C1–R.C6.
---
# Protocollo Caveman (Output Compression)

Riferimenti: PATTERN §20 (Output Compression Layer), §7 r.18 (compression mai sugli
artefatti), §20.4 R.C1–R.C6 (invarianti), §18 (parallel scheduling), `wiki-log-entry`,
[[factory-compression-layer]] (design doc), [[caveman]] (entity product).

Questa skill è **provider-bound** a [[caveman]] (cliva su prompt skill markdown).
Definisce le 5 fasi che ogni invocazione di compressione deve seguire. È invocata
inline dal dispatcher dell'orchestrator (§20.7) e dai sub-agent che producono
return value.

## Prerequisiti

- `factory.config.yaml.compression.output.enabled: true` (altrimenti no-op).
- `factory.config.yaml.compression.output.provider: caveman`.
- [[caveman]] installato sul sistema (`caveman --version` ritorna OK).
- `policy_profile` valorizzato (`conservative | aggressive | custom`).
- Se `policy_profile: custom`, `channels` block completo.

Se uno dei prerequisiti manca → ABORT silenzioso in Fase 1, fallback a normal mode,
warning in `wiki/log.md` (`compression-disabled: <reason>`).

## Fase 1 — Bootstrap

Eseguito **una volta per sessione** (cache in memoria del runtime).

- Read `factory.config.yaml.compression.output` completo.
- Verifica:
  - `enabled: true`. Se `false` → SKIP TUTTO (no-op per il resto della sessione).
  - `provider: caveman`. Mismatch → ABORT con warning.
  - Caveman installato (`Bash: caveman --version`). Se non installato:
    - Se `install_command` valorizzato → istruzioni in chat (mai auto-install).
    - SKIP TUTTO per la sessione + warning persistente.
  - `policy_profile` ∈ `{conservative, aggressive, custom}`.
  - Se `custom`: `channels` block completo (tutti i canali §20.2 valorizzati). Altrimenti
    ABORT con ERROR (no silent fallback ai preset — `wiki-lint` Check 4k lo segnala
    anche staticamente).
- Carica matrice canale→livello in base al profilo (§20.2):
  - `conservative` → preset Conservative
  - `aggressive` → preset Aggressive
  - `custom` → override completo da `channels`
- Carica invarianti enforced (R.C1):
  - `to_user: off`, `to_artifact: off`, `propagate_resolution: off`
- Read `audit_trail_for` list (canali sempre in normal mode).

Output: `caveman_runtime_config` in memoria.

## Fase 2 — Identify Channel

**Input**: payload (string) + metadata (sender, receiver, kind, chain_depth, tsk_id).

Identifica il **canale** dal `(sender, receiver, kind)`:

| `(sender, receiver, kind)` | Canale |
|---|---|
| (orchestrator, sub-agent, dispatch) | `orchestrator_to_subagent` |
| (sub-agent, tool, call) | `subagent_to_tool` |
| (tool, sub-agent, result) | `tool_to_subagent` |
| (sub-agent, orchestrator, return) | `subagent_to_orchestrator` |
| (sub-agent_a, sub-agent_b, handoff) | `sibling_to_sibling` |
| (feedback-router, dev-agent, task_package) | `feedback_router_to_devagent` |
| (qualsiasi, user, *) | `to_user` (R.C1: sempre off) |
| (qualsiasi, file, write) | `to_artifact` (R.C1: sempre off) |
| (propagate-resolution, wiki page, update) | `propagate_resolution` (R.C1: sempre off) |

Canale non identificabile → fallback automatico a normal mode + warning
`compression-unknown-channel: <(sender, receiver, kind)>` in `wiki/log.md` (R.C2).

**Check `audit_trail_for`**: se il canale identificato è in `audit_trail_for` list,
**bypass compressione** per questa invocazione (mantieni normal mode per audit). Mai
ERROR — è un canale legittimo, solo escluso dalla compressione per policy.

**Check cross-factory** (R.C4): se `factory.config.yaml.topology` è `federated-topology`
e `receiver.factory != sender.factory` → fallback a normal mode + log marker
`compression-cross-factory-skip: <tsk_id>`.

## Fase 3 — Apply Compression

Determina il **livello effettivo** di compressione applicato:

1. Livello base dal canale + profilo (matrice §20.2).
2. **R.C3 chain-depth severity ceiling** (solo `conservative` o `custom` con
   `chain_depth_downgrade: true`): se `metadata.chain_depth > 3`:
   - `ultra → full`
   - `full → lite`
   - `lite → off` (no-op, ma log warning)
3. **R.C1 invariants check** (paranoid double-check anche se Fase 2 ha già filtrato):
   se canale ∈ `{to_user, to_artifact, propagate_resolution}` → forza `off`.

Applicazione:

```bash
# Pseudocodice — l'agent invoca caveman CLI o usa la libreria
caveman --level=<level> --input=<payload> --output=<compressed_payload>
```

Output: `compressed_payload` (string).

**Performance**: caveman è un prompt skill markdown applicato dal modello stesso. Non c'è
overhead di rete o processo esterno; è una trasformazione inline nel prompt del modello
chiamante.

## Fase 4 — Drift Check (R.C5)

Eseguito **dopo** che il destinatario ha risposto.

- Read response del destinatario.
- Scansiona per marker di ambiguità (configurabili in `drift_fallback.markers`):
  - `AMBIGUOUS_HANDOFF` — il destinatario non riesce a interpretare il payload
  - `REQUEST_CLARIFY` — il destinatario chiede chiarimenti
  - Exception interpretativa con keyword whitelist
- Se marker presente:
  1. Append a `wiki/log.md`: `compression-drift TSK-<id> canale=<C> profilo=<P>
     livello=<L> chain_depth=<D>`
  2. **Rinvia la stessa request in normal mode** (no Caveman) all'agent destinatario.
     Single retry: se anche normal mode produce ambiguità → escalation umana (chat
     warning) e termina il flow.
  3. Incrementa contatore `drift_count` per la sessione. Se `drift_count >= 3` in una
     sessione → switch automatico globale a normal mode + chat warning per intervento
     utente sul `policy_profile`.

Se no marker → flusso continua normale.

## Fase 5 — Log

Append a `wiki/log.md` (formato standard, `wiki-log-entry` skill):

```
[YYYY-MM-DD HH:MM] compression — <wave_id|tsk_id>: canale=<C>, profilo=<P>,
  livello=<L>, tokens_in=<N>, tokens_out=<M>, ratio=<M/N>, drift=<0|1> — files touched: 0
```

`files touched: 0` perché la compressione non scrive file (oltre al log stesso, che è
single-committer dell'orchestrator/agent invocante — non un duplicate write).

**Aggregazione**: `state-scan` (o `/compression show`) somma le entry `compression`
del `wiki/log.md` per produrre statistiche per canale + profilo:

```
ULTIMA SESSIONE COMPRESSION STATS
=================================
Profilo:    conservative
Canale                          ratio       drift   tokens saved
orchestrator_to_subagent        0.46         0     12.4k
subagent_to_tool                0.18         0      4.7k
tool_to_subagent                0.71         1      3.2k
subagent_to_orchestrator        0.42         0      8.1k
TOTAL                           0.44         1     28.4k (~$3.40)
```

## Sub-agent invocazione (per testing / dry-run)

Se invocato isolato (non da scheduler):

```
/compression dry-run --payload="<text>" --channel=<C> [--profile=<P>]
```

Output: payload compresso + ratio. Mai scrive `wiki/log.md` in dry-run.

## Vincoli (PATTERN §7 r.18 + §20.4 R.C1–R.C6)

- Mai applicare Caveman a `wiki/**`, `management/kanban/**`, `<code_path>/**`,
  `design_&_architecture/**`, `code_quality/**`, `memory/**`, `raw/**` (R.C1).
- Mai applicare Caveman a output destinato all'utente finale (R.C1).
- Mai applicare Caveman cross-factory in topologie federate (R.C4).
- Mai bypass automatico dei marker di drift (R.C5).
- `caveman_policy:` nel frontmatter agent può **solo abbassare** il livello (es. `ultra
  → full`), mai abilitare canali R.C1.
- Modifiche al `policy_profile` solo via `/compression set` con gate umano (mai
  auto-modifica a runtime).

Vedi PATTERN §20 per il contratto completo, [[factory-compression-layer]] per il
design rationale, [[caveman]] per i dettagli del tool.
