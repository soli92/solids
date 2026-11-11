"""voice/tests/test_sentence_splitter_and_session.py — Test sentence_splitter + VoiceSession.

SS-*: split_into_sentences — funzione pura stdlib, nessuna dipendenza esterna.
VS-*: VoiceSession e new_session() — gestione turni e identificatori.

Framework: pytest. Tutti i test sono sincroni.
"""
from __future__ import annotations

import time

import pytest

from voice.tts.sentence_splitter import split_into_sentences
from voice.core.session import VoiceSession, new_session


# ===========================================================================
# SS-*: split_into_sentences
# ===========================================================================


class TestSplitIntoSentences:
    def test_empty_string_returns_empty_list(self):
        assert split_into_sentences("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_into_sentences("   \n  ") == []

    def test_single_sentence_no_punctuation(self):
        result = split_into_sentences("Ho trovato tre task aperti")
        assert result == ["Ho trovato tre task aperti"]

    def test_single_sentence_with_period(self):
        result = split_into_sentences("Ho trovato tre task aperti.")
        assert result == ["Ho trovato tre task aperti."]

    def test_two_sentences_split_by_period_space(self):
        result = split_into_sentences("Prima frase. Seconda frase.")
        assert len(result) == 2
        assert result[0] == "Prima frase."
        assert result[1] == "Seconda frase."

    def test_sentences_split_by_exclamation(self):
        result = split_into_sentences("Ottimo! Procedo subito.")
        assert len(result) == 2
        assert result[0] == "Ottimo!"

    def test_sentences_split_by_question_mark(self):
        result = split_into_sentences("Vuoi procedere? Ho capito.")
        assert len(result) == 2
        assert result[0] == "Vuoi procedere?"

    def test_double_newline_splits_paragraphs(self):
        result = split_into_sentences("Paragrafo uno.\n\nParagrafo due.")
        assert len(result) == 2
        assert "Paragrafo uno." in result
        assert "Paragrafo due." in result

    def test_triple_newline_treated_as_paragraph_break(self):
        result = split_into_sentences("Blocco A.\n\n\nBlocco B.")
        assert len(result) == 2

    def test_output_stripped_of_whitespace(self):
        result = split_into_sentences("  Prima.  Seconda.  ")
        assert all(s == s.strip() for s in result)

    def test_no_empty_strings_in_output(self):
        result = split_into_sentences("Prima. Seconda.")
        assert all(len(s) > 0 for s in result)

    def test_multiple_sentences_order_preserved(self):
        input_text = "Uno. Due. Tre. Quattro."
        result = split_into_sentences(input_text)
        assert result == ["Uno.", "Due.", "Tre.", "Quattro."]

    def test_mixed_punctuation_all_split(self):
        result = split_into_sentences("Ottimo! Confermo? Procedo.")
        assert len(result) == 3


# ===========================================================================
# VS-*: VoiceSession e new_session()
# ===========================================================================


class TestVoiceSession:
    def test_session_id_is_eight_chars(self):
        session = VoiceSession()
        assert len(session.session_id) == 8

    def test_session_id_is_string(self):
        session = VoiceSession()
        assert isinstance(session.session_id, str)

    def test_started_at_is_float(self):
        session = VoiceSession()
        assert isinstance(session.started_at, float)

    def test_started_at_recent(self):
        before = time.time()
        session = VoiceSession()
        after = time.time()
        assert before <= session.started_at <= after

    def test_turn_count_starts_at_zero(self):
        session = VoiceSession()
        assert session.turn_count == 0

    def test_new_turn_increments_count(self):
        session = VoiceSession()
        session.new_turn()
        assert session.turn_count == 1

    def test_new_turn_returns_formatted_id(self):
        session = VoiceSession()
        turn_id = session.new_turn()
        assert turn_id == f"{session.session_id}-t1"

    def test_multiple_new_turn_calls_increment_sequentially(self):
        session = VoiceSession()
        ids = [session.new_turn() for _ in range(3)]
        assert ids == [
            f"{session.session_id}-t1",
            f"{session.session_id}-t2",
            f"{session.session_id}-t3",
        ]

    def test_two_sessions_have_different_ids(self):
        s1 = VoiceSession()
        s2 = VoiceSession()
        assert s1.session_id != s2.session_id

    def test_started_at_dt_is_utc(self):
        from datetime import timezone
        session = VoiceSession()
        assert session.started_at_dt.tzinfo == timezone.utc


class TestNewSession:
    def test_new_session_returns_voice_session(self):
        session = new_session()
        assert isinstance(session, VoiceSession)

    def test_new_session_turn_count_zero(self):
        session = new_session()
        assert session.turn_count == 0

    def test_new_session_unique_each_call(self):
        s1 = new_session()
        s2 = new_session()
        assert s1.session_id != s2.session_id
