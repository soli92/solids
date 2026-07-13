---
name: semantic-drift-scan
description: "Esegue il semantic drift scan sulla wiki (sperimentale, EP-031 US-108). Trigger manuale — non automatico. Non è un gate di pipeline."
---

# /semantic-drift-scan

Comando sperimentale EP-031 (US-108). Esegue il semantic drift scan sull'intera
wiki confrontando ogni pagina con `pattern_section:` dichiarato vs. la sezione
corrispondente di `PATTERN.md` tramite embedding e similarità coseno.

**Trigger manuale — non automatico. Non è un gate di pipeline.**

Il check emette solo INFO; non genera mai WARNING o ERROR di lint. Non blocca
alcun flusso CI/CD, release o wave dispatch.

---

## Utilizzo

```
/semantic-drift-scan
```

Nessun argomento obbligatorio. Tutti i parametri operativi si leggono da
`factory.config.yaml` (blocco `wiki_lint.semantic_check`).

---

## Comportamento

Il comando invoca la skill [semantic-drift-scan-protocol](mdc:.cursor/skills/semantic-drift-scan-protocol/SKILL.md) (5 step):

1. **Step 1 — Bootstrap check**: verifica che `wiki_lint.semantic_check.enabled: true`
   sia impostato in `factory.config.yaml`. Se `false`, STOP con messaggio esplicito.
   Poi verifica la raggiungibilità dell'embedding API (graceful degradation se
   irraggiungibile — non fail-loud).

2. **Step 2 — Discovery pagine candidate**: scansiona `wiki/**/*.md` e individua
   le pagine con `pattern_section:` nel frontmatter. Stima il costo totale delle
   chiamate API.

3. **Gate di conferma costo**: se il costo stimato supera `wiki_lint.semantic_check.cost_warn_usd`
   (default `$1.00`), il comando **si ferma e mostra la stima**, chiedendo conferma
   esplicita ('y'/'n') prima di effettuare qualsiasi chiamata API. Risposta 'n' o
   assenza → STOP pulito (zero API call).

4. **Step 3 — Calcolo embedding e similarità**: per ogni pagina candidata calcola
   l'embedding del body della pagina e dell'estratto di `PATTERN.md` corrispondente
   alla sezione `§N`, poi la similarità coseno.

5. **Step 4 — Produzione report**: scrive
   `<output_report_path>/wiki-lint-semantic-YYYY-MM-DD.md` con sommario, Top 5 pagine
   a rischio, tabella completa sotto soglia, pagine non scansionate, raccomandazioni
   e template falsi positivi.

6. **Step 5 — Log e output**: appende entry a `wiki/log.md` e restituisce il path
   del report + sommario in chat.

---

## Prerequisiti

Prima di usare questo comando verificare:

1. **`factory.config.yaml`** — il blocco `wiki_lint.semantic_check` deve avere
   `enabled: true`:
   ```yaml
   wiki_lint:
     semantic_check:
       enabled: true           # master switch EP-031 (default false)
       similarity_threshold: 0.75
       embedding_model: "voyage-3"
       cost_warn_usd: 1.0
       output_report: true
       output_report_path: "code_quality/reports/"
   ```

2. **API key embedding**: variabile d'ambiente con la chiave del modello scelto
   (es. `ANTHROPIC_API_KEY` per Voyage via Anthropic, `OPENAI_API_KEY` per
   `text-embedding-3-small`). Vedere `wiki/runbooks/semantic-drift-prerequisites.md`
   per la procedura completa di configurazione.

3. **Pagine wiki con `pattern_section:`**: almeno una pagina wiki deve avere il
   campo `pattern_section: "§N"` nel frontmatter per essere inclusa nella
   scansione. Pagine senza il campo sono elencate nel report come "non scansionate"
   ma non generano errori.

4. **`PATTERN.md` aggiornato**: il file deve contenere le sezioni `§N` referenziate
   dai frontmatter wiki; sezioni assenti producono `score = null` per le pagine
   corrispondenti.

---

## Output prodotto

- **File**: `<output_report_path>/wiki-lint-semantic-YYYY-MM-DD.md`
  (default `code_quality/reports/wiki-lint-semantic-YYYY-MM-DD.md`)
- **Sezioni del report**:
  - Sommario (N scansionate, N sotto soglia, score min/max/media, costo reale)
  - Top 5 pagine a rischio drift (tabella ordinata per score crescente)
  - Tabella completa pagine sotto soglia
  - Pagine non scansionate (senza `pattern_section:`)
  - Raccomandazioni (5 azioni concrete)
  - Falsi positivi segnalati (template annotazione per calibrazione soglia)
- **Log entry**: appesa a `wiki/log.md`

---

## Vincoli e avvertenze

- **Sperimentale**: la soglia 0.75 richiede calibrazione empirica (US-108). I risultati
  vanno interpretati come segnali, non verdetti definitivi.
- **Solo INFO**: il comando non altera lo `status:` di alcun TSK, EP o US. Non
  produce ERROR o WARNING di lint.
- **No auto-trigger**: questo comando non viene mai invocato automaticamente da
  `/run`, dallo scheduler, dalla pipeline CI/CD o da qualsiasi altro meccanismo
  del framework. L'unico trigger è l'invocazione manuale da parte di un maintainer.
- **Costo API reale**: ogni scan consuma token dell'API embedding in proporzione
  al numero di pagine candidate. Stimare sempre prima della conferma.
- **Idempotenza**: scan multipli nello stesso giorno sovrascrivono il report
  con lo stesso nome file (`wiki-lint-semantic-YYYY-MM-DD.md`). Rinominare
  manualmente se si vogliono conservare più run dello stesso giorno.

Vedi [semantic-drift-scan-protocol](mdc:.cursor/skills/semantic-drift-scan-protocol/SKILL.md) per la procedura completa
e `wiki/runbooks/semantic-drift-prerequisites.md` per la configurazione dell'ambiente.
