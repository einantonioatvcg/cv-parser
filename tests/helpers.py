"""Utilidades compartidas por los tests."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def to_lines(text: str):
    """Una línea por renglón; un renglón en blanco activa `gap_before` en la siguiente."""
    from cv_parser.lines import Line

    lines = []
    gap = False
    for raw in text.split("\n"):
        if not raw.strip():
            gap = True
            continue
        lines.append(Line(text=raw.strip(), gap_before=gap))
        gap = False
    return lines


def load_json(name: str):
    import json

    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def sin_confianza(value):
    if isinstance(value, dict):
        return {k: sin_confianza(v) for k, v in value.items() if k != "confidence"}
    if isinstance(value, list):
        return [sin_confianza(v) for v in value]
    return value


def codigos(result) -> list[str]:
    return [w.code for w in result.warnings]
