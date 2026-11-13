---
description: Report contestuale in-chat per nuovi contributor — versione factory, task onboarding-friendly, invarianti §7, passo successivo.
argument-hint: "[--compact] [--ruolo=<ruolo>] [--check-env]"
allowed-tools: Read, Glob, Bash
---

Argomenti utente: `$ARGUMENTS`

Invoca la skill `onboarding` (`.claude/skills/onboarding.md`).

Esegui i 4 passi della skill nell'ordine:
1. Leggi `factory.config.yaml` → Sezione 1 Factory corrente
2. Leggi `management/kanban/sprint.md` → Sezione 2 Task onboarding-friendly
3. Leggi `PATTERN.md §7` live → Sezione 3 5 invarianti critiche
4. Appendi Sezione 4 statica (CAPABILITIES.md, CLAUDE.md; QUICKSTART.md e `wiki/getting-started/` solo se esistono)

Con `onboarding_day0.enabled: true` (default `false`) segui la «Modalità Day 0 per ruolo» della
skill: `--compact` benvenuto breve, `--ruolo=<r>` Day 0 del ruolo indicato, `--check-env` solo la
verifica ambiente. A flag spento i flag sono ignorati e valgono i 4 passi sopra. Bash solo per i
comandi elencati dalla skill.

Output esclusivamente in-chat. Nessun file viene scritto.
