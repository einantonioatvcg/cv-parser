"""Clientes de LLM probados sin red: el SDK de cada proveedor se reemplaza por un objeto falso."""

import logging
from types import SimpleNamespace

import pytest

from cv_parser.config import Settings
from cv_parser.llm.clients import LLMError, SYSTEM_PROMPT, make_client
from cv_parser.llm.schema import RESPONSE_SCHEMA


class _Anthropic:
    def __init__(self, texto, tokens):
        self.messages = SimpleNamespace(create=self._create)
        self.texto, self.tokens, self.kwargs = texto, tokens, None

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.texto)],
                               usage=SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1]))


class _OpenAI:
    def __init__(self, texto, tokens):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.texto, self.tokens, self.kwargs = texto, tokens, None

    def _create(self, **kwargs):
        self.kwargs = kwargs
        choice = SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=self.texto, refusal=None))
        return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=self.tokens[0], completion_tokens=self.tokens[1]))


class _Gemini:
    def __init__(self, texto, tokens):
        self.models = SimpleNamespace(generate_content=self._generate)
        self.texto, self.tokens, self.kwargs = texto, tokens, None

    def _generate(self, **kwargs):
        self.kwargs = kwargs
        uso = SimpleNamespace(prompt_token_count=self.tokens[0], candidates_token_count=self.tokens[1], thoughts_token_count=0)
        return SimpleNamespace(text=self.texto, usage_metadata=uso)


FALSOS = {"anthropic": _Anthropic, "openai": _OpenAI, "gemini": _Gemini}


def cliente_con_sdk_falso(proveedor, respuesta, tokens):
    cliente = make_client(Settings(llm_provider=proveedor, llm_model="modelo-x"))
    cliente.sdk = FALSOS[proveedor](respuesta, tokens)
    return cliente


def test_none_no_crea_cliente():
    assert make_client(Settings()) is None


def test_sin_modelo_falla():
    with pytest.raises(ValueError):
        make_client(Settings(llm_provider="anthropic"))


@pytest.mark.parametrize("proveedor,variable", [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"), ("gemini", "GEMINI_API_KEY")])
def test_sin_clave_falla_al_usar_y_no_la_muestra(proveedor, variable, monkeypatch, caplog):
    monkeypatch.delenv(variable, raising=False)
    cliente = make_client(Settings(llm_provider=proveedor, llm_model="modelo-x"))
    with pytest.raises(LLMError):
        cliente.extract("texto")


@pytest.mark.parametrize("proveedor", ["anthropic", "openai", "gemini"])
def test_adaptadores_devuelven_json_y_tokens(proveedor):
    cliente = cliente_con_sdk_falso(proveedor, '{"education": [], "experience": []}', (100, 20))
    r = cliente.extract("texto del cv")
    assert r.data == {"education": [], "experience": []} and (r.input_tokens, r.output_tokens) == (100, 20)
    assert "texto del cv" in str(cliente.sdk.kwargs) and SYSTEM_PROMPT[:40] in str(cliente.sdk.kwargs)


@pytest.mark.parametrize("proveedor", ["anthropic", "openai", "gemini"])
def test_json_invalido_es_llmerror(proveedor):
    with pytest.raises(LLMError):
        cliente_con_sdk_falso(proveedor, '{"education": [', (1, 1)).extract("texto")


def test_error_del_sdk_es_llmerror_sin_texto(caplog):
    cliente = cliente_con_sdk_falso("anthropic", "{}", (1, 1))

    def falla(**kwargs):
        raise RuntimeError("María López en el mensaje del proveedor")
    cliente.sdk.messages.create = falla
    caplog.set_level(logging.DEBUG)
    with pytest.raises(LLMError) as err:
        cliente.extract("texto")
    assert "María" not in str(err.value) and "María" not in caplog.text


def test_prompt_sin_datos_de_consumidor():
    from tests.test_contract import mentions_consumer
    assert not mentions_consumer(SYSTEM_PROMPT) and "experience" in SYSTEM_PROMPT


def test_enum_de_nivel_compatible_con_proveedores():
    nivel = RESPONSE_SCHEMA["properties"]["education"]["items"]["properties"]["level"]
    assert "anyOf" in nivel and {"type": "null"} in nivel["anyOf"] and "enum" not in nivel


def test_gemini_usa_v1beta(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa")
    cliente = make_client(Settings(llm_provider="gemini", llm_model="modelo-x"))
    sdk = cliente._make_sdk("clave-falsa")
    assert sdk._api_client._http_options.api_version == "v1beta"


def _uniones(nodo):
    if isinstance(nodo, dict):
        propio = 1 if ("anyOf" in nodo or isinstance(nodo.get("type"), list)) else 0
        return propio + sum(_uniones(v) for v in nodo.values())
    if isinstance(nodo, list):
        return sum(_uniones(v) for v in nodo)
    return 0


def test_esquema_dentro_del_limite_de_uniones():
    assert _uniones(RESPONSE_SCHEMA) <= 16   # límite de Anthropic para campos nulos o con anyOf
