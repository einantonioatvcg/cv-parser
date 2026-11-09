from cv_parser.header import parse_header
from tests.helpers import to_lines


def test_encabezado_del_cv():
    contacto, titulo = parse_header(to_lines("María Fernanda López Hernández\nAsistente Administrativa\nGuadalajara, Jalisco, México\nTel: 33 1234 5678 | maria.lopez@ejemplo.invalid"))
    assert contacto.name == "María Fernanda López Hernández"
    assert contacto.phone == "3312345678" and contacto.email == "maria.lopez@ejemplo.invalid"
    assert titulo == "Asistente Administrativa"


def test_encabezado_sin_titulo():
    contacto, titulo = parse_header(to_lines("MARÍA LÓPEZ\nCalle 5 #10, Guadalajara\nmaria@ejemplo.invalid"))
    assert contacto.name == "MARÍA LÓPEZ" and titulo is None


def test_encabezado_con_rotulo_curriculum():
    contacto, titulo = parse_header(to_lines("CURRICULUM VITAE\nRosa Pérez Díaz\nCajera\nCel. (33) 1234-5678"))
    assert contacto.name == "Rosa Pérez Díaz" and titulo == "Cajera" and contacto.phone == "3312345678"


def test_encabezado_vacio():
    contacto, titulo = parse_header([])
    assert (contacto.name, contacto.email, contacto.phone, titulo) == (None, None, None, None)


def test_fechas_no_son_telefono():
    contacto, _ = parse_header(to_lines("Rosa Pérez\n2018 - 2020 2021"))
    assert contacto.phone is None


def test_lugar_no_es_titulo():
    contacto, titulo = parse_header(to_lines("Rosa Pérez Díaz\nGuadalajara, Jalisco, México\nrosa@ejemplo.invalid"))
    assert contacto.name == "Rosa Pérez Díaz" and titulo is None
