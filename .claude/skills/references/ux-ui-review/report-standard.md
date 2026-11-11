# Step 5 — Report Standard (dettaglio completo)

Ambito: dettaglio del Step 5 di `ux-ui-review-protocol.md`. Leggere prima di produrre
il report finale.

---

## Schema JSON standard

```json
{
  "target": "...",
  "type": "ux_ui_review",
  "summary": { "critical": 0, "major": 2, "minor": 4, "open_questions": 3 },
  "findings": [
    {
      "rubric_ref": "nielsen-1",
      "severity": "major",
      "location": "...",
      "description": "...",
      "recommendation": "...",
      "evidence": "screenshots/desktop-1280.png (Step 1, capture_screenshot output)",
      "opinion": false
    }
  ],
  "positive_findings": [],
  "open_questions": [],
  "tokens_source": "design_system|css|figma|defaults",
  "critic_judge_section": null,
  "intention_economy_section": null,
  "generated_by": null
}
```

> `generated_by` (opzionale, backward-compat): nome canonico dell'agente o della skill
> che ha eseguito questa review. Assenza → Check 4ac (EP-024) emette `skipped`.

## Campo `evidence` — obbligatorio e non nullable

Deve referenziare un artefatto reale prodotto negli Step 1/2. Valori ammessi:
- Modalità visiva: path screenshot esistente su disco prodotto da Step 1.
- Token/conformance: output di `extract_design_tokens` o `check_design_system_conformance`.
- Modalità `no-visual`: path file/snippet letto via `Read`/`Grep` in Step 1.

## Regola invariante rubric_ref

Ogni `finding` cita un `rubric_ref` (asse 1/2/3 o regola DS). **Niente finding "a sensazione".**
Domande aperte di contesto utente/business → `open_questions`, mai `findings`. Punti opinabili
→ `opinion: true` + nota in `description`. Lo `severity` è in {critical, major, minor}.

**`rubric_strict`**: se `factory.config.yaml.ux_ui.rubric_strict: true` (default), un finding
senza `rubric_ref` è un errore di procedura (scartalo o assegnagli un ref). Con
`rubric_strict: false` emetti un WARNING per il finding e procedi.

## Guard di SOSTANZA — evidence-provenance (ADR-063 §B)

Ogni finding deve avere un campo `evidence` che referenzia un artefatto reale prodotto negli
Step 1/2. **Regola di rigetto**: se `evidence` è null, stringa vuota, path non esistente su
disco, o non tracciabile a un artefatto degli Step 1/2 → il finding viene **rigettato**.

Questo guard è **complementare** a `rubric_strict`:
- finding con `rubric_ref` ma `evidence: null` → rigettato da `evidence-provenance`.
- finding con `evidence` valida ma senza `rubric_ref` → rigettato da `rubric_strict`.
- finding con entrambi valorizzati e verificabili → emesso.

Il guard `evidence-provenance` si applica **indipendentemente** dal valore di `rubric_strict`.

## Storage side-channel

ADR-020 §E, riuso CQRL:
- Con TSK: `code_quality/reports/<TSK-id>-uxui-review-iter-<N>.{json,md}`
- Standalone: `code_quality/reports/_adhoc/uxui-review-<YYYY-MM-DD-HH-MM>-<slug>.{json,md}`
- Asset: `code_quality/reports/<TSK-id>-uxui-review-iter-<N>/`

**Criterio di completamento**: report JSON conforme allo schema; ogni finding con `rubric_ref`
e `evidence` verificabile (guard forma + sostanza entrambi soddisfatti); i finding che non
superano uno dei due guard sono stati scartati prima dell'emissione; digest Markdown prodotto.

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-028-skill-ux-ui-review-protocol/US-028.md §Step 5]
[^src: wiki/concepts/ux-ui-review-design-capability.md §Schema di output standard]
[^src: design_&_architecture/decisions/ADR-063.md §B]
