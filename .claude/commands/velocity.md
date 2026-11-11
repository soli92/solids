---
name: velocity
description: Velocity settimanale sul kanban — punti e TSK chiusi per settimana, proiezione sul backlog, tempo di attraversamento (read-only, vista per persona solo con --per-persona)
domain: analytics
---

Misura quanti punti e TSK si chiudono per settimana ISO. Delegato a `tools/analytics/team-velocity.py`
(con `tools/analytics/kanban_history.py`); non scrive mai nel kanban. Non e' gated da flag: e' una
lettura on demand. Il burndown di uno sprint e' un'altra cosa: `/sprint-progress`.

## Sintassi

```
/velocity                       -> tutte le epiche, media sulle ultime 3 settimane concluse
/velocity --epiche EP-001,EP-002
/velocity --settimane 2         -> finestra di media diversa
/velocity --dal 2026-10-05      -> solo i done da una data
/velocity --per-persona         -> aggiunge la vista per persona (mai senza questo flag)
/velocity --json | --out <path>
```

```bash
python3 tools/analytics/team-velocity.py [--config PATH] [--epiche A,B] [--settimane N] [--dal YYYY-MM-DD] [--per-persona] [--json] [--out PATH]
```

Config opzionale `analytics/velocity/config.json` (modello: `analytics/velocity/config.example.json`:
epiche, scala dei punti, tabella dei giorni, team, soglia della registrazione in blocco). Senza file
valgono i default.

Riporta le tabelle cosi' come prodotte, senza ricalcolare. Commenta solo cio' che la sezione
«Qualità dei dati» rende necessario; se l'utente chiede come sono fatti i numeri, cita la «Legenda».

## Fonti dei dati

| Grandezza | Fonte |
|---|---|
| Chiusura | `closed_at` (opzionale; alias `closed`, `completed_at`, `completed`, `done_at`), altrimenti il commit che porta `status:` a `done` |
| Inizio | `started_at` (opzionale), altrimenti il primo passaggio a `in_progress` nella storia git |
| Punti | `estimate` o `size` → scala `punti`; senza taglia il TSK vale 0 punti |
| Archivio | `archive/` escluso, salvo `includi_archivio: true` |

## Limiti noti

- **Registrazioni in blocco**: un commit che chiude almeno `soglia_chiusura_in_blocco` TSK sposta le chiusure sulla data della registrazione. Lo script le conta e le segnala.
- **Inizio**: senza `started_at` serve un passaggio a `in_progress` committato; chi chiude un TSK senza passare da li' non ha tempo di attraversamento.
- **Non committato**: un TSK portato a `done` solo in locale compare tra i «done senza data».
- I punti misurano la dimensione stimata, non lo sforzo.
