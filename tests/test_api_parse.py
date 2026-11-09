import pytest
from fastapi.testclient import TestClient

from cv_parser import api
from cv_parser.api import create_app
from cv_parser.config import Settings
from tests.helpers import read

client = TestClient(create_app(Settings(max_bytes=1024 * 1024)))


def lanza_runtime_error_con(mensaje):
    def falla(*args, **kwargs):
        raise RuntimeError(mensaje)
    return falla


def test_parse_ok_con_nombre_hostil():
    r = client.post("/v1/parse", files={"file": ("../../x.pdf", read("es_real.doc"))})
    body = r.json()
    assert r.status_code == 200 and set(body) == {"status", "meta", "warnings", "confidence", "extracted"}
    assert body["meta"]["format"] == "doc" and body["meta"]["parser_version"] == "0.1.0"
    assert body["meta"]["duration_ms"] >= 0


@pytest.mark.parametrize("kwargs,codigo,error", [
    ({}, 400, "missing_file"),
    ({"files": {"file": ("a.pdf", b"")}}, 400, "missing_file"),
    ({"files": {"file": ("a.pdf", b"%PDF" + b"0" * (1024 * 1024))}}, 413, "file_too_large"),
    ({"files": {"file": ("a.exe", b"MZ\x90\x00")}}, 415, "unsupported_format"),
    ({"files": {"file": ("a.pdf", read("danado.pdf"))}}, 422, "corrupt_file"),
    ({"files": {"file": ("a.pdf", read("protegido.pdf"))}}, 422, "corrupt_file"),
    ({"data": {"file": "no soy un archivo"}}, 400, "missing_file"),
])
def test_errores(kwargs, codigo, error):
    r = client.post("/v1/parse", **kwargs)
    assert r.status_code == codigo and r.json() == {"error": error}


def test_clave_opcional():
    c = TestClient(create_app(Settings(api_key="secreta")))
    archivo = {"file": ("a.pdf", read("es_una_columna.pdf"))}
    assert c.post("/v1/parse", files=archivo).json() == {"error": "unauthorized"}
    assert c.post("/v1/parse", files=archivo, headers={"X-API-Key": "otra"}).status_code == 401
    assert c.post("/v1/parse", files=archivo, headers={"X-API-Key": "secreta"}).status_code == 200
    assert c.get("/health").status_code == 200


def test_500_sin_contenido(monkeypatch, caplog):
    monkeypatch.setattr(api, "parse_document", lanza_runtime_error_con("María López"))
    r = TestClient(create_app(Settings()), raise_server_exceptions=False).post("/v1/parse", files={"file": ("a.pdf", read("es_una_columna.pdf"))})
    assert r.status_code == 500 and r.json() == {"error": "internal_error"}
    assert "María" not in caplog.text


def test_timeout_de_conversion(monkeypatch):
    from cv_parser.errors import ConversionTimeout

    def lento(*args, **kwargs):
        raise ConversionTimeout()
    monkeypatch.setattr(api, "parse_document", lento)
    r = TestClient(create_app(Settings())).post("/v1/parse", files={"file": ("a.doc", read("es_real.doc"))})
    assert r.status_code == 500 and r.json() == {"error": "conversion_timeout"}
