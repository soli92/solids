# Skill: Semantic Drift Scan Protocol

> Adapter Cursor della skill `semantic-drift-scan-protocol` definita in PATTERN.md.

Metadata skill (originale):
```yaml
name: semantic-drift-scan-protocol
description: "Esegue il semantic drift scan sulla wiki (Check 4af, EP-031 US-108). Sperimentale — opt-in."
status: experimental
epic_id: EP-031
pattern_version: "2.23-candidate"
```

Procedura sperimentale per il semantic drift scan dell'intera wiki rispetto al
PATTERN.md (Check 4af, EP-031 US-108). Invocata dal comando `/semantic-drift-scan`.

**Nota**: questo check è di ricerca. Emette solo INFO nel log; non produce mai
WARNING o ERROR di lint. Non è un gate di pipeline — trigger esclusivamente manuale.

---

## Step 1 — Bootstrap check

1. Leggere `factory.config.yaml`.
2. Verificare `wiki_lint.semantic_check.enabled: true`.
   - Se `false` → **STOP** con messaggio:
     > "Semantic drift scan disabilitato. Attivare `wiki_lint.semantic_check.enabled: true` per procedere."
   - Non procedere oltre.
3. Leggere il modello configurato: `wiki_lint.semantic_check.embedding_model`
   (default `"voyage-3"`).
4. Eseguire un ping leggero all'embedding API per verificarne la disponibilità
   (chiamata minima — es. embed stringa vuota o test token).
   - Se l'API è irraggiungibile o restituisce errore di autenticazione:
     - Emettere WARNING in chat (non ERROR): "Embedding API non raggiungibile —
       semantic drift scan saltato (graceful degradation, check sperimentale)."
     - **STOP** senza fail-loud. Non è un errore bloccante del sistema.
5. Leggere la soglia coseno: `wiki_lint.semantic_check.similarity_threshold`
   (default `0.75`).
6. Leggere il gate costo: `wiki_lint.semantic_check.cost_warn_usd` (default `1.0`).
7. Leggere il path di output: `wiki_lint.semantic_check.output_report_path`
   (default `"code_quality/reports/"`).

---

## Step 2 — Discovery pagine candidate

1. Scansionare `wiki/**/*.md` (glob ricorsivo).
   - Escludere: `wiki/log.md`, `wiki/index.md`, file in `wiki/query/`, `wiki/lint/`.
2. Per ogni file: leggere il frontmatter e cercare il campo `pattern_section: "§N"`.
   - File **con** `pattern_section:` → lista **candidati** (da scansionare).
   - File **senza** `pattern_section:` → lista **non scansionati** (sezione
     separata nel report).
3. Calcolare `N_candidate = len(candidati)`.
4. Stimare il costo totale:
   ```
   costo_stimato = N_candidate × cost_per_call(embedding_model)
   ```
   - Valori di riferimento orientativi (non hardcoded, usare pricing.yaml se presente):
     - `voyage-3`: ~$0.00006 / 1K token; pagina wiki media ~500 token → ~$0.00003/pagina.
     - `text-embedding-3-small`: ~$0.00002 / 1K token.
   - La stima è sul numero di chiamate (1 per pagina + 1 per sezione PATTERN.md);
     arrotondare per eccesso.
5. Se `costo_stimato > wiki_lint.semantic_check.cost_warn_usd`:
   - Mostrare in chat: "Costo stimato: ~$X per N_candidate pagine. Superata soglia
     cost_warn_usd=$Y. Confermare con 'y' per procedere o interrompere con 'n'."
   - **Attendere conferma esplicita** prima di procedere. Se l'utente risponde 'n'
     o non risponde → STOP pulito (nessuna API call effettuata).

---

## Step 3 — Calcolo embedding e similarità

Per ogni pagina candidata (lista di Step 2):

1. Leggere il testo della pagina wiki (intero body, escluso frontmatter).
2. Leggere il campo `pattern_section:` dal frontmatter della pagina (es. `"§5"`).
3. Leggere `PATTERN.md` ed estrarre la sezione corrispondente a `§N`
   (heading `## §N` o `## §N — …` fino al prossimo heading `##`).
   - Se la sezione non è trovata in PATTERN.md: registrare `score = null`,
     motivo `"sezione non trovata in PATTERN.md"`, e passare alla pagina successiva.
4. Calcolare l'embedding della pagina wiki (testo body):
   - `embedding_A = embed(testo_pagina, model=embedding_model)`
5. Calcolare l'embedding della sezione PATTERN.md estratta:
   - `embedding_B = embed(testo_sezione_pattern, model=embedding_model)`
6. Calcolare la similarità coseno:
   ```
   score = dot(embedding_A, embedding_B) / (|embedding_A| × |embedding_B|)
   ```
7. Raccogliere il risultato: `(path, pattern_section, score, last_modified)`.
   - `last_modified`: data ultima modifica del file (filesystem o frontmatter `updated:`).
8. Se un singolo embedding fallisce (errore API transiente):
   - Registrare `score = null`, motivo `"errore API"`.
   - Continuare con la pagina successiva (graceful degradation per-pagina).

Al termine: lista risultati `[(path, pattern_section, score, last_modified), ...]`
con eventuali entry `score = null`.

---

## Step 4 — Produzione report

1. Separare i risultati:
   - `sotto_soglia = [r for r in risultati if r.score is not None and r.score < similarity_threshold]`
   - `sopra_soglia = [r for r in risultati if r.score is not None and r.score >= similarity_threshold]`
   - `errori = [r for r in risultati if r.score is None]`
2. Ordinare `sotto_soglia` per score crescente (primo = più a rischio drift).
3. Ordinare `sopra_soglia` per score decrescente (primo = più allineato).
4. Calcolare statistiche:
   - `score_min`, `score_max`, `score_media` (solo su score non null).
   - `N_scansionate = len(risultati)`.
   - `N_sotto_soglia = len(sotto_soglia)`.
   - `costo_reale` (somma delle chiamate API effettuate — stima o valore da billing
     API se disponibile).
5. Costruire il nome file: `wiki-lint-semantic-YYYY-MM-DD.md`
   (data corrente in formato ISO 8601).
6. Scrivere il report in `<output_report_path>/wiki-lint-semantic-YYYY-MM-DD.md`
   con la struttura seguente:

```markdown
---
type: semantic-drift-report
date: YYYY-MM-DD
epic_id: EP-031
embedding_model: <embedding_model>
similarity_threshold: <similarity_threshold>
---

# Semantic Drift Scan Report — YYYY-MM-DD

> Report sperimentale EP-031 (US-108). Non è un gate di pipeline.
> Severità: INFO only — nessun WARNING/ERROR generato.

## Sommario

| Metrica | Valore |
|---|---|
| Pagine scansionate | N_scansionate |
| Pagine sotto soglia (<threshold) | N_sotto_soglia |
| Score minimo | score_min |
| Score massimo | score_max |
| Score medio | score_media |
| Costo reale stimato | ~$costo_reale |
| Modello embedding | embedding_model |

## Top 5 pagine a rischio drift

> Ordinate per score coseno crescente (score più basso = maggiore rischio deriva).

| Path | Sezione PATTERN | Score | Ultima modifica |
|---|---|---|---|
| path | §N | 0.XX | YYYY-MM-DD |
| ... | ... | ... | ... |

_(Se N_sotto_soglia < 5, mostrare tutte quelle disponibili.)_

## Tabella completa pagine sotto soglia

| Path | Sezione PATTERN | Score | Ultima modifica |
|---|---|---|---|
| path | §N | 0.XX | YYYY-MM-DD |
| ... | ... | ... | ... |

_(Vuota se N_sotto_soglia == 0: nessuna pagina sotto soglia — ottimo risultato.)_

## Pagine non scansionate (senza `pattern_section:`)

Le seguenti pagine wiki non hanno il campo `pattern_section:` nel frontmatter
e sono quindi escluse dal semantic drift scan. Valutare se aggiungere il campo
per includerle nei prossimi scan.

- path/pagina-1.md
- path/pagina-2.md
- ...

_(Vuota se tutte le pagine hanno `pattern_section:`.)_

## Raccomandazioni

1. **Aggiornare le pagine sotto soglia con score < 0.60**: revisione manuale
   prioritaria. Allineare contenuto alla sezione PATTERN.md referenziata.
2. **Aggiungere `pattern_section:` alle pagine non scansionate**: il campo
   permette di monitorare la deriva nel tempo. Vedi `wiki/runbooks/semantic-drift-prerequisites.md`.
3. **Calibrare la soglia `similarity_threshold`**: il valore 0.75 è un default
   iniziale. Dopo ≥3 scan, valutare abbassamento/rialzo basato sulla distribuzione
   osservata (US-108 §calibrazione).
4. **Pianificare un secondo scan post-revisione**: dopo aver aggiornato le pagine
   a rischio, eseguire `/semantic-drift-scan` per verificare il miglioramento.
5. **Segnalare falsi positivi**: se una pagina ha score basso ma il contenuto
   è corretto, annotare nella sezione "Falsi positivi segnalati" di questo report
   per calibrare future soglie.

## Falsi positivi segnalati

> Template annotazione per calibrazione. Compilare manualmente dopo revisione.

| Path | Sezione PATTERN | Score | Motivo falso positivo | Data segnalazione |
|---|---|---|---|---|
| _(nessuno segnalato)_ | | | | |

Per segnalare un falso positivo, aggiungere una riga con:
- **Path**: path relativo della pagina wiki.
- **Sezione PATTERN**: sezione §N referenziata.
- **Score**: score coseno ottenuto.
- **Motivo**: spiegazione del perché il contenuto è corretto nonostante il basso score
  (es. vocabolario divergente intenzionale, sezione PATTERN riscritta recentemente).
- **Data segnalazione**: YYYY-MM-DD.

I falsi positivi raccolti alimentano la calibrazione della soglia coseno
(US-109 ADR go/no-go).
```

7. Se `wiki_lint.semantic_check.output_report` è `false`: non scrivere il file
   ma restituire il report come testo in chat.

---

## Step 5 — Log e output

1. Appendere a `wiki/log.md` la seguente entry (formato canonico):
   ```
   [YYYY-MM-DD HH:MM] semantic-drift-scan — N_scansionate pagine, N_sotto_soglia sotto soglia, costo ~$costo_reale
   ```
2. Restituire all'orchestratore o in chat:
   - Path completo del report (se scritto su disco).
   - Sommario testuale: N_scansionate, N_sotto_soglia, score_min/max/media, costo_reale.
   - Lista Top 5 pagine a rischio (path + score).
   - Eventuale lista pagine con errori API (score null).
