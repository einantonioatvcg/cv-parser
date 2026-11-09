"""Ronda 3 de afinado: estudios y rótulos de campo, con datos inventados."""

from cv_parser.entries import parse_education, parse_experience
from cv_parser.levels import detect_level
from cv_parser.models import YearMonth
from tests.helpers import to_lines


def test_anio_al_inicio_es_fecha_en_estudios():
    salida = parse_education(to_lines("2006 ADQUIRIDO: SECUNDARIA\nEscuela Juan Azul"), None)
    assert (salida[0].level, salida[0].level_text, salida[0].end) == ("middle_school", "SECUNDARIA", YearMonth(year=2006))
    assert salida[0].institution == "Escuela Juan Azul"


def test_rotulos_de_campo_en_empleo():
    salida = parse_experience(to_lines("EMPRESA: Tienda Azul\nPUESTO: Cajera\nLUGAR: Zapopan\n2018 - 2019"), None)
    assert (salida[0].position, salida[0].company) == ("Cajera", "Tienda Azul")


def test_rotulos_de_campo_en_estudios():
    salida = parse_education(to_lines("Escuela: Colegio Azul\nCarrera: Licenciatura en Derecho\n2010 - 2014"), None)
    assert (salida[0].institution, salida[0].level_text, salida[0].area_text) == ("Colegio Azul", "Licenciatura en Derecho", "Derecho")


def test_punto_cierra_el_grado():
    assert detect_level("Bachillerato abierto. modalidad en línea (2009-2012)").level_text == "Bachillerato abierto"


def test_nivel_seguido_de_siglas_de_escuela():
    salida = parse_education(to_lines("Secundaria ESTIC No. 45 “GRAL. JUAN AZUL”"), None)
    assert (salida[0].level_text, salida[0].institution) == ("Secundaria", "ESTIC No. 45 “GRAL. JUAN AZUL”")


def test_renglon_que_sigue_con_conector():
    texto = "2010-2014\nLICENCIATURA EN DISEÑO / COMUNICACIÓN\nDE MEDIOS DIGITALES\nUniversidad Azul del Estado"
    e = parse_education(to_lines(texto), None)
    assert len(e) == 1 and e[0].level_text == "LICENCIATURA EN DISEÑO / COMUNICACIÓN DE MEDIOS DIGITALES"
    assert e[0].institution == "Universidad Azul del Estado"


def test_cursos_y_licencias_no_son_estudios():
    texto = ("Licenciatura en Derecho\nUniversidad Azul\n2010 - 2014\n\nESPECIALIDAD DE INFORMATICA INSTITUTO DE CAPACITACION PARA EL TRABAJO\n2015\n\n"
             "LICENCIA TIPO E (AUTOMOVILES)\n\nPracticas Profesionales Esc. Prim. Azul")
    assert [e.level for e in parse_education(to_lines(texto), None)] == ["university"]
