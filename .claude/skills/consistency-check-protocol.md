# Skill: Consistency Check Protocol

> Adapter Cursor della skill `consistency-check-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
id: consistency-check-protocol
version: v2.19
capability: EP-015
opt_in: compression.output.consistency_check.enabled
actor: consistency-checker
pattern_refs: [evaluator-optimizer, fail-closed]
```

> 5 step per verificare se l'output di un sub-agent contraddice il `decision_anchor`.
> Invocata SOLO dall'agente [consistency-checker](mdc:.cursor/rules/consistency-checker.mdc) (non invocabile da sub-agent su se stesso).

## Step 1 — Read anchor

Leggi il campo `decision_anchor` dall'input (YAML strutturato).
Valida:
- `decision_anchor.checksum` === `sha256(canonical_json(decision_anchor.decisions[]))`.
- Se mismatch → abort con ERROR `[anchor-tampered-pre-check]` in `wiki/log.md`. No verifica eseguita.
- Se anchor assente → abort con WARNING `[no-anchor-to-verify]`. Verdict `pass` per default (no anchor = no contract to enforce).

## Step 2 — Read output artifact

Leggi l'artifact referenziato da `output_artifact_ref` via `read_file`.
Estrazioni rilevanti:
- Decisioni tecniche esplicite dichiarate nel testo.
- Stack / tool / pattern menzionati.
- Architettura proposta o modificata.
- Eventuali `decision_anchor` inline (se il sub-agent ha copiato il proprio anchor nell'output).

Cap: `compression.output.consistency_check.token_budget_max` (default: 5000 token per invocazione).
Cap superato → degraded mode: verdict `warn` con `[checker-budget-exceeded]` + `manual review required`.

## Step 3 — Compare (anchor vs output)

Per ogni `decision` in `anchor.decisions[]`:
1. Estrai la claim chiave da `decision.decision`.
2. Cerca nell'output evidenza di contraddizione (non solo assenza, ma contrasto esplicito o implicito).
3. Per ogni contraddizione trovata: popola un `finding` con:
   - `decision_id_violated`: `decision.id`
   - `decision`: testo originale
   - `contraddict_evidence`: evidenza estratta dall'output (max 200 char, PII safe)
   - `severity`: `critical | major | minor`
   - `confidence`: float 0..1 (confidence del checker sulla contraddizione)

Criteri severity:
- `critical`: la contraddizione invalida una decisione architetturale fondamentale (stack, security, pattern vincolo).
- `major`: la contraddizione introduce rischio operativo significativo.
- `minor`: divergenza stilistica o sub-ottimale ma non bloccante.

## Step 4 — Compute verdict

Regole severity → verdict:
| Findings | Confidence | Verdict |
|----------|-----------|---------|
| ≥ 1 `severity: critical` | `confidence > 0.7` | `fail` |
| ≥ 1 `severity: critical` | `confidence ≤ 0.7` | `warn` |
| Solo `severity: major\|minor` | qualsiasi | `warn` |
| 0 findings | — | `pass` |

Verdict aggregato: più severo tra tutti i finding.

## Step 5 — Log

Emetti `consistency_check_result`:

```yaml
consistency_check_result:
  verdict: pass | warn | fail
  anchor_checksum: <sha256>
  output_artifact_ref: <path|blob_id>
  findings:
    - decision_id_violated: <slug>
      decision: <string>
      contraddict_evidence: <string max 200ch>
      severity: critical | major | minor
      confidence: <float 0..1>
  metadata:
    checker_actor_id: consistency-checker
    checked_at: <ISO-8601>
    hop_id: <uuid>
    checker_tokens_used: <int>
    degraded_mode: <bool>
```

Azioni basate su verdict:
- `pass`: log evento EP-013 `state: consistency_decision` con `verdict: pass`. No altra azione.
- `warn`: log evento EP-013 + WARNING in `wiki/log.md` con findings summary.
- `fail`: log evento EP-013 + ERROR fail-loud in `wiki/log.md` + escalate gate umano con findings.
  Pattern [[fail-closed]]: NO auto-rollback (scope futuro v2.20+).

Evento EP-013:
```json
{
  "state": "consistency_decision",
  "task_id": "<hop_id>",
  "ts": "<ISO-8601>",
  "tokens": "<checker_tokens_used>",
  "consistency": {
    "verdict": "<verdict>",
    "findings_count": <int>,
    "anchor_checksum": "<sha256>",
    "degraded_mode": <bool>
  }
}
```

## Cross-link

- [[evaluator-optimizer]]: consistency-checker è evaluator esterno sul loop.
- [[fail-closed]]: verdict `fail` → escalate (mai soft fail).
- CQRL R.Q1: reviewer NON è dev-agent → R.Q1bis: consistency-checker NON è il sub-agent verificato.
- EP-014 governor (TSK-111): se `checker_tokens_used > 5%` wave budget → governor escalata (coordinato cross-EP).
- Runbook: `wiki/runbooks/decision-anchor-runbook.md` (TSK-115).
- PATTERN §18 dominio `consistency-check` (aggiunto in TSK-118).
