"""verify_gap_closures.py — un gap chiuso vale solo con pagina wiki che cita la fonte (EP-077)."""
import importlib.util
import os
import pathlib
import shutil
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(QUI, '..', 'wiki', 'verify_gap_closures.py'))


def carica(radice):
    spec = importlib.util.spec_from_file_location('verify_gap_closures', SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = pathlib.Path(radice)
    m.WIKI = m.ROOT / 'wiki'
    m.GAPS = m.WIKI / 'gaps.md'
    return m


GAPS = """# Gap

- [x] **G-T-001** — gap chiuso con pagina che cita la fonte.
  **Risolto:** 2026-10-15 — [[con-fonte]]
- [x] **G-T-002** — gap chiuso con pagina inesistente.
  **Risolto:** 2026-10-15 — [[non-esiste]]
- [x] **G-T-003** — gap chiuso con pagina senza fonte.
  **Risolto:** 2026-10-15 — [[senza-fonte]]
- [x] **G-T-004** — gap chiuso a parole.
  **Risolto:** 2026-10-15 — verificato sul codice
- [ ] **G-T-005** — gap aperto sul tema NCC.
"""


def radice():
    r = tempfile.mkdtemp(prefix='gap-closures-')
    os.makedirs(os.path.join(r, 'wiki', 'concepts'))
    os.makedirs(os.path.join(r, 'raw'))
    open(os.path.join(r, 'raw', 'fonte.md'), 'w').write('fonte\n')
    open(os.path.join(r, 'wiki', 'gaps.md'), 'w').write(GAPS)
    open(os.path.join(r, 'wiki', 'concepts', 'con-fonte.md'), 'w').write('testo [^src: raw/fonte.md §1]\n')
    open(os.path.join(r, 'wiki', 'concepts', 'senza-fonte.md'), 'w').write('testo senza citazione\n')
    return r


def esiti(m):
    idx = m.page_index()
    return {g.key: m.verify(g, idx)[0] for g in m.parse()}


def test_tre_casi_e_chiusura_a_parole():
    r = radice()
    try:
        e = esiti(carica(r))
        assert e['G-T-001'] == 'verificata'
        assert e['G-T-002'] == 'pagina indicata assente'
        assert e['G-T-003'] == 'pagina senza fonte in raw/'
        assert e['G-T-004'] == 'chiusura senza pagina della wiki'
        assert e['G-T-005'] == 'aperto'
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_fonte_citata_ma_assente_da_raw():
    r = radice()
    try:
        os.remove(os.path.join(r, 'raw', 'fonte.md'))
        assert esiti(carica(r))['G-T-001'] == 'pagina senza fonte in raw/'
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_filtro_per_tema_e_check(capsys):
    r = radice()
    try:
        m = carica(r)
        assert m.main(['--tema', 'NCC', '--check']) == 0
        assert 'gap del tema' in capsys.readouterr().out
        assert m.main(['--check']) == 1
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_formato_a_sezioni_di_gaps_open_view():
    r = radice()
    try:
        open(os.path.join(r, 'wiki', 'gaps.md'), 'w').write(
            "# Gap\n\n## 2026-10-01 10:00 — gap-uno\n\n**Risolto:** 2026-10-02 — [[con-fonte]]\n\n"
            "## 2026-10-03 10:00 — gap-due\n\ndescrizione ancora aperta\n")
        e = esiti(carica(r))
        assert e == {'gap-uno': 'verificata', 'gap-due': 'aperto'}
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_forme_di_chiusura_della_derivata():
    """`**Risolto (data, contesto):**`, `**Superato:**` e `~~CHIUSO~~` nel titolo sono chiusure (EP-084)."""
    r = radice()
    try:
        open(os.path.join(r, 'wiki', 'gaps.md'), 'w').write(
            "# Gap\n\n"
            "- [x] **G-F-001** — chiuso con la forma lunga.\n"
            "  **Risolto (2026-10-16T09:31Z, verifica sul codice):** vedi [[con-fonte]]\n"
            "- [ ] **G-F-002** — superato senza spunta: era contato aperto.\n"
            "  **Superato:** 2026-10-09 — file rimosso dal commit a187c70e3\n"
            "- [x] **G-F-003** ~~CHIUSO 2026-09-10~~ — solo nel titolo.\n")
        e = esiti(carica(r))
        assert e['G-F-001'] == 'verificata'
        assert e['G-F-002'] == 'chiusura senza pagina della wiki'
        assert e['G-F-003'] == 'chiusura senza pagina della wiki'
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_rimando_a_gap_verificato_un_solo_passo():
    """Un duplicato «gia' chiuso altrove» eredita la verifica del gap citato, per riga o per ID;
    un rimando a un rimando non conta."""
    r = radice()
    try:
        open(os.path.join(r, 'wiki', 'gaps.md'), 'w').write(
            "# Gap\n\n"
            "- [x] **G-R-001** — originale.\n"                                        # riga 3
            "  **Risolto:** 2026-10-01 — [[con-fonte]]\n"                             # riga 4
            "- [x] **G-R-002** — duplicato per riga.\n"
            "  **Risolto:** 2026-10-13 — gia' chiuso altrove: wiki/gaps.md:4\n"
            "- [x] **G-R-003** — duplicato per ID.\n"
            "  **Risolto:** 2026-10-13 — duplicate-of G-R-001\n"
            "- [x] **G-R-004** — rimando al duplicato, non all'originale.\n"
            "  **Risolto:** 2026-10-13 — vedi G-R-002\n"
            "- [x] **G-R-005** — rimando a un gap chiuso a parole.\n"
            "  **Risolto:** 2026-10-13 — come G-R-006\n"
            "- [x] **G-R-006** — chiuso a parole.\n"
            "  **Risolto:** 2026-10-13 — verificato sul codice\n")
        m = carica(r)
        v = m.verify_all(m.parse(), m.page_index())
        assert v['G-R-001'][0] == 'verificata' and v['G-R-001'][2] is None
        assert v['G-R-002'][0] == 'verificata' and v['G-R-002'][2] == 'G-R-001'
        assert v['G-R-003'][0] == 'verificata' and v['G-R-003'][2] == 'G-R-001'
        assert v['G-R-004'][0] == 'chiusura senza pagina della wiki'
        assert v['G-R-005'][0] == 'chiusura senza pagina della wiki'
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_confirmed_open_riapre_e_una_chiusura_successiva_richiude():
    r = radice()
    try:
        open(os.path.join(r, 'wiki', 'gaps.md'), 'a').write(
            "- [CONFIRMED OPEN] **G-T-001** — riaperto: il difetto c'e' ancora.\n"
            "- [CONFIRMED OPEN] **G-T-004** — riaperto.\n"
            "- [CLOSED] G-T-004 — verificata su `wiki/concepts/con-fonte.md`.\n")
        e = esiti(carica(r))
        assert e['G-T-001'] == 'aperto'
        assert e['G-T-004'] == 'verificata'
    finally:
        shutil.rmtree(r, ignore_errors=True)


def test_risolto_fra_backtick_e_closed_senza_id_non_chiudono_il_gap_precedente():
    r = radice()
    try:
        open(os.path.join(r, 'wiki', 'gaps.md'), 'a').write(
            "- [ ] **G-T-006** — gap aperto.\n"
            "  Da chiudere con una riga `**Risolto:**` quando arriva la fonte.\n"
            "- [ ] **G-T-007** — altro gap aperto.\n"
            "- [CLOSED] **Bootstrap gap senza ID** — risolto.\n")
        e = esiti(carica(r))
        assert e['G-T-006'] == 'aperto'
        assert e['G-T-007'] == 'aperto'
        assert [k for k in e if k.startswith('riga-')]
    finally:
        shutil.rmtree(r, ignore_errors=True)
