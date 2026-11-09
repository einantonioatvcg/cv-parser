"""Ronda 1 de afinado: patrones vistos en la muestra, reproducidos con datos inventados."""

from datetime import date

import pytest

from cv_parser.dates import find_date_range
from cv_parser.entries import parse_education, parse_experience
from cv_parser.levels import detect_level
from cv_parser.lines import Line
from cv_parser.models import YearMonth
from cv_parser.places import find_place_loose
from cv_parser.sections import split_sections
from tests.helpers import to_lines

HOY = date(2026, 11, 6)


@pytest.mark.parametrize("texto,inicio,fin,actual", [
    ("03-ABRIL-2017– 28-JULIO-2018", (2017, 4), (2018, 7), False),
    ("(09/agosto/2020 a la fecha)", (2020, 8), None, True),
    ("OCT-2014 A MARZO 2016", (2014, 10), (2016, 3), False),
    ("05 MAYO 2011 AL 20 DE ENERO 2013", (2011, 5), (2013, 1), False),
    ("NOVIEMBRE,2021", (2021, 11), None, False),
])
def test_fechas_con_mes_escrito_y_separadores(texto, inicio, fin, actual):
    r = find_date_range(texto, today=HOY)
    assert (r.start, r.end, r.is_current) == (YearMonth(year=inicio[0], month=inicio[1]),
                                               YearMonth(year=fin[0], month=fin[1]) if fin else None, actual)


@pytest.mark.parametrize("vineta", [" ", " ", "➢ ", "❖ ", "-", "o "])
def test_vinetas_raras(vineta):
    salida = parse_experience(to_lines(f"Cajera\nTienda Azul\n2018 - 2019\n{vineta}Cobro en caja\n{vineta}Cortes de caja"), None)
    assert len(salida) == 1 and salida[0].description == "Cobro en caja\nCortes de caja"


def test_encabezado_mas_grande_que_el_cuerpo():
    lineas = [Line("Ana Pérez", size=17, gap_before=True), Line("Experiencia laboral", size=12, gap_before=True),
              Line("Cajera", size=10, bold=True), Line("Tienda Azul", size=9), Line("2018 - 2019", size=9),
              Line("Educación y formación", size=12, gap_before=True), Line("Bachillerato General", size=10),
              Line("Preparatoria 7", size=9), Line("2010 - 2013", size=9)]
    s = split_sections(lineas)
    assert s.order == ["experience", "education"]


def test_encabezado_en_linea_con_texto():
    s = split_sections(to_lines("Ana Pérez\nObjetivo: Crecer profesionalmente en el área\nde ventas.\nEXPERIENCIA\nCajera"))
    assert [l.text for l in s.parts["summary"]] == ["Crecer profesionalmente en el área", "de ventas."]


def test_vineta_no_es_encabezado_compuesto():
    s = split_sections(to_lines("HABILIDADES\n• Excel\n• Competencias y habilidades de liderazgo\n• Word"))
    assert s.order == ["skills"] and len(s.parts["skills"]) == 3


def test_renglon_partido_se_une():
    texto = "NOVIEMBRE,2021\nPASANTE DE LIC. CONTADURÍA, UNIVERSIDAD AZUL DEL\nESTADO DE COLIMA, FACULTAD DE NEGOCIOS"
    salida = parse_education(to_lines(texto), None)
    assert len(salida) == 1
    assert salida[0].level == "university" and salida[0].end == YearMonth(year=2021, month=11)


def test_abreviatura_sin_conector_da_area():
    assert detect_level("Lic. Mercadotecnia y Ventas").area_text == "Mercadotecnia y Ventas"
    assert detect_level("ING. CIVIL").area_text == "CIVIL"


def test_lugar_al_final_de_una_direccion():
    assert find_place_loose("Dirección: Calle Uno 45 Col. Centro Tulancingo Hgo.").country_code == "MX"
    assert find_place_loose("Calle Uno 45, Colonia Centro") is None
