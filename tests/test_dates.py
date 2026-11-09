from datetime import date

import pytest

from cv_parser.dates import find_date_range
from cv_parser.models import YearMonth

HOY = date(2026, 11, 6)

CASOS = [
    ("Marzo 2021 - Actualidad", (2021, 3), None, True),
    ("March 2021 - Present", (2021, 3), None, True),
    ("Ene 2018 – Feb 2021", (2018, 1), (2021, 2), False),
    ("Jan. 2018 to Feb. 2021", (2018, 1), (2021, 2), False),
    ("03/2021 - 06/2022", (2021, 3), (2022, 6), False),
    ("15/03/2018 - 20/06/2020", (2018, 3), (2020, 6), False),
    ("2018 - 2020", (2018, None), (2020, None), False),
    ("2015 a 2017", (2015, None), (2017, None), False),
    ("de marzo de 2021 a la fecha", (2021, 3), None, True),
    ("Sept 2019 - Dic 2020", (2019, 9), (2020, 12), False),
    ("2021 - hoy", (2021, None), None, True),
    ("Junio 2017", (2017, 6), None, False),
    ("2017", (2017, None), None, False),
    # variantes de texto sucio
    ("MARZO 2021 – ACTUALIDAD", (2021, 3), None, True),
    ("Marzo 2021 - Actualidad", (2021, 3), None, True),
    ("2018-2020", (2018, None), (2020, None), False),
    ("2024 - En curso", (2024, None), None, True),
    ("Febrero de 2019 - Agosto de 2020", (2019, 2), (2020, 8), False),
    ("01/03/2018 - 20/06/2020", (2018, 3), (2020, 6), False),  # ambiguo: día/mes, convención en español
]
SIN_FECHA = ["33 1234 5678", "Tel: 3312345678", "12/05/1990", "1234",
             "Fecha de nacimiento: 12 de mayo de 1990", "Av. Juárez 2021 #45, Col. Centro",
             "2021 - 2018", "Marzo 2099 - Abril 2099", "Recepcionista",
             "CURP: LOHM900512MJCPRR09", "Trabajé en 2019 atendiendo clientes de la tienda"]


def ym(par):
    return None if par is None else YearMonth(year=par[0], month=par[1])


@pytest.mark.parametrize("texto,inicio,fin,actual", CASOS)
def test_rangos(texto, inicio, fin, actual):
    r = find_date_range(texto, today=HOY)
    assert r is not None
    assert (r.start, r.end, r.is_current) == (ym(inicio), ym(fin), actual)


@pytest.mark.parametrize("texto", SIN_FECHA)
def test_sin_fecha(texto):
    assert find_date_range(texto, today=HOY) is None


def test_tramo_de_fecha():
    from cv_parser.dates import find_date_span
    texto = "Recepcionista Enero 2018 - Febrero 2021"
    rango, a, b = find_date_span(texto, today=HOY)
    assert texto[a:b] == "Enero 2018 - Febrero 2021" and rango.end == YearMonth(year=2021, month=2)
    texto = "Asistente | Marzo 2021 – Actualidad"
    _, a, b = find_date_span(texto, today=HOY)
    assert texto[a:b] == "Marzo 2021 – Actualidad"
