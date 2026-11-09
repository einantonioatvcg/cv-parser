"""Líneas de texto con formato, comunes a todos los formatos de entrada."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

_INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"), None)


@dataclass(frozen=True)
class Line:
    text: str
    page: int = 1
    size: float = 0.0
    bold: bool = False
    gap_before: bool = False


@dataclass
class DocumentText:
    lines: list[Line] = field(default_factory=list)
    pages: int | None = None
    columns: int = 1


def normalize_text(text: str) -> str:
    """Unifica ligaduras, espacios duros, acentos separados e invisibles; colapsa espacios."""
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    return " ".join(text.split())


_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")


def fold(text: str) -> str:
    """Texto para comparar: normalizado, en minúsculas, sin acentos y con guiones simples."""
    text = unicodedata.normalize("NFD", normalize_text(text).translate(_DASHES).lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def fold_map(text: str) -> tuple[str, list[int]]:
    """Como `fold` pero carácter por carácter y sin colapsar espacios; devuelve el índice original de cada uno."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        decomposed = unicodedata.normalize("NFD", ch.translate(_DASHES).lower())
        for c in decomposed:
            if unicodedata.category(c) != "Mn":
                out.append(c)
                index.append(i)
    return "".join(out), index


CONNECTOR_END = re.compile(r"(?:\s(?:de|del|la|las|los|el|y|e|en|a|al|para|por|con|of|and|the|in|for|to)|,)$", re.I)


_LONG_MONTHS = {
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre", "octubre",
    "noviembre", "diciembre", "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
}
CONNECTOR_START = re.compile(r"^(?:de|del|y|en|para|por|con)\s", re.I)


def join_wrapped(lines: list[Line], is_bullet: Callable[[str], bool] = lambda _: False,
                 has_date: Callable[[str], bool] | None = None) -> list[Line]:
    """Une un renglón partido por el ancho de página: termina en conector, coma o paréntesis abierto,
    o el siguiente empieza con conector ("DE EMPRESAS TURÍSTICAS") y no es una fecha."""
    out: list[Line] = []
    for line in lines:
        if out and not line.gap_before and not is_bullet(line.text):
            prev = out[-1].text
            starts = has_date is not None and CONNECTOR_START.match(line.text) and not has_date(line.text)
            # Fecha partida: "MAYO 2017-" + "ABRIL 2019", o "DE MARZO" + "2013 – JUNIO 2014".
            dash_end = prev.rstrip().endswith(("-", "–", "—"))
            prev_words = fold(prev).split()
            month_then_year = (bool(prev_words) and prev_words[-1].strip(".") in _LONG_MONTHS
                               and re.match(r"^(19|20)\d{2}\b", line.text.strip()) is not None)
            if CONNECTOR_END.search(prev) or prev.count("(") > prev.count(")") or starts or dash_end or month_then_year:
                last = out[-1]
                out[-1] = Line(text=f"{prev} {line.text}", page=last.page, size=last.size, bold=last.bold,
                               gap_before=last.gap_before)
                continue
        out.append(line)
    return out
