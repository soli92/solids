# Passata 5 — YAGNI Decision Ladder (advisory) (dettaglio completo)

Ambito: dettaglio della Passata 5 (opt-in) di `code-review-protocol.md`. Leggere prima
di eseguire il pass. Condizionale: solo se `ponytail.passes.yagni_ladder: true` in
`factory.config.yaml`.

> **Nota di numerazione**: la documentazione EP-057 (`wiki/concepts/decision-ladder.md`,
> `factory.config.yaml`, Lint Check 4ao, CLAUDE.md) la chiama informalmente «**Pass 4 advisory**»
> nel senso di *passata advisory addizionale oltre le 3 core*. Numericamente, in questo file,
> è la **5ª passata** (dopo premortem-on-merge = 4).

---

**Pass aggiuntivo, additivo e non distruttivo**: non sostituisce le 3 passate primarie,
**non modifica la logica del verdict aggregator** (Fase 3) e **non può cambiare il verdict**
calcolato da Passate 1-3.

**Pre-condizione** (silenzia tutto il pass):

```
IF factory.config.yaml.ponytail.passes.yagni_ladder != true:
    SKIP   # default off (R.P3 + HARD DEP su code_quality.enabled) — comportamento identico a v2.38
```

**Procedura** — per ogni file modificato nel diff, valuta il livello più alto della
Decision Ladder (dal più economico al più costoso) che avrebbe risolto il requisito:

| # | Livello | Domanda |
|---|---------|---------|
| 1 | YAGNI | Era necessaria questa feature? |
| 2 | Riuso | Esiste già una funzione/helper nel codebase? |
| 3 | Stdlib | La libreria standard lo fornisce? |
| 4 | Platform-native | Esiste una feature nativa (browser/OS/runtime)? |
| 5 | Deps installate | Un package già presente lo copre? |
| 6 | Una riga | È risolvibile monolineamente? |
| 7 | Minimo necessario | Implementa solo l'essenziale (stop qui se sì) |

**Output**: una sotto-sezione `### Pass 4 — YAGNI Ladder (advisory)` **dentro il report
standard** (Fase 4), con la tabella dei candidati alla semplificazione:

```markdown
### Pass 4 — YAGNI Ladder (advisory)
| File | Costrutto | Livello suggerito | Note |
|---|---|---|---|
| src/components/DatePicker.tsx | componente custom | 4 (Platform-native) | `<input type="date">` — 23 vs 404 righe |
```
Se nessun candidato: `> Nessun candidato alla semplificazione identificato.`

**Invariante R.PY1 (non-bypassabile)**: questa passata non può downgrade, mascherare o
sopprimere findings di security, accessibilità o trust-boundary prodotti dalle Passate 1-3.
È advisory: arricchisce il report e il `task_package` per il dev-agent, mai il verdict.

**Relazione con `/ponytail-review`**: il comando `/ponytail-review <target>` esegue
**esattamente questa passata** in modalità standalone su un diff arbitrario (senza Passate
1-3 né loop CQRL). Nessuna logica duplicata — è un wrapper di questa sezione.

[^src: wiki/concepts/decision-ladder.md §7 livelli]
[^src: management/kanban/EP-057-ponytail-decision-ladder/US-<n>-yagni-pass-code-review/TSK-<n>.md §Technical Specs]
