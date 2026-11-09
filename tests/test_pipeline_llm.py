"""Integración del LLM opcional con un cliente falso: sin red."""

import logging

import pytest
from fastapi.testclient import TestClient

from cv_parser import api
from cv_parser.api import create_app
from cv_parser.config import Settings
from cv_parser.llm.clients import LLMError, LLMResult
from cv_parser.pipeline import parse_document
from tests.helpers import codigos, load_json, read, sin_confianza


class ClienteFalso:
    provider, model = "falso", "modelo-falso"

    def __init__(self, respuesta):
        self.respuesta, self.llamadas, self.texto = respuesta, 0, None

    def extract(self, text):
        self.llamadas += 1
        self.texto = text
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return LLMResult(self.respuesta, 1000, 300)


def respuesta_valida_es():
    esperado = load_json("expected_es.json")
    return {"education": esperado["education"], "experience": esperado["experience"]}


def test_sin_llm_igual_que_antes():
    r = parse_document(read("es_parrafos.docx"))
    assert {k: r.meta.extraction[k] for k in ("experience", "education")} == {"experience": "rules", "education": "rules"}


def test_llm_reemplaza_empleos_y_estudios():
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta_valida_es()), llm_mode="always")
    assert {k: r.meta.extraction[k] for k in ("experience", "education")} == {"experience": "llm", "education": "llm"}
    assert sin_confianza(r.extracted.model_dump()) == load_json("expected_es.json") and r.status == "ok"


def test_llm_recibe_texto_sin_contacto():
    falso = ClienteFalso(respuesta_valida_es())
    parse_document(read("es_parrafos.docx"), llm=falso, llm_mode="always")
    assert "maria.lopez@ejemplo.invalid" not in falso.texto and "1234 5678" not in falso.texto
    assert "Grupo Comercial del Bajío" in falso.texto


@pytest.mark.parametrize("falla", [LLMError("timeout"), {"educacion": []}, {"education": "x", "experience": []}])
def test_falla_del_llm_deja_reglas(falla, caplog):
    caplog.set_level(logging.DEBUG)
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(falla), llm_mode="always")
    assert r.status == "partial" and "llm_unavailable" in codigos(r)
    assert {k: r.meta.extraction[k] for k in ("experience", "education")} == {"experience": "rules", "education": "rules"}
    assert len(r.extracted.experience) == 2
    assert "Administrativa" not in caplog.text


def test_modo_baja_confianza_no_llama_si_las_reglas_bastan():
    falso = ClienteFalso(respuesta_valida_es())
    r = parse_document(read("es_parrafos.docx"), llm=falso, llm_mode="low_confidence", llm_threshold=0.75)
    assert falso.llamadas == 0 and {k: r.meta.extraction[k] for k in ("experience", "education")} == {"experience": "rules", "education": "rules"}


def test_modo_baja_confianza_llama_si_no_hay_secciones():
    falso = ClienteFalso({"education": [], "experience": []})
    r = parse_document(read("es_sin_encabezados.docx"), llm=falso, llm_mode="low_confidence", llm_threshold=0.75)
    assert falso.llamadas == 1 and {k: r.meta.extraction[k] for k in ("experience", "education")} == {"experience": "llm", "education": "llm"}


def test_ilegible_no_llama_al_llm():
    falso = ClienteFalso(respuesta_valida_es())
    parse_document(read("es_escaneado.pdf"), llm=falso, llm_mode="always")
    assert falso.llamadas == 0


def test_log_con_tokens_sin_contenido(caplog):
    caplog.set_level(logging.INFO)
    parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta_valida_es()), llm_mode="always")
    assert "modelo-falso" in caplog.text and "1000" in caplog.text and "Bajío" not in caplog.text


def test_api_usa_el_cliente_configurado(monkeypatch):
    monkeypatch.setattr(api, "make_client", lambda settings: ClienteFalso(respuesta_valida_es()))
    app = create_app(Settings(llm_provider="anthropic", llm_model="x", llm_mode="always"))
    body = TestClient(app).post("/v1/parse", files={"file": ("a.docx", read("es_parrafos.docx"))}).json()
    assert body["meta"]["extraction"]["experience"] == "llm"


def test_pais_del_encabezado_si_el_llm_no_lo_da():
    respuesta = respuesta_valida_es()
    for entrada in respuesta["experience"] + respuesta["education"]:
        entrada["country_code"], entrada["city"] = None, None
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta), llm_mode="always")
    assert {e.country_code for e in r.extracted.experience + r.extracted.education} == {"MX"}
