"""Lectura de PDF con reconstrucción del orden de lectura por columnas."""

from __future__ import annotations

import io
import logging

import pdfplumber

from cv_parser.errors import CorruptFile
from cv_parser.lines import DocumentText, Line, normalize_text

for _name in ("pdfminer", "pdfplumber"):
    logging.getLogger(_name).setLevel(logging.WARNING)

MAX_PAGES = 20
ROW_TOLERANCE = 3.0      # pt de diferencia en `top` para considerar la misma línea
STRIP = 12.0             # ancho mínimo del canal entre columnas, en pt
MIN_COVERAGE = 0.6       # fracción de la altura con texto que debe cubrir el canal
MIN_ROWS_PER_SIDE = 3
MAX_PAIRED_ROWS = 0.6     # fracción de renglones de la derecha alineados con uno de la izquierda


def extract_pdf(data: bytes) -> DocumentText:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = len(pdf.pages)
            lines: list[Line] = []
            columns = 1
            for number, page in enumerate(pdf.pages[:MAX_PAGES], start=1):
                words = page.extract_words(extra_attrs=["size", "fontname"])
                page_lines, page_columns = _page_lines(words, float(page.width), number)
                lines.extend(page_lines)
                columns = max(columns, page_columns)
    except CorruptFile:
        raise
    except Exception as exc:  # pdfminer lanza varios tipos para archivos dañados o cifrados
        raise CorruptFile(type(exc).__name__) from None
    return DocumentText(lines=lines, pages=pages, columns=columns)


def _page_lines(words: list[dict], width: float, page: int) -> tuple[list[Line], int]:
    words = [w for w in words if w["text"].strip()]
    if not words:
        return [], 1
    gutter = _find_gutter(words, width)
    if gutter is None:
        return _to_lines(words, page), 1
    x, region_top, region_bottom = gutter
    above, left, right, below = [], [], [], []
    for w in words:
        middle = (w["top"] + w["bottom"]) / 2
        if middle < region_top:
            above.append(w)
        elif middle > region_bottom:
            below.append(w)
        elif w["x1"] <= x + STRIP / 2:
            left.append(w)
        else:
            right.append(w)
    lines: list[Line] = []
    for segment in (above, left, right, below):
        lines.extend(_to_lines(segment, page))
    return lines, 2


def _rows(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(w["top"] - rows[-1][0]["top"]) <= ROW_TOLERANCE:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in rows]


def _find_gutter(words: list[dict], width: float) -> tuple[float, float, float] | None:
    """Busca un canal vertical sin palabras entre el 25 y el 75 % del ancho."""
    top = min(w["top"] for w in words)
    bottom = max(w["bottom"] for w in words)
    height = bottom - top
    if height <= 0:
        return None
    best: tuple[float, float, float] | None = None
    x = width * 0.25
    while x + STRIP <= width * 0.75:
        blocking = sorted((w["top"], w["bottom"]) for w in words if w["x0"] < x + STRIP and w["x1"] > x)
        free: list[tuple[float, float]] = []
        cursor = top
        for t, b in blocking:
            if t > cursor:
                free.append((cursor, t))
            cursor = max(cursor, b)
        if bottom > cursor:
            free.append((cursor, bottom))
        for a, b in free:
            if b - a < MIN_COVERAGE * height or (best and b - a <= best[2] - best[1]):
                continue
            inside = [w for w in words if w["top"] >= a and w["bottom"] <= b]
            left_rows = _rows([w for w in inside if w["x1"] <= x])
            right_rows = _rows([w for w in inside if w["x0"] >= x + STRIP])
            if (len(left_rows) >= MIN_ROWS_PER_SIDE and len(right_rows) >= MIN_ROWS_PER_SIDE
                    and _aligned(right_rows) and not _same_rows(left_rows, right_rows)):
                best = (x, a, b)
        x += 2
    return best


def _aligned(rows: list[list[dict]]) -> bool:
    """Una columna real tiene la mayoría de sus renglones alineados al mismo margen izquierdo."""
    starts = [r[0]["x0"] for r in rows]
    margin = min(starts)
    return sum(1 for s in starts if s - margin <= 6) >= len(starts) / 2


def _same_rows(left: list[list[dict]], right: list[list[dict]]) -> bool:
    """Texto alineado a la derecha en el mismo renglón (fechas, ciudades) es una sola columna."""
    tops = [r[0]["top"] for r in left]
    paired = sum(1 for r in right if any(abs(r[0]["top"] - t) <= ROW_TOLERANCE for t in tops))
    return paired >= MAX_PAIRED_ROWS * len(right)


def _to_lines(words: list[dict], page: int) -> list[Line]:
    lines: list[Line] = []
    prev: tuple[float, float] | None = None
    for row in _rows(words):
        parts = [row[0]["text"]]
        for before, w in zip(row, row[1:]):
            parts.append(("" if w["x0"] - before["x1"] < 0.5 else " ") + w["text"])
        text = normalize_text("".join(parts))
        if not text:
            continue
        row_top = min(w["top"] for w in row)
        row_bottom = max(w["bottom"] for w in row)
        chars = sum(len(w["text"]) for w in row)
        bold_chars = sum(len(w["text"]) for w in row if "bold" in str(w.get("fontname", "")).lower())
        gap = True if prev is None else (row_top - prev[1]) > 1.5 * (prev[1] - prev[0])
        lines.append(Line(text=text, page=page, size=round(max(float(w.get("size", 0)) for w in row), 1),
                          bold=bold_chars * 2 > chars, gap_before=gap))
        prev = (row_top, row_bottom)
    return lines
