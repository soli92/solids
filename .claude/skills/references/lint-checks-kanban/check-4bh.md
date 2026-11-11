---
skill: lint-checks
leaf_of: lint-checks-kanban.md
section: "kanban"
description: "Check 4bh: TSK layer be chiusi senza evidenza di test automatici"
---

> Eseguito da `tools/lint/run-deterministic.py` (registrato in `CHECKS`).

# 4bh — Evidenza di test sui TSK `layer: be` chiusi (default off)

**Eseguibile, non interpretato.**

```bash
python3 tools/lint/check_evidenza_test_be.py --root .
```

Opzioni: `--json`, `--strict` (exit 1 con almeno un ERROR), `--severita warning|error` (misura a
regola spenta).

**Cosa controlla.** Ogni TSK `layer: be` con `status: done` deve avere un TSK `layer: qa`
`done` che lo cita in `depends_on` e la cui sezione `## Esito` riporta: il comando (fra apici
inversi), il codice di uscita, i test saltati a zero, il percorso del report, almeno uno SHA.

**Configurazione** (blocco `lint.kanban` di `factory.config.yaml`; default spento):

| Chiave | Valori | Significato |
|---|---|---|
| `be_test_evidence` | `off` / `warning` / `error` | severità dei finding |
| `be_test_evidence_consumers` | lista, default `[agent]` | consumer soggetti; `[agent, human]` per estendere ai TSK BE umani |
| `be_test_evidence_since` | `AAAA-MM-GG` | i TSK chiusi prima non sono soggetti (data = `closed_at`, in mancanza `updated`) |

**Codici.**

| Codice | Quando |
|---|---|
| `be-senza-tsk-qa` | nessun TSK qa lo ha in `depends_on` |
| `be-tsk-qa-aperto` | i TSK qa che lo citano non sono `done` |
| `be-evidenza-incompleta` | l'Esito del qa non riporta tutti gli elementi (elenca i mancanti) |
| `be-na-senza-motivo` | `be_test_evidence: na` senza `be_test_evidence_reason` |

**Esenzioni.** Non sono soggetti: i TSK non `done` (anche `cancelled` e `superseded`), quelli chiusi
prima di `be_test_evidence_since`, quelli con un `consumer` fuori da `be_test_evidence_consumers`,
e i TSK BE senza codice che dichiarano nel frontmatter:

```yaml
be_test_evidence: na
be_test_evidence_reason: "solo documentazione, nessun codice da provare"
```

Il motivo è obbligatorio: senza, l'esenzione non vale e il TSK resta soggetto (più il finding
`be-na-senza-motivo`). La chiave `test_evidence` è un'altra cosa (prova dell'esecuzione del caso) e non esenta dal check.

**Output format:** finding nel formato comune di `tools/lint/lint_comune.py`, con `[4bh]` e il codice.

[^src: tools/lint/check_evidenza_test_be.py]
