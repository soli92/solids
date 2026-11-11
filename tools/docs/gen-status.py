#!/usr/bin/env python3
"""gen-status.py — stato degli adapter generato dai manifest (EP-080 US-350).

La maturita' di un adapter ha una sola fonte: `adapters/*/manifest.yaml`. Prima di EP-080 la
dichiaravano a mano tre file, e il README diceva Aider «full v2.13» mentre CLAUDE.md e il
manifest dicevano «partial».

  python3 tools/docs/gen-status.py            # riscrive il blocco generato di docs/STATUS*.md
  python3 tools/docs/gen-status.py --check    # exit 1 se un blocco e' indietro o CLAUDE.md diverge

Il blocco generato sta fra i marcatori BEGIN/END; il resto della pagina e' scritto a mano.
--check confronta anche la tabella «Adapter registry» di CLAUDE.md: ogni riga deve contenere la
maturita' del manifest e, se cita un «contract X.Y», la versione del manifest. Solo stdlib.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "<!-- gen-status:begin (tools/docs/gen-status.py, non modificare a mano) -->"
END = "<!-- gen-status:end -->"
PAGINE = {
    "docs/STATUS.md": ("Adapter", "Runtime folder", "Maturity", "Contract", "Manifest"),
    "docs/STATUS.it.md": ("Adapter", "Cartella runtime", "Maturita'", "Contratto", "Manifest"),
}


def _campo(testo: str, chiave: str) -> str | None:
    m = re.search(rf"^{chiave}:\s*\"?([^\"#\n]+?)\"?\s*(?:#.*)?$", testo, re.M)
    return m.group(1).strip() if m else None


def manifest(root: Path) -> list[dict]:
    out = []
    for p in sorted(root.glob("adapters/*/manifest.yaml")):
        t = p.read_text(encoding="utf-8")
        out.append({
            "nome": _campo(t, "adapter_name") or _campo(t, "name") or p.parent.name,
            "cartella": _campo(t, "adapter_folder"),
            "tipo": _campo(t, "adapter_type"),
            "maturita": _campo(t, "maturity") or "?",
            "contratto": _campo(t, "contract_version") or "?",
            "path": p.relative_to(root).as_posix(),
        })
    # full prima, poi per maturita' decrescente: chi legge cerca prima cosa funziona davvero
    ordine = {"full": 0, "core": 1, "partial": 2, "manifest-only": 3}
    return sorted(out, key=lambda a: (ordine.get(a["maturita"], 9), a["nome"]))


def blocco(adapters: list[dict], intestazioni: tuple[str, ...]) -> str:
    righe = ["| " + " | ".join(intestazioni) + " |", "|" + "---|" * len(intestazioni)]
    for a in adapters:
        cartella = f"`{a['cartella']}/`" if a["cartella"] else f"— ({a['tipo'] or 'bridge'})"
        righe.append(f"| {a['nome']} | {cartella} | {a['maturita']} | {a['contratto']} "
                     f"| [`{a['path']}`](../{a['path']}) |")
    return BEGIN + "\n" + "\n".join(righe) + "\n" + END


def sostituisci(testo: str, nuovo: str) -> str | None:
    i, j = testo.find(BEGIN), testo.find(END)
    if i < 0 or j < 0:
        return None
    return testo[:i] + nuovo + testo[j + len(END):]


def deriva_claude_md(root: Path, adapters: list[dict]) -> list[str]:
    p = root / "CLAUDE.md"
    if not p.is_file():
        return []
    testo = p.read_text(encoding="utf-8")
    sez = re.search(r"^## Adapter registry.*?(?=^## )", testo, re.M | re.S)
    if not sez:
        return ["CLAUDE.md: sezione «## Adapter registry» non trovata"]
    errori = []
    for a in adapters:
        chiave = f"| `{a['cartella']}/`" if a["cartella"] else f"| {a['nome'].upper()}"
        riga = next((r for r in sez.group(0).splitlines() if r.startswith(chiave)), None)
        if riga is None:
            errori.append(f"CLAUDE.md: nessuna riga per l'adapter {a['nome']} ({chiave} ...)")
            continue
        if a["maturita"] not in riga:
            errori.append(f"CLAUDE.md: riga di {a['nome']} non dichiara la maturita' «{a['maturita']}» "
                          f"del manifest: {riga.strip()}")
        m = re.search(r"contract ([0-9]+\.[0-9]+)", riga)
        if m and m.group(1) != a["contratto"]:
            errori.append(f"CLAUDE.md: riga di {a['nome']} dichiara contract {m.group(1)}, "
                          f"il manifest {a['contratto']}")
    return errori


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="non scrive: exit 1 se c'e' deriva")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args()
    adapters = manifest(a.root)
    errori: list[str] = []
    for rel, intest in PAGINE.items():
        p = a.root / rel
        if not p.is_file():
            errori.append(f"{rel}: file assente")
            continue
        vecchio = p.read_text(encoding="utf-8")
        nuovo = sostituisci(vecchio, blocco(adapters, intest))
        if nuovo is None:
            errori.append(f"{rel}: marcatori del blocco generato assenti")
        elif nuovo != vecchio:
            if a.check:
                errori.append(f"{rel}: blocco generato indietro rispetto ai manifest "
                              "(python3 tools/docs/gen-status.py)")
            else:
                p.write_text(nuovo, encoding="utf-8")
                print(f"aggiornato {rel}")
    errori += deriva_claude_md(a.root, adapters)
    for e in errori:
        print(f"[ERROR][gen-status] {e}")
    if not errori:
        print(f"OK — {len(adapters)} adapter, stato coerente con i manifest")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
