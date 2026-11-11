---
description: Controlla un testo per persone con le regole strutturali di ASD-STE100 (linter deterministico) e, su richiesta, lo riscrive senza perdere fatti, con la sezione «Omesso».
argument-hint: "<file> [--rewrite] [--out=<path>] [--strict] [--lang=it|en] [--json]"
---

# /ste-lite — Scrittura controllata

Argomenti utente: `$ARGUMENTS`

Esegue la skill `ste-lite-protocol` (`.claude/skills/ste-lite-protocol.md`): leggila prima di
procedere. Il comando non ha logica propria: il verdetto di conformità viene da
`tools/lint/ste_lite.py`.

## Procedura

### Step 1 — Parse argomenti

| Flag | Azione |
|---|---|
| `<file>` | obbligatorio. Senza file: stampa l'uso e fermati |
| `--rewrite` | dopo il controllo, riscrivi (skill §Riscrittura) |
| `--out=<path>` | con `--rewrite`, scrivi lì la riscrittura. Senza: mostrala in chat |
| `--strict` | passa `--strict` al linter (exit 1 se ci sono violazioni) |
| `--lang=it\|en` | forza la lingua. Default: riconosciuta dal testo |
| `--json` | passa `--json` al linter |

`--out` non può essere uguale a `<file>`: l'originale non si sovrascrive.

### Step 2 — Controllo

```bash
python3 tools/lint/ste_lite.py <file> [--lang=<l>] [--strict] [--json]
```

Riporta l'output integralmente.

### Step 3 — Riscrittura (solo con `--rewrite`)

Segui la skill §Riscrittura, passi 2-5, e mostra:

- conformità prima e dopo (`frasi_conformi`);
- le violazioni rimaste;
- la sezione `## Omesso`.

Non dichiarare il testo conforme se il linter riporta violazioni.
