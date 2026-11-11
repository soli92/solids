"""
voice/runtime/custom_loop_adapter.py — CustomLoopAdapter (Opzione B: custom loop LLM+tool).

Supporta tre provider LLM (voice_channel.runtime.provider):
  - anthropic: Anthropic Async SDK (API key obbligatoria)
  - ollama:    Ollama REST API via httpx (locale, nessuna API key)
  - mock:      risposta fissa per test pipeline audio senza LLM

Decisione runtime EP-041 §13.1: Opzione B selezionata.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from voice.config import VoiceConfig
from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    Error,
    FactoryRuntime,
    RuntimeEvent,
    SpokenSummary,
)

logger = logging.getLogger(__name__)

_DEFAULT_LLM_MODEL = "claude-sonnet-4-6"
_SYSTEM_PROMPT = (
    "Sei un assistente vocale italiano. Rispondi in modo conciso "
    "e naturale, adatto alla voce: niente elenchi puntati, niente "
    "markdown, frasi brevi. Massimo 3-4 frasi per risposta."
)
_MOCK_RESPONSE = (
    "Ho capito la tua domanda. "
    "Questa è una risposta di prova del sistema vocale. "
    "La pipeline audio funziona correttamente."
)


class CustomLoopAdapter(FactoryRuntime):
    """
    Adapter Opzione B — loop LLM+tool custom, multi-provider.

    Provider supportati: anthropic | ollama | mock.
    Selezione via voice_channel.runtime.provider in factory.config.yaml.
    """

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._provider: str = config.runtime.provider   # "anthropic" | "ollama" | "mock"
        self._cancelled: dict[str, bool] = {}
        self._llm_model: str = config.runtime.llm_model or _DEFAULT_LLM_MODEL

        # Client Anthropic — importato solo se provider=anthropic
        self._anthropic_client = None
        if self._provider == "anthropic":
            try:
                import anthropic as _anthropic  # noqa: PLC0415
                self._anthropic_client = _anthropic.AsyncAnthropic()
            except ImportError as exc:
                raise ImportError(
                    "Il pacchetto 'anthropic' non e' installato. "
                    "Installarlo con: pip install -e '.[voice]'"
                ) from exc

        # Client httpx per Ollama — importato solo se provider=ollama
        self._ollama_client = None
        self._ollama_url: str = ""
        self._ollama_model: str = ""
        if self._provider == "ollama":
            try:
                import httpx  # noqa: PLC0415
                self._ollama_client = httpx.AsyncClient(timeout=120.0)
            except ImportError as exc:
                raise ImportError(
                    "Il pacchetto 'httpx' non e' installato. "
                    "Installarlo con: pip install httpx"
                ) from exc
            self._ollama_url = config.runtime.ollama_base_url.rstrip("/") + "/api/chat"
            self._ollama_model = config.runtime.ollama_model or "llama3.2"
            logger.info(
                "CustomLoopAdapter: Ollama → %s (model=%s)",
                self._ollama_url,
                self._ollama_model,
            )

    # ------------------------------------------------------------------
    # submit() — async generator (contratto §7)
    # ------------------------------------------------------------------

    async def submit(  # type: ignore[override]
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        """Invia la direttiva al runtime LLM e itera gli eventi di risposta.

        Routing per provider:
          - anthropic → _submit_anthropic()
          - ollama    → _submit_ollama()
          - mock      → _submit_mock()
        """
        self._cancelled[session_id] = False
        logger.debug("CustomLoopAdapter.submit: provider=%s sessione=%s", self._provider, session_id)

        yield Acknowledgment("un momento...")
        if self._cancelled.get(session_id):
            return

        if self._provider == "anthropic":
            async for event in self._submit_anthropic(text, session_id):
                yield event
        elif self._provider == "ollama":
            async for event in self._submit_ollama(text, session_id):
                yield event
        else:
            async for event in self._submit_mock(text, session_id):
                yield event

    # ------------------------------------------------------------------
    # _submit_anthropic
    # ------------------------------------------------------------------

    async def _submit_anthropic(
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        full_text: str = ""
        try:
            import anthropic as _anthropic  # noqa: PLC0415
            async with self._anthropic_client.messages.stream(
                model=self._llm_model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            ) as stream:
                async for chunk in stream.text_stream:
                    if self._cancelled.get(session_id):
                        return
                    full_text += chunk
                    yield Artifact(kind="text", content=chunk)

        except _anthropic.APIConnectionError as exc:
            logger.error("Anthropic connection error [%s]: %s", session_id, exc)
            yield Error(message="Errore di connessione al servizio LLM.")
            return
        except _anthropic.RateLimitError as exc:
            logger.error("Anthropic rate limit [%s]: %s", session_id, exc)
            yield Error(message="Limite di richieste raggiunto. Riprova tra qualche istante.")
            return
        except _anthropic.APIStatusError as exc:
            logger.error("Anthropic API error [%s] status=%s: %s", session_id, exc.status_code, exc)
            yield Error(message=f"Errore API ({exc.status_code}).")
            return
        except asyncio.CancelledError:
            return

        if self._cancelled.get(session_id):
            return
        if full_text.strip():
            yield SpokenSummary(full_text.strip())
        yield Done()

    # ------------------------------------------------------------------
    # _submit_ollama  (Ollama REST /api/chat streaming NDJSON)
    # ------------------------------------------------------------------

    async def _submit_ollama(
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        payload = {
            "model": self._ollama_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            "stream": True,
        }
        full_text: str = ""
        try:
            async with self._ollama_client.stream(
                "POST", self._ollama_url, json=payload
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error("Ollama HTTP %s: %s", response.status_code, body[:200])
                    yield Error(message=f"Ollama errore HTTP {response.status_code}.")
                    return

                async for line in response.aiter_lines():
                    if self._cancelled.get(session_id):
                        return
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full_text += chunk
                        yield Artifact(kind="text", content=chunk)
                    if data.get("done"):
                        break

        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama error [%s]: %s", session_id, exc)
            yield Error(message=f"Errore Ollama: {exc}")
            return

        if self._cancelled.get(session_id):
            return
        if full_text.strip():
            yield SpokenSummary(full_text.strip())
        yield Done()
        logger.debug("CustomLoopAdapter._submit_ollama: sessione=%s completata", session_id)

    # ------------------------------------------------------------------
    # _submit_mock  (risposta fissa per test pipeline audio)
    # ------------------------------------------------------------------

    async def _submit_mock(
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        logger.info("CustomLoopAdapter._submit_mock: testo=%r", text[:60])
        await asyncio.sleep(0.3)   # simula latenza LLM
        yield Artifact(kind="text", content=_MOCK_RESPONSE)
        yield SpokenSummary(_MOCK_RESPONSE)
        yield Done()

    # ------------------------------------------------------------------
    # cancel() — idempotente
    # ------------------------------------------------------------------

    async def cancel(self, session_id: str) -> None:
        """
        Imposta il flag di cancel per la sessione indicata.

        Il generator submit() controlla _cancelled[session_id] a ogni yield e
        termina pulitamente senza lasciare task o thread appesi.

        Idempotente: chiamarlo su una session_id non attiva, gia' completata o gia'
        cancellata non genera eccezioni (contratto §7.2).

        Args:
            session_id: identificatore della sessione da interrompere.
        """
        self._cancelled[session_id] = True
        logger.debug("CustomLoopAdapter.cancel: richiesto per sessione=%s", session_id)

    # ------------------------------------------------------------------
    # aclose() — rilascio risorse, idempotente
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Chiude i client e ripulisce lo stato interno. Idempotente."""
        self._cancelled.clear()
        if self._anthropic_client is not None:
            await self._anthropic_client.aclose()
        if self._ollama_client is not None:
            await self._ollama_client.aclose()
        logger.debug("CustomLoopAdapter.aclose: risorse rilasciate (provider=%s)", self._provider)
