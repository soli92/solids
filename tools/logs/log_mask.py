"""Mascheramento e riduzione dei log prima che arrivino a chi li legge.

Tutto quello che esce da log_access.py (righe, errori, dump) passa da `mask()`: email, nomi nei
campi strutturati e i pattern di dati personali scelti in configurazione diventano segnaposto con
un hash corto (HMAC con chiave nuova a ogni esecuzione: stabile solo dentro la stessa esecuzione, per
correlare le righe senza esporre il dato); token, JWT, password e chiavi vengono sostituiti senza hash.

I pattern di dati personali specifici di un paese o di un cliente NON sono cablati: sono insiemi
nominati (`PATTERN_SETS`) da attivare con `log_access.mask_patterns` oppure regex proprie dichiarate in
`log_access.mask_custom_patterns`. Senza configurazione restano attivi solo email e chiavi di persona. I dati personali si possono lasciare in chiaro con una
scelta esplicita (`--no-mask`, `personal=False`); i segreti restano mascherati sempre.

Qui vivono anche le funzioni che accorciano i log senza perdere il senso: schema del
messaggio (`template`), stack trace ridotto (`trim_stack`), riassunto dei message JSON.
Solo libreria standard.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets

# Nuova a ogni esecuzione: gli hash non sono confrontabili tra esecuzioni diverse.
MASK_KEY = secrets.token_bytes(16)

APP_PACKAGE = ""                # prefisso dei frame applicativi tenuti negli stack trace accorciati (vuoto: solo il primo frame)
APP_FRAMES = 3                  # frame applicativi tenuti per ogni blocco dello stack trace

# Pattern opt-in (vedi PATTERN_SETS): codice fiscale e partita IVA italiani.
CF_RE = re.compile(r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", re.IGNORECASE)
PIVA_RE = re.compile(r"(?<![0-9A-Za-z])\d{11}(?![0-9A-Za-z])")     # anche il CF numerico degli enti
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
AUTH_HEADER_RE = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
# Token opachi o troncati (non JWT completi): stringhe lunghe con maiuscole, minuscole e cifre insieme.
# Non toccano uuid e trace id (solo esadecimale minuscolo) ne' nomi di classe (senza cifre).
TOKEN_RE = re.compile(r"(?<![\w-])(?=[\w-]*[a-z])(?=[\w-]*[A-Z])(?=[\w-]*\d)[\w-]{20,}={0,2}")
# Segreti con formato proprio, gli stessi che tools/docs/redact.py cerca nei documenti.
ADO_PAT_RE = re.compile(r"(?<![A-Za-z0-9])(?=[a-z2-7]*[2-7])[a-z2-7]{52}(?![A-Za-z0-9])")
VENDOR_TOKEN_RE = re.compile(r"\b(?:gh[po]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|$)")

# Nomi di persona nei testi strutturati ("chiave":"valore" o chiave=valore): non hanno un formato
# riconoscibile, si riconoscono dalla chiave. Il valore tra virgolette puo' contenere spazi e virgole
# ("MARIO ROSSI,ANNA BIANCHI"). "name" da sola e' il nome di servizi, categorie, tipi processo: viene
# mascherata solo se nel testo c'e' anche "surname".
PERSON_KEYS = (r"signer\w*|(?:note_?)?author|first_?name|last_?name|full_?name|"
               r"display_?name|user_?name|name_user|surname|nome|cognome")
SURNAME_RE = re.compile(r"\bsurname\b", re.IGNORECASE)
SECRET_RE = re.compile(r"\b(password|passwd|pwd|secret|client_secret|api[_-]?key|access_token|refresh_token)"
                       r"([\"']?\s*[:=]\s*[\"']?)[^\s\"',;&}]+", re.IGNORECASE)


def _build_person_res(keys: str):
    quoted = re.compile(rf"([\"']?\b(?:{keys})[\"']?\s*[:=]\s*)([\"'])([^\"']*)\2", re.IGNORECASE)
    plain = re.compile(rf"(\b(?:{keys})\s*[:=]\s*)(?![\"'\s{{\[]|null\b|<)([^,;&}}\]\n]+)", re.IGNORECASE)
    return quoted, plain


PERSON_RES = _build_person_res(PERSON_KEYS)
PERSON_WITH_NAME_RES = _build_person_res(PERSON_KEYS + "|name")

PATTERN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def tag(kind: str, value: str) -> str:
    digest = hmac.new(MASK_KEY, value.upper().encode(), hashlib.sha256).hexdigest()[:6]
    return f"<{kind}#{digest}>"


def valid_piva(digits: str) -> bool:
    """Cifra di controllo della partita IVA: evita di mascherare numeri di 11 cifre qualsiasi."""
    total = 0
    for position, char in enumerate(digits[:10]):
        value = int(char)
        if position % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return (10 - total % 10) % 10 == int(digits[10])


def mask_secrets(text: str) -> str:
    """Segreti e credenziali: sempre mascherati, anche con il mascheramento dei dati personali spento."""
    text = PRIVATE_KEY_RE.sub("<CHIAVE-PRIVATA>", text)
    text = JWT_RE.sub("<JWT>", text)
    text = AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)} <TOKEN>", text)
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<SECRET>", text)
    text = VENDOR_TOKEN_RE.sub("<TOKEN>", text)
    text = ADO_PAT_RE.sub("<TOKEN>", text)
    return TOKEN_RE.sub("<TOKEN>", text)


def _mask_with(spec: dict, text: str) -> str:
    check = spec.get("validator")
    return spec["regex"].sub(
        lambda m: tag(spec["kind"], m.group(0)) if check is None or check(m.group(0)) else m.group(0), text)


# Insiemi nominati di pattern di dati personali, attivabili da configurazione (`mask_patterns`).
PATTERN_SETS: dict = {
    "it-codice-fiscale": {"regex": CF_RE, "kind": "CF", "template": "cf"},
    "it-partita-iva": {"regex": PIVA_RE, "kind": "PIVA", "validator": valid_piva, "template": None},
}

# Stato configurato (processo corrente): pattern attivi e chiavi di persona. Vedi configure().
_active: list = []
_person_pair = (PERSON_RES, PERSON_WITH_NAME_RES)


def configure(patterns=(), custom=None, person_keys=()) -> None:
    """Imposta i pattern di dati personali attivi, le regex proprie e le chiavi di persona aggiuntive.

    patterns: nomi di PATTERN_SETS. custom: {nome: regex}. person_keys: nomi di chiave in piu' (letterali).
    Chiamata senza argomenti: solo email e chiavi di persona di default. Solleva ValueError su nomi o regex non validi.
    """
    global _active, _person_pair
    active = []
    for name in patterns or ():
        if name not in PATTERN_SETS:
            raise ValueError(f"pattern di mascheramento sconosciuto: {name} (disponibili: {', '.join(sorted(PATTERN_SETS))})")
        active.append(PATTERN_SETS[name])
    for name, expression in (custom or {}).items():
        if not PATTERN_NAME_RE.match(str(name)):
            raise ValueError(f"nome di pattern non valido (minuscole, cifre, trattini): {name}")
        try:
            compiled = re.compile(str(expression))
        except re.error as error:
            raise ValueError(f"regex non valida per il pattern {name}: {error}") from None
        active.append({"regex": compiled, "kind": str(name).upper(), "template": str(name)})
    extra = "|".join(re.escape(str(key)) for key in person_keys or ())
    _active = active
    suffix = f"|{extra}" if extra else ""
    _person_pair = (_build_person_res(PERSON_KEYS + suffix), _build_person_res(PERSON_KEYS + "|name" + suffix))


def mask_personal(text: str) -> str:
    """Dati personali: nomi nei campi strutturati, email e i pattern attivati in configurazione."""
    quoted, plain = _person_pair[1] if SURNAME_RE.search(text) else _person_pair[0]
    text = quoted.sub(lambda m: f"{m.group(1)}{m.group(2)}{tag('PERSONA', m.group(3)) if m.group(3) else ''}{m.group(2)}",
                      text)
    text = plain.sub(lambda m: f"{m.group(1)}{tag('PERSONA', m.group(2).strip())}", text)
    text = EMAIL_RE.sub(lambda m: tag("EMAIL", m.group(0)), text)
    for spec in _active:
        text = _mask_with(spec, text)
    return text


def mask(text: str, personal: bool = True) -> str:
    """Segreti sempre; dati personali salvo `personal=False` (scelta esplicita di chi invoca)."""
    text = mask_secrets(text)
    return mask_personal(text) if personal else text


# --- Schemi dei messaggi e stack trace ----------------------------------------------------------------------

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
HEX_RE = re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d+")
PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9-]*>|[\"\\]")
FRAME_RE = re.compile(r"^\s+at\s")

JSON_SUMMARY_KEYS = ("msg", "err.type", "err.message", "err.statusCode", "method", "req_method", "url", "req_path",
                     "resp_status", "statusCode")


def nested(source, dotted: str):
    """Legge 'kubernetes.container_name' sia da campi annidati sia da chiavi con il punto."""
    if not isinstance(source, dict):
        return None
    if dotted in source:
        return source[dotted]
    value = source
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def json_summary(text: str):
    """Per i message JSON (logger strutturati): i campi che dicono cosa e' successo, non il JSON grezzo."""
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    parts = [f"{key}={value}" for key in JSON_SUMMARY_KEYS
             if (value := nested(data, key)) not in (None, "", {}, [])]
    return " ".join(parts) or None


def template(message) -> str:
    """Schema del messaggio: prima riga con dati personali, id, esadecimali e numeri sostituiti da segnaposto.

    I dati personali vanno tolti PRIMA dei numeri: un CF con le cifre gia' sostituite non sarebbe piu'
    riconosciuto dal mascheramento e uscirebbe in parte in chiaro.
    """
    first = json_summary(str(message).strip()) or str(message).strip().split("\n", 1)[0]
    first = JWT_RE.sub("<jwt>", first)          # sulla riga intera: un token tagliato non sarebbe piu' riconosciuto
    first = AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)} <token>", first)
    first = TOKEN_RE.sub("<token>", first)
    for spec in _active:
        if spec.get("template"):
            first = spec["regex"].sub(f"<{spec['template']}>", first)
    first = EMAIL_RE.sub("<email>", first)
    return NUMBER_RE.sub("<n>", HEX_RE.sub("<hex>", UUID_RE.sub("<id>", first)))[:200]


def literal(schema: str) -> str:
    """Il tratto fisso piu' lungo di uno schema (tra segnaposto e virgolette), da usare come frase di match."""
    return max((part.strip(" :;,=[](){}'") for part in PLACEHOLDER_RE.split(schema)), key=len, default="")


def trim_stack(message: str, app_package: str = APP_PACKAGE) -> str:
    """Tiene le righe d'eccezione, il primo frame di ogni blocco e fino a APP_FRAMES frame applicativi."""
    lines = message.split("\n")
    if sum(1 for line in lines if FRAME_RE.match(line)) < 5:
        return message
    kept, in_block, app_kept, omitted = [], 0, 0, 0
    for line in lines:
        if not FRAME_RE.match(line):
            if omitted:
                kept.append(f"\t... {omitted} frame omessi")
            kept.append(line)
            in_block, app_kept, omitted = 0, 0, 0
            continue
        in_block += 1
        is_app = bool(app_package) and app_package in line
        if in_block == 1 or (is_app and app_kept < APP_FRAMES):
            kept.append(line)
            app_kept += is_app
        else:
            omitted += 1
    if omitted:
        kept.append(f"\t... {omitted} frame omessi")
    return "\n".join(kept)
