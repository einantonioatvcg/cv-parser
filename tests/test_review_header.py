"""Hallazgos de la revisión del encabezado con LLM: lo que el CV no dice nunca llega a la salida."""

import pytest

from cv_parser.llm.validate import validate_header, validate_response

CV = ("JUAN CARLOS PÉREZ GÓMEZ\nContador Público\nCorreo: [correo]\nTeléfono: [telefono]\nPERFIL\n"
      "Contador con 5 años de experiencia en auditoría.\nEXPERIENCIA\nAuxiliar Contable\nComercial Norte SA\n2018 - 2023")


@pytest.mark.parametrize("nombre", ["Juan Carlos Peres Gomez", "Ana López Ruiz [correo]", "Comercial Norte SA"])
def test_nombre_alterado_o_que_no_es_nombre_se_vacia(nombre):
    datos, _ = validate_header({"name": nombre, "headline": None, "summary": None}, CV)
    assert datos["name"] is None


def test_nombre_exacto_devuelve_el_texto_del_cv():
    datos, _ = validate_header({"name": "Juan Carlos Pérez Gómez", "headline": None, "summary": None}, CV)
    assert datos["name"] == "JUAN CARLOS PÉREZ GÓMEZ"


@pytest.mark.parametrize("resumen", ["Contador con 8 años de experiencia en auditoría.", "Contador sin 5 años de experiencia en auditoría."])
def test_resumen_alterado_se_vacia(resumen):
    datos, _ = validate_header({"name": None, "headline": None, "summary": resumen}, CV)
    assert datos["summary"] is None


@pytest.mark.parametrize("titulo", ["[correo]", "Experiencia", "Correo: [correo]"])
def test_titulo_que_es_marca_seccion_o_rotulo_se_vacia(titulo):
    datos, _ = validate_header({"name": None, "headline": titulo, "summary": None}, CV)
    assert datos["headline"] is None


def test_resumen_de_palabras_sueltas_se_vacia():
    datos, _ = validate_header({"name": None, "headline": None, "summary": "Contador. Auditoría."}, CV)
    assert datos["summary"] is None


def test_empresa_con_letra_cambiada_se_vacia():
    _, exp, _ = validate_response({"experience": [{"position": "Auxiliar Contable", "company": "Comercial Morte SA"}], "education": []}, CV)
    assert exp[0].company is None and exp[0].position == "Auxiliar Contable"
