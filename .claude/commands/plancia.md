---
name: plancia
description: >-
  Avvia la plancia — superficie locale sull'attività della factory (EP-067). Mostra event store,
  sprint, avanzamento delle attività (report PM di EP-070, aggiornato a runtime), sessioni attive
  e costo, ciascuno con la propria fonte e la propria età; permette di
  avviare lavoro, rispondere ai gate umani e accendere il canale vocale, che legge la stessa
  sequenza di eventi dello schermo. Non è uno scrittore: ogni azione è una
  FactoryRuntime.submit(), lo scrittore resta la sessione. Non arbitra la concorrenza. Opt-in via
  visual_channel.enabled.
---
# /plancia

Canale visivo della factory: l'implementazione del canale che il contratto
`FactoryRuntime` dichiara e che finora era «stdout strutturato in MVP»
(`voice-channel-factory` §Interfaccia FactoryRuntime).

**La plancia non è uno scrittore.** Non modifica `wiki/`, non modifica
`management/kanban/`, non cambia nessun `status:`, non scrive in `analytics/`. Le azioni
esistono — avviare lavoro, rispondere a un gate — ma ognuna è una
`FactoryRuntime.submit()`: **lo scrittore resta la sessione**, che resta singola. È il
vincolo che rende sicuro lo stadio di scrittura, non una precauzione (US-288), ed è
verificato sull'AST da un test, non affidato a questa frase.

Runtime irraggiungibile ⇒ i comandi si disabilitano dichiarando la ragione e le viste
continuano a funzionare: **fail-closed in scrittura, fail-open in lettura**.

### Concorrenza — cosa la plancia non fa

Se un'altra sessione risulta attiva sullo stesso repo, la plancia lo **dichiara**, con
l'età dell'osservazione. Non arbitra: **nessun lock, nessun lease, nessun arbitro**. È la
posizione che EP-064 ha raggiunto sul kanban dopo averne misurato il costo, e qui non si
ri-delibera.

La plancia **non impedisce** il conflitto e **non garantisce** alcuna latenza: la
visibilità è al ciclo di scrittura dei claim, quindi **minuti, non secondi**.

## Uso

```bash
python3 -m visual                      # avvia sulla porta configurata
python3 -m visual --check              # configurazione risolta, senza avviare
python3 -m visual --port 9000          # porta esplicita
python3 -m visual --root ../altra-factory   # osserva una factory derivata
python3 -m visual --force              # avvia anche a gate spento
```

## Azioni

Le azioni offerte sono **derivate dalle capability dichiarate** in
`factory.config.yaml`, non da un elenco scritto a mano: accendere una capability la fa
comparire senza toccare la plancia. Ogni azione difficile da annullare richiede una
conferma che **descrive la conseguenza** — non chiede «sei sicuro».

Un turno alla volta: due turni paralleli dalla stessa superficie sarebbero due richieste
concorrenti alla stessa sessione. Le direttive inviate sono tracciate **in memoria** con
l'origine `canale-visivo`; il record durevole lo produce la sessione eseguendo la
direttiva, perché scriverlo qui violerebbe US-288.

Arresto: `Ctrl-C` oppure `kill`. La porta è rilasciata entro 5 s e non resta
nessuno stato su disco — dopo un `kill -9` il riavvio immediato riesce.

## Cosa mostra

| riquadro | fonte |
|---|---|
| `events` | `analytics/events/*.jsonl` |
| `sprint` | `management/kanban/` |
| `coordinamento` | `tools/coordinamento/run.py` (report PM, EP-070) |
| `sessions` | `memory/active-sessions.yaml` |
| `tokens` | `tools/analytics/statusline-ledger.py --json` |
| `cost_alert` | `tools/analytics/cost_alert.py check --json` (soglie, alert pendenti, note) |

Ogni lettura porta **la propria fonte e la propria età**. Una fonte illeggibile
produce «non osservabile» con la ragione, **mai uno zero**: le due cose si leggono
uguali e significano l'opposto. Un dato oltre `stale_after_seconds` è marcato stantio
anziché nascosto.

### Avanzamento delle attività (report PM)

Il riquadro `coordinamento` porta in plancia il report PM di EP-070: avanzamento per
obiettivo ed epica, avvisi dalle regole, provenienza e qualità del dato, e un link al
**report completo** (la vista HTML del motore, servita su `/coordinamento/vista`).

- **I numeri sono del motore**, già passati dalla verifica L0: la plancia non ne calcola
  nessuno. Uno scostamento L0 svuota il riquadro («nessun numero mostrato»), non lascia
  in pagina l'ultimo valore buono.
- **Si aggiorna a runtime, ma solo quando serve.** La pipeline costa secondi; ogni 15 s
  la plancia ricontrolla l'impronta di ciò che il motore legge (HEAD, file del kanban,
  config, store, data) e la rilancia solo se è cambiata. Con `fonte: worktree` un
  `status:` modificato compare entro ~20 s, senza commit.
- **Non vede il lavoro degli altri prima del push**: la visibilità resta al ciclo di push,
  quindi minuti.
- **Non scrive nella factory.** Le uscite del motore (snapshot, misura, HTML) vanno in una
  cartella temporanea fuori dal repo, non in `deliverables/`.
- Richiede `pm_report.enabled: true` e una config operatore
  (`analytics/coordinamento/config-<git user.name>.json`, o quella indicata in
  `visual_channel.coordinamento.config`). In mancanza, il riquadro dice cosa manca.

## Configurazione

```yaml
visual_channel:
  enabled: false                # opt-in
  host: 127.0.0.1               # solo loopback
  port: 8756
  runtime_timeout_seconds: 300  # quanto attende una direttiva prima di dichiararla scaduta
  stale_after_seconds: 120      # oltre questa età una lettura è marcata «dato stantio»
  coordinamento:                # riquadro «Avanzamento delle attività» (EP-070)
    fonte: worktree             # worktree (anche non committato) | commit (solo HEAD)
    config: analytics/coordinamento/config-<operatore>.json   # opzionale
```

Il canale vocale riusa il blocco `voice_channel:` del Voice Channel (EP-041): stesso
runtime, stessi parametri. Una seconda configurazione sarebbe una seconda verità sullo
stesso oggetto.

A gate spento il comando esce con codice **0** e spiega come abilitarlo: fallback
esplicito, non un errore. Zero dipendenze esterne.

## Canale vocale

Il canale audio non è un secondo sistema: è **lo stesso flusso di eventi** letto da un
secondo consumatore, agganciato al `Tee` costruito per la parità (US-295). Voce e schermo
non hanno due verità da riconciliare — hanno una sequenza e due rese.

Si accende dalla plancia, sezione **Canali**, oppure:

```bash
curl -X POST -H 'Content-Type: application/json' -d '{"attiva":true}' \
     http://127.0.0.1:8756/api/voce
```

**Gli artefatti non vengono mai pronunciati.** Il filtro è `visual.channel.tts_payload` —
lo *stesso* che il canale visivo usa per decidere cosa sarebbe pronunciabile: una seconda
copia della regola sarebbe una seconda occasione di sbagliarla. La plancia conta quante
volte l'invariante ha lavorato e lo mostra («N artefatti non pronunciati»).

Il modello TTS si carica alla **prima attivazione**, non all'avvio: chi non usa la voce non
ne paga il costo, e la plancia parte in un secondo anche su una macchina senza. Se manca un
prerequisito il comando è disabilitato e dice **quale**.

## Mascotte

Indicatore di stato **non testuale e ridondante**: nove stati della factory su nove
espressioni, tabella dichiarata in `visual/static/mascotte.js`.

**Non è un canale di accesso.** È sempre `aria-hidden` — per uno screen reader la
mascotte non esiste, ed è il trattamento corretto per contenuto decorativo. Ogni stato che
mostra è scritto anche in chiaro accanto al titolo, e un test verifica che il testo sia
prodotto *prima* del ramo che decide se disegnare: spegnere la mascotte non deve poter
spegnere l'informazione. Si nasconde con un comando, la scelta persiste, e rispetta
`prefers-reduced-motion`.

Il default è disegnato **in codice** (SVG): nessun asset esterno, nessuna rete, nessun
binario versionato. Per usare fogli veri si passano due sprite sheet 3×3 — stesso
contratto di [`nilbuild/page-mascot`](https://github.com/nilbuild/page-mascot) (MIT), da
cui viene la tecnica. Per generarne di nuovi c'è il backend `mascot` del Prototype
Generation Layer:

```bash
python3 tools/prototype/mascot-backend.py probe              # disponibile?
python3 tools/prototype/mascot-backend.py verify <dir>       # i due fogli si allineano?
python3 tools/prototype/mascot-backend.py reproduce          # gli artefatti si rigenerano?
```

`verify` è un **gate**, non un rapporto: due fogli che non si allineano non vengono
accettati. `reproduce` esiste perché l'anti-pattern misurato a monte — 41 artefatti su 58
non riproducibili dai propri sorgenti — non entri qui.

## Accessibilità

WCAG 2.2 AA è nella definizione di fatto, non in una revisione a valle (US-282):
contrasto AAA in entrambi i temi, navigazione completa da tastiera, bersagli ≥44 px,
regione live per ogni transizione di stato senza spostare il focus, nessuna
informazione veicolata dal solo colore. Verificato: **axe 0 critical / 0 major / 0 minor**, più **17 check deterministici**
(`tools/a11y/target-checks.mjs`) sui cinque criteri che axe restituisce come manuali.

**Il verde non dice «accessibile».** Dice «nessuna violazione rilevata su N criteri».
Restano fuori la comprensibilità del linguaggio — non si misura in un browser — e
l'esperienza reale con una tecnologia assistiva: **US-287, bloccata su
[Q-007](../../management/questions.md)**, perché serve una persona.

## Le tre età

Ogni misura dichiara **la fonte**, **l'età della lettura** e **l'età del dato**. Sono cose
distinte: «letto 0 s fa» su un event store fermo da due giorni è vero e inutile. Se leggi
`dato di 48 h fa`, la fonte è viva e il contenuto no.

Una fonte illeggibile dice **«non osservabile» con la ragione**, mai `0`: «misurato, ed è
zero» e «non lo so» si leggono uguali e significano l'opposto.

I riquadri **Sessione in corso** e **Attività registrata** rispondono a domande diverse, ed
è il motivo per cui esistono entrambi. L'event store registra l'esecuzione formale dei TSK
— `dev-protocol`, `parallel-scheduling` e `dev-handoff` chiamano `record-event.py`. Il
lavoro fatto fuori da quella pipeline non ci finisce: un dato vecchio lì con una sessione
attiva **non è un guasto**.

## Quando qualcosa non risponde

| sintomo | causa | rimedio |
|---|---|---|
| Esce «opt-in ed è spenta» e termina con 0 | `visual_channel.enabled: false` | usa `--force`, o accendi il flag in una factory derivata |
| «la porta N è occupata» | un'altra istanza, o un altro servizio | il messaggio propone la prima porta libera |
| Un riquadro dice «non osservabile» | quella fonte non è leggibile | la ragione è scritta nel riquadro: leggila, non indovinare |
| «Attività registrata» ferma da giorni | nessun TSK è passato da `dev-protocol` | normale — guarda «Sessione in corso» |
| «Sessione in corso» non osservabile | il transcript del runtime non è dove la plancia lo cerca | verifica che la radice osservata sia quella della sessione |
| I comandi sono disabilitati | runtime non raggiungibile | la ragione è nella sezione Comandi |
| Un turno resta «in attesa» | con `ClaudeCodeAdapter` gli avanzamenti arrivano (TSK-689); con gli altri cinque adapter no, perché non fanno streaming | la barra dice da quanto attende e quanto manca alla scadenza, e il dettaglio del turno viene comunque letto dal transcript |

### Esporla in rete

`host: 127.0.0.1` è il default e va lasciato tale salvo decisione esplicita. La plancia è in
sola lettura, ma mostra kanban, telemetria e costi: metterla su `0.0.0.0` la rende leggibile
a chiunque sia sulla rete locale.

## Perché non c'è ancora un runbook né una sezione in PATTERN.md

Non è una dimenticanza. `PATTERN.md` §23.8 vieta a una capability **nel bucket di ingresso**
— cioè nuova, fuori dall'allowlist di grandfathering — di arrivare con la cerimonia in mano:
sezione PATTERN, invariante §7, lint check, runbook o concept page **prima di un artefatto di
esercizio**. Il divieto è a severità ERROR e lo verifica
`tests/test_fleet_contract.py::test_asse4_nessuna_capability_nel_bucket_di_ingresso_porta_cerimonia`.

Il caso che ha reso necessaria la regola è EP-061, che spedì una capability a flag spento con
§37, runbook, concept page, dieci invarianti e uno schema JSON — «ho confuso un interruttore
di runtime con uno stadio di maturità».

Questo file **non è cerimonia**: è la documentazione del comando, ed è dove sta cio' che
serve per usarlo. Runbook e sezione PATTERN arrivano quando la capability è stata esercitata.
