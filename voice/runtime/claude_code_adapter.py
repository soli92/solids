"""
voice/runtime/claude_code_adapter.py — Adapter Claude Code CLI (EP-041 ext).

Invia l'utterance vocale trascritto a `claude -p "<text>"` con il contesto
completo della factory (CLAUDE.md, wiki, skill, config). La risposta JSON viene
filtrata per TTS e mostrata integralmente nel canale visivo (stdout).

Questo adapter trasforma il voice channel da "secondo chatbot standalone" al
suo scopo originale: front-end vocale per la factory multi-agente.

Prerequisiti:
  - Claude Code installato (https://claude.ai/download)
  - ANTHROPIC_API_KEY nel PATH oppure autenticazione OAuth in corso
  - factory.config.yaml nella CWD o in una parent directory

Config (voice_channel.runtime):
  provider: claude-code
  claude_code_bin: ""           # percorso esplicito (auto-detect se vuoto)
  claude_code_timeout: 120      # secondi max attesa risposta
  claude_code_max_spoken: 500   # caratteri max sintetizzati via TTS
  claude_code_model: ""         # "" = usa il default di Claude Code
  claude_code_allowed_tools: "Read,Glob,Bash(git log*),Bash(git status),Bash(git diff*)"
                                # lista tool permessi (default: sola lettura)
                                # "*" per accesso completo (richiede conferma esplicita)

Nota: con allowed_tools="*" Claude Code ha accesso completo ai tool (scrittura,
esecuzione bash, ecc.). Abilitare solo dopo aver compreso le implicazioni.
Il default (sola lettura) supporta query di stato, lettura wiki, git log.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    Error,
    FactoryRuntime,
    Progress,
    Question,
    RuntimeEvent,
    SpokenSummary,
)

if TYPE_CHECKING:
    from voice.config import VoiceConfig

logger = logging.getLogger(__name__)

# Tool di default: accesso in sola lettura (sicuro per query vocali di stato)
_DEFAULT_ALLOWED_TOOLS = "Read,Glob,Bash(git log*),Bash(git status),Bash(git diff*)"

# ---------------------------------------------------------------------------
# Regex per filtro TTS
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b[@-Z\\-_]")
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_ITALIC_RE = re.compile(r"\*{1,3}(.+?)\*{1,3}", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _extract_spoken(text: str, max_chars: int = 500) -> str:
    """Rimuove markup e artefatti tecnici, ritorna testo parlabile troncato."""
    text = _ANSI_RE.sub("", text)
    text = _CODE_BLOCK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _HEADER_RE.sub("", text)
    text = _BOLD_ITALIC_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# ---------------------------------------------------------------------------
# Auto-detection binary Claude Code
# ---------------------------------------------------------------------------

#: Oltre questa lunghezza l'ultima riga non e' una domanda: e' un paragrafo che finisce con
#: un punto interrogativo. Misurato, non scelto a occhio — vedi `_domanda_finale`.
_DOMANDA_MAX_CHARS = 160


def _domanda_finale(testo: str) -> str | None:
    """L'ultima riga e' una domanda rivolta a chi legge? **Euristica, dichiarata tale.**

    In modalita' `--print` non esiste un segnale strutturale: la sessione headless annuncia
    26 strumenti e `AskUserQuestion` **non e' fra questi** (verificato 2026-09-25 leggendo
    l'evento `system/init`). Quindi il riconoscimento e' per forza sul testo, ed e' meglio
    dirlo qui che lasciarlo scoprire a chi legge il codice fra sei mesi.

    **Misurata su 399 messaggi finali reali** presi dai transcript delle sessioni passate:

    | regola | scatta su | precisione |
    |---|---|---|
    | ultima riga finisce con `?` | 9/399 (2,3%) | include suggerimenti lunghi, non domande |
    | + al massimo 160 caratteri | 5/399 (1,3%) | **5 su 5 domande vere** |
    | + parole di seconda persona | 5/399 (1,3%) | identica alla precedente |

    Il filtro sulla seconda persona e' stato **scartato dalla misura**: non aggiungeva
    precisione e portava una lista di parole chiave che invecchia e che vale per una lingua
    sola.

    Falsi negativi: 6 su 399 hanno un `?` nell'ultima riga senza finirci, e di quelli **uno
    solo** era una domanda vera. Il costo di un falso negativo e' il comportamento di oggi —
    nessun gate — quindi non e' una regressione.

    Il costo di un falso positivo e' un gate di troppo sullo schermo, **non una plancia
    bloccata**: il turno viene marcato concluso comunque, quindi un comando nuovo parte lo
    stesso.
    """
    senza_codice = re.sub(r"```.*?```", "", testo or "", flags=re.S)
    senza_tabelle = re.sub(r"^\s*[|>].*$", "", senza_codice, flags=re.M)
    righe = [r.strip() for r in senza_tabelle.splitlines() if r.strip()]
    if not righe:
        return None
    ultima = righe[-1]
    if not ultima.endswith("?") or len(ultima) > _DOMANDA_MAX_CHARS:
        return None
    return ultima


#: Da `tool_use` a una frase corta e utile. Il nome del campo che porta l'informazione
#: cambia per strumento, e mostrarne uno solo («Read») butta via la parte che serve.
_CAMPO_PARLANTE = ("file_path", "path", "pattern", "description", "command", "url", "query")


def _descrivi_tool_use(nome: str, argomenti: dict) -> str:
    """«Read visual/server.py», «Bash esegue i test», «Task docs-dev».

    Tenuta corta di proposito: questo testo puo' finire al TTS, e un percorso assoluto
    letto ad alta voce e' rumore. La plancia mostra comunque il dettaglio pieno leggendo
    il transcript, che resta la sorgente ricca (canale asimmetrico, PATTERN §30.1).
    """
    valore = ""
    for campo in _CAMPO_PARLANTE:
        grezzo = argomenti.get(campo)
        if isinstance(grezzo, str) and grezzo.strip():
            valore = grezzo.strip()
            break
    if not valore:
        return nome
    valore = valore.splitlines()[0]
    if len(valore) > 60:
        valore = valore[:57] + "..."
    return f"{nome} {valore}"


def _eventi_da_riga(riga: str) -> tuple[list[str], str | None, bool]:
    """Da una riga NDJSON di `--output-format stream-json`: (avanzamenti, esito, errore).

    `esito is None` finche' non arriva l'evento `result`: e' il solo che chiude il turno.
    Una riga non-JSON non e' un guasto — la CLI stampa avvisi su stdout — e viene ignorata
    invece di far cadere il turno.
    """
    try:
        dato = json.loads(riga)
    except json.JSONDecodeError:
        return [], None, False
    if not isinstance(dato, dict):
        return [], None, False

    tipo = dato.get("type")
    if tipo == "assistant":
        blocchi = ((dato.get("message") or {}).get("content")) or []
        avanzamenti = [
            _descrivi_tool_use(b.get("name", "strumento"), b.get("input") or {})
            for b in blocchi
            if isinstance(b, dict) and b.get("type") == "tool_use"
        ]
        return avanzamenti, None, False
    if tipo == "result":
        return [], str(dato.get("result") or ""), bool(dato.get("is_error", False))
    return [], None, False


def _find_claude_binary(config_bin: str = "") -> str:
    """Trova l'eseguibile claude nell'ordine: config → PATH → app macOS → VSCode ext."""
    if config_bin:
        p = Path(config_bin).expanduser()
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"claude_code_bin configurato non trovato: {config_bin}")

    # 1. PATH
    found = shutil.which("claude")
    if found:
        return found

    # 2. macOS Claude Code app (versioned, newest first)
    app_base = Path.home() / "Library/Application Support/Claude/claude-code"
    if app_base.exists():
        versions = sorted(
            (p for p in app_base.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        for v in versions:
            binary = v / "claude.app/Contents/MacOS/claude"
            if binary.exists():
                logger.info("ClaudeCodeAdapter: binary trovato in %s", binary)
                return str(binary)

    # 3. VSCode extension (anthropic.claude-code-*)
    pattern = str(
        Path.home() / ".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"
    )
    matches = sorted(glob.glob(pattern), reverse=True)
    if matches:
        logger.info("ClaudeCodeAdapter: binary trovato in VSCode ext: %s", matches[0])
        return matches[0]

    raise FileNotFoundError(
        "claude CLI non trovato. Installa Claude Code (https://claude.ai/download) "
        "oppure imposta voice_channel.runtime.claude_code_bin in factory.config.yaml."
    )


# ---------------------------------------------------------------------------
# ClaudeCodeAdapter
# ---------------------------------------------------------------------------

class ClaudeCodeAdapter(FactoryRuntime):
    """
    Adapter che delega ogni utterance vocale a `claude -p` CLI.

    La factory viene eseguita con accesso ai tool specificati in claude_code_allowed_tools
    (default: sola lettura). Claude Code legge CLAUDE.md e applica l'intero contesto
    della factory (skill, agenti, wiki, config).

    Ogni turno e' indipendente (sessione fresca a ogni utterance).
    """

    def __init__(
        self,
        config: "VoiceConfig",
        repo_dir: str | None = None,
    ) -> None:
        self._config = config
        self._repo_dir = repo_dir or str(Path.cwd())
        rt = config.runtime
        self._timeout: int = getattr(rt, "claude_code_timeout", 120)
        self._max_spoken: int = getattr(rt, "claude_code_max_spoken", 500)
        self._allowed_tools: str = getattr(rt, "claude_code_allowed_tools", _DEFAULT_ALLOWED_TOOLS)
        self._model: str = getattr(rt, "claude_code_model", "")
        self._cancelled: dict[str, bool] = {}

        # Auto-detect binary una volta sola nel costruttore
        try:
            self._bin = _find_claude_binary(getattr(rt, "claude_code_bin", ""))
        except FileNotFoundError as exc:
            self._bin = ""
            self._startup_error = str(exc)
        else:
            self._startup_error = ""

    # ------------------------------------------------------------------
    # submit
    # ------------------------------------------------------------------

    async def submit(
        self, text: str, session_id: str
    ) -> AsyncGenerator[RuntimeEvent, None]:
        """Esegue `claude -p` in **streaming** e itera eventi, avanzamenti compresi.

        Prima usava `--output-format json`, che non e' uno stream: fra l'acknowledgment e
        la fine non arrivava nulla per minuti, e `Progress` — uno dei sette tipi del
        contratto — **non veniva emesso da nessuno**. Chi consumava il contratto non poteva
        distinguere «sta lavorando» da «e' bloccato»: la plancia mostrava «la factory sta
        lavorando...» e basta, e per saperne di piu' doveva leggere il transcript della
        sessione figlia, cioe' aggirare il contratto invece di usarlo.

        `--output-format stream-json --verbose` emette NDJSON: `system/init`, poi un
        `assistant` per ogni passo (che porta i blocchi `tool_use`), poi un `result` che
        chiude. Gli avanzamenti nascono da li'.
        """
        self._cancelled[session_id] = False

        if self._startup_error:
            yield Error(self._startup_error)
            return

        yield Acknowledgment("sto consultando la factory...")

        if self._cancelled.get(session_id):
            return

        # Costruisce il comando claude -p
        cmd = [
            self._bin,
            "--print",
            text,
            # `--verbose` non e' un di piu': la CLI rifiuta `stream-json` senza di esso
            # quando si usa `--print`.
            "--output-format", "stream-json",
            "--verbose",
            "--allowedTools", self._allowed_tools,
        ]
        if self._model:
            cmd += ["--model", self._model]

        logger.debug(
            "ClaudeCodeAdapter: avvio cmd=%r cwd=%s allowed_tools=%r",
            cmd[0], self._repo_dir, self._allowed_tools,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._repo_dir,
            )

        except FileNotFoundError:
            yield Error(
                "claude CLI non trovato. "
                "Installa Claude Code oppure imposta claude_code_bin in factory.config.yaml."
            )
            return
        except Exception as exc:
            yield Error(f"Errore avvio ClaudeCode: {exc}")
            return

        if self._cancelled.get(session_id):
            return

        # stderr si drena in parallelo: un processo che riempie il buffer di stderr mentre
        # noi leggiamo stdout si blocca, e il sintomo sarebbe un timeout — cioe' la diagnosi
        # sbagliata per la causa sbagliata.
        raccolta_errori = asyncio.ensure_future(proc.stderr.read())

        scadenza = time.monotonic() + self._timeout
        result_text: str | None = None
        is_error_flag = False
        fuori_protocollo: list[str] = []
        scaduto = False

        while True:
            resta = scadenza - time.monotonic()
            if resta <= 0:
                scaduto = True
                break
            try:
                riga_b = await asyncio.wait_for(proc.stdout.readline(), timeout=resta)
            except asyncio.TimeoutError:
                scaduto = True
                break
            if not riga_b:                       # EOF: il processo ha chiuso stdout
                break
            if self._cancelled.get(session_id):
                break

            riga = riga_b.decode("utf-8", errors="replace").strip()
            if not riga:
                continue
            avanzamenti, esito, errore = _eventi_da_riga(riga)
            for passo in avanzamenti:
                yield Progress(passo)
            if esito is not None:
                result_text, is_error_flag = esito, errore
                break
            if not riga.startswith("{"):
                # Una CLI che non conosce `stream-json` stampa testo semplice: si tiene
                # da parte invece di perderlo, e serve da risposta se il `result` non arriva.
                fuori_protocollo.append(riga)

        if scaduto:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raccolta_errori.cancel()
            yield Error(f"Timeout: la factory non ha risposto in {self._timeout}s.")
            return

        if self._cancelled.get(session_id):
            raccolta_errori.cancel()
            return

        try:
            stderr_raw = (await raccolta_errori).decode("utf-8", errors="replace").strip()
        except Exception:
            stderr_raw = ""

        if result_text is None:
            result_text = "\n".join(fuori_protocollo).strip()

        if not result_text:
            yield Error(f"Nessuna risposta dalla factory. {stderr_raw[:200]}")
            return

        if is_error_flag or not result_text:
            err_msg = result_text or stderr_raw[:200] or "Risposta vuota dalla factory."
            yield Error(err_msg[:300])
            return

        # La domanda si toglie dal riassunto prima di estrarlo: altrimenti la voce la
        # direbbe due volte, una dentro il riassunto e una come gate (TSK-688).
        domanda = _domanda_finale(result_text)
        testo_riassunto = result_text
        if domanda:
            testo_riassunto = result_text.rsplit(domanda, 1)[0]

        spoken = _extract_spoken(testo_riassunto, max_chars=self._max_spoken)
        if not spoken:
            spoken = "elaborazione completata"

        yield SpokenSummary(spoken)
        yield Artifact(kind="text", content=result_text)

        if domanda:
            # `Question` al posto di `Done`: il turno NON e' finito, attende una persona.
            # Distinguerli e' tutto il punto — «finito» e «fermo ad aspettarti» si vedevano
            # uguali, e il committente se n'e' accorto guardando lo schermo (2026-09-24).
            yield Question(domanda)
        else:
            yield Done()

        logger.debug(
            "ClaudeCodeAdapter: sessione=%s completata (%d chars, spoken=%d chars)",
            session_id, len(result_text), len(spoken),
        )

    # ------------------------------------------------------------------
    # cancel / aclose
    # ------------------------------------------------------------------

    async def cancel(self, session_id: str) -> None:
        self._cancelled[session_id] = True

    async def aclose(self) -> None:
        self._cancelled.clear()
