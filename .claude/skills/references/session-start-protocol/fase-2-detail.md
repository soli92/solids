# session-start-protocol — Fase 2: raw/ non ingestati

Ambito: conteggio dei file raw/ non ancora ingestati. Serve in **tutte** le modalita'
(alimenta `pending_ingest_count`); solo la domanda finale e' di `manual`.
Sola lettura su `raw/` e sul manifest (§7 r.1).

```python
import json
from pathlib import Path

root = Path("<factory_root>")
raw = root / "raw"
raw_slugs = {p.stem for p in raw.glob("*.md")}
session_slugs = {p.stem for p in (raw / "sessions").glob("*.md")}

try:
    manifest = json.loads((raw / ".extraction-manifest.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    manifest = {}          # manifest assente: tutto risulta non ingestato, dichiaralo

ingested = set(manifest) | {
    Path(v["primary_artifact"]).stem
    for v in manifest.values()
    if isinstance(v, dict) and v.get("primary_artifact")
}
non_ingestati = sorted(raw_slugs - ingested)
sessioni_non_ingestate = sorted(session_slugs - ingested)
pending_ingest_count = len(non_ingestati) + len(sessioni_non_ingestate)
```

Le sessioni chiuse da `/session-close` hanno `primary_artifact: raw/sessions/<label>.md`
nel manifest: il loro stem confluisce in `ingested` e non vengono ricontate.

## Domanda (solo `manual`, se `pending_ingest_count > 0`)

```
[SESSION-START Fase 2 — raw/ non ingestati]
raw/:            <len(non_ingestati)>
raw/sessions/:   <len(sessioni_non_ingestate)>
Ingesto adesso? [s/n/lista]
```
`s` → invoca `wiki-keeper` esplicitamente. `n`/invio → annota il conteggio.
`lista` → mostra i due elenchi e ripropone [s/n]. Oltre 10 file, premetti
`[ATTENZIONE: N file raw/ non ingestati]`.
