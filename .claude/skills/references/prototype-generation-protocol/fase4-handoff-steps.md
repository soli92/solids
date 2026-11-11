# Fase 4 — Handoff: dettaglio Steps 4.1, 4.5, 4.6, 4.7

**Ambito**: template log entry (Step 4.1), tabella suggerimenti per backend (Step 4.5),
segnale push EP-033 (Step 4.6), formato output finale (Step 4.7). Steps 4.2/4.3/4.4
restano nel corpo della skill (gate determinanti). Va letta prima di emettere suggerimenti
downstream (dopo Step 4.4).

---

## Step 4.1 — Template log entry

Determina il path del log:
- Se `prototyping_config.log_path` è valorizzato → usa quel path.
- Altrimenti → default `wiki/log.md`.

Append al log (append-only, mai editare entry passate):

```
## YYYY-MM-DD HH:MM — prototype <TSK-id | US-id | "intent">
**Backend:** <selected_backend> (<resolved_marker>)
**Artefatto:** <output_ref>
**Spec source:** <spec_source | "none (intent only)">
**Art-director:** <art_director_active>
**States covered:** <states_covered list — da artifact_metadata>
**Suggerimenti emessi:** <N> (elenco comandi, o "nessuno — oracle_handoff: false")
**Files touched:** 1 (<output_ref> [NEW])
```

Usa la data corrente nel formato ISO-8601 locale (YYYY-MM-DD HH:MM). Il log entry
viene scritto **sempre**, indipendentemente dal valore di `oracle_handoff`.

---

## Step 4.5 — Suggerimenti per backend

Determina i suggerimenti candidati in funzione del `selected_backend` risolto in Fase 0:

| Backend | Suggerimenti candidati (emessi solo se comando installato e gate config attivo) |
|---|---|
| `html` | `/visual-oracle` (sempre · verifica rendering) · `/functional-oracle` (se `artifact_metadata.states_covered` ha più di un elemento) · `/ux-ui-review` (sempre) · `/a11y` (sempre) |
| `react` | `/visual-oracle` (sempre) · `/functional-oracle` (sempre) · `/review` (se `code_quality.enabled: true`) · `/a11y` (sempre) · handoff narrativo a `fe-dev` (scaffold consumabile) |
| `figma` | `/ux-ui-review` (sempre) · round-trip `figma-sync` (narrativo: "eseguire `/figma-sync` per re-ingest del file Figma aggiornato") · revisione manuale nel file Figma (`output_ref`) |
| `penpot` | `/ux-ui-review` (sempre) · revisione manuale nel file Penpot (`output_ref`) |

**Gate config per suggerimento** (verifica flag in `factory.config.yaml` prima di emettere):

| Suggerimento | Flag richiesto |
|---|---|
| `/visual-oracle` | `fe_correctness.enabled: true` |
| `/functional-oracle` | `fe_correctness.functional_oracle.enabled: true` |
| `/ux-ui-review` | `ux_ui.enabled: true` |
| `/a11y` | `a11y.enabled: true` |
| `/review` | `code_quality.enabled: true` |

Se il flag è `false` (o assente): suggerimento soppresso silenziosamente.
Se il flag è `true` ma il comando non è installato (Step 4.4 nel corpo): suggerimento soppresso.
Se entrambi i gate sono superati: suggerimento emesso.

I suggerimenti narrativi (handoff `fe-dev`, round-trip `figma-sync`, revisione manuale)
non sono legati a flag config — vengono emessi se il comando di riferimento è installato
o se si tratta di un'azione narrativa (non un comando `/`).

---

## Step 4.6 — Segnale push EP-033

Questo step implementa la regola EP-033 per il `prototype-generation-protocol`
(PATTERN §26 + `wiki/syntheses/ep-035-prototype-generation-integration.md §Runtime suggestions`).

**Trigger** (valutato dall'orchestrator — la skill emette il segnale come push leggibile):

```
SE prototyping.enabled: true
E lo sprint corrente include TSK con layer=fe
E quei TSK hanno design-spec.md associata (campo design_source valorizzato o
  file design-spec.md presente nella dir US)
E nessun prototipo recente è registrato in wiki/log.md per quella US nella
  sessione corrente (verifica per us_id)
→ emetti il segnale push:
  "[EP-033 push] Rilevati TSK FE con spec ma senza prototipo recente per <US-id>.
   Considera: /prototype <US-id>"
```

Il segnale è **non-bloccante e informativo**: non interrompe il flusso, non richiede
conferma, non blocca la chiusura della Fase 4. Viene emesso in chat come suggerimento
(stile EP-033 `## Suggerimento post-esecuzione`), non nel log.

**Gate**: il segnale è soppresso se `prototyping.enabled: false` (default R.P3) o se
il comando `/prototype` non è installato (`.claude/commands/prototype.md` assente).

---

## Step 4.7 — Formato output Fase 4

Emetti in chat il blocco di chiusura Fase 4:

```
[Fase 4] Prototipo registrato: <output_ref>
Log: <log_path> (entry appended)

Passi successivi disponibili:
- `/<comando>` — <motivazione breve, max 1 riga, specifica per il backend>.
[... un suggerimento per riga, solo quelli che hanno superato tutti i gate ...]
```

Se 0 suggerimenti superano i gate (tutti soppressi o `oracle_handoff: false`):

```
[Fase 4] Prototipo registrato: <output_ref>
Log: <log_path> (entry appended)
Nessun suggerimento downstream disponibile (capability non attivate o oracle_handoff: false).
```

Tono: sempre "disponibili", "considera", "potresti" — mai imperativo ("devi", "è richiesto").
La Fase 4 è informativa, non è un gate bloccante.

[^src: .claude/skills/prototype-generation-protocol.md §Fase 4 — Handoff]
[^src: wiki/syntheses/ep-035-prototype-generation-integration.md §Oracle handoff (Fase 4) §Runtime suggestions (EP-033)]
[^src: .claude/skills/dev-handoff.md §Suggerimento post-esecuzione (EP-033) §Gate installazione]
