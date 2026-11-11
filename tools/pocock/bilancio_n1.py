#!/usr/bin/env python3
"""
bilancio_n1.py — bilancio N:1 (complexity budget): parole aggiunte e tolte nelle istruzioni degli
agenti rispetto a un commit di partenza.

Conta le parole di CLAUDE.md, PATTERN*.md e .claude/**/*.md al commit base e nel working tree.
Separa i file nuovi (si caricano solo quando un agente li legge) dai file esistenti modificati
(pesano su ogni lancio dell'agente o del comando che li carica). Il commit base sta in
<registri>/bilancio-n1.yaml (chiave `base`), la cartella dei registri in
engineering_practices.analytics_path di factory.config.yaml.

Uso:
  python3 tools/pocock/bilancio_n1.py                  # base da bilancio-n1.yaml
  python3 tools/pocock/bilancio_n1.py --base <sha>
  python3 tools/pocock/bilancio_n1.py --registri <dir> --repo <dir>
Solo stdlib + git (+ pyyaml per leggere la base). Nessuna scrittura.
"""
import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _config import ROOT, settings  # noqa: E402


def git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)


def tracked(path):
    return path == "CLAUDE.md" or (path.startswith("PATTERN") and path.endswith(".md")) or \
        (path.startswith(".claude/") and path.endswith(".md"))


def words_at(repo, base, path):
    r = git(repo, "show", f"{base}:{path}")
    return len(r.stdout.split()) if r.returncode == 0 else None


def bilancio(repo, base):
    """Ritorna (modificati, nuovi): liste di (path, parole_prima, parole_dopo)."""
    repo = pathlib.Path(repo)
    changed = git(repo, "diff", "--name-only", base, "--").stdout.split()
    changed += git(repo, "ls-files", "--others", "--exclude-standard").stdout.split()
    rows_new, rows_mod = [], []
    for p in sorted(set(f for f in changed if tracked(f))):
        now = len((repo / p).read_text(encoding="utf-8").split()) if (repo / p).exists() else 0
        before = words_at(repo, base, p)
        (rows_new if before is None else rows_mod).append((p, before or 0, now))
    return rows_mod, rows_new


def main(argv=None):
    cfg = settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--registri", default=str(ROOT / cfg["analytics_path"]))
    ap.add_argument("--repo", default=str(ROOT))
    a = ap.parse_args(argv)
    base = a.base
    if not base:
        import yaml
        base = yaml.safe_load((pathlib.Path(a.registri) / "bilancio-n1.yaml").read_text(encoding="utf-8"))["base"]

    rows_mod, rows_new = bilancio(a.repo, base)
    print(f"Bilancio N:1 rispetto a {str(base)[:8]}\n")
    print("File esistenti modificati (pesano su ogni caricamento):")
    for p, b, n in rows_mod:
        print(f"  {n - b:+6d}  {p}  ({b} → {n})")
    print(f"  {sum(n - b for _, b, n in rows_mod):+6d}  totale\n")
    print("File nuovi (caricati solo quando servono):")
    for p, _, n in rows_new:
        print(f"  {n:+6d}  {p}")
    print(f"  {sum(n for _, _, n in rows_new):+6d}  totale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
