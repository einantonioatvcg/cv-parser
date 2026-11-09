"""División del CV en secciones con un diccionario único de encabezados en español e inglés."""

from __future__ import annotations

import re
from difflib import get_close_matches
from dataclasses import dataclass, field
from datetime import date

from cv_parser.dates import find_date_range
from cv_parser.lines import Line, fold
from cv_parser.vocab import HEADINGS

MAX_HEADING_WORDS = 5
MAX_COMPOUND_WORDS = 7
SECTION_KEYS = ("summary", "experience", "education", "skills", "languages", "certifications", "projects",
                "personal", "references", "other")
ENTRY_SECTIONS = {"experience", "education"}
CONNECTORS = {"y", "and", "e", "/", "&", "-"}
LOOKAHEAD = 3

_COMPACT = {key.replace(" ", ""): section for key, section in HEADINGS.items()}
# Señales de que una línea es parte de una entrada, no un encabezado desconocido.
_ENTRY_SIGNAL = re.compile(
    r"(?<![a-z])(s\.? ?a\.?|inc|llc|grupo|hospital|clinica|universidad|university|instituto|colegio|escuela|"
    r"preparatoria|licenciatura|ingenieria|bachillerato|maestria|bachelor|master)(?![a-z])"
)


@dataclass
class Sections:
    header: list[Line] = field(default_factory=list)
    parts: dict[str, list[Line]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    found_any: bool = False


def _clean(text: str) -> str:
    return re.sub(r"^[\W\d_]+|[\W_]+$", "", fold(text))  # viñetas, numeración, dos puntos


def heading_key(text: str) -> str | None:
    """Devuelve la sección si la línea completa es un encabezado conocido."""
    folded = _clean(text)
    tokens = folded.replace("&", " and ").split()
    letter_spaced = len(tokens) > 2 and all(len(t) == 1 for t in tokens)  # E X P E R I E N C I A
    if not tokens or (len(tokens) > MAX_HEADING_WORDS and not letter_spaced):
        return None
    for variant in (tokens, folded.replace("&", " y ").split()):
        key = _COMPACT.get(re.sub(r"[^a-z]", "", "".join(variant)))
        if key:
            return key
    compact = re.sub(r"[^a-z]", "", "".join(tokens))
    if len(compact) >= 8 and _is_caps(text):
        # "EXPERIENCIA PROFECIONAL", "EXPREIENCIA": errores de dedo en encabezados en mayúsculas.
        close = get_close_matches(compact, list(_COMPACT), n=1, cutoff=0.88)
        if close:
            return _COMPACT[close[0]]
    return None


def compound_heading_key(text: str) -> str | None:
    """Encabezado conocido seguido de un conector: "Formación académica y complementaria", "Educación / Education"."""
    tokens = re.sub(r"([/&])", r" \1 ", _clean(text)).split()
    if not 2 < len(tokens) <= MAX_COMPOUND_WORDS:
        return None
    for cut in range(len(tokens) - 1, 0, -1):
        if tokens[cut] in CONNECTORS:
            key = _COMPACT.get(re.sub(r"[^a-z]", "", "".join(tokens[:cut])))
            if key:
                return key
    return None


def _is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def _body_size(lines: list[Line]) -> float:
    sizes = sorted(l.size for l in lines if l.size > 0)
    return sizes[len(sizes) // 2] if sizes else 0.0


def _looks_like_heading(line: Line, body: float = 0.0) -> bool:
    bigger = body > 0 and line.size >= body + 1.5
    return _is_caps(line.text) or line.bold or bigger


def _starts_with_symbol(text: str) -> bool:
    return bool(re.match(r"^\s*[^\w\s(¿¡\"']", text))


INLINE_KEYS = {"summary", "skills", "languages"}


def _inline_heading(line: Line) -> tuple[str, Line] | None:
    """"Objetivo: texto" en un solo renglón: encabezado con su contenido."""
    m = re.match(r"^\s*([^:]{3,40}):\s*(\S.*)$", line.text)
    if not m or len(m.group(1).split()) > 4:
        return None
    key = heading_key(m.group(1))
    if key is None or (key not in INLINE_KEYS and not _is_caps(m.group(1))):
        return None
    return key, Line(text=m.group(2), page=line.page, size=line.size, bold=line.bold)


def _date_ahead(lines: list[Line], i: int) -> bool:
    return any(find_date_range(l.text, date.today()) for l in lines[i + 1:i + 1 + LOOKAHEAD])


def _unknown_heading(lines: list[Line], i: int, body: float = 0.0) -> bool:
    """Línea con forma de encabezado que no está en el diccionario: abre una sección "other"."""
    line = lines[i]
    words = line.text.split()
    if not (2 <= len(words) <= MAX_HEADING_WORDS) or re.search(r"\d|@", line.text):
        return False
    if not (line.gap_before and _looks_like_heading(line, body)) or _ENTRY_SIGNAL.search(fold(line.text)):
        return False
    return not _date_ahead(lines, i)


def split_sections(lines: list[Line]) -> Sections:
    result = Sections()
    current: list[Line] = result.header
    current_key: str | None = None
    body = _body_size(lines)
    for i, line in enumerate(lines):
        symbol = _starts_with_symbol(line.text)
        key = heading_key(line.text) if not symbol or _is_caps(line.text) else None
        if key is None and not symbol:
            key = compound_heading_key(line.text)
        content: Line | None = None
        if key is None and not symbol:
            inline = _inline_heading(line)
            if inline:
                key, content = inline
        if key and content is None and current_key in ENTRY_SECTIONS and not _looks_like_heading(line, body):
            # Dentro de empleos o estudios, "Capacitación" seguido de fechas es un puesto, no una sección.
            if not line.gap_before or _date_ahead(lines, i):
                key = None
        if key is None and current_key is not None and _unknown_heading(lines, i, body):
            key = "other"
        if key is None:
            current.append(line)
            continue
        result.found_any = True
        if key not in result.parts:
            result.parts[key] = []
            result.order.append(key)
        current = result.parts[key]
        current_key = key
        if content is not None:
            current.append(content)
    return result
