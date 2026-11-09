import pytest

from cv_parser.entries import parse_education, parse_experience
from cv_parser.models import YearMonth
from cv_parser.places import Place
from cv_parser.sections import split_sections
from tests.helpers import to_lines

ESPERADO = [("Asistente Administrativa", "Grupo Comercial del Bajío S.A. de C.V."), ("Recepcionista", "Clínica San Rafael")]


@pytest.mark.parametrize("texto", [
    # puesto, empresa, fecha, viñetas
    "Asistente Administrativa\nGrupo Comercial del Bajío S.A. de C.V., Guadalajara, Jalisco\nMarzo 2021 - Actualidad\n- Gestión de agenda\n\nRecepcionista\nClínica San Rafael, Zapopan, Jalisco\nEnero 2018 - Febrero 2021\n- Atención a pacientes",
    # empresa antes que puesto
    "Grupo Comercial del Bajío S.A. de C.V.\nAsistente Administrativa\nMarzo 2021 - Actualidad\n- Gestión de agenda\n\nClínica San Rafael\nRecepcionista\nEnero 2018 - Febrero 2021\n- Atención a pacientes",
    # todo en una línea
    "Asistente Administrativa | Grupo Comercial del Bajío S.A. de C.V. | Marzo 2021 - Actualidad\n- Gestión de agenda\nRecepcionista | Clínica San Rafael | Enero 2018 - Febrero 2021\n- Atención a pacientes",
    # fecha primero
    "Marzo 2021 - Actualidad\nAsistente Administrativa\nGrupo Comercial del Bajío S.A. de C.V.\n- Gestión de agenda\nEnero 2018 - Febrero 2021\nRecepcionista\nClínica San Rafael\n- Atención a pacientes",
    # sin renglones en blanco, puesto antes que fecha
    "Asistente Administrativa\nGrupo Comercial del Bajío S.A. de C.V.\nMarzo 2021 - Actualidad\n• Gestión de agenda\nRecepcionista\nClínica San Rafael\nEnero 2018 - Febrero 2021\n• Atención a pacientes",
    # fecha en la misma línea que el puesto, separada por espacio
    "Asistente Administrativa Marzo 2021 - Actualidad\nGrupo Comercial del Bajío S.A. de C.V.\n- Gestión de agenda\nRecepcionista Enero 2018 - Febrero 2021\nClínica San Rafael\n- Atención a pacientes",
])
def test_empleos_en_cuatro_formatos(texto):
    salida = parse_experience(to_lines(texto), None)
    assert [(e.position, e.company) for e in salida] == ESPERADO
    assert salida[0].is_current is True and salida[0].end is None
    assert salida[1].start == YearMonth(year=2018, month=1)
    assert salida[0].description == "Gestión de agenda"


def test_lugar_de_la_entrada():
    salida = parse_experience(to_lines("Recepcionista\nClínica San Rafael, Zapopan, Jalisco\nEnero 2018 - Febrero 2021"), None)
    assert (salida[0].company, salida[0].city, salida[0].country_code) == ("Clínica San Rafael", "Zapopan", "MX")


def test_descripcion_varias_lineas():
    texto = "Cajera\nTienda Azul\n2018 - 2019\n• Manejo de caja y cortes\n• Atención a clientes en piso de venta,\nresolviendo dudas"
    salida = parse_experience(to_lines(texto), None)
    assert salida[0].description == "Manejo de caja y cortes\nAtención a clientes en piso de venta, resolviendo dudas"


def test_empleos_sin_fecha_se_conservan():
    salida = parse_experience(to_lines("Recepcionista\nClínica San Rafael\n\nMesero\nRestaurante Azul"), None)
    assert [e.position for e in salida] == ["Recepcionista", "Mesero"]
    assert all(e.start is None and e.confidence < 0.7 for e in salida)


def test_empleo_sin_fecha_al_final_no_se_fusiona():
    texto = "Cajera\nTienda Azul\n2018 - 2019\n- Manejo de caja\n\nMesero\nRestaurante Azul"
    salida = parse_experience(to_lines(texto), None)
    assert [(e.position, e.company) for e in salida] == [("Cajera", "Tienda Azul"), ("Mesero", "Restaurante Azul")]
    assert salida[1].start is None and salida[1].confidence < 0.7


def test_pais_propio_gana_al_del_encabezado():
    fallback = Place(city="Guadalajara", country_code="MX", country_name="México")
    salida = parse_experience(to_lines("Cajera\nTienda Azul, Madrid, España\n2018 - 2019\n\nMesera\nCafé Sol\n2016 - 2017"), fallback)
    assert salida[0].country_code == "ES" and salida[1].country_code == "MX"
    assert salida[1].city is None


def test_sin_pais_y_sin_fallback_queda_vacio():
    salida = parse_experience(to_lines("Mesera\nCafé Sol\n2016 - 2017"), None)
    assert salida[0].country_code is None and salida[0].city is None


def test_datos_personales_no_contaminan():
    s = split_sections(to_lines("DATOS PERSONALES\nFecha de nacimiento: 12/05/1990\nCURP: XXXX900512\nEXPERIENCIA\nCajera\nTienda Azul\n2018 - 2019\nREFERENCIAS\nJuan Pérez 3312345678"))
    salida = parse_experience(s.parts["experience"], None)
    assert len(salida) == 1 and salida[0].start.year == 2018


def test_confianza():
    salida = parse_experience(to_lines("Cajera\nTienda Azul\n2018 - 2019"), None)
    assert salida[0].confidence == pytest.approx(0.9)  # rango, empresa con señal, puesto con señal, sin sobrantes


@pytest.mark.parametrize("texto", [
    "Licenciatura en Administración\nUniversidad de Guadalajara, Guadalajara, Jalisco\nAgosto 2013 - Junio 2017",
    "Universidad de Guadalajara, Guadalajara, Jalisco\nLicenciatura en Administración\nAgosto 2013 - Junio 2017",
    "Agosto 2013 - Junio 2017\nLicenciatura en Administración\nUniversidad de Guadalajara\nGuadalajara, Jalisco",
])
def test_estudios_en_dos_ordenes(texto):
    e = parse_education(to_lines(texto), None)[0]
    assert (e.level, e.area_text, e.institution, e.city, e.country_code) == ("university", "Administración", "Universidad de Guadalajara", "Guadalajara", "MX")
    assert e.start == YearMonth(year=2013, month=8) and e.end == YearMonth(year=2017, month=6)


def test_nivel_e_institucion_en_una_linea():
    e = parse_education(to_lines("Preparatoria 7, Guadalajara, Jalisco\n2010 - 2013"), None)[0]
    assert (e.level, e.institution, e.city) == ("high_school", "Preparatoria 7", "Guadalajara")


def test_fecha_unica_en_estudios_es_termino():
    e = parse_education(to_lines("Bachelor of Arts, University of Texas, 2015"), None)[0]
    assert e.start is None and e.end == YearMonth(year=2015, month=None)


def test_estudio_en_curso():
    e = parse_education(to_lines("Maestría en Finanzas\nUniversidad Azul\n2024 - En curso"), None)[0]
    assert e.is_current is True and e.end is None


def test_dos_estudios_sin_renglon_en_blanco():
    texto = ("Licenciatura en Administración de Empresas\nUniversidad de Guadalajara\nGuadalajara, Jalisco\nAgosto 2013 - Junio 2017\n"
             "Bachillerato General\nPreparatoria 7\nGuadalajara, Jalisco\n2010 - 2013")
    salida = parse_education(to_lines(texto), None)
    assert [(e.level, e.level_text, e.institution) for e in salida] == [
        ("university", "Licenciatura en Administración de Empresas", "Universidad de Guadalajara"),
        ("high_school", "Bachillerato General", "Preparatoria 7"),
    ]
