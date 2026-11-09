"""Rangos de fechas e idioma del texto."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from cv_parser.lines import fold, fold_map, normalize_text
from cv_parser.models import YearMonth
from cv_parser.vocab import CURRENT_WORDS, ENGLISH_WORDS, MONTHS, PERSONAL_PREFIXES, SPANISH_WORDS

MIN_YEAR = 1950
MAX_BARE_YEAR_WORDS = 4

_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))
_YEAR = r"(?:19|20)\d{2}"
_POINT = re.compile(
    rf"(?<![\w/.-])(?P<d>\d{{1,2}})[/.-](?P<dm>\d{{1,2}})[/.-](?P<dy>{_YEAR})(?![\w/])"
    rf"|(?<![\w/.-])(?P<m>\d{{1,2}})[/.-](?P<my>{_YEAR})(?![\w/])"
    rf"|(?:(?<![\w/.-])\d{{1,2}}(?:\s*[/.-]\s*|\s+(?:de\s+)?))?"
    rf"(?<![a-z])(?P<name>{_MONTH_ALT})\.?(?:[\s,./-]+(?:de|del|of)(?![a-z]))?[\s,./-]*(?P<ny>{_YEAR})(?!\d)"
    rf"|(?<![\w])(?P<y>{_YEAR})(?![\w])"
)
_CURRENT = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in sorted(CURRENT_WORDS, key=len, reverse=True)) + r")(?![a-z])")
# Datos personales e identificadores en cualquier parte de la línea: nunca dan fecha.
_PERSONAL = re.compile(
    r"(?<![a-z])(nacimiento|nac\.|naci|nacid[oa]|birth|birthday|birthdate|born|d\.?o\.?b\.?|edad|age|curp|rfc|nss|imss)(?![a-z])"
)
PERSONAL_RE = _PERSONAL
_LEADING_BULLET = re.compile(r"^[\s\-•·*▪●◦‣➢➤►✓✔→–—]+")
_MONTH_ONLY = re.compile(
    rf"(?:(?<![\w/.-])\d{{1,2}}(?:\s*[/.-]\s*|\s+de\s+))?(?<![a-z])(?P<mo>{_MONTH_ALT})\.?\s*(?:-+|a|al|to|hasta)\s*$"
)
_SEPARATOR = re.compile(r"^[\s]*(?:-+|/|a|al|to|hasta|until|till|>)?[\s]*$")


@dataclass(frozen=True)
class DateRange:
    start: YearMonth | None
    end: YearMonth | None
    is_current: bool


@dataclass
class _Point:
    begin: int
    end: int
    year: int
    month: int | None
    full: bool      # fecha completa dd/mm/aaaa
    bare: bool      # año suelto


def _points(text: str) -> list[_Point]:
    points: list[_Point] = []
    for m in _POINT.finditer(text):
        if m.group("dy"):
            a, b = int(m.group("d")), int(m.group("dm"))
            if a > 12 and 1 <= b <= 12:
                month: int | None = b
            elif b > 12 and 1 <= a <= 12:
                month = a
            elif 1 <= a <= 12 and 1 <= b <= 12:
                month = b  # ambiguo: en CVs en español la convención es día/mes
            else:
                continue
            points.append(_Point(m.start(), m.end(), int(m.group("dy")), month, True, False))
        elif m.group("my"):
            month = int(m.group("m"))
            if not 1 <= month <= 12:
                continue
            points.append(_Point(m.start(), m.end(), int(m.group("my")), month, False, False))
        elif m.group("ny"):
            points.append(_Point(m.start(), m.end(), int(m.group("ny")), MONTHS[m.group("name")], False, False))
        else:
            points.append(_Point(m.start(), m.end(), int(m.group("y")), None, False, True))
    return points


def _valid(p: _Point, today: date) -> bool:
    return MIN_YEAR <= p.year <= today.year + 1


def _key(p: _Point) -> tuple[int, int]:
    return (p.year, p.month or 0)


def _ym(p: _Point) -> YearMonth:
    return YearMonth(year=p.year, month=p.month)


def find_date_range(text: str, today: date | None = None) -> DateRange | None:
    found = find_date_span(text, today)
    return found[0] if found else None


def find_date_span(text: str, today: date | None = None) -> tuple[DateRange, int, int] | None:
    """Como `find_date_range`, más el tramo [inicio, fin) de la fecha dentro de `normalize_text(text)`."""
    original = normalize_text(text)
    folded, index = fold_map(original)
    found = _find(folded, today or date.today())
    if found is None:
        return None
    rng, begin, end = found
    return rng, index[begin], index[end - 1] + 1


def _find(folded: str, today: date) -> tuple[DateRange, int, int] | None:
    head = _LEADING_BULLET.sub("", folded)
    if not head or any(head.startswith(prefix) for prefix in PERSONAL_PREFIXES) or _PERSONAL.search(folded):
        return None
    points = _points(folded)
    currents = list(_CURRENT.finditer(folded))

    # "julio al 16 de octubre de 2020" y "agosto-diciembre 2015": el año escrito al final vale para ambos meses.
    if points and points[0].month is not None:
        point = points[0]
        m = _MONTH_ONLY.search(folded[:point.begin])
        if m:
            month = MONTHS[m.group("mo")]
            year = point.year if month <= point.month else point.year - 1
            start_point = _Point(m.start(), m.end(), year, month, False, False)
            if not (_valid(start_point, today) and _valid(point, today)):
                return None
            return DateRange(_ym(start_point), _ym(point), False), m.start(), point.end

    # Rango: un punto seguido, solo con separadores en medio, de otro punto o de una palabra de "actual".
    for i, start in enumerate(points):
        following = points[i + 1] if i + 1 < len(points) else None
        if following and _SEPARATOR.match(folded[start.end:following.begin]):
            if not (_valid(start, today) and _valid(following, today)) or _key(start) > _key(following):
                return None
            return DateRange(_ym(start), _ym(following), False), start.begin, following.end
        current = next((c for c in currents if c.start() >= start.end), None)
        if current and _SEPARATOR.match(folded[start.end:current.start()]):
            if not _valid(start, today) or (start.year, start.month or 1) > (today.year, today.month):
                return None
            return DateRange(_ym(start), None, True), start.begin, current.end()

    # Fecha suelta.
    singles = [p for p in points if not p.full]
    if len(singles) != 1:
        return None
    point = singles[0]
    if not _valid(point, today):
        return None
    if point.bare and (len(folded.split()) > MAX_BARE_YEAR_WORDS or "#" in folded):
        return None
    return DateRange(_ym(point), None, False), point.begin, point.end


Language = Literal["es", "en", "mixed"]


def detect_language(text: str) -> Language:
    words = re.findall(r"[a-z]+", fold(text))
    es = sum(1 for w in words if w in SPANISH_WORDS)
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    total = es + en
    if total == 0:
        return "es"
    if min(es, en) / total > 0.25:
        return "mixed"
    return "es" if es >= en else "en"
