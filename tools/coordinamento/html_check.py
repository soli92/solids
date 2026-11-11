#!/usr/bin/env python3
"""Validazione dei deliverable HTML prima della consegna.

  python tools/coordinamento/html_check.py deliverables/coordinamento/report-pm/<operatore>/<data>/*.html

Per ogni file:
- HTML leggibile (UTF-8, parser senza eccezioni), <style> aperto e chiuso lo stesso numero di volte;
- nessun carattere di controllo (es. un \\b diventato backspace dentro un prompt);
- nessuna firma di generazione automatica (Co-Authored-By con email, "Generated with [Claude Code]",
  emoji robot) nel documento;
- se e' un batch (contiene <pre id="prompt">): il prompt contiene le sezioni obbligatorie e il
  pulsante di copia ha lo script.
Esce con 1 se almeno un file fallisce.
"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SEZIONI_BATCH = ["Controllo manuale prima di OGNI commit", "Vincoli di processo", "ai-policy-scan.py", "--strict"]
FIRME = [re.compile(r"Co-Authored-By:\s*[^<\n]*<[^>]+@[^>]+>", re.I), re.compile(r"Generated with \[Claude Code\]"),
         re.compile("\U0001F916")]
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def controlla(path):
    errori = []
    try:
        t = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ["non e' UTF-8"]
    try:
        p = HTMLParser()
        p.feed(t)
        p.close()
    except Exception as e:  # noqa: BLE001
        errori.append("parser HTML: %s" % e)
    ap, ch = len(re.findall(r"<style[\s>]", t)), t.count("</style>")
    if ap != ch or ap == 0:
        errori.append("<style> aperti %d, chiusi %d" % (ap, ch))
    if re.search(r"(?m)^\s*:root\{", t) and not re.search(r"<style[\s>]", t):
        errori.append("CSS fuori da <style>: verrebbe mostrato come testo")
    m = CTRL.search(t)
    if m:
        errori.append("carattere di controllo U+%04X alla posizione %d" % (ord(m.group()), m.start()))
    for rx in FIRME:
        if rx.search(t):
            errori.append("firma di generazione automatica: %s" % rx.pattern)
    mp = re.search(r'<pre id="prompt">(.*?)</pre>', t, re.S)
    if mp:
        prompt = html.unescape(mp.group(1))
        for s in SEZIONI_BATCH:
            if s not in prompt:
                errori.append("prompt senza la sezione obbligatoria: %s" % s)
        if "copyPrompt" in t and "function copyPrompt" not in t:
            errori.append("pulsante di copia senza script")
        if "<" in mp.group(1) and re.search(r"<(?!/?(b|i|code)\b)[a-z]", mp.group(1)):
            errori.append("tag HTML non escapato dentro il prompt")
    return errori


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    files = argv if argv is not None else sys.argv[1:]
    if not files:
        print(__doc__)
        return 2
    ko = 0
    for f in files:
        e = controlla(f)
        print(("OK  " if not e else "KO  ") + f)
        for x in e:
            print("     - " + x)
        ko += bool(e)
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
