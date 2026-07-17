---
id: test-content-share-size-boundary
tsk: TSK-404
epic: EP-048
type: integration
---

# Test Size Boundary — content-share-protocol

Limite hard: 100 KB HTML decoded.
Warning threshold: 80 KB HTML decoded.

## Scenario 1 — HTML > 100 KB → EGRESS_BLOCK (hard stop)

**Setup**: `content_share.enabled: true`, tutti i campi compilati
**Azione**: `/share tests/content-share/fixtures/large.html --dry-run`
**Expected**: STOP in Fase 0 con EGRESS_BLOCK — la skill non arriva a Fase 3 (nessun gate umano)
**Output atteso**: stringa "EGRESS_BLOCK" + dimensione misurata in KB + messaggio "supera il limite hard di 100 KB"
**Pass criterion**: presenza "EGRESS_BLOCK" e assenza del riepilogo del gate umano

## Scenario 2 — HTML 80-100 KB → EGRESS_WARN + gate umano visibile

**Setup**: `content_share.enabled: true`, tutti i campi compilati
**Azione**: `/share tests/content-share/fixtures/medium.html --dry-run`
**Expected**: Fase 0 emette EGRESS_WARN con dimensione — la skill continua fino a Fase 3 con warning visibile nel riepilogo gate
**Output atteso**: "EGRESS_WARN" in Fase 0, riepilogo gate con warning dimensione, "DRY RUN completato"
**Pass criterion**: presenza "EGRESS_WARN" + riepilogo gate + "DRY RUN"

## Scenario 3 — Verifica che il messaggio EGRESS_BLOCK includa la dimensione misurata

**Setup**: stesso di Scenario 1
**Azione**: `/share tests/content-share/fixtures/large.html --dry-run`
**Expected**: output contiene "X KB" dove X > 100
**Pass criterion**: regex `[0-9]+(\.[0-9]+)? KB` presente nel messaggio EGRESS_BLOCK

## Note sulle fixture

| File | Dimensione attesa | Dimensione generata |
|---|---|---|
| `fixtures/large.html` | > 102400 bytes (> 100 KB) | 105001 bytes (102.5 KB) |
| `fixtures/medium.html` | 81920-102400 bytes (80-100 KB) | 88001 bytes (85.9 KB) |

La misura è su HTML **decoded** (il file grezzo, non la stringa base64 né il payload JSON).
