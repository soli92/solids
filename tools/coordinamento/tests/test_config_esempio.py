"""La config di esempio misura il kanban di questa factory ed e' coerente con lo schema."""
import json
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
STRUMENTI = os.path.dirname(QUI)
FACTORY = os.path.normpath(os.path.join(STRUMENTI, '..', '..'))
sys.path.insert(0, STRUMENTI)
from kanban_ids import cartelle_epiche  # noqa: E402

CONFIG = os.path.join(FACTORY, 'analytics', 'coordinamento', 'config-esempio.json')
SCHEMA = os.path.join(FACTORY, 'analytics', 'coordinamento', 'config-schema.json')


def _cfg():
    return json.load(open(CONFIG, encoding='utf-8'))


def test_schema_e_campi_obbligatori():
    cfg, schema = _cfg(), json.load(open(SCHEMA, encoding='utf-8'))
    assert all(k in cfg for k in schema['required'])
    assert all(k in cfg['stati'] for k in schema['properties']['stati']['required'])
    try:
        import jsonschema
    except ImportError:  # validazione completa solo se la libreria c'e'; i campi obbligatori sono controllati sopra
        return
    jsonschema.validate(cfg, schema)


def test_tabella_stati_disgiunta_e_copre_gli_stati_della_factory():
    visti = {}
    for cat, valori in _cfg()['stati'].items():
        for v in valori:
            visti.setdefault(v.lower(), set()).add(cat)
    assert all(len(c) == 1 for c in visti.values())
    for v in ('done', 'todo', 'in-progress', 'in_progress', 'blocked', 'cancelled', 'superseded'):
        assert v in visti, v


def test_epiche_del_perimetro_esistono_nel_kanban():
    cfg = _cfg()
    kanban = os.path.join(FACTORY, cfg['kanban_root'])
    cartelle = [n for n in os.listdir(kanban) if os.path.isdir(os.path.join(kanban, n))]
    for o in cfg['obiettivi']:
        for p in o['perimetro']:
            for ep in p['selettore']['epiche']:
                assert cartelle_epiche(cartelle, [ep]), 'epica %s senza cartella in %s' % (ep, cfg['kanban_root'])
