---
description: Prova a rompere un componente o una schermata con i dati del caso peggiore (nomi lunghi, campi mancanti, 0/1/migliaia di elementi), con toggle solo dev, e riporta le rotture con il fix prima di correggere. Opt-in ui_craft.worst_case_data.
argument-hint: <componente | TSK-id | path> [--correggi]
allowed-tools: Read, Bash, Glob, Grep, Write, Edit
---

Sintassi:

```
/worst-case <componente>      → mappa dei valori, fixture del caso peggiore, toggle, report; poi stop
/worst-case TSK-<id>          → idem sui componenti toccati dal TSK (code_path da kanban)
/worst-case <path>            → idem sul file o sulla cartella indicata
/worst-case <target> --correggi → dopo il report applica i fix non marcati «decisione: sì»
```

## Comportamento

1. **Pre-condizione**: se `ui_craft.enabled` o `ui_craft.worst_case_data` non sono `true` in
   `factory.config.yaml`, **non è un errore**: si risponde in chat che la passata è spenta, con le due chiavi da
   attivare, e non si tocca nulla.
2. Con i flag attivi, invoca la skill `kowalski-worst-case-data` (mappa, catalogo, fixture, toggle, rottura, report).
3. Output: tabella `# | Gravità | Campo | Valore | Cosa si rompe | Fix proposto | Decisione richiesta` in chat,
   poi ci si ferma.

## Vincoli

- **Report prima della correzione**: i fix si applicano solo su richiesta; le decisioni di design si chiedono.
- Il toggle è solo dev (canale nativo del progetto, es. args di Storybook; altrimenti parametro URL o route di prototipo), mai in produzione.
- I valori sono plausibili o dallo schema, mai casuali; cambiano al confine della fixture, mai nel markup.

## Cross-link

- Skill: `.claude/skills/kowalski-worst-case-data.md`
- Catalogo: `.claude/skills/references/kowalski-worst-case-data/catalogo.md`
- Aggancio: `.claude/skills/functional-oracle-protocol.md` §Fixture del caso peggiore
- Comandi affini: `/prototype`, `/review`
