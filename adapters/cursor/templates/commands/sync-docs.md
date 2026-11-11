# Comando: /sync-docs

> Equivalente Cursor del comando Claude Code `/sync-docs` (`.claude/commands/sync-docs.md`).
> In Cursor non esiste sub-agent nativo: esegui le fasi manualmente nella sessione Chat.

**Sintassi**: `/sync-docs`

## Comportamento

Estrae testo e immagini dai PDF in `raw/`. Procedura:

1. Scansiona `raw/*.pdf` per file non ancora nel manifest (`raw/.extraction-manifest.json`).
2. Estrae testo → `raw/<data>-<nome>.txt`.
3. Estrae figure → `raw/images/<data>-<nome>-fig-NN.md` + binari.
4. Aggiorna `raw/.extraction-manifest.json`.
5. Suggerisce di invocare `wiki-keeper` per l'ingest L1→L2.

Prerequisito `wiki-keeper`: legge i `.txt` estratti, mai i PDF direttamente.

## Limitazioni Cursor

- L'estrazione PDF reale richiede un tool esterno (pdfplumber, pymupdf). Usare terminal integrato Cursor:
  ```bash
  cd <factory-root> && python3 tools/sync-docs/extract.py raw/<file>.pdf
  ```
- Se lo script non è presente nella factory, l'estrazione va fatta manualmente o con strumento locale.
- L'agente `sync-docs` non è disponibile come sub-agent in Cursor: eseguire i passi sequenzialmente.
