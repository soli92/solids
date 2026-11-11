#!/usr/bin/env python3
"""Lancio di spec Cypress con un report scritto nella factory, mai nel repo di test.

Esegue uno o piu' spec con la config del repo di test e raccoglie l'output in
`code_quality/cypress/<TSK-id>/run-<AAAAMMGG_HHMMSS>/`:

    run-<ts>/
      esito.md                  totali, suite, test falliti, link (unico file versionato)
      junit/*.xml               un JUnit per spec (reporter integrato di Cypress)
      screenshots/              screenshot dei test falliti
      html_report/              JUnit unito (junit-report.xml) + copia degli screenshot
      <altro>                   cio' che aggiunge il profilo di reporter scelto

Profili di reporter (`--reporter`, o `reporter:` in `cypress_pipeline` / nella voce del repo):

  generic   (default) solo reporter integrati di Cypress (`junit`): nessuna dipendenza npm
            oltre a Cypress, report markdown neutro. Selezionabile senza altro.
  <custom>  punto di estensione: un modulo Python che espone `PROFILE`, istanza di una
            sottoclasse di `ReporterProfile` (vedi `tools/cypress/README.md`), caricato con
            `--reporter-module <file.py>`. Serve a chi deve riprodurre il formato di una
            pipeline CI propria (mochawesome, HTML, ecc.): il profilo decide gli argomenti
            del reporter di Cypress e gli artefatti da produrre dopo il lancio.

La config del repo di test non si modifica: reporter e cartella degli screenshot si
sovrascrivono da riga di comando. Cypress e gli strumenti del profilo sono quelli del
`node_modules` del repo di test; se mancano lo script si ferma e indica `npm ci` nel repo
(lo decide l'operatore).

Esecuzione solo su richiesta dell'operatore: il login dello spec puo' essere interattivo.

Uso:
    python3 tools/cypress/run_report.py --tsk TSK-123 --repo <name> \\
        --spec "cypress/e2e/area/login.cy.js" [--spec ...] [--headed]
    python3 tools/cypress/run_report.py --tsk TSK-123 --test-path <path> --spec <spec>
    python3 tools/cypress/run_report.py --tsk TSK-123 --test-path <path> --merge-only <run-dir>
    python3 tools/cypress/run_report.py ... --dry-run

Exit: 0 report prodotto (anche con test falliti: i falliti sono nell'esito), 1 errore di
ambiente o di esecuzione, 2 argomenti non validi.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

FACTORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_CANDIDATES = ("cypress.config.js", "cypress.config.ts", "cypress.config.mjs", "cypress.config.cjs")
MERGED_JUNIT = "junit-report.xml"
TSK_RE = re.compile(r"^(?:[A-Z]{2,4}-)?TSK-[0-9A-Za-z-]+$")
DEFAULT_REPORTER = "generic"


def fail(msg: str, code: int = 1) -> None:
    print(f"[run_report] ERRORE: {msg}", file=sys.stderr)
    sys.exit(code)


def tool_bin(test_path: Path, name: str) -> Path:
    return test_path / "node_modules" / ".bin" / name


# ---------------------------------------------------------------------------
# Profili di reporter
# ---------------------------------------------------------------------------

class ReporterProfile:
    """Punto di estensione: come si lancia Cypress e quali artefatti si producono dopo.

    Una sottoclasse puo' ridefinire:
      - `required_tools`: binari di `node_modules/.bin` oltre a `cypress`;
      - `cypress_args(run_dir)`: argomenti di riga di comando del reporter (la config del
        repo di test non si tocca);
      - `finalize(test_path, run_dir, stamp, dry)`: artefatti post-lancio (merge, HTML...);
        ritorna le righe markdown da aggiungere alla sezione «File» di `esito.md`.
    Il JUnit unito, gli screenshot e `esito.md` li produce sempre lo script, dai file
    `junit/*.xml`: un profilo custom che vuole totali coerenti deve far scrivere il JUnit
    in `<run_dir>/junit/`.
    """

    name = "base"
    required_tools: tuple = ()

    def cypress_args(self, run_dir: Path) -> List[str]:
        raise NotImplementedError

    def finalize(self, test_path: Path, run_dir: Path, stamp: str, dry: bool) -> List[str]:
        return []


class GenericProfile(ReporterProfile):
    """Reporter `junit` integrato di Cypress: nessun pacchetto npm da aggiungere."""

    name = "generic"

    def cypress_args(self, run_dir: Path) -> List[str]:
        mocha_file = run_dir / "junit" / "junit-report-[hash].xml"
        return ["--reporter", "junit",
                "--reporter-options", f"mochaFile={mocha_file},toConsole=false"]


PROFILES: Dict[str, ReporterProfile] = {GenericProfile.name: GenericProfile()}


def load_profile_module(path: str) -> ReporterProfile:
    """Carica un profilo custom da un file Python che espone `PROFILE`."""
    file = Path(path)
    if not file.is_file():
        fail(f"--reporter-module non trovato: {path}", 2)
    spec = importlib.util.spec_from_file_location("cypress_reporter_profile", file)
    if spec is None or spec.loader is None:
        fail(f"--reporter-module non importabile: {path}", 2)
    # il modulo puo' fare `from run_report import ReporterProfile`: stessa classe di questo processo
    if __name__ in sys.modules:
        sys.modules.setdefault("run_report", sys.modules[__name__])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    profile = getattr(module, "PROFILE", None)
    # duck typing: il modulo puo' aver importato una copia della classe base
    if not all(hasattr(profile, a) for a in ("name", "cypress_args", "finalize")):
        fail(f"{path} deve esporre PROFILE, istanza di ReporterProfile", 2)
    PROFILES[profile.name] = profile
    return profile


def choose_profile(name: Optional[str], module: Optional[str], repo: Optional[str]) -> ReporterProfile:
    """Ordine: --reporter-module, --reporter, registro (voce del repo, poi globale), generic."""
    if module:
        return load_profile_module(module)
    if not name and repo:
        sys.path.insert(0, str(FACTORY_ROOT / "tools" / "cypress"))
        from resolve_repo import load_registry  # noqa: E402
        registry = load_registry(FACTORY_ROOT) or {}
        entry = next((r for r in registry.get("repos", []) if r.get("name") == repo), {})
        name = entry.get("reporter") or registry.get("reporter")
    name = name or DEFAULT_REPORTER
    if name not in PROFILES:
        fail(f"profilo di reporter '{name}' sconosciuto (disponibili: {', '.join(sorted(PROFILES))}); "
             "per uno custom usa --reporter-module", 2)
    return PROFILES[name]


# ---------------------------------------------------------------------------
# Passi
# ---------------------------------------------------------------------------

def find_config_file(test_path: Path, explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if (test_path / explicit).exists() else None
    return next((c for c in CONFIG_CANDIDATES if (test_path / c).exists()), None)


def check_tools(test_path: Path, profile: ReporterProfile, need_cypress: bool) -> None:
    names = list(profile.required_tools) + (["cypress"] if need_cypress else [])
    missing = [n for n in names if not tool_bin(test_path, n).exists()]
    if missing:
        fail(
            f"nel repo di test mancano {', '.join(missing)} in node_modules/.bin. "
            f"Esegui `npm ci` in {test_path} (node_modules e' escluso da git) e rilancia."
        )


def run_cypress(args, profile: ReporterProfile, config_file: str, test_path: Path, run_dir: Path) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(tool_bin(test_path, "cypress")), "run",
        "--browser", args.browser,
        "--config-file", config_file,
        "--spec", ",".join(args.spec),
        *profile.cypress_args(run_dir),
        "--config", f"screenshotsFolder={run_dir / 'screenshots'},video=false",
    ]
    if args.headed:
        cmd.append("--headed")
    print("[run_report] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    if args.dry_run:
        return 0
    # Le shell aperte da VS Code esportano ELECTRON_RUN_AS_NODE=1: con quella variabile il binario
    # di Cypress (Electron) parte come Node e rifiuta le proprie opzioni («bad option: --no-sandbox»).
    env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    # Cypress esce con il numero di test falliti: non e' un errore dello script.
    return subprocess.run(cmd, cwd=str(test_path), env=env).returncode


def _suites(root: ET.Element) -> List[ET.Element]:
    return [root] if root.tag == "testsuite" else list(root.findall("testsuite"))


def merge_junit(run_dir: Path) -> Path:
    """JUnit unito: una <testsuites tests failures time> con tutte le testsuite per spec."""
    root = ET.Element("testsuites", {"name": "Cypress Tests"})
    tests = failures = skipped = 0
    time = 0.0
    for f in sorted((run_dir / "junit").glob("*.xml")):
        for s in _suites(ET.parse(f).getroot()):
            root.append(s)
            tests += int(s.get("tests", 0) or 0)
            failures += int(s.get("failures", 0) or 0)
            skipped += int(s.get("skipped", 0) or 0)
            time += float(s.get("time", 0) or 0)
    root.set("tests", str(tests))
    root.set("failures", str(failures))
    root.set("skipped", str(skipped))
    root.set("time", f"{time:.3f}")
    out = run_dir / "html_report" / MERGED_JUNIT
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(out, encoding="UTF-8", xml_declaration=True)
    return out


def copy_screenshots(run_dir: Path) -> int:
    src = run_dir / "screenshots"
    files = [p for p in src.rglob("*.png")] if src.exists() else []
    if not files:
        print("[run_report] Non sono presenti screenshot")
        return 0
    shutil.copytree(src, run_dir / "html_report" / "screenshots", dirs_exist_ok=True)
    return len(files)


def failed_tests(junit: Path) -> List[str]:
    """«suite / test: messaggio» per ogni testcase con failure o error."""
    out: List[str] = []
    if not junit.exists():
        return out
    for suite in _suites(ET.parse(junit).getroot()):
        for case in suite.findall("testcase"):
            bad = case.find("failure")
            if bad is None:
                bad = case.find("error")
            if bad is not None:
                message = " ".join((bad.get("message") or "").split())[:200]
                out.append(f"{suite.get('name', '?')} / {case.get('name', '?')}"
                           + (f": {message}" if message else ""))
    return out


def write_esito(run_dir: Path, tsk: str, specs: List[str], junit: Path, n_shots: int,
                cypress_rc: Optional[int], profile: ReporterProfile, extra: List[str]) -> Path:
    totals = ET.parse(junit).getroot() if junit.exists() else None
    get = (lambda k: totals.get(k, "0")) if totals is not None else (lambda k: "n/d")
    rel = lambda p: p.relative_to(run_dir).as_posix()  # noqa: E731
    folder = run_dir.relative_to(FACTORY_ROOT).as_posix() if _inside(run_dir, FACTORY_ROOT) else str(run_dir)
    failed = failed_tests(junit)
    lines = [
        f"# Esito del lancio Cypress — {tsk}",
        "",
        f"- Cartella: `{folder}`",
        f"- Data: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Profilo di reporter: `{profile.name}`",
        f"- Spec: {', '.join(f'`{s}`' for s in specs) if specs else '(da merge di un lancio esistente)'}",
        f"- Exit di Cypress: {cypress_rc if cypress_rc is not None else 'n/a (solo merge)'}",
        "",
        "| Test | Falliti | Saltati | Durata (s) |",
        "|---|---|---|---|",
        f"| {get('tests')} | {get('failures')} | {get('skipped')} | {get('time')} |",
        "",
    ]
    if failed:
        lines += ["## Test falliti", "", *(f"- {f}" for f in failed), ""]
    lines += [
        "## File",
        "",
        f"- JUnit unito: [{rel(junit)}]({rel(junit)})" if junit.exists() else "- JUnit unito: assente",
        f"- Screenshot dei falliti: {n_shots}" + (" in `html_report/screenshots/`" if n_shots else ""),
        *extra,
        "",
        "Gli artefatti del lancio contengono dati dell'ambiente di test e restano locali (gitignore):",
        "si versiona solo questo file.",
        "",
    ]
    out = run_dir / "esito.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tsk", required=True, help="TSK di riferimento, es. TSK-123")
    ap.add_argument("--repo", help="name del repo nel registro cypress_pipeline.repos (path e reporter)")
    ap.add_argument("--test-path", help="radice del repo di test (alternativa a --repo)")
    ap.add_argument("--spec", action="append", default=[], help="spec relativo al repo (ripetibile)")
    ap.add_argument("--config-file", default=None,
                    help="config di Cypress nel repo di test (default: cypress.config.{js,ts,mjs,cjs})")
    ap.add_argument("--reporter", default=None, help="profilo di reporter (default: registro, poi generic)")
    ap.add_argument("--reporter-module", default=None, help="file Python con PROFILE (profilo custom)")
    ap.add_argument("--browser", default="chrome")
    ap.add_argument("--headed", action="store_true", help="browser visibile (login interattivo)")
    ap.add_argument("--out-root", default=None, help="default: code_quality/cypress/<TSK-id>/ nella factory")
    ap.add_argument("--merge-only", metavar="RUN_DIR", help="rifa' solo merge e report su un lancio esistente")
    ap.add_argument("--dry-run", action="store_true", help="stampa i comandi senza eseguirli")
    args = ap.parse_args(argv)

    if not TSK_RE.match(args.tsk):
        fail(f"TSK non valido: {args.tsk}", 2)

    test_arg = args.test_path
    if not test_arg and args.repo:
        sys.path.insert(0, str(FACTORY_ROOT / "tools" / "cypress"))
        from resolve_repo import resolve  # noqa: E402
        result, code = resolve(FACTORY_ROOT, args.repo)
        if result.get("status") != "ok":
            fail(f"repo '{args.repo}' non risolvibile: {result.get('status')} "
                 f"{result.get('errors') or result.get('message')}", 2 if code == 2 else 1)
        test_arg = result["test"]["path"]
    if not test_arg:
        fail("serve --repo o --test-path", 2)

    profile = choose_profile(args.reporter, args.reporter_module, args.repo)
    test_path = Path(test_arg)
    if not test_path.is_absolute():
        test_path = FACTORY_ROOT / test_path
    test_path = test_path.resolve()
    config_file = find_config_file(test_path, args.config_file)
    if config_file is None:
        fail(f"config di Cypress non trovata in {test_path} "
             f"({args.config_file or ', '.join(CONFIG_CANDIDATES)})", 2)

    cypress_rc: Optional[int] = None
    if args.merge_only:
        run_dir = Path(args.merge_only).resolve()
        if not (run_dir / "junit").is_dir():
            fail(f"{run_dir}/junit non esiste: niente da unire", 2)
        stamp = re.sub(r"^run-", "", run_dir.name)
        if not args.dry_run:
            check_tools(test_path, profile, need_cypress=False)
    else:
        if not args.spec:
            fail("serve almeno uno --spec (o --merge-only)", 2)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_root = Path(args.out_root) if args.out_root else FACTORY_ROOT / "code_quality" / "cypress" / args.tsk
        run_dir = (out_root / f"run-{stamp}").resolve()
        if _inside(run_dir, test_path):
            fail("la cartella del report non puo' stare nel repo di test", 2)
        if not args.dry_run:
            check_tools(test_path, profile, need_cypress=True)
        cypress_rc = run_cypress(args, profile, config_file, test_path, run_dir)
        if args.dry_run:
            profile.finalize(test_path, run_dir, stamp, dry=True)
            return
        if not list((run_dir / "junit").glob("*.xml")):
            fail(f"Cypress (exit {cypress_rc}) non ha prodotto JUnit in {run_dir}/junit")

    extra = profile.finalize(test_path, run_dir, stamp, dry=args.dry_run)
    if args.dry_run:
        return
    junit = merge_junit(run_dir)
    n_shots = copy_screenshots(run_dir)
    esito = write_esito(run_dir, args.tsk, args.spec, junit, n_shots, cypress_rc, profile, extra)
    print(f"[run_report] report in {run_dir}")
    print(f"[run_report] esito: {esito}")


if __name__ == "__main__":
    main()
