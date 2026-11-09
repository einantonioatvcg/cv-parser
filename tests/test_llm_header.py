"""Nombre, título y resumen también desde el LLM, validados contra el texto."""

from cv_parser.llm.schema import RESPONSE_SCHEMA
from cv_parser.llm.validate import validate_header
from cv_parser.pipeline import parse_document
from tests.helpers import codigos, load_json, read
from tests.test_pipeline_llm import ClienteFalso, respuesta_valida_es

TEXTO = ("Rosa Pérez Díaz\nAuxiliar Contable\nPERFIL\nContadora con cinco años de experiencia.\n"
         "Manejo de nómina y facturación.\nEXPERIENCIA\nAuxiliar Contable\nDespacho Azul\n2018 - 2023")


def test_esquema_incluye_encabezado():
    assert {"name", "headline", "summary"} <= set(RESPONSE_SCHEMA["required"])


def test_encabezado_valido():
    datos, avisos = validate_header({"name": "Rosa Pérez Díaz", "headline": "Auxiliar Contable",
                                     "summary": "Contadora con cinco años de experiencia. Manejo de nómina y facturación."}, TEXTO)
    assert datos == {"name": "Rosa Pérez Díaz", "headline": "Auxiliar Contable",
                     "summary": "Contadora con cinco años de experiencia. Manejo de nómina y facturación."}
    assert avisos == []


def test_encabezado_inventado_se_vacia():
    datos, avisos = validate_header({"name": "Rosa María Pérez", "headline": "Gerente General",
                                     "summary": "Contadora con cinco años de experiencia. Experta en auditoría fiscal."}, TEXTO)
    assert datos["name"] is None and datos["headline"] is None
    assert datos["summary"] == "Contadora con cinco años de experiencia."
    assert {a.section for a in avisos} == {"contact", "headline", "summary"} and all(a.code == "llm_rejected" for a in avisos)


def respuesta_con_encabezado(**cambios):
    r = respuesta_valida_es()
    esperado = load_json("expected_es.json")
    r.update({"name": esperado["contact"]["name"], "headline": esperado["headline"], "summary": esperado["summary"]})
    r.update(cambios)
    return r


def test_pipeline_usa_encabezado_del_llm():
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta_con_encabezado()), llm_mode="always")
    assert r.meta.extraction == {"experience": "llm", "education": "llm", "contact": "llm", "headline": "llm", "summary": "llm"}
    assert r.extracted.contact.email == "maria.lopez@ejemplo.invalid"   # correo y teléfono siempre de las reglas


def test_pipeline_conserva_reglas_si_el_llm_no_da_encabezado():
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta_con_encabezado(name=None, headline="Inventado", summary=None)),
                       llm_mode="always")
    assert r.meta.extraction["contact"] == "rules" and r.meta.extraction["headline"] == "rules"
    assert r.extracted.headline == "Asistente Administrativa" and r.extracted.contact.name == "María Fernanda López Hernández"
    assert "llm_rejected" in codigos(r)


def test_sin_llm_extraction_completo():
    assert parse_document(read("es_parrafos.docx")).meta.extraction == {
        "experience": "rules", "education": "rules", "contact": "rules", "headline": "rules", "summary": "rules"}
