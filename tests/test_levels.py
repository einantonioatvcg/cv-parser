import pytest

from cv_parser.levels import detect_level

NIVELES = [
    ("Licenciatura en Administración de Empresas", "university", False, "Administración de Empresas"),
    ("Ingeniería en Sistemas", "university", False, "Sistemas"),
    ("Bachelor of Business Administration", "university", False, "Business Administration"),
    ("Maestría en Finanzas", "master", False, "Finanzas"),
    ("MBA", "master", False, None),
    ("Doctorado en Derecho", "doctorate", False, "Derecho"),
    ("PhD in Physics", "doctorate", False, "Physics"),
    ("Bachillerato General", "high_school", False, None),
    ("High School Diploma", "high_school", False, None),
    ("Secundaria Técnica 12", "middle_school", True, None),
    ("Primaria", "elementary", False, None),
    ("Carrera Técnica en Enfermería", "high_school", True, "Enfermería"),
    ("TSU en Logística", "university", True, "Logística"),
    # variantes
    ("LICENCIATURA EN ADMINISTRACIÓN", "university", False, "ADMINISTRACIÓN"),
    ("Licenciatura en Contaduría Pública, Universidad Azul", "university", False, "Contaduría Pública"),
    ("Ingeniería en Sistemas por el Instituto Tecnológico de León", "university", False, "Sistemas"),
    ("Técnico Superior Universitario en Mantenimiento", "university", True, "Mantenimiento"),
    ("Preparatoria 7", "high_school", False, None),
]
NO_NIVEL = ["Universidad de Guadalajara", "Curso de Excel", "Recepcionista", "Universidad Tecnológica de Jalisco"]


@pytest.mark.parametrize("texto,nivel,tecnico,area", NIVELES)
def test_niveles(texto, nivel, tecnico, area):
    m = detect_level(texto)
    assert m is not None
    assert (m.level, m.is_technical, m.area_text) == (nivel, tecnico, area)


def test_level_text_es_el_segmento():
    assert detect_level("Licenciatura en Administración de Empresas").level_text == "Licenciatura en Administración de Empresas"
    assert detect_level("Preparatoria 7, Guadalajara, Jalisco").level_text == "Preparatoria 7"


@pytest.mark.parametrize("texto", NO_NIVEL)
def test_sin_nivel(texto):
    assert detect_level(texto) is None
