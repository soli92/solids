"""Stringhe di calendario del report, in un punto solo (lingua della factory: italiano).

Per un'altra lingua si sostituiscono qui GIORNI, MESI e GIORNO_DATA: nessun altro modulo
le ridefinisce. verifica_l0.py non ne dipende (confronta date ISO e gg/mm numerici).
"""
import re

GIORNI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']
MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
# «mer 06/10», «lunedi 5/10/2026»: giorno abbreviato (o per esteso) seguito da gg/mm[/aaaa]
GIORNO_DATA = re.compile(r'\b(%s)[a-zì]*\.? +(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b' % '|'.join(GIORNI))
