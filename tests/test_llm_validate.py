from datetime import date

import pytest

from cv_parser.llm.schema import RESPONSE_SCHEMA
from cv_parser.llm.validate import validate_response

HOY = date(2026, 11, 9)
TEXTO = ("Cajera\nTienda Azul, Zapopan, Jalisco\nMarzo 2018 - Febrero 2021\n- Cobro en caja\n"
         "Licenciatura en Derecho\nUniversidad Azul\n2010 - 2014")


def empleo(**cambios):
    base = {"position": "Cajera", "company": "Tienda Azul", "city": "Zapopan", "country_code": "MX",
            "start": {"year": 2018, "month": 3}, "end": {"year": 2021, "month": 2}, "is_current": False,
            "description": "Cobro en caja"}
    base.update(cambios)
    return base


def estudio(**cambios):
    base = {"level": "university", "level_text": "Licenciatura en Derecho", "is_technical": False,
            "area_text": "Derecho", "institution": "Universidad Azul", "city": None, "country_code": None,
            "start": {"year": 2010, "month": None}, "end": {"year": 2014, "month": None}, "is_current": False}
    base.update(cambios)
    return base


def test_esquema_cubre_ambas_listas():
    assert {"education", "experience"} <= set(RESPONSE_SCHEMA["required"])
    assert RESPONSE_SCHEMA["additionalProperties"] is False


def test_entrada_valida_pasa_con_confianza():
    edu, exp, avisos = validate_response({"experience": [empleo()], "education": [estudio()]}, TEXTO, HOY)
    assert exp[0].position == "Cajera" and exp[0].confidence == pytest.approx(1.0) and avisos == []
    assert edu[0].institution == "Universidad Azul" and edu[0].confidence == pytest.approx(1.0)


def test_texto_que_no_esta_en_el_cv_se_vacia():
    _, exp, avisos = validate_response({"experience": [empleo(company="Grupo Inventado")], "education": []}, TEXTO, HOY)
    assert exp[0].company is None and [a.code for a in avisos] == ["llm_rejected"]
    assert (avisos[0].section, avisos[0].index) == ("experience", 0)


def test_tolera_mayusculas_y_acentos():
    _, exp, _ = validate_response({"experience": [empleo(position="CAJERA", city="zapopán")], "education": []}, TEXTO, HOY)
    assert exp[0].position == "Cajera" and exp[0].city == "Zapopan"   # se devuelve el texto del CV


@pytest.mark.parametrize("inicio,fin", [({"year": 2099, "month": 1}, None), ({"year": 2021, "month": 1}, {"year": 2018, "month": 1}),
                                        ({"year": 2018, "month": 13}, None)])
def test_fechas_invalidas_se_vacian(inicio, fin):
    _, exp, _ = validate_response({"experience": [empleo(start=inicio, end=fin)], "education": []}, TEXTO, HOY)
    assert exp[0].start is None and exp[0].end is None


def test_nivel_y_pais_fuera_de_catalogo():
    edu, _, _ = validate_response({"experience": [], "education": [estudio(level="kinder", country_code="XX")]}, TEXTO, HOY)
    assert edu[0].level is None and edu[0].country_code is None


def test_entrada_sin_datos_clave_se_descarta():
    _, exp, avisos = validate_response({"experience": [empleo(position="Nada", company="Tampoco", start=None, end=None)], "education": []}, TEXTO, HOY)
    assert exp == [] and avisos[0].code == "llm_rejected"


def test_actual_quita_fin():
    texto = TEXTO.replace("Febrero 2021", "Febrero 2021 - Actualidad")
    _, exp, _ = validate_response({"experience": [empleo(is_current=True, end={"year": 2021, "month": 2})], "education": []}, texto, HOY)
    assert exp[0].is_current and exp[0].end is None


def test_campos_faltantes_o_de_otro_tipo_no_rompen():
    _, exp, _ = validate_response({"experience": [{"position": "Cajera", "start": "2018"}], "education": []}, TEXTO, HOY)
    assert exp[0].position == "Cajera" and exp[0].start is None


def test_ciudad_sin_estado():
    _, exp, _ = validate_response({"experience": [empleo(city="Zapopan, Jalisco")], "education": []}, TEXTO, HOY)
    assert exp[0].city == "Zapopan"
