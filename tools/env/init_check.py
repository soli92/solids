#!/usr/bin/env python3
"""
tools/env/init_check.py — Diagnostica ambiente locale per qualunque factory della flotta.

Legge il blocco `environment:` da factory.config.yaml (opzionale).
Se assente: esegue solo i controlli base e dichiara "environment non configurato".

Controlli base (sempre presenti):
  - python3 (versione)
  - git (>= 2.40)
  - shell (linux/macos/wsl/wsl-mnt/gitbash/unknown)
  - git core.autocrlf
  - code_paths dichiarati esistono e sono repo git
  - submodule: stato e perimetro

Controlli da config (environment:):
  - binaries: [{name, min_version?, version_cmd?, required: bool}]
              oppure [{any_of: [nvm, fnm], required: bool}] — basta uno dei binari elencati
  - env_files: [path]   — solo esistenza, mai il contenuto
  - variables.required / variables.optional  — solo presenza, mai il valore
    variables.source_file: .env.x  → le chiavi si cercano in quel file (KEY=valore non vuoto),
    letto riga per riga e mai eseguito; senza: nell'ambiente del processo
  - node_version_file: .nvmrc  (WARN se presente ma node non matcha) — nella root e in ogni
    code_path dichiarato che lo contiene (una riga per repo)
  - probes: [{name, kind: http|tcp|cmd, target, timeout_s, required: bool}]
    → eseguiti SOLO con --probes (default: nessun traffico di rete implicito)

Output:
  - tabella PASS/WARN/FAIL in stdout
  - --json: JSON machine-readable
  - exit 0 = READY (fail=0, warn=0)
  - exit 1 = PARTIAL (fail=0, warn>0)
  - exit 2 = BLOCKED (fail>=1)

Uso:
  python3 tools/env/init_check.py [--probes] [--json] [--root <path>]
  --root  <path>    root della factory (default: CWD)
  --probes          attiva le probe di rete dichiarate in environment.probes
  --json            output JSON invece di tabella

Privacy invariante: mai stampare il VALORE delle variabili.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tipi di dato
# ---------------------------------------------------------------------------

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"


@dataclass
class Check:
    label: str
    status: str   # PASS | WARN | FAIL
    note: str


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    env_configured: bool = True

    def add(self, label: str, status: str, note: str) -> None:
        self.checks.append(Check(label, status, note))
        if status == STATUS_FAIL:
            self.fail_count += 1
        elif status == STATUS_WARN:
            self.warn_count += 1

    @property
    def state(self) -> str:
        if self.fail_count >= 1:
            return "BLOCKED"
        if self.warn_count > 0:
            return "PARTIAL"
        return "READY"

    @property
    def exit_code(self) -> int:
        if self.fail_count >= 1:
            return 2
        if self.warn_count > 0:
            return 1
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    """Esegue un comando. Ritorna (returncode, stdout, stderr). Mai eccezione."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def _parse_version(s: str) -> tuple[int, ...]:
    """Estrae tuple di interi da una stringa di versione ('2.40.1' → (2,40,1))."""
    nums = re.findall(r"\d+", s)
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def _load_yaml_simple(path: Path) -> dict:
    """
    Parser YAML minimalista (stdlib).
    Gestisce solo la struttura piatta e nested necessaria a factory.config.yaml.
    Fallisce con ValueError su sintassi non supportata — il chiamante gestisce l'eccezione.
    Usa PyYAML se disponibile (meglio), stdlib altrimenti.
    """
    try:
        import yaml  # type: ignore[import]
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass
    # fallback: lettura linea per linea (struttura YAML supportata: chiavi di primo livello
    # e nested indentate con 2 spazi; liste con trattino)
    return _yaml_fallback(path)


def _has_pyyaml() -> bool:
    try:
        import yaml  # type: ignore[import]  # noqa: F401
    except ImportError:
        return False
    return True


def _yaml_fallback(path: Path) -> dict:
    """Fallback parser per factory.config.yaml senza PyYAML (supporto limitato)."""
    result: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, result)]
    list_indent: int = -1

    def _current_container():
        return stack[-1][1]

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            # pop stack finché l'indentazione è coerente
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            container = _current_container()
            if stripped.startswith("- "):
                # list item
                item_str = stripped[2:].strip()
                if isinstance(container, list):
                    container.append(_scalar(item_str))
                elif isinstance(container, dict):
                    # lista inline appesa all'ultimo dict — non gestita bene, saltiamo
                    pass
            elif ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val == "" or val == "|" or val == ">":
                    # valore blocco: dict o lista
                    new_node: dict | list = {}
                    if isinstance(container, dict):
                        container[key] = new_node
                    stack.append((indent, new_node))
                elif val == "[]":
                    if isinstance(container, dict):
                        container[key] = []
                else:
                    if isinstance(container, dict):
                        container[key] = _scalar(val)
            # liste pure (riga con solo trattino)
            elif stripped == "-":
                if isinstance(container, list):
                    container.append(None)
    return result


def _scalar(s: str):
    """Converte stringa YAML in scalare Python."""
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", "None"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    # stringa con o senza virgolette
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


# ---------------------------------------------------------------------------
# Controlli base (sempre eseguiti)
# ---------------------------------------------------------------------------

def check_python(report: Report) -> None:
    """2a-equiv — python3 disponibile."""
    py = shutil.which("python3") or shutil.which("python")
    if py is None:
        report.add("python3", STATUS_FAIL, "python3 non trovato nel PATH")
        return
    rc, out, _ = _run([py, "--version"])
    if rc != 0:
        report.add("python3", STATUS_FAIL, "python3 --version fallito")
    else:
        report.add("python3", STATUS_PASS, f"({out})")


def check_pyyaml(report: Report) -> None:
    """PyYAML per i tool che leggono regole e config (cost_alert.py, analytics)."""
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        report.add("pyyaml", STATUS_WARN,
                   "non installato: /cost-alert e la statusLine non valutano le soglie "
                   "(pip install -r tools/requirements.txt)")
        return
    report.add("pyyaml", STATUS_PASS, f"({getattr(yaml, '__version__', '?')})")


def check_git(report: Report, min_version: tuple[int, ...] = (2, 40)) -> None:
    """2c-equiv — git >= min_version (FAIL)."""
    git = shutil.which("git")
    if git is None:
        report.add("git", STATUS_FAIL, "git non trovato nel PATH")
        return
    rc, out, _ = _run(["git", "--version"])
    if rc != 0:
        report.add("git", STATUS_FAIL, "git --version fallito")
        return
    ver = _parse_version(out)
    if ver < min_version:
        min_str = ".".join(str(v) for v in min_version)
        report.add(
            "git",
            STATUS_FAIL,
            f"versione {out} — richiesta >= {min_str}",
        )
    else:
        report.add("git", STATUS_PASS, f"({out})")


def check_shell(report: Report) -> None:
    """
    2e-equiv — rilevamento shell/OS:
    linux | macos | wsl | wsl-mnt | gitbash | unknown.
    WARN su wsl-mnt (repo sotto /mnt/) e gitbash (Windows nativo).
    """
    system = platform.system().lower()

    # macOS
    if system == "darwin":
        shell_id = "macos"
        report.add("shell", STATUS_PASS, f"(macOS — {platform.release()})")
        return

    # Linux: distinguiamo WSL
    if system == "linux":
        # WSL: /proc/version contiene "microsoft" o "wsl"
        wsl = False
        try:
            pv = Path("/proc/version").read_text(errors="ignore").lower()
            wsl = "microsoft" in pv or "wsl" in pv
        except OSError:
            pass

        if wsl:
            cwd = Path.cwd()
            if str(cwd).startswith("/mnt/"):
                # repo sotto /mnt/ → WARN (performance e CRLF)
                report.add(
                    "shell",
                    STATUS_WARN,
                    "(WSL2 — repo sotto /mnt/; considera di spostarlo in /home/ per performance e CRLF)",
                )
            else:
                report.add("shell", STATUS_PASS, "(WSL2 — repo in filesystem Linux)")
        else:
            report.add("shell", STATUS_PASS, f"(Linux — {platform.release()})")
        return

    # Windows nativo (Git Bash / PowerShell / CMD)
    if system == "windows":
        report.add(
            "shell",
            STATUS_WARN,
            "(Windows nativo — preferire WSL2 o Git Bash per compatibilità POSIX)",
        )
        return

    # MSYS/MINGW (Git Bash su Windows — platform.system() ritorna "Windows" ma può
    # comparire come MINGW in MSYSTEM env var)
    msystem = os.environ.get("MSYSTEM", "")
    if msystem.startswith("MINGW") or msystem.startswith("MSYS"):
        report.add(
            "shell",
            STATUS_WARN,
            f"(Git Bash / MSYS2 — {msystem}; POSIX parziale, path con / supportati)",
        )
        return

    report.add("shell", STATUS_WARN, f"(ambiente non riconosciuto: {system})")


def check_autocrlf(report: Report) -> None:
    """2f-equiv — git core.autocrlf (WARN se 'true')."""
    rc, val, _ = _run(["git", "config", "--global", "core.autocrlf"])
    if rc != 0:
        # non configurato → OK (non imposto il valore)
        report.add("git core.autocrlf", STATUS_PASS, "(non configurato — OK)")
        return
    if val.lower() == "true":
        report.add(
            "git core.autocrlf",
            STATUS_WARN,
            "(core.autocrlf=true — può causare problemi di CRLF; considera 'input' o 'false')",
        )
    else:
        report.add("git core.autocrlf", STATUS_PASS, f"({val})")


def check_code_paths(report: Report, root: Path, config: dict) -> list[str]:
    """
    Step 3 — code_paths dichiarati esistono e sono repo git.
    Ritorna lista di path dei code_paths in-perimetro (per il check submodule).
    """
    code_paths_cfg = config.get("code_paths", [])
    perimeter_paths: list[str] = []

    if not code_paths_cfg:
        # legacy code_path singolare
        cp = config.get("code_path", "")
        if cp and cp != ".":
            code_paths_cfg = [{"name": "default", "path": cp}]

    if not code_paths_cfg:
        report.add(
            "code_paths",
            STATUS_PASS,
            "(nessun code_path esterno dichiarato — factory reflexive)",
        )
        return perimeter_paths

    for entry in code_paths_cfg:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "?")
        path_str = entry.get("path", "")
        if not path_str or path_str == ".":
            continue  # reflexive, ok
        p = Path(path_str) if Path(path_str).is_absolute() else root / path_str
        if not p.exists():
            report.add(
                f"code_path:{name}",
                STATUS_FAIL,
                f"(path '{path_str}' non trovato nel filesystem)",
            )
        elif not (p / ".git").exists() and not (p / ".git").is_file():
            report.add(
                f"code_path:{name}",
                STATUS_WARN,
                f"('{path_str}' esiste ma non sembra un repo git)",
            )
        else:
            report.add(f"code_path:{name}", STATUS_PASS, f"('{path_str}' — OK)")
            perimeter_paths.append(path_str)

    return perimeter_paths


def _get_archived_paths(root: Path) -> set:
    """Fase 3a-arch: set dei path dei submodule con `archived = true` in .gitmodules."""
    gitmodules = root / ".gitmodules"
    if not gitmodules.exists():
        return set()
    rc_p, out_p, _ = _run([
        "git", "config", "-f", str(gitmodules),
        "--get-regexp", r"submodule\..*\.path",
    ])
    name_to_path: dict = {}
    if rc_p == 0 and out_p:
        for line in out_p.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                key, value = parts[0], parts[1].strip()
                inner = key[len("submodule."):]
                section_name = inner[: -len(".path")] if inner.endswith(".path") else inner
                name_to_path[section_name] = value
    rc_a, out_a, _ = _run([
        "git", "config", "-f", str(gitmodules),
        "--get-regexp", r"^submodule\..*\.archived$",
    ])
    archived_paths: set = set()
    if rc_a == 0 and out_a:
        for line in out_a.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[1].strip().lower() == "true":
                key = parts[0]
                inner = key[len("submodule."):]
                section_name = inner[: -len(".archived")] if inner.endswith(".archived") else inner
                sm_path = name_to_path.get(section_name)
                if sm_path:
                    archived_paths.add(sm_path)
    return archived_paths


def _same_or_nested(a: str, b: str) -> bool:
    """True se i due path coincidono o uno contiene l'altro, per segmenti interi.

    Un semplice startswith confonderebbe `code_repos/app` con `code_repos/app-test`.
    """
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def check_submodules(report: Report, root: Path, perimeter_paths: list[str]) -> None:
    """
    Step 3b — submodule: stato e perimetro.

    Fase 3a-arch: individua i submodule archiviati (chiave `archived = true`
    in .gitmodules) ed escludili dall'analisi di perimetro; vengono raccolti
    in una entry separata PASS «archiviati» (mai FAIL, mai WARN).

    Analisi git submodule status:
      '-' non inizializzato
      '+' pointer diverge
      ' ' allineato
    """
    # Fase 3a-arch — individua submodule archiviati
    archived_paths = _get_archived_paths(root)

    gm = root / ".gitmodules"
    dichiarati = gm.is_file() and "[submodule" in gm.read_text(encoding="utf-8", errors="replace")
    if not dichiarati:
        report.add("submodule (perimetro)", STATUS_PASS, "(nessun submodule dichiarato in .gitmodules)")
        return
    # `git submodule status` apre un processo per submodule: su decine di submodule supera di
    # molto i 5 s di default, e un timeout NON vuol dire «nessun submodule».
    rc, out, err = _run(["git", "-C", str(root), "submodule", "status"], timeout=120)
    if rc != 0 or not out:
        report.add("submodule (perimetro)", STATUS_WARN,
                   f"(stato non verificato: git submodule status exit {rc}"
                   f"{' — ' + err.strip().splitlines()[0] if err.strip() else ''})")
        return

    in_perim_statuses: list[str] = []
    out_perim_statuses: list[str] = []
    archived_count = 0

    for line in out.splitlines():
        if not line:
            continue
        prefix = line[0]  # '-', '+', ' ', 'U'
        rest = line[1:].strip()
        parts = rest.split()
        # Formato: [prefix]sha path [(branch_desc)]; il path e' all'indice 1
        sm_path = parts[1] if len(parts) >= 2 else (parts[0] if parts else "")

        # Fase 3a-arch: salta gli archiviati dall'analisi di perimetro
        if sm_path in archived_paths:
            archived_count += 1
            continue

        in_p = any(_same_or_nested(sm_path, pp) for pp in perimeter_paths)

        if in_p:
            in_perim_statuses.append(prefix)
        else:
            out_perim_statuses.append(prefix)
    # Aggregazione perimetro
    if not in_perim_statuses:
        report.add("submodule (perimetro)", STATUS_PASS, "(nessun submodule in perimetro)")
    elif "-" in in_perim_statuses:
        report.add(
            "submodule (perimetro)",
            STATUS_FAIL,
            "(submodule del perimetro non inizializzato — esegui: git submodule update --init <path>)",
        )
    elif "+" in in_perim_statuses:
        report.add(
            "submodule (perimetro)",
            STATUS_WARN,
            "(pointer diverge — verifica con: git submodule update --remote <path>)",
        )
    else:
        report.add(
            "submodule (perimetro)",
            STATUS_PASS,
            "(tutti i submodule del perimetro inizializzati e allineati)",
        )

    # Aggregazione fuori perimetro (mai FAIL)
    if out_perim_statuses:
        n = len(out_perim_statuses)
        if "-" in out_perim_statuses:
            report.add(
                "submodule (fuori perimetro)",
                STATUS_WARN,
                f"({n} submodule fuori perimetro non inizializzati — non bloccanti; esegui submodule update se necessario)",
            )
        else:
            report.add(
                "submodule (fuori perimetro)",
                STATUS_PASS,
                f"({n} submodule fuori perimetro — non bloccanti per questa sessione)",
            )

    # Fase 3c, punto 3 — entry archiviati (solo se presenti; sempre PASS)
    if archived_count > 0:
        report.add(
            "submodule (archiviati)",
            STATUS_PASS,
            f"({archived_count} submodule archiviati read-only — nessuna azione)",
        )
def _found(entry: dict) -> bool:
    """Nel PATH, oppure uno dei `paths` esiste: per gli strumenti che sono funzioni di shell
    (nvm: `$NVM_DIR/nvm.sh`), che `which` non vede mai."""
    if shutil.which(entry.get("name", "")):
        return True
    return any(Path(os.path.expandvars(os.path.expanduser(str(p)))).exists()
               for p in entry.get("paths", []) or [])


def check_binaries(report: Report, binaries: list[dict]) -> None:
    """Check binari dichiarati in environment.binaries."""
    for b in binaries:
        if b.get("any_of"):
            voci = [v if isinstance(v, dict) else {"name": str(v)} for v in b["any_of"]]
            nomi = [v.get("name", "?") for v in voci]
            trovati = [v["name"] for v in voci if _found(v)]
            label = "binary:" + "|".join(nomi)
            if trovati:
                report.add(label, STATUS_PASS, f"({trovati[0]})")
            else:
                req = b.get("required", False)
                report.add(label, STATUS_FAIL if req else STATUS_WARN,
                           f"(nessuno trovato nel PATH — {'richiesto' if req else 'opzionale'}: uno fra {', '.join(nomi)})")
            continue
        name = b.get("name", "?")
        required = b.get("required", True)
        min_ver_str = b.get("min_version", "")
        version_cmd = b.get("version_cmd", f"{name} --version")

        found = shutil.which(name)
        if not found:
            status = STATUS_FAIL if required else STATUS_WARN
            qualifier = "FAIL" if required else "WARN"
            report.add(f"binary:{name}", status, f"(non trovato nel PATH — {'richiesto' if required else 'opzionale'})")
            continue

        if min_ver_str:
            min_ver = _parse_version(min_ver_str)
            cmd_parts = version_cmd.replace("{name}", name).split()
            rc, out, _ = _run(cmd_parts)
            ver = _parse_version(out)
            if ver < min_ver:
                status = STATUS_FAIL if required else STATUS_WARN
                report.add(
                    f"binary:{name}",
                    status,
                    f"(trovato ma versione insufficiente: {out.splitlines()[0] if out else '?'} < {min_ver_str})",
                )
                continue
            report.add(f"binary:{name}", STATUS_PASS, f"({out.splitlines()[0] if out else 'ok'})")
        else:
            report.add(f"binary:{name}", STATUS_PASS, f"({found})")


def check_env_files(report: Report, root: Path, env_files: list[str]) -> None:
    """Check file .env dichiarati in environment.env_files — solo esistenza."""
    for ef in env_files:
        p = Path(ef) if Path(ef).is_absolute() else root / ef
        if p.exists():
            report.add(f"env_file:{ef}", STATUS_PASS, "(presente)")
        else:
            report.add(
                f"env_file:{ef}",
                STATUS_FAIL,
                f"(assente — crea '{ef}' con le credenziali richieste)",
            )


def _keys_from_file(path: Path) -> dict:
    """KEY -> True se il valore non e' vuoto. Riga per riga, mai eseguito, mai il valore."""
    out: dict = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        k, sep, v = line.strip().removeprefix("export ").partition("=")
        if sep and k.strip() and not k.strip().startswith("#"):
            out[k.strip()] = bool(v.strip().strip("\"'"))
    return out


def check_variables(report: Report, required: list[str | dict], optional: list[str | dict],
                    source_file: Path | None = None) -> None:
    """
    Check variabili — mai stampare il valore.
    required: FAIL se assente/vuota.
    optional: WARN se assente/vuota.
    source_file: se dato, le chiavi si cercano nel file (.env) invece che nell'ambiente.
    """
    if source_file is not None:
        if not source_file.is_file():
            report.add(f"var-file:{source_file.name}", STATUS_FAIL,
                       "(assente — le variabili dichiarate non si possono verificare)")
            return
        nel_file = _keys_from_file(source_file)
        dove = f" in {source_file.name}"
        _val = lambda n: nel_file.get(n, False)
    else:
        dove = ""
        _val = lambda n: bool(os.environ.get(n))
    def _name(entry) -> str:
        if isinstance(entry, dict):
            return entry.get("name", "?")
        return str(entry)

    def _tied(entry) -> str:
        if isinstance(entry, dict):
            tc = entry.get("tied_to_capability", "")
            return f" [capability: {tc}]" if tc else ""
        return ""

    for entry in required:
        n = _name(entry)
        if _val(n):
            report.add(f"var:{n}", STATUS_PASS, f"(presente{dove})")
        else:
            report.add(f"var:{n}", STATUS_FAIL, f"(assente o vuota{dove}{_tied(entry)})")

    for entry in optional:
        n = _name(entry)
        if _val(n):
            report.add(f"var:{n}", STATUS_PASS, f"(presente{dove}{_tied(entry)})")
        else:
            report.add(f"var:{n}", STATUS_WARN, f"(assente — opzionale{dove}{_tied(entry)})")


def check_nvmrc(report: Report, root: Path, node_version_file: str, label: str = "") -> None:
    """
    WARN se il file .nvmrc è dichiarato, esiste, ma node non è disponibile o la versione
    non matcha. `label` distingue i repo quando il check gira per code_path.
    """
    nvmrc_path = Path(node_version_file) if Path(node_version_file).is_absolute() else root / node_version_file
    if label:
        node_version_file = f"{label}/{node_version_file}"
    if not nvmrc_path.exists():
        # non presente → nessun check
        return

    required_ver_str = nvmrc_path.read_text(encoding="utf-8").strip().lstrip("v")
    node = shutil.which("node")
    if node is None:
        report.add(
            f"node ({node_version_file})",
            STATUS_WARN,
            f"(node non trovato — .nvmrc richiede v{required_ver_str})",
        )
        return

    rc, out, _ = _run(["node", "--version"])
    actual_ver = out.lstrip("v").strip()
    if actual_ver.split(".")[0] != required_ver_str.split(".")[0]:
        report.add(
            f"node ({node_version_file})",
            STATUS_WARN,
            f"(versione attiva {actual_ver} ≠ .nvmrc {required_ver_str} — usa nvm use o fnm use)",
        )
    else:
        report.add(f"node ({node_version_file})", STATUS_PASS, f"(v{actual_ver} — allineato a .nvmrc)")


def check_probes(report: Report, probes: list[dict]) -> None:
    """
    Probe di rete/cmd — eseguite SOLO con --probes.
    kind: http | tcp | cmd
    required: bool — se True: FAIL; altrimenti: WARN
    """
    for probe in probes:
        name = probe.get("name", "probe")
        kind = probe.get("kind", "http")
        target = probe.get("target", "")
        timeout_s = int(probe.get("timeout_s", 5))
        required = probe.get("required", False)

        label = f"probe:{name}"

        if kind == "http":
            try:
                req = urllib.request.urlopen(target, timeout=timeout_s)
                code = req.getcode()
                report.add(label, STATUS_PASS, f"(HTTP {code} — {target})")
            except urllib.error.HTTPError as exc:
                # l'host ha risposto (401, 403, 404...): e' raggiungibile, che e' cio' che si sonda
                report.add(label, STATUS_PASS, f"(HTTP {exc.code}, raggiungibile — {target})")
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, ssl.SSLCertVerificationError):
                    # handshake TLS avvenuto: l'host risponde, a Python manca la CA (tipico delle
                    # CA aziendali, che curl trova nel portachiavi di sistema e Python no)
                    report.add(label, STATUS_PASS,
                               f"(raggiungibile; certificato non verificabile da Python — {target})")
                else:
                    status = STATUS_FAIL if required else STATUS_WARN
                    report.add(label, status, f"(non raggiungibile: {exc} — {target})")
            except Exception as exc:
                status = STATUS_FAIL if required else STATUS_WARN
                report.add(label, status, f"(non raggiungibile: {exc} — {target})")

        elif kind == "tcp":
            # target = "host:port"
            try:
                host, _, port_str = target.partition(":")
                port = int(port_str or "80")
                sock = socket.create_connection((host, port), timeout=timeout_s)
                sock.close()
                report.add(label, STATUS_PASS, f"(TCP OK — {target})")
            except Exception as exc:
                status = STATUS_FAIL if required else STATUS_WARN
                report.add(label, status, f"(non raggiungibile: {exc} — {target})")

        elif kind == "cmd":
            cmd_parts = target.split()
            rc, out, err = _run(cmd_parts, timeout=timeout_s)
            if rc == 0:
                report.add(label, STATUS_PASS, f"(exit 0 — {target})")
            else:
                status = STATUS_FAIL if required else STATUS_WARN
                report.add(label, status, f"(exit {rc} — {target})")

        else:
            report.add(label, STATUS_WARN, f"(kind '{kind}' non riconosciuto)")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def render_table(report: Report) -> str:
    """Tabella PASS/WARN/FAIL + riga Stato."""
    header = "/init-check — diagnostica ambiente"
    sep = "─" * 68
    lines = [header, sep]

    max_label = max((len(c.label) for c in report.checks), default=20)
    max_status = 4  # PASS/WARN/FAIL

    for c in report.checks:
        lines.append(
            f"  {c.label:<{max_label}}  {c.status:<{max_status}}  {c.note}"
        )

    lines.append(sep)

    if not report.env_configured:
        lines.append("  [environment non configurato — eseguiti solo controlli base]")

    state = report.state
    fc = report.fail_count
    wc = report.warn_count
    if state == "READY":
        lines.append(f"Stato: READY       — 0 FAIL, 0 WARN")
    elif state == "PARTIAL":
        lines.append(f"Stato: PARTIAL     — 0 FAIL, {wc} WARN")
    else:
        lines.append(f"Stato: BLOCKED     — {fc} FAIL, {wc} WARN")

    if state != "READY":
        lines.append("")
        if state == "PARTIAL":
            lines.append("Passo successivo: puoi procedere con /dev <TSK-id>.")
            lines.append("Per risolvere i WARN: .claude/commands/init-check.md (blocco environment:)")
        else:
            lines.append("Passo successivo: risolvi i FAIL prima di procedere.")
            lines.append("Guida: .claude/commands/init-check.md (blocco environment:)")
    else:
        lines.append("")
        lines.append("Passo successivo: /run oppure /dev <TSK-id>")

    return "\n".join(lines)


def render_json(report: Report) -> str:
    data = {
        "state": report.state,
        "fail_count": report.fail_count,
        "warn_count": report.warn_count,
        "env_configured": report.env_configured,
        "checks": [
            {"label": c.label, "status": c.status, "note": c.note}
            for c in report.checks
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    # la console di Windows (cp1252) non codifica i caratteri non ASCII: il print fallirebbe
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Diagnostica ambiente locale factory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root della factory (default: CWD)",
    )
    parser.add_argument(
        "--probes",
        action="store_true",
        help="Attiva le probe di rete dichiarate in environment.probes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON invece di tabella",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    report = Report()

    # --- Carica factory.config.yaml ---
    config_path = root / "factory.config.yaml"
    config: dict = {}
    if config_path.exists():
        try:
            config = _load_yaml_simple(config_path)
        except Exception as exc:
            report.add("factory.config.yaml", STATUS_WARN, f"(errore di parsing: {exc})")

    env_cfg = config.get("environment", {}) or {}
    report.env_configured = bool(env_cfg)
    # Il parser di ripiego non legge liste di mappe, mappe inline e commenti in coda: sul blocco
    # environment: darebbe valori sbagliati. Meglio un FAIL dichiarato.
    if env_cfg and not _has_pyyaml():
        report.add("environment (config)", STATUS_FAIL,
                   "(non verificabile senza PyYAML: pip install -r tools/requirements.txt)")
        env_cfg = {}

    # -----------------------------------------------------------------------
    # Controlli base (sempre)
    # -----------------------------------------------------------------------
    check_python(report)
    check_pyyaml(report)
    check_git(report)
    check_shell(report)
    check_autocrlf(report)

    perimeter_paths = check_code_paths(report, root, config)
    check_submodules(report, root, perimeter_paths)

    # -----------------------------------------------------------------------
    # Controlli da config (environment:)
    # -----------------------------------------------------------------------
    if env_cfg:
        binaries = env_cfg.get("binaries", []) or []
        if binaries:
            check_binaries(report, binaries)

        env_files = env_cfg.get("env_files", []) or []
        if env_files:
            check_env_files(report, root, env_files)

        variables = env_cfg.get("variables", {}) or {}
        req_vars = variables.get("required", []) or []
        opt_vars = variables.get("optional", []) or []
        if req_vars or opt_vars:
            src = variables.get("source_file") or ""
            check_variables(report, req_vars, opt_vars,
                            (Path(src) if Path(src).is_absolute() else root / src) if src else None)

        node_version_file = env_cfg.get("node_version_file", "")
        if node_version_file:
            check_nvmrc(report, root, node_version_file)
            if not Path(node_version_file).is_absolute():
                for cp in perimeter_paths:
                    cp_dir = root / cp
                    if cp_dir.resolve() != root.resolve() and (cp_dir / node_version_file).exists():
                        check_nvmrc(report, cp_dir, node_version_file, label=cp)

        if args.probes:
            probes = env_cfg.get("probes", []) or []
            if probes:
                check_probes(report, probes)
    # -----------------------------------------------------------------------

    if args.json_output:
        print(render_json(report))
    else:
        print(render_table(report))

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
