# Copia fedele di emilkowalski/skills

- **Sorgente:** https://github.com/emilkowalski/skills
- **Commit:** `715c1807e08c497cfd1dc4feb450a2a3300ef2a9` (715c180, 2026-11-09)
- **Licenza:** MIT, Copyright (c) 2026 Emil Kowalski, testo in [`LICENSE`](LICENSE). La licenza chiede
  di conservare copyright e testo di permesso in ogni copia: restano qui, accanto ai file.
- **Copiata il:** 2026-11-11 con EP-090

## Cosa contiene

I file di 4 skill, **non modificati**, con il loro path originale sotto `skills/`:
break-ui (SKILL.md, CATALOG.md), review-animations (SKILL.md, STANDARDS.md),
improve-animations (SKILL.md, AUDIT.md, PLAN-TEMPLATE.md), prototype (SKILL.md, PICKER.md).

## Esclusi per scelta

emil-design-eng, apple-design, animate, animate-expo, choreograph, gestures, mobile-native,
write-swift, ask-sonner, pick-ui-library, animation-vocabulary, find-animation-opportunities,
remove-animations, animation-performance e i cheatsheet della root del repo.

## Dove sono le versioni adattate

Le versioni che la factory usa stanno in `.claude/skills/kowalski-worst-case-data.md` e
`.claude/skills/kowalski-motion-review.md`; le varianti di prototype sono assorbite in
`prototype-generation-protocol` e il `base_commit` in `dev-protocol`. Questa cartella serve solo
come riferimento e per confrontare l'adattamento con l'originale: nessun agente la carica.

## Verifica

```bash
python3 tools/pocock/verify_vendor.py --vendor emilkowalski-skills            # impronte contro MANIFEST.sha1
python3 tools/pocock/verify_vendor.py --vendor emilkowalski-skills --clone <clone>   # anche contro un clone al commit
python3 tools/pocock/verify_vendor.py --all                                   # tutte le copie in vendor/
```

`MANIFEST.sha1` contiene l'impronta git (blob SHA-1) di ogni file: è la stessa che GitHub mostra
per quel file al commit indicato.

## Aggiornare la copia

Mai in automatico. Si legge il CHANGELOG del repo di Emil Kowalski, si copia il nuovo commit in
questa cartella, si rigenera `MANIFEST.sha1`, si confrontano le differenze con le versioni
adattate e si aggiornano a mano, su branch `framework/` con PR.
