"""Modelos del contrato /v1. Agregar campos es compatible; quitarlos o cambiar su sentido exige /v2."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["elementary", "middle_school", "high_school", "university", "master", "doctorate"]


class YearMonth(BaseModel):
    year: int
    month: int | None = None


class Contact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class Education(BaseModel):
    level: Level | None = None
    level_text: str | None = None
    is_technical: bool = False
    area_text: str | None = None
    institution: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, description="ISO 3166-1 alfa-2")
    start: YearMonth | None = None
    end: YearMonth | None = None
    is_current: bool = False
    confidence: float = 0.0


class Experience(BaseModel):
    position: str | None = None
    company: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, description="ISO 3166-1 alfa-2")
    start: YearMonth | None = None
    end: YearMonth | None = None
    is_current: bool = False
    description: str | None = None
    confidence: float = 0.0


class Extracted(BaseModel):
    contact: Contact = Field(default_factory=Contact)
    headline: str | None = None
    summary: str | None = None
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)


class ParseWarning(BaseModel):
    code: str = Field(description="scanned_pdf, empty_document, no_sections, llm_unavailable, llm_rejected; pueden agregarse otros")
    section: str | None = None
    index: int | None = None


class Meta(BaseModel):
    format: Literal["pdf", "docx", "doc"]
    language: Literal["es", "en", "mixed"]
    pages: int | None = None
    columns: int = 1
    sections: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    parser_version: str
    extraction: dict[str, str] = Field(
        default_factory=lambda: {"experience": "rules", "education": "rules", "contact": "rules",
                                 "headline": "rules", "summary": "rules"},
        description="Cómo se obtuvo cada parte: rules (reglas) o llm. Correo y teléfono siempre salen de las reglas.",
    )


class Confidence(BaseModel):
    summary: float = 0.0
    education: float = 0.0
    experience: float = 0.0
    overall: float = 0.0


class ParseResult(BaseModel):
    status: Literal["ok", "partial", "unreadable"]
    meta: Meta
    warnings: list[ParseWarning] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    extracted: Extracted = Field(default_factory=Extracted)
