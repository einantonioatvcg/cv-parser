"""Valida lo que devuelve el LLM contra el texto del CV: lo que no está escrito o no tiene forma válida se vacía."""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from cv_parser.dates import MIN_YEAR
from cv_parser.levels import detect_level
from cv_parser.vocab import CURRENT_WORDS, MONTHS
from cv_parser.lines import fold, fold_map
from cv_parser.llm.schema import LEVELS
from cv_parser.models import Education, Experience, ParseWarning, YearMonth
from cv_parser.places import COUNTRIES

COUNTRY_CODES = {code for code, _ in COUNTRIES.values()}
FUZZY = 0.9


_MARKS = re.compile(r"\[(correo|telefono|curp|rfc|nss|dato)\]", re.I)
_TOKEN = re.compile(r"[a-z0-9ñ]+")


def _norm(text: str) -> list[str]:
    return _TOKEN.findall(fold(text))


def _close(a: str, b: str) -> bool:
    """Dos palabras equivalen si son iguales; solo en palabras largas se tolera una errata. Números, siempre exactos."""
    if a == b:
        return True
    if a.isdigit() or b.isdigit() or min(len(a), len(b)) < 6:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.83


class _Source:
    def __init__(self, text: str) -> None:
        self.text = text
        folded, index = fold_map(text)
        self.tokens: list[str] = []
        self.spans: list[tuple[int, int]] = []
        for m in _TOKEN.finditer(folded):
            self.tokens.append(m.group(0))
            self.spans.append((index[m.start()], index[m.end() - 1] + 1))
        self.token_set = set(self.tokens)
        joined = " " + " ".join(fold(text).split()) + " "
        self.has_current = any(f" {w} " in joined or f" {w}" in joined for w in CURRENT_WORDS)

    def find(self, value: str, fuzzy: bool = True) -> str | None:
        """Devuelve el tramo del CV que corresponde al valor, con el texto del CV; None si no está escrito."""
        words = _norm(value)
        n = len(words)
        if not n or _MARKS.search(value):
            return None
        for i in range(len(self.tokens) - n + 1):
            window = self.tokens[i:i + n]
            if window == words or (fuzzy and all(_close(a, b) for a, b in zip(window, words))):
                start, end = self.spans[i][0], self.spans[i + n - 1][1]
                while end < len(self.text) and self.text[end] in ".)!?":
                    end += 1   # "S.A. de C.V." y el punto final de una oración son parte del texto
                return " ".join(self.text[start:end].split())
        return None

    def contains(self, value: str) -> bool:
        return self.find(value) is not None

    def has_year(self, year: int) -> bool:
        return str(year) in self.token_set or any(t.endswith(str(year)) and t[:-4].isdigit() for t in self.tokens)

    def has_month(self, month: int) -> bool:
        names = {k for k, v in MONTHS.items() if v == month}
        return bool(names & self.token_set) or f"{month:02d}" in self.token_set or str(month) in self.token_set


def _text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _ym(value, today: date) -> YearMonth | None:
    if not isinstance(value, dict):
        return None
    year, month = value.get("year"), value.get("month")
    if not isinstance(year, int) or isinstance(year, bool) or not MIN_YEAR <= year <= today.year + 1:
        return None
    if month is not None and (not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12):
        return None
    return YearMonth(year=year, month=month)


def _in_source(value: YearMonth | None, source: "_Source") -> tuple[YearMonth | None, bool]:
    """El año debe estar escrito en el CV; el mes también, o se vacía."""
    if value is None:
        return None, False
    if not source.has_year(value.year):
        return None, True
    if value.month is not None and not source.has_month(value.month):
        return YearMonth(year=value.year, month=None), True
    return value, False


def _dates(raw: dict, today: date, source: "_Source") -> tuple[YearMonth | None, YearMonth | None, bool, bool]:
    """Devuelve inicio, fin, actual y si algo se descartó."""
    start, end = _ym(raw.get("start"), today), _ym(raw.get("end"), today)
    rejected = (raw.get("start") is not None and start is None) or (raw.get("end") is not None and end is None)
    start, bad_s = _in_source(start, source)
    end, bad_e = _in_source(end, source)
    rejected = rejected or bad_s or bad_e
    current = raw.get("is_current") is True and source.has_current
    rejected = rejected or (raw.get("is_current") is True and not current)
    if current:
        end = None
    if start and end and (start.year, start.month or 0) > (end.year, end.month or 12):
        start, end, rejected = None, None, True
    if start and (start.year, start.month or 1) > (today.year, today.month):
        start, rejected = None, True
    return start, end, current, rejected


def _checked(raw: dict, field: str, source: _Source, fuzzy: bool = True) -> tuple[str | None, bool]:
    """Valor tal como está escrito en el CV, o None si el CV no lo dice."""
    value = _text(raw.get(field))
    if field == "city" and value and "," in value:
        value = value.split(",")[0].strip() or None   # "Zapopan, Jalisco": la ciudad sin el estado
    if value is None:
        return None, raw.get(field) not in (None, "")
    found = source.find(value, fuzzy=fuzzy)
    return (found, False) if found else (None, True)


def _description(value, source: "_Source") -> tuple[str | None, bool]:
    """Solo se conservan los renglones de la descripción que están en el CV."""
    text = _text(value)
    if text is None:
        return None, False
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    kept = [found for found in (source.find(l) for l in lines) if found]
    return ("\n".join(kept) or None), len(kept) != len(lines)


def validate_response(raw: dict, source_text: str, today: date | None = None
                      ) -> tuple[list[Education], list[Experience], list[ParseWarning]]:
    today = today or date.today()
    source = _Source(source_text)
    warnings: list[ParseWarning] = []
    education: list[Education] = []
    experience: list[Experience] = []

    for index, item in enumerate(raw.get("experience") or []):
        item = item if isinstance(item, dict) else {}
        position, bad_p = _checked(item, "position", source)
        company, bad_c = _checked(item, "company", source)
        city, bad_city = _checked(item, "city", source)
        start, end, current, bad_d = _dates(item, today, source)
        country = _text(item.get("country_code"))
        bad_country = country is not None and country.upper() not in COUNTRY_CODES
        country = country.upper() if country and not bad_country else None
        description, bad_desc = _description(item.get("description"), source)
        bad_d = bad_d or bad_desc
        if not (position or company):
            warnings.append(ParseWarning(code="llm_rejected", section="experience", index=index))
            continue
        if bad_p or bad_c or bad_city or bad_d or bad_country:
            warnings.append(ParseWarning(code="llm_rejected", section="experience", index=index))
        confidence = (0.4 if start else 0.0) + (0.3 if position else 0.0) + (0.3 if company else 0.0)
        experience.append(Experience(
            position=position, company=company, city=city, country_code=country, start=start, end=end,
            is_current=current, description=description, confidence=round(confidence, 2),
        ))

    for index, item in enumerate(raw.get("education") or []):
        item = item if isinstance(item, dict) else {}
        level_text, bad_lt = _checked(item, "level_text", source)
        area, bad_a = _checked(item, "area_text", source)
        institution, bad_i = _checked(item, "institution", source)
        city, bad_city = _checked(item, "city", source)
        start, end, current, bad_d = _dates(item, today, source)
        level = item.get("level") if item.get("level") in LEVELS else None
        bad_level = item.get("level") is not None and level is None
        detected = detect_level(level_text) if level_text else None
        if level and detected and detected.level != level:
            level, bad_level = None, True   # el nivel contradice el nombre del grado
        country = _text(item.get("country_code"))
        bad_country = country is not None and country.upper() not in COUNTRY_CODES
        country = country.upper() if country and not bad_country else None
        if not (level_text or institution):
            warnings.append(ParseWarning(code="llm_rejected", section="education", index=index))
            continue
        if bad_lt or bad_a or bad_i or bad_city or bad_d or bad_level or bad_country:
            warnings.append(ParseWarning(code="llm_rejected", section="education", index=index))
        confidence = (0.4 if (start or end) else 0.0) + (0.3 if level else 0.0) + (0.3 if institution else 0.0)
        education.append(Education(
            level=level, level_text=level_text, is_technical=item.get("is_technical") is True, area_text=area,
            institution=institution, city=city, country_code=country, start=start, end=end, is_current=current,
            confidence=round(confidence, 2),
        ))
    return education, experience, warnings


HEADER_SECTIONS = {"name": "contact", "headline": "headline", "summary": "summary"}
MIN_SUMMARY_WORDS = 4


def _valid_name(value: str | None) -> bool:
    from cv_parser.entries import COMPANY
    from cv_parser.header import looks_like_name

    return bool(value) and looks_like_name(value) and not COMPANY.search(fold(value))


def _valid_headline(value: str | None) -> bool:
    from cv_parser.header import FIELD_LABEL, is_contact_line
    from cv_parser.sections import compound_heading_key, heading_key

    return bool(value) and not (heading_key(value) or compound_heading_key(value) or is_contact_line(value)
                                or FIELD_LABEL.match(value))


def validate_header(raw: dict, source_text: str, summary_text: str | None = None
                    ) -> tuple[dict[str, str | None], list[ParseWarning]]:
    """Nombre, título y resumen tal como están escritos en el CV. Del resumen solo quedan oraciones completas que
    están en la sección de perfil (o en el CV, si no la hay)."""
    source = _Source(source_text)
    out: dict[str, str | None] = {}
    warnings: list[ParseWarning] = []
    name, bad = _checked(raw, "name", source, fuzzy=False)
    if name and not _valid_name(name):
        name, bad = None, True
    out["name"] = name
    if bad:
        warnings.append(ParseWarning(code="llm_rejected", section="contact"))
    headline, bad = _checked(raw, "headline", source)
    if headline and not _valid_headline(headline):
        headline, bad = None, True
    out["headline"] = headline
    if bad:
        warnings.append(ParseWarning(code="llm_rejected", section="headline"))
    summary = _text(raw.get("summary"))
    if summary is None:
        out["summary"] = None
    else:
        summary_source = _Source(summary_text) if summary_text else source
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", summary) if s.strip()]
        kept = [found for found in (summary_source.find(s) for s in sentences if len(_norm(s)) >= MIN_SUMMARY_WORDS)
                if found]
        out["summary"] = " ".join(kept) or None
        if len(kept) != len(sentences):
            warnings.append(ParseWarning(code="llm_rejected", section="summary"))
    return out, warnings
