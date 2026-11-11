"""check-wiki-structure: il codice non contiene wikilink (EP-072, backport dalla derivata).

`new Map([['key', 'value']])` in un esempio JS e la sintassi `[[name]]` citata fra backtick
risultavano broken-link ERROR; la derivata li escludeva gia'.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "lint" / "check-wiki-structure.py"

_PAGINA = """---
title: Pagina
updated: 2026-10-07
---

# Pagina

Esempio:

```js
const ctx = new Map([['key', 'value']]);
```

La sintassi `[[name]]` crea un link. Link vero ma rotto: [[pagina-che-non-esiste]].
"""


def test_solo_il_link_fuori_dal_codice_e_rotto(tmp_path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts" / "pagina.md").write_text(_PAGINA)
    (tmp_path / "wiki" / "index.md").write_text("# Indice\n\n- [[pagina]]\n")
    (tmp_path / "management" / "kanban").mkdir(parents=True)
    r = subprocess.run([sys.executable, str(_SCRIPT), "--root", str(tmp_path), "--oggi", "2026-10-07"],
                       capture_output=True, text=True)
    rotti = [l for l in r.stdout.splitlines() if "[broken-link]" in l]
    assert len(rotti) == 1 and "pagina-che-non-esiste" in rotti[0], r.stdout
