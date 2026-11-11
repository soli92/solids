#!/usr/bin/env python3
"""
check_notes_config.py — Lint check: consistency notes vs actual config values.

Reads the `notes:` field of factory.config.yaml, extracts the declarations
`nested.field: value` via regex and compares them to the actual values.
Severity: WARNING (notes are documentation, not contract — US-174 EP-047).

Usage:
    python tools/lint/check_notes_config.py [factory_path]

    factory_path — factory path (default: current directory)

Exit code:
    0 — no warnings found
    1 — at least one warning found


"""

import re
import sys
from pathlib import Path


# Regex to capture `nested.field: value` declarations in notes.

# The field must contain at least one period (e.g. code_quality.enabled).

# The value is limited to: true | false | an integer | an alphanumeric word-dash.

_NOTES_PATTERN = re.compile(
    r'(\w[\w._]*(?:\.\w[\w._]*)+):\s*(true|false|\d+|[\w-]+)'
)


def _normalize_value(raw: str):
    """Converte la stringa catturata dalla regex al tipo Python equivalente."""
    if raw == "true":
        return True
    if raw == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _get_nested(config: dict, path: str):
    """
    Naviga il config YAML per path dot-separated.
    Restituisce (valore, trovato).
    """
    keys = path.split(".")
    current = config
    for key in keys:
        if not isinstance(current, dict):
            return None, False
        if key not in current:
            return None, False
        current = current[key]
    return current, True


def check_notes_config(factory_path: Path) -> int:
    """
    Esegue il check e restituisce il numero di warning trovati.
    """
    config_file = factory_path / "factory.config.yaml"

    if not config_file.exists():
        print(f"[lint/notes-config] factory.config.yaml non trovato in {factory_path}")
        return 0

    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        print("[lint/notes-config] ERROR: PyYAML non installato (pip install pyyaml)")
        sys.exit(2)

    with open(config_file, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not isinstance(config, dict):
        print("[lint/notes-config] factory.config.yaml non è un mapping valido")
        return 0

    notes = config.get("notes", "") or ""

    print("[lint/notes-config] Checking notes field coerenza...")

    if not notes.strip():
        print("[lint/notes-config] 0 warning(s) trovati.")
        return 0

    # Removes double-quoted substrings before applying the regex.

    # Avoid false positives from historical references or citations as "field: stale-value".

    # Example: notes declared "vcs.mode: none" → skip (was old, now correct).

    notes_clean = re.sub(r'"[^"]*"', "", notes)

    warnings = 0
    for match in _NOTES_PATTERN.finditer(notes_clean):
        field_path = match.group(1)
        raw_value = match.group(2)
        declared_value = _normalize_value(raw_value)

        actual_value, found = _get_nested(config, field_path)

        if not found:
            # Field does not exist in config: skip (not error, field might

            # be deprecated or declared for derived factories).

            print(f"  OK:   {field_path} (non trovato nel config — skip)")
            continue

        # Skip complex values (dict/list): not comparable to a declaration

        # scale in the notes. Typically config blocks documented as TEMPLATE.
        if isinstance(actual_value, (dict, list)):
            print(f"  OK:   {field_path} (valore complesso nel config — skip)")
            continue

        if actual_value != declared_value:
            print(
                f"  WARN: notes dichiara '{field_path}: {raw_value}' "
                f"ma il valore effettivo e' {actual_value!r}"
            )
            warnings += 1

    print(f"[lint/notes-config] {warnings} warning(s) trovati.")
    return warnings


def main() -> None:
    factory_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    factory_path = factory_path.resolve()
    warnings = check_notes_config(factory_path)
    sys.exit(0 if warnings == 0 else 1)


if __name__ == "__main__":
    main()
