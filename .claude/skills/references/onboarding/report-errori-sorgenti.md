# Onboarding — Report, errori e sorgenti

Ambito: formato del report del Passo 6 di `.claude/skills/onboarding.md` nel **report esteso**
(`onboarding_day0.enabled: true`), gestione degli errori e tabella delle sorgenti dichiarate.
Non serve a `--compact`. La logica di stato READY/PARTIAL/BLOCKED resta nel Passo 6 della skill.

---

#### Formato del report

```
══════════════════════════════════════════════════════════
 ONBOARDING REPORT — <nome della factory>
══════════════════════════════════════════════════════════

Stato: [ READY | PARTIAL | BLOCKED ]
Data:  <YYYY-MM-DD>

─── SEZIONE 1: Factory corrente ───────────────────────────
Versione factory:   <vX.Y>
Stack:              <dal CLAUDE.md, se dichiarato>
code_path:          <dalla config>
Agenti installati:  <N> file in .claude/agents/

─── SEZIONE 2: Aree di lavoro attive ──────────────────────
Sprint: <titolo> | TSK todo/in-progress/done: <N>/<M>/<K>
  <prefisso>  — <TSK-id: titolo breve> [in-progress|todo]
Sorgente: management/kanban/sprint.md

─── SEZIONE 3: Risorse Day 0 ──────────────────────────────
  [✓] <file di ambiente>          — PRESENTE / ⚠ ASSENTE (solo se configurato)
  [✓] <checklist prerequisiti>    — (solo se configurata)
  [✓] /init-check                 — binari, submodule, variabili

─── SEZIONE 4: Prossimi passi ─────────────────────────────
<output di day0.py: Day 0 del ruolo>

US ad alta priorità aperte (max 3):
  <US-id> [<priorità>] <titolo breve> — Epica: <epic-id>

─── SEZIONE 5: Comandi utili per iniziare ─────────────────
  /init-check                        — verifica prerequisiti tecnici
  /query "<domanda>"                 — interroga la wiki
  /promemoria --registrami           — registrati in anagrafica e dichiara il ruolo (se promemoria è acceso)
  /dev <TSK-id>                      — sviluppa un task
  /lint                              — verifica qualità factory
  /help <domanda>                    — quale comando usare

══════════════════════════════════════════════════════════
Nessun file scritto. Output solo in-chat.
```

La riga `/promemoria --registrami` compare solo a `promemoria_operatori.enabled: true`.

---

## Gestione errori

- **`factory.config.yaml` assente**: segnala `factory.config.yaml non trovato — verifica di essere nella root della factory`; stato BLOCKED; continua con le sezioni che non ne dipendono.
- **`CLAUDE.md` assente**: `[nota] CLAUDE.md non trovato`; stato PARTIAL; continua.
- **`management/kanban/sprint.md` assente**: `[nota] sprint.md non trovato`; ometti Sezione 2 e le US; stato PARTIAL.
- **`day0.py` in errore** (exit 1, 2): usa il fallback del Passo 5 della skill; con exit 2 (ruolo sconosciuto) mostra l'elenco `ruoli` dell'output.
- **Flag `--check-env`**: esegui solo Passi 2-3, poi componi un report ridotto con la sola Sezione 3 e lo stato corrispondente.
- **`.claude/agents/` assente**: conta = 0; segnala `[nota]`.

---

## Sorgenti dichiarate

| Sorgente | Obbligatoria | Impatto se assente | Note |
|---|---|---|---|
| `factory.config.yaml` | si | BLOCKED | versione, blocchi `onboarding_day0` e `promemoria` |
| `CLAUDE.md` | no | PARTIAL | versione, stack |
| `management/kanban/sprint.md` | no | PARTIAL | aree attive, sprint |
| `management/kanban/` | no | PARTIAL | US ad alta priorità |
| `tools/onboarding/day0.py` + file di `onboarding_day0.file` | no | fallback statico | Day 0 per ruolo |
| `onboarding_day0.prerequisites_file` | no | PARTIAL se dichiarato e assente | checklist |
| `onboarding_day0.env_file` | no | PARTIAL/BLOCKED se dichiarato e assente | solo presenza booleana |
| `.claude/agents/` | no | conta = 0 | conteggio agenti |
