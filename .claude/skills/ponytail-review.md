---
name: ponytail-review
description: "Esegue la Passata YAGNI Decision Ladder (Pass 4 advisory) su un diff arbitrario (TSK-id | branch | file | --staged). Wrapper standalone di code-review-protocol §Passata 5. Opt-in EP-057. Non esegue Passate 1-3, non produce verdict."
status: stable
epic_id: EP-057
pattern_version: "2.39-candidate"
---

# Skill — ponytail-review

Esegue **la passata YAGNI Decision Ladder** ([[decision-ladder]]) su un diff arbitrario, in
modalità standalone. È un **wrapper** di `code-review-protocol` §Passata 5 («Pass 4 advisory»
nella terminologia EP-057): stessa procedura, nessuna logica duplicata. Non esegue le Passate
1-3 del CQRL né calcola un verdict — produce solo findings advisory.

Invocata dal comando `/ponytail-review`.

## Gate (precondizione)

```
IF factory.config.yaml.ponytail.enabled != true:
    STOP — "Ponytail non abilitato. Aggiungi `ponytail.enabled: true` + `ponytail.passes.yagni_ladder: true` in factory.config.yaml."
```

Nota: `/ponytail-review` è **esecuzione esplicita = volontà esplicita** — richiede solo
`ponytail.enabled: true` (non necessariamente `passes.yagni_ladder`, che governa l'integrazione
automatica nel loop CQRL/lint). Pattern coerente con `/visual-oracle` (EP-005).

## Input

| `<target>` | Risoluzione del diff |
|---|---|
| `TSK-<id>` | diff dei file in `code_path` del TSK (da frontmatter kanban) |
| `<branch>` | `git diff <default-branch>...<branch>` |
| `<file-path>` | diff del singolo file (o contenuto se untracked) |
| `--staged` | `git diff --staged` |

## Procedura (4 step)

### Step 1 — Risolvi il diff
Determina i file in scope dal `<target>`. Se il target non risolve alcun file →
STOP informativo: `"Nessun file in scope per <target>."`

### Step 2 — Applica la Decision Ladder
Per ogni file in scope, valuta il livello più alto (più economico) che avrebbe risolto il
requisito (identico a `code-review-protocol` §Passata 5):

| # | Livello | Domanda |
|---|---------|---------|
| 1 | YAGNI | Era necessaria questa feature? |
| 2 | Riuso | Esiste già una funzione/helper nel codebase? |
| 3 | Stdlib | La libreria standard lo fornisce? |
| 4 | Platform-native | Esiste una feature nativa (browser/OS/runtime)? |
| 5 | Deps installate | Un package già presente lo copre? |
| 6 | Una riga | È risolvibile monolineamente? |
| 7 | Minimo necessario | Implementa solo l'essenziale |

### Step 3 — Produci i findings
Tabella dei candidati alla semplificazione:

```markdown
| File | Costrutto | Livello suggerito | Note |
|---|---|---|---|
| src/components/DatePicker.tsx | componente custom | 4 (Platform-native) | `<input type="date">` — 23 vs 404 righe |
```
Se nessun candidato: `> Nessun candidato alla semplificazione identificato.`

### Step 4 — Output
Findings mostrati in chat. Con `--save`, scrivi anche in
`code_quality/reports/ponytail-review-<target-slug>-<YYYY-MM-DD>.md` (alimenta `/ponytail-gain`).

## Invariante R.PY1

Questo comando **non valuta, non sopprime e non modifica** findings di security, accessibilità
o validazione trust-boundary. La riduzione di codice è conseguenza del minimalismo necessario,
mai del taglio di controlli critici. Non bypassabile.

## Cross-link

- Procedura canonica: `.claude/skills/code-review-protocol.md §Passata 5`
- Concetto: `wiki/concepts/decision-ladder.md`, `wiki/concepts/ponytail.md`
- Comando: `.claude/commands/ponytail-review.md`
- Companion: Lint Check 4ao (enforcement post-develop) + `/ponytail-audit` (full-repo)
