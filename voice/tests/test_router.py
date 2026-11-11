"""voice/tests/test_router.py — Test EventRouter e spoken_summary_extractor.

Copre le invarianti critiche del layer di routing (US-145, EP-041 §Vincolo):
  INV-1: Artifact NON raggiunge tts_queue (AC3 — non negoziabile)
  INV-2: SpokenSummary, Acknowledgment, Question raggiungono tts_queue (AC1)
  INV-3: Done e Error chiudono il turno (route() ritorna False)
  INV-4: _to_tts scarta tipi non in TTS_ALLOWED con WARNING (AC5)
  INV-5: spoken_summary_extractor separa testo da fence markdown (AC2)

Framework: pytest + asyncio.run() — nessun pytest-asyncio richiesto.
Nessun hardware audio o LLM coinvolto.
"""
from __future__ import annotations

import asyncio
import io
import logging
from unittest.mock import AsyncMock, patch

import pytest

from voice.core.router import EventRouter, spoken_summary_extractor
from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    Error,
    Progress,
    Question,
    SpokenSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_router() -> tuple[EventRouter, asyncio.Queue, io.StringIO]:
    """Crea un EventRouter con sink e queue ispezionabili."""
    tts_queue: asyncio.Queue = asyncio.Queue()
    sink = io.StringIO()
    router = EventRouter(tts_queue=tts_queue, visual_sink=sink)
    return router, tts_queue, sink


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# spoken_summary_extractor — unit pura, nessuna IO
# ===========================================================================


class TestSpokenSummaryExtractor:
    def test_empty_string_returns_empty_lists(self):
        parlato, artefatto = spoken_summary_extractor("")
        assert parlato == []
        assert artefatto == []

    def test_plain_text_no_fence_goes_to_parlato(self):
        parlato, artefatto = spoken_summary_extractor("Ho analizzato i task aperti.")
        assert parlato == ["Ho analizzato i task aperti."]
        assert artefatto == []

    def test_code_fence_splits_correctly(self):
        testo = "Ecco il risultato:\n```python\nprint('ciao')\n```\nFatto."
        parlato, artefatto = spoken_summary_extractor(testo)
        assert any("Ecco il risultato" in p for p in parlato)
        assert any("Fatto" in p for p in parlato)
        assert any("print('ciao')" in a for a in artefatto)

    def test_only_fence_goes_to_artefatto_not_parlato(self):
        testo = "```diff\n+riga aggiunta\n```"
        parlato, artefatto = spoken_summary_extractor(testo)
        assert any("+riga aggiunta" in a for a in artefatto)
        # no text outside fence
        assert all("diff" not in p for p in parlato)

    def test_multiple_fences_produce_multiple_artefatti(self):
        testo = (
            "Prima parte.\n"
            "```python\ncodice_a()\n```\n"
            "Mezzo.\n"
            "```json\n{\"ok\": true}\n```\n"
            "Fine."
        )
        parlato, artefatto = spoken_summary_extractor(testo)
        assert len(artefatto) == 2
        assert sum(1 for p in parlato if p) >= 1  # almeno un segmento parlato

    def test_whitespace_only_string_returns_empty(self):
        parlato, artefatto = spoken_summary_extractor("   \n  ")
        assert parlato == []
        assert artefatto == []


# ===========================================================================
# EventRouter.route() — invarianti di instradamento
# ===========================================================================


class TestEventRouterRoute:
    def test_spoken_summary_goes_to_tts_queue_and_continues(self):
        router, q, sink = _make_router()
        result = _run(router.route(SpokenSummary("Ho trovato tre task aperti.")))
        assert result is True
        assert q.get_nowait() == "Ho trovato tre task aperti."
        assert q.empty()

    def test_acknowledgment_goes_to_tts_queue_and_continues(self):
        router, q, sink = _make_router()
        result = _run(router.route(Acknowledgment("ricevuto, elaboro...")))
        assert result is True
        assert q.get_nowait() == "ricevuto, elaboro..."

    def test_question_goes_to_tts_queue_and_continues(self):
        router, q, sink = _make_router()
        result = _run(router.route(Question("Confermi l'operazione?")))
        assert result is True
        assert q.get_nowait() == "Confermi l'operazione?"

    def test_artifact_never_reaches_tts_queue(self):
        """INV-1: Artifact.content NON deve mai raggiungere tts_queue (AC3)."""
        router, q, sink = _make_router()
        result = _run(router.route(Artifact(kind="code", content="rm -rf /")))
        assert result is True
        assert q.empty(), "Artifact.content ha raggiunto tts_queue — invariante violata!"
        assert "rm -rf /" in sink.getvalue()

    def test_artifact_appears_in_visual_sink(self):
        router, q, sink = _make_router()
        _run(router.route(Artifact(kind="diff", content="+ riga aggiunta")))
        output = sink.getvalue()
        assert "ARTIFACT" in output or "riga aggiunta" in output

    def test_done_closes_turn_and_appears_in_sink(self):
        router, q, sink = _make_router()
        result = _run(router.route(Done()))
        assert result is False
        assert q.empty()
        assert "DONE" in sink.getvalue()

    def test_error_closes_turn_and_notifies_both_channels(self):
        router, q, sink = _make_router()
        result = _run(router.route(Error(message="connessione persa")))
        assert result is False
        # TTS riceve versione breve pronunciabile
        tts_text = q.get_nowait()
        assert "errore" in tts_text.lower() or "connessione persa" in tts_text.lower()
        # Visual channel receives full message
        assert "connessione persa" in sink.getvalue()

    def test_progress_goes_to_visual_sink_only(self):
        router, q, sink = _make_router()
        result = _run(router.route(Progress(text="analisi in corso...", pct=0.5)))
        assert result is True
        assert q.empty()
        assert "analisi in corso" in sink.getvalue()

    def test_progress_with_pct_shown_in_sink(self):
        router, q, sink = _make_router()
        _run(router.route(Progress(text="build", pct=0.75)))
        assert "75%" in sink.getvalue()

    def test_unknown_event_type_does_not_reach_tts_queue(self, caplog):
        """Tipo sconosciuto: scartato con WARNING, queue rimane vuota."""
        router, q, sink = _make_router()

        class _UnknownEvent:
            pass

        with caplog.at_level(logging.WARNING, logger="voice.core.router"):
            result = _run(router.route(_UnknownEvent()))  # type: ignore[arg-type]
        assert result is True
        assert q.empty()
        assert any("sconosciuto" in r.message.lower() or "unknown" in r.message.lower()
                   for r in caplog.records)


# ===========================================================================
# EventRouter._to_tts — defense in depth (AC5)
# ===========================================================================


class TestToTtsDefensiveCheck:
    def test_artifact_type_discarded_with_warning(self, caplog):
        """_to_tts deve scartare Artifact anche se chiamato direttamente (AC5)."""
        router, q, _ = _make_router()
        artifact = Artifact(kind="code", content="codice segreto")
        with caplog.at_level(logging.WARNING, logger="voice.core.router"):
            _run(router._to_tts(artifact, "codice segreto"))
        assert q.empty(), "_to_tts ha accodato un Artifact — difesa AC5 violata!"
        assert any("non-parlato" in r.message or "non" in r.message.lower()
                   for r in caplog.records)

    def test_done_type_discarded(self, caplog):
        """Done is not in TTS_ALLOWED — _to_tts must discard it."""
        router, q, _ = _make_router()
        with caplog.at_level(logging.WARNING, logger="voice.core.router"):
            _run(router._to_tts(Done(), "fine"))
        assert q.empty()


# ===========================================================================
# EventRouter.extract_spoken_summary — pattern spoken fence + HTML comment
# ===========================================================================


class TestExtractSpokenSummary:
    def test_spoken_fence_extracted(self):
        router, _, _ = _make_router()
        md = "```spoken\nHo completato l'analisi.\n```"
        result = router.extract_spoken_summary(md)
        assert result == "Ho completato l'analisi."

    def test_html_comment_spoken_extracted(self):
        router, _, _ = _make_router()
        md = "<!-- spoken: Operazione completata con successo. -->"
        result = router.extract_spoken_summary(md)
        assert result == "Operazione completata con successo."

    def test_no_pattern_returns_none(self):
        router, _, _ = _make_router()
        result = router.extract_spoken_summary("Testo senza pattern speciali.")
        assert result is None

    def test_spoken_fence_priority_over_html_comment(self):
        """spoken fence takes priority over HTML comment."""
        router, _, _ = _make_router()
        md = "```spoken\nTesto fence.\n```\n<!-- spoken: Testo comment. -->"
        result = router.extract_spoken_summary(md)
        assert result == "Testo fence."

    def test_empty_spoken_fence_returns_none(self):
        router, _, _ = _make_router()
        result = router.extract_spoken_summary("```spoken\n\n```")
        assert result is None
