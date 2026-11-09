from fastapi.testclient import TestClient

from cv_parser.api import create_app
from cv_parser.config import Settings


def preflight(client, origin):
    return client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


def test_health():
    r = TestClient(create_app(Settings())).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "healthy", "version": "0.1.0"}


def test_cors_configurable():
    c = TestClient(create_app(Settings(cors_origins=["http://localhost:3000"])))
    assert preflight(c, "http://localhost:3000").headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in preflight(c, "https://example.com").headers


def test_cors_apagado_por_defecto():
    c = TestClient(create_app(Settings()))
    assert "access-control-allow-origin" not in preflight(c, "http://localhost:3000").headers


def test_settings_desde_entorno(monkeypatch):
    monkeypatch.setenv("CV_PARSER_CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("CV_PARSER_MAX_BYTES", "2048")
    monkeypatch.setenv("CV_PARSER_API_KEY", "")
    s = Settings.from_env()
    assert s.cors_origins == ["http://a.test", "http://b.test"]
    assert s.max_bytes == 2048 and s.api_key is None and s.convert_timeout == 60
