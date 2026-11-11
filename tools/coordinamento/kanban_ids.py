"""Forma degli ID del kanban e appartenenza TSK → US → EP, in un punto solo.

Le factory della flotta hanno due forme di kanban:
- ID con prefisso di namespace e cartelle senza slug (``XX-EP-020/XX-US-172/XX-TSK-541.md``);
- ID senza prefisso e cartelle con slug (``EP-064-kanban-multi-user-coordination/US-251-trial/TSK-572.md``).

Il prefisso e' opzionale, come in ``tools/vcs/ai_policy.py``. L'appartenenza si legge dal
frontmatter (``story:``/``us:``, ``epic:``/``ep:``) e solo in mancanza dalla posizione nel path;
la cartella si riconosce dall'ID con cui comincia, mai dal suo nome esatto.

verifica_l0.py NON importa questo modulo: ha la sua implementazione, per costruzione.
"""
import re

ID_RE = re.compile(r'^(?:([A-Z]{2,4})-)?(EP|US|TSK)-(\d+)$')
ID_IN_TESTO = re.compile(r'\b(?:[A-Z]{2,4}-)?(?:EP|US|TSK)-\d+\b')
TSK_RE = re.compile(r'^(?:[A-Z]{2,4}-)?TSK-\d+$')
EP_RE = re.compile(r'^(?:([A-Z]{2,4})-)?EP-\d+$')
# cartella che comincia con un ID, seguito da fine nome o da «-slug»
CARTELLA_RE = re.compile(r'^((?:[A-Z]{2,4}-)?(EP|US|TSK)-\d+)(?=-|$)')

CAMPI_US = ('story', 'us', 'story_id', 'user_story', 'parent_us', 'parent')
CAMPI_EP = ('epic', 'ep', 'epica', 'epic_id')


def tipo_di(nome):
    """'EP' | 'US' | 'TSK' | None."""
    m = ID_RE.match(str(nome or ''))
    return m.group(2) if m else None


def prefisso_di(nome):
    """Prefisso di namespace dell'ID ('XX' in XX-TSK-541), None se l'ID non ne ha o non e' un ID."""
    m = ID_RE.match(str(nome or ''))
    return m.group(1) if m else None


def id_cartella(nome_cartella):
    """(ID, tipo) se la cartella comincia con un ID del kanban, altrimenti (None, None)."""
    m = CARTELLA_RE.match(str(nome_cartella or ''))
    return (m.group(1), m.group(2)) if m else (None, None)


def cartella_e_di(nome_cartella, ident):
    """True se la cartella e' quella dell'entita' `ident` (nome uguale all'ID o «ID-slug»)."""
    return id_cartella(nome_cartella)[0] == ident


def da_frontmatter(dati, campi, tipo):
    """Primo valore fra `campi` del frontmatter che e' un ID del `tipo` richiesto."""
    for c in campi:
        v = (dati or {}).get(c)
        if isinstance(v, list):
            v = v[0] if len(v) == 1 else None
        v = str(v).strip().strip('"\'') if v not in (None, '') else ''
        if v and tipo_di(v) == tipo:
            return v
    return None


def da_path(dentro, tipo):
    """ID del `tipo` richiesto fra le cartelle del path relativo al kanban (ultima componente esclusa)."""
    for comp in dentro[:-1]:
        i, t = id_cartella(comp)
        if t == tipo:
            return i
    return None


def epiche_nel_path(paths, kanban, epiche):
    """{path: epica} dei file .md sotto le cartelle delle epiche richieste (riconosciute dall'ID iniziale)."""
    base = len(kanban.rstrip('/').split('/'))
    voluti = set(epiche)
    out = {}
    for p in paths:
        parti = p.split('/')
        if len(parti) <= base + 1 or not p.endswith('.md'):
            continue
        ep, _ = id_cartella(parti[base])
        if ep in voluti:
            out[p] = ep
    return out


def cartelle_epiche(nomi_cartelle, epiche):
    """Nomi delle cartelle di primo livello del kanban che appartengono alle epiche richieste."""
    voluti = set(epiche)
    return sorted(n for n in nomi_cartelle if id_cartella(n)[0] in voluti)


_INTERVALLO_RE = re.compile(r'^((?:[A-Z]{2,4}-)?TSK-)(\d+)\s*\.\.\s*(?:(?:[A-Z]{2,4}-)?TSK-)?(\d+)$')
_INTERVALLO_MAX = 500


def tsk_dichiarati(dati):
    """TSK che una US dichiara come propri in `tsk_ids` (lista) o `tsk_range` (stringa).

    `tsk_range` accetta ID singoli, elenchi separati da virgola e intervalli completi o abbreviati:
    «TSK-708..TSK-713», «XX-TSK-561..563», «XX-TSK-267, XX-TSK-541..547». Serve al controllo di
    roll-up per le US che elencano TSK di altre cartelle. Restituisce un insieme di ID, oppure
    None se il campo manca o non si lascia leggere (testo libero, intervallo rovesciato o enorme):
    in quel caso valgono solo i TSK della US per frontmatter/path.
    """
    sorgente = (dati or {}).get('tsk_ids')
    if sorgente in (None, '', []):
        sorgente = (dati or {}).get('tsk_range')
    if sorgente in (None, '', []):
        return None
    pezzi = sorgente if isinstance(sorgente, list) else str(sorgente).split(',')
    ids = set()
    for pezzo in pezzi:
        t = str(pezzo).strip().strip('"\'')
        if not t:
            continue
        if TSK_RE.match(t):
            ids.add(t)
            continue
        m = _INTERVALLO_RE.match(t)
        if not m:
            return None
        base, da, a = m.group(1), m.group(2), m.group(3)
        n_da, n_a = int(da), int(a)
        if n_a < n_da or n_a - n_da > _INTERVALLO_MAX:
            return None
        ids.update('%s%s' % (base, str(n).zfill(len(da))) for n in range(n_da, n_a + 1))
    return ids or None



def nel_selettore(epica, us, selettore):
    """Vero se un elemento (epica, US) sta nel selettore di un perimetro: la sua epica e' fra le `epiche` e, quando il
    selettore elenca `us`, la sua US e' fra quelle. Vale sia per `perimetro[].selettore` della config sia per le voci
    `perimetro` della misura, che portano le stesse chiavi. Senza `us` conta l'epica intera, come prima del campo."""
    sel = selettore or {}
    if epica not in sel.get('epiche', []):
        return False
    lista = sel.get('us')
    return lista is None or us in lista


def nel_perimetro(epica, us, obiettivo):
    """Vero se (epica, US) sta in almeno uno dei perimetri dell'obiettivo della config."""
    return any(nel_selettore(epica, us, p.get('selettore')) for p in obiettivo.get('perimetro', []))
