# Fase 3 — Screenshot multi-viewport/tema, dettaglio

Ambito: matrice viewports × themes, invocazione di `screenshot-capture-protocol`, naming e criteri. Foglia di `.claude/skills/visual-oracle-protocol.md` (testo originale spostato senza modifiche; la spina dorsale resta nella skill e prevale in caso di dubbio).

## Fase 3 — Screenshot Multi-Viewport/Tema

> **Refactor non distruttivo v2.18 (ADR-017)**: la logica di cattura è ora estratta nella
> skill condivisa [`screenshot-capture-protocol`](../../screenshot-capture-protocol.md) (single
> source of truth Playwright, riusata anche da `ux-ui-review-protocol` EP-008). La Fase 3
> **delega** la cattura a quella skill invece di implementarla inline. Il **contratto
> pubblico della Fase 3 è invariato**: stessi PNG, stessa cartella side-channel
> (`code_quality/reports/<TSK-id>-visual-iter-<N>/`), stesso naming, stesso schema dati
> (ADR-012 §H). Chi invoca `/visual-oracle` o consuma la skill non vede differenze (backward
> compat totale — ADR-017 §«Cosa NON cambia»). La risoluzione della matrice `viewports × themes`
> resta nel caller (questa Fase 3), non nella skill condivisa (ADR-017 §Rationale 5).

**Input atteso**: `viewports` + `themes` da `factory.config.yaml.fe_correctness`.

**Azione**:

1. Costruisce la **matrice cartesiana** `viewports × themes`. Default (da ADR-012 §E):
   - `viewports: [{ name: mobile, width: 375 }, { name: desktop, width: 1280 }]`
   - `themes: [light, dark]`
   - → **4 combinazioni**: `mobile-light`, `mobile-dark`, `desktop-light`, `desktop-dark`.
2. **Override da config**: se l'utente valorizza `fe_correctness.viewports` /
   `fe_correctness.themes`, quei valori sono passati direttamente alla skill condivisa (no
   abstraction layer intermedio — ADR-008 §Conseguenze). La matrice può quindi essere
   N viewport × M temi.
3. **INVOCA `screenshot-capture-protocol`** con i parametri risolti (ADR-017 §«Cosa cambia in
   EP-005»):
   ```
   INVOCA screenshot-capture-protocol con:
     target         = <target risolto in Fase 2>
     viewports      = factory.config.yaml.fe_correctness.viewports
     themes         = factory.config.yaml.fe_correctness.themes
     output_dir     = code_quality/reports/<TSK-id>-visual-iter-<N>/
     naming_pattern = "{viewport}-{theme}.png"
   Output: lista screenshot path { viewport, theme, path, bytes } da passare alla Fase 4
           (Critica Visiva).
   ```
   La skill condivisa pilota Playwright via Bash (`page.setViewportSize` per il viewport,
   `page.emulateMedia({ colorScheme })` per il tema, `page.screenshot`) e fail-loud se
   Playwright manca — comportamento identico all'implementazione inline pre-refactor
   (ADR-008 §Decisione, ADR-017 §Rationale 4/6).
4. **Naming convention** (invariata, ora applicata dalla skill condivisa via `naming_pattern`):
   `<viewport>-<theme>.png` (es. `mobile-light.png`, `desktop-dark.png`).

**Output prodotto**: N PNG (N = |viewports| × |themes|) nella cartella
`code_quality/reports/<TSK-id>-visual-iter-<N>/`. Identico al pre-refactor.

**Criterio di completamento**: esistono `|viewports| × |themes|` file PNG nella cartella
artefatti, nominati secondo la convention.

[^src: design_&_architecture/decisions/ADR-008.md §Conseguenze]
[^src: design_&_architecture/decisions/ADR-012.md §E]
[^src: design_&_architecture/decisions/ADR-017.md §«Cosa cambia in EP-005 (refactor non distruttivo)»]
