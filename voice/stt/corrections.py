"""voice/stt/corrections.py — Post-STT correction dictionary for domain terms.

Applies exact token substitutions after faster-whisper transcription.
The medium model transcribes in "pure" Italian and normalizes English technical
terms toward phonetically similar Italian words (e.g. "task" → "tasche").

Source: E2E session 2026-07-10 (16 utterances, Italian speech with factory terms).

Usage:
    from voice.stt.corrections import apply_corrections
    text = apply_corrections(raw_transcript)
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Correction table: {pattern_regex: replacement}
# Keys in lowercase; apply_corrections works on lowercased text + restores case.
# Order: longer/more specific substitutions first to avoid conflicts.
# ---------------------------------------------------------------------------

_CORRECTIONS: dict[str, str] = {
    # Factory / kanban terms
    r"\btasche\b": "task",
    r"\btask[ei]\b": "task",          # "taski", "taske"
    r"\bcamman\b": "kanban",
    r"\bcamban\b": "kanban",
    r"\bcanban\b": "kanban",
    r"\bkamban\b": "kanban",

    # Voice technical acronyms
    r"\bvod\b": "VAD",
    r"\bvat\b": "VAD",               # possible variant
    r"\bstt\b": "STT",
    r"\btts\b": "TTS",
    r"\bfsm\b": "FSM",

    # Handsfree keyword (detected phonetic variants)
    r"\bin spree\b": "handsfree",
    r"\binspree\b": "handsfree",
    r"\bspree\b": "handsfree",        # only when isolated

    # Factory identifiers
    r"\bep\s*-\s*0(\d{2})\b": r"EP-0\1",   # "ep - 044" → "EP-044"
    r"\bus\s*-\s*(\d+)\b": r"US-\1",
    r"\btsk\s*-\s*(\d+)\b": r"TSK-\1",

    # Mis-transcribed Italian words
    r"\bdicionario\b": "dizionario",
    r"\bpedagoco\b": "pedagogo",
    r"\bpedagogo\b": "pedagogo",      # no-op but explicit
}

# Pre-compile regex for performance
_COMPILED: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in _CORRECTIONS.items()
]


def apply_corrections(text: str) -> str:
    """Apply the correction dictionary to transcribed text.

    Args:
        text: raw text from faster-whisper.

    Returns:
        Corrected text. If no correction applies, returns the text unchanged.
    """
    if not text:
        return text
    result = text
    for pattern, replacement in _COMPILED:
        result = pattern.sub(replacement, result)
    return result
