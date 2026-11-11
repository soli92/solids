"""voice/tests/test_stt_corrections.py — Test dizionario correzioni post-STT.

Copre i misrecognition rilevati nella sessione E2E 2026-07-10:
  - "tasche" → "task"
  - "camman" → "kanban"
  - "Vod" → "VAD"
  - "in spree" → "handsfree"
  - "dicionario" → "dizionario"
  - Stringhe senza match: restituite invariate
  - Stringa vuota: restituita invariata
"""
from __future__ import annotations

import pytest

from voice.stt.corrections import apply_corrections


class TestApplyCorrections:
    def test_empty_string_unchanged(self):
        assert apply_corrections("") == ""

    def test_no_match_unchanged(self):
        assert apply_corrections("Ciao come stai?") == "Ciao come stai?"

    # --- Termini dominio factory ---

    def test_tasche_to_task(self):
        result = apply_corrections("Quante tasche sono aperte?")
        assert "task" in result.lower()
        assert "tasche" not in result.lower()

    def test_camman_to_kanban(self):
        result = apply_corrections("Apri il camman")
        assert "kanban" in result.lower()
        assert "camman" not in result.lower()

    def test_canban_to_kanban(self):
        result = apply_corrections("stato del canban")
        assert "kanban" in result.lower()

    # --- Acronimi tecnici ---

    def test_vod_to_vad(self):
        result = apply_corrections("il vod non funziona")
        assert "VAD" in result
        assert "vod" not in result.lower()

    # --- Keyword handsfree ---

    def test_in_spree_to_handsfree(self):
        result = apply_corrections("attiva modalità in spree")
        assert "handsfree" in result.lower()
        assert "in spree" not in result.lower()

    def test_inspree_to_handsfree(self):
        result = apply_corrections("attiva inspree")
        assert "handsfree" in result.lower()

    # --- Parole italiane ---

    def test_dicionario_to_dizionario(self):
        result = apply_corrections("il mio dicionario")
        assert "dizionario" in result.lower()
        assert "dicionario" not in result.lower()

    # --- Sessione reale completa ---

    def test_session_utterance_7_kanban_task(self):
        """E2E session utterance #7: 'Quanti tasche sono attualmente aperti sul camman?'"""
        raw = "Quanti tasche sono attualmente aperti sul camman?"
        result = apply_corrections(raw)
        assert "task" in result.lower()
        assert "kanban" in result.lower()
        assert "tasche" not in result.lower()
        assert "camman" not in result.lower()

    def test_session_utterance_3_vad(self):
        """E2E session utterance #3: 'Vod con pause e eccetera'"""
        raw = "Vod con pause e eccetera"
        result = apply_corrections(raw)
        assert "VAD" in result

    def test_session_utterance_13_handsfree(self):
        """E2E session utterance #13: 'Ok, attiva modalità in spree'"""
        raw = "Ok, attiva modalità in spree"
        result = apply_corrections(raw)
        assert "handsfree" in result.lower()

    # --- Stability: no false positive ---

    def test_no_false_positive_on_compito(self):
        """'task' corretto non deve triggerare su parole diverse."""
        result = apply_corrections("ho un compito da fare")
        assert "task" not in result  # "compito" must not become "task"

    def test_no_false_positive_on_handsfree_already_correct(self):
        result = apply_corrections("attiva handsfree")
        assert result == "attiva handsfree"
