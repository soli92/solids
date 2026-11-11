---
skill: dev-protocol
leaf_of: dev-protocol.md
section: Fase 4-quater
description: "Trigger CQRL di default: review_status pending impostato dal dev-agent, review dispatchata dall'orchestrator"
---

# Fase 4-quater — Trigger CQRL di default (opt-in, `code_quality.trigger_default`)

Sub-step di Develop **dopo la Fase 4-ter** (UX/UI Review, se attiva) e **prima della Fase 5**.
Il dev-agent imposta `review_status: pending` sul TSK quando le condizioni sono soddisfatte; non
invoca `code-reviewer` (agente distinto, dispatchato dall'orchestrator in `dispatch-policy` §12).
Senza questa fase la review parte solo sui TSK che nascono gia' con `review_status: pending`.

**Trigger (AND)**:
- `code_quality.trigger_default.enabled: true`;
- `TSK.layer ∈ code_quality.trigger_default.layer`;
- `TSK.consumer ∈ code_quality.trigger_default.consumer`.

**No-op** (compatibilita'):
- `trigger_default` assente o `enabled: false` → la fase non fa nulla, il TSK passa alla Fase 5;
- layer o consumer fuori dalle liste → nulla;
- l'opt-in per TSK (`review_status: pending` scritto da chi crea il TSK) resta valido.

**Azione**:

1. Leggi `code_quality.trigger_default` (gia' letto in Fase 0).
2. Campo e valore da `review_status_field` (default `review_status`) e `review_status_default`
   (default `pending`).
3. Se il campo vale gia' `passed` o `rejected` (review fatta in una sessione precedente) → nulla:
   non sovrascrivere.
4. Altrimenti imposta il campo nel frontmatter del TSK.
5. Segnala in chat:
   ```
   CQRL trigger_default: review_status: pending su <TSK-id>. code-reviewer sara' dispatchato
   dall'orchestrator (dispatch-policy §12) dopo il commit.
   ```
6. Procedi alla Fase 5 senza invocare `code-review-protocol`.

**Avvisi, non blocchi**:
- trigger attivo ma `code_quality/rules/` vuoto per il ruleset → WARNING «il code-reviewer
  produrra' zero finding reali»; il commit procede (il CQRL e' advisory, Layer-2);
- trigger attivo ma `code-reviewer` non presente nella topologia → WARNING; la verifica spetta
  all'orchestrator.

**Layer-2**: questa fase prepara l'ingresso nel ciclo CQRL, non esegue la review. Il
`verdict: reject` resta gate umano (R.16); nessun blocco automatico di merge o deploy.

**Su `/dev`**: l'orchestrator non c'e', quindi nessuno dispatcha la review: la verifica di
chiusura di `/dev` (passo 6a) lo segnala.

[^src: portale-servizi-factory — FAC-TSK-219, trigger default-on del CQRL; ritorno EP-072 TSK-778]
