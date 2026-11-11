#!/usr/bin/env python3
"""
observe.py — Osservatore della flotta (EP-065 / US-270 / TSK-642 + TSK-648 +
TSK-657, che vi ha assorbito TSK-655).

UN SOLO tool, UN SOLO entry point sulla telemetria, TRE SOTTOCOMANDI, UN formato
JSON (A-22 + AC1: «due artefatti separati sulla stessa telemetria sono la
duplicazione che A-6 vieta»). Sopra il layer di parsing di TSK-642 stanno i tre
sottocomandi della domanda, piu' `mandato` che rende il layer ispezionabile:

    observe.py --differ [--json] [--unita X]   le unita' dichiarate obbligatorie
                                               vengono raggiunte?   exit 5 su >=1
                                               verdetto `divergente`
    observe.py censimento [--orphans]          quali unita' non lo sono mai
                                               state?               exit 0
    observe.py --load [--json] [--asserzione]  quanto carico si paga, E SU QUALE
                                               ADAPTER + istruttoria PATTERN +
                                               asserzione A-23(i); `--asserzione`
                                               mette l'exit code nel path (6)
    observe.py mandato [--json]                il layer di parsing di TSK-642

Comune ai quattro: `--foglie-snapshot FILE.json` sostituisce l'inventario delle
foglie con uno CONGELATO nei soli verdetti del differ (TSK-657, ingresso delle
fixture di regressione di A-49; `censimento` e `--load` restano sul filesystem
reale, e un run congelato lo dichiara in `meta.foglie_snapshot`).

TELEMETRIA ASSENTE NON E' UN ERRORE (TSK-655): con `--projects-dir` su una
cartella inesistente i quattro sottocomandi stampano `verdetto: non osservabile`
con la `ragione` ed escono **0**. Prima morivano con `KeyError: 'config'` (exit
1): «uno strumento che non sa dire *non ho visto* senza esplodere viola
l'invariante di lettura che lui stesso stampa».

OGNI run stampa `osservabilita: X/Y` (AC8), «cosi' un futuro 0/2/8 si legge come
*lo strumento non ha visto*, MAI come *la flotta e' conforme*».

CINQUE PRIMITIVE (tutte necessarie, tutte esposte come funzioni importabili):

  1. `mandato(T)`            — primo messaggio `role: user` del transcript,
                               classificato esecuzione / manutenzione / citazione.
                               Il campo esiste nella telemetria e non era esposto:
                               senza di esso il differ **misura se stesso**.
  2. canali `Read U Bash`    — unione, con path-match sui segmenti read-like di
                               `Bash`. A-22 congela verbatim che «`Read.file_path`
                               e' la Famiglia 2»: implementato alla lettera e'
                               SBAGLIATO e produce falsi `divergente`.
  3. `config@ts(e)`          — i trigger condizionali sono valutati con lo stato
                               dei flag AL MOMENTO DELL'ESECUZIONE, via
                               `git show <commit-at-ts>:factory.config.yaml`.
  4. asse-foglia-only        — per le unita'-agente l'asse corpo e' inosservabile
                               per costruzione (frontmatter Pattern A): nessun
                               `Read` viene emesso. L'ancoraggio e' la foglia.
  5. filtro di esclusione    — fuori la giornata di authoring (> 2026-09-04) e i
                               tocchi auto-referenziali dello strumento di misura
                               o della deliberazione.

NESSUNO DEI DUE CANALI E' GROUND TRUTH (A-33, dichiarato dal Critico come
assunzione piu' fragile della sessione):
  - `Read` **sottostima**: dove il corpo e' iniettato (agenti via frontmatter,
    skill slash-invocate via tool `Skill`) nessun `Read` viene emesso;
  - `Bash` path-match **sovrastima**: un `grep`/`wc` conta come lettura, e la
    popolarita' di un file non e' l'esecuzione del protocollo che contiene
    (A-43: «ho misurato la popolarita' del file, non l'esecuzione del protocollo»).
Il layer misura l'**accesso**, non l'**onoraggio**. Un `invariato` derivato da
questi canali e' **poca informazione**; solo il `divergente` e' forte.

LIMITE NON RISOLTO (dissenso 6 di EP-065 / A-49) — va letto insieme all'output:
tutte e quattro le raffinature di specifica che questo file implementa, prodotte
da due autori indipendenti, hanno mosso il conteggio nella **stessa direzione**:
meno reperti contro la campagna EP-060. **Nessuna correzione ha peggiorato il
verdetto di una singola unita'.** Le 3 fixture di regressione di TSK-649 sono il
rimedio adottato e verificano che lo strumento non sbagli *sui tre casi che i
suoi autori hanno gia' classificato a mano*: un test di regressione, **non una
calibrazione indipendente**. Questo file non e' una calibrazione indipendente.

VINCOLI (AC17): read-only sulla telemetria (nessuna scrittura, nessuno
spostamento di transcript), determinism-first (nessun LLM nel path del verdetto),
nessun auto-fix, nessun `git checkout`, nessuna scrittura in `wiki/`.
Zero dipendenze esterne: stdlib + `tools/session-analysis/parse-transcript.py`
(che porta con se' il walker fan-in riparato da EP-062 e il suo schema-guard).

Exit codes: 0 ok · 1 errore d'uso/IO · 4 dipendenza interna assente · 5 almeno un
verdetto `divergente` (`--differ`) · 6 asserzione A-23(i) fallita
(`--load --asserzione`) · 7 asserzione ANTI-RICRESCITA di `CLAUDE.md` fallita
(`--load --asserzione`, US-276 AC5; precede il 6 perche' A-23(i) e' rossa oggi e
un codice condiviso renderebbe il verdetto inosservabile). Il codice 3 di TSK-642 («sottocomando non implementato»)
e' ritirato: i tre sottocomandi esistono.

CIO' CHE NON ESISTE ANCORA, e che va saputo leggendo l'output: le fixture reali e
il contract test di TSK-649, incluse le 3 fixture di regressione di A-49. Finche'
non esistono, questo strumento non e' stato verificato da nessuno tranne i propri
autori — e «un osservatore scritto una volta e mai riverificato produce uno zero
fiducioso».

[^src: management/kanban/EP-065-sanatoria-della-flotta/US-270-osservatore-flotta-multi-asse/TSK-642.md]
[^src: wiki/decisions/tavola-rotonda-e5b81d64-9f27-4a3c-b012-7d6e4f8a91c5-2026-09-21.md §A-22, A-32, A-33, A-41, A-43, A-49]
"""

import argparse
import collections
import datetime
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent

# ─── Riuso, non copia (A-6) ───────────────────────────────────────────────────
# Il layer di lettura della telemetria e' quello di EP-061 (467 LOC) sopra il
# walker fan-in riparato da EP-062. Import via importlib perche' il nome del
# file contiene trattini. FAIL-LOUD: se la dipendenza manca non reimplementiamo
# il walker in silenzio — sarebbe esattamente la duplicazione che A-6 vieta.
_PT_PATH = HERE.parent / "session-analysis" / "parse-transcript.py"


def _carica_parse_transcript():
    if not _PT_PATH.exists():
        sys.stderr.write(
            "ERROR: dipendenza interna assente: %s\n"
            "       Il layer di parsing riusa il walker fan-in di EP-061/EP-062 "
            "(import, non copia — A-6).\n" % _PT_PATH
        )
        raise SystemExit(4)
    spec = importlib.util.spec_from_file_location("_fo_parse_transcript", _PT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PT = _carica_parse_transcript()

# US-319: il PATTERN e' indice (`PATTERN.md`) + moduli linkati nella sua tabella
# §Moduli. Quali file sono «il PATTERN» lo decide un solo modulo (import, non copia).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lint"))
from pattern_modules import pattern_files as _pattern_files  # noqa: E402

# Schema-guard di EP-062 (TSK-546): l'insieme verificato empiricamente vive in
# `harvest-session-tokens.py` ed e' raggiunto per transitivita', cosi' resta una
# sola fonte di verita'. Se la catena si rompe lo diciamo (WARNING fail-loud):
# «un osservatore scritto una volta e mai riverificato produce uno zero fiducioso».
_CC_VERSIONS_FALLBACK = frozenset({"2.1.263", "2.1.258", "2.1.257", "2.1.256"})


def versioni_cc_supportate():
    """Ritorna (frozenset, fonte). Fonte 'fallback-locale' => la catena e' rotta."""
    harvest = getattr(PT, "_harvest_mod", None)
    supportate = getattr(harvest, "SUPPORTED_CC_VERSIONS", None) if harvest else None
    if supportate:
        return frozenset(supportate), "harvest-session-tokens.py"
    return _CC_VERSIONS_FALLBACK, "fallback-locale"


# ─── Costanti normative ───────────────────────────────────────────────────────

# AC6 — giornata di authoring della campagna EP-060, ESCLUSA obbligatoriamente.
# Commit di riferimento: 781ea01 (2026-09-04T11:22) e 6857314 (2026-09-04T12:03).
# Senza il filtro `dev-protocol` legge falsamente `invariato`, perche' i suoi
# accessi in quella giornata sono l'atto di scriverlo, non di eseguirlo.
# Il filtro puo' essere stretto (`--da` piu' recente), MAI allargato.
GIORNATA_AUTHORING = "2026-09-04"

TIPI_UNITA_FLOTTA = ("agents", "skills", "commands")

# v2.34: `lint-checks` e' modulare in 11 famiglie `lint-checks-*.md`. Le famiglie
# sono l'asse foglia dell'unita', non unita' distinte (A-43 attribuisce a
# `lint-checks` gli accessi alle famiglie). Mappa DICHIARATA, non euristica: la
# regola generica «slug con prefisso di un'altra unita' => foglia» sbaglierebbe
# su `agents/wiki-keeper-worker` e `commands/prototype-status`, che sono unita'.
FAMIGLIE_MODULARI = {"lint-checks-": "skills/lint-checks"}

# AC10 — asse agnostico: cio' che `/factory-bootstrap` e `/factory-upgrade`
# copiano verbatim nelle factory derivate. «Always-on» non ha un valore unico in
# una factory multi-adapter, quindi l'asse agnostico si misura a parte.
# US-319: i moduli del PATTERN sono agnostici come l'indice.
PATTERN_MODULI_NOTI = ("PATTERN-integration.md", "PATTERN-runtime.md",
                       "PATTERN-governance.md", "PATTERN-capabilities.md")
AGNOSTICO_FILE = {"PATTERN.md", "CHANGELOG.md", "CAPABILITIES.md", *PATTERN_MODULI_NOTI}
AGNOSTICO_PREFISSI = {"meta-prompts/": "agnostico/meta-prompts"}

# AC11 — entry point PER-ADAPTER (il report always-on e' per-adapter, non globale).
ADAPTER_ENTRYPOINT = {
    "CLAUDE.md": "claude",
    ".claude/CLAUDE.md": "claude",
    "CONVENTIONS.md": "aider",
    "AGENTS.md": "openai",
}
ADAPTER_PREFISSI = {
    ".cursor/rules/": "cursor",
    ".cursor/": "cursor",
    ".aider/": "aider",
    ".openai/": "openai",
    ".gemini/": "gemini",
    ".chatgpt/": "chatgpt",
}

# Tabella DICHIARATA (fonte: CLAUDE.md §Adapter registry), non misurata: e' il
# contesto di lettura che AC11 pretende accanto al report per-adapter. TSK-648 la
# stampa; qui e' esposta perche' il layer di parsing e' l'unica sede condivisa.
ADAPTER_LAG = {
    "claude":  {"contract": "2.42", "maturita": "full"},
    "cursor":  {"contract": "2.37", "maturita": "core"},
    "aider":   {"contract": "2.13", "maturita": "core"},
    "openai":  {"contract": None,   "maturita": "partial"},
    "gemini":  {"contract": None,   "maturita": "manifest-only"},
    "chatgpt": {"contract": None,   "maturita": "manifest-only"},
}

# AC4 — trigger condizionali per unita'. Valutati con `config@ts(e)`, non con lo
# stato di oggi. Tabella estendibile: un'unita' assente qui non ha trigger
# dichiarato e riceve `flags: {}` (assenza di condizione, non condizione falsa).
TRIGGER_CONDIZIONALI = {
    "skills/dev-protocol": [
        "analytics.measurement.enabled",   # [ENABLED 2026-06-04] — gate della foglia
        "analytics.dogfooding.enabled",    #   analytics-instrumentation.md
        "code_intelligence.l3_impact.enabled",
        "fe_correctness.enabled",
        "ux_ui.enabled",
    ],
    "skills/functional-oracle-protocol": ["fe_correctness.functional_oracle.enabled"],
    "skills/prototype-generation-protocol": ["prototyping.enabled"],
    "commands/prototype": ["prototyping.enabled"],
    "skills/tavola-rotonda-protocol": ["tavola_rotonda.enabled"],
    "agents/tavola-rotonda-moderatore": ["tavola_rotonda.enabled"],
    "skills/refactor-agent-skills": ["refactor_agent_skills.enabled"],
    "agents/fleet-doctor": ["refactor_agent_skills.enabled"],
    "skills/session-analysis-protocol": ["session_analysis.enabled"],
    "skills/parallel-scheduling": ["scheduler.enabled"],
    "skills/kanban-coordination-protocol": ["kanban_coordination.enabled"],
}

# ─── mandato(T): classificazione del primo messaggio `role: user` ─────────────
# Regole deterministiche con id esplicito. L'id finisce nell'output
# (`mandato_regola`), cosi' chi legge vede quanti record poggiano su un match
# positivo e quanti su un default — la taratura resta ispezionabile (A-49).

_WRAPPER_NON_MANDATO = re.compile(
    r"^\s*(\[Your previous response|\[Request interrupted|<task-notification>|"
    r"<local-command-caveat>|Caveat:|<command-name>|<command-message>|"
    r"<system-reminder>|<user-prompt-submit-hook>|<local-command-stdout>|"
    r"This session is being continued|Please continue the conversation)",
    re.IGNORECASE,
)

# La deliberazione non e' esecuzione: un partecipante a una Tavola Rotonda che
# legge un'unita' per argomentarci sopra non la sta eseguendo. Senza questa
# regola il role-assignment R-ESEC-4 marca `esecuzione` ogni round di ogni
# tavolo, e il differ torna a misurare se stesso (A-32).
# Ancorato all'INIZIO del mandato: e' il turno di un partecipante, non un
# qualsiasi testo che cita un tavolo. Misurato sul proprio output prima di
# pubblicarlo: la versione non ancorata escludeva «Implementa TSK-545 seguendo
# la skill dev-protocol» e «Consuma TSK-636/637» — cioe' proprio le esecuzioni
# che compongono l'unico `divergente` della tabella di A-41. Un filtro che
# cancella il solo reperto forte e' la taratura a senso unico di A-49 in atto.
_R_DELIBERA = re.compile(
    r"^\s*(?:\*\*)?(?:sei|partecipi|partecipa)\b[^\n]{0,140}?tavola[\s-]rotonda",
    re.IGNORECASE)
_R_DELIBERA_CRITICO = re.compile(
    r"^\s*(?:\*\*)?sei\b[^\n]{0,90}critico[\s-]dedicato", re.IGNORECASE)

_R_ESEC = [
    ("R-ESEC-1", re.compile(r"\b(esegui|implementa|consuma|completa|prosegui con)\b[^\n]{0,120}\bTSK-\d+", re.IGNORECASE)),
    ("R-ESEC-2", re.compile(r"\bsegu(?:endo|i)\s+(?:la\s+skill|il\s+protocollo|la\s+procedura)\b", re.IGNORECASE)),
    ("R-ESEC-3", re.compile(r"\besegui\b[^\n]{0,80}\b(protocollo|ciclo standard|skill|comando|upgrade)\b", re.IGNORECASE)),
    ("R-ESEC-4", re.compile(r"^\s*sei\s+[`'\"]?[a-z][a-z0-9-]{2,}[`'\"]?\b", re.IGNORECASE)),  # role assignment
    ("R-ESEC-5", re.compile(r"\b(/dev|/run|/review|/lint|/query|/tavola-rotonda|/prototype|/functional-oracle)\b")),
    ("R-ESEC-6", re.compile(
        r"\b(invoca|lancia|avvia|attiva|gira)\b[^\n]{0,70}"
        r"(tavola[\s-]rotonda|\bskill\b|\bcomando\b|protocollo|\bagente\b|osservatore|/[a-z-]{3,})",
        re.IGNORECASE)),
]

_R_MANU = [
    ("R-MANU-1", re.compile(
        r"\b(refactor\w*|riscriv\w+|aggiorna|modifica|correggi|sposta|rinomina|estrai|"
        r"sostituisc\w+|riduci|ripara|allinea|cleanup|bump|crea|aggiungi|estendi|elimina|rimuovi)\b"
        r"[^\n]{0,200}?(\.claude/|\.cursor/|meta-prompts/|PATTERN\.md|CHANGELOG\.md|"
        r"CAPABILITIES\.md|CLAUDE\.md|CONVENTIONS\.md)", re.IGNORECASE | re.DOTALL)),
    ("R-MANU-2", re.compile(
        r"\b(aggiorna|allinea|upgrade|migra|porta)\b[^\n]{0,80}"
        r"\b(factory|documentazione|versione|adapter|meta-prompt\w*)\b", re.IGNORECASE)),
    ("R-MANU-3", re.compile(r"\b(pilot|target)\b[^\n]{0,200}?(soglia\s+REFACTOR|verdetto\s+(REFACTOR|VALUTARE))", re.IGNORECASE | re.DOTALL)),
    ("R-MANU-4", re.compile(r"\bfactory-upgrade\b|\bskill-creator\b", re.IGNORECASE)),
]

_R_CIT = [
    ("R-CIT-1", re.compile(
        r"\b(leggi|analizza|censisci|misura|conta|verifica|valuta|documenta|riporta|"
        r"indaga|istruttoria|rispondi|confronta|ispeziona|elenca)\b", re.IGNORECASE)),
]

# AC6 — auto-referenzialita': il tocco prodotto dallo strumento di misura o dalla
# deliberazione sul proprio oggetto. «Un'unita' il cui unico evento nella
# finestra e' prodotto dallo strumento di misura non ha un verdetto: ha un
# artefatto dell'osservazione» (A-41). Marker CO-OCCORRENTI dove serve, per non
# marcare auto-referenziale ogni Tavola Rotonda: solo quelle il cui OGGETTO e' la
# flotta. Marcare troppo sposterebbe il conteggio nella direzione che assolve.
# Marker DIRETTI: l'oggetto del mandato e' lo strumento di misura o questo EP.
# Gli id di EP-065 sono espliciti (TSK-640..653, US-268..278): la versione con
# intervallo approssimato inglobava TSK-636/637 di EP-064, che sono due delle
# nove esecuzioni su cui poggia l'unico `divergente` misurato.
_R_AUTOREF_DIRETTI = [
    ("A-EP065", re.compile(r"\bEP-065\b|sanatoria della flotta", re.IGNORECASE)),
    ("A-OSSERVATORE", re.compile(r"fleet-observer|osservatore della flotta", re.IGNORECASE)),
    ("A-TSK-EP065", re.compile(r"\bTSK-6(?:4[0-9]|5[0-3])\b|\bUS-2(?:6[89]|7[0-8])\b")),
]
# Marker CO-OCCORRENTI: mandati il cui intento PRIMARIO e' misurare la flotta.
# Deliberatamente stretti. Le versioni larghe (tavola rotonda + flotta;
# EP-060 + audit; `complexity-budget-check`) escludevano le esecuzioni e i
# refactor reali di EP-060 — 47 transcript su 194, tutti nella direzione che
# assolve la campagna. «Lavorare SULLA flotta» non e' «misurare la flotta»:
# un refactor e' manutenzione e va classificato, non nascosto.
_R_AUTOREF_COOCCORRENTI = [
    ("A-MISURA-FLOTTA",
     re.compile(r"^\s*(?:\*\*|[-*#>]|\d+\.)?\s*(?:conta|misura|censisci|quantifica|pesa)\b|"
                r"\bcensimento\b", re.IGNORECASE | re.MULTILINE),
     re.compile(r"\bflott\w+|\.claude/(?:skills|agents|commands)", re.IGNORECASE)),
]


def _testo_utente(contenuto):
    """Testo di un messaggio `role: user`, o None se non e' testo.

    Claude Code usa DUE forme per lo stesso campo: stringa (CC <= 2.1.263) e
    lista di blocchi `{"type": "text"}` (CC 2.1.270+). Accettare solo la prima
    fa sparire in silenzio il mandato delle sessioni recenti — la classe esatta
    di `isSidechain` in EP-062, che ometteva il 60% della flotta senza dirlo.
    I record che contengono un `tool_result` non sono mandati e restano fuori.
    """
    if isinstance(contenuto, str):
        return contenuto.strip()
    if isinstance(contenuto, list):
        pezzi = []
        for item in contenuto:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_result":
                return None
            if item.get("type") == "text" and item.get("text"):
                pezzi.append(item["text"])
        return "\n".join(pezzi).strip() if pezzi else None
    return None


def prima_richiesta_utente(percorso):
    """Primitiva 1a — primo messaggio `role: user` utile del transcript.

    Salta i wrapper dell'harness (`<task-notification>`, caveat dei comandi
    locali, solleciti di continuazione) e i `tool_result` (content = lista):
    non sono mandati, sono meccanica della sessione.

    Ritorna (testo, ts) oppure (None, None). Read-only, fail-open sulle righe
    malformate (stessa politica di EP-062).
    """
    try:
        fh = open(percorso, encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    with fh:
        for riga in fh:
            riga = riga.strip()
            if not riga:
                continue
            try:
                rec = json.loads(riga)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "user":
                continue
            testo = _testo_utente((rec.get("message") or {}).get("content"))
            if testo is None:
                continue  # tool_result o blocco non testuale: non e' un mandato
            if not testo or _WRAPPER_NON_MANDATO.match(testo):
                continue
            return testo, rec.get("timestamp")
    return None, None


def e_deliberazione(testo, unita_esecutrice=None):
    """True se il transcript e' un TURNO DI DELIBERAZIONE, non un'esecuzione.

    Discriminante misurato, non assunto: l'unita' esecutrice viene dal campo
    `attributionAgent` della telemetria. Il MODERATORE che gira il protocollo lo
    sta **eseguendo** (e' la Famiglia 2 sull'unita' `tavola-rotonda-protocol`, il
    caso congelato in A-32 come `invariato`); i PARTECIPANTI che leggono le
    unita' di cui discutono producono i tocchi della deliberazione, che AC6
    esclude alla lettera («i tocchi auto-referenziali prodotti dallo strumento
    di misura **o dalla deliberazione**»).
    """
    if not testo:
        return False
    if unita_esecutrice == "agents/tavola-rotonda-moderatore":
        return False
    return bool(_R_DELIBERA.search(testo) or _R_DELIBERA_CRITICO.search(testo))


def classifica_mandato(testo, unita_esecutrice=None):
    """Primitiva 1b — (classe, regola) con classe in {esecuzione, manutenzione,
    citazione}.

    Precedenza dichiarata:
      1. formula di esecuzione di un TSK/protocollo  -> esecuzione
      2. intento di mutazione su un'unita'/factory   -> manutenzione
      3. verbo di sola lettura                       -> citazione
      4. default                                     -> citazione (R-CIT-DEFAULT)

    (1) precede (2) perche' un TSK il cui effetto e' manutentivo resta un mandato
    di esecuzione a livello di sessione: la correzione per-unita' non e' testuale
    ma **di canale** (A-41) e avviene in `mandato_effettivo()`.

    Il default a `citazione` e' conservativo e **va letto**: riduce il numero di
    esecuzioni osservate, quindi riduce le divergenze possibili — la stessa
    direzione che assolve di cui A-49 accusa l'intero strumento. Per questo la
    regola che ha sparato viaggia nell'output e il conteggio per regola sta nel
    meta: chi legge deve poter vedere quanti record poggiano su un default.
    """
    if not testo:
        return "citazione", "R-CIT-DEFAULT-NO-MANDATO"
    if e_deliberazione(testo, unita_esecutrice):
        return "citazione", "R-CIT-DELIBERA"
    for rid, rx in _R_ESEC:
        if rx.search(testo):
            return "esecuzione", rid
    for rid, rx in _R_MANU:
        if rx.search(testo):
            return "manutenzione", rid
    for rid, rx in _R_CIT:
        if rx.search(testo):
            return "citazione", rid
    return "citazione", "R-CIT-DEFAULT"


def e_auto_referenziale(testo, unita_esecutrice=None):
    """Primitiva 5a — (bool, marker) sull'auto-referenzialita' del mandato."""
    if not testo:
        return False, None
    for mid, rx in _R_AUTOREF_DIRETTI:
        if rx.search(testo):
            return True, mid
    for mid, rx_a, rx_b in _R_AUTOREF_COOCCORRENTI:
        if rx_a.search(testo) and rx_b.search(testo):
            return True, mid
    if e_deliberazione(testo, unita_esecutrice):
        return True, "A-DELIBERAZIONE"
    return False, None


def mandato(percorso_transcript, unita_esecutrice=None, slugs=None):
    """Primitiva 1 — `mandato(T)` completo per un transcript (main o sub-agent).

    Ritorna dict con: testo (troncato e redatto), ts, classe, regola,
    auto_referenziale, marker, unita nominate nel mandato.

    `unita_nominate` (TSK-648) e' calcolato sul testo COMPLETO, non sull'estratto
    troncato a 220 char che viaggia nell'output: e' l'evidenza di esecuzione del
    differ e troncarla perderebbe i mandati lunghi.
    """
    testo, ts = prima_richiesta_utente(percorso_transcript)
    classe, regola = classifica_mandato(testo, unita_esecutrice)
    autoref, marker = e_auto_referenziale(testo, unita_esecutrice)
    return {
        "mandato": classe,
        "mandato_regola": regola,
        "ts": ts,
        "auto_referenziale": autoref,
        "auto_referenziale_marker": marker,
        "estratto": PT._redact_str(testo[:220].replace("\n", " "), 220) if testo else None,
        "unita_nominate": unita_nominate(testo, slugs),
        "unita_menzionate": unita_menzionate(testo, slugs),
    }


def mandato_effettivo(classe_sessione, regola_sessione, unita, unita_mutate):
    """Primitiva 1c — mandato EFFETTIVO per (transcript, unita').

    A-41, correzione di CANALE e non di classificazione: «nell'harness un `Edit`
    **richiede** un `Read` precedente sullo stesso path: quel `Read` e' la
    precondizione meccanica della mutazione, non un atto di esecuzione». Quindi
    se in quel transcript l'unita' e' stata MUTATA, ogni accesso alla stessa
    unita' e' manutenzione, qualunque cosa dica il testo del mandato.
    """
    if unita in unita_mutate:
        return "manutenzione", "R-MANU-CANALE"
    return classe_sessione, regola_sessione


# ─── Primitiva 4: risoluzione unita' + asse (con asse-foglia-only) ────────────

_RX_UNITA_FOGLIA_DIR = re.compile(r"^\.claude/(agents|skills|commands)/references/([^/]+)/[^/]+\.md$")
_RX_UNITA_FOGLIA_PIATTA = re.compile(r"^\.claude/(agents|skills|commands)/references/([^/]+\.md)$")
_RX_UNITA_CORPO = re.compile(r"^\.claude/(agents|skills|commands)/([^/]+)\.md$")

_cache_genitore_foglia = {}
_cache_genitore_dir = {}


def _genitore_foglia_piatta(radice_repo, tipo, nome_file):
    """Genitore di una foglia piatta `references/<nome>.md`: la prima unita' (in
    ordine alfabetico, quindi deterministico) il cui corpo la nomina.

    Es. `references/scheduler-wave-templates.md` -> `skills/parallel-scheduling`.
    Se nessuno la nomina resta orfana: e' un reperto, non un errore da nascondere.
    """
    chiave = (tipo, nome_file)
    if chiave in _cache_genitore_foglia:
        return _cache_genitore_foglia[chiave]
    genitore = None
    for kind in (tipo,) + tuple(t for t in TIPI_UNITA_FLOTTA if t != tipo):
        cartella = radice_repo / ".claude" / kind
        if not cartella.is_dir():
            continue
        for corpo in sorted(cartella.glob("*.md")):
            try:
                if nome_file in corpo.read_text(encoding="utf-8", errors="replace"):
                    genitore = "%s/%s" % (kind, corpo.stem)
                    break
            except OSError:
                continue
        if genitore:
            break
    _cache_genitore_foglia[chiave] = genitore
    return genitore


def _genitore_dir_foglia(radice_repo, tipo, cartella_foglie):
    """Genitore di `references/<cartella>/<foglia>.md` — e i suoi comproprietari.

    La cartella NON coincide sempre con lo slug dell'unita':
    `skills/references/tavola-rotonda/` appartiene a `skills/tavola-rotonda-protocol`
    e `skills/references/refactor/` a `skills/refactor-agent-skills`. Dare per
    scontata la coincidenza fabbrica unita' fantasma (`skills/tavola-rotonda`) e
    lascia le unita' reali con ZERO foglie lette: e' la classe del regex col
    gruppo di cattura sbagliato che ha restituito «zero foglie con fiducia»
    (A-32), qui trovata sul proprio output prima di pubblicarlo.

    Risoluzione deterministica: unita' omonima se esiste, altrimenti l'unita' che
    nomina la cartella piu' volte, con preferenza allo stesso tipo e tie-break
    alfabetico. Gli altri proprietari vengono RESTITUITI, non scartati: la foglia
    condivisa e' reale (`agents/tavola-rotonda-moderatore` condivide le foglie
    del protocollo) e TSK-648 deve poterla vedere.
    """
    chiave = (tipo, cartella_foglie)
    if chiave in _cache_genitore_dir:
        return _cache_genitore_dir[chiave]

    omonima = radice_repo / ".claude" / tipo / ("%s.md" % cartella_foglie)
    ago = "references/%s/" % cartella_foglie
    proprietari = []
    for kind in TIPI_UNITA_FLOTTA:
        cartella = radice_repo / ".claude" / kind
        if not cartella.is_dir():
            continue
        for corpo in sorted(cartella.glob("*.md")):
            try:
                n = corpo.read_text(encoding="utf-8", errors="replace").count(ago)
            except OSError:
                continue
            if n:
                proprietari.append((kind != tipo, -n, "%s/%s" % (kind, corpo.stem)))
    proprietari.sort()
    nomi = [nome for _, _, nome in proprietari]

    if omonima.exists():
        principale = "%s/%s" % (tipo, cartella_foglie)
    elif nomi:
        principale = nomi[0]
    else:
        principale = "%s/references/%s" % (tipo, cartella_foglie)
    altri = [n for n in nomi if n != principale]
    _cache_genitore_dir[chiave] = (principale, altri)
    return principale, altri


def normalizza_path(grezzo, radice_repo):
    """Path relativo alla radice del repo, oppure None se fuori dal repo.

    Gli accessi ai file di ALTRE factory (derivate, upgrade) non sono accessi a
    questa unita': vengono contati a parte (`fuori_repo`), non silenziati.
    """
    if not grezzo or not isinstance(grezzo, str):
        return None
    p = grezzo.strip().strip("'\"")
    if not p:
        return None
    radice = str(radice_repo)
    if p.startswith("~"):
        return None
    if p.startswith("/"):
        if p == radice:
            return "."
        if p.startswith(radice + "/"):
            p = p[len(radice) + 1:]
        else:
            return None  # fuori repo
    while p.startswith("./"):
        p = p[2:]
    return p or None


def risolvi_unita(path_rel, radice_repo):
    """Primitiva 4 — (unita', tipo, asse, adapter) per un path relativo.

    Asse `corpo` = il file dell'unita'; asse `foglia` = un reference file o una
    famiglia modulare. L'ancoraggio (quale asse e' osservabile) e' in
    `asse_ancorante()`.
    """
    if not path_rel:
        return None

    m = _RX_UNITA_FOGLIA_DIR.match(path_rel)
    if m:
        tipo, cartella_foglie = m.group(1), m.group(2)
        genitore, altri = _genitore_dir_foglia(radice_repo, tipo, cartella_foglie)
        return {"unita": genitore, "tipo_unita": genitore.split("/")[0],
                "asse": "foglia", "adapter": "claude",
                "unita_altri_proprietari": altri}

    m = _RX_UNITA_FOGLIA_PIATTA.match(path_rel)
    if m:
        tipo, nome = m.group(1), m.group(2)
        genitore = _genitore_foglia_piatta(radice_repo, tipo, nome)
        return {"unita": genitore or "%s/references/%s" % (tipo, nome[:-3]),
                "tipo_unita": tipo, "asse": "foglia", "adapter": "claude",
                "foglia_orfana": genitore is None}

    m = _RX_UNITA_CORPO.match(path_rel)
    if m:
        tipo, slug = m.group(1), m.group(2)
        for prefisso, unita_padre in FAMIGLIE_MODULARI.items():
            if slug.startswith(prefisso) and unita_padre.startswith(tipo + "/"):
                return {"unita": unita_padre, "tipo_unita": tipo,
                        "asse": "foglia", "adapter": "claude"}
        return {"unita": "%s/%s" % (tipo, slug), "tipo_unita": tipo,
                "asse": "corpo", "adapter": "claude"}

    # AC10 — asse agnostico
    if path_rel in AGNOSTICO_FILE:
        return {"unita": "agnostico/%s" % path_rel, "tipo_unita": "agnostico",
                "asse": "corpo", "adapter": None}
    for prefisso, unita_agn in AGNOSTICO_PREFISSI.items():
        if path_rel.startswith(prefisso):
            return {"unita": unita_agn, "tipo_unita": "agnostico",
                    "asse": "corpo", "adapter": None}

    # AC11 — entry point per-adapter
    if path_rel in ADAPTER_ENTRYPOINT:
        nome = ADAPTER_ENTRYPOINT[path_rel]
        return {"unita": "adapter/%s" % nome, "tipo_unita": "adapter",
                "asse": "corpo", "adapter": nome}
    for prefisso, nome in ADAPTER_PREFISSI.items():
        if path_rel.startswith(prefisso):
            return {"unita": "adapter/%s" % nome, "tipo_unita": "adapter",
                    "asse": "corpo", "adapter": nome}
    if path_rel.startswith("adapters/"):
        pezzi = path_rel.split("/")
        if len(pezzi) > 1 and pezzi[1] in ADAPTER_LAG:
            return {"unita": "adapter/%s" % pezzi[1], "tipo_unita": "adapter",
                    "asse": "corpo", "adapter": pezzi[1]}
    return None


def asse_ancorante(tipo_unita, asse):
    """Primitiva 4b — AC5: per le unita'-agente il differ si ancora al SOLO asse
    foglia.

    Il corpo di un agente e' **iniettato via frontmatter** (Pattern A): nessun
    `Read` viene emesso, quindi la sua assenza non e' informazione — non e' un
    `divergente`, e' un asse cieco. `tavola-rotonda-moderatore` (corpo 0,
    foglie 8) e' l'esempio congelato in A-32.

    NOTA aperta, deliberatamente NON estesa qui: anche le skill/comandi
    slash-invocati hanno il corpo iniettato (tool `Skill`, 14 chiamate nella
    finestra). Estendere la regola ai comandi allargherebbe l'area
    «inosservabile», cioe' la direzione che assolve la campagna (A-49): la
    decisione spetta a TSK-648, che ha in mano `invocazioni_skill` misurate.
    """
    if tipo_unita == "agents" and asse == "corpo":
        return False, "corpo-agente-iniettato-frontmatter-pattern-A"
    return True, None


# ─── Primitiva 2: canali Read U Bash read-like ────────────────────────────────

_RX_SEGMENTI = re.compile(r"&&|\|\||;|\n|(?<!\|)\|(?!\|)")
_RX_TOKEN_MD = re.compile(r"[A-Za-z0-9_@./~-]*\.md\b")
_RX_DIR_FLOTTA = re.compile(r"\.claude/(?:skills|agents|commands)/?(?:\s|\"|'|$)")

_CMD_READ_LIKE = {
    "cat", "sed", "head", "tail", "grep", "rg", "egrep", "fgrep", "wc", "less",
    "more", "awk", "nl", "diff", "cut", "sort", "uniq", "strings", "xxd", "od",
}
_GIT_READ_LIKE = {"show", "diff", "log", "grep", "blame", "cat-file"}
_RX_PY_READ = re.compile(r"read_text\(|\.read\(\)|readlines\(|read_bytes\(|open\([^)]*['\"]r['\"]")
_RX_SCRITTURA = re.compile(
    r">>|(?<![0-9<>=!-])>(?![>=])|\bsed\s+-i\b|\btee\b|\bmv\s|\bcp\s|\brm\s|"
    r"write_text\(|writelines\(|open\([^)]*['\"][wa]|\btruncate\b|\bapply\b\s+patch",
)
_STRUMENTI_LETTURA = {"Read", "NotebookRead"}
_STRUMENTI_MUTAZIONE = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def _segmento_e_scrittura(seg):
    return bool(_RX_SCRITTURA.search(seg))


def _segmento_e_read_like(seg):
    """Read-like DETERMINISTICO per allowlist, mai per euristica generica.

    `echo`, `ls`, `find` NON sono letture (64 `echo` con path `.md` nella
    finestra: contarli sarebbe il bug di canale al rovescio). `git` conta solo
    sui sottocomandi che leggono contenuto.
    """
    pezzi = seg.strip().split()
    if not pezzi:
        return False
    parola = pezzi[0].split("/")[-1]
    if parola in ("sudo", "time", "nice", "command"):
        pezzi = pezzi[1:]
        parola = pezzi[0].split("/")[-1] if pezzi else ""
    if parola in _CMD_READ_LIKE:
        return True
    if parola == "git":
        return any(p in _GIT_READ_LIKE for p in pezzi[1:3])
    if _RX_PY_READ.search(seg):
        return True
    return False


def canali_read_like(nome_tool, inp, radice_repo):
    """Primitiva 2 — accessi read-like di UN tool_use: `Read` UNIONE `Bash`.

    Ritorna lista di dict {canale, path, evidenza}. `canale` in {Read, Bash}.

    A-22 congela verbatim che «`Read.file_path` e' la Famiglia 2»: implementato
    alla lettera e' SBAGLIATO (rapporto misurato `Bash` read-like / `Read` =
    2,11x; `lint-checks` ha 0 `Read` e decine di `Bash`). Ma **nessuno dei due
    canali e' ground truth**: `Read` sottostima i corpi iniettati, il path-match
    su `Bash` sovrastima contando `grep`/`wc` come letture.

    Sottostima dichiarata e NON corretta: `grep -rn X .claude/skills/` legge
    l'intera cartella e qui non viene attribuito a nessuna unita' (nessun token
    `.md`). Viene contato in `bash_dir_scan_ignorati`, perche' attribuirlo a
    tutte le unita' gonfierebbe ogni `invariato` — l'esito che assolve.
    """
    accessi = []
    if nome_tool in _STRUMENTI_LETTURA:
        p = normalizza_path((inp or {}).get("file_path") or (inp or {}).get("notebook_path"), radice_repo)
        if p:
            accessi.append({"canale": "Read", "path": p, "evidenza": p})
        return accessi

    if nome_tool != "Bash":
        return accessi

    comando = (inp or {}).get("command") or ""
    for seg in _RX_SEGMENTI.split(comando):
        if not seg or not seg.strip():
            continue
        if _segmento_e_scrittura(seg) or not _segmento_e_read_like(seg):
            continue
        visti = set()
        for token in _RX_TOKEN_MD.findall(seg):
            p = normalizza_path(token, radice_repo)
            if not p or p in visti:
                continue
            visti.add(p)
            accessi.append({
                "canale": "Bash",
                "path": p,
                "evidenza": PT._redact_str(seg.strip()[:160], 160),
            })
    return accessi


def mutazioni(nome_tool, inp, radice_repo):
    """Path mutati da UN tool_use (`Edit`/`Write` o segmento `Bash` di scrittura).

    Alimenta `mandato_effettivo()`: e' la correzione di canale di A-41.
    """
    mutati = []
    if nome_tool in _STRUMENTI_MUTAZIONE:
        p = normalizza_path((inp or {}).get("file_path") or (inp or {}).get("notebook_path"), radice_repo)
        if p:
            mutati.append(p)
        return mutati
    if nome_tool != "Bash":
        return mutati
    for seg in _RX_SEGMENTI.split((inp or {}).get("command") or ""):
        if not seg or not _segmento_e_scrittura(seg):
            continue
        for token in _RX_TOKEN_MD.findall(seg):
            p = normalizza_path(token, radice_repo)
            if p:
                mutati.append(p)
    return mutati


def conta_dir_scan(nome_tool, inp):
    """Quante volte un `Bash` ha scandito una cartella della flotta senza che il
    path-match potesse attribuire l'accesso a un'unita'. Limite dichiarato."""
    if nome_tool != "Bash":
        return 0
    return len(_RX_DIR_FLOTTA.findall((inp or {}).get("command") or ""))


# ─── Primitiva 3: config@ts(e) ────────────────────────────────────────────────

class ConfigAlTs:
    """Primitiva 3 — stato dei flag AL MOMENTO DELL'ESECUZIONE (AC4).

    `git show <commit-at-ts>:factory.config.yaml`. Senza questo, `dev-protocol`
    restituisce 3 divergenze di cui 2 FALSE: i suoi trigger vengono valutati con
    i flag di oggi invece di quelli attivi quando l'esecuzione e' avvenuta.

    Read-only: solo `git log` / `git show`. Nessun `git checkout` (AC17).
    La storia del solo `factory.config.yaml` viene caricata UNA volta: le
    versioni distinte del file nella finestra sono pochissime, quindi il costo e'
    qualche `git show`, non uno per record.
    """

    def __init__(self, radice_repo, percorso_config="factory.config.yaml"):
        self.radice = pathlib.Path(radice_repo)
        self.percorso = percorso_config
        self.storia = self._carica_storia()      # [(commit, ts_iso)] desc
        self._testo = {}                          # commit -> testo file
        self._valori = {}                         # (commit, chiave) -> valore
        self.errore = None if self.storia else "storia del file non disponibile"

    def _git(self, *args):
        try:
            p = subprocess.run(("git", "-C", str(self.radice)) + args,
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            self.errore = str(exc)
            return None
        if p.returncode != 0:
            return None
        return p.stdout

    def _carica_storia(self):
        out = self._git("log", "--format=%H %cI", "--", self.percorso)
        if not out:
            return []
        storia = []
        for riga in out.splitlines():
            pezzi = riga.split(None, 1)
            if len(pezzi) == 2:
                storia.append((pezzi[0], pezzi[1].strip()))
        return storia  # git log e' gia' in ordine decrescente

    def commit_al_ts(self, ts):
        """Commit che ha prodotto la versione del file in vigore a `ts`."""
        if not ts or not self.storia:
            return None, None
        chiave = _ts_confrontabile(ts)
        for commit, cts in self.storia:
            if _ts_confrontabile(cts) <= chiave:
                return commit, cts
        return None, None  # ts precedente alla nascita del file

    def _testo_config(self, commit):
        if commit not in self._testo:
            self._testo[commit] = self._git("show", "%s:%s" % (commit, self.percorso)) or ""
        return self._testo[commit]

    def flag(self, ts, chiavi):
        """{chiave: valore} con i flag in vigore a `ts`, piu' il commit usato."""
        commit, cts = self.commit_al_ts(ts)
        risultato = {"commit": commit[:7] if commit else None,
                     "commit_ts": cts, "flags": {}}
        if not chiavi or not commit:
            return risultato
        testo = self._testo_config(commit)
        for chiave in chiavi:
            cache = (commit, chiave)
            if cache not in self._valori:
                self._valori[cache] = yaml_scalare(testo, chiave)
            risultato["flags"][chiave] = self._valori[cache]
        return risultato


_RX_YAML_CHIAVE = re.compile(r"^(\s*)([A-Za-z_][\w.-]*):\s*(.*)$")


def yaml_scalare(testo, chiave_punteggiata):
    """Lettore YAML MINIMALE, stdlib-only: mappature annidate + scalari.

    Le liste non servono (leggiamo flag booleani) e vengono ignorate. Ritorna
    None se la chiave e' assente: assenza di chiave non e' `false` — distinguerle
    e' il punto, perche' un trigger senza chiave non e' un trigger spento.
    """
    attesa = chiave_punteggiata.split(".")
    pila = []
    for riga in testo.splitlines():
        if not riga.strip() or riga.lstrip().startswith("#"):
            continue
        m = _RX_YAML_CHIAVE.match(riga)
        if not m:
            continue
        indent, chiave, resto = len(m.group(1)), m.group(2), m.group(3)
        while pila and pila[-1][0] >= indent:
            pila.pop()
        pila.append((indent, chiave))
        if [k for _, k in pila] == attesa:
            return _scalare(resto)
    return None


def _scalare(grezzo):
    v = grezzo.strip()
    if " #" in v:
        v = v.split(" #", 1)[0].strip()
    if v.startswith("#") or v == "":
        return None
    if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    basso = v.lower()
    if basso in ("true", "yes", "on"):
        return True
    if basso in ("false", "no", "off"):
        return False
    if basso in ("null", "~"):
        return None
    try:
        return int(v)
    except ValueError:
        return v


# ─── Primitiva 5: finestra + esclusioni ───────────────────────────────────────

def _ts_confrontabile(ts):
    """Chiave di ordinamento stabile per ISO8601 con offset o Z."""
    if not ts:
        return ""
    t = ts.strip()
    if t.endswith("Z"):
        return t[:-1] + "+00:00"
    if re.search(r"[+-]\d{2}:\d{2}$", t):
        try:
            dt = datetime.datetime.fromisoformat(t).astimezone(datetime.timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "+00:00"
        except ValueError:
            return t
    return t


def nella_finestra(ts, giorno_esclusivo):
    """AC6 — True se `ts` cade DOPO la giornata di authoring (esclusa)."""
    if not ts:
        return False
    return ts[:10] > giorno_esclusivo


def sessione_aperta(principale):
    """True se la sessione e' ANCORA IN CORSO — e allora non si misura.

    `PT._check_session_open` guarda il main JSONL (env var + mtime < 60s), ma con
    il walker fan-in di EP-062 i sub-agent scrivono in
    `<session-uuid>/subagents/`: la sessione che sta girando l'osservatore ha il
    main fermo e i sub freschi. Guardare solo il main lascia entrare nel
    campione i tocchi dello strumento di misura in funzione.
    """
    aperta, _ = PT._check_session_open(principale)
    if aperta:
        return True
    cartella_sub = principale.parent / principale.stem / "subagents"
    if not cartella_sub.is_dir():
        return False
    for f in cartella_sub.glob("agent-*.jsonl"):
        try:
            if time.time() - f.stat().st_mtime < 60:
                return True
        except OSError:
            continue
    return False


def cartella_progetto(radice_repo):
    """Cartella dei transcript per questo repo (mangling di Claude Code)."""
    mangled = str(radice_repo).replace("/", "-").replace(".", "-")
    return pathlib.Path.home() / ".claude" / "projects" / mangled


def radice_repo_corrente():
    try:
        p = subprocess.run(("git", "-C", str(HERE), "rev-parse", "--show-toplevel"),
                           capture_output=True, text=True, timeout=20)
        if p.returncode == 0 and p.stdout.strip():
            return pathlib.Path(p.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return HERE.parent.parent


# ─── Scansione ────────────────────────────────────────────────────────────────

def _tool_use(rec):
    contenuto = (rec.get("message") or {}).get("content")
    if not isinstance(contenuto, list):
        return
    for item in contenuto:
        if isinstance(item, dict) and item.get("type") == "tool_use":
            yield item.get("name"), (item.get("input") or {})


def scansiona_transcript(percorso, attribuzione, radice_repo, giorno_esclusivo):
    """Legge UN file JSONL e ritorna (accessi, unita_mutate, dispatch,
    invocazioni, contatori).

    Non emette verdetti e non scrive niente: read-only sulla telemetria (AC17).
    """
    accessi, dispatch, invocazioni = [], [], []
    unita_mutate = set()
    cnt = collections.Counter()
    esecutrice = None
    visti = set()

    try:
        fh = open(percorso, encoding="utf-8", errors="replace")
    except OSError:
        cnt["file_illeggibile"] += 1
        return accessi, unita_mutate, dispatch, invocazioni, cnt, esecutrice

    with fh:
        for riga in fh:
            riga = riga.strip()
            if not riga:
                continue
            try:
                rec = json.loads(riga)
            except json.JSONDecodeError:
                cnt["righe_malformate"] += 1
                continue
            if rec.get("type") != "assistant":
                continue
            if esecutrice is None and rec.get("attributionAgent"):
                esecutrice = "agents/%s" % rec["attributionAgent"]
            ts = rec.get("timestamp") or ""
            in_finestra = nella_finestra(ts, giorno_esclusivo)
            uuid_rec = rec.get("uuid")

            for nome_tool, inp in _tool_use(rec):
                # Le mutazioni si raccolgono SEMPRE (anche fuori finestra): sono
                # la precondizione della correzione di canale, non un accesso.
                for p in mutazioni(nome_tool, inp, radice_repo):
                    info = risolvi_unita(p, radice_repo)
                    if info:
                        unita_mutate.add(info["unita"])
                        cnt["mutazioni"] += 1

                if not in_finestra:
                    cnt["fuori_finestra"] += 1
                    continue

                cnt["bash_dir_scan_ignorati"] += conta_dir_scan(nome_tool, inp)

                if nome_tool == "Agent":
                    tipo = inp.get("subagent_type")
                    if tipo:
                        dispatch.append({"unita": "agents/%s" % tipo, "ts": ts,
                                         "attribuzione": attribuzione})
                        cnt["dispatch"] += 1
                    continue

                if nome_tool == "Skill":
                    nome = inp.get("skill")
                    if nome:
                        invocazioni.append({"unita": "commands/%s" % nome, "ts": ts,
                                            "attribuzione": attribuzione})
                        cnt["invocazioni_skill"] += 1
                    continue

                for acc in canali_read_like(nome_tool, inp, radice_repo):
                    info = risolvi_unita(acc["path"], radice_repo)
                    if info is None:
                        cnt["accessi_non_unita"] += 1
                        continue
                    chiave = (uuid_rec, info["unita"], acc["path"], acc["canale"])
                    if chiave in visti:
                        continue
                    visti.add(chiave)
                    ancorante, motivo = asse_ancorante(info["tipo_unita"], info["asse"])
                    accessi.append({
                        "unita": info["unita"],
                        "tipo_unita": info["tipo_unita"],
                        "adapter": info.get("adapter"),
                        "path": acc["path"],
                        "asse": info["asse"],
                        "asse_ancorante": ancorante,
                        "asse_non_ancorante_motivo": motivo,
                        "canale": acc["canale"],
                        "ts": ts,
                        "evidenza": acc["evidenza"],
                    })
                    cnt["canale_%s" % acc["canale"]] += 1
                    if not ancorante:
                        cnt["asse_non_ancorante"] += 1

                if nome_tool == "Bash":
                    for token in _RX_TOKEN_MD.findall(inp.get("command") or ""):
                        if token.startswith("/") and normalizza_path(token, radice_repo) is None:
                            cnt["fuori_repo"] += 1
                            break

    return accessi, unita_mutate, dispatch, invocazioni, cnt, esecutrice


def raccogli(radice_repo, cartella, giorno_esclusivo):
    """Fan-in su tutte le sessioni del progetto + i loro sub-agent.

    Il walker e' quello riparato da EP-062 (`collect_jsonl_files`): omettere i
    file `<session-uuid>/subagents/agent-*.jsonl` significherebbe perdere ~60%
    dell'attivita' della flotta IN SILENZIO — la classe di `isSidechain`.
    """
    supportate, fonte_guard = versioni_cc_supportate()
    if fonte_guard == "fallback-locale":
        sys.stderr.write(
            "WARNING: SUPPORTED_CC_VERSIONS non raggiungibile da "
            "harvest-session-tokens.py; uso la copia locale di fallback. "
            "Lo schema-guard di EP-062 non e' piu' a fonte unica.\n")

    esito = {
        "mandati": [], "record": [], "dispatch": [], "invocazioni_skill": [],
        "contatori": collections.Counter(), "sessioni": [],
        "cc_versions": collections.Counter(), "non_supportate": set(),
        "schema_guard_fonte": fonte_guard,
    }
    # `config` viene valorizzato PRIMA di qualunque uscita anticipata (TSK-655).
    # Il difetto riparato qui: `raccogli()` usciva al controllo `is_dir()` senza
    # aver messo `esito["config"]`, e `main()` lo leggeva senza guardia —
    # `KeyError: 'config'`, exit 1, su TUTTI E QUATTRO i sottocomandi. La sede
    # del rimedio e' questa e non una guardia in `main()`: con la costruzione
    # sopra il controllo esiste UN SOLO punto di uscita in cui la chiave manchi,
    # cioe' nessuno, e un'altra uscita anticipata aggiunta domani non puo'
    # rianimare il difetto. Costo: un `git log` sul solo `factory.config.yaml`
    # anche quando la telemetria e' assente.
    config = ConfigAlTs(radice_repo)
    esito["config"] = config
    esito["config_errore"] = config.errore

    if not cartella.is_dir():
        sys.stderr.write("WARNING: cartella transcript assente: %s — "
                         "osservabilita' zero, non conformita' zero.\n" % cartella)
        # Telemetria assente NON e' un errore: e' ASSENZA DI INFORMAZIONE,
        # esattamente come `non osservabile` (US-270 §Business Rules + AC7).
        # L'exit != 0 su un errore di infrastruttura e' corretto; l'exit != 0
        # sull'assenza di dati direbbe «rotto» dove il fatto e' «non ho visto»,
        # e uno strumento che non sa dire «non ho visto» senza esplodere viola
        # l'invariante di lettura che lui stesso stampa.
        esito["telemetria_assente"] = {
            "assente": True,
            "verdetto": "non osservabile",
            "ragione": "telemetria assente: cartella dei transcript non trovata (%s)"
                       % cartella,
            "cartella": str(cartella),
            "exit": EXIT_OK,
            "lettura": VERDETTI_SIGNIFICATO["non osservabile"],
        }
        return esito

    slugs = slugs_flotta(radice_repo)

    for principale in sorted(cartella.glob("*.jsonl")):
        # Pre-filtro sulla mtime: se la sessione non e' stata scritta dopo la
        # giornata di authoring, nessun suo record puo' esserlo. Il filtro
        # autorevole resta quello per-record.
        try:
            mtime = datetime.datetime.fromtimestamp(
                principale.stat().st_mtime, datetime.timezone.utc)
        except OSError:
            continue
        if mtime.strftime("%Y-%m-%d") <= giorno_esclusivo:
            esito["contatori"]["sessioni_fuori_finestra"] += 1
            continue

        # La sessione ancora aperta e' lo strumento di misura in funzione: i suoi
        # tocchi sono auto-referenziali per costruzione (R-SAA-8 di EP-061).
        if sessione_aperta(principale):
            esito["contatori"]["sessioni_aperte_escluse"] += 1
            continue

        versione = PT._detect_cc_version(str(principale))
        esito["cc_versions"][versione or "sconosciuta"] += 1
        if versione is None or versione not in supportate:
            esito["non_supportate"].add(versione or "sconosciuta")
            sys.stderr.write(
                "WARNING: versione Claude Code %s non nell'insieme supportato "
                "(%s): parsing in modalita' degradata su %s\n"
                % (versione or "assente", fonte_guard, principale.name))

        esito["sessioni"].append(principale.stem)
        for percorso, scope in PT._collect_files(principale, None):
            attribuzione = "subagent" if scope == "subagent" else "main"
            rel = str(percorso.relative_to(cartella)) if hasattr(percorso, "relative_to") else str(percorso)

            accessi, mutate, dispatch, invocazioni, cnt, esecutrice = scansiona_transcript(
                percorso, attribuzione, radice_repo, giorno_esclusivo)
            esito["contatori"].update(cnt)
            # Il mandato si classifica DOPO la scansione: l'unita' esecutrice
            # (`attributionAgent`) e' il discriminante fra il moderatore che
            # esegue il protocollo e il partecipante che delibera.
            info_mandato = mandato(percorso, esecutrice, slugs)

            voce = dict(info_mandato)
            voce.update({
                "transcript": rel, "sessione": principale.stem,
                "attribuzione": attribuzione,
                "unita_esecutrice": esecutrice,
                "unita_mutate": sorted(mutate),
                "accessi": len(accessi),
            })
            esito["mandati"].append(voce)
            esito["contatori"]["mandato_%s" % info_mandato["mandato"]] += 1
            esito["contatori"]["regola_%s" % info_mandato["mandato_regola"]] += 1

            if info_mandato["auto_referenziale"]:
                # AC6: i tocchi auto-referenziali NON compaiono nell'output.
                esito["contatori"]["esclusi_auto_referenziali"] += len(accessi)
                esito["contatori"]["transcript_auto_referenziali"] += 1
                continue

            esito["dispatch"].extend(dispatch)
            esito["invocazioni_skill"].extend(invocazioni)
            for acc in accessi:
                classe, regola = mandato_effettivo(
                    info_mandato["mandato"], info_mandato["mandato_regola"],
                    acc["unita"], mutate)
                trigger = TRIGGER_CONDIZIONALI.get(acc["unita"], [])
                record = dict(acc)
                record.update({
                    "mandato": classe,
                    "mandato_regola": regola,
                    "mandato_sessione": info_mandato["mandato"],
                    "unita_esecutrice": esecutrice,
                    "config_at_ts": config.flag(acc["ts"], trigger),
                    "sessione": principale.stem,
                    "transcript": rel,
                    "attribuzione": attribuzione,
                })
                esito["record"].append(record)
                esito["contatori"]["mandato_effettivo_%s" % classe] += 1

    esito["config_errore"] = config.errore
    esito["record"].sort(key=lambda r: (_ts_confrontabile(r["ts"]), r["unita"]))
    esito["mandati"].sort(key=lambda m: (_ts_confrontabile(m.get("ts") or ""), m["transcript"]))
    return esito


INVARIANTE_DI_LETTURA = (
    "Il layer misura l'ACCESSO, non l'ONORAGGIO. Nessuno dei due canali e' "
    "ground truth: Read sottostima i corpi iniettati, il path-match su Bash "
    "sovrastima contando grep/wc come letture. I verdetti si leggono cosi': "
    "divergente = problema reale; invariato = poca informazione, perche' "
    "l'accesso non e' l'uso; non osservabile = nessuna informazione, in nessuna "
    "direzione. Mai «la flotta e' conforme»."
)

LIMITI_DICHIARATI = [
    "A-49 / dissenso 6 EP-065: le quattro raffinature di specifica implementate "
    "qui hanno mosso il conteggio tutte nella stessa direzione (meno reperti "
    "contro EP-060) e nessuna ha peggiorato il verdetto di una singola unita'. "
    "Questo file non e' una calibrazione indipendente.",
    "Il default di classificazione e' `citazione` (R-CIT-DEFAULT): riduce le "
    "esecuzioni osservate, quindi le divergenze possibili. Il conteggio per "
    "regola sta in meta.regole per renderlo ispezionabile.",
    "`grep -rn <x> .claude/skills/` legge un'intera cartella e non viene "
    "attribuito a nessuna unita' (contato in bash_dir_scan_ignorati): "
    "sottostima dichiarata, preferita a gonfiare ogni `invariato`.",
    "Gli accessi ai file delle factory derivate (fuori dalla radice del repo) "
    "non sono accessi a queste unita': contati in `fuori_repo`.",
    "L'asse corpo delle unita'-agente e' cieco per costruzione (AC5); le "
    "skill/comandi slash-invocati hanno lo stesso problema ma la regola NON e' "
    "stata estesa — allargare l'inosservabile assolve (decisione confermata in "
    "TSK-648: non estesa).",
    "TSK-648, scelta di criterio che ASSOLVE: l'evidenza di esecuzione richiede "
    "il nome in POSIZIONE DI DIRETTIVA. La menzione semplice produceva 3 "
    "`divergente` (fe-dev, factory-bootstrap, parallel-scheduling) — gli stessi "
    "tre falsi positivi di PA-30. Il criterio largo e quello propagato girano a "
    "ogni run e stanno in `criterio_largo` / `criterio_propagato`: sotto "
    "propagazione a un hop `fe-dev` e `parallel-scheduling` sarebbero "
    "`divergente`, e quel numero e' dentro l'output, non fuori.",
    "TSK-648, quattro difetti trovati sul PROPRIO output prima di pubblicarlo, "
    "due nella direzione che AGGRAVA: (1) la giornata di authoring non era "
    "esclusa per i MANDATI, solo per i tool_use — falsi `divergente`; (2) i "
    "trigger di `dev-protocol` erano valutati in AND a livello di unita', il che "
    "CANCELLAVA l'unico `divergente` forte (i flag per-foglia sono diversi); "
    "(3) il censimento collassava gli 8 slug condivisi fra comando e agente e "
    "dichiarava irraggiungibili 4 unita' vive; (4) il censimento contava come "
    "arco entrante le menzioni contenute in QUESTO file, tenendo in vita "
    "`test-healing-protocol` (446 righe) perche' lo strumento la nominava.",
    "Il censimento decide la classe `irraggiungibile` sul solo tier DISPATCH. "
    "`test-healing-protocol` ha un arco di CATALOGO (`CAPABILITIES.md`) e 50 "
    "documentali: la scelta di tier sposta 446 righe dentro o fuori dalla classe "
    "su cui US-277 cancella, ed e' dichiarata perche' non sia invisibile.",
]


# ══════════════════════════════════════════════════════════════════════════════
# TSK-648 — I TRE SOTTOCOMANDI, UN SOLO JSON
# ══════════════════════════════════════════════════════════════════════════════

# AC7 — invariante di lettura, VERBATIM e non riformulabile. Le tre stringhe sono
# cablate qui e stampate da tutti i sottocomandi: il verdetto non viaggia mai
# senza il proprio significato.
VERDETTI_SIGNIFICATO = {
    "divergente": "PROBLEMA REALE (zero accessi su ENTRAMBI i canali)",
    "invariato": "POCA INFORMAZIONE, perche' l'accesso non e' l'uso",
    "non osservabile": "NESSUNA INFORMAZIONE, IN NESSUNA DIREZIONE",
}

# DIVIETO, non descrizione. La frase «la flotta e' conforme» (e ogni variante:
# «conformita' della flotta», «flotta a norma», «tutto onorato») NON e'
# producibile da questo strumento, e non lo e' per una ragione strutturale: il
# differ misura l'ACCESSO, non l'ONORAGGIO. `invariato` e' poca informazione,
# `non osservabile` e' nessuna informazione ⇒ nessuna combinazione di verdetti
# sostiene un enunciato di conformita'. Un `0/2/8` si legge «lo strumento non ha
# visto», MAI «la flotta e' conforme» (AC7 + AC8, clausola obbligatoria di A-41).
DIVIETO_ENUNCIATO_DI_CONFORMITA = (
    "VIETATO dedurre un enunciato di conformita' della flotta da questi "
    "verdetti: il differ misura l'ACCESSO, non l'ONORAGGIO. `invariato` e' poca "
    "informazione, `non osservabile` e' nessuna informazione. Un X/Y basso si "
    "legge «lo strumento non ha visto»."
)

# AC14 — il puntatore all'errata in loco, nominato NELL'OUTPUT del censimento
# «cosi' la correzione e' raggiungibile da uno strumento, non solo da un
# documento che si chiude» (A-46).
PUNTATORE_ERRATA = "ADR-EP060-002 §Contesto"

# AC13 / A-37 — la riga che `complexity-budget-check` deve stampare nel proprio
# output. Lo stato reale della riga nel file del check e' MISURATO, non assunto
# (`stato_a37()`): questo strumento non modifica il check e non lo cancella —
# la cancellazione richiede la question Q-005 (TSK-647), «porre fine a un
# controllo istituito da un ADR `accepted`» non e' dentro l'autorita' di un agente.
RIGA_SUPERSEDED_BY = "superseded_by: tools/fleet-observer/observe.py --load"
CHECK_SUPERSEDUTO = ".claude/skills/complexity-budget-check.md"

# ─── Registro della campagna EP-060 — DICHIARATO, non misurato ────────────────
# Le baseline sono SHA, non numeri in prosa: «un numero in prosa drifta» (A-23).
# `righe_prima_dichiarate` viaggia accanto alla misura da `git show` proprio
# perche' un disaccordo fra le due e' un reperto (la prosa ha driftato o lo SHA
# e' sbagliato), non un dettaglio da sanare in silenzio.
CAMPAGNA_EP060 = [
    {"unita": "skills/dev-protocol", "path": ".claude/skills/dev-protocol.md",
     "baseline_sha": "94c1e95", "righe_prima_dichiarate": 519,
     "righe_dopo_dichiarate": 291, "sha_fonte": "registro TR-e5b81d64"},
    {"unita": "skills/parallel-scheduling", "path": ".claude/skills/parallel-scheduling.md",
     "baseline_sha": "94c1e95", "righe_prima_dichiarate": 624,
     "righe_dopo_dichiarate": 371, "sha_fonte": "registro TR-e5b81d64"},
    {"unita": "commands/factory-bootstrap", "path": ".claude/commands/factory-bootstrap.md",
     "baseline_sha": "6857314", "righe_prima_dichiarate": 583,
     "righe_dopo_dichiarate": 175, "sha_fonte": "registro TR-e5b81d64"},
    {"unita": "skills/tavola-rotonda-protocol", "path": ".claude/skills/tavola-rotonda-protocol.md",
     "baseline_sha": "6dba092", "righe_prima_dichiarate": 799,
     "righe_dopo_dichiarate": 220, "sha_fonte": "registro TR-e5b81d64"},
    {"unita": "skills/lint-checks", "path": ".claude/skills/lint-checks.md",
     "baseline_sha": "006b001", "righe_prima_dichiarate": 2196,
     "righe_dopo_dichiarate": 119, "sha_fonte": "registro TR-e5b81d64"},
    {"unita": "skills/functional-oracle-protocol", "path": ".claude/skills/functional-oracle-protocol.md",
     "baseline_sha": "1fbaa84", "righe_prima_dichiarate": 962,
     "righe_dopo_dichiarate": 342, "sha_fonte": "registro TR-e5b81d64"},
    # Le quattro righe «da completare» del registro, RICAVATE in authoring di
    # TSK-648 con `git log --follow --format='%h %ad' -- <path>` sui commit della
    # campagna 2026-09-04 e `git show <sha>:<path> | wc -l`. La baseline e' il
    # commit IMMEDIATAMENTE PRECEDENTE al commit di refactor del path.
    {"unita": "agents/fe-dev", "path": ".claude/agents/fe-dev.md",
     "baseline_sha": "1f5d7ca", "righe_prima_dichiarate": 410,
     "righe_dopo_dichiarate": 94,
     "sha_fonte": "ricavato TSK-648: predecessore di ba90e31 (refactor fe-dev 410->94)"},
    {"unita": "skills/prototype-generation-protocol", "path": ".claude/skills/prototype-generation-protocol.md",
     "baseline_sha": "ba90e31", "righe_prima_dichiarate": 637,
     "righe_dopo_dichiarate": 245,
     "sha_fonte": "ricavato TSK-648: predecessore di 08fad8f (refactor 637->245)"},
    {"unita": "commands/prototype", "path": ".claude/commands/prototype.md",
     "baseline_sha": "87277bd", "righe_prima_dichiarate": 325,
     "righe_dopo_dichiarate": 210,
     "sha_fonte": "ricavato TSK-648: predecessore di af6ba6c (refactor 325->210)"},
    {"unita": "agents/tavola-rotonda-moderatore", "path": ".claude/agents/tavola-rotonda-moderatore.md",
     "baseline_sha": "6857314", "righe_prima_dichiarate": 464,
     "righe_dopo_dichiarate": 371,
     "sha_fonte": "ricavato TSK-648: predecessore di 294c5fd (refactor 464->371)"},
    # A-30: il NO-REFACTOR deliberato e motivato NON va contato fra i reject —
    # va A CREDITO del protocollo, «la capability sa dire di no». E' l'unico dato
    # della sessione che difende EP-060, messo a verbale dal Critico.
    {"unita": "agents/prototype-generator", "path": ".claude/agents/prototype-generator.md",
     "baseline_sha": "c0cb7d4", "righe_prima_dichiarate": 313,
     "righe_dopo_dichiarate": 313, "no_refactor": True,
     "sha_fonte": "registro TR-e5b81d64 (0/0, no-refactor motivato)"},
]

# Obbligazione DICHIARATA per unita' refattorizzata: la Famiglia 2 di
# `.claude/skills/references/refactor/protocollo-test-equivalenza.md` §6 —
# «lettura della foglia prima dell'azione». Il refactor di EP-060 sposta
# contenuto in foglia e lascia nel corpo un trigger: l'obbligazione e' che sotto
# esecuzione la foglia venga APERTA. L'asse obbligato e' quindi `foglia` per
# tutte le unita' che hanno prodotto foglie; un'unita' senza foglie non ha
# obbligazione dichiarata (e' il caso del no-refactor).
ASSE_OBBLIGATO = "foglia"
OBBLIGAZIONE_DESCRIZIONE = (
    "Famiglia 2 (protocollo-test-equivalenza.md §6): la foglia va LETTA prima "
    "dell'azione. Il corpo e' stato ridotto a un trigger che vi punta."
)


# ─── Utilita' di misura (righe, char, token stimati) ──────────────────────────

# Stima, NON tokenizzazione: `byte // 4`. E' la stessa approssimazione con cui
# sono stati prodotti i numeri del registro — verificabile ALLA BASELINE DEL
# 2026-09-21, PRIMA del taglio di TSK-651: CLAUDE.md misurava 49.924 char, e
# 49.924 // 4 = 12.481, che e' esattamente il valore dichiarato in EP-065 §Delta
# di massa netto per `CLAUDE.md`. Oggi il file e' piu' piccolo (TSK-651 ne ha
# cancellato 25.236 byte di changelog duplicato): il 49.924 resta la VERIFICA
# DEL METODO su un numero noto, non la misura corrente — quella la stampa
# `--load`. Dichiarata qui perche' un lettore
# deve sapere che sta leggendo una stima riproducibile, non un conteggio di un
# tokenizer che questo strumento non ha (zero dipendenze esterne, AC17).
def stima_token(char):
    return char // 4


def misura_file(percorso):
    """(righe, byte) di un file, (0, 0) se assente/illeggibile. Read-only.

    BYTE, come `wc -c`, non code point: e' l'unita' con cui sono stati prodotti
    i numeri del registro, e la differenza non e' cosmetica — `PATTERN.md` ha
    352.907 code point e 358.955 byte, perche' «§» e «—» sono multibyte. Contare
    code point avrebbe reso il rapporto 7,14x invece del 7,2x dichiarato e la
    stima di `CLAUDE.md` 12.359 token invece dei 12.481 del registro: due numeri
    che non si potevano piu' confrontare con la baseline.
    """
    try:
        dati = percorso.read_bytes()
    except OSError:
        return 0, 0
    return len(dati.decode("utf-8", errors="replace").splitlines()), len(dati)


def righe_a_commit(radice_repo, sha, path_rel):
    """`git show <sha>:<path> | wc -l`. None se non recuperabile (read-only)."""
    try:
        p = subprocess.run(("git", "-C", str(radice_repo), "show", "%s:%s" % (sha, path_rel)),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return len(p.stdout.splitlines())


def _percorsi_unita(radice_repo):
    """Tutti i file `.md` sotto `.claude/{agents,skills,commands}` (anche foglie)."""
    for tipo in TIPI_UNITA_FLOTTA:
        cartella = radice_repo / ".claude" / tipo
        if not cartella.is_dir():
            continue
        for f in sorted(cartella.rglob("*.md")):
            yield f


def inventario_flotta(radice_repo):
    """Inventario DETERMINISTICO della flotta, costruito con il solo resolver del
    layer di parsing (nessuna euristica nuova, A-6: si riusa, non si copia).

    Ritorna (corpi, foglie): `corpi` = {unita: {path, righe, char, descrizione...}},
    `foglie` = {unita: [ {path, righe, char} ]}.
    """
    corpi, foglie = {}, collections.defaultdict(list)
    for f in _percorsi_unita(radice_repo):
        rel = str(f.relative_to(radice_repo))
        info = risolvi_unita(rel, radice_repo)
        if not info or not info.get("unita"):
            continue
        righe, char = misura_file(f)
        voce = {"path": rel, "righe": righe, "char": char}
        if info["asse"] == "corpo":
            voce["descrizione_char"] = len((frontmatter_descrizione(f) or "").encode("utf-8"))
            voce["tipo_unita"] = info["tipo_unita"]
            corpi[info["unita"]] = voce
        else:
            foglie[info["unita"]].append(voce)
    for lista in foglie.values():
        lista.sort(key=lambda v: v["path"])
    return corpi, dict(foglie)


# ─── Inventario delle foglie CONGELATO (TSK-657 / US-270 AC15) ───────────────

# Perche' esiste questo ingresso. Le tre fixture di regressione di A-49 portano
# la telemetria congelata, ma l'inventario delle foglie veniva letto dal
# FILESYSTEM REALE al momento dell'esecuzione: il verdetto della fixture
# dipendeva quindi dallo stato del repo di oggi. Il 2026-09-21 e' accaduto: il
# rimedio di TSK-650 ha cancellato `analytics-instrumentation.md` e la fixture
# `a49-dev-protocol` e' passata da `divergente` (exit 5) a `non osservabile`
# (exit 0) per una ragione che non c'entra nulla con l'osservatore. TSK-649 lo
# aveva previsto per iscritto. **Una fixture di regressione il cui verdetto
# dipende dallo stato corrente del filesystem non e' una fixture.**
#
# AMBITO DELIBERATAMENTE STRETTO: lo snapshot sostituisce l'inventario delle
# foglie SOLO nei verdetti del differ (l'asse dell'obbligazione). `censimento`,
# `--load` e l'asserzione A-23(i) continuano a misurare il filesystem REALE,
# perche' la loro domanda E' «com'e' il repo adesso». Un run con lo snapshot
# attivo lo DICHIARA in `meta.foglie_snapshot`, in JSON e in testo: un output
# congelato che tacesse si leggerebbe come una misura di oggi.

def carica_foglie_snapshot(percorso):
    """Legge un inventario di foglie congelato. Ritorna (foglie, meta).

    Formato (JSON): `{"foglie": {<unita>: [{"path", "righe", "char"}, ...]}}`,
    con i campi di provenienza accanto (`catturato_il`, `fonte`, `provenienza`).
    E' accettata anche la mappatura nuda `{<unita>: [...]}`.
    """
    percorso = pathlib.Path(percorso)
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    involucro = dati.get("foglie") if isinstance(dati, dict) else None
    grezzo = involucro if isinstance(involucro, dict) else dati
    if not isinstance(grezzo, dict):
        raise ValueError("snapshot foglie malformato: atteso un oggetto, "
                         "trovato %s" % type(grezzo).__name__)
    foglie = {}
    for unita, lista in grezzo.items():
        voci = []
        for v in lista or []:
            # `ValueError` e non un'eccezione qualunque: `main()` cattura questa
            # e esce 1 fail-loud. Un `TypeError` sfuggirebbe come traceback, che
            # e' il modo di fallire che TSK-655 ha appena chiuso.
            if not isinstance(v, dict) or "path" not in v:
                raise ValueError("voce di foglia malformata in %s: attesa una "
                                 "mappatura con `path`, trovato %r" % (unita, v))
            voci.append({"path": v["path"], "righe": int(v.get("righe", 0)),
                         "char": int(v.get("char", 0))})
        foglie[unita] = sorted(voci, key=lambda v: v["path"])
    meta = {
        "path": str(percorso),
        "unita": len(foglie),
        "foglie": sum(len(v) for v in foglie.values()),
        "catturato_il": (dati.get("catturato_il") if isinstance(dati, dict) else None),
        "fonte": (dati.get("fonte") if isinstance(dati, dict) else None),
        "provenienza": (dati.get("provenienza") if isinstance(dati, dict) else None),
        "ambito": ("sostituisce l'inventario delle foglie SOLO nei verdetti del "
                   "differ; censimento, --load e l'asserzione A-23(i) restano sul "
                   "filesystem reale"),
        "lettura": ("run con inventario delle foglie CONGELATO: i verdetti del "
                    "differ NON misurano il repo di oggi, misurano la telemetria "
                    "congelata contro l'inventario congelato. E' l'ingresso delle "
                    "fixture di regressione di A-49, non una modalita' di misura."),
    }
    return foglie, meta


_RX_DESCR = re.compile(r"^description:\s*(.*)$", re.MULTILINE)


def frontmatter_descrizione(percorso):
    """Campo `description:` del frontmatter — e' la parte ALWAYS-ON di un'unita'
    nell'adapter Claude: il corpo si carica on-demand, la description no."""
    try:
        testo = percorso.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not testo.startswith("---"):
        return None
    fine = testo.find("\n---", 3)
    testa = testo[:fine if fine > 0 else 4000]
    m = _RX_DESCR.search(testa)
    if not m:
        return None
    valore = m.group(1).strip()
    if valore in (">", ">-", "|", "|-"):
        # blocco multi-riga: raccoglie le righe indentate successive
        righe = testa[m.end():].splitlines()
        pezzi = []
        for r in righe:
            if r.strip() and not r.startswith((" ", "\t")):
                break
            pezzi.append(r.strip())
        valore = " ".join(p for p in pezzi if p)
    return valore

# ─── Sottocomando 1: `--differ` — le unita' obbligate vengono raggiunte? ──────

# Verbi che rendono un nome una DIRETTIVA e non una menzione. Senza questo
# filtro il differ conta come «esecuzione di X» ogni mandato che nomina X per
# qualunque ragione — incluso «refattorizza X» — ed e' l'errore che A-43 nomina:
# «ho misurato la popolarita' del file, non l'esecuzione del protocollo».
_DIRETTIVE = (r"segu(?:endo|i|ito)|esegu\w+|consum\w+|invoc\w+|lanci\w+|avvi\w+|"
              r"attiv\w+|gir\w+|usa\b|usando|utilizz\w+|applic\w+|second\w+|"
              r"richiam\w+|rispett\w+|onor\w+")

# Puntatori nel CORPO di un'unita' verso un'altra unita': «Vedi `dev-protocol`
# (skill) per la procedura completa» e' il puntatore con cui i cinque dev-agent
# dichiarano quale protocollo eseguono. Serve alla propagazione a UN HOP, che
# gira come criterio ALTERNATIVO e non nel path del verdetto: il dispatch di
# `be-dev` come esecuzione di `dev-protocol` e' la relazione che A-42 ha
# misurato dall'altro lato, ma resta un'inferenza sul grafo, non un'osservazione.
# Piu' larga della direttiva di mandato (ammette «Vedi»/«via»/«secondo»), piu'
# stretta della menzione nuda: una menzione nuda in un corpo non e' un puntatore.
_PUNTATORI_CORPO = (r"vedi|vd\.|leggi|consulta|segu(?:endo|i|ito)|esegu\w+|invoc\w+|"
                    r"usa\b|usando|utilizz\w+|applic\w+|second\w+|delega\w*|"
                    r"richiam\w+|attiv\w+|via|tramite|gir\w+|coordina\w*")
_RX_NOMI_UNITA = r"skill|protocoll\w+|procedur\w+|comand\w+|agent\w+|sub-agent"

# Regex ALTERNATE, compilate una volta per run: una passata per testo invece di
# una per slug. La versione per-slug faceva 140 search per ogni mandato e per
# ogni corpo (~50.000 search per run) e portava il run a un minuto: uno
# strumento che nessuno aspetta e' uno strumento che nessuno esegue.
_cache_alternanza = {}


def _alternanza(slugs, genere):
    chiave = (genere, tuple(sorted(slugs.items())))
    if chiave in _cache_alternanza:
        return _cache_alternanza[chiave]
    mappa = collections.defaultdict(list)
    for unita, slug in slugs.items():
        mappa[slug.lower()].append(unita)
    alt = "|".join(re.escape(s) for s in sorted(mappa, key=len, reverse=True))
    if genere == "menzione":
        rx = [re.compile(r"(?<![\w-])/?(%s)(?![\w-])" % alt, re.IGNORECASE)]
    elif genere == "direttiva":
        rx = [re.compile(r"(?:%s)\b[^\n]{0,44}?(?<![\w-])/?(%s)(?![\w-])"
                         % (_DIRETTIVE, alt), re.IGNORECASE),
              re.compile(r"(?<![\w-])/(%s)(?![\w-])" % alt, re.IGNORECASE)]
    else:  # puntatore nel corpo di un'unita'
        rx = [re.compile(r"(?:%s)\b[^\n]{0,44}?(?<![\w-])/?(%s)(?![\w-])"
                         % (_PUNTATORI_CORPO, alt), re.IGNORECASE),
              re.compile(r"(?:%s)\s+[`\'\"]?/?(%s)(?![\w-])"
                         % (_RX_NOMI_UNITA, alt), re.IGNORECASE)]
    _cache_alternanza[chiave] = (rx, dict(mappa))
    return _cache_alternanza[chiave]


def _cerca(testo, slugs, genere):
    if not testo or not slugs:
        return []
    regex, mappa = _alternanza(slugs, genere)
    trovate = set()
    for rx in regex:
        for m in rx.finditer(testo):
            trovate.update(mappa.get(m.group(1).lower(), ()))
    return sorted(trovate)


def unita_menzionate(testo, slugs):
    r"""Unita' NOMINATE nel testo, in qualunque posizione (criterio LARGO).

    Il lookahead `(?![\w-])` e' cio' che impedisce a `prototype` di matchare
    dentro `prototype-generation-protocol` e a `lint-checks` dentro
    `lint-checks-governance`: senza di esso il differ attribuirebbe l'esecuzione
    di un'unita' a un'altra, che e' la classe del regex col gruppo di cattura
    sbagliato (A-32).
    """
    return _cerca(testo, slugs, "menzione")


def unita_nominate(testo, slugs):
    """Primitiva 1d (TSK-648) — unita' nominate IN POSIZIONE DI DIRETTIVA.

    E' il criterio di evidenza di esecuzione di A-41 alla lettera: la tripla del
    solo `divergente` misurato poggia su «9 mandati di esecuzione distinti
    (`Implementa/Consuma TSK-… seguendo la skill dev-protocol`)» — il nome in
    posizione di direttiva, non il nome.

    DIREZIONE DELLA SCELTA, dichiarata (A-49): questo criterio e' PIU' STRETTO
    della semplice menzione, quindi produce MENO divergenze — la direzione che
    assolve. La prima versione di questo file usava la menzione semplice e
    produceva 3 `divergente` (`fe-dev`, `factory-bootstrap`,
    `parallel-scheduling`): erano gli stessi tre falsi positivi che PA-30 ha
    registrato e che A-41 ha risolto all'unanimita', prodotti qui una seconda
    volta da un'implementazione indipendente. Il criterio largo NON viene
    nascosto: gira a ogni run e sta in `criterio_largo` di ogni verdetto.
    """
    return _cerca(testo, slugs, "direttiva")


def unita_puntate(testo, slugs):
    """Unita' verso cui il testo porta un PUNTATORE di esecuzione (per i corpi)."""
    return _cerca(testo, slugs, "puntatore")


_cache_puntatori_unita = {}


def puntatori_di_unita(radice_repo, unita, slugs):
    """Un HOP: le unita' puntate dal corpo di `unita`. Cache per run."""
    if unita in _cache_puntatori_unita:
        return _cache_puntatori_unita[unita]
    tipo, _, slug = unita.partition("/")
    percorso = radice_repo / ".claude" / tipo / ("%s.md" % slug)
    try:
        testo = percorso.read_text(encoding="utf-8", errors="replace")
    except OSError:
        testo = ""
    esito = [u for u in unita_puntate(testo, slugs) if u != unita]
    _cache_puntatori_unita[unita] = esito
    return esito


def esecutori_a_un_hop(radice_repo, unita_bersaglio, slugs):
    """Inverso: quali unita' PUNTANO a `unita_bersaglio` nel proprio corpo.

    La propagazione si ferma a UN HOP per scelta dichiarata: una catena piu'
    lunga sarebbe inferenza illimitata, e un osservatore che inferisce
    esecuzioni a profondita' arbitraria misura il grafo, non la telemetria.
    """
    esecutori = []
    for unita in slugs:
        if unita == unita_bersaglio:
            continue
        if unita_bersaglio in puntatori_di_unita(radice_repo, unita, slugs):
            esecutori.append(unita)
    return sorted(esecutori)


def slugs_flotta(radice_repo):
    """{unita: slug} per ogni CORPO di unita' esistente in `.claude/`."""
    slugs = {}
    for tipo in TIPI_UNITA_FLOTTA:
        cartella = radice_repo / ".claude" / tipo
        if not cartella.is_dir():
            continue
        for f in sorted(cartella.glob("*.md")):
            info = risolvi_unita(str(f.relative_to(radice_repo)), radice_repo)
            if info and info.get("asse") == "corpo" and info.get("unita"):
                slugs[info["unita"]] = info["unita"].split("/", 1)[1]
    return slugs


# Trigger PER FOGLIA, letti dal corpo dell'unita' che vi punta. Necessario e non
# cosmetico: `dev-protocol` dichiara CINQUE flag e le sue tre foglie sono gated
# da flag DIVERSI. Valutarli in AND a livello di unita' — come faceva la prima
# versione di questo file — rende `dev-protocol` `non osservabile` perche'
# `fe_correctness` e `ux_ui` sono `false`, cioe' CANCELLA l'unico `divergente`
# forte della finestra con un difetto di granularita'. E' la taratura a senso
# unico di A-49 colta in atto sul proprio output.
# A-42 e' esplicito nell'altra direzione: le due foglie di Fase 4-bis/4-ter sono
# «foglie il cui mancato accesso e' CORRETTO» con i flag spenti; la foglia
# `analytics-instrumentation.md` no, perche' il suo gate e' vero da 2026-06-04.
TRIGGER_FOGLIA = {
    ".claude/skills/references/dev-protocol/analytics-instrumentation.md":
        ["analytics.measurement.enabled", "analytics.dogfooding.enabled"],
    ".claude/skills/references/dev-protocol/fase4-bis-visual-verification.md":
        ["fe_correctness.enabled"],
    ".claude/skills/references/dev-protocol/fase4-ter-ux-ui-review.md":
        ["ux_ui.enabled"],
    ".claude/agents/references/fe-dev/visual-oracle-integration.md":
        ["fe_correctness.enabled"],
    ".claude/agents/references/fe-dev/a11y-and-functional-oracle.md":
        ["fe_correctness.enabled", "a11y.enabled"],
    ".claude/agents/references/fe-dev/ux-ui-review-and-design-spec.md":
        ["ux_ui.enabled"],
    ".claude/agents/references/fe-dev/llm-generator-separation.md":
        ["design_intelligence.enabled"],
    ".claude/agents/references/fe-dev/hydration-drift-check.md":
        ["ssr_aware.enabled"],
}


def _trigger_di_foglia(path_foglia, trigger_unita):
    """(trigger, fonte). Eredita dall'unita' SOLO se l'unita' dichiara UN flag:
    ereditare una lista in AND e' il difetto di granularita' descritto sopra.
    Trigger non dichiarato => INCONDIZIONATO, non spento (assenza di chiave non
    e' `false`: trattarla come falsa cancellerebbe l'obbligazione)."""
    if path_foglia in TRIGGER_FOGLIA:
        return TRIGGER_FOGLIA[path_foglia], "dichiarato per-foglia"
    if len(trigger_unita) == 1:
        return list(trigger_unita), "ereditato dall'unita' (un solo flag)"
    if trigger_unita:
        return [], ("NON dichiarato: l'unita' ha %d flag in AND, ereditarli "
                    "cancellerebbe l'obbligazione — trattata come incondizionata"
                    % len(trigger_unita))
    return [], "nessun trigger dichiarato: obbligazione incondizionata"


# Relazione ESECUTORE -> UNITA' ESEGUITA, **dichiarata e con la fonte accanto**,
# non inferita dal grafo dei puntatori. Serve perche' il dispatch osservato e'
# quello dell'AGENTE, mentre l'unita' obbligata e' la SKILL che l'agente esegue:
# senza la relazione, `tavola-rotonda-protocol` resta `non osservabile` mentre
# A-32 ha congelato che «il MODERATORE che gira il protocollo lo sta eseguendo —
# e' la Famiglia 2 sull'unita' `tavola-rotonda-protocol`».
# Ogni voce porta la propria fonte perche' AGGIUNGERE UNA VOCE CAMBIA I VERDETTI:
# una tabella senza fonti diventa la leva con cui si tara l'osservatore.
# La versione INFERITA (un hop sul grafo dei puntatori) esiste ma NON e' nel path
# del verdetto: gira come `criterio_propagato` e viene riportata a ogni run.
ESECUTORE_DICHIARATO = {
    # dichiarato dall'unita' stessa: dev-protocol.md §1 «Skill condivisa fra
    # `be-dev`, `fe-dev`, `db-dev`, `qa-dev`». `docs-dev` punta alla skill nel
    # proprio corpo ma NON e' nella lista dichiarata dalla skill: resta fuori dal
    # criterio diretto e compare nel solo criterio propagato.
    "skills/dev-protocol": [
        ("agents/be-dev", "dev-protocol.md §1 (skill condivisa)"),
        ("agents/fe-dev", "dev-protocol.md §1 (skill condivisa)"),
        ("agents/db-dev", "dev-protocol.md §1 (skill condivisa)"),
        ("agents/qa-dev", "dev-protocol.md §1 (skill condivisa)"),
    ],
    # A-32, verbatim: «il MODERATORE che gira il protocollo lo sta eseguendo».
    "skills/tavola-rotonda-protocol": [
        ("agents/tavola-rotonda-moderatore", "TR-e5b81d64 A-32 (verbatim)"),
    ],
}


def _condizione_al_ts(config, ts, trigger):
    """(vera, dettaglio) — AC4: i flag AL MOMENTO DELL'ESECUZIONE, non di oggi.

    Nessun trigger => obbligazione INCONDIZIONATA (vera). Chiave assente nel
    config di quel commit => None, che NON e' `false`.
    """
    if not trigger:
        return True, {"trigger": [], "regola": "obbligazione incondizionata"}
    stato = config.flag(ts, trigger)
    valori = stato.get("flags", {})
    falsi = [k for k, v in valori.items() if v is False]
    return (not falsi), {"trigger": trigger, "flags": valori,
                         "flag_falsi_al_ts": falsi,
                         "config_commit": stato.get("commit"),
                         "config_commit_ts": stato.get("commit_ts")}


def _eventi_esecuzione(unita, mandati, dispatch_per_unita, invoc_per_unita,
                       giorno_esclusivo, radice_repo, slugs, modo="diretto"):
    """Eventi di ESECUZIONE dell'unita' nella finestra, in uno dei tre modi.

    Filtri obbligatori sui mandati, tutti con la loro ragione:
      1. `nella_finestra(ts)` — AC6: la giornata di authoring e' esclusa ANCHE
         per i mandati. Senza questo filtro i mandati dei pilot del 2026-09-04
         («PILOT WAVE D #4 — Target `fe-dev.md`») entrano come esecuzioni e
         producono divergenze che sono l'atto di SCRIVERE l'unita', non di
         eseguirla. La prima versione di questo file non aveva il filtro e
         produceva tre falsi `divergente`.
      2. correzione di CANALE di A-41 (`mandato_effettivo`) — se in quel
         transcript l'unita' e' stata MUTATA, il mandato per quell'unita' e'
         manutenzione qualunque cosa dica il testo: «nell'harness un `Edit`
         richiede un `Read` precedente sullo stesso path».
      3. posizione: direttiva (`diretto`) o menzione semplice (`largo`).

    Modi:
      `diretto`    — evidenza OSSERVATA: mandato in posizione di direttiva,
                     dispatch/invocazione dell'unita', dispatch/invocazione di un
                     esecutore DICHIARATO (con fonte).
      `largo`      — come `diretto` ma basta la MENZIONE nel mandato.
      `propagato`  — come `diretto` piu' UN HOP inferito sul grafo dei puntatori
                     fra i corpi. **Inferenza, non osservazione**: non e' nel
                     path del verdetto.
    """
    eventi = []
    chiave = "unita_menzionate" if modo == "largo" else "unita_nominate"
    for m in mandati:
        if m["mandato"] != "esecuzione" or m["auto_referenziale"]:
            continue
        if not nella_finestra(m.get("ts"), giorno_esclusivo):
            continue
        if unita not in (m.get(chiave) or []):
            continue
        classe, regola = mandato_effettivo(m["mandato"], m["mandato_regola"],
                                           unita, set(m.get("unita_mutate") or []))
        if classe != "esecuzione":
            continue  # A-41: l'unita' e' stata MUTATA qui, non eseguita
        eventi.append({"fonte": "mandato-%s" % ("menzione" if modo == "largo"
                                                else "direttiva"),
                       "ts": m.get("ts"), "transcript": m["transcript"],
                       "sessione": m["sessione"], "regola_mandato": regola,
                       "estratto": m.get("estratto")})

    def _aggiungi(sorgente, etichetta):
        for d in dispatch_per_unita.get(sorgente, []):
            eventi.append({"fonte": "dispatch %s%s" % (sorgente, etichetta),
                           "ts": d["ts"], "transcript": None, "sessione": None})
        for i2 in invoc_per_unita.get(sorgente, []):
            eventi.append({"fonte": "invocazione Skill %s%s" % (sorgente, etichetta),
                           "ts": i2["ts"], "transcript": None, "sessione": None})

    _aggiungi(unita, "")
    for sorgente, fonte in ESECUTORE_DICHIARATO.get(unita, []):
        _aggiungi(sorgente, " [esecutore dichiarato: %s]" % fonte)
    if modo == "propagato":
        dichiarati = {s for s, _ in ESECUTORE_DICHIARATO.get(unita, [])}
        for sorgente in esecutori_a_un_hop(radice_repo, unita, slugs):
            if sorgente in dichiarati or sorgente == unita:
                continue
            _aggiungi(sorgente, " [INFERITO un hop dal grafo dei puntatori]")

    eventi.sort(key=lambda e: _ts_confrontabile(e.get("ts") or ""))
    return eventi


def _valuta_unita(voce, mie_foglie, accessi, eventi, config):
    """Regola DETERMINISTICA del verdetto, in quest'ordine:

      1. l'unita' non ha foglie               -> `non osservabile`
      2. zero esecuzioni osservate            -> `non osservabile`
      3. nessuna foglia obbligata al ts di
         nessuna esecuzione                    -> `non osservabile`
      4. zero accessi alle foglie OBBLIGATE
         su ENTRAMBI i canali, sotto mandato
         di esecuzione                         -> `divergente`
      5. altrimenti                            -> `invariato`

    Nessun LLM, nessuna soglia, nessun giudizio (AC17).
    """
    trigger_unita = TRIGGER_CONDIZIONALI.get(voce["unita"], [])
    per_foglia = []
    obbligate = []
    for f in mie_foglie:
        trig, fonte = _trigger_di_foglia(f["path"], trigger_unita)
        ts_obbliganti, falsi, evidenza_config = [], set(), []
        for ev in eventi:
            vera, dett = _condizione_al_ts(config, ev.get("ts"), trig)
            if vera:
                ts_obbliganti.append(ev.get("ts"))
            else:
                falsi.update(dett.get("flag_falsi_al_ts") or [])
            # AC4 — l'evidenza del `config@ts(e)` deve essere LEGGIBILE, non
            # solo usata: il commit da cui i flag sono stati letti viaggia
            # nell'output insieme ai valori che aveva a quel ts.
            if trig and len(evidenza_config) < 3:
                evidenza_config.append({
                    "ts": ev.get("ts"), "config_commit": dett.get("config_commit"),
                    "config_commit_ts": dett.get("config_commit_ts"),
                    "flags": dett.get("flags"), "condizione_vera": vera})
        acc_f = [a for a in accessi if a["path"] == f["path"]]
        acc_f_esec = [a for a in acc_f if a["mandato"] == "esecuzione"]
        voce_f = {
            "foglia": f["path"], "righe": f["righe"],
            "trigger": trig, "trigger_fonte": fonte,
            "obbligata": bool(ts_obbliganti),
            "esecuzioni_obbliganti": len(ts_obbliganti),
            "flag_falsi_al_ts": sorted(falsi),
            "accessi_sotto_esecuzione": len(acc_f_esec),
            "accessi_qualunque_mandato": len(acc_f),
            "config_at_ts_evidenza": evidenza_config,
        }
        per_foglia.append(voce_f)
        if voce_f["obbligata"]:
            obbligate.append(voce_f)

    paths_obbligate = {v["foglia"] for v in obbligate}
    acc_obbl_esec = [a for a in accessi if a["path"] in paths_obbligate
                     and a["mandato"] == "esecuzione"]
    acc_obbl_tutti = [a for a in accessi if a["path"] in paths_obbligate]

    if not mie_foglie:
        verdetto = "non osservabile"
        motivo = ("nessuna foglia: l'unita' non ha un'obbligazione di lettura "
                  "dichiarata da misurare" + (" — no-refactor motivato, a CREDITO "
                  "del protocollo (A-30)" if voce.get("no_refactor") else ""))
    elif not eventi:
        verdetto = "non osservabile"
        motivo = ("zero esecuzioni osservate nella finestra: nessun mandato in "
                  "posizione di direttiva, nessun dispatch, nessuna invocazione")
    elif not obbligate:
        falsi = sorted({k for v in per_foglia for k in v["flag_falsi_al_ts"]})
        verdetto = "non osservabile"
        motivo = ("%d esecuzioni osservate, ZERO foglie obbligate al loro ts "
                  "(flag falsi: %s): il trigger non obbligava, e il mancato "
                  "accesso e' CORRETTO (A-42)" % (len(eventi), ", ".join(falsi) or "-"))
    elif not acc_obbl_esec:
        verdetto = "divergente"
        motivo = ("%d esecuzioni, %d foglia/e OBBLIGATA/E (%s), ZERO accessi su "
                  "entrambi i canali sotto mandato di esecuzione"
                  % (len(eventi), len(obbligate),
                     ", ".join(v["foglia"].split("/")[-1] for v in obbligate)))
        if acc_obbl_tutti:
            motivo += (" — %d accessi esistono, ma sotto mandato %s: l'accesso "
                       "non e' l'esecuzione" % (len(acc_obbl_tutti),
                       "/".join(sorted({a["mandato"] for a in acc_obbl_tutti}))))
    else:
        verdetto = "invariato"
        motivo = ("%d esecuzioni, %d accessi alle foglie obbligate sotto "
                  "esecuzione — POCA INFORMAZIONE: l'accesso non e' l'uso"
                  % (len(eventi), len(acc_obbl_esec)))
    return verdetto, motivo, per_foglia, obbligate, acc_obbl_esec, acc_obbl_tutti


def verdetti_differ(esito, radice_repo, config, giorno_esclusivo, campagna=None,
                    foglie=None):
    """Sottocomando `--differ`: un verdetto per unita' obbligata, piu' i due
    criteri alternativi (menzione e propagazione a un hop) riportati a ogni run.

    I due criteri alternativi NON sono decorazione: sono cio' che la scelta del
    criterio diretto sopprime. Riportarli e' l'unico rimedio disponibile dentro
    lo strumento al dissenso 6 / A-49 — «l'osservatore non ha mai dimostrato di
    poter dire ne' piu' ne' meno di quello che i suoi autori gli hanno fatto
    dire» — perche' rende leggibile, a ogni run, quanto del risultato dipende
    dalla scelta di criterio e non dalla telemetria.
    """
    campagna = campagna or CAMPAGNA_EP060
    # `foglie` iniettato = inventario CONGELATO (TSK-657). Senza iniezione si
    # legge il filesystem, che e' il comportamento di misura normale.
    if foglie is None:
        _, foglie = inventario_flotta(radice_repo)
    slugs = slugs_flotta(radice_repo)

    per_unita = collections.defaultdict(list)
    for r in esito["record"]:
        per_unita[r["unita"]].append(r)
    dispatch_per_unita = collections.defaultdict(list)
    for d in esito["dispatch"]:
        dispatch_per_unita[d["unita"]].append(d)
    invoc_per_unita = collections.defaultdict(list)
    for i in esito["invocazioni_skill"]:
        invoc_per_unita[i["unita"]].append(i)
    mandati = esito["mandati"]

    verdetti = []
    for voce in campagna:
        unita = voce["unita"]
        mie_foglie = foglie.get(unita, [])
        accessi = [a for a in per_unita.get(unita, []) if a["asse_ancorante"]]

        def eventi_in(modo):
            return _eventi_esecuzione(unita, mandati, dispatch_per_unita,
                                      invoc_per_unita, giorno_esclusivo,
                                      radice_repo, slugs, modo)

        eventi = eventi_in("diretto")
        verdetto, motivo, per_foglia, obbligate, acc_esec, acc_tutti = _valuta_unita(
            voce, mie_foglie, accessi, eventi, config)

        alternativi = {}
        for modo in ("largo", "propagato"):
            ev_alt = eventi_in(modo)
            v_alt, m_alt = _valuta_unita(voce, mie_foglie, accessi, ev_alt, config)[:2]
            alternativi[modo] = {
                "verdetto": v_alt, "motivo": m_alt,
                "differisce": v_alt != verdetto,
                "esecuzioni_osservate": len(ev_alt),
            }
        alternativi["largo"]["definizione"] = (
            "la MENZIONE dell'unita' in un mandato di esecuzione vale come "
            "evidenza (invece della posizione di direttiva)")
        alternativi["propagato"]["definizione"] = (
            "un HOP INFERITO sul grafo dei puntatori fra corpi: il dispatch di "
            "A vale come esecuzione di B se il corpo di A punta a B. Inferenza, "
            "non osservazione: fuori dal path del verdetto")

        verdetti.append({
            "unita": unita, "path": voce["path"], "verdetto": verdetto,
            "significato": VERDETTI_SIGNIFICATO[verdetto], "motivo": motivo,
            "no_refactor": bool(voce.get("no_refactor")),
            "criterio": ("evidenza OSSERVATA: mandato in posizione di direttiva "
                         "+ dispatch/invocazione dell'unita' + dispatch di un "
                         "esecutore dichiarato con fonte"),
            "obbligazione": {
                "asse": ASSE_OBBLIGATO,
                "descrizione": OBBLIGAZIONE_DESCRIZIONE,
                "trigger_unita": TRIGGER_CONDIZIONALI.get(unita, []),
                "esecutori_dichiarati": [
                    {"unita": s, "fonte": f}
                    for s, f in ESECUTORE_DICHIARATO.get(unita, [])],
                "per_foglia": per_foglia,
                "foglie_obbligate": [v["foglia"] for v in obbligate],
            },
            "esecuzioni_osservate": len(eventi),
            "accessi_foglie_obbligate_sotto_esecuzione": len(acc_esec),
            "accessi_foglie_obbligate_qualunque_mandato": len(acc_tutti),
            "accessi_corpo": sum(1 for a in accessi if a["asse"] == "corpo"),
            "canali": {"Read": sum(1 for a in accessi if a["canale"] == "Read"),
                       "Bash": sum(1 for a in accessi if a["canale"] == "Bash")},
            "criterio_largo": alternativi["largo"],
            "criterio_propagato": alternativi["propagato"],
            "evidenza": eventi[:12],
            "evidenza_accessi": [
                {"path": a["path"], "canale": a["canale"], "ts": a["ts"],
                 "mandato": a["mandato"], "evidenza": a["evidenza"]}
                for a in accessi[:12]],
        })

    verdetti.sort(key=lambda v: ({"divergente": 0, "invariato": 1,
                                  "non osservabile": 2}[v["verdetto"]], v["unita"]))
    return verdetti


def conta_osservabilita(verdetti):
    """AC8 — `osservabilita: X/Y` + la tripla. Y esclude il no-refactor, che non
    e' un refactor misurato (A-30): i 10 applicati sono l'universo del differ."""
    misurabili = [v for v in verdetti if not v["no_refactor"]]
    tripla = collections.Counter(v["verdetto"] for v in misurabili)
    x = tripla["divergente"] + tripla["invariato"]
    return {
        "X": x, "Y": len(misurabili),
        "riga": "osservabilità: %d/%d" % (x, len(misurabili)),
        "divergente": tripla["divergente"],
        "invariato": tripla["invariato"],
        "non osservabile": tripla["non osservabile"],
        "a_credito_no_refactor": len(verdetti) - len(misurabili),
        "lettura": DIVIETO_ENUNCIATO_DI_CONFORMITA,
        "significati": VERDETTI_SIGNIFICATO,
    }

# ─── Snapshot DATATO di A-23(i) e indicatore di DRIFT (TSK-657) ──────────────

# COS'ERA E PERCHE' E' CAMBIATO. Fino a TSK-657 questa sede conteneva
# `atteso = {"accept": 1, "reject": 9}` e un campo `concorda_con_il_registro`
# booleano. Il 2026-09-21 il rimedio di TSK-650 ha ridotto `skills/dev-protocol`
# e il conteggio e' diventato `{accept: 2, reject: 8}`: `concorda` e' passato a
# `false` PERCHE' IL REPO E' MIGLIORATO. Un indicatore che segnala fallimento
# quando l'oggetto misurato migliora e' tarato a senso unico — e' il dissenso 6
# / A-49 che sorveglia esattamente questo — e il rimedio VIETATO era sostituire
# il numero con quello di oggi continuando a chiamarlo «concordanza».
#
# COS'E' ORA. Lo snapshot resta CONGELATO E DATATO e il campo diventa un
# INDICATORE DI DRIFT: dice quali unita' si sono mosse e IN QUALE DIREZIONE
# rispetto allo snapshot. Non e' un esito, non entra in `fallita`, non muove
# l'exit code. Il ri-congelamento e' un ATTO DELIBERATO, come per
# `INVENTARIO_VERSIONI_CLAUDE_MD`: chi lo esegue lo dichiara nel proprio TSK.
#
# PROVENIENZA DELLA TABELLA PER-UNITA', che l'aggregato del registro non aveva.
# Il registro TR-e5b81d64 congela l'AGGREGATO (1 accept / 9 reject); la tabella
# per-unita' e' stata RICOSTRUITA E MISURATA — non assunta — al commit 5f77b46,
# che e' lo stato pre-rimedio (le modifiche di TSK-650 erano ancora non
# committate), con:
#
#   git ls-tree -r --name-only 5f77b46 -- .claude/{agents,skills,commands}/
#   git show 5f77b46:<path> | wc -l        # corpo e foglie, una per una
#
# La misura ha restituito `skills/dev-protocol` = reject (corpo 305 + foglie 281
# = 586 > baseline 519, +67) e somma ESATTAMENTE all'aggregato congelato dal
# registro: 1 accept (`skills/prototype-generation-protocol`), 9 reject, 1 a
# credito. La concordanza fra la tabella e l'aggregato e' verificata a ogni run
# (`per_unita_concorda_col_registro`) ed e' un controllo dello snapshot CON SE
# STESSO: se qualcuno ritoccasse una voce per far quadrare un verdetto di oggi,
# la somma non tornerebbe piu'.
SNAPSHOT_A23I_PER_UNITA = {
    "skills/dev-protocol": "reject",
    "skills/parallel-scheduling": "reject",
    "commands/factory-bootstrap": "reject",
    "skills/tavola-rotonda-protocol": "reject",
    "skills/lint-checks": "reject",
    "skills/functional-oracle-protocol": "reject",
    "agents/fe-dev": "reject",
    "skills/prototype-generation-protocol": "accept",
    "commands/prototype": "reject",
    "agents/tavola-rotonda-moderatore": "reject",
    "agents/prototype-generator": "a credito",
}

# L'aggregato VERBATIM del registro, che resta la fonte: la tabella per-unita'
# gli si deve sommare. `a credito` e' fuori dal conteggio accept/reject (A-30).
SNAPSHOT_A23I_CONTEGGIO_REGISTRO = {"accept": 1, "reject": 9}

SNAPSHOT_A23I_META = {
    "snapshot": "TR-e5b81d64 2026-09-21 pre-rimedio",
    "data": "2026-09-21",
    "stato": "pre-rimedio di TSK-650 (US-275)",
    "fonte": "registro TR-e5b81d64 §A-23 (aggregato) + misura a 5f77b46 (per-unita')",
    "commit_di_misura": "5f77b46",
    "congelato": True,
    "ri_congelamento": ("atto DELIBERATO, da dichiarare nel TSK che lo esegue: "
                        "aggiornare lo snapshot per far concordare il conteggio "
                        "di oggi e' la taratura a senso unico che A-49 sorveglia"),
}


def _direzione(da, a):
    """Direzione di un movimento fra due esiti di A-23(i).

    `accept` e' l'unico polo definito: l'asserzione dice `totale <= baseline` e
    tutto il resto non e' un accept. `non valutabile` NON e' un accept e non si
    degrada (A-23 ii); `a credito` sta FUORI dal conteggio (A-30). Un movimento
    che non coinvolge `accept` ha una direzione che questa scala non definisce,
    e viene riportato come tale invece di essere forzato in una delle due liste.
    """
    if da == a:
        return "invariato"
    if a == "accept":
        return "miglioramento"
    if da == "accept":
        return "regressione"
    return "indefinito"


def drift_a23i(esiti, snapshot=None, per_unita=None):
    """Drift degli esiti di oggi rispetto allo snapshot congelato e datato.

    NON e' un test di concordanza e non ha un esito: un movimento migliorativo
    non e' un fallimento, e nessuna voce di questo campo entra in `fallita` ne'
    muove l'exit code. Serve a rispondere a «che cosa si e' mosso, e da che
    parte», che e' la domanda che `concorda: False` non sapeva porre.
    """
    per_unita = SNAPSHOT_A23I_PER_UNITA if per_unita is None else per_unita
    snapshot = SNAPSHOT_A23I_META if snapshot is None else snapshot
    oggi = {e["unita"]: e["esito"] for e in esiti}
    delta_oggi = {e["unita"]: e.get("delta") for e in esiti}

    gruppi = {"miglioramenti": [], "regressioni": [], "indefiniti": []}
    invariati, fuori_snapshot = [], []
    for unita, esito_oggi in oggi.items():
        if unita not in per_unita:
            fuori_snapshot.append({"unita": unita, "oggi": esito_oggi})
            continue
        prima = per_unita[unita]
        direzione = _direzione(prima, esito_oggi)
        if direzione == "invariato":
            invariati.append(unita)
            continue
        voce = {"unita": unita, "da": prima, "a": esito_oggi,
                "delta_oggi": delta_oggi.get(unita)}
        gruppi[{"miglioramento": "miglioramenti", "regressione": "regressioni",
                "indefinito": "indefiniti"}[direzione]].append(voce)

    conteggio_snapshot = collections.Counter(per_unita.values())
    conteggio_oggi = collections.Counter(oggi.values())
    usciti = sorted(u for u in per_unita if u not in oggi)
    return {
        "snapshot": snapshot["snapshot"],
        "snapshot_riferimento": dict(snapshot, per_unita=dict(per_unita),
                                     conteggio_per_unita=dict(conteggio_snapshot),
                                     conteggio_registro=dict(SNAPSHOT_A23I_CONTEGGIO_REGISTRO)),
        "per_unita_concorda_col_registro": all(
            conteggio_snapshot.get(k, 0) == v
            for k, v in SNAPSHOT_A23I_CONTEGGIO_REGISTRO.items()),
        "miglioramenti": sorted(gruppi["miglioramenti"], key=lambda v: v["unita"]),
        "regressioni": sorted(gruppi["regressioni"], key=lambda v: v["unita"]),
        "movimenti_di_direzione_indefinita": sorted(gruppi["indefiniti"],
                                                    key=lambda v: v["unita"]),
        "invariati": sorted(invariati),
        "unita_fuori_snapshot": sorted(fuori_snapshot, key=lambda v: v["unita"]),
        "unita_uscite_dalla_campagna": usciti,
        "conteggio_oggi": dict(conteggio_oggi),
        "mosse": sum(len(v) for v in gruppi.values()),
        "bloccante": False,
        "regola_di_lettura": (
            "DRIFT su uno snapshot DATATO, non concordanza. Un movimento "
            "migliorativo NON e' un fallimento e non produce exit != 0: questo "
            "campo e' informativo e non entra in `fallita`. L'exit 6 di "
            "`--load --asserzione` dipende dai `reject` di A-23(i), cioe' dalla "
            "MASSA di oggi, non dal drift. Il rimedio a un drift non e' "
            "aggiornare lo snapshot: e' leggere che cosa si e' mosso."),
    }


# ─── Asserzione A-23(i) — exit code nel path (AC9) ────────────────────────────

def asserzione_a23i(radice_repo, campagna=None):
    """`righe(corpo) + righe(foglie create) <= righe(baseline)`.

    La baseline e' letta da `git show <baseline_commit>:<path>` — MAI da un
    numero in prosa: «un numero in prosa drifta» (A-23, che e' l'argomento con
    cui fleet-doctor ha ritirato il proprio meter in A-4). Il numero dichiarato
    nel registro viaggia accanto alla misura: se divergono, il reperto e' il
    disaccordo.

    Girata sui 10 refactor applicati deve restituire **1 accept e 9 reject**;
    il no-refactor e' A CREDITO e non entra nel conteggio (A-30).

    Nessun taglio, nessun `git checkout`, nessuna riparazione: e' MISURA (A-12,
    R.S5, R-SAA-6).
    """
    campagna = campagna or CAMPAGNA_EP060
    _, foglie = inventario_flotta(radice_repo)
    esiti = []
    for voce in campagna:
        unita, path_rel = voce["unita"], voce["path"]
        righe_corpo, _ = misura_file(radice_repo / path_rel)
        mie_foglie = foglie.get(unita, [])
        righe_foglie = sum(f["righe"] for f in mie_foglie)
        baseline = righe_a_commit(radice_repo, voce["baseline_sha"], path_rel)
        totale = righe_corpo + righe_foglie

        if baseline is None:
            esito = "non valutabile"
            nota = ("baseline non recuperabile da `git show %s:%s` — NON e' un "
                    "accept e non si degrada (A-23 ii)" % (voce["baseline_sha"], path_rel))
        elif voce.get("no_refactor"):
            esito = "a credito"
            nota = ("no-refactor deliberato e motivato: «la capability sa dire "
                    "di no» (A-30). Fuori dal conteggio accept/reject.")
        elif totale <= baseline:
            esito = "accept"
            nota = "corpo %d + foglie %d = %d <= baseline %d" % (
                righe_corpo, righe_foglie, totale, baseline)
        else:
            esito = "reject"
            nota = "corpo %d + foglie %d = %d > baseline %d (+%d)" % (
                righe_corpo, righe_foglie, totale, baseline, totale - baseline)

        esiti.append({
            "unita": unita, "path": path_rel, "esito": esito,
            "baseline_sha": voce["baseline_sha"],
            "baseline_righe_misurate": baseline,
            "baseline_righe_dichiarate": voce["righe_prima_dichiarate"],
            "baseline_dichiarata_concorda": (baseline == voce["righe_prima_dichiarate"]
                                             if baseline is not None else None),
            "sha_fonte": voce["sha_fonte"],
            "righe_corpo_oggi": righe_corpo,
            "righe_corpo_dichiarate_post_refactor": voce["righe_dopo_dichiarate"],
            "righe_foglie_oggi": righe_foglie,
            "foglie": [f["path"] for f in mie_foglie],
            "totale_oggi": totale,
            "delta": (totale - baseline) if baseline is not None else None,
            "nota": nota,
        })

    conteggio = collections.Counter(e["esito"] for e in esiti)
    # `atteso_dal_registro` + `concorda_con_il_registro` sono stati SOSTITUITI
    # da `drift_dal_snapshot` (TSK-657): lo snapshot e' datato e congelato, e il
    # campo dice che cosa si e' mosso invece di dire «non concorda» quando
    # l'oggetto misurato migliora. Vedi il commento su SNAPSHOT_A23I_PER_UNITA.
    drift = drift_a23i(esiti)
    return {
        "asserzione": "righe(corpo) + righe(foglie create) <= righe(baseline)",
        "fonte": "A-23(i) — baseline da `git show <baseline_commit>:<path>`",
        "esiti": esiti,
        "conteggio": dict(conteggio),
        "drift_dal_snapshot": drift,
        "fallita": conteggio.get("reject", 0) > 0 or conteggio.get("non valutabile", 0) > 0,
        "regola_di_lettura": (
            "L'asserzione misura la MASSA, non la qualita' del refactor: «l'agente "
            "ripara il failure mode, il verdetto di massa non e' suo» (A-42). Un "
            "reject NON autorizza un ripristino: la factory non auto-ripara "
            "(R.S5, R-SAA-6) e nessuna sezione viene rimossa in questo EP (A-12)."),
    }


# ─── Asserzione ANTI-RICRESCITA di `CLAUDE.md` (TSK-651 / US-276 AC5) ────────

# `CLAUDE.md` e' l'UNICO file sempre in contesto dell'adapter Claude, e non e'
# cresciuto per caso: e' cresciuto **PER accumulo di changelog**. Al 2026-09-21
# il preambolo (8.355 byte) e la lista di `## Meta-prompt versioning` (11.712)
# erano 20.067 byte = 40% del file, ed erano CACHE DICHIARATA — l'intestazione
# dice `(authoritative source: factory.config.yaml#pattern_version)` e poi ne
# incollava l'elenco. TSK-651 li ha cancellati (duplicato provato in
# `CHANGELOG.md` + `meta-prompts/README.md` §Available versions, entrambi NON
# always-on). Senza questa asserzione **il file ricresce entro tre release**:
# la causa va chiusa, non solo l'effetto.
#
# FORMA DELL'ASSERZIONE, e perche' non e' la forma letterale di AC5. AC5 chiede
# «`CLAUDE.md` non contiene stringhe di versione diverse da quella corrente».
# Preso alla lettera e' INSODDISFACIBILE senza violare AC4: le 66 occorrenze
# residue sono **tag di provenienza** (`(v2.12, opt)`, `| Fleet Doctor (v2.41,
# opt) |`, `## §code_intelligence ... v2.37`) e 13 di esse vivono dentro le
# sezioni `§capability` e nei blocchi VERBATIM di AC8, che questo TSK non puo'
# toccare. La forma implementata e' quindi la piu' stretta che sia soddisfacibile:
# **inventario congelato per token + tetto di occorrenze**. Una versione NUOVA e'
# rossa; una versione nota che compare UNA VOLTA IN PIU' e' rossa. Il calo non e'
# mai rosso (ridurre e' sempre lecito) ma viene riportato, perche' il
# ri-congelamento dell'inventario deve essere un ATTO DELIBERATO e non un effetto.
#
# Non e' un giudizio semantico e non legge il significato del testo: conta
# occorrenze di una regex. Read-only, nessun auto-fix (R.S5, R-SAA-6).
VERSIONE_CORRENTE_FALLBACK = "2.42"

# Congelato il 2026-09-21 su `CLAUDE.md` DOPO il taglio di TSK-651 (24.688 byte).
# Ogni voce e' un tag di provenienza in una sezione che TSK-651 non tocca:
# `§Adapter registry` (contract degli adapter: 2.13, 2.37), `§Configurazione
# factory`, `§Quick start`, `§Mapping ruoli`, le cinque `§capability` (AC4) e i
# quattro blocchi VERBATIM di AC8. NON c'e' nessuna riga di changelog.
# RI-CONGELATO il 2026-10-05 da TSK-731 (EP-069), atto deliberato: US-305 ha ridotto
# `CLAUDE.md` da 30.861 a 9.487 byte spostando il dettaglio in `CAPABILITIES.md`, quindi
# l'inventario del 2026-09-21 (66 occorrenze) era tutto «in calo». Tetto nuovo: 18. Il token
# `2.42` (contract dell'adapter `.claude/` nel registro adapter) era libero quando la
# versione corrente era 2.42 e non e' mai entrato nell'inventario precedente: e' un tag di
# provenienza legittimo, non changelog. Misura:
#   python3 -c "import re,collections; ..." su CLAUDE.md @ EP-069 (vedi TSK-731)
INVENTARIO_VERSIONI_CLAUDE_MD = {
    "2.13": 1, "2.37": 1, "2.42": 1, "v2.10": 1, "v2.12": 2, "v2.21": 1,
    "v2.39": 1, "v2.4": 1, "v2.40": 2, "v2.41": 1, "v2.44": 1, "v2.7": 4,
    "v2.9": 1,
}

_RX_VERSIONE_TESTO = re.compile(r"\bv?2[.-]\d{1,2}\b")


def versione_corrente(radice_repo):
    """`pattern_version` da `factory.config.yaml` — SSOT (Lint Check 4am).

    Non un numero in prosa: «un numero in prosa drifta» (A-23). Se la chiave e'
    illeggibile si usa il fallback E lo si DICHIARA nell'output, perche' un
    confronto con una versione indovinata non e' un confronto.
    """
    try:
        testo = (radice_repo / "factory.config.yaml").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return VERSIONE_CORRENTE_FALLBACK, False
    v = yaml_scalare(testo, "pattern_version")
    if not isinstance(v, str) or not v.strip():
        return VERSIONE_CORRENTE_FALLBACK, False
    return v.strip(), True


def asserzione_anti_ricrescita(radice_repo, path_rel="CLAUDE.md",
                               inventario=None):
    """Nessuna stringa di versione NUOVA o IN ECCESSO in `CLAUDE.md` (AC5).

    Rosso se: un token di versione non nell'inventario congelato compare, o un
    token noto compera piu' volte del tetto. Verde (con drift riportato) se
    cala. La versione corrente e' libera: e' l'unica che il file DEVE dichiarare
    (Check 4am la cerca nell'intestazione di `## Meta-prompt versioning`).
    """
    inventario = INVENTARIO_VERSIONI_CLAUDE_MD if inventario is None else inventario
    corrente, letta_da_config = versione_corrente(radice_repo)
    libere = {corrente, "v" + corrente, "v" + corrente.replace(".", "-")}
    percorso = radice_repo / path_rel
    try:
        testo = percorso.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "asserzione": "nessuna stringa di versione nuova o in eccesso in %s" % path_rel,
            "file_assente": True, "fallita": False,
            "nota": "%s non leggibile: l'asserzione non ha un oggetto, non un verdetto" % path_rel,
        }
    trovati = collections.Counter(
        tk for tk in _RX_VERSIONE_TESTO.findall(testo) if tk not in libere)
    nuovi = sorted(tk for tk in trovati if tk not in inventario)
    eccedenze = sorted(("%s: %d > %d" % (tk, n, inventario[tk]))
                       for tk, n in trovati.items()
                       if tk in inventario and n > inventario[tk])
    in_calo = sorted(("%s: %d < %d" % (tk, trovati.get(tk, 0), atteso))
                     for tk, atteso in inventario.items()
                     if trovati.get(tk, 0) < atteso)
    righe_colpevoli = []
    if nuovi or eccedenze:
        sospetti = set(nuovi) | {e.split(":")[0] for e in eccedenze}
        for n, riga in enumerate(testo.splitlines(), 1):
            if any(tk in riga for tk in sospetti):
                righe_colpevoli.append("r%d: %s" % (n, riga.strip()[:120]))
    return {
        "asserzione": "nessuna stringa di versione nuova o in eccesso in %s" % path_rel,
        "fonte": "US-276 AC5 — «il file e' cresciuto PER accumulo di changelog»",
        "file": path_rel,
        "byte_oggi": len(testo.encode("utf-8")),
        "versione_corrente": corrente,
        "versione_corrente_da_factory_config": letta_da_config,
        "token_liberi": sorted(libere),
        "occorrenze_non_correnti": sum(trovati.values()),
        "tetto_congelato": sum(inventario.values()),
        "token_nuovi": nuovi,
        "eccedenze": eccedenze,
        "in_calo": in_calo,
        "righe": righe_colpevoli[:12],
        "fallita": bool(nuovi or eccedenze),
        "regola_di_lettura": (
            "VERDE NON significa «il file non e' cresciuto»: significa «non e' "
            "cresciuto DI CHANGELOG». Un blocco di prosa senza numeri di versione "
            "passa indisturbato, e il carico si misura con `--load`, non qui. "
            "ROSSO e' un fatto: o una versione nuova o una versione nota in "
            "eccesso. Il rimedio NON e' allargare l'inventario per far passare il "
            "verdetto: e' togliere la riga. Se il tag di provenienza e' legittimo "
            "(una `§capability` nuova), il ri-congelamento e' un atto deliberato, "
            "da dichiarare nel TSK che lo esegue."),
    }

# ─── Sottocomando 2: `censimento` — quali unita' non lo sono mai state? ───────

# Superficie di RAGGIUNGIBILITA' A RUNTIME: da dove un puntatore puo' portare a
# un'unita' durante l'esecuzione. `management/kanban/` e `wiki/` NON sono qui:
# un TSK che nomina una skill e' documentazione, non un arco entrante. Sono
# contati a parte (`riferimenti_documentali`) perche' US-277 deve vedere anche
# quelli prima di cancellare.
# TIER 1 — DISPATCH: cio' che un agente carica o attraverso cui viene instradato.
# E' l'unico tier che decide la classe `irraggiungibile`.
SUPERFICIE_DISPATCH = (("CLAUDE.md",), ("AGENTS.md",))
CARTELLE_DISPATCH = (".claude", ".cursor", "adapters", "tools", "meta-prompts")
# TIER 2 — CATALOGO: spec e cataloghi. Essere ELENCATI in un catalogo non rende
# un'unita' raggiungibile a runtime: nessuno instrada attraverso `CAPABILITIES.md`.
# Il tier esiste perche' il conteggio NON va perso: `test-healing-protocol` (446
# righe) ha esattamente UN arco, ed e' `CAPABILITIES.md`. Metterlo nel tier 1
# tiene l'unita' fuori dalla classe che US-277 cancella; metterlo nel tier 2 ce
# la mette. La scelta e' dichiarata qui e il numero e' riportato accanto a ogni
# unita', perche' e' una scelta che SPOSTA 446 righe e non deve essere invisibile.
SUPERFICIE_CATALOGO = (("PATTERN.md",) + PATTERN_MODULI_NOTI, ("CAPABILITIES.md",), ("CHANGELOG.md",))
CARTELLE_CATALOGO = ()
# TIER 3 — DOCUMENTALE: un TSK o una pagina wiki che nomina una skill e'
# documentazione, non un arco entrante.
CARTELLE_DOCUMENTALI = ("management", "wiki", "design_&_architecture")
_ESTENSIONI_TESTO = {".md", ".mdc", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}

# AC6 sull'asse STATICO: lo strumento di misura non fa parte del corpus misurato.
# Difetto trovato sul proprio output: questo file nomina `test-healing-protocol`
# in un commento, e il censimento contava quel commento come ARCO ENTRANTE —
# tenendo 446 righe fuori dalla classe `irraggiungibile` per il solo fatto di
# essere state misurate. E' l'auto-referenzialita' di AC6 sull'asse sbagliato, e
# il suo effetto e' quello che ASSOLVE: un'unita' morta che resta viva perche'
# lo strumento la nomina.
CARTELLE_ESCLUSE_CORPUS = ("tools/fleet-observer",)


def _file_di_testo(radice_repo, cartelle, file_singoli=()):
    for nomi in file_singoli:
        for nome in nomi:
            f = radice_repo / nome
            if f.is_file():
                yield f
    for nome in cartelle:
        base = radice_repo / nome
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if not (f.is_file() and f.suffix in _ESTENSIONI_TESTO):
                continue
            if "__pycache__" in f.parts:
                continue
            rel = str(f.relative_to(radice_repo))
            if any(rel.startswith(x) for x in CARTELLE_ESCLUSE_CORPUS):
                continue
            yield f


def _conta_archi(radice_repo, slugs, cartelle, file_singoli=()):
    """Archi entranti per unita', in un solo passaggio con la regex alternata.

    Esclude il file dell'unita' stessa e le proprie foglie: un'unita' che nomina
    se stessa non e' raggiungibile da altri.

    ATTENZIONE, difetto trovato sul proprio output prima di pubblicarlo: OTTO
    slug sono CONDIVISI fra due tipi di unita' (`sync-docs`, `repo-sync`,
    `graphify-sync`, `figma-sync`, `token-ledger`, `onboarding`,
    `ponytail-audit`, `ponytail-review` esistono come comando E come
    agente/skill). Una mappa `{slug: unita}` ne collassa uno dei due e regala
    ZERO archi all'altro: la prima versione di questo censimento dichiarava
    `agents/sync-docs`, `agents/repo-sync`, `agents/graphify-sync` e
    `skills/token-ledger` IRRAGGIUNGIBILI — quattro falsi positivi su sei, e la
    classe `irraggiungibile` e' quella su cui US-277 CANCELLA 521 righe. La
    mappa e' quindi slug -> LISTA di unita'.
    """
    if not slugs:
        return {}, {}
    per_unita = {u: 0 for u in slugs}
    esempi = {u: [] for u in slugs}
    regex, mappa = _alternanza(slugs, "menzione")
    for f in _file_di_testo(radice_repo, cartelle, file_singoli):
        rel = str(f.relative_to(radice_repo))
        info = risolvi_unita(rel, radice_repo)
        proprietaria = info.get("unita") if info else None
        try:
            testo = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        visti = collections.Counter()
        for rx in regex:
            for m in rx.finditer(testo):
                visti[m.group(1).lower()] += 1
        for slug, n in visti.items():
            for unita in mappa.get(slug, ()):
                if unita == proprietaria:
                    continue  # se stessa (corpo o propria foglia)
                per_unita[unita] += n
                if len(esempi[unita]) < 5:
                    esempi[unita].append(rel)
    return per_unita, esempi


def censimento(esito, radice_repo):
    """Censimento di RAGGIUNGIBILITA' su due assi indipendenti, mai fusi:

      - STATICO: archi entranti dalla superficie runtime (`.claude/`, `.cursor/`,
        `adapters/`, `tools/`, `meta-prompts/`, `CLAUDE.md`, `PATTERN.md`, ...);
      - TELEMETRIA: accessi / dispatch / invocazioni nella finestra.

    `irraggiungibile` = zero su ENTRAMBI. Zero solo sulla telemetria e' un'altra
    cosa e porta un altro nome (`senza esercizio osservato`): «l'assenza di
    esercizio apre un'istruttoria, NON un taglio» (A-12, vincolo esteso dal
    maintainer). Il censimento non cancella niente: la rimozione e' US-277 e
    richiede la conferma del censimento, non la sua sola esistenza.
    """
    corpi, foglie = inventario_flotta(radice_repo)
    slugs = {u: u.split("/", 1)[1] for u in corpi}

    archi_runtime, esempi_runtime = _conta_archi(
        radice_repo, slugs, CARTELLE_DISPATCH, SUPERFICIE_DISPATCH)
    archi_catalogo, esempi_catalogo = _conta_archi(
        radice_repo, slugs, CARTELLE_CATALOGO, SUPERFICIE_CATALOGO)
    archi_doc, _ = _conta_archi(radice_repo, slugs, CARTELLE_DOCUMENTALI)

    accessi = collections.Counter(r["unita"] for r in esito["record"])
    dispatch = collections.Counter(d["unita"] for d in esito["dispatch"])
    invoc = collections.Counter(i["unita"] for i in esito["invocazioni_skill"])
    # gli accessi alle foglie di un'unita' sono esercizio DELL'UNITA' (A-43)
    voci = []
    for unita, corpo in sorted(corpi.items()):
        eventi = accessi.get(unita, 0) + dispatch.get(unita, 0) + invoc.get(unita, 0)
        statici = archi_runtime.get(unita, 0)
        if statici == 0 and eventi == 0:
            classe = "irraggiungibile"
        elif eventi == 0:
            classe = "senza esercizio osservato"
        elif statici == 0:
            classe = "esercitata senza arco statico"
        else:
            classe = "raggiungibile"
        voci.append({
            "unita": unita, "path": corpo["path"], "righe": corpo["righe"],
            "righe_foglie": sum(f["righe"] for f in foglie.get(unita, [])),
            "classe": classe,
            "archi_statici_runtime": statici,
            "archi_catalogo": archi_catalogo.get(unita, 0),
            "archi_documentali": archi_doc.get(unita, 0),
            "esempi_archi_runtime": esempi_runtime.get(unita, []),
            "esempi_archi_catalogo": esempi_catalogo.get(unita, []),
            "eventi_telemetria": eventi,
            "accessi": accessi.get(unita, 0),
            "dispatch": dispatch.get(unita, 0),
            "invocazioni_skill": invoc.get(unita, 0),
        })

    orfane = [v for v in voci if v["classe"] == "irraggiungibile"]
    senza_esercizio = [v for v in voci if v["classe"] == "senza esercizio osservato"]
    return {
        "unita_censite": len(voci),
        "voci": voci,
        "irraggiungibili": orfane,
        "irraggiungibili_righe": sum(v["righe"] + v["righe_foglie"] for v in orfane),
        "senza_esercizio_osservato": len(senza_esercizio),
        "senza_esercizio_righe": sum(v["righe"] + v["righe_foglie"] for v in senza_esercizio),
        "tier_di_raggiungibilita": {
            "tier1_dispatch": {"cartelle": list(CARTELLE_DISPATCH),
                               "file": [f[0] for f in SUPERFICIE_DISPATCH],
                               "decide_la_classe": True},
            "tier2_catalogo": {"file": [f[0] for f in SUPERFICIE_CATALOGO],
                               "decide_la_classe": False,
                               "nota": "essere elencati in un catalogo non e' "
                                       "raggiungibilita' a runtime; il conteggio "
                                       "e' riportato per unita'"},
            "tier3_documentale": {"cartelle": list(CARTELLE_DOCUMENTALI),
                                  "decide_la_classe": False},
        },
        "puntatore_errata": PUNTATORE_ERRATA,
        "vincolo_a12": (
            "L'assenza di esercizio apre un'ISTRUTTORIA, non un taglio (A-12, "
            "vincolo esteso dal maintainer). Solo la classe `irraggiungibile` "
            "(zero archi statici E zero eventi) e' massa provabilmente morta; la "
            "rimozione resta US-277 e richiede la conferma del censimento."),
        "errata_in_loco": (
            "La premessa «10 ACCEPT» di %s e' falsificata dalla misura di questo "
            "strumento: l'asserzione A-23(i) restituisce 1 accept e 9 reject, e "
            "A-41 aggiunge che 7 su 10 non hanno evidenza di esecuzione. "
            "L'errata vive IN LOCO in %s; `status:` non e' toccato e nessuna "
            "catena di supersedes e' aperta (A-46)." % (PUNTATORE_ERRATA, PUNTATORE_ERRATA)),
        "clausola_c3": {
            "asse": "user-invoked / model-invoked",
            "stato": "OUT con clausola di scadenza",
            "condizione_di_decadenza": "invocazioni per description-match > 0 nel censimento",
            "invocazioni_via_tool_Skill": sum(invoc.values()),
            "invocazioni_per_description_match": None,
            "nota": ("la telemetria non porta un campo che distingua "
                     "l'invocazione per description-match: il valore e' NON "
                     "OSSERVABILE, non zero. La clausola non decade ne' si "
                     "conferma con questo strumento."),
        },
    }

# ─── Sottocomando 3: `--load` — quanto carico, E SU QUALE ADAPTER ─────────────

# AC11 — entry point ALWAYS-ON per adapter, nella factory MISURATA (non nel
# template). Un adapter il cui entry point non e' installato qui ha carico
# always-on 0 IN QUESTA FACTORY, e il report lo dice con `installato: false`
# invece di tacerlo: «"always-on" non ha un valore unico in una factory
# multi-adapter, e un report globale ne inventerebbe uno» (AC11).
ENTRYPOINT_PER_ADAPTER = {
    "claude":  {"file": ["CLAUDE.md", ".claude/CLAUDE.md"], "glob": [], "descrizioni": True},
    "cursor":  {"file": [], "glob": [".cursor/rules/*.md", ".cursor/rules/*.mdc"],
                "descrizioni": False},
    "aider":   {"file": ["CONVENTIONS.md", ".aider.conf.yml"], "glob": [], "descrizioni": False},
    "openai":  {"file": ["AGENTS.md"], "glob": [], "descrizioni": False},
    "gemini":  {"file": ["GEMINI.md", ".gemini/GEMINI.md"], "glob": [], "descrizioni": False},
    "chatgpt": {"file": [], "glob": [], "descrizioni": False},
}

# Superficie TEMPLATE (non installata): il materiale che `/factory-bootstrap`
# depositerebbe se l'adapter venisse attivato. Misurata a parte: confonderla con
# l'always-on installato sarebbe il valore inventato che AC11 vieta.
TEMPLATE_PER_ADAPTER = {
    "claude": "adapters/claude", "cursor": "adapters/cursor",
    "aider": "adapters/aider", "openai": "adapters/openai",
    "gemini": "adapters/gemini", "chatgpt": "adapters/chatgpt",
}

# AC10 — asse AGNOSTICO: cio' che `/factory-bootstrap` e `/factory-upgrade`
# copiano verbatim nelle factory derivate. Non e' always-on per nessun adapter
# ed e' propagato a TUTTI: e' l'asse che un criterio di pulizia su `.claude/`
# non vede.
AGNOSTICO_TARGET = [("file", "PATTERN.md"), ("file", "CHANGELOG.md"),
                    ("file", "CAPABILITIES.md"), ("cartella", "meta-prompts")]

# AC12 — baseline per-sezione DICHIARATA di `PATTERN.md` (righe di CORPO,
# heading escluso). Serve da controllo del parser: se la misura di oggi non
# riproduce la baseline, il disaccordo e' un reperto, non un dettaglio.
PATTERN_SEZIONI_BASELINE = {
    "§20": 465, "§23": 326, "§30": 269, "§19": 241,
    "§13": 234, "§18": 233, "§16": 229, "§15": 213,
}
_RX_SEZIONE_PATTERN = re.compile(r"^##\s+(?:(§[0-9.]+)\s*[—-]\s*)?(.+)$")


def _misura_gruppo(radice_repo, percorsi):
    righe = char = 0
    dettaglio = []
    for p in percorsi:
        if not p.is_file():
            continue
        r, c = misura_file(p)
        righe += r
        char += c
        dettaglio.append({"path": str(p.relative_to(radice_repo)), "righe": r,
                          "char": c, "token_stimati": stima_token(c)})
    return righe, char, dettaglio


def _file_testo_cartella(radice_repo, cartella):
    base = radice_repo / cartella
    if not base.is_dir():
        return []
    return [f for f in sorted(base.rglob("*"))
            if f.is_file() and f.suffix in _ESTENSIONI_TESTO and "__pycache__" not in f.parts]


def carico_per_adapter(radice_repo, corpi):
    """AC11 — report always-on PER-ADAPTER. Nessun aggregato globale."""
    descr_char = sum(c.get("descrizione_char", 0) for c in corpi.values())
    report = {}
    for nome, spec in ENTRYPOINT_PER_ADAPTER.items():
        percorsi = [radice_repo / f for f in spec["file"]]
        for pattern in spec["glob"]:
            percorsi.extend(sorted(radice_repo.glob(pattern)))
        righe, char, dettaglio = _misura_gruppo(radice_repo, percorsi)
        voce = {
            "installato": bool(dettaglio),
            "entry_point_cercati": spec["file"] + spec["glob"],
            "entry_point_trovati": [d["path"] for d in dettaglio],
            "entry_point": {"righe": righe, "char": char, "token_stimati": stima_token(char)},
            "dettaglio": dettaglio,
            "lag_dichiarato": ADAPTER_LAG.get(nome, {}),
        }
        if spec["descrizioni"]:
            voce["descrizioni_unita"] = {
                "unita": len(corpi), "char": descr_char,
                "token_stimati": stima_token(descr_char),
                "nota": "il corpo si carica on-demand, la `description:` no",
            }
            voce["always_on_token_stimati"] = stima_token(char) + stima_token(descr_char)
        else:
            voce["descrizioni_unita"] = None
            voce["always_on_token_stimati"] = stima_token(char)
            voce["descrizioni_nota"] = (
                "questo adapter non carica le `description:` delle unita' "
                "`.claude/`: il suo always-on e' il solo entry point")
        tmpl = TEMPLATE_PER_ADAPTER.get(nome)
        trighe, tchar, _ = _misura_gruppo(radice_repo, _file_testo_cartella(radice_repo, tmpl or ""))
        voce["superficie_template_non_installata"] = {
            "cartella": tmpl, "righe": trighe, "char": tchar,
            "token_stimati": stima_token(tchar),
            "nota": "materiale di scaffolding: NON e' carico always-on di questa factory",
        }
        report[nome] = voce
    return report


def carico_agnostico(radice_repo):
    """AC10 — l'asse agnostico, quello che un criterio su `.claude/` non vede."""
    voci = []
    for genere, nome in AGNOSTICO_TARGET:
        if genere == "file" and nome == "PATTERN.md":
            # US-319: indice + moduli; un PATTERN monolitico resta un file solo.
            percorsi = _pattern_files(radice_repo) or [radice_repo / nome]
        elif genere == "file":
            percorsi = [radice_repo / nome]
        else:
            percorsi = _file_testo_cartella(radice_repo, nome)
        righe, char, dettaglio = _misura_gruppo(radice_repo, percorsi)
        voci.append({"target": nome, "genere": genere, "file": len(dettaglio),
                     "righe": righe, "char": char, "token_stimati": stima_token(char),
                     "dettaglio": dettaglio if genere == "cartella" or len(dettaglio) > 1 else None})
    totale_char = sum(v["char"] for v in voci)
    return {
        "voci": voci,
        "totale": {"righe": sum(v["righe"] for v in voci), "char": totale_char,
                   "token_stimati": stima_token(totale_char)},
        "motivo": ("e' l'artefatto che `/factory-bootstrap` e `/factory-upgrade` "
                   "copiano VERBATIM nelle factory derivate: un criterio di "
                   "pulizia che vive solo su `.claude/` misura un adapter e "
                   "chiama il risultato «la factory»"),
        "baseline_impegnata": None,
        "baseline_nota": ("nessun delta impegnato su questo asse: la baseline "
                          "per-adapter non era mai stata calcolata in questa "
                          "factory. Questo comando PRODUCE la baseline, non un "
                          "miglioramento — «non si impegna un delta su un asse "
                          "che non ha una baseline»"),
    }


def istruttoria_pattern(radice_repo):
    """AC12 — peso PER-SEZIONE di `PATTERN.md`.

    E' un'ISTRUTTORIA: l'assenza di esercizio apre un'istruttoria, NON un taglio
    (A-12, vincolo esteso dal maintainer). **Nessuna sezione viene rimossa in
    questo EP**, e questo strumento non ha alcun path di scrittura su PATTERN.md.
    """
    # US-319: indice + moduli. Ogni file si misura per conto suo: una sezione finisce
    # dove finisce il suo file, e la riga di testa di un modulo non e' corpo di nessuno.
    percorsi = _pattern_files(radice_repo) or [radice_repo / "PATTERN.md"]
    righe_tot = char_tot = 0
    sezioni = []
    for percorso in percorsi:
        r_f, c_f = misura_file(percorso)
        righe_tot += r_f
        char_tot += c_f
        sezioni.extend(_sezioni_di(percorso))
    sezioni.sort(key=lambda s: -s["righe_corpo"])
    controllate = [s for s in sezioni if s["baseline_dichiarata"] is not None]
    return {
        "file": "PATTERN.md", "moduli": [p.name for p in percorsi[1:]],
        "righe": righe_tot, "char": char_tot,
        "token_stimati": stima_token(char_tot),
        "sezioni_totali": len(sezioni),
        "sezioni": sezioni,
        "controllo_baseline": {
            "sezioni_controllate": len(controllate),
            "concordanti": sum(1 for s in controllate if s["concorda_con_baseline"]),
            "convenzione": "righe di corpo, heading `## ` escluso",
        },
        "vincolo": ("NESSUNA SEZIONE DI PATTERN.md VIENE RIMOSSA IN QUESTO EP "
                    "(A-12 esteso dal maintainer): l'assenza di esercizio apre "
                    "un'ISTRUTTORIA, non un taglio. Questo strumento e' read-only "
                    "e non ha alcun path di scrittura su PATTERN.md."),
    }


def _sezioni_di(percorso):
    """Sezioni `## ` di UN file del PATTERN (indice o modulo), corpo heading escluso."""
    try:
        righe = percorso.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        righe = []
    intestazioni = []
    for i, riga in enumerate(righe):
        m = _RX_SEZIONE_PATTERN.match(riga)
        if m:
            intestazioni.append((i, m.group(1), m.group(2).strip()))
    sezioni = []
    for j, (i, num, titolo) in enumerate(intestazioni):
        fine = intestazioni[j + 1][0] if j + 1 < len(intestazioni) else len(righe)
        corpo = fine - i - 1  # heading escluso: e' la convenzione della baseline
        char_sez = sum(len(r.encode("utf-8")) + 1 for r in righe[i + 1:fine])
        atteso = PATTERN_SEZIONI_BASELINE.get(num or "")
        sezioni.append({
            "sezione": num, "titolo": titolo, "file": percorso.name, "riga_iniziale": i + 1,
            "righe_corpo": corpo, "char": char_sez, "token_stimati": stima_token(char_sez),
            "baseline_dichiarata": atteso,
            "concorda_con_baseline": (corpo == atteso) if atteso is not None else None,
        })
    return sezioni


def stato_a37(radice_repo):
    """AC13 / A-37 — stato MISURATO della riga `superseded_by:` nel check.

    Lo strumento non modifica `complexity-budget-check` e non lo cancella: la
    cancellazione richiede la question Q-005 (TSK-647), perche' «documentare un
    difetto misurato e' dentro l'autorita' di un agente; porre fine a un
    controllo istituito da un ADR `accepted` non lo e'». Qui si MISURA se la riga
    e' presente e si espone la riga esatta da stampare: uno stato dichiarato
    senza misura sarebbe la classe dello «zero fiducioso».
    """
    percorso = radice_repo / CHECK_SUPERSEDUTO
    esiste = percorso.is_file()
    presente = False
    if esiste:
        try:
            presente = "superseded_by" in percorso.read_text(encoding="utf-8", errors="replace")
        except OSError:
            presente = False
    return {
        "check": CHECK_SUPERSEDUTO,
        "check_esiste": esiste,
        "riga_da_stampare": RIGA_SUPERSEDED_BY,
        "riga_presente_nel_check": presente,
        "metrica_di_record_unica": "tools/fleet-observer/observe.py --load",
        "verdetto_del_check_nel_release_gate": (
            "deve USCIRE dalla checklist del release gate (Check 4v, "
            ".claude/skills/lint-checks-governance.md), dove non era vincolante "
            "per design: nulla si scarica su di esso"),
        "check_cancellato": False,
        "cancellazione_richiede": "question Q-005 (TSK-647) — non e' autorita' di un agente",
    }


def carico(radice_repo):
    """`--load`: always-on per-adapter (AC11) + asse agnostico (AC10) +
    istruttoria PATTERN (AC12) + on-demand, in un solo blocco JSON."""
    corpi, foglie = inventario_flotta(radice_repo)
    righe_corpi = sum(c["righe"] for c in corpi.values())
    char_corpi = sum(c["char"] for c in corpi.values())
    righe_foglie = sum(f["righe"] for lista in foglie.values() for f in lista)
    char_foglie = sum(f["char"] for lista in foglie.values() for f in lista)
    per_adapter = carico_per_adapter(radice_repo, corpi)
    agnostico = carico_agnostico(radice_repo)
    pattern = istruttoria_pattern(radice_repo)
    claude_char = per_adapter["claude"]["entry_point"]["char"] or 0
    return {
        "stima_token": ("byte // 4 — stima riproducibile, non un tokenizer "
                        "(zero dipendenze, AC17). Verifica del metodo sulla "
                        "baseline 2026-09-21 PRE-TSK-651: CLAUDE.md = 49.924 "
                        "byte // 4 = 12.481 token, esattamente il valore "
                        "dichiarato in EP-065 §Delta di massa netto. La misura "
                        "corrente del file e' nel blocco always_on_per_adapter, "
                        "non qui"),
        "always_on_per_adapter": per_adapter,
        "always_on_globale": None,
        "always_on_globale_motivo": (
            "NON CALCOLATO PER SCELTA: «always-on» non ha un valore unico in una "
            "factory multi-adapter e un report globale ne inventerebbe uno (AC11). "
            "I sette adapter hanno entry point diversi e lag diversi."),
        "agnostico": agnostico,
        "on_demand": {
            "corpi": {"unita": len(corpi), "righe": righe_corpi, "char": char_corpi,
                      "token_stimati": stima_token(char_corpi)},
            "foglie": {"unita_con_foglie": len(foglie),
                       "file": sum(len(l) for l in foglie.values()),
                       "righe": righe_foglie, "char": char_foglie,
                       "token_stimati": stima_token(char_foglie)},
            "regola_di_lettura": ("una crescita dell'asse on-demand senza un calo "
                                  "dell'asse always-on e' DUPLICAZIONE, non "
                                  "spostamento (A-6)"),
        },
        "istruttoria_pattern": pattern,
        "rapporto_pattern_su_entrypoint_claude": (
            round(pattern["char"] / claude_char, 2) if claude_char else None),
        "confronto_baseline_registro": {
            "always_on_claude_dichiarato_token": 18779,
            "always_on_claude_dichiarato_unita": 136,
            "always_on_claude_misurato_token":
                per_adapter["claude"]["always_on_token_stimati"],
            "always_on_claude_misurato_unita": len(corpi),
            "nota": ("il registro ha misurato 136 unita'; il repo ne ha %d oggi. "
                     "La differenza NON e' un delta di miglioramento ne' di "
                     "peggioramento: e' un universo diverso, e va letta da "
                     "US-276 prima di impegnare -6.200 token su questo asse."
                     % len(corpi)),
            "descrizione_piu' pesante": max(
                ((u, c.get("descrizione_char", 0)) for u, c in corpi.items()),
                key=lambda kv: kv[1], default=(None, 0)),
        },
        "a37": stato_a37(radice_repo),
    }

# ─── Stampa umana dei tre sottocomandi ───────────────────────────────────────

def righe_osservabilita(oss):
    """AC8 — la riga `osservabilità: X/Y` piu' la tripla e il divieto di lettura.
    Stampata da OGNI sottocomando: il numero non viaggia mai senza il significato.
    """
    righe = [
        "  %s   (divergente %d · invariato %d · non osservabile %d%s)"
        % (oss["riga"], oss["divergente"], oss["invariato"], oss["non osservabile"],
           ", a credito no-refactor %d" % oss["a_credito_no_refactor"]
           if oss["a_credito_no_refactor"] else ""),
        "    divergente       = %s" % VERDETTI_SIGNIFICATO["divergente"],
        "    invariato        = %s" % VERDETTI_SIGNIFICATO["invariato"],
        "    non osservabile  = %s" % VERDETTI_SIGNIFICATO["non osservabile"],
        "    %s" % DIVIETO_ENUNCIATO_DI_CONFORMITA,
    ]
    tel = oss.get("telemetria_assente")
    if tel:
        # Nessuna delle due righe contiene la parola «osservabilita'»: la riga
        # di AC8 deve restare UNA, ed e' il contract test a pretenderlo.
        righe.append("    TELEMETRIA ASSENTE — verdetto `%s`: %s"
                     % (tel["verdetto"], tel["ragione"]))
        righe.append("    Non e' un errore ma ASSENZA DI INFORMAZIONE: exit %d "
                     "(TSK-655)." % tel["exit"])
    return righe


def _righe_testata(out, titolo):
    m = out["meta"]
    righe = [
        "osservatore della flotta — %s" % titolo,
        "  finestra:   %s   (sessioni %d, aperte escluse %d, fuori finestra %d)"
        % (m["finestra"]["regola"], m["sessioni_analizzate"],
           m["esclusioni"]["sessioni_aperte"], m["esclusioni"]["sessioni_fuori_finestra"]),
        "  canali:     Read %d · Bash read-like %d (rapporto %s) — nessuno e' ground truth"
        % (m["canali"]["Read"], m["canali"]["Bash"], m["canali"]["rapporto_bash_su_read"]),
        "  schema:     %s (degradato: %s)"
        % (", ".join(sorted(m["schema_guard"]["viste"])) or "-", m["schema_guard"]["degradato"]),
    ]
    if m["schema_guard"]["degradato"]:
        righe.append(
            "  ATTENZIONE: lo schema-guard di EP-062 e' SCADUTO — versioni non "
            "supportate nella finestra: %s. Il parsing di quelle sessioni e' in "
            "modalita' DEGRADATA e il WARNING su stderr non e' silenziato. "
            "`SUPPORTED_CC_VERSIONS` vive in tools/analytics/harvest-session-tokens.py "
            "e vieta l'aggiunta di versioni senza verifica empirica: FUORI SCOPE "
            "di TSK-648, va aperto un TSK proprio (classe EP-062)."
            % ", ".join(sorted(m["schema_guard"]["non_supportate"])))
    return righe


def stampa_differ(out):
    r = _righe_testata(out, "differ di invocazione (`--differ`)")
    r += righe_osservabilita(out["meta"]["osservabilita"])
    r.append("")
    r.append("  la domanda: le unita' DICHIARATE OBBLIGATORIE vengono raggiunte?")
    r.append("  %-38s %-16s %s" % ("unita'", "verdetto", "misura"))
    for v in out["differ"]["verdetti"]:
        r.append("  %-38s %-16s esec %d · foglie obbligate %d/%d · accessi obblig %d · corpo %d"
                 % (v["unita"], v["verdetto"], v["esecuzioni_osservate"],
                    len(v["obbligazione"]["foglie_obbligate"]),
                    len(v["obbligazione"]["per_foglia"]),
                    v["accessi_foglie_obbligate_sotto_esecuzione"], v["accessi_corpo"]))
        r.append("      %s" % v["motivo"])
        for nome in ("criterio_largo", "criterio_propagato"):
            alt = v[nome]
            if alt["differisce"]:
                r.append("      [%s] sarebbe `%s` (%d esecuzioni): %s"
                         % (nome.replace("criterio_", "criterio "), alt["verdetto"],
                            alt["esecuzioni_osservate"], alt["definizione"]))
    div = [v for v in out["differ"]["verdetti"] if v["verdetto"] == "divergente"]
    if div:
        r.append("")
        r.append("  EVIDENZA NOMINATA dei `divergente` (A-41: verdetto + evidenza + comando):")
        for v in div:
            r.append("   · %s" % v["unita"])
            for f in v["obbligazione"]["per_foglia"]:
                r.append("     foglia %-58s %-9s accessi esec %d · trigger %s [%s]"
                         % (f["foglia"].split("references/")[-1],
                            "OBBLIGATA" if f["obbligata"] else "non obbl.",
                            f["accessi_sotto_esecuzione"],
                            ", ".join(f["trigger"]) or "nessuno", f["trigger_fonte"]))
                for ec in f["config_at_ts_evidenza"][:2]:
                    r.append("        config@ts %s -> commit %s (%s): %s"
                             % (ec["ts"], ec["config_commit"], ec["config_commit_ts"],
                                ec["flags"]))
            for ev in v["evidenza"][:6]:
                r.append("     esecuzione %s  [%s]" % (ev.get("ts"), ev.get("fonte")))
                if ev.get("estratto"):
                    r.append("        mandato: %s" % ev["estratto"][:150])
            r.append("     comando che riproduce: python3 tools/fleet-observer/observe.py "
                     "--differ --unita %s" % v["unita"])
    r.append("")
    r.append("  exit %d — %s" % (out["differ"]["exit_code"], out["differ"]["exit_motivo"]))
    return "\n".join(r)


def stampa_censimento(out, solo_orfane=False):
    c = out["censimento"]
    r = _righe_testata(out, "censimento di raggiungibilita' (`censimento`)")
    r += righe_osservabilita(out["meta"]["osservabilita"])
    r.append("")
    r.append("  unita' censite: %d · irraggiungibili: %d (%d righe corpo+foglie) · "
             "senza esercizio osservato: %d (%d righe)"
             % (c["unita_censite"], len(c["irraggiungibili"]), c["irraggiungibili_righe"],
                c["senza_esercizio_osservato"], c["senza_esercizio_righe"]))
    r.append("")
    r.append("  IRRAGGIUNGIBILI — zero archi statici runtime E zero eventi di telemetria:")
    for v in c["irraggiungibili"]:
        r.append("   · %-45s %4d righe  dispatch %d · catalogo %d%s · documentali %d · eventi %d"
                 % (v["unita"], v["righe"], v["archi_statici_runtime"],
                    v["archi_catalogo"],
                    " (%s)" % ", ".join(v["esempi_archi_catalogo"]) if v["esempi_archi_catalogo"] else "",
                    v["archi_documentali"], v["eventi_telemetria"]))
    if not c["irraggiungibili"]:
        r.append("   (nessuna)")
    if not solo_orfane:
        r.append("")
        r.append("  SENZA ESERCIZIO OSSERVATO — hanno archi entranti, zero eventi nella "
                 "finestra. A-12: ISTRUTTORIA, NON TAGLIO:")
        for v in sorted(c["voci"], key=lambda v: -v["righe"]):
            if v["classe"] != "senza esercizio osservato":
                continue
            r.append("   · %-45s %4d righe  archi runtime %d"
                     % (v["unita"], v["righe"], v["archi_statici_runtime"]))
    r.append("")
    r.append("  La classe `irraggiungibile` NON autorizza la cancellazione: gli "
             "archi di catalogo e documentali elencati sopra esistono e US-277 "
             "deve aggiornarli. Il tier che decide la classe e' il solo tier 1 "
             "(dispatch): %s + %s."
             % (", ".join(CARTELLE_DISPATCH), ", ".join(f[0] for f in SUPERFICIE_DISPATCH)))
    r.append("  %s" % c["vincolo_a12"])
    r.append("")
    r.append("  PUNTATORE ALL'ERRATA IN LOCO: %s" % c["puntatore_errata"])
    r.append("    %s" % c["errata_in_loco"])
    r.append("")
    r.append("  clausola C3 (`invocation:`): invocazioni via tool `Skill` = %d · "
             "per description-match = %s"
             % (c["clausola_c3"]["invocazioni_via_tool_Skill"],
                c["clausola_c3"]["invocazioni_per_description_match"]))
    r.append("    %s" % c["clausola_c3"]["nota"])
    return "\n".join(r)


def stampa_load(out):
    l = out["load"]
    r = _righe_testata(out, "misura del carico (`--load`)")
    r += righe_osservabilita(out["meta"]["osservabilita"])
    r.append("")
    r.append("  ALWAYS-ON PER-ADAPTER (AC11 — nessun aggregato globale: ne inventerebbe uno)")
    r.append("  %-9s %-11s %-16s %10s %10s  %s" %
             ("adapter", "installato", "contract/maturita", "entry byte",
              "always-on", "entry point"))
    for nome, v in l["always_on_per_adapter"].items():
        lag = v["lag_dichiarato"]
        r.append("  %-9s %-11s %-16s %10d %10d  %s"
                 % (nome, "si" if v["installato"] else "NO",
                    "%s/%s" % (lag.get("contract") or "-", lag.get("maturita") or "-"),
                    v["entry_point"]["char"], v["always_on_token_stimati"],
                    ", ".join(v["entry_point_trovati"]) or "(assente in questa factory)"))
    claude = l["always_on_per_adapter"]["claude"]
    if claude.get("descrizioni_unita"):
        d = claude["descrizioni_unita"]
        r.append("    claude: entry %d token + %d `description:` di %d unita' = %d token"
                 % (claude["entry_point"]["token_stimati"], d["token_stimati"],
                    d["unita"], claude["always_on_token_stimati"]))
    cb = l["confronto_baseline_registro"]
    r.append("    baseline del registro: %d token su %d unita' · misurato ora: "
             "%d token su %d unita' (universo diverso, non un delta)"
             % (cb["always_on_claude_dichiarato_token"],
                cb["always_on_claude_dichiarato_unita"],
                cb["always_on_claude_misurato_token"],
                cb["always_on_claude_misurato_unita"]))
    r.append("    description piu' pesante: %s (%d byte)" % cb["descrizione_piu' pesante"])
    r.append("    lag come CONTESTO DI LETTURA, non come difetto di questo EP: un "
             "contenuto che atterra solo in `.claude/` non raggiunge nessuno degli altri.")
    r.append("")
    r.append("  ASSE AGNOSTICO (AC10) — copiato VERBATIM nelle factory derivate")
    for v in l["agnostico"]["voci"]:
        r.append("   · %-16s %5d righe %9d byte %8d token  (%d file)"
                 % (v["target"], v["righe"], v["char"], v["token_stimati"], v["file"]))
    t = l["agnostico"]["totale"]
    r.append("   = totale agnostico: %d righe · %d byte · %d token stimati"
             % (t["righe"], t["char"], t["token_stimati"]))
    r.append("   PATTERN.md / entry point claude = %sx" % l["rapporto_pattern_su_entrypoint_claude"])
    r.append("   %s" % l["agnostico"]["baseline_nota"])
    r.append("")
    r.append("  ON-DEMAND: %d corpi %d righe (%d token) · %d foglie %d righe (%d token)"
             % (l["on_demand"]["corpi"]["unita"], l["on_demand"]["corpi"]["righe"],
                l["on_demand"]["corpi"]["token_stimati"], l["on_demand"]["foglie"]["file"],
                l["on_demand"]["foglie"]["righe"], l["on_demand"]["foglie"]["token_stimati"]))
    r.append("   %s" % l["on_demand"]["regola_di_lettura"])
    r.append("")
    p = l["istruttoria_pattern"]
    r.append("  ISTRUTTORIA `PATTERN.md` (AC12) — %d righe, %d char, %d sezioni `##`"
             % (p["righe"], p["char"], p["sezioni_totali"]))
    r.append("  %-6s %-52s %6s %8s %s" % ("sez", "titolo", "righe", "token", "baseline"))
    for s in p["sezioni"][:12]:
        base = s["baseline_dichiarata"]
        marca = "-" if base is None else ("%d %s" % (base, "ok" if s["concorda_con_baseline"] else "DIVERGE"))
        r.append("  %-6s %-52s %6d %8d %s"
                 % (s["sezione"] or "-", s["titolo"][:52], s["righe_corpo"],
                    s["token_stimati"], marca))
    cb = p["controllo_baseline"]
    r.append("   controllo baseline dichiarata: %d/%d sezioni concordanti (%s)"
             % (cb["concordanti"], cb["sezioni_controllate"], cb["convenzione"]))
    r.append("   %s" % p["vincolo"])
    r.append("")
    a = out["asserzione_a23i"]
    r.append("  ASSERZIONE A-23(i) — %s" % a["asserzione"])
    for e in a["esiti"]:
        r.append("   %-14s %-45s %s" % (e["esito"], e["unita"], e["nota"]))
    r += righe_drift(a)
    r.append("   %s" % a["regola_di_lettura"])
    r.append("   exit code nel path: `--load --asserzione` esce != 0 su asserzione fallita")
    r.append("")
    r += righe_anti_ricrescita(out["asserzione_anti_ricrescita"])
    r.append("")
    a37 = l["a37"]
    r.append("  %s" % RIGA_SUPERSEDED_BY)
    r.append("   (riga che `%s` deve stampare nel proprio output — A-37; "
             "stato misurato: presente = %s)"
             % (a37["check"], a37["riga_presente_nel_check"]))
    r.append("   metrica di record unica: %s" % a37["metrica_di_record_unica"])
    r.append("   %s" % a37["verdetto_del_check_nel_release_gate"])
    r.append("   il check NON e' cancellato: %s" % a37["cancellazione_richiede"])
    return "\n".join(r)


def righe_drift(a, indent="   "):
    """Il drift datato al posto di `concorda: <bool>` (TSK-657).

    Poche righe, sempre stampate: il conteggio di oggi, lo snapshot con la sua
    data, e che cosa si e' mosso da che parte. Se nulla si e' mosso lo dice —
    «invariato su 11 unita'» e' un'informazione, `concorda: True` era un
    giudizio.
    """
    d = a["drift_dal_snapshot"]
    r = ["%sconteggio oggi: %s" % (indent, a["conteggio"]),
         "%sDRIFT dallo snapshot %s — snapshot %s · oggi %s%s"
         % (indent, d["snapshot"],
            d["snapshot_riferimento"]["conteggio_per_unita"], d["conteggio_oggi"],
            "" if d["per_unita_concorda_col_registro"] else
            "  [ATTENZIONE: la tabella per-unita' NON somma all'aggregato "
            "congelato dal registro %s: lo snapshot e' stato ritoccato]"
            % d["snapshot_riferimento"]["conteggio_registro"])]
    for chiave, etichetta in (("miglioramenti", "MIGLIORAMENTO"),
                              ("regressioni", "REGRESSIONE"),
                              ("movimenti_di_direzione_indefinita", "MOVIMENTO")):
        for v in d[chiave]:
            r.append("%s %-14s %-45s %s -> %s%s"
                     % (indent, etichetta, v["unita"], v["da"], v["a"],
                        "" if v["delta_oggi"] is None else
                        " (oggi %+d righe sulla baseline)" % v["delta_oggi"]))
    if not d["mosse"]:
        r.append("%s nessun movimento: %d unita' invariate rispetto allo snapshot"
                 % (indent, len(d["invariati"])))
    else:
        r.append("%s invariati: %d unita' — %s"
                 % (indent, len(d["invariati"]), ", ".join(d["invariati"]) or "-"))
    for v in d["unita_fuori_snapshot"]:
        r.append("%s FUORI SNAPSHOT %-45s oggi %s (nessun riferimento congelato)"
                 % (indent, v["unita"], v["oggi"]))
    if d["unita_uscite_dalla_campagna"]:
        r.append("%s nello snapshot ma non nella campagna di oggi: %s"
                 % (indent, ", ".join(d["unita_uscite_dalla_campagna"])))
    r.append("%s%s" % (indent, d["regola_di_lettura"]))
    return r


def righe_anti_ricrescita(ar):
    """Poche righe, sempre stampate: un'asserzione che non si vede non frena
    nulla. L'inventario non viene elencato — il tetto e il conteggio bastano a
    dire se il file sta riaccumulando changelog."""
    r = ["  ASSERZIONE ANTI-RICRESCITA (US-276 AC5) — %s" % ar["asserzione"]]
    if ar.get("file_assente"):
        r.append("   %s" % ar["nota"])
        return r
    r.append("   %s: %d byte · versione corrente %s (da factory.config.yaml: %s)"
             % (ar["file"], ar["byte_oggi"], ar["versione_corrente"],
                ar["versione_corrente_da_factory_config"]))
    r.append("   occorrenze di versioni non correnti: %d · tetto congelato: %d -> %s"
             % (ar["occorrenze_non_correnti"], ar["tetto_congelato"],
                "ROSSA" if ar["fallita"] else "verde"))
    if ar["token_nuovi"]:
        r.append("   VERSIONI NUOVE (nessuna sede legittima): %s"
                 % ", ".join(ar["token_nuovi"]))
    for e in ar["eccedenze"]:
        r.append("   ECCEDENZA %s" % e)
    for riga in ar["righe"]:
        r.append("     %s" % riga)
    if ar["in_calo"] and not ar["fallita"]:
        r.append("   in calo rispetto all'inventario (lecito, da ri-congelare "
                 "deliberatamente): %s" % ", ".join(ar["in_calo"]))
    r.append("   exit code nel path: `--load --asserzione` esce %d su ricrescita"
             % EXIT_RICRESCITA)
    r.append("   %s" % ar["regola_di_lettura"])
    return r

def stampa_asserzione(out):
    a = out["asserzione_a23i"]
    r = ["osservatore della flotta — asserzione A-23(i)"]
    r += righe_osservabilita(out["meta"]["osservabilita"])
    r.append("")
    r.append("  %s" % a["asserzione"])
    r.append("  %-14s %-45s %-9s %7s %7s %7s"
             % ("esito", "unita'", "baseline", "corpo", "foglie", "totale"))
    for e in a["esiti"]:
        r.append("  %-14s %-45s %-9s %7s %7d %7d"
                 % (e["esito"], e["unita"],
                    "%s:%s" % (e["baseline_sha"], e["baseline_righe_misurate"]),
                    e["righe_corpo_oggi"], e["righe_foglie_oggi"], e["totale_oggi"]))
    r += righe_drift(a, indent="  ")
    r.append("  %s" % a["regola_di_lettura"])
    r.append("")
    r += righe_anti_ricrescita(out["asserzione_anti_ricrescita"])
    return "\n".join(r)


def costruisci_output(esito, radice_repo, cartella, giorno_esclusivo,
                      sottocomando="mandato"):
    cnt = esito["contatori"]
    regole = {k[len("regola_"):]: v for k, v in cnt.items() if k.startswith("regola_")}
    classificati_positivi = sum(v for k, v in regole.items() if not k.startswith("R-CIT-DEFAULT"))
    return {
        "meta": {
            "strumento": "tools/fleet-observer/observe.py",
            "sottocomando": sottocomando,
            "tsk": "TSK-642 (parsing) + TSK-648 (tre sottocomandi, un JSON)",
            "generato_il": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "radice_repo": str(radice_repo),
            "cartella_transcript": str(cartella),
            "finestra": {
                "giornata_authoring_esclusa": giorno_esclusivo,
                "regola": "ts[:10] > %s (AC6, non allargabile)" % giorno_esclusivo,
            },
            "sessioni_analizzate": len(esito["sessioni"]),
            "sessioni": esito["sessioni"],
            "schema_guard": {
                "fonte": esito["schema_guard_fonte"],
                "supportate": sorted(versioni_cc_supportate()[0]),
                "viste": dict(esito["cc_versions"]),
                "non_supportate": sorted(esito["non_supportate"]),
                "degradato": bool(esito["non_supportate"]),
            },
            "config_at_ts": {
                "file": "factory.config.yaml",
                "metodo": "git show <commit-at-ts>:factory.config.yaml",
                "errore": esito.get("config_errore"),
            },
            # TSK-655 — telemetria assente: verdetto `non osservabile` con la
            # ragione, exit 0. Il campo c'e' SEMPRE: un output che tacesse
            # sull'assenza di telemetria si leggerebbe come una misura.
            # Nel caso normale il campo e' il solo `assente: False`: la
            # cartella e' gia' in `cartella_transcript` e ripeterla renderebbe
            # volatile un campo che non ha ragione di esserlo.
            "telemetria": esito.get("telemetria_assente") or {"assente": False},
            "transcript_con_mandato": len(esito["mandati"]),
            "mandati_per_classe": {
                "esecuzione": cnt.get("mandato_esecuzione", 0),
                "manutenzione": cnt.get("mandato_manutenzione", 0),
                "citazione": cnt.get("mandato_citazione", 0),
            },
            "mandato_effettivo_per_classe": {
                "esecuzione": cnt.get("mandato_effettivo_esecuzione", 0),
                "manutenzione": cnt.get("mandato_effettivo_manutenzione", 0),
                "citazione": cnt.get("mandato_effettivo_citazione", 0),
            },
            "regole": regole,
            "classificazione": {
                "da_match_positivo": classificati_positivi,
                "da_default": sum(v for k, v in regole.items() if k.startswith("R-CIT-DEFAULT")),
            },
            "canali": {
                "Read": cnt.get("canale_Read", 0),
                "Bash": cnt.get("canale_Bash", 0),
                "rapporto_bash_su_read": (
                    round(cnt.get("canale_Bash", 0) / cnt["canale_Read"], 2)
                    if cnt.get("canale_Read") else None),
                "nessuno_e_ground_truth": True,
            },
            "esclusioni": {
                "sessioni_fuori_finestra": cnt.get("sessioni_fuori_finestra", 0),
                "sessioni_aperte": cnt.get("sessioni_aperte_escluse", 0),
                "tool_use_fuori_finestra": cnt.get("fuori_finestra", 0),
                "transcript_auto_referenziali": cnt.get("transcript_auto_referenziali", 0),
                "accessi_auto_referenziali": cnt.get("esclusi_auto_referenziali", 0),
                "accessi_fuori_repo": cnt.get("fuori_repo", 0),
                "bash_dir_scan_ignorati": cnt.get("bash_dir_scan_ignorati", 0),
                "accessi_non_unita": cnt.get("accessi_non_unita", 0),
                "righe_malformate": cnt.get("righe_malformate", 0),
            },
            "asse": {
                "regola": "AC5 — unita'-agente ancorate al solo asse foglia",
                "accessi_su_asse_non_ancorante": cnt.get("asse_non_ancorante", 0),
            },
            "mutazioni_rilevate": cnt.get("mutazioni", 0),
            "dispatch": cnt.get("dispatch", 0),
            "invocazioni_skill": cnt.get("invocazioni_skill", 0),
            "asse_agnostico": {
                "implementato": ["risoluzione unita' agnostiche (PATTERN.md, "
                                 "CHANGELOG.md, CAPABILITIES.md, meta-prompts/)",
                                 "risoluzione entry point per-adapter",
                                 "tabella ADAPTER_LAG come contesto di lettura"],
                "predisposto_per_TSK-648": ["report per-adapter (AC11)",
                                            "peso per-sezione di PATTERN.md (AC12)",
                                            "misura del carico --load (AC10)"],
                "adapter_lag": ADAPTER_LAG,
            },
            "invariante_di_lettura": INVARIANTE_DI_LETTURA,
            "limiti_dichiarati": LIMITI_DICHIARATI,
            "non_implementato_qui": [
                "fixture reale + contract test, incluse le 3 fixture di "
                "regressione di A-49 (TSK-649): finche' non esistono, questo "
                "strumento non e' mai stato verificato da nessuno tranne i suoi "
                "autori — «un osservatore scritto una volta e mai riverificato "
                "produce uno zero fiducioso»",
            ],
        },
        "mandati": esito["mandati"],
        "record": esito["record"],
        "dispatch": esito["dispatch"],
        "invocazioni_skill": esito["invocazioni_skill"],
    }


# ─── Entry point: UN SOLO tool, tre sottocomandi, UN formato JSON (AC1) ──────

# I tre sottocomandi della domanda + `mandato`, che espone il layer di parsing
# di TSK-642. `--differ` / `--load` / `--censimento` sono accettati anche nella
# forma con i trattini, perche' e' la forma in cui il registro li ha congelati.
SOTTOCOMANDI = ("mandato", "differ", "censimento", "load")
EXIT_OK = 0
EXIT_USO = 1
EXIT_DIPENDENZA = 4
EXIT_DIVERGENTE = 5
EXIT_ASSERZIONE = 6
# 7 e' DISTINTO da 6 di proposito: A-23(i) e' rossa oggi (9 reject), quindi
# un'asserzione anti-ricrescita che condividesse il codice 6 sarebbe
# INOSSERVABILE — «un verdetto che non puo' cambiare l'exit code non e' un
# verdetto». Ha precedenza su 6 quando entrambe fallono.
EXIT_RICRESCITA = 7


def _normalizza_argv(argv):
    """Porta il sottocomando in testa e accetta gli alias con i trattini.

    `observe.py --load --json` e `observe.py load --json` sono lo stesso comando:
    il registro nomina `--differ` e `--load` con i trattini e `censimento` senza,
    e un tool che accetta solo una delle due forme costringe chi legge il
    registro a indovinare.
    """
    argv = list(argv)
    for i, token in enumerate(argv):
        nudo = token[2:] if token.startswith("--") else token
        if nudo in SOTTOCOMANDI:
            argv.pop(i)
            return [nudo] + argv
    return argv


def stampa_mandato(out):
    m = out["meta"]
    righe = [
        "osservatore della flotta — layer di parsing (`mandato`)",
        "  transcript: %s  (sessioni analizzate: %d, aperte escluse: %d, fuori finestra: %d)"
        % (m["cartella_transcript"], m["sessioni_analizzate"],
           m["esclusioni"]["sessioni_aperte"], m["esclusioni"]["sessioni_fuori_finestra"]),
        "  finestra:   %s" % m["finestra"]["regola"],
        "  mandati:    esecuzione %d · manutenzione %d · citazione %d  (su %d transcript)"
        % (m["mandati_per_classe"]["esecuzione"], m["mandati_per_classe"]["manutenzione"],
           m["mandati_per_classe"]["citazione"], m["transcript_con_mandato"]),
        "  di cui da default (R-CIT-DEFAULT): %d" % m["classificazione"]["da_default"],
        "  canali:     Read %d · Bash read-like %d  (rapporto %s) — nessuno e' ground truth"
        % (m["canali"]["Read"], m["canali"]["Bash"], m["canali"]["rapporto_bash_su_read"]),
        "  esclusi:    auto-referenziali %d accessi in %d transcript · fuori repo %d · dir-scan non attribuiti %d"
        % (m["esclusioni"]["accessi_auto_referenziali"], m["esclusioni"]["transcript_auto_referenziali"],
           m["esclusioni"]["accessi_fuori_repo"], m["esclusioni"]["bash_dir_scan_ignorati"]),
        "  record:     %d (asse non ancorante: %d)" % (len(out["record"]), m["asse"]["accessi_su_asse_non_ancorante"]),
        "  schema:     %s (degradato: %s)" % (", ".join(sorted(m["schema_guard"]["viste"])) or "-",
                                              m["schema_guard"]["degradato"]),
        "",
        "  " + INVARIANTE_DI_LETTURA,
        "  I verdetti sono in `--differ` / `censimento` / `--load`.",
    ]
    righe[8:8] = righe_osservabilita(m["osservabilita"])
    return "\n".join(righe)


def main(argv=None):
    argv = _normalizza_argv(list(sys.argv[1:] if argv is None else argv))

    comune = argparse.ArgumentParser(add_help=False)
    comune.add_argument("--json", action="store_true",
                        help="output JSON (default: sommario leggibile). UN SOLO "
                             "formato condiviso dai tre sottocomandi")
    comune.add_argument("--unita", default=None,
                        help="filtra su una singola unita' (es. skills/dev-protocol)")
    comune.add_argument("--da", default=GIORNATA_AUTHORING, metavar="YYYY-MM-DD",
                        help="giornata esclusiva di inizio finestra; puo' solo "
                             "restringere, mai allargare oltre %s (AC6)" % GIORNATA_AUTHORING)
    comune.add_argument("--repo-root", default=None,
                        help="radice del repo misurato (default: git rev-parse)")
    comune.add_argument("--projects-dir", default=None,
                        help="cartella dei transcript (default: ~/.claude/projects/"
                             "<mangled>); usata dalle fixture di TSK-649")
    comune.add_argument("--foglie-snapshot", default=None, metavar="FILE.json",
                        help="inventario delle foglie CONGELATO da usare al posto "
                             "del filesystem nei soli verdetti del differ "
                             "(fixture di regressione di A-49, TSK-657). "
                             "censimento/--load restano sul filesystem reale")

    ap = argparse.ArgumentParser(
        prog="observe.py",
        description=("Osservatore della flotta — UN tool, tre sottocomandi, UN "
                     "formato JSON. Read-only sulla telemetria, determinism-first: "
                     "nessun LLM nel path del verdetto, nessun auto-fix. Il differ "
                     "misura l'ACCESSO, non l'ONORAGGIO."),
        epilog=("exit: 0 ok · 1 uso/IO · 4 dipendenza interna assente · "
                "5 >=1 verdetto `divergente` (--differ) · 6 asserzione A-23(i) "
                "fallita (--load --asserzione) · 7 anti-ricrescita di CLAUDE.md "
                "fallita (--load --asserzione)"))
    sub = ap.add_subparsers(dest="sottocomando", required=True)
    sub.add_parser("mandato", parents=[comune],
                   help="espone il layer di parsing: mandato(T), canali Read U "
                        "Bash, config@ts(e), asse-foglia-only, filtro authoring")
    sub.add_parser("differ", parents=[comune], aliases=[],
                   help="le unita' dichiarate obbligatorie vengono raggiunte? "
                        "(exit %d su >=1 `divergente`)" % EXIT_DIVERGENTE)
    p_cens = sub.add_parser("censimento", parents=[comune],
                            help="quali unita' non lo sono mai state?")
    p_cens.add_argument("--orphans", action="store_true",
                        help="stampa solo le unita' irraggiungibili")
    p_load = sub.add_parser("load", parents=[comune],
                            help="quanto carico si paga, e su quale adapter "
                                 "(always-on per-adapter + asse agnostico + "
                                 "istruttoria PATTERN + asserzione A-23(i))")
    p_load.add_argument("--asserzione", action="store_true",
                        help="mette l'exit code delle asserzioni nel path "
                             "(esce %d su A-23(i) fallita, %d su ricrescita di "
                             "CLAUDE.md)" % (EXIT_ASSERZIONE, EXIT_RICRESCITA))
    args = ap.parse_args(argv)

    radice = pathlib.Path(args.repo_root).resolve() if args.repo_root else radice_repo_corrente()
    cartella = pathlib.Path(args.projects_dir) if args.projects_dir else cartella_progetto(radice)

    giorno = args.da
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", giorno):
        sys.stderr.write("ERROR: --da vuole YYYY-MM-DD, ricevuto %r\n" % giorno)
        return EXIT_USO
    if giorno < GIORNATA_AUTHORING:
        sys.stderr.write(
            "WARNING: --da %s allargherebbe la finestra sulla giornata di "
            "authoring; l'esclusione e' obbligatoria (AC6) — uso %s.\n"
            % (giorno, GIORNATA_AUTHORING))
        giorno = GIORNATA_AUTHORING

    foglie_congelate, meta_snapshot = None, None
    if args.foglie_snapshot:
        try:
            foglie_congelate, meta_snapshot = carica_foglie_snapshot(args.foglie_snapshot)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            # Fail-loud: uno snapshot illeggibile che degradasse in silenzio al
            # filesystem rimetterebbe la fixture in mano allo stato del repo,
            # che e' esattamente il difetto chiuso da TSK-657.
            sys.stderr.write("ERROR: --foglie-snapshot %s non caricabile: %s\n"
                             % (args.foglie_snapshot, exc))
            return EXIT_USO

    esito = raccogli(radice, cartella, giorno)
    out = costruisci_output(esito, radice, cartella, giorno, args.sottocomando)
    if meta_snapshot:
        out["meta"]["foglie_snapshot"] = meta_snapshot

    # AC8 — `osservabilita: X/Y` su OGNI sottocomando: il differ gira sempre,
    # anche quando la domanda e' il carico o la raggiungibilita'. Un run che non
    # stampa la riga permetterebbe di leggere un output come conformita'.
    verdetti = verdetti_differ(esito, radice, esito["config"], giorno,
                               foglie=foglie_congelate)
    out["meta"]["osservabilita"] = conta_osservabilita(verdetti)
    if esito.get("telemetria_assente"):
        out["meta"]["osservabilita"]["telemetria_assente"] = esito["telemetria_assente"]

    if args.unita:
        out["record"] = [r for r in out["record"] if r["unita"] == args.unita]
        out["meta"]["filtro_unita"] = args.unita
        verdetti_vista = [v for v in verdetti if v["unita"] == args.unita]
    else:
        verdetti_vista = verdetti

    codice = EXIT_OK
    if args.sottocomando == "differ":
        divergenti = [v for v in verdetti_vista if v["verdetto"] == "divergente"]
        codice = EXIT_DIVERGENTE if divergenti else EXIT_OK
        out["differ"] = {
            "domanda": "le unita' dichiarate obbligatorie vengono raggiunte?",
            "verdetti": verdetti_vista,
            "divergenti": [v["unita"] for v in divergenti],
            "exit_code": codice,
            "exit_motivo": (
                "%d verdetto/i `divergente`: %s — PROBLEMA REALE, con evidenza "
                "nominata sopra e comando che la riproduce"
                % (len(divergenti), ", ".join(v["unita"] for v in divergenti))
                if divergenti else
                "nessun `divergente` nella vista: NON significa che la flotta "
                "onori le proprie obbligazioni (vedi osservabilita' e il divieto "
                "di lettura)"),
            "misura": "ACCESSO, non ONORAGGIO",
        }
    elif args.sottocomando == "censimento":
        out["censimento"] = censimento(esito, radice)
        out["censimento"]["exit_code"] = EXIT_OK
        out["censimento"]["exit_motivo"] = (
            "il censimento non ha un esito da bloccare: e' un'istruttoria (A-12). "
            "La rimozione e' US-277 e richiede la conferma del censimento.")
    elif args.sottocomando == "load":
        out["load"] = carico(radice)
        out["asserzione_a23i"] = asserzione_a23i(radice)
        out["asserzione_anti_ricrescita"] = asserzione_anti_ricrescita(radice)
        if args.asserzione and out["asserzione_a23i"]["fallita"]:
            codice = EXIT_ASSERZIONE
        if args.asserzione and out["asserzione_anti_ricrescita"]["fallita"]:
            codice = EXIT_RICRESCITA

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=False))
    elif args.sottocomando == "differ":
        print(stampa_differ(out))
    elif args.sottocomando == "censimento":
        print(stampa_censimento(out, solo_orfane=args.orphans))
    elif args.sottocomando == "load":
        print(stampa_asserzione(out) if args.asserzione else stampa_load(out))
    else:
        print(stampa_mandato(out))
    return codice


if __name__ == "__main__":
    sys.exit(main())
