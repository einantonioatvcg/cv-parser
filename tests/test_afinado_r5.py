"""Ronda 5 de afinado: fechas partidas en dos renglones y dd/mm, con datos inventados."""

from datetime import date

import pytest

from cv_parser.dates import find_date_range
from cv_parser.entries import parse_experience
from cv_parser.models import YearMonth
from tests.helpers import to_lines


@pytest.mark.parametrize("texto,inicio,fin", [
    ("Cajera\nMAYO 2017-\nABRIL 2019 Tienda Azul", (2017, 5), (2019, 4)),
    ("Cajera\nTienda Azul\nJulio –\nNoviembre 2015", (2015, 7), (2015, 11)),
    ("Cajera\nTienda Azul\nDE MARZO\n2013 – JUNIO 2014", (2013, 3), (2014, 6)),
])
def test_fecha_partida_en_dos_renglones(texto, inicio, fin):
    e = parse_experience(to_lines(texto), None)
    assert len(e) == 1 and (e[0].start, e[0].end) == (YearMonth(year=inicio[0], month=inicio[1]), YearMonth(year=fin[0], month=fin[1]))


def test_fecha_numerica_ambigua_es_dia_mes():
    r = find_date_range("02-03-2017 - 05-11-2018", today=date(2026, 11, 9))
    assert (r.start, r.end) == (YearMonth(year=2017, month=3), YearMonth(year=2018, month=11))


from cv_parser.levels import detect_level


@pytest.mark.parametrize("texto,nivel,area", [
    ("Técnico superior terminado en Diseño gráfico", "university", "Diseño gráfico"),
    ("Licenciatura trunca o en curso en Comercio Exterior", "university", "Comercio Exterior"),
    ("BACHILLER TÉCNICO EN CONTABILIDAD", "high_school", "CONTABILIDAD"),
])
def test_area_tras_palabras_de_estado(texto, nivel, area):
    m = detect_level(texto)
    assert (m.level, m.area_text) == (nivel, area)
