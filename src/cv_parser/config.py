"""Configuración del servicio, leída de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


LLM_PROVIDERS = ("none", "anthropic", "openai", "gemini")
LLM_MODES = ("low_confidence", "always")


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str] = field(default_factory=list)
    max_bytes: int = 10_485_760
    api_key: str | None = None
    convert_timeout: int = 60
    llm_provider: str = "none"
    llm_model: str | None = None
    llm_timeout: int = 30
    llm_mode: str = "low_confidence"
    llm_threshold: float = 0.75

    @classmethod
    def from_env(cls) -> "Settings":
        origins = [o.strip() for o in os.environ.get("CV_PARSER_CORS_ORIGINS", "").split(",") if o.strip()]
        provider = (os.environ.get("CV_PARSER_LLM_PROVIDER") or "none").strip().lower()
        if provider not in LLM_PROVIDERS:
            raise ValueError(f"CV_PARSER_LLM_PROVIDER inválido: {provider}")
        mode = (os.environ.get("CV_PARSER_LLM_MODE") or "low_confidence").strip().lower()
        if mode not in LLM_MODES:
            raise ValueError(f"CV_PARSER_LLM_MODE inválido: {mode}")
        return cls(
            cors_origins=origins,
            max_bytes=int(os.environ.get("CV_PARSER_MAX_BYTES") or 10_485_760),
            api_key=os.environ.get("CV_PARSER_API_KEY") or None,
            convert_timeout=int(os.environ.get("CV_PARSER_CONVERT_TIMEOUT") or 60),
            llm_provider=provider,
            llm_model=os.environ.get("CV_PARSER_LLM_MODEL") or None,
            llm_timeout=int(os.environ.get("CV_PARSER_LLM_TIMEOUT") or 30),
            llm_mode=mode,
            llm_threshold=float(os.environ.get("CV_PARSER_LLM_THRESHOLD") or 0.75),
        )
