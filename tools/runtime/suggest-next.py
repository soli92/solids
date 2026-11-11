#!/usr/bin/env python3
"""
suggest-next.py — Runtime Contextual Suggestions hook (EP-033, v2.24 + EP-035 rule)
Canonical path: tools/runtime/suggest-next.py (provider-agnostic).
Claude Code hooks may call this directly or via .claude/tools/suggest-next.py shim.

Typically invoked by Stop hooks after certain commands.
Operates outside the LLM context: static rules, deterministic, no API calls.

Adapter note: The script is runtime-agnostic; the *binding* hook is adapter-specific
(.claude/settings.json Stop, Cursor post-command, Aider wrapper shell).

Usage:
  python3 tools/runtime/suggest-next.py --command=/dev [--dry-run]

  --command name of the command just executed (e.g. /dev, /lint, /run, /review)
  --dry-run print evaluated rules to stderr, no suggested output (debug)

Changelog:
  v2.24 EP-033 core rules (a11y, ux-ui-review, semantic-drift-scan, premortem, analytics)
  EP-035 Added Rule EP-035: TSK FE + design-spec without recent prototype → /prototype
  Sprint-1+ Canonical under tools/runtime/; shim retained under .claude/tools/


"""

import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def find_project_root():
    """Walk up from cwd until a factory root is found (adapter-agnostic).

    Markers (any): factory.config.yaml, PATTERN.md, tools/ + ( .claude/ | .cursor/ | .aider/ ).
    Prefer factory.config.yaml so Cursor/Aider-only checkouts still resolve.
    """
    current = Path(os.getcwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "factory.config.yaml").is_file():
            return candidate
        if (candidate / "PATTERN.md").is_file() and (candidate / "tools").is_dir():
            return candidate
        if (candidate / ".claude").is_dir() and (candidate / "tools").is_dir():
            return candidate
    return None


def read_log_tail(log_path, n=100):
    """Legge le ultime n righe di wiki/log.md. Restituisce stringa o '' se assente."""
    try:
        p = Path(log_path)
        if not p.exists():
            return ""
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def read_config_flags(config_path):
    """
    Parsing YAML manuale di factory.config.yaml per le chiavi rilevanti.
    Restituisce dict con chiavi booleane; default False se file assente o chiave assente.
    """
    flags = {
        "a11y_enabled": False,
        "ux_ui_enabled": False,
        "visual_oracle_enabled": False,
        "code_quality_enabled": False,
        "analytics_enabled": False,
        # EP-035: Prototype Generation Layer
        "prototyping_enabled": False,
    }
    try:
        p = Path(config_path)
        if not p.exists():
            return flags
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*enabled:\s*true", text, re.MULTILINE):
            # Contextual per-section detection

            pass
        if re.search(r"a11y\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", text) or \
           re.search(r"a11y\.enabled:\s*true", text):
            flags["a11y_enabled"] = True
        if re.search(r"ux_ui\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", text) or \
           re.search(r"ux_ui\.enabled:\s*true", text):
            flags["ux_ui_enabled"] = True
        if re.search(r"visual_oracle\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", text) or \
           re.search(r"fe_correctness\.visual_oracle\.enabled:\s*true", text):
            flags["visual_oracle_enabled"] = True
        if re.search(r"code_quality\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", text) or \
           re.search(r"code_quality\.enabled:\s*true", text):
            flags["code_quality_enabled"] = True
        if re.search(r"analytics\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", text) or \
           re.search(r"analytics\.measurement\.enabled:\s*true", text):
            flags["analytics_enabled"] = True
        # EP-035: rileva prototyping.enabled: true
        # The prototyping block: as a top-level key may be absent (backward compat — silently skip).

        # NOTE: The search excludes YAML comments (lines starting with #).

        # Pattern: top-level "prototyping:" block followed by "enabled: true" on non-comment line.

        # Fallback: entry "prototyping.enabled: true" as dot-notation key (not in comments).

        _text_no_comments = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("#")
        )
        if re.search(r"^prototyping\s*:\s*$", _text_no_comments, re.MULTILINE) and \
           re.search(r"prototyping\s*:\s*\n(?:.*\n)*?\s*enabled:\s*true", _text_no_comments):
            flags["prototyping_enabled"] = True
        elif re.search(r"^prototyping\.enabled:\s*true\s*$", _text_no_comments, re.MULTILINE):
            flags["prototyping_enabled"] = True
    except Exception:
        pass
    return flags


def has_recent_prototype_in_log(log_tail, us_id, days=7):
    """
    Regola EP-035 — deduplication.
    Restituisce True se wiki/log.md contiene un'entry PROTOTYPE_GENERATED
    per us_id negli ultimi `days` giorni.
    Pattern cercato: riga con PROTOTYPE_GENERATED + us_id (case-insensitive)
    entro la finestra temporale.
    Se us_id e' None/vuoto, non puo' deduplicare → assume nessun prototipo recente.
    """
    if not us_id:
        return False
    try:
        cutoff = datetime.utcnow().date() - timedelta(days=days)
        # Search for entries with date + PROTOTYPE_GENERATED + us_id

        # Formato log: ## YYYY-MM-DD HH:MM — prototype <id>
        # or line with PROTOTYPE_GENERATED marker: ...

        date_pattern = re.compile(r"##\s+(\d{4}-\d{2}-\d{2})")
        prototype_pattern = re.compile(
            r"PROTOTYPE_GENERATED|prototype\s+" + re.escape(us_id),
            re.IGNORECASE,
        )
        us_pattern = re.compile(re.escape(us_id), re.IGNORECASE)

        lines = log_tail.splitlines()
        current_date = None
        for line in lines:
            date_match = date_pattern.search(line)
            if date_match:
                try:
                    current_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
                except ValueError:
                    current_date = None
            # Check if this line contains PROTOTYPE_GENERATED + us_id

            if current_date and current_date >= cutoff:
                if prototype_pattern.search(line) and us_pattern.search(line):
                    return True
        return False
    except Exception:
        return False


def has_design_spec_for_us(root, us_id):
    """
    Regola EP-035 — verifica presenza di design-spec.
    Cerca:
      1. output/designs/{us_id}-spec.md (pattern esplicito EP-035)
      2. wiki/sources/*{us_id}* con pattern 'design' o 'spec' nel nome
      3. management/kanban/**/{us_id}**/design-spec.md (prossimita' dir US)
    Restituisce True se almeno uno dei path esiste.
    Se us_id e' None/vuoto → False (non puo' cercare).
    """
    if not us_id:
        return False
    try:
        us_id_lower = us_id.lower()

        # 1. output/designs/{us_id}-spec.md
        candidate1 = root / "output" / "designs" / f"{us_id}-spec.md"
        if candidate1.exists():
            return True

        # 2. wiki/sources/*{us_id}* with 'design' or 'spec' in the filename

        wiki_sources = root / "wiki" / "sources"
        if wiki_sources.is_dir():
            for f in wiki_sources.iterdir():
                fname = f.name.lower()
                if us_id_lower in fname and ("design" in fname or "spec" in fname):
                    return True

        # 3. management/kanban/**/{us_id}*/design-spec.md
        kanban_root = root / "management" / "kanban"
        if kanban_root.is_dir():
            for ep_dir in kanban_root.iterdir():
                if not ep_dir.is_dir():
                    continue
                for us_dir in ep_dir.iterdir():
                    if not us_dir.is_dir():
                        continue
                    if us_id_lower in us_dir.name.lower():
                        spec_candidate = us_dir / "design-spec.md"
                        if spec_candidate.exists():
                            return True

        return False
    except Exception:
        return False


def extract_us_id_from_log(log_tail):
    """
    Estrae l'us_id dall'ultima entry di log che menziona un layer fe.
    Cerca pattern 'US-NNN' nelle vicinanze di 'layer: fe' o 'layer=fe'.
    Restituisce il primo us_id trovato o None.
    """
    try:
        # Look for the last few lines that mention FE

        fe_section = ""
        lines = log_tail.splitlines()
        # Look for the last section ## which contains fe layers

        current_section_lines = []
        last_fe_section_lines = []
        for line in lines:
            if line.startswith("## "):
                # new section: save the previous one if it was FE

                section_text = "\n".join(current_section_lines)
                if re.search(r"layer:\s*fe\b|layer=fe\b|TSK.*\bfe\b", section_text, re.IGNORECASE):
                    last_fe_section_lines = current_section_lines[:]
                current_section_lines = [line]
            else:
                current_section_lines.append(line)
        # Also check the last accumulated section

        section_text = "\n".join(current_section_lines)
        if re.search(r"layer:\s*fe\b|layer=fe\b|TSK.*\bfe\b", section_text, re.IGNORECASE):
            last_fe_section_lines = current_section_lines[:]

        if last_fe_section_lines:
            section_text = "\n".join(last_fe_section_lines)
            m = re.search(r"\b(US-\d+)\b", section_text)
            if m:
                return m.group(1)
        return None
    except Exception:
        return None


def command_installed(root, cmd_name):
    """
    Verifica se .claude/commands/<cmd_name>.md esiste.
    cmd_name deve essere senza slash (es. 'a11y', 'semantic-drift-scan').
    """
    try:
        cmd_file = root / ".claude" / "commands" / f"{cmd_name}.md"
        return cmd_file.exists()
    except Exception:
        return False


def evaluate_rules(command, log_tail, flags, root):
    """
    Applica le regole statiche per il comando ricevuto.
    Restituisce lista di stringhe di suggerimento (prefisso '💡' aggiunto dal caller).
    """
    suggestions = []
    cmd = command.lstrip("/")

    # --- /dev rules ---
    if cmd == "dev":
        # Detect whether the latest log entry concerns an FE TSK
        fe_in_log = bool(
            re.search(r"layer:\s*fe\b|layer=fe\b|TSK.*\bfe\b", log_tail, re.IGNORECASE)
        )
        if fe_in_log:
            # Rule 1: suggest /a11y if not already in the log for this US

            a11y_in_log = bool(re.search(r"/a11y\b|a11y.*done|a11y.*completat", log_tail, re.IGNORECASE))
            if not a11y_in_log and command_installed(root, "a11y"):
                suggestions.append("Considera /a11y: TSK FE completato.")
            # Rule 2: suggest /ux-ui-review if not already in the log

            ux_in_log = bool(re.search(r"/ux-ui-review\b|ux-ui-review.*done|ux.ui.*review.*completat", log_tail, re.IGNORECASE))
            if not ux_in_log and command_installed(root, "ux-ui-review"):
                suggestions.append("Considera /ux-ui-review: componenti UI prodotti.")
            # EP-035 rule: suggest /prototype if prototyping enabled,
            # US has design-spec but no recent prototypes in wiki/log.md

            # Backward compat: if prototyping: not present in config → silent skip

            if flags.get("prototyping_enabled", False) and command_installed(root, "prototype"):
                us_id = extract_us_id_from_log(log_tail)
                has_spec = has_design_spec_for_us(root, us_id)
                has_proto = has_recent_prototype_in_log(log_tail, us_id, days=7)
                if has_spec and not has_proto:
                    us_label = us_id if us_id else "<US-id>"
                    suggestions.append(
                        f"Suggerimento EP-035: {us_label} ha spec ma nessun prototipo recente"
                        f" → considera /prototype {us_label}"
                    )

    # --- /lint rules ---
    elif cmd == "lint":
        # Rule 3: staleness in the log

        staleness_in_log = bool(re.search(r"staleness|WARNING staleness", log_tail, re.IGNORECASE))
        if staleness_in_log and command_installed(root, "semantic-drift-scan"):
            suggestions.append("Considera /semantic-drift-scan: il lint segnala staleness.")

    # --- /run rules ---
    elif cmd == "run":
        # Rule 4: open epic without premortem
        # Look for pattern "status: open" associated with epic (EP-NNN) without "premortem" nearby

        epic_open = re.findall(r"(EP-\d+).*status:\s*open|status:\s*open.*(EP-\d+)", log_tail, re.IGNORECASE)
        premortem_in_log = bool(re.search(r"premortem", log_tail, re.IGNORECASE))
        if epic_open and not premortem_in_log and command_installed(root, "premortem"):
            # Extract the first epic id found

            epic_id = ""
            for m in epic_open:
                epic_id = m[0] if m[0] else m[1]
                if epic_id:
                    break
            if epic_id:
                suggestions.append(f"Considera /premortem {epic_id}: epic aperta senza premortem.")
            else:
                suggestions.append("Considera /premortem <epic-id>: epic aperta senza premortem.")

    # --- /review rules ---
    elif cmd == "review":
        # Rule 5: last entry "pass" + >=3 TSK done in the current week

        pass_in_log = bool(re.search(r"\bpass\b", log_tail, re.IGNORECASE))
        if pass_in_log:
            # Count "done" entries in the current week
            today = datetime.utcnow().date()
            week_start = today - timedelta(days=today.weekday())
            week_pattern = re.compile(
                r"\[(\d{4}-\d{2}-\d{2})[^\]]*\].*\bdone\b", re.IGNORECASE
            )
            done_this_week = 0
            for m in week_pattern.finditer(log_tail):
                try:
                    entry_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                    if entry_date >= week_start:
                        done_this_week += 1
                except ValueError:
                    pass
            if done_this_week >= 3 and command_installed(root, "analytics"):
                suggestions.append(
                    "Considera /analytics: settimana produttiva — un report costi potrebbe essere utile."
                )

    return suggestions


def main():
    parser = argparse.ArgumentParser(
        description="suggest-next.py — Runtime Contextual Suggestions (EP-033, v2.24)"
    )
    parser.add_argument(
        "--command",
        required=True,
        help="Nome del comando appena eseguito (es. /dev, /lint, /run, /review)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Stampa le regole valutate su stderr, nessun output suggerito (debug)",
    )
    args = parser.parse_args()

    root = find_project_root()
    if root is None:
        sys.exit(0)

    log_path = root / "wiki" / "log.md"
    config_path = root / "factory.config.yaml"

    log_tail = read_log_tail(log_path, n=100)
    flags = read_config_flags(config_path)

    if args.dry_run:
        print(f"[dry-run] command={args.command}", file=sys.stderr)
        print(f"[dry-run] root={root}", file=sys.stderr)
        print(f"[dry-run] log_tail_len={len(log_tail)}", file=sys.stderr)
        print(f"[dry-run] flags={flags}", file=sys.stderr)

    suggestions = evaluate_rules(args.command, log_tail, flags, root)

    if args.dry_run:
        print(f"[dry-run] suggestions={suggestions}", file=sys.stderr)
        sys.exit(0)

    for s in suggestions:
        print(f"\U0001F4A1 {s}")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
