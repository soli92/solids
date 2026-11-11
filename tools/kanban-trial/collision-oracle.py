#!/usr/bin/env python3
"""
collision-oracle.py — EP-064/US-251/TSK-573 (misura) + TSK-574 (verdetto asimmetrico)

Strumento di SOLA OSSERVAZIONE del trial M1 di EP-064. Misura, sulla storia git
di `management/kanban/`, TRE GRANDEZZE DISTINTE e le presenta separate:

  (a) autori umani unici          — identita' autrici non-bot nel periodo
  (b) finestre di 5 min con >=2 autori distinti — OVERLAP TEMPORALE, e' LA
      metrica di contesa dell'epica (US-251 BR3)
  (c) collisioni                  — «stesso file, autori diversi, delta < 300s»,
      con dettaglio per file

E applica l'ORACOLO ASIMMETRICO (US-251 AC2 / BR1, Accordo 43 del registro
TR-9b4e7c02), che ha tre sole uscite ammesse:

  >=1 collisione                                  ⇒ PROBLEMA REALE
  0 collisioni                                    ⇒ NESSUNA INFORMAZIONE
  0 collisioni ma >=3 finestre-5min con >=2 autori ⇒ RISCHIO LATENTE NON MATERIALIZZATO

La conclusione simmetrica — la negazione del problema — NON e' esprimibile da
questo strumento: non esiste un percorso di codice che la produca, e un guard
finale (`guard_formulazioni_vietate`) ispeziona l'output prima di stamparlo e
FALLISCE RUMOROSAMENTE (exit 3) se una formulazione vietata comparisse.
Il motivo e' misurato, non retorico: `management/kanban/` ha ~320 commit da una
sola identita' autrice, quindi qualunque oracolo basato sugli autori git
restituisce 0 PER COSTRUZIONE. Uno 0 presentato come evidenza negativa sarebbe
una bugia statistica.

Vincoli di progetto:
  - stdlib-only (nessuna dipendenza pip), come il resto della strumentazione
  - sola osservazione: nessun enforcement, nessuna scrittura su TSK, nessun
    processo persistente, nessun writer su `status:`
  - degradazione graziosa: dati assenti ⇒ «NESSUNA INFORMAZIONE», mai «0 collisioni»
  - a strumento assente il comportamento della factory e' identico a oggi

CLI:
  python3 tools/kanban-trial/collision-oracle.py [--repo PATH] [--path P ...]
          [--since <git-date>] [--until <git-date>] [--days N]
          [--window-seconds 300] [--collision-seconds 300]
          [--latent-min-windows 3] [--max-detail 20] [--json]

Exit code (l'esito NON e' codificato nell'exit code: l'oracolo non e' un gate
pass/fail, e un verdetto non e' un fallimento):
  0 = misura eseguita (qualunque sia il verdetto, dati presenti o assenti)
  1 = errore interno dello strumento
  3 = guard dell'asimmetria scattato (formulazione vietata nell'output)

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-251-trial-strumentato-collisioni/US-251.md
       §AC1 §AC2 §AC4 §BR1 §BR2 §BR3 §BR5; EP-064.md §sunset_condition.metrica_di_contesa]
"""

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

TOOL_NAME = "collision-oracle.py"
TOOL_VERSION = "1.0.0"

# ── Parametri della misura (US-251 AC1) ───────────────────────────────────────

DEFAULT_KANBAN_PATHS = ("management/kanban",)

#: Lista ESPLICITA dei bot esclusi dal conteggio degli autori umani (AC1.a).
#: Confronto per sottostringa, case-insensitive, su email E nome autore.
BOT_PATTERNS = ("cursoragent", "github-actions", "noreply@anthropic")

DEFAULT_WINDOW_SECONDS = 300      # (b) finestre di 5 minuti
DEFAULT_COLLISION_SECONDS = 300   # (c) delta < 300s
DEFAULT_LATENT_MIN_WINDOWS = 3    # soglia del «rischio latente» (AC2)

# ── AC4 — la metrica VIETATA, dichiarata e non usata ──────────────────────────
# La riga marcata `AC4-DECLARATION-LINE` e' l'UNICA occorrenza ammessa della
# metrica vietata in questo file: e' TESTO dichiarativo stampato nel report, mai
# un argomento passato a git. Il codice di misura usa `%aE`/`%aN`/`%aI`
# per-commit (mailmap-aware) e non aggrega mai le email come metrica di contesa.
# La proprieta' e' verificata da tests/test_kanban_trial_oracle.py.
METRICA_VIETATA_CMD = "git log --format=%ae | sort -u"  # AC4-DECLARATION-LINE

METRICA_VIETATA_MOTIVO = (
    "NON e' usata da questo strumento come metrica di contesa, ed e' vietata "
    "dall'epica: su questo repo restituisce 3 identita' che sono la stessa "
    "persona piu' un agente (doppia email del maintainer + "
    "cursoragent@cursor.com). Chi la usa misura le email, non le persone in "
    "overlap temporale. La metrica di contesa e' la grandezza (b)."
)

# ── TSK-574 — le tre uscite ammesse, VERBATIM, come costanti ──────────────────
# Sono l'oggetto dell'assert di TSK-575: non sono interpolazioni.

VERDETTO_PROBLEMA_REALE = ">=1 collisione ⇒ PROBLEMA REALE"
VERDETTO_NESSUNA_INFORMAZIONE = "0 collisioni ⇒ NESSUNA INFORMAZIONE"
VERDETTO_RISCHIO_LATENTE = (
    "0 collisioni ma >=3 finestre-5min con >=2 autori "
    "⇒ RISCHIO LATENTE NON MATERIALIZZATO"
)

VERDETTI_AMMESSI = (
    VERDETTO_PROBLEMA_REALE,
    VERDETTO_NESSUNA_INFORMAZIONE,
    VERDETTO_RISCHIO_LATENTE,
)

# ── Guard dell'asimmetria (TSK-574 / TSK-575) ─────────────────────────────────
#: Formulazioni che lo strumento non puo' emettere in nessun percorso di codice.
#: Il guard e' un presidio, non una decorazione: se una compare, l'output NON
#: viene stampato e il processo esce con 3.
FORMULAZIONI_VIETATE = (
    "il problema non esiste",
    "non esiste il problema",
    "problema inesistente",
    "il problema non e reale",
    "il problema non c'e'",
    "non serve costruire",
    "non c'e bisogno di costruire",
    "nessun problema",
    "nessuna contesa",
    "non c'e contesa",
    "contesa inesistente",
)


class ForbiddenClaim(RuntimeError):
    """Sollevata dal guard quando l'output conterrebbe una formulazione vietata."""


def _normalizza(testo):
    """Minuscole, accenti rimossi, apostrofi uniformati, spazi collassati.

    Serve al guard: «Il problema non è reale.» e «il problema non e' reale»
    devono collassare sulla stessa forma confrontabile.
    """
    if testo is None:
        return ""
    piatto = unicodedata.normalize("NFD", str(testo))
    piatto = "".join(c for c in piatto if not unicodedata.combining(c))
    piatto = piatto.lower()
    for apostrofo in ("’", "ʼ", "´", "`", "'"):
        piatto = piatto.replace(apostrofo, "")
    piatto = re.sub(r"\s+", " ", piatto)
    return piatto


def guard_formulazioni_vietate(output, blocklist=FORMULAZIONI_VIETATE):
    """Ispeziona l'output finale; solleva ForbiddenClaim alla prima violazione.

    Invariante di US-251 BR1: lo strumento non deve POTER emettere la
    conclusione simmetrica. Questo e' il punto in cui la regola e' eseguibile.
    """
    piatto = _normalizza(output)
    for frase in blocklist:
        if _normalizza(frase) in piatto:
            raise ForbiddenClaim(frase)
    return True


# ── TSK-574 — la funzione di verdetto, isolata e testabile ────────────────────

def verdetto(
    collisioni,
    finestre_overlap,
    dati_disponibili=True,
    latent_min_windows=DEFAULT_LATENT_MIN_WINDOWS,
):
    """Restituisce `(verdetto_verbatim, nota)`.

    Input: le tre grandezze di TSK-573 (qui servono (b) e (c)).
    Output: UNA delle tre stringhe costanti di VERDETTI_AMMESSI.

    Precedenze:
      1. `collisioni >= 1`                         -> PROBLEMA REALE
      2. `finestre_overlap >= latent_min_windows`  -> RISCHIO LATENTE (precede il caso 3)
      3. altrimenti                                -> NESSUNA INFORMAZIONE

    `dati_disponibili=False` (git assente, nessun commit nel periodo, storia
    illeggibile) forza NESSUNA INFORMAZIONE: la degradazione graziosa dice
    «nessuna informazione», non «0 collisioni».
    """
    collisioni = int(collisioni or 0)
    finestre_overlap = int(finestre_overlap or 0)

    if not dati_disponibili:
        return (
            VERDETTO_NESSUNA_INFORMAZIONE,
            "dati assenti nel perimetro osservato: nessuna misura possibile, "
            "quindi nessuna informazione. Lo 0 qui non e' un risultato: e' "
            "l'assenza di un risultato.",
        )

    if collisioni >= 1:
        return (
            VERDETTO_PROBLEMA_REALE,
            "almeno una collisione osservata: la contesa e' un fatto "
            "registrato, non una stima.",
        )

    if finestre_overlap >= latent_min_windows:
        return (
            VERDETTO_RISCHIO_LATENTE,
            "rischio latente non materializzato: gli autori sono stati attivi "
            "in overlap temporale senza incrociarsi sugli stessi file. "
            "Da rivalutare, non da concludere.",
        )

    return (
        VERDETTO_NESSUNA_INFORMAZIONE,
        "0 collisioni su questa fonte NON e' evidenza in direzione opposta: la "
        "fonte git e' cieca alle sessioni indipendenti che condividono la "
        "stessa identita' autrice, e su questo repo l'esito 0 e' atteso PER "
        "COSTRUZIONE. L'unica lettura ammessa e' l'assenza di informazione.",
    )


# ── Raccolta dati (TSK-573) ───────────────────────────────────────────────────

# Campi del record di commit. Costruiti come tupla e uniti a runtime: il codice
# di misura non contiene alcuna stringa `--format=` pre-assemblata da grep-are.
_GIT_FIELDS = ("%H", "%aI", "%aE", "%aN")
_REC_SEP = "\x1e"
_FLD_SEP = "\x1f"


class GitUnavailable(RuntimeError):
    """git non disponibile, o il percorso non e' un repository leggibile."""


def _git(repo, args):
    completo = ["git", "-C", str(repo)] + list(args)
    try:
        proc = subprocess.run(
            completo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, ValueError) as exc:  # git non installato, repo illeggibile
        raise GitUnavailable(str(exc)) from exc
    if proc.returncode != 0:
        raise GitUnavailable(
            proc.stderr.decode("utf-8", "replace").strip()
            or f"git ha restituito {proc.returncode}"
        )
    return proc.stdout.decode("utf-8", "replace")


def repo_root(start="."):
    """Toplevel del repo che contiene `start`; `start` stesso in degradazione."""
    try:
        return _git(start, ["rev-parse", "--show-toplevel"]).strip() or str(start)
    except GitUnavailable:
        return str(start)


def is_bot(email, nome, bot_patterns=BOT_PATTERNS):
    """True se l'identita' autrice e' un bot della lista esplicita (AC1.a)."""
    campo = f"{email or ''} {nome or ''}".lower()
    return any(pattern.lower() in campo for pattern in bot_patterns)


def _parse_ts(iso):
    """ISO-8601 con offset -> datetime aware; None se illeggibile."""
    try:
        return datetime.fromisoformat(iso.strip())
    except (ValueError, AttributeError):
        return None


def raccogli_commit(repo, percorsi, since=None, until=None):
    """Legge la storia git dei `percorsi` e restituisce `(commit, diagnostica)`.

    `commit` e' una lista di dict ordinati per timestamp crescente:
      {sha, ts (datetime aware), iso, autore, autore_nome, bot (bool), files [str]}
    Nessuna aggregazione delle email: l'identita' e' un campo per-commit.
    """
    argv = [
        "log",
        "--no-merges",
        "--name-only",
        "--date-order",
        "--format=" + _REC_SEP + _FLD_SEP.join(_GIT_FIELDS),
    ]
    if since:
        argv.append("--since=" + since)
    if until:
        argv.append("--until=" + until)
    argv.append("--")
    argv.extend(percorsi)

    grezzo = _git(repo, argv)

    commit = []
    malformati = 0
    for blocco in grezzo.split(_REC_SEP):
        if not blocco.strip():
            continue
        righe = blocco.splitlines()
        campi = righe[0].split(_FLD_SEP)
        if len(campi) < 4:
            malformati += 1
            continue
        sha, iso, email, nome = campi[0], campi[1], campi[2], campi[3]
        ts = _parse_ts(iso)
        if ts is None:
            malformati += 1
            continue
        files = sorted({r.strip() for r in righe[1:] if r.strip()})
        commit.append(
            {
                "sha": sha[:12],
                "ts": ts,
                "iso": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "autore": email.strip(),
                "autore_nome": nome.strip(),
                "bot": is_bot(email, nome),
                "files": files,
            }
        )

    commit.sort(key=lambda c: c["ts"])
    # I separatori sono caratteri di controllo: nel comando mostrato all'umano
    # vengono resi con i placeholder git equivalenti, altrimenti la riga stampata
    # sembra priva di separatori.
    argv_leggibile = [
        a.replace(_REC_SEP, "%x1e").replace(_FLD_SEP, "%x1f") for a in argv
    ]
    diagnostica = {
        "commit_letti": len(commit),
        "commit_malformati_saltati": malformati,
        "comando": "git -C <repo> " + " ".join(argv_leggibile),
    }
    return commit, diagnostica


# ── Le tre grandezze, separate (TSK-573 AC1) ──────────────────────────────────

def grandezza_a_autori_umani(commit):
    """(a) autori umani unici — identita' autrici non-bot, con i loro conteggi."""
    per_identita = {}
    for c in commit:
        if c["bot"]:
            continue
        voce = per_identita.setdefault(
            c["autore"],
            {"identita": c["autore"], "nomi": set(), "commit": 0},
        )
        voce["nomi"].add(c["autore_nome"])
        voce["commit"] += 1
    elenco = [
        {
            "identita": v["identita"],
            "nomi": sorted(n for n in v["nomi"] if n),
            "commit": v["commit"],
        }
        for v in per_identita.values()
    ]
    elenco.sort(key=lambda v: (-v["commit"], v["identita"]))
    return {"conteggio": len(elenco), "identita": elenco}


def grandezza_b_finestre_overlap(commit, window_seconds=DEFAULT_WINDOW_SECONDS):
    """(b) finestre da `window_seconds` con >=2 autori distinti (OVERLAP TEMPORALE).

    Finestre tumbling allineate all'epoch: e' la definizione dell'epica
    («finestre di 5 minuti»). Conseguenza dichiarata nel perimetro: due autori a
    cavallo di un confine di finestra NON sono contati, quindi (b) e' un LIMITE
    INFERIORE dell'overlap reale.
    """
    per_finestra = {}
    for c in commit:
        if c["bot"]:
            continue
        indice = int(c["ts"].timestamp()) // window_seconds
        voce = per_finestra.setdefault(indice, {"autori": set(), "commit": []})
        voce["autori"].add(c["autore"])
        voce["commit"].append(c["sha"])

    finestre = []
    for indice, voce in sorted(per_finestra.items()):
        if len(voce["autori"]) < 2:
            continue
        inizio = datetime.fromtimestamp(indice * window_seconds, tz=timezone.utc)
        finestre.append(
            {
                "inizio_utc": inizio.isoformat().replace("+00:00", "Z"),
                "autori": sorted(voce["autori"]),
                "autori_distinti": len(voce["autori"]),
                "commit": voce["commit"],
            }
        )
    return {
        "conteggio": len(finestre),
        "window_seconds": window_seconds,
        "finestre_totali_con_attivita": len(per_finestra),
        "finestre": finestre,
    }


def grandezza_c_collisioni(commit, collision_seconds=DEFAULT_COLLISION_SECONDS):
    """(c) collisioni: stesso file, autori diversi, delta < `collision_seconds`.

    Dettaglio per file, come richiesto da AC1.c.
    """
    tocchi = {}
    for c in commit:
        if c["bot"]:
            continue
        for percorso in c["files"]:
            tocchi.setdefault(percorso, []).append(c)

    per_file = []
    coppie_totali = 0
    for percorso, elenco in sorted(tocchi.items()):
        elenco = sorted(elenco, key=lambda c: c["ts"])
        coppie = []
        for i, primo in enumerate(elenco):
            for secondo in elenco[i + 1:]:
                delta = (secondo["ts"] - primo["ts"]).total_seconds()
                if delta >= collision_seconds:
                    break
                if secondo["autore"] == primo["autore"]:
                    continue
                coppie.append(
                    {
                        "autore_a": primo["autore"],
                        "autore_b": secondo["autore"],
                        "sha_a": primo["sha"],
                        "sha_b": secondo["sha"],
                        "ts_a": primo["iso"],
                        "ts_b": secondo["iso"],
                        "delta_secondi": round(delta, 1),
                    }
                )
        if coppie:
            coppie_totali += len(coppie)
            per_file.append(
                {"file": percorso, "collisioni": len(coppie), "coppie": coppie}
            )

    per_file.sort(key=lambda v: (-v["collisioni"], v["file"]))
    return {
        "conteggio": coppie_totali,
        "collision_seconds": collision_seconds,
        "file_coinvolti": len(per_file),
        "file_tracciati": len(tocchi),
        "dettaglio_per_file": per_file,
    }


def cecita_strutturale(grandezza_a, commit_non_bot):
    """Dichiara quando l'esito 0 e' atteso PER COSTRUZIONE (US-251 BR2).

    Con una sola identita' autrice nel perimetro, (b) e (c) valgono 0
    qualunque sia l'attivita' reale: l'oracolo e' strutturalmente incapace di
    informare, e va detto nell'output, non scoperto dal lettore.
    """
    autori = grandezza_a["conteggio"]
    cieco = autori <= 1
    if autori == 0:
        motivo = (
            "nessuna identita' autrice nel perimetro osservato: le tre "
            "grandezze non sono state misurate. L'esito non e' uno zero, e' "
            "l'assenza di misura."
        )
    elif cieco:
        motivo = (
            f"una sola identita' autrice ({autori}) su {commit_non_bot} commit "
            "non-bot nel perimetro: le grandezze (b) e (c) valgono 0 PER "
            "COSTRUZIONE, indipendentemente dall'attivita' reale. L'unica "
            "lettura ammessa dell'esito e' l'assenza di informazione."
        )
    else:
        motivo = (
            f"{autori} identita' autrici distinte nel perimetro: le grandezze "
            "(b) e (c) sono in principio osservabili."
        )
    return {"oracolo_strutturalmente_cieco": cieco, "motivo": motivo}


# ── Misura completa ───────────────────────────────────────────────────────────

def misura(
    repo,
    percorsi=DEFAULT_KANBAN_PATHS,
    since=None,
    until=None,
    window_seconds=DEFAULT_WINDOW_SECONDS,
    collision_seconds=DEFAULT_COLLISION_SECONDS,
    latent_min_windows=DEFAULT_LATENT_MIN_WINDOWS,
):
    """Esegue la misura e restituisce il risultato strutturato (dict).

    Degradazione graziosa: git assente o storia vuota non e' un errore, e' un
    perimetro senza dati -> `dati_disponibili: false` e verdetto NESSUNA
    INFORMAZIONE.
    """
    percorsi = list(percorsi) or list(DEFAULT_KANBAN_PATHS)
    degradazione = []
    commit = []
    diagnostica = {"commit_letti": 0, "commit_malformati_saltati": 0, "comando": None}

    try:
        commit, diagnostica = raccogli_commit(repo, percorsi, since=since, until=until)
    except GitUnavailable as exc:
        degradazione.append(
            "storia git non leggibile (" + str(exc).splitlines()[0][:200] + ")"
        )

    return componi_risultato(
        commit,
        repo=repo,
        percorsi=percorsi,
        since=since,
        until=until,
        window_seconds=window_seconds,
        collision_seconds=collision_seconds,
        latent_min_windows=latent_min_windows,
        degradazione=degradazione,
        diagnostica=diagnostica,
    )


def componi_risultato(
    commit,
    repo=".",
    percorsi=DEFAULT_KANBAN_PATHS,
    since=None,
    until=None,
    window_seconds=DEFAULT_WINDOW_SECONDS,
    collision_seconds=DEFAULT_COLLISION_SECONDS,
    latent_min_windows=DEFAULT_LATENT_MIN_WINDOWS,
    degradazione=None,
    diagnostica=None,
):
    """Calcola le tre grandezze e il verdetto da una lista di commit.

    Parte PURA della misura: nessun sottoprocesso, nessun accesso alla rete,
    nessuna dipendenza da git. E' il punto di innesto dei test con input
    sintetici (TSK-575).
    """
    percorsi = list(percorsi) or list(DEFAULT_KANBAN_PATHS)
    degradazione = list(degradazione or [])
    diagnostica = dict(
        diagnostica
        or {"commit_letti": len(commit), "commit_malformati_saltati": 0, "comando": None}
    )

    # ordine non assunto dal chiamante: primo/ultimo commit vanno letti su una
    # sequenza ordinata anche se l'input arriva non ordinato (test sintetici).
    non_bot = sorted((c for c in commit if not c["bot"]), key=lambda c: c["ts"])
    commit_bot = len(commit) - len(non_bot)
    if commit and not non_bot:
        degradazione.append(
            "tutti i commit del perimetro appartengono ai bot della lista esplicita"
        )
    if not commit and not degradazione:
        degradazione.append("nessun commit nel perimetro osservato")

    dati_disponibili = bool(non_bot)

    a = grandezza_a_autori_umani(commit)
    b = grandezza_b_finestre_overlap(commit, window_seconds=window_seconds)
    c = grandezza_c_collisioni(commit, collision_seconds=collision_seconds)

    esito, nota = verdetto(
        c["conteggio"],
        b["conteggio"],
        dati_disponibili=dati_disponibili,
        latent_min_windows=latent_min_windows,
    )

    primo = non_bot[0]["iso"] if non_bot else None
    ultimo = non_bot[-1]["iso"] if non_bot else None

    return {
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "generato_il": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "enforcement": "nessuno (strumento di sola osservazione)",
        "metrica_vietata": {
            "comando": METRICA_VIETATA_CMD,
            "usata_da_questo_strumento": False,
            "motivo": METRICA_VIETATA_MOTIVO,
        },
        "perimetro_osservato": {
            "repo": str(repo),
            "percorsi": percorsi,
            "since": since,
            "until": until,
            "primo_commit_utc": primo,
            "ultimo_commit_utc": ultimo,
            "commit_non_bot": len(non_bot),
            "commit_bot_esclusi": commit_bot,
            "bot_esclusi": list(BOT_PATTERNS),
            "mailmap_presente": _mailmap_presente(repo),
            "dati_disponibili": dati_disponibili,
            "degradazione": degradazione,
            **diagnostica,
        },
        "grandezza_a_autori_umani_unici": a,
        "grandezza_b_finestre_overlap": b,
        "grandezza_c_collisioni": c,
        "cecita_strutturale": cecita_strutturale(a, len(non_bot)),
        "verdetto": esito,
        "verdetto_nota": nota,
        "verdetti_ammessi": list(VERDETTI_AMMESSI),
        "perimetro_non_misurabile": list(PERIMETRO_NON_MISURABILE),
    }


def _mailmap_presente(repo):
    try:
        import pathlib

        return (pathlib.Path(repo) / ".mailmap").exists()
    except OSError:
        return False


# ── Perimetro dichiarato (US-251 AC6) ─────────────────────────────────────────

PERIMETRO_NON_MISURABILE = (
    "le sessioni agentiche su macchine diverse non sono correlabili senza il "
    "canale: i transcript vivono in ~/.claude/projects/**, sono locali per "
    "macchina e mai versionati",
    "due sessioni indipendenti che committano con la stessa identita' autrice "
    "sono indistinguibili in git: la contesa fra loro e' invisibile a questa fonte",
    "il lavoro non committato (edit locali, TSK presi e non ancora scritti) non "
    "esiste nella storia git e non entra in nessuna delle tre grandezze",
    "le finestre sono tumbling: una coppia di autori a cavallo di un confine di "
    "finestra non viene contata, quindi (b) e' un limite inferiore",
    "la contesa dichiarata dal committente (15+ scrittori misti) non e' "
    "osservabile su questo repo: il perimetro contiene una sola identita' autrice",
)


# ── Rendering ─────────────────────────────────────────────────────────────────

def _riga(titolo, valore):
    return f"  {titolo:<62}{valore}"


def render_testo(risultato, max_detail=20):
    """Report leggibile da un umano (US-251 AC6). Il verdetto e' la PRIMA riga
    del blocco di esito, non una nota."""
    p = risultato["perimetro_osservato"]
    a = risultato["grandezza_a_autori_umani_unici"]
    b = risultato["grandezza_b_finestre_overlap"]
    c = risultato["grandezza_c_collisioni"]
    mv = risultato["metrica_vietata"]

    out = []
    out.append("=" * 78)
    out.append(
        f"KANBAN TRIAL — ORACOLO DI COLLISIONE   ({risultato['tool']} v{risultato['tool_version']})"
    )
    out.append("EP-064 / US-251 — strumento di SOLA OSSERVAZIONE: nessun enforcement.")
    out.append("=" * 78)
    out.append("")

    out.append("METRICA VIETATA (AC4) — dichiarata, non usata")
    out.append(f"  `{mv['comando']}`")
    out.append(f"  {mv['motivo']}")
    out.append(
        _riga(".mailmap presente nel repo", "si" if p["mailmap_presente"] else "no")
    )
    out.append("")

    out.append("PERIODO DI OSSERVAZIONE")
    out.append(_riga("repo", p["repo"]))
    out.append(_riga("percorsi", ", ".join(p["percorsi"])))
    out.append(_riga("--since / --until", f"{p['since'] or 'inizio storia'} / {p['until'] or 'HEAD'}"))
    out.append(_riga("primo / ultimo commit non-bot (UTC)", f"{p['primo_commit_utc'] or 'n/d'} / {p['ultimo_commit_utc'] or 'n/d'}"))
    out.append(_riga("commit non-bot letti", p["commit_non_bot"]))
    out.append(_riga("commit di bot esclusi", p["commit_bot_esclusi"]))
    out.append(_riga("bot esclusi (lista esplicita)", ", ".join(p["bot_esclusi"])))
    if p["commit_malformati_saltati"]:
        out.append(_riga("record git saltati (malformati)", p["commit_malformati_saltati"]))
    out.append(_riga("comando eseguito", p["comando"] or "n/d"))
    for nota in p["degradazione"]:
        out.append(f"  [degradazione] {nota}")
    out.append("")

    disponibili = p["dati_disponibili"]

    out.append("LE TRE GRANDEZZE (distinte, mai collassate in un unico numero)")
    out.append("")
    out.append(
        _riga(
            "(a) AUTORI UMANI UNICI  — identita' autrici, NON persone",
            a["conteggio"] if disponibili else "n/d (non misurato)",
        )
    )
    for voce in a["identita"][: max_detail or None]:
        nomi = ", ".join(voce["nomi"]) or "?"
        out.append(f"      - {voce['identita']} ({nomi}) — {voce['commit']} commit")
    out.append("      (a) NON e' la metrica di contesa: conta identita', non persone in overlap.")
    out.append("")

    out.append(
        _riga(
            f"(b) FINESTRE DA {b['window_seconds']}s CON >=2 AUTORI — OVERLAP TEMPORALE",
            b["conteggio"] if disponibili else "n/d (non misurato)",
        )
    )
    out.append(
        _riga(
            "    finestre con attivita' (denominatore)",
            b["finestre_totali_con_attivita"] if disponibili else "n/d",
        )
    )
    for finestra in b["finestre"][: max_detail or None]:
        out.append(
            f"      - {finestra['inizio_utc']} — {finestra['autori_distinti']} autori: "
            f"{', '.join(finestra['autori'])} ({len(finestra['commit'])} commit)"
        )
    if b["conteggio"] > (max_detail or b["conteggio"]):
        out.append(f"      ... (+{b['conteggio'] - max_detail} finestre, vedi --json)")
    out.append("      (b) e' LA metrica di contesa dell'epica (US-251 BR3).")
    out.append("")

    out.append(
        _riga(
            f"(c) COLLISIONI — stesso file, autori diversi, delta < {c['collision_seconds']}s",
            c["conteggio"] if disponibili else "n/d (non misurato)",
        )
    )
    out.append(
        _riga(
            "    file tracciati nel perimetro",
            c["file_tracciati"] if disponibili else "n/d",
        )
    )
    out.append(
        _riga(
            "    file con almeno una collisione",
            c["file_coinvolti"] if disponibili else "n/d",
        )
    )
    if c["dettaglio_per_file"]:
        out.append("      dettaglio per file:")
        for voce in c["dettaglio_per_file"][: max_detail or None]:
            out.append(f"      - {voce['file']} — {voce['collisioni']} collisioni")
            for coppia in voce["coppie"][:3]:
                out.append(
                    f"          {coppia['autore_a']} ({coppia['sha_a']}) x "
                    f"{coppia['autore_b']} ({coppia['sha_b']}) "
                    f"delta {coppia['delta_secondi']}s"
                )
        if c["file_coinvolti"] > (max_detail or c["file_coinvolti"]):
            out.append(
                f"      ... (+{c['file_coinvolti'] - max_detail} file, vedi --json)"
            )
    else:
        out.append("      dettaglio per file: nessuna coppia entro la soglia.")
    out.append("")

    out.append("-" * 78)
    out.append("ESITO — ORACOLO ASIMMETRICO (US-251 AC2, Accordo 43)")
    out.append("-" * 78)
    out.append(f"  {risultato['verdetto']}")
    out.append("")
    out.append(f"  nota: {risultato['verdetto_nota']}")
    out.append("")
    out.append("  Le tre uscite ammesse da questo strumento, e nessun'altra:")
    for ammesso in risultato["verdetti_ammessi"]:
        marcatore = "->" if ammesso == risultato["verdetto"] else "  "
        out.append(f"    {marcatore} {ammesso}")
    out.append("")
    out.append(
        "  L'uscita simmetrica — la negazione del problema — non e' esprimibile: "
        "nessun\n  percorso di codice la produce e un guard ispeziona questo "
        "testo prima di stamparlo."
    )
    out.append("")

    out.append("CECITA' STRUTTURALE DELLA FONTE (US-251 BR2)")
    out.append(
        _riga(
            "oracolo strutturalmente cieco su questo perimetro",
            "si" if risultato["cecita_strutturale"]["oracolo_strutturalmente_cieco"] else "no",
        )
    )
    out.append(f"  {risultato['cecita_strutturale']['motivo']}")
    out.append("")

    out.append("PERIMETRO — CIO' CHE QUESTO STRUMENTO NON PUO' MISURARE (AC6)")
    for voce in risultato["perimetro_non_misurabile"]:
        out.append(f"  - {voce}")
    out.append("")
    out.append(
        "Il gate di frequenza e' stato spostato dalla COSTRUZIONE all'ESPANSIONE\n"
        "allo scope umano (Accordo 55): si misura sul WAL dell'arbitro (US-258),\n"
        "non qui. Nessuna decisione su M3 e' presa da questo strumento."
    )
    out.append("=" * 78)
    return "\n".join(out)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _costruisci_parser():
    ap = argparse.ArgumentParser(
        prog="collision-oracle.py",
        description=(
            "Misura tre grandezze distinte sulla storia git di management/kanban/ "
            "(autori umani unici, finestre di overlap temporale, collisioni per "
            "file) e applica l'oracolo asimmetrico di EP-064/US-251. Strumento "
            "di sola osservazione: nessun enforcement."
        ),
    )
    ap.add_argument("--repo", default=None, metavar="PATH",
                    help="Radice del repo da osservare (default: toplevel git della cwd).")
    ap.add_argument("--path", dest="paths", nargs="*", default=None, metavar="P",
                    help="Percorsi osservati (default: management/kanban).")
    ap.add_argument("--since", default=None, metavar="DATE",
                    help="Inizio del periodo di osservazione (qualunque formato data di git).")
    ap.add_argument("--until", default=None, metavar="DATE",
                    help="Fine del periodo di osservazione.")
    ap.add_argument("--days", type=int, default=None, metavar="N",
                    help="Scorciatoia: osserva gli ultimi N giorni (ignorata se --since e' presente).")
    ap.add_argument("--window-seconds", type=int, default=DEFAULT_WINDOW_SECONDS, metavar="S",
                    help=f"Ampiezza delle finestre di overlap, grandezza (b) (default {DEFAULT_WINDOW_SECONDS}).")
    ap.add_argument("--collision-seconds", type=int, default=DEFAULT_COLLISION_SECONDS, metavar="S",
                    help=f"Soglia di delta per la collisione, grandezza (c) (default {DEFAULT_COLLISION_SECONDS}).")
    ap.add_argument("--latent-min-windows", type=int, default=DEFAULT_LATENT_MIN_WINDOWS, metavar="N",
                    help=f"Finestre di overlap oltre le quali si dichiara rischio latente (default {DEFAULT_LATENT_MIN_WINDOWS}).")
    ap.add_argument("--max-detail", type=int, default=20, metavar="N",
                    help="Righe di dettaglio per sezione nell'output testuale (0 = tutte).")
    ap.add_argument("--json", action="store_true",
                    help="Output machine-readable su stdout.")
    return ap


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # interprete vecchio o stdout sostituito
        pass

    args = _costruisci_parser().parse_args(argv)

    repo = args.repo or repo_root(".")
    since = args.since
    if since is None and args.days:
        since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    try:
        risultato = misura(
            repo,
            percorsi=args.paths or DEFAULT_KANBAN_PATHS,
            since=since,
            until=args.until,
            window_seconds=max(1, args.window_seconds),
            collision_seconds=max(1, args.collision_seconds),
            latent_min_windows=max(1, args.latent_min_windows),
        )
    except Exception as exc:  # errore interno: fail-loud, mai un verdetto finto
        print(f"ERRORE INTERNO: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        output = json.dumps(risultato, indent=2, ensure_ascii=False)
    else:
        output = render_testo(risultato, max_detail=max(0, args.max_detail))

    try:
        guard_formulazioni_vietate(output)
    except ForbiddenClaim as exc:
        print(
            "GUARD DELL'ASIMMETRIA SCATTATO: l'output conteneva una formulazione "
            f"vietata ({exc}). Output soppresso: e' un difetto dello strumento, "
            "non un esito. Vedi US-251 BR1 e tests/test_kanban_trial_oracle.py.",
            file=sys.stderr,
        )
        return 3

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
