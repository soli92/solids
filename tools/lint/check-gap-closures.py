#!/usr/bin/env python3
"""Check 4bc — chiusure dei gap non verificate sulla wiki (WARNING, advisory, mai bloccante).

Un gap di `wiki/gaps.md` e' chiuso davvero solo se il testo di chiusura rimanda a una pagina
della wiki che esiste e cita una fonte presente in `raw/`. Questo check riporta le chiusure «a
parole» (checkbox senza pagina, pagina assente, pagina senza fonte) che
`tools/wiki/verify_gap_closures.py` conta come gap da trattare ancora aperti. Legge i due
formati di gaps.md (sezioni `## AAAA-MM-GG` e voci `- [ ]`/`- [x]`).

Uso:
    python3 tools/lint/check-gap-closures.py [--json] [--strict] [<root>]
Exit code: 0 anche con finding; con --strict 1 se ce n'e' almeno uno.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

VERIFICA = pathlib.Path(__file__).resolve().parents[1] / "wiki" / "verify_gap_closures.py"


def carica(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("verify_gap_closures", VERIFICA)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = root
    m.WIKI = root / "wiki"
    m.GAPS = m.WIKI / "gaps.md"
    return m


def scan(root: pathlib.Path) -> tuple[dict, list[dict]]:
    """(conteggi, finding: un gap chiuso non verificato ciascuno)"""
    v = carica(root)
    conteggi = {"gap": 0, "aperti": 0, "verificati": 0, "non_verificati": 0}
    if not v.GAPS.is_file():
        return conteggi, []
    idx = v.page_index()
    findings = []
    gaps = v.parse()
    esiti = v.verify_all(gaps, idx)     # comprende i rimandi a gap chiusi e verificati altrove
    for g in gaps:
        esito = esiti[g.key][0]
        conteggi["gap"] += 1
        if esito == "aperto":
            conteggi["aperti"] += 1
        elif esito == "verificata":
            conteggi["verificati"] += 1
        else:
            conteggi["non_verificati"] += 1
            findings.append({"gap": g.key, "riga": g.line, "motivo": esito})
    return conteggi, findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Check 4bc — chiusure dei gap verificate")
    ap.add_argument("root", nargs="?", default=".", help="root della factory (default: .)")
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--strict", action="store_true", help="exit 1 se ci sono finding")
    args = ap.parse_args()

    conteggi, findings = scan(pathlib.Path(args.root).resolve())
    if args.json:
        print(json.dumps({"check": "4bc", "conteggi": conteggi, "findings": findings},
                         indent=2, ensure_ascii=False))
    elif not findings:
        print(f"[4bc] OK — {conteggi['gap']} gap, nessuna chiusura non verificata")
    else:
        print("## WARNING (chiusure a parole)")
        motivi: dict[str, list[dict]] = {}
        for f in findings:
            motivi.setdefault(f["motivo"], []).append(f)
        for motivo, fs in sorted(motivi.items(), key=lambda kv: -len(kv[1])):
            print(f"- [WARNING][gap-chiuso-non-verificato][4bc] wiki/gaps.md: {len(fs)} gap chiusi con "
                  f"motivo «{motivo}»: contano come aperti finche' la chiusura non rimanda a una pagina "
                  f"della wiki con fonte in raw/")
            for f in fs:
                print(f"    {f['gap']} (gaps.md:{f['riga']})")
        print(f"\nTotale: {conteggi['gap']} gap | aperti {conteggi['aperti']} | chiusi e verificati "
              f"{conteggi['verificati']} | chiusi non verificati {conteggi['non_verificati']}")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
