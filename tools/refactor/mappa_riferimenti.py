#!/usr/bin/env python3
"""mappa_riferimenti.py — Grafo dei riferimenti tra file di una flotta di agenti.

Uso:
    mappa_riferimenti.py <root> [--gate] [--json] [--injection-glob GLOB ...]
                                [--collision-threshold F]

Modalità report (default): stampa nodi, archi, orfani, collisioni di description,
anomalie di frontmatter e mismatch nome/filename.

Modalità --gate: esce con codice != 0 se un gate di grafo fallisce (Fase 3):
  G9  ogni riferimento strutturato (path, dispatch-path, membership) risolve;
  G10 nessun agente irraggiungibile dai punti d'ingresso;
  G11 nessuna foglia references/ citata da un agente dispatchato per iniezione.

Ogni agente è identificato SIA dal `name` di frontmatter SIA dal nome-file (stem):
gli orchestratori spesso citano gli specialisti per nome-file nei path di dispatch
e per `name` in prosa. Un disallineamento tra i due è un rischio di riferimento e
viene segnalato.

Dipendenze: solo standard library. Robusto a CRLF e a byte non-UTF8.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
import os
from pathlib import Path

# Console Windows (cp1252) non gestisce alcuni caratteri: forziamo UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

FM_DELIM = "---"


_EXT = chr(92) * 2 + "?" + chr(92)   # prefisso Windows extended-length: \\?\


def _exists(path) -> bool:
    """exists() robusto: su Windows os.stat fallisce silenziosamente (ritorna False)
    per path > MAX_PATH; ritenta con prefisso extended-length."""
    try:
        if os.path.exists(str(path)):
            return True
    except OSError:
        pass
    if os.name == "nt":
        try:
            return os.path.exists(_EXT + os.path.abspath(str(path)))
        except OSError:
            return False
    return False


def read_text(path: Path) -> str:
    """Legge un file. Su Windows ritenta con prefisso extended-length se il path
    supera MAX_PATH (260); se anche quello fallisce, avvisa e ritorna vuoto invece
    di far crashare l'intera analisi (robustezza vista negli eval su path profondi)."""
    try:
        with open(str(path), encoding="utf-8", errors="replace") as f:
            return f.read().replace("\r\n", "\n")
    except OSError:
        if os.name == "nt":
            try:
                with open(_EXT + os.path.abspath(str(path)), encoding="utf-8", errors="replace") as f:
                    return f.read().replace("\r\n", "\n")
            except OSError:
                pass
        print(f"[AVVISO] impossibile leggere (path troppo lungo?): {path}", file=sys.stderr)
        return ""


_YAML_BLOCK_SCALAR = re.compile(r"^[>|][-+]?\s*$")


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Ritorna (frontmatter_dict, body). Parsing YAML minimale sufficiente per
    name/description/tools/model.

    Gestisce YAML block scalars (`description: >-`, `description: |`): l'indicatore
    (`>-`, `|`, `>+`, ...) è metadata di parsing, non parte del valore. Bug fix
    EP-060 pilot: senza questo, il parser cattura `>-` come contenuto e la
    validazione "description con parentesi angolari" produce falsi positivi su
    tutti i frontmatter multi-line YAML."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != FM_DELIM:
        return {}, text
    fm_lines: list[str] = []
    body_start = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FM_DELIM:
            body_start = i + 1
            break
        fm_lines.append(lines[i])
    if body_start is None:
        return {}, text
    fm: dict[str, str] = {}
    key = None
    for ln in fm_lines:
        m = re.match(r"^([A-Za-z][\w-]*):\s?(.*)$", ln)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            # YAML block scalar indicator (>-, |-, >, |, >+, |+) → non è contenuto
            fm[key] = "" if _YAML_BLOCK_SCALAR.match(val) else val
        elif key is not None and ln.strip():
            fm[key] = (fm[key] + " " + ln.strip()).strip()
    return fm, "\n".join(lines[body_start:])


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    return v


def norm(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


@dataclass
class Node:
    path: Path
    rel: str
    fmname: str           # `name` di frontmatter (normalizzato)
    stem: str             # nome-file senza .md
    description: str
    body: str
    has_frontmatter: bool
    is_index: bool = False
    out: set[str] = field(default_factory=set)     # id risolti citati (fmname o stem)
    out_paths: set[str] = field(default_factory=set)
    md_rel: set[str] = field(default_factory=set)   # citazioni .md agent-relative (raw) — per G11
    md_claude: set[str] = field(default_factory=set)  # basename .md citati con ancora .claude/
    incoming: int = 0

    @property
    def ids(self) -> set[str]:
        return {i for i in (self.fmname, self.stem) if i}

    @property
    def label(self) -> str:
        return self.fmname or self.stem

    @property
    def kind(self) -> str:
        """Discriminatore per specie (EP-060 pilot fix G10): il calcolo orfani deve
        applicarsi solo agli AGENTI (nodi in `agents/`). Skill/commands sono unità
        invocate dinamicamente via `Skill` tool o slash-command, non tramite path
        espliciti — marcarle 'orfane' produce falsi positivi ricorrenti."""
        parts = set(Path(self.rel).parts)
        if "agents" in parts or "specialists" in parts:
            return "agent"
        if "skills" in parts:
            return "skill"
        if "commands" in parts:
            return "command"
        return "unknown"


FENCE_RE = re.compile(r"^```")
HANDOFF_RE = re.compile(r"`?([a-z0-9][a-z0-9-]{2,})`?\s*(?:->|→|<->|↔)\s*`?([a-z0-9][a-z0-9-]{2,})`?")
BACKTICK_RE = re.compile(r"`([a-z0-9][a-z0-9-]{2,})`")
# PATH_RE richiede un'estensione file: evita falsi positivi su prosa tipo
# "scripts/tools" (visto negli eval), matchando solo path a file veri.
PATH_RE = re.compile(r"(?<![\w./-])((?:references|scripts|assets)/[A-Za-z0-9._/-]*\.[A-Za-z0-9]{1,5}(?:#[A-Za-z0-9._-]+)?)")
# Qualsiasi citazione di file .md con almeno un separatore di cartella (per G11).
MD_CITE_RE = re.compile(r"(?<![\w./~-])([\w./~-]*[\w-]/[\w./~-]*\.md)(?![\w])")
DISPATCH_PATH_RE = re.compile(r"(?:agents|specialists)/([A-Za-z0-9_-]+)\.md")
MEMBER_RE = re.compile(r"^\s*[-*]\s+`([a-z0-9][a-z0-9-]{2,})`")
INJECTION_HINT_RE = re.compile(r"extract the body|Task\(\s*(?:description|prompt)|prompt=\"?<body>", re.I)
PREFIX_RE = re.compile(r"([\w./~-]*)$")


def leading_token(line: str, start: int) -> str:
    """Token di path immediatamente prima di una citazione, per distinguere un
    riferimento interno alla flotta (nessun prefisso, o '.claude/') da uno
    qualificato con il nome di un'altra skill (esterno)."""
    m = PREFIX_RE.search(line[:start])
    return m.group(1) if m else ""


def internal_prefix(tok: str) -> bool:
    t = tok.rstrip("/")
    return t == "" or t == "." or t.endswith(".claude")


def build_nodes(root: Path) -> list[Node]:
    files = [root] if root.is_file() else sorted(root.rglob("*.md"))
    base = root if root.is_dir() else root.parent
    nodes: list[Node] = []
    for f in files:
        if {"node_modules", "__pycache__", "evals"} & set(f.parts):
            continue
        fm, body = split_frontmatter(read_text(f))
        nodes.append(Node(
            path=f, rel=str(f.relative_to(base)),
            fmname=norm(unquote(fm.get("name", ""))),
            stem=norm(f.stem),
            description=unquote(fm.get("description", "")),
            body=body, has_frontmatter=bool(fm),
        ))
    return nodes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--collision-threshold", type=float, default=0.6)
    ap.add_argument("--injection-glob", action="append", default=[])
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"[ERRORE] path inesistente: {root}", file=sys.stderr)
        return 2
    base = root if root.is_dir() else root.parent
    nodes = build_nodes(root)
    if not nodes:
        print("[ERRORE] nessun file .md trovato.", file=sys.stderr)
        return 2

    # indice id -> nodo (fmname e stem entrambi puntano al nodo)
    by_id: dict[str, Node] = {}
    for n in nodes:
        for i in n.ids:
            by_id.setdefault(i, n)
    known = set(by_id)

    # rileva indici di flotta
    for n in nodes:
        cited = sum(1 for k in known if re.search(rf"`{re.escape(k)}`", n.body))
        if (Path(n.rel).name.lower() == "agents.md"
                or (not n.has_frontmatter and cited >= 3)
                or "commands" in Path(n.rel).parts):  # Bug fix EP-060 US-234 TSK-549: commands/*.md sempre entry point
            n.is_index = True
    index_nodes = [n for n in nodes if n.is_index]
    # G10 orphan check applies to AGENTS only (EP-060 pilot fix): skill/commands are
    # invoked dynamically via Skill tool or slash-command, not via explicit path arcs.
    agents = [n for n in nodes if n.has_frontmatter and not n.is_index and n.kind == "agent"]

    # rileva cartelle dispatchate per iniezione: la cartella nominata NELLA STESSA
    # frase della frase di iniezione (robusto ai path-placeholder tipo <name>.md).
    # Per-riga per non catturare cartelle di diagrammi/liste lontane.
    injection_dirs: set[str] = set()
    for idx in index_nodes:
        for ln in idx.body.split("\n"):
            if INJECTION_HINT_RE.search(ln):
                for d in ("specialists", "agents"):
                    if f"{d}/" in ln:
                        injection_dirs.add(d)

    unresolved: list[tuple[str, str]] = []    # path/agenti interni assenti (gating)
    external_refs: list[tuple[str, str]] = []  # cross-skill o altri path di progetto (info)

    # --- estrazione archi + G9 riferimenti strutturati (pass per riga + heading)
    for n in nodes:
        heading = ""
        fence = False  # EP-060 pilot fix: skippa i code fence (ospitano esempi/placeholder foo/bar/baz)
        for ln in n.body.split("\n"):
            if FENCE_RE.match(ln):
                fence = not fence
                continue
            if fence:
                continue
            hm = re.match(r"^\s*(?:#+\s+|\*\*)(.+?)(?:\*\*|:)?\s*$", ln)
            if hm and (ln.lstrip().startswith("#") or ln.strip().startswith("**")):
                heading = hm.group(1).lower()
            if not ln.lstrip().startswith(">"):    # le blockquote ospitano esempi
                # citazioni .md (per G11): distingui forma .claude/-ancorata (raggiungibile
                # dal subagent iniettato, cwd=root) da forma agent-relative (non raggiungibile)
                for m in MD_CITE_RE.finditer(ln):
                    raw = m.group(1)
                    if raw.startswith((".claude/", "~/.claude/", "claude/")):
                        n.md_claude.add(raw.rsplit("/", 1)[-1])
                    elif internal_prefix(leading_token(ln, m.start())):
                        n.md_rel.add(raw)
                # path refs references|scripts|assets
                for m in PATH_RE.finditer(ln):
                    p = m.group(1).split("#")[0]
                    if not internal_prefix(leading_token(ln, m.start())):
                        external_refs.append((n.rel, f"{leading_token(ln, m.start())}{m.group(1)}"))
                        continue
                    n.out_paths.add(p)
                    # i path interni si citano relativi al file OPPURE alla radice
                    if not (_exists(n.path.parent / p) or _exists(base / p)):
                        unresolved.append((n.rel, f"path {p} (file assente)"))
                # dispatch-path agents|specialists/<name>.md
                for m in DISPATCH_PATH_RE.finditer(ln):
                    nm = norm(m.group(1))
                    if "<" in m.group(1) or nm.endswith("-name"):
                        continue
                    if not internal_prefix(leading_token(ln, m.start())):
                        external_refs.append((n.rel, f"{leading_token(ln, m.start())}{m.group(0)}"))
                        continue
                    if nm in known:
                        n.out.add(nm)
                    else:
                        unresolved.append((n.rel, f"path {m.group(0)} (file assente)"))
            # bullet list `- `nome`` : skill se sotto un heading "Skills", altrimenti membro
            # Bug fix EP-060 US-234 TSK-549: MEMBER_RE context-aware — classifica membership
            # SOLO sotto heading espliciti; bullets vocabolario chiuso non diventano unresolved.
            m = MEMBER_RE.match(ln)
            if m:
                nm = m.group(1)
                if "skill" in heading:
                    if nm not in known:
                        external_refs.append((n.rel, nm))
                elif any(k in heading for k in ("members", "team", "membership", "partecipanti")):
                    # Solo qui: heading membership esplicito → classifica come arco + segnala mancanti
                    if nm in known:
                        n.out.add(nm)
                    elif n.is_index:
                        unresolved.append((n.rel, f"membership `{nm}` (nessun agente)"))
                # else: NON classificare come membership (bullets vocabolario chiuso, pass/reject/ecc.)
                elif nm in known:
                    n.out.add(nm)  # arco leggero (backtick reference generica), non membership
        # handoff arrows e backtick: SOLO archi tra nodi noti (niente reporting rumoroso)
        for m in HANDOFF_RE.finditer(n.body):
            for g in m.groups():
                if g in known:
                    n.out.add(g)
        for m in BACKTICK_RE.finditer(n.body):
            if m.group(1) in known:
                n.out.add(m.group(1))
        n.out -= n.ids  # niente auto-riferimento

    # dedup preservando l'ordine
    unresolved = list(dict.fromkeys(unresolved))
    external_refs = list(dict.fromkeys(external_refs))

    # archi entranti
    for n in nodes:
        for tgt in n.out:
            node = by_id.get(tgt)
            if node and node is not n:
                node.incoming += 1

    # --- G10: orfani / irraggiungibili (N/A su target a unità singola)
    is_fleet = bool(index_nodes) or len(agents) > 1
    orphans = [n.label for n in agents if n.incoming == 0] if is_fleet else []
    reachable: set[str] = set()
    frontier = [i for idx in index_nodes for i in idx.ids]
    reachable.update(frontier)
    while frontier:
        node = by_id.get(frontier.pop())
        if not node:
            continue
        for tgt in node.out:
            if tgt not in reachable:
                reachable.add(tgt)
                tn = by_id.get(tgt)
                if tn:
                    frontier.extend(tn.ids - reachable)
    unreachable = [n.label for n in agents if index_nodes and not (n.ids & reachable)]

    # --- G11: dispatch-safety (V-9). Un agente dispatchato per iniezione riceve
    # solo il corpo: una foglia esterna è raggiungibile SOLO se citata con path
    # .claude/-ancorato (cwd del subagent = root). Una citazione agent-relative a
    # una foglia esistente (non un altro agente) SENZA forma .claude/ = violazione.
    v9: list[tuple[str, str]] = []
    agent_ids = {i for a in agents for i in a.ids}   # solo AGENTI (le foglie sono nodi ma non agenti)
    for n in agents:
        in_inj = any(Path(n.rel).match(g) for g in args.injection_glob) or \
            (bool(injection_dirs) and bool(injection_dirs & set(Path(n.rel).parts)))
        if not in_inj:
            continue
        for raw in sorted(n.md_rel):
            basename = raw.rsplit("/", 1)[-1]
            stem = norm(basename[:-3])           # senza '.md'
            if stem in agent_ids:                # è un altro AGENTE, non una foglia
                continue
            if not (_exists(n.path.parent / raw) or _exists(base / raw)):
                continue                         # foglia inesistente -> illustrativa/G9
            if basename not in n.md_claude:       # nessuna forma .claude/ raggiungibile
                v9.append((n.rel, raw))

    # --- anomalie
    anomalies = []
    for n in agents:
        # SKILL.md ha per convenzione stem 'skill' != slug: non è un mismatch.
        if (n.fmname and n.stem and n.fmname != n.stem
                and Path(n.rel).name != "SKILL.md"):
            anomalies.append(f"{n.rel}: name '{n.fmname}' != filename '{n.stem}' "
                             f"(citato in due modi -> rischio riferimento)")
        if len(n.description) > 1024:
            anomalies.append(f"{n.label}: description {len(n.description)} char (>1024)")
        if "<" in n.description or ">" in n.description:
            anomalies.append(f"{n.label}: description con parentesi angolari (rifiutata all'upload)")
        if n.has_frontmatter and not n.description:
            anomalies.append(f"{n.label}: description assente")

    # --- collisioni description (Jaccard)
    def toks(d: str) -> set[str]:
        stop = {"agent", "agente", "usare", "quando", "questo", "della", "delle",
                "with", "that", "your", "this", "into", "uses", "when", "help",
                "code", "review"}
        return {t for t in re.findall(r"[a-z]{4,}", d.lower()) if t not in stop}
    coll = []
    da = [n for n in agents if n.description]
    for i in range(len(da)):
        for j in range(i + 1, len(da)):
            a, b = toks(da[i].description), toks(da[j].description)
            if a and b:
                jac = len(a & b) / len(a | b)
                if jac >= args.collision_threshold:
                    coll.append((da[i].label, da[j].label, round(jac, 2)))
    coll.sort(key=lambda x: -x[2])

    result = {
        "nodi": len(nodes), "agenti": len(agents),
        "indici": [n.rel for n in index_nodes],
        "injection_dispatched": sorted(injection_dirs),
        "unresolved_refs": unresolved, "orphans": orphans,
        "unreachable": unreachable, "v9_violations": v9,
        "external_refs": external_refs,
        "anomalies": anomalies, "description_collisions": coll,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=" * 64)
        print(f"GRAFO DEI RIFERIMENTI: {root}")
        print("=" * 64)
        print(f"nodi: {len(nodes)} | agenti: {len(agents)} | indici: {len(index_nodes)}")
        if index_nodes:
            print("  indici:", ", ".join(n.rel for n in index_nodes))
        if injection_dirs:
            print("  dispatch per iniezione:", ", ".join(sorted(injection_dirs)))
        print("\n-- G9 riferimenti strutturati non risolti --")
        print("  (nessuno)" if not unresolved else
              "\n".join(f"  [MANCANTE] {f}: {r}" for f, r in unresolved))
        print("\n-- G10 agenti orfani (nessun arco entrante) --")
        print("  (nessuno)" if not orphans else "  " + ", ".join(sorted(orphans)))
        if index_nodes:
            print("-- G10 agenti irraggiungibili dai punti d'ingresso --")
            print("  (nessuno)" if not unreachable else "  " + ", ".join(sorted(unreachable)))
        print("\n-- G11 foglie non raggiungibili da agenti dispatchati per iniezione (V-9) --")
        print("  (nessuna)" if not v9 else "\n".join(f"  [V-9] {f} -> {r}" for f, r in v9))
        print("\n-- riferimenti esterni: cross-skill o altri path di progetto "
              "(informativo, non-gating) --")
        print("  (nessuno)" if not external_refs else
              "\n".join(f"  {f}: `{s}`" for f, s in external_refs))
        print("\n-- anomalie (frontmatter / nome-file) --")
        print("  (nessuna)" if not anomalies else "\n".join(f"  {a}" for a in anomalies))
        print(f"\n-- collisioni di description (Jaccard >= {args.collision_threshold}) --")
        print("  (nessuna)" if not coll else
              "\n".join(f"  {a} ~ {b}  ({j})" for a, b, j in coll))

    if args.gate:
        if unresolved or unreachable or v9:
            print("\nGATE GRAFO: FAIL (G9/G10/G11).", file=sys.stderr)
            return 1
        print("\nGATE GRAFO: PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
