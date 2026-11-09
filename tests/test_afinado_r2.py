"""Ronda 2 de afinado: encabezado del CV, con datos inventados."""

import pytest

from cv_parser.header import parse_header
from tests.helpers import to_lines


@pytest.mark.parametrize("texto,nombre,titulo", [
    ("Rosa Pérez Díaz\nMujer • 27 años\nrosa@ejemplo.invalid", "Rosa Pérez Díaz", None),
    ("Rosa Pérez Díaz\nCASADA\nrosa@ejemplo.invalid", "Rosa Pérez Díaz", None),
    ("Rosa Pérez Díaz\nCol. Centro Jiutepec Morelos\nLicenciada en Derecho", "Rosa Pérez Díaz", None),
    ("Rosa Pérez Díaz\nTLAJOMULCO DE ZUÑIGA", "Rosa Pérez Díaz", None),
    ("Lic. en Administración\nRosa Pérez Díaz\nrosa@ejemplo.invalid", "Rosa Pérez Díaz", "Lic. en Administración"),
    ("INGENIERÍA EN SISTEMAS DE LA\nCONSTRUCCIÓN\nROSA PÉREZ DÍAZ", "ROSA PÉREZ DÍAZ", "INGENIERÍA EN SISTEMAS DE LA CONSTRUCCIÓN"),
    ("Rosa Pérez Díaz\nChofer\nCel. 33 1234 5678", "Rosa Pérez Díaz", "Chofer"),
    ("Rosa Pérez Díaz\nAsistente Administrativa", "Rosa Pérez Díaz", "Asistente Administrativa"),
])
def test_titulo_conservador(texto, nombre, titulo):
    contacto, encontrado = parse_header(to_lines(texto))
    assert (contacto.name, encontrado) == (nombre, titulo)


@pytest.mark.parametrize("texto", [
    "DATOS DE IDENTIFICACIÓN\nantecedentes",
    "crecer de manera personal y laboral.",
    "Disponible para viajar: sí",
    "PUESTO: AYUDANTE DE BODEGA GENERAL",
])
def test_no_es_nombre(texto):
    contacto, _ = parse_header(to_lines(texto))
    assert contacto.name is None


def test_nombre_con_abreviatura():
    contacto, _ = parse_header(to_lines("Ma. Fernanda Pérez Díaz\nrosa@ejemplo.invalid"))
    assert contacto.name == "Ma. Fernanda Pérez Díaz"


from datetime import date

from cv_parser.dates import find_date_range
from cv_parser.entries import parse_experience
from cv_parser.models import YearMonth
from cv_parser.sections import split_sections


@pytest.mark.parametrize("texto,clave", [
    ("EXPERIENCIA PROFECIONAL", "experience"), ("EXPREIENCIA", "experience"), ("EXPERIENCIAS", "experience"),
    ("ANTECEDENTES ACADEMICOS", "education"), ("DATOS DE IDENTIFICACIÓN", "personal"),
    ("REFERENCIAS VECINALES", "references"), ("Experiencia laboral informal", "experience"),
])
def test_variantes_de_encabezado(texto, clave):
    assert clave in split_sections(to_lines(f"Nombre\n{texto}\nContenido")).parts


def test_rotulo_en_linea_en_mayusculas():
    s = split_sections(to_lines("Ana Pérez\nEDUCACION: Secundaria Técnica 12\nEXPERIENCIA: Tienda Azul\nCajera"))
    assert s.parts["education"][0].text == "Secundaria Técnica 12" and s.parts["experience"][0].text == "Tienda Azul"


@pytest.mark.parametrize("texto,inicio,fin", [
    ("Del 3 de mayo al 30 de septiembre de 2017", (2017, 5), (2017, 9)),
    ("DE MARZO-JUNIO 2012", (2012, 3), (2012, 6)),
    ("noviembre a febrero de 2020", (2019, 11), (2020, 2)),
])
def test_mes_sin_anio_toma_el_del_final(texto, inicio, fin):
    r = find_date_range(texto, today=date(2026, 11, 6))
    assert (r.start, r.end) == (YearMonth(year=inicio[0], month=inicio[1]), YearMonth(year=fin[0], month=fin[1]))


def test_rotulo_de_tareas():
    salida = parse_experience(to_lines("Cajera\nTienda Azul\n2018 - 2019\nTareas o actividades:\n-Cobro en caja"), None)
    assert len(salida) == 1 and salida[0].description == "Cobro en caja"


def test_puesto_en_empresa():
    salida = parse_experience(to_lines("• GERENTE DE ZONA en BANCO AZUL DEL SUR SA (02/abril/2009 al 30/junio/2015)"), None)
    assert (salida[0].position, salida[0].company) == ("GERENTE DE ZONA", "BANCO AZUL DEL SUR SA")
    assert salida[0].start == YearMonth(year=2009, month=4)


def test_telefono_fuera_de_la_empresa():
    salida = parse_experience(to_lines("Construcciones Azul Tel. 555 – 010 - 4567\nCoordinador de Proyectos\nEnero 2015 - Mayo 2016"), None)
    assert salida[0].company == "Construcciones Azul" and salida[0].position == "Coordinador de Proyectos"


def test_datos_personales_y_pie_de_pagina_no_son_empleos():
    texto = "Cajera\nTienda Azul\n2018 - 2019\n\nEdad: 40 años. Fecha de nac.: 3 de Enero 1985\n\nPágina 2"
    assert len(parse_experience(to_lines(texto), None)) == 1


def test_vineta_antes_de_la_empresa_con_fecha():
    salida = parse_experience(to_lines(" Laboratorios Azul S.A. de C.V. (OCT 2012- ENE 2014)\nAnalista de calidad\n-Pruebas"), None)
    assert salida[0].company == "Laboratorios Azul S.A. de C.V." and salida[0].position == "Analista de calidad"
