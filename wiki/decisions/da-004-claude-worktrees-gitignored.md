---
id: da-004-claude-worktrees-gitignored
type: decision
title: "DA-004 — .claude/worktrees/ gitignored (checkout isolati Claude Code)"
status: accepted
created: 2026-07-17
updated: 2026-07-17
sources:
  - "docs/raw/bonifica-repo-2026-07-17.txt §DA-004 — .claude/worktrees/ gitignored"
context: bonifica-2026-07-17
---

# DA-004 — `.claude/worktrees/` gitignored

## Contesto

Claude Code usa la directory `.claude/worktrees/` per checkout isolati durante
l'esecuzione di task che richiedono un ambiente separato dalla working tree principale.[^src: docs/raw/bonifica-repo-2026-07-17.txt §DA-004 — .claude/worktrees/ gitignored]

Durante lo scaffold dell'adapter `.claude/` v2.33, questa directory non era ancora
presente nel `.gitignore`.

## Decisione

Aggiungere il pattern `.claude/worktrees/` al `.gitignore`.

## Motivazione

I checkout in `.claude/worktrees/` sono temporanei e specifici alla sessione di Claude
Code. Non contengono lavoro prodotto dall'utente né artefatti da preservare: sono
copie di lavoro per l'isolamento dei task. Includerli nel tracking git causerebbe:

- Commit involontari di file di sessione temporanei
- Conflitti se Claude Code modifica la working tree durante un commit
- Rumore nei `git status` e `git diff`

## Conseguenze

- `.gitignore`: aggiunto pattern `.claude/worktrees/`
- Claude Code può creare checkout isolati senza impattare il repository

## Incident di riferimento

[[bonifica-2026-07-17]] — Incidente 4 (adapter Claude Code, scaffold `.claude/`)
