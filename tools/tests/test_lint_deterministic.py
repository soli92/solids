"""Test dei check deterministici di /lint (EP-071 US-324, TSK-739).

Ogni caso gira sulle due forme di kanban della flotta:
- «A»: ID con prefisso di namespace, cartelle senza slug (XX-EP-001/XX-US-001/XX-TSK-001.md);
- «B»: ID senza prefisso, cartelle con slug (EP-001-alfa/US-001-beta/TSK-001.md).
Una factory pulita non produce finding; ogni difetto iniettato produce esattamente il suo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[2]
LINT = RADICE / 'tools' / 'lint'
OGGI = '2026-10-06'


def esegui(script, root, *argomenti):
    r = subprocess.run([sys.executable, str(LINT / script), '--root', str(root), *argomenti],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def findings(script, root, *argomenti):
    code, out = esegui(script, root, '--json', *argomenti)
    assert code == 0, out
    return json.loads(out)['findings']


def chiavi(fs):
    return sorted('%s/%s' % (f['check'], f['codice']) for f in fs)


def _fm(campi):
    righe = ['---']
    for k, v in campi.items():
        if isinstance(v, list):
            v = '[%s]' % ', '.join(v)
        righe.append('%s: %s' % (k, v))
    return '\n'.join(righe + ['---', ''])


class Factory:
    def __init__(self, root: Path, forma: str):
        self.root, self.forma = root, forma
        self.p = 'XX-' if forma == 'A' else ''
        (root / 'wiki' / 'concepts').mkdir(parents=True)
        (root / 'wiki' / 'concepts' / 'pagina.md').write_text(_fm({'updated': OGGI}) + '# Pagina\n')
        (root / 'wiki' / 'index.md').write_text('# Indice\n\n- [[pagina]]\n')
        (root / 'management' / 'kanban').mkdir(parents=True)

    def id(self, tipo, n):
        return '%s%s-%03d' % (self.p, tipo, n)

    def cartella(self, tipo, n):
        slug = {'EP': '-alfa', 'US': '-beta'}[tipo] if self.forma == 'B' else ''
        return self.id(tipo, n) + slug

    def ep(self, n, status='todo', corpo=None, **extra):
        d = self.root / 'management' / 'kanban' / self.cartella('EP', n)
        d.mkdir(parents=True, exist_ok=True)
        campi = dict(id=self.id('EP', n), title='"Epica"', status=status, priority='P2', confidence='80%')
        campi.update(extra)
        if corpo is None:
            corpo = '| US | Titolo |\n|---|---|\n' + ''.join(
                '| [%s](x/%s.md) | t |\n' % (u, u) for u in getattr(self, '_us_di_%d' % n, []))
        (d / (self.id('EP', n) + '.md')).write_text(_fm({k: v for k, v in campi.items() if v is not None}) + '\n' + corpo)
        return d

    def us(self, ep_n, n, status='todo', **extra):
        d = self.root / 'management' / 'kanban' / self.cartella('EP', ep_n) / self.cartella('US', n)
        d.mkdir(parents=True, exist_ok=True)
        campi = dict(id=self.id('US', n), epic=self.id('EP', ep_n), title='"Storia"', role='dev', priority='P2',
                     status=status, wiki_page='wiki/concepts/pagina.md')
        campi.update(extra)
        (d / (self.id('US', n) + '.md')).write_text(_fm({k: v for k, v in campi.items() if v is not None}) + '\n# US\n')
        setattr(self, '_us_di_%d' % ep_n, getattr(self, '_us_di_%d' % ep_n, []) + [self.id('US', n)])
        return d

    def tsk(self, ep_n, us_n, n, status='todo', corpo='', **extra):
        d = self.root / 'management' / 'kanban' / self.cartella('EP', ep_n) / self.cartella('US', us_n)
        d.mkdir(parents=True, exist_ok=True)
        campi = dict(id=self.id('TSK', n), story=self.id('US', us_n), epic=self.id('EP', ep_n), sprint='1',
                     layer='be', consumer='agent', priority='P2', estimate='S', status=status)
        campi.update(extra)
        f = d / (self.id('TSK', n) + '.md')
        f.write_text(_fm({k: v for k, v in campi.items() if v is not None}) + '\n# TSK\n' + corpo)
        return f

    def sprint(self, righe):
        corpo = '| ID | Titolo | Status |\n|---|---|---|\n' + ''.join('| %s | t | %s |\n' % r for r in righe)
        (self.root / 'management' / 'kanban' / 'sprint.md').write_text('# Sprint\n\n' + corpo)


@pytest.fixture(params=['A', 'B'])
def fx(request, tmp_path):
    return Factory(tmp_path / ('f' + request.param), request.param)


def pulita(fx, us_status='todo', tsk_status=('todo',)):
    for i, s in enumerate(tsk_status, 1):
        fx.tsk(1, 1, i, status=s)
    fx.us(1, 1, status=us_status)
    fx.ep(1)


# ------------------------------------------------------------------ factory pulita

def test_factory_pulita_nessun_finding(fx):
    pulita(fx, tsk_status=('todo', 'done'))
    fx.sprint([('[%s](p.md)' % fx.id('TSK', 1), 'todo'), ('**%s**' % fx.id('TSK', 2), 'done')])
    assert findings('check-status-rollup.py', fx.root) == []
    assert findings('check-kanban-integrity.py', fx.root) == []
    assert findings('check-wiki-structure.py', fx.root, '--oggi', OGGI) == []


# ------------------------------------------------------------------ 4au

def test_4au_1_us_aperta_tsk_tutti_terminali(fx):
    pulita(fx, us_status='todo', tsk_status=('done', 'cancelled'))
    assert chiavi(findings('check-status-rollup.py', fx.root)) == ['4au.1/status-rollup']


def test_4au_1_tsk_misti_nessun_finding(fx):
    pulita(fx, us_status='todo', tsk_status=('done', 'todo'))
    assert findings('check-status-rollup.py', fx.root) == []


def test_4au_2_us_chiusa_con_tsk_aperto(fx):
    fx.tsk(1, 1, 1, status='done')
    fx.tsk(1, 1, 2, status='todo')
    fx.us(1, 1, status='done')
    fx.ep(1, status='done')
    fs = findings('check-status-rollup.py', fx.root)
    assert chiavi(fs) == ['4au.2/status-rollup']
    assert any(fx.id('TSK', 2) in d for d in fs[0]['dettagli'])


def test_4au_3_epica_aperta_us_tutte_terminali(fx):
    fx.tsk(1, 1, 1, status='done')
    fx.us(1, 1, status='done')
    fx.ep(1, status='in-progress')
    assert chiavi(findings('check-status-rollup.py', fx.root)) == ['4au.3/status-rollup']


def test_4au_4_epica_chiusa_us_aperta(fx):
    fx.tsk(1, 1, 1, status='todo')
    fx.us(1, 1, status='todo')
    fx.ep(1, status='done')
    assert chiavi(findings('check-status-rollup.py', fx.root)) == ['4au.4/status-rollup']


def test_4au_5_sprint_disallineato(fx):
    pulita(fx, tsk_status=('done', 'todo'))
    fx.sprint([('[%s](p.md)' % fx.id('TSK', 1), 'todo')])
    fs = findings('check-status-rollup.py', fx.root)
    assert chiavi(fs) == ['4au.5/status-rollup']
    assert 'sprint.md="todo" vs file="done"' in fs[0]['dettagli'][0]


def test_4au_5_granularita_us_e_normalizzazioni(fx):
    # G2 a livello US; V2: in-progress = in_progress; ~~cancelled~~ = cancelled; completed ~ done (scenario 11)
    fx.tsk(1, 1, 1, status='cancelled')
    fx.tsk(1, 1, 2, status='done')
    fx.tsk(1, 1, 3, status='todo')
    fx.us(1, 1, status='in-progress')
    fx.ep(1)
    fx.sprint([(fx.id('US', 1), 'in_progress'), (fx.id('TSK', 1), '~~cancelled~~'), (fx.id('TSK', 2), 'completed'),
               (fx.id('TSK', 3), '**todo**')])
    assert findings('check-status-rollup.py', fx.root) == []


def test_4au_6_us_in_tabella_senza_file(fx):
    pulita(fx)
    fantasma = fx.id('US', 9)
    fx.ep(1, corpo='| US | t |\n|---|---|\n| [%s](x.md) | t |\n| [%s](y.md) | t |\n' % (fx.id('US', 1), fantasma))
    fs = findings('check-status-rollup.py', fx.root)
    assert chiavi(fs) == ['4au.6/status-rollup']
    assert fantasma in fs[0]['dettagli'][0]


def test_4au_7_us_non_elencata_e_epica_inesistente(fx):
    pulita(fx)
    fx.ep(1, corpo='nessuna tabella\n')
    fx.us(1, 2, status='todo', epic=fx.id('EP', 7))
    fs = findings('check-status-rollup.py', fx.root)
    assert chiavi(fs) == ['4au.7/status-rollup', '4au.7/status-rollup']
    note = ' '.join(f['dettagli'][0] for f in fs)
    assert 'file epica non trovato' in note and 'potenziale falso positivo' in note


def test_4au_5_backtick_normalizzato(fx):
    """`done` (con backtick) in sprint.md e' normalizzato come 'done': nessun disallineamento."""
    # us_status=done, ep_status=done evitano 4au.1/4au.3 (tutto terminale)
    fx.tsk(1, 1, 1, status='done')
    fx.us(1, 1, status='done')
    fx.ep(1, status='done')
    fx.sprint([(fx.id('TSK', 1), '`done`')])
    assert findings('check-status-rollup.py', fx.root) == []


def test_4au_5_stato_non_riconosciuto_info(fx):
    """Cella sprint.md con stato non riconosciuto -> INFO, non WARNING."""
    # us/ep chiuse per evitare 4au.1/4au.3
    fx.tsk(1, 1, 1, status='done')
    fx.us(1, 1, status='done')
    fx.ep(1, status='done')
    fx.sprint([(fx.id('TSK', 1), 'Q4-2026')])  # non uno stato valido
    fs = findings('check-status-rollup.py', fx.root)
    # Esattamente 1 finding INFO (non WARNING) per lo stato non riconosciuto
    assert len(fs) == 1 and fs[0]['sev'] == 'INFO' and '4au.5' in fs[0]['check']


def test_4au_v1_status_nel_corpo_ignorato(fx):
    fx.tsk(1, 1, 1, status='done', corpo='```yaml\nstatus: todo\n```\n')
    fx.us(1, 1, status='done')
    fx.ep(1, status='done')
    assert findings('check-status-rollup.py', fx.root) == []


def test_4au_v1_frontmatter_4kb_ora_letto(fx):
    """LIMITE_V1 alzato a 64 KB: frontmatter da 4200 char ora letto e incluso nel roll-up."""
    fx.tsk(1, 1, 1, status='done')
    fx.us(1, 1, status='todo', note='"%s"' % ('x' * 4200))
    fx.ep(1)
    code, out = esegui('check-status-rollup.py', fx.root)
    assert code == 0
    # Non piu' escluso: nessuna riga "[4au] V1: 1 artefatti..."
    assert '[4au] V1: 1 artefatti' not in out
    # Ora letto: 4au.1 scatta (US todo con TSK done)
    assert '4au.1=1' in out


def test_4au_tsk_dichiarati_in_tsk_range(fx):
    # un TSK di un'altra US, dichiarato dalla US in tsk_range, entra nel suo roll-up
    fx.tsk(1, 2, 5, status='todo')
    fx.us(1, 2, status='todo')
    fx.tsk(1, 1, 1, status='done')
    fx.us(1, 1, status='done', tsk_range='%s..%s' % (fx.id('TSK', 1), fx.id('TSK', 5)))
    fx.ep(1)
    assert chiavi(findings('check-status-rollup.py', fx.root)) == ['4au.2/status-rollup']


def test_4au_riepilogo_completo(fx):
    pulita(fx)
    code, out = esegui('check-status-rollup.py', fx.root)
    assert 'Riepilogo 4au: 4au.1=0, 4au.2=0, 4au.3=0, 4au.4=0, 4au.5=0, 4au.6=0, 4au.7=0' in out


# ------------------------------------------------------------------ Check 3, 4as, 4b

@pytest.mark.parametrize('difetto, atteso', [
    ({'priority': None}, '3/missing-field'),
    # docs e' nel fallback LAYERS_DEFAULT e non produce invalid-layer (factory senza config)
    ({'layer': 'xyz_invalid'}, '3/invalid-layer'),
    ({'consumer': 'bot'}, '3/invalid-consumer'),
    ({'team': 'be'}, '3/deprecated-field'),
])
def test_check_3_tsk(fx, difetto, atteso):
    fx.tsk(1, 1, 1, **difetto)
    fx.us(1, 1)
    fx.ep(1)
    assert chiavi(findings('check-kanban-integrity.py', fx.root)) == [atteso]


def test_check_3_layer_da_routing(tmp_path):
    """Layer validi letti da factory.config.yaml routing:; fallback se assente."""
    # Factory con routing: solo {be, fe}
    f = Factory(tmp_path / 'fR', 'B')
    (tmp_path / 'fR' / 'factory.config.yaml').write_text('routing:\n  be: agent\n  fe: agent\n')
    f.tsk(1, 1, 1, layer='be')   # valido
    f.tsk(1, 1, 2, layer='docs') # docs NON in routing -> invalid-layer
    f.us(1, 1)
    f.ep(1)
    fs = findings('check-kanban-integrity.py', f.root)
    errs = [x for x in fs if x['codice'] == 'invalid-layer']
    assert len(errs) == 1 and 'docs' in errs[0]['messaggio']


def test_check_3_layer_fallback_senza_config(tmp_path):
    """Senza factory.config.yaml, fallback = {be, fe, db, qa, infra, docs}."""
    f = Factory(tmp_path / 'fF', 'B')
    f.tsk(1, 1, 1, layer='docs')   # valido nel fallback
    f.tsk(1, 1, 2, layer='xyz')    # non valido
    f.us(1, 1)
    f.ep(1)
    fs = findings('check-kanban-integrity.py', f.root)
    errs = [x for x in fs if x['codice'] == 'invalid-layer']
    assert len(errs) == 1 and 'xyz' in errs[0]['messaggio']


def test_check_3_chiuso_mancano_non_identita_info(fx):
    """Artefatto CHIUSO con campo non-identita' mancante -> INFO aggregata, non ERROR."""
    fx.tsk(1, 1, 1, status='done', priority=None)  # priority mancante su done
    fx.us(1, 1, status='done')
    fx.ep(1, status='done')
    fs = findings('check-kanban-integrity.py', fx.root)
    # Nessun ERROR missing-field (la priority e' un campo non-identita' su artefatto chiuso)
    errori = [x for x in fs if x['sev'] == 'ERROR' and x['codice'] == 'missing-field']
    assert errori == []
    # Deve esserci esattamente 1 INFO aggregata per (TSK, priority)
    info_chiusi = [x for x in fs if x['sev'] == 'INFO' and x['codice'] == 'missing-field-closed']
    assert len(info_chiusi) == 1
    assert 'TSK' in info_chiusi[0]['messaggio'] and 'priority' in info_chiusi[0]['messaggio']


def test_check_3_chiuso_mancano_identita_error(fx):
    """Artefatto CHIUSO con id o status mancante -> ERROR (campi d'identita')."""
    fx.tsk(1, 1, 1, status='done', id=None)  # id mancante su done -> ERROR
    fx.us(1, 1)
    fx.ep(1)
    fs = findings('check-kanban-integrity.py', fx.root)
    errori = [x for x in fs if x['sev'] == 'ERROR' and x['codice'] == 'missing-field']
    assert len(errori) == 1


def test_check_3_aperto_mancano_tutti_error(fx):
    """Artefatto APERTO con campo mancante -> ERROR (invariato)."""
    fx.tsk(1, 1, 1, status='todo', priority=None)
    fx.us(1, 1)
    fx.ep(1)
    fs = findings('check-kanban-integrity.py', fx.root)
    errori = [x for x in fs if x['sev'] == 'ERROR' and x['codice'] == 'missing-field']
    assert len(errori) == 1


def test_check_3_sprint_facoltativo_todo(fx):
    """sprint facoltativo: TSK todo senza sprint -> nessun finding."""
    fx.tsk(1, 1, 1, status='todo', sprint=None)
    fx.us(1, 1)
    fx.ep(1)
    fs = findings('check-kanban-integrity.py', fx.root)
    assert all(f['codice'] != 'missing-field' or 'sprint' not in f['messaggio'] for f in fs)
    assert all(f['codice'] != 'in-progress-senza-sprint' for f in fs)


def test_check_3_sprint_warning_in_progress(fx):
    """TSK in-progress senza sprint -> WARNING in-progress-senza-sprint."""
    fx.tsk(1, 1, 1, status='in-progress', sprint=None)
    fx.us(1, 1)
    fx.ep(1)
    fs = findings('check-kanban-integrity.py', fx.root)
    warns = [x for x in fs if x['codice'] == 'in-progress-senza-sprint']
    assert len(warns) == 1


def test_check_3_id_heal_eligible_solo_se_manca_solo_id(fx):
    fx.tsk(1, 1, 1, id=None)               # solo id mancante -> heal_eligible=True
    fx.tsk(1, 1, 2, id=None, priority=None) # id e priority mancanti -> heal_eligible=False
    fx.us(1, 1)
    fx.ep(1)
    fs = sorted(findings('check-kanban-integrity.py', fx.root), key=lambda f: f['path'])
    assert [f['heal_eligible'] for f in fs] == [True, False]


def test_check_3_ep_us_e_duplicati(fx):
    fx.tsk(1, 1, 1)
    fx.tsk(1, 1, 2, id=fx.id('TSK', 1))
    fx.us(1, 1, wiki_page='wiki/concepts/inesistente.md', role=None)
    fx.ep(1, id=fx.id('EP', 2), confidence=None)
    (fx.root / 'management' / 'kanban' / fx.cartella('EP', 1) / (fx.id('US', 5) + '.md')).write_text('# senza\n')
    assert chiavi(findings('check-kanban-integrity.py', fx.root)) == [
        '3/broken-wiki-page', '3/id-duplicate', '3/id-mismatch', '3/missing-field', '3/missing-field',
        '3/missing-frontmatter']


def test_4as(fx):
    fx.tsk(1, 1, 1, status='done', consumer='human', assignee='anna')
    fx.tsk(1, 1, 2, status='todo', consumer='agent', assignee='anna')
    fx.tsk(1, 1, 3, status='done')
    fx.us(1, 1)
    fx.ep(1)
    assert chiavi(findings('check-kanban-integrity.py', fx.root)) == ['4as.1/assignee', '4as.2/assignee']


def test_4b(fx):
    fx.tsk(1, 1, 1)
    fx.us(1, 1, blocked_by='[Q-002]', pending_clarification='[Q-003]')
    fx.ep(1)
    (fx.root / 'management' / 'questions.md').write_text(
        '# Q\n\n## [APERTE]\n\n### Q-001 — senza livello\n\ntesto\n\n'
        '### Q-003 — con livello\n\n**Bloccante:** soft\n\n## [RISOLTE]\n\n### Q-002 — chiusa\n\nfatto\n')
    fs = findings('check-kanban-integrity.py', fx.root)
    msg = sorted(f['messaggio'].split(' — ')[0] for f in fs)
    assert msg == ['Q-001: missing-blocking-level', '%s: orphan-pending-clarification' % fx.id('US', 1),
                   '%s: stale-blocked-by' % fx.id('US', 1)]
    adr = fx.root / 'design_&_architecture' / 'decisions'
    adr.mkdir(parents=True)
    (adr / 'ADR-001.md').write_text(_fm({'pending_clarification': '[Q-003]'}) + '# ADR\n')
    assert len(findings('check-kanban-integrity.py', fx.root)) == 2


# ------------------------------------------------------------------ Check 1, 4, 4ag

def test_check_1_orphan_e_broken_link(fx):
    pulita(fx)
    w = fx.root / 'wiki' / 'concepts'
    (w / 'orfana.md').write_text(_fm({'updated': OGGI}) + 'vedi [[pagina]] e [[paginaa]] e [[nulla-del-genere]]\n')
    fs = findings('check-wiki-structure.py', fx.root, '--oggi', OGGI)
    assert chiavi(fs) == ['1/broken-link', '1/broken-link', '1/orphan']
    heal = {f['messaggio'].split('[[')[1].split(']]')[0]: f['heal_eligible'] for f in fs if f['codice'] == 'broken-link'}
    assert heal == {'paginaa': True, 'nulla-del-genere': False}


def test_check_4_storie_collegate(fx):
    pulita(fx)
    (fx.root / 'wiki' / 'concepts' / 'pagina.md').write_text(
        _fm({'updated': OGGI}) + '# P\n\n## Storie collegate\n\n- [%s](x.md)\n- %s\n\n## Altro\n\n%s\n'
        % (fx.id('US', 1), fx.id('US', 8), fx.id('US', 9)))
    fs = findings('check-wiki-structure.py', fx.root, '--oggi', OGGI)
    assert chiavi(fs) == ['4/story-missing']
    assert fx.id('US', 8) in fs[0]['messaggio']


def test_check_4ag(fx):
    pulita(fx)
    w = fx.root / 'wiki' / 'concepts'
    (w / 'vecchia.md').write_text(_fm({'updated': '2025-01-01'}) + 'x\n')
    (w / 'media.md').write_text(_fm({'created': '2026-03-01'}) + 'x\n')
    (w / 'senza.md').write_text('# nessun frontmatter\n')
    (fx.root / 'wiki' / 'index.md').write_text('[[pagina]] [[vecchia]] [[media]] [[senza]]\n')
    fs = findings('check-wiki-structure.py', fx.root, '--oggi', OGGI)
    assert sorted((f['sev'], f['messaggio'].split(':')[0]) for f in fs) == [
        ('INFO', 'INFO'), ('WARNING', 'MISSING-DATE'), ('WARNING', 'STALE')]


# ------------------------------------------------------------------ runner, exit, idempotenza

def test_runner_exit_strict_out_json(fx):
    # xyz_invalid non e' ne' nel fallback LAYERS_DEFAULT ne' in nessun routing
    fx.tsk(1, 1, 1, layer='xyz_invalid')
    fx.us(1, 1)
    fx.ep(1)
    code, out = esegui('run-deterministic.py', fx.root, '--solo', '1,3,4au', '--oggi', OGGI)
    assert code == 0 and '| 3, 4as, 4b |' in out and '[ERROR][invalid-layer][3]' in out
    code, _ = esegui('run-deterministic.py', fx.root, '--solo', '1,3,4au', '--oggi', OGGI, '--strict')
    assert code == 1
    code, out = esegui('run-deterministic.py', fx.root, '--solo', '3', '--json', '--out', 'wiki/lint/r.json')
    dati = json.loads(out)
    assert code == 0 and dati['totale']['ERROR'] == 1
    assert json.loads((fx.root / 'wiki' / 'lint' / 'r.json').read_text()) == dati


def test_idempotenza(fx):
    pulita(fx, us_status='done', tsk_status=('done', 'todo'))
    fx.sprint([(fx.id('TSK', 1), 'todo')])
    for script, extra in (('check-status-rollup.py', ()), ('check-kanban-integrity.py', ()),
                          ('check-wiki-structure.py', ('--oggi', OGGI)),
                          ('run-deterministic.py', ('--solo', '1,3,4au', '--oggi', OGGI))):
        assert esegui(script, fx.root, *extra) == esegui(script, fx.root, *extra)
        assert esegui(script, fx.root, '--json', *extra) == esegui(script, fx.root, '--json', *extra)


def test_nessuna_regex_di_id_propria():
    # una sola fonte per la forma degli ID: tools/coordinamento/kanban_ids.py
    for f in ('lint_comune.py', 'check-status-rollup.py', 'check-kanban-integrity.py', 'check-wiki-structure.py'):
        testo = (LINT / f).read_text()
        assert 'EP-\\d' not in testo and 'US-\\d' not in testo and 'TSK-\\d' not in testo, f
