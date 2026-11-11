# Step 3-bis — Critic/Judge Design + Intention Economy (dettaglio completo)

Ambito: dettaglio del Step 3-bis di `ux-ui-review-protocol.md`. Leggere prima di eseguire
il passo. Condizionale: solo se `design_intelligence.critic_enabled: true`.

---

## Trigger e prerequisiti

**Trigger**: eseguire questo step **SOLO** se `factory.config.yaml.design_intelligence.critic_enabled: true`.
A flag spento (default): **SKIP** — procedere direttamente allo Step 4 (no-op totale, R.P3).

**Prerequisito**: screenshot disponibili dallo Step 1 (modalità visiva). In modalità `no-visual`
→ il passo è **SKIPPED** automaticamente (non valutabile senza render).

## Regole vincolanti

**Regola R.D3** (ADR-070 §C, ADR-071): il Critic/Judge Design è uno **strumento di refinement,
NON un oracolo**. Le critiche alimentano il loop di refinement ma **non emettono un verdict
deterministico** di «design buono/cattivo». La correlazione con il giudizio di un designer umano
non è garantita — ancorare a checkpoint umani periodici. Ogni finding **deve** avere evidenza
visiva concreta (`evidence_zone`): finding senza evidenza → rigettato (guard evidence-provenance,
ADR-063 §B).

**Confine EP-005** (dichiarare nel report verbatim):

> «Scope: qualità visiva del design (6 principi di qualità); NON correttezza funzionale FE
> (Visual Oracle EP-005, che emette verdict deterministico su asserzioni binarie).
> Il Visual Oracle e il Critic/Judge sono capability distinte — runtime di cattura condiviso,
> scopo e output distinti (ADR-070 §A).»

## 6 dimensioni di qualità visiva (ADR-070 §D)

| dim_id | Principio | Domanda critica |
|---|---|---|
| `critic-gerarchia` | Gerarchia visiva | L'occhio segue l'ordine di importanza dichiarato nel `design_rationale`? |
| `critic-contrasto` | Contrasto visivo | Le distinzioni figura/sfondo, primario/secondario, attivo/inattivo sono percepibili? |
| `critic-allineamento` | Allineamento | Gli elementi sono allineati in modo coerente? Il grid system è rispettato? |
| `critic-ritmo` | Ritmo / Spaziatura | La spaziatura segue il ritmo del design system? Il bilanciamento bianco/contenuto è equilibrato? |
| `critic-spaziatura` | Densità informativa | Il contenuto è adeguatamente aerato? Nessun affollamento visivo? |
| `critic-coerenza-tema` | Coerenza col tema | I token applicati corrispondono all'`art_director_spec`? Deviazioni documentate nel `design_rationale`? |

## Schema finding Critic/Judge

```json
{
  "principle": "critic-gerarchia|critic-contrasto|critic-allineamento|critic-ritmo|critic-spaziatura|critic-coerenza-tema",
  "evidence_zone": "<region of screenshot + description>",
  "rationale_ref": "<campo del design_rationale violato o assente>",
  "severity": "critical|major|minor",
  "description": "<osservazione concreta>",
  "recommendation": "<proposta di refinement>",
  "is_refinement_suggestion": true
}
```

- `evidence_zone` **obbligatorio e non nullable** — finding senza → rigettato.
- `rationale_ref` dovrebbe puntare a un campo specifico del `design_rationale`. Se
  `design_rationale` non è disponibile → `"design_rationale: non disponibile"`.
- `is_refinement_suggestion: true` sempre (R.D3: advisory, non verdict deterministico).

**Bounded loop** (ADR-070 §D): ciclo critic → fix → re-review bounded da
`ux_ui.max_iterations` (default 3). Su reject del Critic/Judge → richiedere una
**nuova spec** all'LLM (ADR-069 §E), non riscrivere il template.

**Output**: `critic_findings[]`, inseriti nel report Step 5 in sezione separata
`critic_judge_section`. **Non** vanno in `findings[]` della rubrica principale.

**Criterio di completamento**: le 6 dimensioni valutate; ogni finding con `evidence_zone`
e `is_refinement_suggestion: true`; confine EP-005 dichiarato; R.D3 applicato.

---

## Sotto-dimensione — Intention Economy / Resolution Velocity (condizionale)

**Trigger**: eseguire **SOLO** se `factory.config.yaml.design_intelligence.rubric_intention_economy: true`.
A flag spento (default `false`): **SKIP** — no-op totale (backward compat EP-008, R.P3).

**Nota**: l'Intention Economy è una **sotto-dimensione qualitativa** del Critic/Judge, **NON**
una formula matematica. La formula `RV = step_count / completed_intentions` è **respinta**
(ADR-070 §E: US-077 prescrive esplicitamente «non è una formula matematica in v1»).

**3 domande operative** (checklist obbligatoria, risposta sì/no + evidenza):

1. **Riduzione passi** — questa scelta riduce il numero di step per completare l'azione comune
   dell'utente? *(sì: positivo | no: potenziale warn | non applicabile: annotare)*
2. **Eliminazione elementi distrattivi** — questa scelta elimina elementi decorativi o
   distrattivi che rallentano lettura/navigazione? *(sì: positivo | no: potenziale warn)*
3. **Chiarezza su novità** — questa scelta preferisce chiarezza e prevedibilità rispetto
   a novità visiva? *(sì: positivo | no: possibile fail se la novità non è giustificata)*

**Verdict `intention_economy`** (qualitativo):

| Verdict | Criteri |
|---|---|
| `pass` | Tutte e 3 le risposte positive, o le risposte negative hanno rationale esplicito |
| `warn` | 1 risposta negativa senza rationale sufficiente, o `resolution_velocity_impact` assente |
| `fail` | 2+ risposte negative senza rationale, o presenza di anti-pattern engagement |

**Anti-pattern obbligatorio — Attention Economy** (ADR-070 §E): qualsiasi rationale che
giustifica una scelta con metriche di **engagement** (tempo sul sito, click-through, novità
visiva, "gamification dell'attenzione") → **finding `major`** automatico con nota:
`"criterio obsoleto, attention economy — rigettato. La scelta deve essere giustificata
con criteri di chiarezza/prevedibilità/riduzione di passi (intention economy paradigm 2026)."`

**Schema output** (aggiunto a `intention_economy_section` nel report Step 5):

```json
{
  "intention_economy_verdict": "pass|warn|fail",
  "questions": [
    {"q": "riduzione_passi", "answer": "yes|no|na", "evidence": "<...>"},
    {"q": "eliminazione_distrattivi", "answer": "yes|no|na", "evidence": "<...>"},
    {"q": "chiarezza_su_novita", "answer": "yes|no|na", "evidence": "<...>"}
  ],
  "resolution_velocity_impact_ref": "<design_rationale.consequences.resolution_velocity_impact o 'non disponibile'>",
  "attention_economy_finding": null
}
```

`intention_economy_section` nel report è `null` se il flag è spento.

[^src: design_&_architecture/decisions/ADR-070.md §A §B §C §D §E]
[^src: management/kanban/EP-019-design-intelligence-layer/US-076-critic-judge-design-rubrica-ux-ui-review/TSK-172.md §Technical Specs]
[^src: management/kanban/EP-019-design-intelligence-layer/US-077-intention-economy-resolution-velocity-rubrica/TSK-173.md §Technical Specs]
