---
description: Estrae testo + immagini dai PDF in raw/.
---

Invoca l'agente `sync-docs` via `Agent`. L'agente:

1. Scansiona `raw/*.pdf` per file non ancora nel manifest.
2. Estrae testo → `raw/<data>-<nome>.txt`.
3. Estrae figure → `raw/images/<data>-<nome>-fig-NN.md` + binari.
4. Aggiorna `raw/.extraction-manifest.json`.
5. Suggerisce di invocare `wiki-keeper` per l'ingest.

Prerequisito per `wiki-keeper`: `wiki-keeper` legge i `.txt` estratti, mai i PDF direttamente.
