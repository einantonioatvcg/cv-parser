"""La confianza de cada entrada sale de señales, no solo de campos presentes."""

from cv_parser.entries import parse_education, parse_experience
from eval.score import Counts, score_entries_by_actual
from tests.helpers import to_lines


def test_confianza_baja_por_senales_de_duda():
    dudosa = parse_experience(to_lines("Ventas\nZona Norte\nCentro\n2018 - 2019"), None)[0]
    clara = parse_experience(to_lines("Cajera\nTienda Azul S.A. de C.V.\n2018 - 2019"), None)[0]
    assert dudosa.confidence < 0.75 <= clara.confidence


def test_confianza_de_estudio_con_senales():
    claro = parse_education(to_lines("Licenciatura en Derecho\nUniversidad Azul\n2010 - 2014"), None)[0]
    dudoso = parse_education(to_lines("Estudios varios\nCentro Azul"), None)
    assert claro.confidence >= 0.75 and all(e.confidence < 0.75 for e in dudoso)


def test_puntaje_por_entrada_producida():
    esperado = [{"position": "Cajera", "company": "Tienda Azul"}]
    producido = [{"position": "Cajera", "company": "Tienda Azul"}, {"position": "Mesera", "company": "Café Sol"}]
    por_entrada = score_entries_by_actual(esperado, producido)
    assert por_entrada == [Counts(2, 0, 0), Counts(0, 0, 2)]


def test_campo_largo_baja_la_confianza():
    texto = ("Cajera\nTienda Azul S.A. de C.V. Realizaba cobros, cortes de caja, inventarios y atención a clientes en piso de venta\n"
             "2018 - 2019")
    assert parse_experience(to_lines(texto), None)[0].confidence < 0.75


def test_rotulo_no_es_puesto():
    e = parse_experience(to_lines("Tienda Azul S.A. de C.V.\n2018 - 2019\nTareas o actividades\n-Cobro en caja"), None)[0]
    assert e.position is None and e.company == "Tienda Azul S.A. de C.V."


def test_prosa_de_estudios_conserva_nivel_sin_texto_de_grado():
    salida = parse_education(to_lines("2008\nCurse la primaria .\n2011\nCurse la secundaria ."), None)
    assert [(e.level, e.level_text) for e in salida] == [("elementary", None), ("middle_school", None)]
