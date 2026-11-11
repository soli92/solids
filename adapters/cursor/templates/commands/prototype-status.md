# Comando: /prototype-status

> Equivalente Cursor del comando Claude Code `/prototype-status` (`.claude/commands/prototype-status.md`).
> Procedura: vedi [backend-resolver](mdc:.cursor/rules/skills/backend-resolver.mdc).

**Sintassi**: `/prototype-status`

Nessun argomento obbligatorio. Snapshot read-only del Prototype Generation Layer.

**Funziona anche a `prototyping.enabled: false`** (esecuzione esplicita = volonta' esplicita).

## Comportamento

1. Legge `factory.config.yaml.prototyping:` (enabled, backend, fallback_chain, degrade_policy).
2. Se layer spento → mostra istruzioni di attivazione + STOP.
3. Invoca [backend-resolver](mdc:.cursor/rules/skills/backend-resolver.mdc) in modalita' dry-run con `intent: "auto"`.
4. Per ogni backend nella `fallback_chain`: probe di disponibilita' read-only (figma: MCP autenticato; penpot: MCP raggiungibile; react: stack-detector; html: sempre AVAILABLE INV-1).
5. Mostra tabella disponibilita' + marker `BACKEND_RESOLVED` o `BACKEND_DEGRADED` o `BACKEND_UNAVAILABLE_STRICT`.

## Output esempio (layer abilitato)

```
PROTOTYPE STATUS (EP-035)
=========================
Layer:           ENABLED
Backend config:  auto
Degrade policy:  notify
Fallback chain:  [figma, penpot, react, html]

DISPONIBILITA' BACKEND (ASSE 2)
backend   tier  stato        motivo
figma     T2    UNAVAILABLE  MCP figma non autenticato
html      T0    AVAILABLE    fallback terminale (INV-1)

RISOLUZIONE (intent: auto)
BACKEND_DEGRADED: figma→html
Backend selezionato: html
```

## Vincoli

- **Read-only assoluto**: nessun artefatto generato, nessuna modifica a `factory.config.yaml`.
- `html` e' sempre AVAILABLE (INV-1).

## Limitazioni Cursor

- I probe MCP vanno verificati manualmente (Cursor non ha accesso diretto ai MCP configurati).
- Per `react`: verificare la presenza di framework FE in `code_paths` tramite [stack-detector](mdc:.cursor/rules/skills/stack-detector.mdc).
