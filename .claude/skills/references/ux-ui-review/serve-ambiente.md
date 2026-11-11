# Step 1.0 — Serve & ambiente di render (dettaglio completo)

Ambito: prerequisiti di avvio server per `ux-ui-review-protocol.md` Step 1. Leggere prima
di eseguire `capture_screenshot`/`run_a11y_scan`. (app-lifecycle, ADR-064)

---

Prerequisito **prima** di `capture_screenshot`/`run_a11y_scan`: i tool sono script Playwright via
`Bash` (ADR-064 §binding). Richiedono (a) Playwright/axe risolvibili da `node_modules` e Node
compatibile, (b) un **target raggiungibile**. Risolvere così:

```
# 1. Risolvi il code_path/package target (dal TSK frontmatter o da factory.config.yaml.code_paths).
#    Le invocazioni dei tool .sh vanno eseguite da QUESTA CWD (require('playwright') risolve dalla CWD).
# 2. Determina il target servito:
if target è URL http/https già live:
    SERVED_URL = target                              # nessun avvio
elif esiste build servibile (dist/) OR serve dev-server:
    avvia un server effimero in background:
      preferisci  `npm run preview` / `vite preview --port <p>`  (build esistente)
      fallback    `npm run dev`                                  (dev-server)
    attendi health-check HTTP 200 su http://127.0.0.1:<p>/  (poll, timeout 30s)
    SERVED_URL = http://127.0.0.1:<p>/
    REGISTRA il pid per il teardown (vedi Step 6)
else:
    → STOP-condition fail-loud (target visivo non servibile)
```

> **Nota Node/CWD (ADR-064 §D)**: se il server fallisce con «Vite requires Node 20.19+» o i tool
> falliscono con `Cannot find module 'playwright'`, l'ambiente Node/CWD è errato — è un **errore
> tecnico fail-loud**, NON un degrado a `no-visual`. Allinea Node (`.nvmrc`) e CWD al package target.

**Invocazione concreta** (sostituisce lo pseudo-`capture_screenshot(...)` della cascata):

```bash
bash <factory>/tools/visual/capture_screenshot.sh \
     --target "$SERVED_URL" --viewports "desktop,mobile" --out "<output_dir>"
```

Il **teardown** del server effimero avviene nello Step 6 (o `finally`): `kill <pid>` — mai lasciare
processi orfani. `output_dir` è la cartella asset del report (vedi Step 5).

## STOP-condition fail-loud (ADR-063 §A)

Si attiva in DUE casi:

1. **`capture_screenshot` restituisce vuoto / errore / tool-not-callable** in modalità visiva
   (target = URL | componente | mockup-con-render): la review NON procede e NON produce finding.
2. **`screenshots: []` dopo invocazione di `capture_screenshot`** in modalità visiva: questo stato
   NON attiva silenziosamente la modalità `no-visual`; attiva il fail-loud.

In entrambi i casi: **STOP immediato**. Emettere il seguente messaggio canonico (invariante):

> «Evidenza visiva non disponibile (capture_screenshot/render fallito o tool non registrato):
> review UX/UI impossibile. Non si producono finding senza evidenza (ADR-063). Verificare la
> disponibilità dei tool / l'ambiente di render.»

Uscire dalla skill. **Non procedere agli Step 2-6.** Fail-closed, non fail-graceful.

## Nota modalità `no-visual`

La modalità `no-visual` (review di sola struttura/codice senza render) deve essere **dichiarata
esplicitamente** (`--mode=no-visual` o `target` di tipo codebase/file). `screenshots: []` da
`capture_screenshot` vuoto NON attiva silenziosamente `no-visual`: attiva la STOP-condition
fail-loud sopra. Per avviare una review `no-visual`: invocare la skill con `mode: no-visual`
esplicito; in `no-visual` Step 1 raccoglie evidenza via `Read`/`Grep` sul sorgente (ADR-063 §C).

## Matrice viewports

La matrice `viewports` è risolta **nel caller** con la cascade:
(1) `factory.config.yaml.fe_correctness.viewports` se `fe_correctness.enabled: true` (riuso totale);
(2) fallback `factory.config.yaml.ux_ui.default_viewports`
(default `[{name: mobile, width: 375}, {name: desktop, width: 1280}]`).
Themes omessi di default per la review euristica (un solo theme sufficiente).

**Output**: `{target, modalità, screenshots: [{viewport, theme, path}]}` (o `screenshots: []`
solo se `modalità = "no-visual"` dichiarata esplicitamente).

[^src: management/kanban/EP-008-ux-ui-review-design-capability/US-028-skill-ux-ui-review-protocol/US-028.md §Step 1]
[^src: design_&_architecture/decisions/ADR-063.md §A]
