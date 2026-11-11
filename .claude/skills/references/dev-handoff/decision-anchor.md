# Decision Anchor Propagation — dettaglio (opt-in v2.19, EP-015)

**Ambito**: estensione opt-in di `dev-handoff.md` per la propagazione del
`decision_anchor` (EP-015). Leggere obbligatoriamente prima di emettere l'handoff
quando `factory.config.yaml.compression.output.decision_anchor.enabled: true`.

---

> **Gated**: `factory.config.yaml.compression.output.decision_anchor.enabled: true`.
> A flag spento questa sezione è no-op, comportamento identico v2.18 (R.P3).

## Step pre-handoff (DA ESEGUIRE PRIMA DI EMETTERE L'HANDOFF)

1. **Controlla presenza**: l'input del dev-agent include `decision_anchor` nel task package?
   - Se NO e `enabled: true` → ERROR `[anchor-stripped]` in `wiki/log.md` + blocco handoff.
   - Se NO e `enabled: false` → no-op.
2. **Controlla checksum**: il campo `decision_anchor.checksum` nel task package ricevuto corrisponde
   all'hash di `canonical_json(decision_anchor.decisions[])`?
   - Se NO → ERROR `[anchor-tampered]` in `wiki/log.md` + blocco handoff.
3. **Copia invariata**: includi il campo `decision_anchor` nell'output del handoff senza modifiche.
   Il dev-agent è **read-only** sull'anchor.

## Struttura handoff arricchita (gated)

```yaml
# dev-handoff output — sezione aggiunta v2.19
decision_anchor: <<anchor copiato invariato dall'input>>
# Nota: <<...>> = marcatore template cross-adapter (non stampare letteralmente)
```

## Errori

| Codice | Condizione | Severity | Azione |
|--------|-----------|----------|--------|
| `anchor-stripped` | Anchor atteso ma assente | ERROR | Blocco handoff, log `[anchor-stripped]` |
| `anchor-tampered` | Checksum mismatch | ERROR | Blocco handoff, log `[anchor-tampered]` |

## Cross-link

- Schema anchor: `wiki/runbooks/decision-anchor-runbook.md` (TSK-115)
- PATTERN §20.4 R.C7 (TSK-119)
- Skill parallela: `vcs-handoff.md` (stessa logica)
