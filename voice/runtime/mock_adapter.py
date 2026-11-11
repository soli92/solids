"""
voice/runtime/mock_adapter.py — MockAdapter: test implementation of FactoryRuntime.

Does not use any external LLM: responds with an echo of the received text.
Useful for unit tests, CI, offline development, and voice pipeline verification
without Anthropic SDK or an active model dependencies.

Contract honored (§7.2):
  - Acknowledgment emitted immediately as the first event.
  - Simulated 300 ms latency after Acknowledgment (simulates minimum LLM latency).
  - Cancel check after simulated latency.
  - SpokenSummary with echo of transcribed text.
  - Artifact(kind="text") for the visual channel.
  - Done() closes the turn.
  - cancel() idempotent, same pattern as CustomLoopAdapter.
  - aclose() cleans up the _cancelled dictionary.

No import of 'anthropic' or any other LLM.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from voice.config import VoiceConfig
from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    FactoryRuntime,
    RuntimeEvent,
    SpokenSummary,
)

logger = logging.getLogger(__name__)

# Simulated latency in seconds — matches the 300 ms required by the spec.
_MOCK_LATENCY_S: float = 0.3


class MockAdapter(FactoryRuntime):
    """
    Test adapter — deterministic echo, no LLM.

    Event sequence emitted by submit():
      Acknowledgment → (300 ms) → SpokenSummary → Artifact → Done

    Typical usage::

        from voice.config import load_config
        from voice.runtime.mock_adapter import MockAdapter

        config = load_config()
        adapter = MockAdapter(config)
        try:
            async for event in adapter.submit("elenca i task aperti", session_id="turn-1"):
                print(event)
        finally:
            await adapter.aclose()
    """

    def __init__(self, config: VoiceConfig) -> None:
        """
        Initialize MockAdapter.

        Args:
            config: VoiceConfig read from factory.config.yaml. Accepted for
                    FactoryRuntime signature compatibility; not used.
        """
        # config is not used — received only for signature compatibility (§7).
        self._config = config
        # _cancelled: dict[session_id → bool] — flag for idempotent cancel().
        # The submit() generator checks the flag after simulated latency.
        self._cancelled: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # submit() — async generator (contract §7)
    # ------------------------------------------------------------------

    async def submit(  # type: ignore[override]
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        """
        Emit a deterministic sequence of events in response to received text.

        Sequence:
          1. Acknowledgment("ricevuto, elaboro in modalita' mock...") — immediate.
          2. asyncio.sleep(300 ms) — simulates minimum LLM latency.
          3. Cancel check: if cancel() was called, exit cleanly.
          4. SpokenSummary(f"Hai detto: {text}") — spoken echo.
          5. Artifact(kind="text", content=f"[MOCK] Input: {text}") — visual channel.
          6. Done() — closes the turn.

        Args:
            text: text transcribed by STT (user directive).
            session_id: unique turn identifier (e.g. UUID).

        Yields:
            RuntimeEvent: Acknowledgment → SpokenSummary → Artifact → Done
        """
        # Initialize (or reset) the cancel flag for this session
        self._cancelled[session_id] = False
        logger.debug("MockAdapter.submit: avvio sessione=%s", session_id)

        # --- 1. Immediate Acknowledgment (contract §7.2) ---
        yield Acknowledgment("ricevuto, elaboro in modalita' mock...")

        # --- 2. Simulate minimum LLM latency ---
        await asyncio.sleep(_MOCK_LATENCY_S)

        # --- 3. Cancel check (barge-in, Phase 3 US-144) ---
        if self._cancelled.get(session_id):
            logger.info(
                "MockAdapter: sessione %s cancellata dopo latenza simulata", session_id
            )
            return

        # --- 4. SpokenSummary — echo of transcribed text ---
        yield SpokenSummary(f"Hai detto: {text}")

        # --- 5. Artifact — visual channel (NEVER to TTS, contract §4.2 / US-145 AC3) ---
        yield Artifact(kind="text", content=f"[MOCK] Input: {text}")

        # --- 6. Done — closes the turn ---
        yield Done()
        logger.debug("MockAdapter.submit: sessione=%s completata", session_id)

    # ------------------------------------------------------------------
    # cancel() — idempotent
    # ------------------------------------------------------------------

    async def cancel(self, session_id: str) -> None:
        """
        Set the cancel flag for the given session.

        Idempotent: calling on an inactive, already completed, or already
        cancelled session_id does not raise (contract §7.2).

        Args:
            session_id: identifier of the session to interrupt.
        """
        self._cancelled[session_id] = True
        logger.debug("MockAdapter.cancel: richiesto per sessione=%s", session_id)

    # ------------------------------------------------------------------
    # aclose() — resource release, idempotent
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """
        Clear the _cancelled dictionary and release internal state.

        Idempotent: calling multiple times is safe.
        After aclose() the instance must not be reused.
        """
        self._cancelled.clear()
        logger.debug("MockAdapter.aclose: risorse rilasciate")
