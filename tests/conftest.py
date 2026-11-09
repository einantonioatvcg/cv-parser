"""Ninguna prueba debe usar claves reales ni configuración de LLM del entorno."""

import pytest

_VARIABLES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "CV_PARSER_LLM_PROVIDER", "CV_PARSER_LLM_MODEL",
              "CV_PARSER_LLM_MODE", "CV_PARSER_LLM_THRESHOLD", "CV_PARSER_LLM_TIMEOUT")


@pytest.fixture(autouse=True)
def _sin_claves_ni_llm(monkeypatch):
    for name in _VARIABLES:
        monkeypatch.delenv(name, raising=False)
