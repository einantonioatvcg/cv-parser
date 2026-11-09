"""Nivel de estudios a partir del texto de una entrada."""

from __future__ import annotations

import re
from dataclasses import dataclass

from cv_parser.lines import fold_map, normalize_text


@dataclass(frozen=True)
class LevelMatch:
    level: str
    is_technical: bool
    level_text: str
    area_text: str | None


# (nivel, técnico, patrón plegado). El orden desempata coincidencias en la misma posición.
_PATTERNS: list[tuple[str, bool, str]] = [
    ("doctorate", False, r"doctorado|doctorate|doctor|ph\.? ?d\.?"),
    ("master", False, r"maestria|master'?s?(?: degree)?|mba|m\.sc\.?|msc|magister"),
    ("university", True, r"tecnico superior universitario|tecnico superior|t\.?s\.?u\.?|associate'?s? degree|associate of"),
    ("university", False, r"licenciatura|licenciad[oa]|lic\.|ingenieria|ingenier[oa]|ing\.|bachelor'?s?(?: degree)?"
                          r"|b\.a\.|b\.s\.|bsc|b\.sc\.|carrera profesional|carrera universitaria"),
    ("high_school", True, r"bachillerato tecnologico|bachillerato tecnico|carrera tecnica|profesional tecnico"
                          r"|bachiller tecnico|bachiller bivalente|tecnico en|tecnica en|conalep|cbtis|cetis|cecyt|cbta|technical high school"),
    ("high_school", False, r"colegio de bachilleres|bachillerato|bachiller|preparatoria|prepa|high school|cobach"),
    ("middle_school", False, r"secundaria tecnica|secundaria|middle school|junior high"),
    ("elementary", False, r"primaria|elementary school|elementary|primary school"),
]
_COMPILED = [(level, tech, re.compile(rf"(?<![a-z])(?:{pattern})(?![a-z])")) for level, tech, pattern in _PATTERNS]
_SEGMENT_BREAK = re.compile(r"\s*(?:[,|;•·(]|\s[-–]\s)\s*")
_STATUS = r"(?:terminad[oa]|trunc[oa]|concluid[oa]|inconclus[oa]|en curso|cursando|pasante|titulad[oa]|o|y)"
_CONNECTOR = re.compile(r"^\s*(?:" + _STATUS + r"\s+)*(?:en el area de|en|in|of|de|del)\s+")
_AREA_CUT = re.compile(r"\s+(?:por|at|from|en la universidad|en el instituto|[-–])\s|\s*\d")


def detect_level(text: str) -> LevelMatch | None:
    """El grado termina en un punto seguido de minúscula: "Bachillerato comunitario. ciclo escolar"."""
    original = normalize_text(text)
    # Se corta en ". " seguido de minúscula, salvo tras una abreviatura corta ("Lic. en", "Ing. en").
    cuts = [m.end(1) for m in re.finditer(r"([^\W\d_]+)\.\s+(?=[a-záéíóúñü])", original) if len(m.group(1)) > 4]
    start = 0
    for end in cuts + [len(original)]:
        found = _detect(original[start:end])
        if found:
            return found
        start = end
    return None


def _detect(text: str) -> LevelMatch | None:
    original = normalize_text(text)
    folded, index = fold_map(original)
    best: tuple[int, int, str, bool, re.Match] | None = None
    for order, (level, tech, pattern) in enumerate(_COMPILED):
        m = pattern.search(folded)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), order, level, tech, m)
    if best is None:
        return None
    _, _, level, tech, m = best
    if level == "middle_school" and "tecnica" in m.group(0):
        tech = True

    # Segmento: el tramo entre separadores que contiene la coincidencia.
    seg_start, seg_end = 0, len(folded)
    for brk in _SEGMENT_BREAK.finditer(folded):
        if brk.end() <= m.start():
            seg_start = brk.end()
        elif brk.start() >= m.end():
            seg_end = brk.start()
            break
    level_text = original[index[seg_start]: index[seg_end - 1] + 1].strip()

    area = None
    rest = folded[m.end():seg_end]
    conn = _CONNECTOR.match(rest)
    abbreviation = m.group(0).rstrip().endswith(".") and re.match(r"^\s+\w", rest)
    if conn or abbreviation:
        area_start = m.end() + (conn.end() if conn else len(rest) - len(rest.lstrip()))
        cut = _AREA_CUT.search(folded, area_start, seg_end)
        area_end = cut.start() if cut else seg_end
        while area_end > area_start and not folded[area_end - 1].isalnum():
            area_end -= 1
        if area_end > area_start:
            area = original[index[area_start]: index[area_end - 1] + 1].strip() or None
    return LevelMatch(level=level, is_technical=tech, level_text=level_text, area_text=area)
