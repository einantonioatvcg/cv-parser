"""Ronda 4 de afinado (más esfuerzo en Python), con datos inventados."""

import pytest

from cv_parser.entries import parse_experience
from cv_parser.lines import Line
from tests.helpers import to_lines


@pytest.mark.parametrize("linea", ["Restaurantes Azules   Mayo 2012 a Agosto 2012", "Tiendas Sol   Mayo 2012 a Agosto 2012"])
def test_una_linea_con_senal_de_empresa_es_empresa(linea):
    e = parse_experience(to_lines(linea), None)[0]
    assert (e.position, e.company) == (None, linea.split("   ")[0])


@pytest.mark.parametrize("duracion", ["(4 meses)", "2 meses y 10 días.", "3 años 2 meses"])
def test_duracion_junto_a_la_fecha_no_es_puesto_ni_empresa(duracion):
    texto = f"ENLACE REGIONAL OFICINA AZUL\nDel 3 de mayo al 30 de septiembre de 2017 {duracion}\nManejo de caja"
    e = parse_experience(to_lines(texto), None)
    assert len(e) == 1 and e[0].position == "ENLACE REGIONAL OFICINA AZUL" and e[0].company is None


@pytest.mark.parametrize("linea,puesto,empresa", [
    ("AUXILIAR DE CAJA BANCO DEL SOL", "AUXILIAR DE CAJA", "BANCO DEL SOL"),
    ("AUXILIAR ADMINISTRATIVO H. AYUNTAMIENTO DE VILLA AZUL", "AUXILIAR ADMINISTRATIVO", "H. AYUNTAMIENTO DE VILLA AZUL"),
])
def test_puesto_y_empresa_sin_separador(linea, puesto, empresa):
    e = parse_experience(to_lines(f"{linea}\n2015 - 2016"), None)[0]
    assert (e.position, e.company) == (puesto, empresa)


def renglones(*filas):
    """(texto, negrita, renglón en blanco antes)"""
    return [Line(text=t, bold=b, gap_before=g) for t, b, g in filas]


def test_titulos_en_negrita_y_funciones_sin_vineta():
    lineas = renglones(
        ("chofer", True, True), ("Constructora Azul - Culiacán, Sin", True, False), ("enero 2009 - diciembre 2009", False, False),
        ("Se cerró la obra", False, False), ("Cierre de la sucursal", False, False),
        ("ayudante de ventas", True, False), ("Helados Sol S.A. de C.V", True, False), ("junio 2007 - marzo 2008", False, False),
        ("Manejo de la camioneta de 3 ton", False, False), ("Acomodo de producto", False, False), ("Inventarios", False, False),
        ("operador de produccion", True, True), ("Refrescos Azules - Culiacán, Sin.", False, False), ("marzo 2005 - diciembre 2006", False, False),
        ("Operador de línea de envasado", False, True), ("CONTRATO POR TEMPORADA", False, True),
    )
    e = parse_experience(lineas, None)
    assert [x.position for x in e] == ["chofer", "ayudante de ventas", "operador de produccion"]
    assert e[1].description == "Manejo de la camioneta de 3 ton\nAcomodo de producto\nInventarios"


@pytest.mark.parametrize("linea", ["CLUB AZUL IXTAPA DE FEBRERO-ABRIL 2016", "Tienda Azul 2018-2020(actual)"])
def test_restos_de_fecha_fuera_de_la_empresa(linea):
    e = parse_experience(to_lines(f"Cajera\n{linea}"), None)[0]
    assert e.company in ("CLUB AZUL IXTAPA", "Tienda Azul")
