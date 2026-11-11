"""Milestone dei sotto-obiettivi lette dalla config (`perimetro[].sotto_obiettivi.milestone`)."""
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
from vista_pm import milestone_sotto_obiettivo  # noqa: E402


def _cfg(milestone):
    so = {'etichetta': 'x', 'sezioni': []}
    if milestone is not None:
        so['milestone'] = milestone
    return {'obiettivi': [{'id': 'ob', 'perimetro': [{'progetto_id': 'p1', 'sotto_obiettivi': so}]}]}


def test_ordinate_per_data_con_descrizione():
    cfg = _cfg([{'data': '2026-11-13', 'etichetta': 'M3', 'descrizione': 'IB pronto'},
                {'data': '2026-10-30', 'etichetta': 'M1'}])
    assert milestone_sotto_obiettivo(cfg, 'ob', 'p1') == [('2026-10-30', 'M1', ''), ('2026-11-13', 'M3', 'IB pronto')]


def test_date_non_valide_ignorate():
    cfg = _cfg([{'data': '30/10', 'etichetta': 'M1'}, {'etichetta': 'M2'}, {'data': '2026-12-10', 'etichetta': 'M9'}])
    assert milestone_sotto_obiettivo(cfg, 'ob', 'p1') == [('2026-12-10', 'M9', '')]


def test_campo_assente_o_progetto_diverso():
    assert milestone_sotto_obiettivo(_cfg(None), 'ob', 'p1') == []
    assert milestone_sotto_obiettivo(_cfg([{'data': '2026-10-30', 'etichetta': 'M1'}]), 'ob', 'altro') == []
    assert milestone_sotto_obiettivo(_cfg([{'data': '2026-10-30', 'etichetta': 'M1'}]), 'altro', 'p1') == []
