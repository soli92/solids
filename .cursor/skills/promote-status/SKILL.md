# Skill: Promote Status

> Adapter Cursor della skill `promote-status` definita in PATTERN.md.

# Operazione `/promote` (canonica)

Riferimenti: [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template `promote`), `PATTERN.md §3` (operazione
canonica) e `§10` (eccezione di scrittura su wiki/).

## Chi può eseguirla

**Solo l'[orchestrator](mdc:.cursor/rules/orchestrator.mdc).** È l'unica eccezione strutturata in cui un agente
diverso da [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc) modifica il frontmatter di una pagina wiki/. La
modifica è **meccanica** e ristretta a 2 campi: `status:` e `updated:`.

## Trigger

L'umano invoca `/promote <path> [<new-status>]` come slash command.

## Transizioni legali

```
draft → review → approved
```

- Mai salti (no `draft → approved`).
- Mai retrocessione senza passare per `deprecated`.
- `approved → deprecated` legale (decisione esplicita di deprecazione).
- `deprecated → archived` legale (pagina fuori uso permanente).

Se l'umano non specifica `<new-status>`, applica la transizione successiva
naturale (`draft → review` o `review → approved`).

## Procedura

1. **Read** della pagina target.
2. Estrai `status:` corrente dal frontmatter YAML.
3. Calcola target legale (vedi tabella sopra). Se illegale → **STOP**: rifiuta
   in chat, suggerisci il passo intermedio.
4. **Edit meccanico**: cambia **solo** i campi `status:` e `updated:`
   (= oggi, YYYY-MM-DD) nel frontmatter YAML. **Mai toccare il corpo della
   pagina.** Mai toccare altri campi (`type`, `sources`, `tags`, `created`).
5. Append a `wiki/log.md` secondo [wiki-log-entry](mdc:.cursor/skills/wiki-log-entry/SKILL.md) (template `promote`):
   ```
   [YYYY-MM-DD HH:MM] promote — <path> <old-status> → <new-status> — files touched: 1
   ```

## Refusal cases

- Path non esiste → rifiuta, suggerisci `Glob` per verificare.
- `status:` corrente non trovato nel frontmatter → rifiuta, indica all'umano di
  contattare [wiki-keeper](mdc:.cursor/rules/wiki-keeper.mdc).
- Transizione illegale → rifiuta, mostra il passo intermedio richiesto.
- Pagina è un `log.md`, `gaps.md`, `index.md` o file in `query/`/`lint/`:
  rifiuta, queste pagine non hanno ciclo di status.

## Anti-pattern (vietati)

| Anti-pattern | Correzione |
|---|---|
| Modificare il corpo della pagina "per coerenza" | Vietato. Solo `status:` e `updated:`. |
| Saltare `review` (`draft → approved` diretto) | Vietato. Richiede 2 invocazioni separate. |
| Promuovere senza loggare in `wiki/log.md` | Vietato. Log obbligatorio. |
| Promuovere pagine in `wiki/query/` o `wiki/lint/` | Vietato. Non hanno status. |
