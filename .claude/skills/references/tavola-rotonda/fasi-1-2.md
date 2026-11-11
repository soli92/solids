# Fase 1 e Fase 2 — procedura dettagliata

**Ambito**: passi di Fase 1 (posizioni iniziali) e Fase 2 (confronto) del Protocollo Tavola Rotonda.
**Gate**: Fase 1 attivata dopo Fase 0; Fase 2 attivata dopo Fase 1 (o loop da Fase 3).
**Riferimento origine**: `.claude/skills/tavola-rotonda-protocol.md` §Fase 1 e §Fase 2.
**Esecutore (ADR-EP073-001)**: la sessione principale che ha invocato `/tavola-rotonda`, nel ruolo di
moderatore (il subagente `tavola-rotonda-moderatore` non lancia sub-agenti da Claude Code
2.1.289). Dove sotto si legge «il moderatore», si intende chi esegue queste fasi.

---

## Fase 1 — Posizioni iniziali indipendenti

**Input**: blackboard con `stato: fase1`, topic riformulato, criteri di successo, lista
partecipanti verificata, ruolo Critico assegnato.

Il meccanismo anti-groupthink si basa interamente sull'indipendenza delle posizioni in
questa fase. Riferimento: concept [[multi-agent-debate]] (letteratura MoA, isolamento
proposers) e PATTERN §28.

### Passo 1 — Lancia i partecipanti in parallelo

Usa il tool `Agent` (`subagent_type` = slug del partecipante) per lanciare ogni partecipante
in un sub-agente isolato, con il prompt di Fase 1 restituito dal moderatore in `setup`. Ogni
sub-agente riceve **esattamente** questo contesto — e nient'altro:

- Il testo riformulato del problema (Fase 0 Passo 1)
- I criteri di successo (Fase 0 Passo 2)
- Il proprio ruolo assegnato — es.:
  - Per partecipante standard: «Sei il `lead-architect`. Produce una posizione
    indipendente sul problema. Non conosci le posizioni degli altri partecipanti.»
  - Per il Critico: «Sei il `qa-dev` nel ruolo Critico. Il tuo mandato è identificare
    rischi strutturali e debolezze nelle soluzioni possibili. Non convergere per
    default — se hai riserve reali, esprimile con argomentazione esplicita.»

Il contesto è **identico** per tutti (stesso topic, stessi criteri di successo). Solo
il ruolo varia. Il moderatore NON passa il file blackboard in questa fase.

**WARNING**: il moderatore NON deve condividere la risposta di nessun partecipante
prima che tutti abbiano risposto. Farlo viola R.TR1 — la sessione deve essere
riavviata da Fase 0.

### Passo 2 — Trascrivi le posizioni nel blackboard

Dopo che **tutti** i partecipanti hanno risposto, il moderatore trascrive le posizioni
nella sezione `## Posizioni Fase 1` del blackboard. Per ogni partecipante, aggiunge
una subsection di livello 3 nel formato prescritto da ADR-EP039-001:

```markdown
### <agent-slug> — <ISO8601-timestamp> — agent_id <id>

<posizione integrale — trascrizione verbatim, nessun riassunto>
```

Per ogni lancio aggiungi nel frontmatter una voce `lanci`
(`{agente: <slug>, fase: 1, round: 0, agent_id: <id>}`) e aggiorna `partecipanti_lanciati`.
Un partecipante il cui lancio fallisce resta senza posizione (scritto come assente): la sua
posizione non si ricostruisce (R.TR9).

**Regola verbatim**: le posizioni vengono trascritte integralmente, senza riassunti né
parafrasi. Il riassunto introduce distorsione e viola R.TR5 (no anchoring moderatore).

**Immutabilità post-scrittura**: il contenuto di `## Posizioni Fase 1` non viene
modificato nei round successivi. Resta come audit trail storico dell'indipendenza
delle posizioni iniziali (ADR-EP039-001 §Tre sezioni obbligatorie).

### Passo 3 — Transizione a Fase 2

Aggiorna il frontmatter del blackboard: `stato: fase2`, `round_corrente: 1`
(ADR-EP039-001 §Ciclo di vita del frontmatter).

**Output Fase 1**: sezione `## Posizioni Fase 1` popolata con N subsections (una per
agente, heading `### <slug> — <ISO8601>`, posizione verbatim). Frontmatter aggiornato:
`stato: fase2`, `round_corrente: 1`.

---

## Fase 2 — Confronto

**Input**: blackboard con `stato: fase2`, sezione `## Posizioni Fase 1` popolata,
`round_corrente ≥ 1`.

In questa fase il moderatore rende visibili le posizioni accumulate a tutti i
partecipanti. Ogni agente produce critiche, integrazioni e rischi sulle proposte altrui.
Tutto il traffico degli interventi passa dalla lavagna: il moderatore è il solo writer
del blackboard (R.TR2); i partecipanti non si scambiano messaggi direttamente.

### Passo 1 — Condividi le posizioni del blackboard

Condividi con tutti i partecipanti il contenuto del blackboard rilevante al round
corrente:

- **Round 1**: passa `## Posizioni Fase 1` (accordi e punti aperti sono ancora vuoti).
- **Round N > 1**: passa l'intero blackboard (`## Posizioni Fase 1` come audit trail
  storico + `## Accordi (congelati)` + `## Punti Aperti` aggiornati al round precedente).

Regola: ogni partecipante deve avere la stessa snapshot del blackboard prima di
produrre il suo intervento nel round corrente.

### Passo 2 — Convoca il Critico (priorità di intervento)

Lancia il Critico come sub-task **prima** degli altri. Il sub-task riceve:
- Il blackboard corrente (dal Passo 1)
- Il mandato esplicito del Critico: «identifica rischi strutturali, debolezze
  argomentative e punti di disaccordo nelle proposte. Non convergere per default —
  se hai riserve reali, esprimile con argomentazione esplicita.»

Attendi la risposta del Critico prima di procedere al Passo 3.

### Passo 3 — Convoca gli altri partecipanti (in parallelo)

Dopo aver ricevuto la risposta del Critico, convoca gli altri partecipanti in parallelo
(tool `Agent`). Ogni sub-agente riceve:
- Il blackboard corrente (dal Passo 1)
- L'intervento del Critico già disponibile
- Il mandato: «produci integrazioni, contro-argomenti, rischi aggiuntivi o accordi
  parziali sulle proposte altrui. Porta nuova evidenza o argomentazione; non ripetere
  posizioni già espresse senza sviluppo.»

### Passo 4 — Trascrivi gli interventi nel blackboard

Il moderatore trascrive verbatim sotto `## Punti Aperti` gli interventi del round
corrente, come sotto-voci taggate:

```markdown
- [Round <N> — <agent-slug> — agent_id <id>] <intervento verbatim>
```

Ogni lancio del round aggiunge una voce `lanci` (`fase: 2, round: <N>`).

Regole di trascrizione:
- Verbatim: nessuna sintesi, parafrasi o omissione (R.TR5 — no anchoring moderatore).
- Il Critico viene trascritto per primo, nell'ordine in cui ha risposto.
- Nuovi rischi o punti emersi dagli interventi vengono aggiunti come voci separate.
- Il moderatore NON decide nel merito: non filtra, non commenta, non valuta.

### Passo 5 — Aggiorna il frontmatter: `stato: fase3`

Aggiorna il frontmatter del blackboard: `stato: fase3`.

**Output Fase 2**: `## Punti Aperti` arricchito con gli interventi del round corrente
(voci taggate `[Round N — <agent-slug>]`). `stato: fase3`.
