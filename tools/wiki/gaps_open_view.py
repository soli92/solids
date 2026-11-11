#!/usr/bin/env python3
"""
gaps_open_view.py — Vista dei gap aperti da wiki/gaps.md.

Legge wiki/gaps.md e scrive memory/gaps-open.md con i soli gap aperti. Due formati, riconosciuti
dal file:
  - a sezioni: ogni gap e' una sezione `## YYYY-MM-DD ...`, chiusa da una riga `**Risolto:**`;
  - a voci: ogni gap e' una voce `- [ ]` (aperta), `- [CONFIRMED OPEN]`, `- [x]` / `- [CLOSED]`
    (chiusa) — forma della derivata portale-servizi-factory, da cui viene questo ramo (EP-073).

- NON modifica wiki/gaps.md (R.5, R.12).
- Idempotente: ogni esecuzione sovrascrive memory/gaps-open.md.
- Output: memory/gaps-open.md con header GENERATO + data UTC + misure della fonte.

Formato di gaps.md atteso:
  Ogni gap e' una sezione ## YYYY-MM-DD ... seguita da campi in grassetto.
  Un gap e' aperto se non contiene una riga "**Risolto:**".
  Un gap e' chiuso se contiene una riga "**Risolto:**".

Verifica: ogni sezione di gap aperto della fonte compare nella vista;
          nessun gap chiuso compare.

Uso: python3 tools/wiki/gaps_open_view.py
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FACTORY_ROOT = Path(__file__).parent.parent.parent
GAPS_PATH = FACTORY_ROOT / "wiki" / "gaps.md"
OUTPUT_PATH = FACTORY_ROOT / "memory" / "gaps-open.md"

# Regex per riconoscere l'header di una sezione gap
GAP_HEADER_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}")
# Marker di chiusura gap
CLOSED_MARKER = "**Risolto:**"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_gaps(lines: list) -> dict:
    """
    Separa wiki/gaps.md in:
    - 'preamble': righe prima del primo gap (frontmatter + intro)
    - 'gaps': lista di dict {header, lines, closed}
      header: prima riga (## ...)
      lines: tutte le righe della sezione (incluso header)
      closed: bool (True se contiene **Risolto:**)
    """
    preamble = []
    gaps = []
    current = None

    for line in lines:
        if GAP_HEADER_RE.match(line):
            if current is not None:
                gaps.append(current)
            current = {"header": line.rstrip("\n"), "lines": [line], "closed": False}
        else:
            if current is None:
                preamble.append(line)
            else:
                current["lines"].append(line)
                if CLOSED_MARKER in line:
                    current["closed"] = True

    if current is not None:
        gaps.append(current)

    return {"preamble": preamble, "gaps": gaps}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _main_sezioni():
    if not GAPS_PATH.exists():
        print(f"ERRORE: {GAPS_PATH} non trovato.", file=sys.stderr)
        sys.exit(1)

    with open(GAPS_PATH, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    source_bytes = sum(len(line.encode("utf-8")) for line in all_lines)
    source_lines = len(all_lines)

    parsed = parse_gaps(all_lines)
    open_gaps = [g for g in parsed["gaps"] if not g["closed"]]
    closed_gaps = [g for g in parsed["gaps"] if g["closed"]]

    # Costruisci output
    output_lines = []
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    output_lines.append("---\n")
    output_lines.append("type: gaps-open-view\n")
    output_lines.append("generated_by: tools/wiki/gaps_open_view.py\n")
    output_lines.append("source: wiki/gaps.md\n")
    output_lines.append(f"generated_at: {now_utc}\n")
    output_lines.append("---\n")
    output_lines.append("\n")
    output_lines.append(
        "<!-- GENERATO da tools/wiki/gaps_open_view.py — non editare; "
        "fonte di verita': wiki/gaps.md -->\n"
    )
    output_lines.append(
        f"<!-- Generato: {now_utc} UTC | "
        f"Fonte: {source_bytes:,} byte, {source_lines} righe -->\n"
    )
    output_lines.append("\n")
    output_lines.append("# Gap Aperti\n")
    output_lines.append("\n")
    output_lines.append(
        "> Vista derivata. Gap aperti estratti da `wiki/gaps.md`.\n"
    )
    output_lines.append(
        "> Per aggiungere o chiudere un gap: usa `wiki/gaps.md` (fonte di verita').\n"
    )
    output_lines.append(
        "> Per rigenerare questa vista: `python3 tools/wiki/gaps_open_view.py`\n"
    )
    output_lines.append("\n")
    output_lines.append(
        f"<!-- Fonte: {len(open_gaps)} gap aperti, {len(closed_gaps)} chiusi -->\n"
    )
    output_lines.append("\n")

    for gap in open_gaps:
        entry_text = "".join(gap["lines"])
        if not entry_text.endswith("\n"):
            entry_text += "\n"
        output_lines.append(entry_text)
        if not entry_text.endswith("\n\n"):
            output_lines.append("\n")

    view_content = "".join(output_lines)
    view_bytes = sum(len(line.encode("utf-8")) for line in output_lines)

    # Verifica: ogni gap aperto deve comparire nella vista
    errors = []
    for gap in open_gaps:
        if gap["header"] not in view_content:
            errors.append(f"MANCANTE: {gap['header'][:100]!r}")

    # Verifica: nessun gap chiuso deve comparire nella vista (solo primo header)
    for gap in closed_gaps:
        if gap["header"] in view_content:
            errors.append(f"GAP CHIUSO NELLA VISTA: {gap['header'][:80]!r}")

    # Scrivi
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    # Stampa misure
    print(f"Fonte:  {GAPS_PATH}")
    print(f"  {source_bytes:,} byte | {source_lines} righe")
    print(f"Gap aperti:  {len(open_gaps)}")
    print(f"Gap chiusi:  {len(closed_gaps)}")
    print()
    print(f"Vista:  {OUTPUT_PATH}")
    print(f"  {view_bytes:,} byte")
    print()

    if errors:
        print(f"VERIFICA: {len(errors)} errori trovati:")
        for e in errors[:10]:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(
            f"Verifica OK: {len(open_gaps)} gap aperti nella vista; "
            f"nessun gap chiuso incluso."
        )


# ---------------------------------------------------------------------------
# Parser (adattato da deliverables/2026-10-05-sharding-file-operativi/shard.py)
# ---------------------------------------------------------------------------

def _parse_gap_entries(lines: list) -> list:
    """
    Parser a stati per gaps.md.
    Restituisce lista di dict con:
      - 'status': 'open' | 'confirmed_open' | 'closed' | 'header' | 'other'
      - 'lines': list[str]  (righe dell'entry, incluse multi-riga)
    """
    entries = []
    current = None

    OPEN_RE = re.compile(r"^- \[ \]")
    CLOSED_RE = re.compile(r"^- \[x\]|^- \[CLOSED\]")
    CONFIRMED_OPEN_RE = re.compile(r"^- \[CONFIRMED OPEN\]")

    for line in lines:
        if line.startswith("---") and line.strip() == "---":
            if current:
                entries.append(current)
            current = {"status": "header", "lines": [line]}
        elif line.startswith("#"):
            if current:
                entries.append(current)
            current = {"status": "header", "lines": [line]}
        elif OPEN_RE.match(line):
            if current:
                entries.append(current)
            current = {"status": "open", "lines": [line]}
        elif CONFIRMED_OPEN_RE.match(line):
            if current:
                entries.append(current)
            current = {"status": "confirmed_open", "lines": [line]}
        elif CLOSED_RE.match(line):
            if current:
                entries.append(current)
            current = {"status": "closed", "lines": [line]}
        elif line.startswith("- ") or line.startswith(">"):
            if current and current["status"] in ("open", "closed", "confirmed_open"):
                # Sub-bullet di un'entry
                current["lines"].append(line)
            elif current and current["status"] not in ("open", "closed", "confirmed_open"):
                current["lines"].append(line)
            else:
                if current:
                    entries.append(current)
                current = {"status": "other", "lines": [line]}
        else:
            # Continuazione dell'entry corrente
            if current is None:
                current = {"status": "header", "lines": [line]}
            else:
                current["lines"].append(line)

    if current:
        entries.append(current)

    return entries


def _is_open(entry: dict) -> bool:
    """Restituisce True se l'entry e' un gap aperto (open o confirmed_open)."""
    return entry["status"] in ("open", "confirmed_open")


def _is_closed(entry: dict) -> bool:
    """Restituisce True se l'entry e' un gap chiuso."""
    return entry["status"] == "closed"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _main_voci():
    if not GAPS_PATH.exists():
        print(f"ERRORE: {GAPS_PATH} non trovato.", file=sys.stderr)
        sys.exit(1)

    with open(GAPS_PATH, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    source_bytes = sum(len(line.encode("utf-8")) for line in all_lines)
    source_lines = len(all_lines)

    entries = _parse_gap_entries(all_lines)

    # Identifica i gap aperti e i loro titoli di sezione
    # Strategia: teniamo traccia della sezione ## corrente.
    # Includiamo nella vista: frontmatter + H1 + preamble, poi per ogni sezione
    # con almeno un gap aperto: il titolo ## + le entry aperte.

    # Separazione: frontmatter + H1 + descrizione intro = prima del primo ##
    # Sezioni ## con contenuto

    # Raccoglie sezioni: list di (header_entry, [sub_entries])
    sections = []
    current_section_header = None
    current_section_entries = []

    for entry in entries:
        if entry["status"] == "header":
            lines_stripped = [l.strip() for l in entry["lines"]]
            # Se e' una sezione ##, salva quella corrente e inizia nuova
            is_section = any(l.startswith("##") and not l.startswith("###") for l in lines_stripped)
            is_h1 = any(l.startswith("# ") and not l.startswith("##") for l in lines_stripped)
            is_frontmatter = any(l == "---" for l in lines_stripped)

            if is_section:
                # Salva sezione precedente se ha entry aperte
                if current_section_header is not None:
                    sections.append((current_section_header, current_section_entries))
                current_section_header = entry
                current_section_entries = []
            elif is_h1 or is_frontmatter or current_section_header is None:
                # Header globale (frontmatter, H1, intro): va nella "sezione 0"
                if current_section_header is None:
                    sections.append((entry, []))
                else:
                    # Header non-## dentro una sezione: trattato come sub-header
                    current_section_entries.append(entry)
            else:
                current_section_entries.append(entry)
        else:
            if current_section_header is not None:
                current_section_entries.append(entry)
            else:
                # Entry prima di qualsiasi sezione: aggiungi alla prima sezione vuota
                sections.append((entry, []))

    # Salva ultima sezione
    if current_section_header is not None:
        sections.append((current_section_header, current_section_entries))

    # Costruisci output: solo le sezioni con gap aperti + header globale
    output_lines = []

    # Header del file generato
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_lines.append("---\n")
    output_lines.append("type: gaps-open-view\n")
    output_lines.append("generated_by: tools/wiki/gaps_open_view.py\n")
    output_lines.append("source: wiki/gaps.md\n")
    output_lines.append(f"generated_at: {now_utc}\n")
    output_lines.append("---\n")
    output_lines.append("\n")
    output_lines.append("<!-- GENERATO da tools/wiki/gaps_open_view.py — non editare; fonte di verita': wiki/gaps.md -->\n")
    output_lines.append(f"<!-- Generato: {now_utc} UTC | Fonte: {source_bytes:,} byte, {source_lines} righe -->\n")
    output_lines.append("\n")
    output_lines.append("# Gap Aperti — portale-servizi-factory\n")
    output_lines.append("\n")
    output_lines.append("> Vista derivata. Gap aperti estratti da `wiki/gaps.md`.\n")
    output_lines.append("> Per aggiungere o chiudere un gap: usa `wiki/gaps.md` (fonte di verita').\n")
    output_lines.append("> Per rigenerare questa vista: `python3 tools/wiki/gaps_open_view.py`\n")
    output_lines.append("\n")

    # Conta gap per verifica
    open_count = 0
    closed_count = 0
    confirmed_open_count = 0

    for entry in entries:
        if entry["status"] == "open":
            open_count += 1
        elif entry["status"] == "confirmed_open":
            confirmed_open_count += 1
        elif entry["status"] == "closed":
            closed_count += 1

    output_lines.append(f"<!-- Fonte: {open_count} gap aperti ([ ]) + {confirmed_open_count} CONFIRMED OPEN = {open_count + confirmed_open_count} totali aperti; {closed_count} chiusi -->\n")
    output_lines.append("\n")

    # Ora emetti le sezioni con gap aperti
    # La sezione 0 (frontmatter/H1/intro) e' globale: non la includiamo verbatim
    # ma abbiamo gia' aggiunto il nostro header sopra.
    # Per le sezioni successive: emettiamo il titolo ## solo se ha gap aperti.

    sections_with_open = []
    for sec_header, sec_entries in sections:
        has_open = any(_is_open(e) for e in sec_entries)
        # Controlla se anche il sec_header stesso e' un gap aperto (edge case)
        header_is_open = _is_open(sec_header)
        if has_open or header_is_open:
            sections_with_open.append((sec_header, sec_entries))

    for sec_header, sec_entries in sections_with_open:
        # Emetti il titolo della sezione
        if sec_header["status"] == "header":
            header_text = "".join(sec_header["lines"])
            # Assicura che la sezione ## sia inclusa verbatim
            if not header_text.endswith("\n"):
                header_text += "\n"
            output_lines.append(header_text)
            if not header_text.endswith("\n\n"):
                # Aggiungi riga vuota dopo il titolo se non c'e'
                if not header_text.endswith("\n"):
                    output_lines.append("\n")
        elif _is_open(sec_header):
            # Il header stesso e' un gap aperto
            output_lines.extend(sec_header["lines"])
            output_lines.append("\n")

        # Emetti solo le entry aperte (skip closed, skip other)
        for entry in sec_entries:
            if _is_open(entry):
                entry_text = "".join(entry["lines"])
                if not entry_text.endswith("\n"):
                    entry_text += "\n"
                output_lines.append(entry_text)
                # Riga vuota separatrice tra entry
                if not entry_text.endswith("\n\n"):
                    output_lines.append("\n")

    view_bytes = sum(len(line.encode("utf-8")) for line in output_lines)

    # Scrivi il file di output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    # Verifica: ogni riga di gap aperto della fonte deve comparire nella vista
    view_content = "".join(output_lines)
    errors = []
    for entry in entries:
        if _is_open(entry):
            for line in entry["lines"]:
                line_stripped = line.rstrip("\n")
                if line_stripped and line_stripped not in view_content:
                    errors.append(f"MANCANTE: {line_stripped[:100]!r}")

    # Verifica: nessun gap chiuso deve comparire nella vista
    for entry in entries:
        if _is_closed(entry):
            # Controlla solo la prima riga (identificatore del gap)
            first_line = entry["lines"][0].rstrip("\n") if entry["lines"] else ""
            if first_line and first_line in view_content:
                errors.append(f"GAP CHIUSO NELLA VISTA: {first_line[:80]!r}")

    # Stampa misure
    print(f"Fonte:  {GAPS_PATH}")
    print(f"  {source_bytes:,} byte | {source_lines} righe")
    print(f"Gap aperti  (- [ ]):          {open_count}")
    print(f"Gap CONFIRMED OPEN:           {confirmed_open_count}")
    print(f"Gap chiusi  ([x] o [CLOSED]): {closed_count}")
    print(f"")
    print(f"Vista:  {OUTPUT_PATH}")
    print(f"  {view_bytes:,} byte")
    print(f"Sezioni con gap aperti:       {len(sections_with_open)}")
    print(f"")

    if errors:
        print(f"VERIFICA: {len(errors)} errori trovati:")
        for e in errors[:10]:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"Verifica OK: tutte le {open_count + confirmed_open_count} entry aperte presenti nella vista; nessun gap chiuso.")

VOCE_RE = re.compile(r"^- \[(?: |x|CLOSED|CONFIRMED OPEN)\]", re.M)


def formato(testo: str) -> str:
    """`voci` se il file ha almeno una voce a checkbox, altrimenti `sezioni`."""
    return "voci" if VOCE_RE.search(testo) else "sezioni"


def main():
    if not GAPS_PATH.exists():
        return _main_sezioni()
    testo = GAPS_PATH.read_text(encoding="utf-8")
    return _main_voci() if formato(testo) == "voci" else _main_sezioni()


if __name__ == "__main__":
    sys.exit(main())
