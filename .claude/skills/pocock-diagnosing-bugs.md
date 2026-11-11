---
name: pocock-diagnosing-bugs
description: Diagnosi dei bug difficili e delle regressioni in sei fasi - segnale che va rosso sul bug, ipotesi falsificabili, gate umano prima della correzione, test di regressione. Opt-in engineering_practices. Adattata da mattpocock/skills diagnosing-bugs @49dd158.
---
# Diagnosi dei bug

Pre-condizione: `engineering_practices.enabled: true`. Adattata da `diagnosing-bugs` di Matt
Pocock (MIT, originale in `vendor/mattpocock-skills/skills/engineering/diagnosing-bugs/`). Per
bug difficili, regressioni e lentezze; non per difetti con causa già nota. Le fasi non si
saltano senza dirlo e motivarlo.

## Riservatezza

Comandi, output e artefatti mostrati vanno ripuliti: ogni segreto diventa `<REDACTED>`. Le
credenziali restano nelle variabili d'ambiente, mai nei comandi scritti né nei TSK. Di un
artefatto catturato si citano solo le righe che portano il segnale.

## Fase 1 — Un segnale che va rosso sul bug

È la parte che conta: con un segnale stretto la causa si trova, senza leggere il codice non basta.
Modi di costruirlo, in quest'ordine:

1. **Test che fallisce** al seam che raggiunge il bug (vedi `pocock-tdd`).
2. **Script** che guida l'applicazione e verifica uscita, log o rete.
3. **Replay** di una richiesta o risposta catturata (ripulita) dentro il modulo isolato.
4. **Confronto fra due versioni** (due branch, due build, due ambienti) sullo stesso input.
5. **Bisezione** fra due stati noti con `git bisect run`, in un worktree separato: mai nel
   checkout condiviso, dove lavorano altre sessioni.
6. **Passi manuali guidati**, ultima scelta: se serve una persona, uno script la guida passo per
   passo (modello in `vendor/mattpocock-skills/skills/engineering/diagnosing-bugs/scripts/hitl-loop.template.sh`).

Il segnale va reso stretto: più veloce, più preciso sul sintomo, deterministico (tempo fissato,
rete congelata). Per i bug intermittenti l'obiettivo è alzare il tasso di riproduzione.

**Fatto quando** esiste **un comando**, già lanciato e mostrato, che percorre il codice del bug,
verifica il sintomo esatto riportato, dà sempre lo stesso esito e dura secondi. Se non si riesce
a costruirlo: STOP, si elenca cosa si è provato e si chiede accesso all'ambiente o un artefatto.
Senza segnale non si passa alle ipotesi.

## Fase 2 — Riproduci e riduci

Il segnale va rosso sul sintomo descritto, non su un difetto vicino. Poi si riduce lo scenario
togliendo un elemento alla volta, finché ogni elemento rimasto è necessario.

## Fase 3 — Ipotesi

Da 3 a 5 ipotesi in ordine, ognuna falsificabile: «se la causa è X, cambiando Y il bug sparisce».
Un'ipotesi senza previsione si scarta.

## Fase 4 — Strumenta

Ogni sonda verifica una previsione, una variabile alla volta. Log mirati con un prefisso unico
(`[DEBUG-a4f2]`) da togliere tutti con una ricerca. Per le lentezze: prima la misura di base,
poi la bisezione.

## Gate umano — prima della correzione

Si presentano al Tech Lead, nella sessione principale: il comando della Fase 1 con il suo esito,
le ipotesi in ordine e quella confermata dalla sonda. **La correzione parte solo dopo la sua
conferma.** Un dev-agent che lavora come sub-agente si ferma qui e restituisce questo materiale.

## Fase 5 — Correzione e test di regressione

Il test di regressione si scrive prima della correzione, al seam corretto: quello in cui il test
riproduce il bug come accade davvero. Va rosso, si applica la correzione, va verde, si rilancia
il segnale della Fase 1 sullo scenario originale. Se il seam corretto non esiste, è esso stesso il
risultato: si scrive nel TSK e diventa materiale per `pocock-improve-codebase-architecture`.

Il TSK registra il test nel campo `regression_test:` (path della spec, oppure
`nessun seam corretto: <motivo>`).

## Fase 6 — Pulizia

- [ ] Lo scenario originale non riproduce più il bug.
- [ ] Il test di regressione passa, oppure l'assenza di seam è scritta nel TSK.
- [ ] Nessun `[DEBUG-` rimasto nel codice.
- [ ] Nessun prototipo usa e getta rimasto.
- [ ] Il commit nel repo del cliente rispetta `ai_policy` (`tools/vcs/sm-commit.sh` con
      `suppress_ai_traces: true`) e il messaggio dice la causa trovata, senza ID della factory.
