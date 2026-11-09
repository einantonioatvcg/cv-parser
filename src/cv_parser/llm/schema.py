"""Esquema JSON que se pide a cualquier proveedor: la forma de `extracted.education` y `.experience` sin confianza."""

from __future__ import annotations

LEVELS = ["elementary", "middle_school", "high_school", "university", "master", "doctorate"]


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


# Los textos sin dato van como cadena vacía: Anthropic admite pocas uniones por esquema (16).
TEXT = {"type": "string"}


_YEAR_MONTH = {
    "type": ["object", "null"],
    "properties": {"year": {"type": "integer"}, "month": _nullable("integer")},
    "required": ["year", "month"],
    "additionalProperties": False,
}


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


EDUCATION = _object({
    "level": {"anyOf": [{"type": "string", "enum": LEVELS}, {"type": "null"}]},
    "level_text": TEXT,
    "is_technical": {"type": "boolean"},
    "area_text": TEXT,
    "institution": TEXT,
    "city": TEXT,
    "country_code": TEXT,
    "start": _YEAR_MONTH,
    "end": _YEAR_MONTH,
    "is_current": {"type": "boolean"},
})

EXPERIENCE = _object({
    "position": TEXT,
    "company": TEXT,
    "city": TEXT,
    "country_code": TEXT,
    "start": _YEAR_MONTH,
    "end": _YEAR_MONTH,
    "is_current": {"type": "boolean"},
    "description": TEXT,
})

RESPONSE_SCHEMA = _object({
    "name": TEXT,
    "headline": TEXT,
    "summary": TEXT,
    "education": {"type": "array", "items": EDUCATION},
    "experience": {"type": "array", "items": EXPERIENCE},
})
