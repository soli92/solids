# Comando: /ponytail-audit

> Equivalente Cursor del comando Claude Code `/ponytail-audit` (`.claude/commands/ponytail-audit.md`).
> Scan YAGNI Decision Ladder sull'intero code_path (o sottoinsieme). Full-repo counterpart di /ponytail-review. Produce report in code_quality/reports/ letto da /ponytail-gain. Opt-in ponytail.enabled.

> Procedura: [ponytail-audit](mdc:.cursor/rules/skills/ponytail-audit.mdc)

> **Gate**: `factory.config.yaml.ponytail.enabled: true`. Se `false` → ABORT e suggerisci di abilitarlo.

**Sintassi**:
```
/ponytail-audit                  → scan dell'intero code_path (da factory.config.yaml)
/ponytail-audit src/components/  → scan di un sottoinsieme
/ponytail-audit "**/*.tsx"       → scan via glob
```

## Limitazioni Cursor

- I tool deterministici sotto `tools/` sono invocati da terminale e si comportano in modo identico: la differenza sta solo nell'agente che li chiama.
