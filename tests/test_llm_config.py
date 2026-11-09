import pytest

from cv_parser.config import Settings


def test_settings_llm_desde_entorno(monkeypatch):
    monkeypatch.setenv("CV_PARSER_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("CV_PARSER_LLM_MODEL", "claude-haiku-5-5")
    s = Settings.from_env()
    assert (s.llm_provider, s.llm_model, s.llm_timeout) == ("anthropic", "claude-haiku-5-5", 30)
    assert (s.llm_mode, s.llm_threshold) == ("low_confidence", 0.75)
    assert Settings().llm_provider == "none"


def test_modo_y_umbral(monkeypatch):
    monkeypatch.setenv("CV_PARSER_LLM_MODE", "always")
    monkeypatch.setenv("CV_PARSER_LLM_THRESHOLD", "0.6")
    s = Settings.from_env()
    assert (s.llm_mode, s.llm_threshold) == ("always", 0.6)


@pytest.mark.parametrize("var,valor", [("CV_PARSER_LLM_PROVIDER", "otro"), ("CV_PARSER_LLM_MODE", "a veces")])
def test_valores_desconocidos_fallan(monkeypatch, var, valor):
    monkeypatch.setenv(var, valor)
    with pytest.raises(ValueError):
        Settings.from_env()
