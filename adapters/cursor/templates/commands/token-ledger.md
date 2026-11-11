# Comando: /token-ledger

> Equivalente Cursor del comando Claude Code `/token-ledger` (`.claude/commands/token-ledger.md`).
> EP-022, opt-in `analytics.token_ledger.enabled`.

**Sintassi**:
```
/token-ledger                        → display compatto (default)
/token-ledger --full                 → box completo con breakdown modelli
/token-ledger --transcript <path>    → path esplicito al transcript JSONL
```

## Comportamento

Display puro del costo cumulativo sessione. Non prende decisioni.

1. Legge `factory.config.yaml.analytics.token_ledger.enabled`. Se `false` → mostra nota ma esegue comunque (il comando e' sempre disponibile).
2. Individua il transcript JSONL piu' recente (`~/.claude/projects/<cwd>/*.jsonl`).
3. Aggrega token `message.usage` dai messaggi assistant.
4. Risolve pricing da `analytics/pricing.yaml`.
5. Mostra display.

**Invocazione**:
```bash
python3 "<factory-path>/tools/analytics/show-session-tokens.py"
python3 "<factory-path>/tools/analytics/show-session-tokens.py" --full
```

## Display format

**Compatto** (default):
```
◉ TOKENS  in:42.3k  out:8.1k  💾 -$0.0031  │  sessione: ~$0.1527
```

**Completo** (`--full`):
```
╭────────────────────────────────────────────────────╮
│  TOKEN LEDGER — sessione corrente                  │
│  Modelli: claude-sonnet-4-6                        │
├────────────────────────────────────────────────────┤
│  Input:           42.3k  tokens                    │
│  Output:           8.1k  tokens                    │
│  Cache read:      31.2k  tokens                    │
│  Risparmio:      $0.0031                           │
├────────────────────────────────────────────────────┤
│  Costo sessione:  ~$0.1527                         │
╰────────────────────────────────────────────────────╯
```

## Limitazioni Cursor

- Il transcript JSONL `~/.claude/projects/<cwd>/*.jsonl` e' Claude Code-specifico. In Cursor il formato del transcript e' diverso → lo script non funziona nativamente.
- In Cursor: invocare lo script dal terminal se il transcript e' accessibile, oppure stimare manualmente il costo basandosi sul context window usato.
- Per reportistica batch (per-TSK/wave) usa lo script `tools/analytics/harvest-session-tokens.py`.
