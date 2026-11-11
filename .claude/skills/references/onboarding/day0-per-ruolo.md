# Day 0 per ruolo

Letto da `tools/onboarding/day0.py` (percorso configurabile con `onboarding_day0.file`): una
sezione `## <ruolo>` per ogni ruolo di `onboarding_day0.roles` (o dell'elenco neutro di
`tools/promemoria/promemoria.py`), più `## generico` per chi salta la domanda. Ogni sezione ha al
massimo tre azioni: il resto è nel piano di lettura della wiki. Il ruolo sceglie solo questo
testo, non dà permessi.

**Esempio neutro.** Questo file è un punto di partenza: la factory lo sostituisce con i propri
ruoli e i propri comandi (stesso formato, stessi slug di `onboarding_day0.roles`).

## sviluppo

1. Apri `management/kanban/sprint.md` e scegli un TSK `todo` del tuo layer.
2. Lancia `/dev <TSK-id>`: il dev-agent lavora nel `code_path` indicato dal TSK.
3. Leggi in `PATTERN.md` §7 le invarianti critiche prima del primo commit.

## tester

1. Apri `management/kanban/sprint.md` e scegli un TSK `todo` con `layer: qa`.
2. Lancia `/dev <TSK-id>` per far scrivere il test al dev-agent QA, poi `/review <TSK-id>`.
3. Esiti e evidenze dei test vanno nel TSK, non a memoria.

## tech-lead

1. Lancia `/run` per la dashboard di stato e il prossimo passo suggerito.
2. Rivedi un TSK in `review` con `/review <TSK-id>`: il verdetto `reject` resta una tua decisione.
3. Le modifiche a `PATTERN.md`, `factory.config.yaml` e `CLAUDE.md` passano da un branch dedicato con PR.

## funzionale-pm

1. Fai una domanda alla wiki con `/query "<domanda>"`: risponde solo da `wiki/`, con le fonti.
2. Leggi `management/kanban/` per epiche e storie aperte.
3. Per documentazione funzionale c'è `/doc-funzionale` (bozza, da approvare).

## management

1. Lancia `/digest-settimanale`: digest della settimana con numeri calcolati da script.
2. Lancia `/velocity` per punti e TSK chiusi per settimana.
3. Leggi `CAPABILITIES.md` per l'elenco delle capability attive.

## esterno

1. Usa la factory in lettura: `/query "<domanda>"`.
2. Il lavoro di una persona esterna al team entra nel kanban solo tramite il Tech Lead: chiedi a lui.
3. Leggi `PATTERN.md` §7 prima di proporre modifiche.

## generico

1. Lancia `/query "cosa fa questa factory"` e leggi il risultato.
2. Apri `management/kanban/sprint.md` e trova un task con `status: todo`.
3. Lancia `/dev <id-task>` e porta il ciclo fino al commit.
