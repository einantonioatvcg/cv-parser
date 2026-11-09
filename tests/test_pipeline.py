import logging
import socket

import pytest

from cv_parser.errors import UnsupportedFormat
from cv_parser.pipeline import parse_document
from tests.helpers import codigos, load_json, read, sin_confianza


def lanza_error(*args, **kwargs):
    raise OSError("conexión bloqueada en pruebas")


@pytest.mark.parametrize("name,expected", [
    ("es_una_columna.pdf", "expected_es.json"), ("es_dos_columnas.pdf", "expected_es.json"),
    ("es_parrafos.docx", "expected_es.json"), ("es_tablas_cuadros.docx", "expected_es.json"),
    ("es_real.doc", "expected_es.json"), ("es_rtf_renombrado.doc", "expected_es.json"),
    ("es_html_renombrado.doc", "expected_es.json"), ("es_docx_renombrado.doc", "expected_es.json"),
    ("en_una_columna.pdf", "expected_en.json"), ("en_dos_columnas.pdf", "expected_en.json"),
    ("en_parrafos.docx", "expected_en.json"), ("en_tablas_cuadros.docx", "expected_en.json"),
    ("en_real.doc", "expected_en.json"),
])
def test_fixture_coincide(name, expected):
    r = parse_document(read(name))
    assert r.status == "ok" and sin_confianza(r.extracted.model_dump()) == load_json(expected)
    assert {"summary", "experience", "education"} <= set(r.meta.sections)


def test_meta():
    r = parse_document(read("es_dos_columnas.pdf"))
    assert (r.meta.format, r.meta.language, r.meta.pages, r.meta.columns) == ("pdf", "es", 1, 2)
    assert r.meta.parser_version == "0.1.0" and r.meta.duration_ms >= 0
    assert parse_document(read("en_parrafos.docx")).meta.language == "en"
    assert r.confidence.overall >= 0.6 and r.confidence.summary == pytest.approx(0.9)


def test_escaneado():
    r = parse_document(read("es_escaneado.pdf"))
    assert r.status == "unreadable" and "scanned_pdf" in codigos(r)


def test_sin_texto():
    r = parse_document(read("sin_texto.docx"))
    assert r.status == "unreadable" and "empty_document" in codigos(r)


def test_sin_encabezados():
    r = parse_document(read("es_sin_encabezados.docx"))
    assert r.status == "partial" and "no_sections" in codigos(r)
    assert r.meta.sections == [] and r.extracted.experience == [] and r.extracted.education == []


def test_formato_legacy_se_reporta_doc():
    assert parse_document(read("es_rtf_renombrado.doc")).meta.format == "doc"


def test_formato_no_soportado():
    with pytest.raises(UnsupportedFormat):
        parse_document(b"MZ\x90\x00")


def test_no_abre_conexiones(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lanza_error)
    assert parse_document(read("es_parrafos.docx")).status == "ok"


def test_logs_sin_contenido(caplog):
    caplog.set_level(logging.DEBUG)
    parse_document(read("es_una_columna.pdf"))
    assert "Administrativa" not in caplog.text
