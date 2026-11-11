#!/usr/bin/env python3
"""check-kanban-integrity.py — Check 3 (integrita' kanban), 4as (assignee), 4b (question ↔ kanban).

Implementa le regole di `.claude/skills/lint-checks-kanban.md` cosi' come sono scritte,
su tutta la popolazione (archivio incluso, artefatti aperti e chiusi).

Check 3
  EP   mancano id/title/status/priority/confidence              → ERROR missing-field
       id != ID della cartella (o del nome file)                  → ERROR id-mismatch
  US   mancano id/title/role/priority/status/wiki_page            → ERROR missing-field
       wiki_page valorizzato che non punta a un file esistente   → ERROR broken-wiki-page
  TSK  mancano id/sprint/layer/consumer/priority/estimate/status  → ERROR missing-field
       stesso id in piu' file                                     → ERROR id-duplicate
       layer ∉ {be, fe, db, qa, infra}                            → ERROR invalid-layer
       consumer ∉ {agent, human}                                  → ERROR invalid-consumer
       campo legacy team:                                         → WARNING deprecated-field
  ogni file <ID>.md senza frontmatter                             → ERROR missing-frontmatter
  frontmatter non leggibile come YAML (chi lo legge con un parser vero, come il report PM,
  lo scarta in silenzio)                                          → ERROR yaml-invalid se aperto,
                                                                    WARNING se chiuso
  Controllo a righe, senza PyYAML (stesso esito su ogni macchina): riga senza chiave, valore
  non quotato che contiene «: » (anche nelle voci di lista; esclusi i commenti in linea),
  blockquote `>` dentro il frontmatter. Sono le forme trovate su una derivata (10 file).
  Regole parametriche (blocco `lint.kanban` di factory.config.yaml, default = master): scope
  all|open, campi required/warning per tipo, severita' del layer e segmento prima di «/»,
  id-duplicate on/off. Vedi lint_comune.REGOLE_DEFAULT.
  Un campo presente ma vuoto (`""`, `[]`, `null`) conta come mancante. Se l'unico campo
  mancante e' `id` (deducibile dal nome file) il finding e' heal-eligible (heal-protocol).
  La prima voce di Check 4 («ogni US referenzia una pagina wiki: esiste?») coincide con
  broken-wiki-page e si riporta una volta sola, qui.
Check 4as (WARNING-only, silenzioso senza `assignee:`)
  4as.1  assignee su TSK in stato di chiusura                     → stale-assignee-on-closed
  4as.2  assignee su TSK con consumer: agent                      → assignee-on-agent-consumer
  Lo script non distingue un'identita' umana da un altro valore: ogni assignee valorizzato conta.
Check 4b (WARNING) su management/questions.md, sezioni [APERTE] / [RISOLTE]
  question aperta senza `**Bloccante:**`                          → missing-blocking-level
  question risolta ancora in blocked_by/pending_clarification di una US → stale-blocked-by
  question in pending_clarification di una US non citata nel pending_clarification di alcun ADR
                                                                  → orphan-pending-clarification

USO:
  python3 tools/lint/check-kanban-integrity.py [--root <factory>] [--json] [--out <file>] [--strict]

Solo stdlib. Read-only (scrive solo --out). Exit 0 sempre; con --strict exit 1 se c'e' un ERROR.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_comune as lc  # noqa: E402
from lint_comune import kanban_ids  # noqa: E402

QUESTIONS = 'management/questions.md'
CAMPI = {
    'EP': ('id', 'title', 'status', 'priority', 'confidence'),
    'US': ('id', 'title', 'role', 'priority', 'status', 'wiki_page'),
    # sprint e' facoltativo sui TSK (v2.43+): rimosso dai campi obbligatori.
    # WARNING in-progress-senza-sprint se status in {in_progress, review} e sprint assente.
    'TSK': ('id', 'layer', 'consumer', 'priority', 'estimate', 'status'),
}
# CAMPI_IDENTITA: sempre ERROR anche su artefatti chiusi (servono alla derivazione
# dello stato in PATTERN §8). Gli altri campi mancanti sui chiusi diventano INFO aggregata.
CAMPI_IDENTITA = {'id', 'status'}
# STATI_IN_PROGRESS: normalizziamo in-progress → in_progress prima del confronto
STATI_IN_PROGRESS = {'in_progress', 'review'}
CONSUMERS = {'agent', 'human'}
CHIUSURA = {'done', 'completed', 'superseded', 'cancelled', 'renamed', 'wontfix'}
Q_RE = re.compile(r'\bQ[-_](?:[A-Z0-9]+-)*\d+\b')


def vuoto(v):
    if isinstance(v, list):
        return not v
    return v is None or str(v).strip() in ('', 'null', '~')


def norm(v):
    return lc.testo_di(v).strip().lower().replace('-', '_')


def _wiki_page_esiste(radice, valore, slugs):
    v = valore.strip().strip('[]').split('|')[0].split('#')[0].split(' §')[0].strip()
    if not v:
        return True
    candidati = (v, os.path.join('wiki', v), v + '.md', os.path.join('wiki', v + '.md'))
    if any(os.path.isfile(os.path.join(radice, c)) for c in candidati):
        return True
    return os.path.splitext(os.path.basename(v))[0].lower() in slugs


_CHIAVE_YAML = re.compile(r"^[A-Za-z_][\w-]*:(\s|$)")


def yaml_invalido(testo):
    """Motivo per cui il frontmatter non e' YAML valido, o None (controllo a righe, stdlib)."""
    m = re.match(r"---\n(.*?)\n---", testo, re.S)
    if not m:
        return None
    blocco = False  # dentro uno scalare a blocco (| o >): le righe indentate sono testo
    for n, line in enumerate(m.group(1).splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indentata = line.startswith((" ", "\t"))
        if blocco and indentata:
            continue
        blocco = False
        if not indentata:
            if line.startswith(">"):
                return "blockquote dentro il frontmatter (riga %d)" % n
            if not line.startswith("- ") and not _CHIAVE_YAML.match(line):
                return "riga senza chiave (riga %d)" % n
        voce = line.strip()
        if voce.startswith("- "):
            voce = voce[2:].strip()
        if not _CHIAVE_YAML.match(voce):
            continue
        valore = voce.split(":", 1)[1].strip()
        if valore[:1] not in ("\"", "'"):
            valore = valore.split(" #", 1)[0].strip()  # commento in linea: lo YAML lo ignora
        if valore[:1] in ("|", ">"):
            blocco = True
            continue
        if valore and valore[0] not in "\"'[{&*!" and ": " in valore:
            return "valore non quotato con «: » (riga %d)" % n
    return None


def check_3(radice, arts):
    layers = lc.leggi_routing_layers(radice)
    regole = lc.regole_lint(radice)['kanban']
    solo_aperti = regole['scope'] == 'open'
    out = []
    slugs = set()
    for d, _, fs in os.walk(os.path.join(radice, 'wiki')):
        slugs.update(f[:-3].lower() for f in fs if f.endswith('.md'))
    per_id = {}
    # Per artefatti CHIUSI: raccoglie i campi mancanti (non d'identita') per INFO aggregata.
    # Formato: (tipo, campo) -> [id1, id2, ...]
    chiusi_mancanti = {}
    for a in arts:
        if a.fm is None:
            out.append(lc.finding('ERROR', 'missing-frontmatter', '3', '%s — frontmatter assente o non chiuso' % a.rel,
                                  path=a.rel))
            continue
        motivo = yaml_invalido(lc.leggi(a.path))
        chiuso = norm(lc.testo_di(a.fm.get('status')).strip()) in CHIUSURA
        if motivo:
            out.append(lc.finding('WARNING' if chiuso else 'ERROR', 'yaml-invalid', '3',
                                  '%s — frontmatter non valido come YAML: %s' % (a.rel, motivo),
                                  path=a.rel))
        if solo_aperti and chiuso:
            continue  # lint.kanban.scope: open — la storia non si riscrive
        eq = regole.get('equivalents') or {}
        assente = lambda k: vuoto(a.fm.get(k)) and all(vuoto(a.fm.get(x)) for x in (eq.get(k) or []))
        consigliati = [k for k in regole['warning'].get(a.tipo, []) if assente(k)]
        if consigliati:
            out.append(lc.finding('WARNING', 'missing-recommended', '3', '%s — mancano (consigliati): %s'
                                  % (a.rel, ', '.join(consigliati)), path=a.rel))
        mancano = [k for k in regole['required'].get(a.tipo, CAMPI[a.tipo]) if assente(k)]
        if mancano:
            stato_val = norm(lc.testo_di(a.fm.get('status')).strip())
            is_chiuso = stato_val in CHIUSURA
            if is_chiuso:
                # Artefatto CHIUSO: ERROR solo per id/status; altri campi → INFO aggregata
                mancano_id = [k for k in mancano if k in CAMPI_IDENTITA]
                if mancano_id:
                    out.append(lc.finding('ERROR', 'missing-field', '3',
                                          '%s — mancano (identita\'): %s' % (a.rel, ', '.join(mancano_id)),
                                          path=a.rel))
                for k in mancano:
                    if k not in CAMPI_IDENTITA:
                        chiavi = (a.tipo, k)
                        chiusi_mancanti.setdefault(chiavi, []).append(a.id)
            else:
                # Artefatto APERTO: tutti i campi mancanti → ERROR (invariato)
                heal = mancano == ['id']
                out.append(lc.finding('ERROR', 'missing-field', '3', '%s — mancano: %s%s'
                                      % (a.rel, ', '.join(mancano), ' (heal-eligible: id dal nome file)' if heal else ''),
                                      path=a.rel, heal_eligible=heal))
        ident = lc.testo_di(a.fm.get('id')).strip()
        if a.tipo == 'EP' and ident:
            cartella = kanban_ids.id_cartella(os.path.basename(os.path.dirname(a.path)))[0]
            if ident != a.id or (cartella is not None and cartella != ident):
                out.append(lc.finding('ERROR', 'id-mismatch', '3', '%s — id: %s, file %s, cartella %s'
                                      % (a.rel, ident, a.id, cartella or '(senza ID)'), path=a.rel))
        if a.tipo == 'US' and not vuoto(a.fm.get('wiki_page')):
            pagine = a.fm['wiki_page'] if isinstance(a.fm['wiki_page'], list) else [a.fm['wiki_page']]
            for wp in pagine:
                if not _wiki_page_esiste(radice, str(wp), slugs):
                    out.append(lc.finding('ERROR', 'broken-wiki-page', '3', '%s — wiki_page: %s inesistente'
                                          % (a.rel, wp), path=a.rel))
        if a.tipo == 'TSK':
            per_id.setdefault(ident or a.id, []).append(a.rel)
            layer = lc.testo_di(a.fm.get('layer')).strip()
            if regole['layer_segment']:
                layer = layer.split('/')[0].strip()
            if layer and layer not in layers:
                out.append(lc.finding('ERROR' if regole['layer_severity'] == 'error' else 'WARNING',
                                      'invalid-layer', '3', '%s — layer: %s (ammessi: %s)'
                                      % (a.rel, layer, ', '.join(sorted(layers))), path=a.rel))
            consumer = lc.testo_di(a.fm.get('consumer')).strip()
            if consumer and consumer not in CONSUMERS:
                out.append(lc.finding('ERROR', 'invalid-consumer', '3', '%s — consumer: %s (ammessi: agent, human)'
                                      % (a.rel, consumer), path=a.rel))
            if 'team' in a.fm:
                out.append(lc.finding('WARNING', 'deprecated-field', '3', '%s — campo legacy team: (migrare a layer:)'
                                      % a.rel, path=a.rel))
            # sprint facoltativo: WARNING se in-progress/review senza sprint
            st_norm = norm(lc.testo_di(a.fm.get('status')).strip())
            if regole['in_progress_needs_sprint'] and st_norm in STATI_IN_PROGRESS and vuoto(a.fm.get('sprint')):
                out.append(lc.finding('WARNING', 'in-progress-senza-sprint', '3',
                                      '%s — status: %s senza sprint: (pianificare lo sprint prima di avviare)'
                                      % (a.rel, st_norm), path=a.rel))
    for ident in sorted(per_id) if regole['id_duplicate'] else []:
        if len(per_id[ident]) > 1:
            out.append(lc.finding('ERROR', 'id-duplicate', '3', '%s in %d file' % (ident, len(per_id[ident])),
                                  dettagli=sorted(per_id[ident])))
    # INFO aggregata per i campi mancanti su artefatti chiusi (1 riga per tipo+campo)
    for (tipo, campo) in sorted(chiusi_mancanti):
        esempi = chiusi_mancanti[(tipo, campo)]
        cnt = len(esempi)
        esempi3 = ', '.join(esempi[:3])
        out.append(lc.finding('INFO', 'missing-field-closed', '3',
                              '%s: %d artefatti chiusi senza %s (esempi: %s)'
                              % (tipo, cnt, campo, esempi3)))
    return out


def check_4as(arts, solo_aperti=False):
    out = []
    for a in arts:
        if a.tipo != 'TSK' or not a.fm or vuoto(a.fm.get('assignee')):
            continue
        chi = lc.testo_di(a.fm['assignee']).strip()
        st = lc.testo_di(a.fm.get('status')).strip()
        if norm(st) in CHIUSURA:
            out.append(lc.finding('WARNING', 'assignee', '4as.1',
                                  '%s: stale-assignee-on-closed — `assignee: %s` su status: %s (FM-NEW-4 riallocazione '
                                  'non tracciata: rimuovere il campo alla chiusura o riconciliarlo)' % (a.id, chi, st),
                                  path=a.rel))
        if lc.testo_di(a.fm.get('consumer')).strip() == 'agent' and not (solo_aperti and norm(st) in CHIUSURA):
            out.append(lc.finding('WARNING', 'assignee', '4as.2',
                                  '%s: assignee-on-agent-consumer — `assignee: %s` su consumer: agent (il campo copre il '
                                  'lavoro umano pianificato; copertura 0%% sul traffico di claim agentico)' % (a.id, chi),
                                  path=a.rel))
    return out


def _sezioni_questions(testo):
    """{'APERTE': [(intestazione, corpo)], 'RISOLTE': [...]} dalle sezioni `## [APERTE]` / `## [RISOLTE]`."""
    out = {'APERTE': [], 'RISOLTE': []}
    corrente, voce, corpo = None, None, []

    def chiudi():
        if corrente and voce is not None:
            out[corrente].append((voce, '\n'.join(corpo)))

    for line in testo.splitlines():
        m = re.match(r'^##\s+\[(APERTE|RISOLTE)\]', line)
        if m:
            chiudi()
            corrente, voce, corpo = m.group(1), None, []
            continue
        if re.match(r'^##\s', line) and not line.startswith('###'):
            chiudi()
            corrente, voce, corpo = None, None, []
            continue
        if corrente and re.match(r'^###+\s', line):
            chiudi()
            voce, corpo = line, []
            continue
        if voce is not None:
            corpo.append(line)
    chiudi()
    return out


def _adr_pending(radice):
    citate = set()
    for base in ('design_&_architecture', 'wiki'):
        for d, _, fs in os.walk(os.path.join(radice, base)):
            for f in fs:
                if f.startswith('ADR-') and f.endswith('.md'):
                    fm = lc.frontmatter(os.path.join(d, f)) or {}
                    citate.update(Q_RE.findall(lc.testo_di(fm.get('pending_clarification'))))
    return citate


def check_4b(radice, arts):
    out = []
    path = os.path.join(radice, QUESTIONS)
    if not os.path.isfile(path):
        return out, ['[4b] %s assente: check non eseguito' % QUESTIONS]
    sez = _sezioni_questions(lc.leggi(path))
    for voce, corpo in sez['APERTE']:
        ids = Q_RE.findall(voce)
        if not ids:
            continue
        if not re.search(r'\*\*Bloccante:?\*\*:?', corpo):
            for q in ids:
                out.append(lc.finding('WARNING', 'questions', '4b',
                                      '%s: missing-blocking-level — nessun campo `**Bloccante:** hard | soft` (default: hard)'
                                      % q, path=QUESTIONS))
    risolte = {q for voce, _ in sez['RISOLTE'] for q in Q_RE.findall(voce)}
    adr = _adr_pending(radice)
    for a in arts:
        if a.tipo != 'US' or not a.fm:
            continue
        for campo in ('blocked_by', 'pending_clarification'):
            for q in sorted(set(Q_RE.findall(lc.testo_di(a.fm.get(campo)))) & risolte):
                out.append(lc.finding('WARNING', 'questions', '4b',
                                      '%s: stale-blocked-by — %s cita %s, gia\' risolta (riconciliare: product-manager)'
                                      % (a.id, campo, q), path=a.rel))
        for q in sorted(set(Q_RE.findall(lc.testo_di(a.fm.get('pending_clarification')))) - adr):
            out.append(lc.finding('WARNING', 'questions', '4b',
                                  '%s: orphan-pending-clarification — %s non citata nel pending_clarification di alcun ADR'
                                  % (a.id, q), path=a.rel))
    diag = ['[4b] question lette: %d aperte, %d risolte' % (len(sez['APERTE']), len(risolte))]
    return out, diag


def check(radice):
    arts = lc.raccogli_kanban(radice)
    findings = check_3(radice, arts) + check_4as(arts, lc.regole_lint(radice)['kanban']['scope'] == 'open')
    f4b, diag = check_4b(radice, arts)
    findings += f4b
    conta = lc.conteggi(findings)
    n = {t: sum(1 for a in arts if a.tipo == t) for t in ('EP', 'US', 'TSK')}
    diag = ['[3] popolazione: %d EP, %d US, %d TSK (aperti e chiusi, archivio incluso)' % (n['EP'], n['US'], n['TSK'])] + diag
    per_check = {}
    for f in findings:
        k = '%s/%s' % (f['check'], f['codice'])
        per_check[k] = per_check.get(k, 0) + 1
    diag.append('[3/4as/4b] %d ERROR, %d WARNING — %s' % (conta['ERROR'], conta['WARNING'],
                ', '.join('%s=%d' % kv for kv in sorted(per_check.items())) or 'nessun finding'))
    return findings, diag, {'popolazione': n, 'per_check': per_check}


def main(argv=None):
    args = lc.parser(__doc__).parse_args(argv)
    findings, diag, stats = check(args.root)
    return lc.emetti(args, '3, 4as, 4b', findings, diag, stats)


if __name__ == '__main__':
    sys.exit(main())
