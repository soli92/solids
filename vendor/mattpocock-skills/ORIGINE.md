# Copia fedele di mattpocock/skills

- **Sorgente:** https://github.com/mattpocock/skills
- **Commit:** `49dd158d1076134a641b33efb035946536778336` (v1.3.1, 2026-10-09)
- **Licenza:** MIT, testo in [`LICENSE`](LICENSE). La licenza chiede di conservare copyright e
  testo di permesso in ogni copia: restano qui, accanto ai file.
- **Copiata il:** 2026-10-15 nella derivata portale-servizi-factory; portata nel master con EP-077

## Cosa contiene

I file delle 9 skill adottate dal pilota, **non modificati**, con il loro path originale sotto
`skills/`: tdd, grilling, codebase-design, diagnosing-bugs, code-review, to-tickets, retro,
domain-modeling, improve-codebase-architecture.

Esclusi: i file `agents/openai.yaml` (metadati per Codex, non servono a Claude Code né a Cursor).
Lo script `diagnosing-bugs/scripts/hitl-loop.template.sh` è copiato senza permesso di
esecuzione: è un modello da leggere, non si lancia da qui.

Non copiate per scelta: setup-matt-pocock-skills, triage, to-spec, implement, implement-spec,
wizard, pr. wayfinder è rinviata a dopo il pilota.

## Dove sono le versioni adattate

Le versioni che la factory usa stanno in `.claude/skills/pocock-*.md` (e
`.claude/skills/references/pocock-*/`). Questa cartella serve solo come riferimento e per
confrontare l'adattamento con l'originale: nessun agente la carica.

## Verifica

```bash
python3 tools/pocock/verify_vendor.py                      # impronte dei file contro MANIFEST.sha1
python3 tools/pocock/verify_vendor.py --clone <clone>      # anche contro un clone di mattpocock/skills al commit
```

`MANIFEST.sha1` contiene l'impronta git (blob SHA-1) di ogni file: è la stessa che GitHub mostra
per quel file al commit indicato.

## Aggiornare la copia

Mai in automatico. Si legge il CHANGELOG del repo di Pocock, si copia il nuovo commit in questa
cartella, si rigenera `MANIFEST.sha1`, si confrontano le differenze con le versioni adattate e
si aggiornano a mano, su branch `framework/` con PR.
