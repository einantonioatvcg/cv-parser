import pytest

from cv_parser.places import find_place, is_place_line

LUGARES = [
    ("Guadalajara, Jalisco", "Guadalajara", "MX"), ("Zapopan, Jalisco, México", "Zapopan", "MX"),
    ("CDMX", "Ciudad de México", "MX"), ("Austin, Texas, USA", "Austin", "US"),
    ("Madrid, España", "Madrid", "ES"), ("Guadalajara, España", "Guadalajara", "ES"),
    ("Universidad de Guadalajara, Guadalajara, Jalisco", "Guadalajara", "MX"),
    # variantes
    ("GUADALAJARA, JAL.", "Guadalajara", "MX"), ("Monterrey, N.L.", "Monterrey", "MX"),
    ("Tienda Azul, Madrid, España", "Madrid", "ES"), ("Jalisco", None, "MX"), ("México", None, "MX"),
    ("Zapopan, Jalisco, C.P. 45100", "Zapopan", "MX"),
]
NO_LUGAR = ["Universidad de Guadalajara", "Grupo Comercial del Bajío", "Foo, Bar",
            "Trabajé en Guadalajara", "Tienda Azul, Lugarcito, México"]


@pytest.mark.parametrize("texto,ciudad,pais", LUGARES)
def test_lugares(texto, ciudad, pais):
    p = find_place(texto)
    assert p is not None and (p.city, p.country_code) == (ciudad, pais)


@pytest.mark.parametrize("texto", NO_LUGAR)
def test_sin_lugar(texto):
    p = find_place(texto)
    assert p is None or p.city is None


def test_pais_explicito_sin_ciudad_conocida():
    p = find_place("Tienda Azul, Lugarcito, México")
    assert p is not None and p.country_code == "MX" and p.city is None


def test_linea_entera_es_lugar():
    assert is_place_line("Guadalajara, Jalisco, México")
    assert not is_place_line("Universidad de Guadalajara, Guadalajara, Jalisco")


def test_separa_lugar():
    from cv_parser.places import split_place
    resto, lugar = split_place("Grupo Comercial del Bajío S.A. de C.V., Guadalajara, Jalisco")
    assert resto == "Grupo Comercial del Bajío S.A. de C.V." and lugar.city == "Guadalajara"
    assert split_place("Guadalajara, Jalisco")[0] == ""
    assert split_place("Tienda Azul") == ("Tienda Azul", None)
