"""
voice/runtime/ollama_adapter.py — OllamaAdapter: local runtime via Ollama.

Concrete FactoryRuntime implementation delegating to a local Ollama server
via direct HTTP calls (POST /api/chat with ndjson streaming).

This adapter does NOT use the PyPI 'ollama' package: uses httpx.AsyncClient
(transitive dependency of 'anthropic') for ndjson streaming, with fallback
to urllib.request via asyncio.to_thread if httpx is not available.

Useful for:
  - Offline development and testing without Anthropic API access.
  - Privacy: local processing, no data sent to cloud.
  - Cost: zero per token after model download.

Prerequisites:
  - Ollama installed and running: https://ollama.com
      ollama serve          # start server on http://localhost:11434
      ollama pull llama3.2  # download default model
  - httpx (transitive dependency of 'anthropic'):
      pip install httpx     # if not already present

Ollama ndjson streaming format (POST /api/chat, stream: true):
  - Each line is a JSON object: {"message": {"content": "<chunk>"}, "done": false}
  - Last line: {"message": {"content": ""}, "done": true, "done_reason": "stop", ...}

Uso::

    from voice.config import load_config
    from voice.runtime.ollama_adapter import OllamaAdapter

    config = load_config()
    adapter = OllamaAdapter(config)
    try:
        async for event in adapter.submit("elenca i task aperti", session_id="turn-1"):
            await router.dispatch(event)
    finally:
        await adapter.aclose()
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, Optional

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

# Default Ollama endpoint
_DEFAULT_BASE_URL = "http://localhost:11434"
# Default Ollama model (available via `ollama pull llama3.2`)
_DEFAULT_MODEL = "llama3.2"

# Conditional httpx import (transitive dependency of anthropic).
# If unavailable, activate urllib.request fallback path.
try:
    import httpx as _httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _httpx = None  # type: ignore[assignment]
    _HTTPX_AVAILABLE = False
    logger.debug(
        "OllamaAdapter: httpx non disponibile — attivato fallback urllib.request. "
        "Per prestazioni migliori: pip install httpx"
    )


class OllamaAdapter(FactoryRuntime):
    """
    Ollama adapter — local LLM loop via HTTP ndjson streaming.

    Uses httpx.AsyncClient for non-blocking async calls to Ollama POST /api/chat.
    Fallback to urllib.request via asyncio.to_thread if httpx is not available.

    Behavior is identical to CustomLoopAdapter from the voice layer perspective:
    both implement FactoryRuntime and produce the same event taxonomy
    (Acknowledgment → SpokenSummary → Artifact → Done).

    Differenza chiave rispetto a CustomLoopAdapter:
      - CustomLoopAdapter: cloud LLM via Anthropic SDK (network latency, cost per token).
      - OllamaAdapter: local LLM via Ollama (hardware latency, zero cost post-download).

    SpokenSummary emitted by OllamaAdapter is full text truncated to first 300
    characters (directly speakable without router extraction, since
    Ollama produces plain text without factory markup). Unlike CustomLoopAdapter
    (which emits a fixed placeholder in Phase 1 and delegates separation to TSK-302), this
    adapter produces meaningful SpokenSummary from Phase 1.

    Thread safety: same note as CustomLoopAdapter — single asyncio event loop,
    no cross-thread sharing, separate instances for parallel runs.
    """

    def __init__(
        self,
        config: VoiceConfig,
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        """
        Initialize adapter with configuration read from factory.config.yaml.

        I parametri base_url e model vengono sovrascrittti se config ha un campo
'runtime' field (dict or object with attributes) specifying them, allowing
        centralized configuration via factory.config.yaml without passing
        constructor arguments.

        Args:
            config: VoiceConfig con i parametri del canale vocale.
            base_url: Ollama server base URL. Default: http://localhost:11434.
                      Precedence: config.runtime.base_url > parameter > default.
            model: Ollama model name. Default: llama3.2.
                   Precedence: config.runtime.model > parameter > default.
        """
        self._config = config

        # Read base_url and model from config.runtime if present.
        # Supports both dict (from YAML) and objects with attributes (future RuntimeConfig dataclass).
        runtime_cfg = getattr(config, "runtime", None)
        if isinstance(runtime_cfg, dict):
            base_url = str(runtime_cfg.get("base_url", base_url))
            model = str(runtime_cfg.get("model", model))
        elif runtime_cfg is not None:
            base_url = str(getattr(runtime_cfg, "base_url", base_url))
            model = str(getattr(runtime_cfg, "model", model))

        self._base_url: str = base_url.rstrip("/")
        self._model: str = model
        # _cancelled: dict[session_id → bool] — flag for idempotent cancel().
        # submit() generator checks flag each chunk for clean termination.
        self._cancelled: dict[str, bool] = {}
        # httpx client reused for all session submit() calls.
        # timeout=None: Ollama stream may take variable time — no fixed timeout.
        self._client = (
            _httpx.AsyncClient(timeout=None)  # type: ignore[union-attr]
            if _HTTPX_AVAILABLE
            else None
        )
        logger.debug(
            "OllamaAdapter: inizializzato base_url=%s model=%s httpx=%s",
            self._base_url,
            self._model,
            _HTTPX_AVAILABLE,
        )

    # ------------------------------------------------------------------
    # submit() — async generator (contract §7)
    # ------------------------------------------------------------------

    async def submit(  # type: ignore[override]
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        """
        Send directive to Ollama runtime and iterate response events.

        Sequenza eventi emessi:
          1. Acknowledgment("ci sto lavorando con Ollama...") — immediate (contract §7.2).
          2. ndjson stream from POST /api/chat: accumulate chunks in full_text.
             Check cancel each chunk to support barge-in (Phase 3, US-144 AC6).
          3. A done=true:
             - SpokenSummary(full_text[:300]) — spoken summary (first 300 chars, truncated).
             - Artifact(kind="text", content=full_text) — full text for visual channel.
               INVARIANTE: Artifact.content NON viene passato a TTS (contratto §4.2 + US-145 AC3).
          4. Done() — chiude il turno.

        On connection error (Ollama not started):
          Error("Ollama non raggiungibile. Avvia Ollama con: ollama serve")

        Args:
            text: text transcribed by STT (user directive).
            session_id: unique turn identifier (e.g. UUID).

        Yields:
            RuntimeEvent: Acknowledgment → SpokenSummary → Artifact → Done
                          or ... → Error on fatal error.
        """
        # Initialize (or reset) cancel flag for this session
        self._cancelled[session_id] = False
        logger.debug(
            "OllamaAdapter.submit: avvio sessione=%s model=%s", session_id, self._model
        )

        # --- 1. Acknowledgment immediato (contratto §7.2) ---
        yield Acknowledgment("ci sto lavorando con Ollama...")
        if self._cancelled.get(session_id):
            logger.info(
                "OllamaAdapter: sessione %s cancellata dopo Acknowledgment", session_id
            )
            return

        # --- 2. Stream ndjson da Ollama ---
        url = f"{self._base_url}/api/chat"
        body: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }
        full_text = ""

        if _HTTPX_AVAILABLE and self._client is not None:
            # Primary path: httpx async streaming (non-blocking)
            try:
                async with self._client.stream("POST", url, json=body) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        # Check cancel before each yield (barge-in support)
                        if self._cancelled.get(session_id):
                            logger.info(
                                "OllamaAdapter: sessione %s cancellata durante stream",
                                session_id,
                            )
                            return
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(
                                "OllamaAdapter: linea ndjson non valida ignorata: %r", line
                            )
                            continue
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_text += chunk
                        if data.get("done"):
                            break
            except _httpx.ConnectError as exc:  # type: ignore[union-attr]
                logger.error(
                    "OllamaAdapter: ConnectError [%s]: %s", session_id, exc
                )
                yield Error(
                    "Ollama non raggiungibile. Avvia Ollama con: ollama serve"
                )
                return
            except asyncio.CancelledError:
                # asyncio.CancelledError must not be swallowed — clean exit
                logger.info(
                    "OllamaAdapter: CancelledError per sessione %s — terminazione pulita",
                    session_id,
                )
                return
            except Exception as exc:
                logger.error(
                    "OllamaAdapter: errore inatteso [%s] %s: %s",
                    session_id,
                    type(exc).__name__,
                    exc,
                )
                yield Error(
                    f"Errore durante l'elaborazione Ollama: {type(exc).__name__}."
                )
                return
        else:
            # Fallback path: urllib.request via asyncio.to_thread (sync in thread)
            # Note: per-chunk granular cancel is not supported in this path;
            # flag is checked only before thread start.
            try:
                result = await asyncio.to_thread(
                    _urllib_post_ollama,
                    url,
                    body,
                    lambda: bool(self._cancelled.get(session_id, False)),
                )
                if result is None:
                    # Cancelled before thread start (lambda returned True)
                    logger.info(
                        "OllamaAdapter: sessione %s cancellata (fallback urllib)", session_id
                    )
                    return
                full_text = result
            except (ConnectionRefusedError, OSError) as exc:
                logger.error(
                    "OllamaAdapter: errore connessione urllib [%s]: %s", session_id, exc
                )
                yield Error(
                    "Ollama non raggiungibile. Avvia Ollama con: ollama serve"
                )
                return
            except asyncio.CancelledError:
                logger.info(
                    "OllamaAdapter: CancelledError (fallback urllib) sessione %s — terminazione pulita",
                    session_id,
                )
                return
            except Exception as exc:
                logger.error(
                    "OllamaAdapter: errore inatteso urllib [%s] %s: %s",
                    session_id,
                    type(exc).__name__,
                    exc,
                )
                yield Error(
                    f"Errore durante l'elaborazione Ollama: {type(exc).__name__}."
                )
                return

        if self._cancelled.get(session_id):
            logger.info(
                "OllamaAdapter: sessione %s cancellata dopo stream", session_id
            )
            return

        # --- 3. SpokenSummary (first 300 chars) + Artifact (full text for visual) ---
        # SpokenSummary: truncate to 300 chars for compatibility with TTS engines that have
        # increasing latency on long text. Full text available via Artifact.
        # INVARIANTE (contratto §4.2 + US-145 AC3): Artifact.content NON deve mai raggiungere TTS.
        spoken = full_text[:300].strip() if full_text else "elaborazione completata"
        yield SpokenSummary(spoken)
        if full_text:
            yield Artifact(kind="text", content=full_text)

        # --- 4. Done — closes turn ---
        yield Done()
        logger.debug(
            "OllamaAdapter.submit: sessione=%s completata (%d chars)",
            session_id,
            len(full_text),
        )

    # ------------------------------------------------------------------
    # cancel() — idempotent
    # ------------------------------------------------------------------

    async def cancel(self, session_id: str) -> None:
        """
        Set cancel flag for the given session.

        submit() generator checks _cancelled[session_id] at each ndjson chunk
        and terminates cleanly without leaving HTTP connections open.

        Idempotent: calling on inactive, already completed or already
        cancelled session_id raises no exceptions (contract §7.2).

        Args:
            session_id: session identifier to interrupt.
        """
        self._cancelled[session_id] = True
        logger.debug("OllamaAdapter.cancel: richiesto per sessione=%s", session_id)

    # ------------------------------------------------------------------
    # aclose() — resource release, idempotent
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """
        Close httpx client and clean internal state (_cancelled).

        Called by state_machine at end of voice session or on
        unrecoverable fatal error. Idempotent: safe to call multiple times.

        After aclose() instance must not be reused: create a new
        OllamaAdapter instance for the next session.
        """
        self._cancelled.clear()
        if self._client is not None:
            await self._client.aclose()
        logger.debug("OllamaAdapter.aclose: risorse rilasciate")


# ---------------------------------------------------------------------------
# urllib.request fallback (only when httpx is not available)
# ---------------------------------------------------------------------------

def _urllib_post_ollama(
    url: str,
    body: dict,
    is_cancelled: Callable[[], bool],
) -> Optional[str]:
    """
    Call POST /api/chat via urllib.request in synchronous mode.

    Invoked with asyncio.to_thread() from OllamaAdapter.submit() fallback path
    when httpx is not available.

    Per-chunk granular cancel is not supported in this implementation:
    is_cancelled flag is checked only before connection start.
    For granular cancel during stream install httpx (primary path).

    Args:
        url: full Ollama endpoint URL (/api/chat).
        body: JSON body dict (model, messages, stream).
        is_cancelled: no-arg callable returning True if session
                      was cancelled. Checked before opening connection.

    Returns:
        Text accumulated from ndjson stream, or None if session was already
        cancelled before start (is_cancelled() was True).

    Raises:
        ConnectionRefusedError: if Ollama is not listening on specified URL.
        urllib.error.URLError: other network or HTTP errors.
        OSError: low-level socket errors.
    """
    import urllib.error
    import urllib.request

    # Check cancel before opening connection (only cancel point in fallback)
    if is_cancelled():
        return None

    encoded = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_text = ""
    try:
        with urllib.request.urlopen(req) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(
                        "_urllib_post_ollama: linea ndjson non valida ignorata: %r", line
                    )
                    continue
                chunk = parsed.get("message", {}).get("content", "")
                if chunk:
                    full_text += chunk
                if parsed.get("done"):
                    break
    except urllib.error.URLError as exc:
        # Unwrap URLError to expose underlying error to caller
        raise exc.reason if isinstance(exc.reason, OSError) else OSError(str(exc)) from exc

    return full_text
