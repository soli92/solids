---
skill: lint-checks
leaf_of: lint-checks-wiki-structure.md
section: "wiki-structure"
description: "Check 4bg: contatore Sources di wiki/index.md"
---

> Eseguito da `tools/lint/run-deterministic.py` (registrato in `CHECKS`).

# 4bg — Contatore «## Sources (N)» di `wiki/index.md` (always-on, WARNING)

**Eseguibile, non interpretato.** Stesso script del 4bf:

```bash
python3 tools/lint/check_dati_derivati.py .
```

**Cosa controlla.** `N` nel titolo della sezione `## Sources (N)` deve essere uguale al numero
delle voci `- [[...]]` che la sezione elenca. Il numero reale è calcolato dallo script.

**Configurazione.** Nessuna chiave in `factory.config.yaml`; stessi argomenti del 4bf
(`--json`, `--strict`, radice).

**Codice e severità.** `sources-contatore` (WARNING), con valore dichiarato, valore reale e scarto.

**Esenzioni.** Nessuna. Se `wiki/index.md` o la sezione mancano non c'è nulla da confrontare.

**Chi corregge.** Il wiki-keeper (`wiki/` ha un solo autore): il check non modifica il file,
quindi non è `heal-eligible`.

**Output format:**

```
- [WARNING][sources-contatore][4bg] wiki/index.md: «## Sources (120)» ma la sezione elenca 121 voci (scarto +1). Aggiornare il contatore (wiki-keeper).
```

[^src: tools/lint/check_dati_derivati.py]
