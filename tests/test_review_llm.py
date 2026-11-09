"""Hallazgos de la revisión de la capa de LLM y de las rondas 4–5: cada uno reproduce el defecto."""

from datetime import date

import pytest

from cv_parser.entries import parse_experience
from cv_parser.llm.redact import redact
from cv_parser.llm.validate import validate_response
from tests.helpers import to_lines
from tests.test_pipeline_llm import ClienteFalso

HOY = date(2026, 11, 9)


# 1. Redacción
@pytest.mark.parametrize("sucio,secreto", [
    ("RFC: PEDR850103", "850103"), ("RFC PEDR-850103-AB1", "850103"), ("RFC: PEDR 850103 AB1", "850103"),
    ("CURP: PEDR 850103 HJCRZS 09", "850103"), ("CURP: PEDR-850103-HJCRZS09", "850103"),
    ("Tel: 1234-5678", "5678"), ("Casa: 36 12 34 56", "34 56"),
])
def test_redacta_variantes(sucio, secreto):
    assert secreto not in redact(f"Ana Pérez\n{sucio}\nCajera 2018 - 2019")


def test_redacta_telefono_partido_en_dos_renglones():
    salida = redact("Ana Pérez\nTel: 33 1234\n5678\nCajera 2018 - 2019")
    assert "1234" not in salida and "Cajera 2018 - 2019" in salida


# 2. Validación
TEXTO = "Cajera\nTienda Azul\nMarzo 2018 - 2019\nLicenciatura en Derecho\nUniversidad Azul\n2010 - 2014\n- Cobro en caja"


def _empleo(**c):
    base = {"position": "Cajera", "company": "Tienda Azul", "city": None, "country_code": None,
            "start": {"year": 2018, "month": 3}, "end": {"year": 2019, "month": None}, "is_current": False,
            "description": "Cobro en caja"}
    base.update(c)
    return base


def test_fechas_que_no_estan_en_el_cv_se_vacian():
    _, exp, avisos = validate_response({"experience": [_empleo(start={"year": 2015, "month": 3}, end={"year": 2016, "month": 7})], "education": []}, TEXTO, HOY)
    assert exp[0].start is None and exp[0].end is None and avisos


def test_mes_que_no_esta_en_el_cv_se_vacia():
    _, exp, _ = validate_response({"experience": [_empleo(end={"year": 2019, "month": 6})], "education": []}, TEXTO, HOY)
    assert exp[0].end.year == 2019 and exp[0].end.month is None


def test_entrada_solo_con_fecha_se_descarta():
    _, exp, avisos = validate_response({"experience": [{"start": {"year": 2018, "month": None}}], "education": []}, TEXTO, HOY)
    assert exp == [] and avisos


def test_estudio_solo_con_nivel_se_descarta():
    edu, _, _ = validate_response({"experience": [], "education": [{"level": "university"}]}, TEXTO, HOY)
    assert edu == []


def test_nivel_que_contradice_el_texto_se_vacia():
    estudio = {"level": "doctorate", "level_text": "Licenciatura en Derecho", "institution": "Universidad Azul"}
    edu, _, _ = validate_response({"experience": [], "education": [estudio]}, TEXTO, HOY)
    assert edu[0].level is None


def test_descripcion_inventada_se_quita():
    _, exp, _ = validate_response({"experience": [_empleo(description="Cobro en caja\nGerente regional de 50 tiendas")], "education": []}, TEXTO, HOY)
    assert exp[0].description == "Cobro en caja"


def test_actual_sin_palabra_de_actual_no_cuenta():
    _, exp, _ = validate_response({"experience": [_empleo(is_current=True, end=None)], "education": []}, TEXTO, HOY)
    assert exp[0].is_current is False


# 3. Apellido como país
@pytest.mark.parametrize("nombre", ["Juan Pérez Guerrero", "María López Hidalgo", "Pedro Sánchez España"])
def test_apellido_no_da_pais(nombre):
    import io

    from docx import Document

    from cv_parser.pipeline import parse_document
    doc = Document()
    for renglon in [nombre, "EXPERIENCIA", "Cajera", "Tienda Azul", "2018 - 2019"]:
        doc.add_paragraph(renglon)
    buf = io.BytesIO()
    doc.save(buf)
    assert parse_document(buf.getvalue()).extracted.experience[0].country_code is None


# 4. Título más palabra genérica de empresa
@pytest.mark.parametrize("linea", ["Analista Servicios Financieros", "Gerente Restaurante"])
def test_no_inventa_empresa_de_palabra_generica(linea):
    e = parse_experience(to_lines(f"{linea}\n2015 - 2017"), None)[0]
    assert e.company is None and e.position == linea
