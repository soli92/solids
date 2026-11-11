#!/usr/bin/env python3
"""mascot-backend.py — backend `mascot` del Prototype Generation Layer (EP-035/US-293).

NON e' una capability autonoma: e' un backend che si inserisce nella catena di
fallback gia' esistente. La factory ha gia' un layer generativo con un resolver e una
degradazione; aggiungerne un secondo per le mascotte significherebbe due impianti da
mantenere per lo stesso problema.

    python3 tools/prototype/mascot-backend.py probe            # disponibile?
    python3 tools/prototype/mascot-backend.py verify <dir>     # i due fogli si allineano?
    python3 tools/prototype/mascot-backend.py reproduce        # gli artefatti si rigenerano?

TRE COSE CHE QUESTO BACKEND RIFIUTA DI FARE, e sono le tre che il progetto a monte
(`nilbuild/page-mascot`, MIT) fa e che l'analisi del 2026-09-23 ha misurato come
difetti:

  1. **Non versiona artefatti irriproducibili.** Su 58 personaggi pubblicati a monte,
     **41 non si rigenerano** dai propri sorgenti con lo script committato (build
     deterministico: 17/58 byte-identici). `reproduce` rende la proprieta' eseguibile
     qui, cosi' non puo' scivolare in silenzio.
  2. **Non accetta un output non verificato.** Due fogli che non si allineano
     producono una mascotte che salta al cambio di stato. La verifica e' un gate,
     non un rapporto.
  3. **Non introduce dipendenze proprie.** Quelle che servono sono quelle gia'
     dichiarate dal Prototype Generation Layer. Assenti -> il backend e'
     `UNAVAILABLE` e la catena degrada: la mascotte inclusa (SVG, generata in
     codice) resta utilizzabile e non richiede nulla.

Solo stdlib + Pillow/numpy quando presenti. `probe` non importa mai nulla di pesante.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Sotto questa soglia i due fogli sono disegni diversi e la mascotte cambia aspetto
#: al cambio di stato. Ereditata dalla misura a monte: un mismatch genuino stava al 12%,
#: i robot con placca facciale piatta scendono legittimamente al 27%.
PALETTE_MIN = 0.22
#: Sopra questo spostamento il cambio di stato si vede come uno scatto.
SHIFT_MAX_PX = 2.0


def _dipendenze() -> tuple[bool, str]:
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as mancante:
        return False, f"dipendenza assente: {mancante.name}"
    return True, ""


def probe(root: Path) -> dict:
    """ASSE 1 (dipendenze) + ASSE 2 (sorgenti). Non genera nulla, non importa nulla di pesante."""
    ok, ragione = _dipendenze()
    sorgenti = root / "visual/mascots"
    return {
        "backend": "mascot",
        "status": "AVAILABLE" if ok else "UNAVAILABLE",
        "reason": ragione or None,
        "sources_dir": str(sorgenti.relative_to(root)) if sorgenti.exists() else None,
        # La degradazione non e' un guasto: la mascotte inclusa e' disegnata in codice
        # (SVG in visual/static/mascotte.js) e non richiede ne' questo backend ne' rete.
        "fallback": "mascotte SVG inclusa in visual/static/mascotte.js — nessun prerequisito",
    }


def verify(directory: Path) -> dict:
    """I due fogli sono lo stesso personaggio, alla stessa scala, nella stessa posizione?"""
    ok, ragione = _dipendenze()
    if not ok:
        return {"verdict": "unverifiable", "reason": ragione}

    import numpy as np
    from PIL import Image

    fogli = {}
    for nome in ("directions", "reactions"):
        percorso = next((directory / f"{nome}{e}" for e in (".png", ".webp")
                         if (directory / f"{nome}{e}").is_file()), None)
        if percorso is None:
            return {"verdict": "reject", "reason": f"foglio `{nome}` assente in {directory}"}
        fogli[nome] = np.array(Image.open(percorso).convert("RGBA"))

    for nome, foglio in fogli.items():
        if foglio.shape[0] != foglio.shape[1]:
            # Il difetto che a monte passava il pre-volo con verdetto GOOD: una griglia
            # 3x3 derivata da un foglio non quadrato e' silenziosamente sbagliata.
            return {"verdict": "reject",
                    "reason": f"`{nome}` non e' quadrato ({foglio.shape[1]}x{foglio.shape[0]}): "
                              f"la griglia 3x3 che se ne deriva e' sbagliata senza dirlo"}
        if (foglio[..., 3] < 10).mean() < 0.05:
            return {"verdict": "reject",
                    "reason": f"`{nome}` non ha un canale alfa reale: la trasparenza e' una "
                              f"proprieta' della chiamata all'immagine, non del prompt"}

    def istogramma(foglio):
        maschera = foglio[..., 3] > 200
        if not maschera.any():
            return np.zeros(4096)
        rgb = (foglio[maschera][:, :3] // 16).astype(np.int32)
        conteggio = np.bincount(rgb[:, 0] * 256 + rgb[:, 1] * 16 + rgb[:, 2], minlength=4096)
        totale = conteggio.sum()
        return conteggio / totale if totale else conteggio

    palette = float(np.minimum(istogramma(fogli["directions"]), istogramma(fogli["reactions"])).sum())

    def baricentro(foglio):
        maschera = foglio[..., 3] > 120
        righe = np.where(maschera.any(axis=1))[0]
        colonne = np.where(maschera.any(axis=0))[0]
        return (righe.mean(), colonne.mean()) if len(righe) else (0.0, 0.0)

    ay, ax = baricentro(fogli["directions"])
    by, bx = baricentro(fogli["reactions"])
    lato = fogli["directions"].shape[0] / 3
    shift = float(np.hypot(ay - by, ax - bx) * (140.0 / lato))   # in px alla resa

    problemi = []
    if palette < PALETTE_MIN:
        problemi.append(f"i due fogli sono disegni diversi (palette {palette * 100:.0f}%, "
                        f"minimo {PALETTE_MIN * 100:.0f}%)")
    if shift > SHIFT_MAX_PX:
        problemi.append(f"i due fogli si spostano di {shift:.2f}px alla resa "
                        f"(massimo {SHIFT_MAX_PX}px): la mascotte salterebbe al cambio di stato")

    return {"verdict": "reject" if problemi else "pass",
            "palette_match": round(palette, 4), "shift_px": round(shift, 2),
            "reason": "; ".join(problemi) or None}


def reproduce(root: Path) -> dict:
    """Ogni artefatto versionato si rigenera dai propri sorgenti?

    E' il controllo che a monte non esiste e la cui assenza ha prodotto 41 artefatti su
    58 fuori sync. Qui nulla di binario e' versionato: la mascotte inclusa e' **codice**
    (SVG generato da `visual/static/mascotte.js`), quindi la proprieta' vale per
    costruzione. Il controllo esiste perche' continui a valere.
    """
    artefatti = sorted((root / "visual/static").rglob("*.webp")) + \
                sorted((root / "visual/static").rglob("*.png"))
    irriproducibili = [str(a.relative_to(root)) for a in artefatti
                       if not (root / "visual/mascots" / a.stem).exists()]
    return {
        "artefatti_binari_versionati": len(artefatti),
        "senza_sorgente": irriproducibili,
        "verdict": "reject" if irriproducibili else "pass",
        "reason": (f"{len(irriproducibili)} artefatti binari senza sorgente da cui rigenerarli: "
                   f"e' il difetto misurato a monte (41/58)") if irriproducibili else None,
        "nota": "la mascotte inclusa e' codice, non un binario: riproducibile per costruzione",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("comando", choices=["probe", "verify", "reproduce"])
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    if args.comando == "probe":
        esito = probe(root)
    elif args.comando == "reproduce":
        esito = reproduce(root)
    else:
        if not args.directory:
            parser.error("`verify` richiede la cartella dei due fogli")
        esito = verify(args.directory)

    print(json.dumps(esito, ensure_ascii=False, indent=2))
    return 1 if esito.get("verdict") == "reject" else 0


if __name__ == "__main__":
    sys.exit(main())
