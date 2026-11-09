"""Clientes de LLM intercambiables. Cada adaptador pide la misma salida JSON con esquema.

Nunca se registra texto del CV, del prompt ni de la respuesta; los errores solo llevan la clase de la excepción.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from cv_parser.config import Settings
from cv_parser.llm.prompt import SYSTEM_PROMPT
from cv_parser.llm.schema import RESPONSE_SCHEMA

MAX_OUTPUT_TOKENS = 8000
KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}

__all__ = ["LLMClient", "LLMError", "LLMResult", "SYSTEM_PROMPT", "make_client"]


class LLMError(Exception):
    """El LLM no dio una respuesta usable. El mensaje nunca lleva contenido del CV."""


@dataclass
class LLMResult:
    data: dict
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    provider: str
    model: str

    def extract(self, text: str) -> LLMResult: ...


def _parse(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "")
    except (TypeError, ValueError):
        raise LLMError("invalid_json") from None
    if not isinstance(data, dict):
        raise LLMError("invalid_json")
    return data


class _Base:
    provider = ""

    def __init__(self, model: str, timeout: int) -> None:
        self.model = model
        self.timeout = timeout
        self.sdk = None

    def _key(self) -> str:
        key = os.environ.get(KEY_VARS[self.provider])
        if not key:
            raise LLMError("missing_api_key")
        return key

    def extract(self, text: str) -> LLMResult:
        try:
            if self.sdk is None:
                self.sdk = self._make_sdk(self._key())
            return self._call(text)
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - cualquier error del SDK se reporta solo por su clase
            raise LLMError(type(exc).__name__) from None

    def _make_sdk(self, key: str):  # pragma: no cover - lo cubren las pruebas en vivo
        raise NotImplementedError

    def _call(self, text: str) -> LLMResult:  # pragma: no cover
        raise NotImplementedError


class AnthropicClient(_Base):
    provider = "anthropic"

    def _make_sdk(self, key: str):
        import anthropic

        return anthropic.Anthropic(api_key=key, timeout=float(self.timeout), max_retries=1)

    def _call(self, text: str) -> LLMResult:
        response = self.sdk.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            raise LLMError(response.stop_reason)
        raw = next((b.text for b in response.content if getattr(b, "type", "") == "text"), None)
        usage = response.usage
        cached = (getattr(usage, "cache_creation_input_tokens", 0) or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        return LLMResult(_parse(raw), usage.input_tokens + cached, usage.output_tokens)


class OpenAIClient(_Base):
    provider = "openai"

    def _make_sdk(self, key: str):
        import openai

        return openai.OpenAI(api_key=key, timeout=float(self.timeout), max_retries=1)

    def _call(self, text: str) -> LLMResult:
        response = self.sdk.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "cv_entries", "schema": RESPONSE_SCHEMA, "strict": True}},
        )
        choice = response.choices[0]
        if choice.finish_reason == "length" or getattr(choice.message, "refusal", None):
            raise LLMError("incomplete")
        return LLMResult(_parse(choice.message.content), response.usage.prompt_tokens, response.usage.completion_tokens)


class GeminiClient(_Base):
    provider = "gemini"

    def _make_sdk(self, key: str):
        from google import genai
        from google.genai import types

        return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=self.timeout * 1000, api_version="v1beta"))

    def _call(self, text: str) -> LLMResult:
        config = {
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "response_json_schema": RESPONSE_SCHEMA,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        response = self.sdk.models.generate_content(model=self.model, contents=text, config=config)
        usage = response.usage_metadata
        output = (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
        return LLMResult(_parse(response.text), usage.prompt_token_count or 0, output)


CLIENTS = {"anthropic": AnthropicClient, "openai": OpenAIClient, "gemini": GeminiClient}


def make_client(settings: Settings) -> LLMClient | None:
    if settings.llm_provider == "none":
        return None
    if not settings.llm_model:
        raise ValueError("CV_PARSER_LLM_MODEL es obligatorio cuando hay proveedor de LLM")
    return CLIENTS[settings.llm_provider](settings.llm_model, settings.llm_timeout)
