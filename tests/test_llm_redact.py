import pytest

from cv_parser.llm.redact import redact


@pytest.mark.parametrize("sucio", [
    "ana.perez@ejemplo.invalid", "(33) 1234-5678", "+52 33 1234 5678", "Cel. 3312345678",
    "CURP: PEPA900101MJCRRN09", "RFC: PEPA900101AB1", "NSS: 12345678901",
])
def test_redacta(sucio):
    salida = redact(f"Ana Pérez\n{sucio}\nCajera 2018 - 2019")
    assert sucio.split()[-1] not in salida and "Cajera 2018 - 2019" in salida and "Ana Pérez" in salida


def test_conserva_fechas_y_renglones():
    texto = "Cajera\nMarzo 2018 - 01/02/2021\nTienda Azul"
    assert redact(texto) == texto
