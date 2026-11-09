"""Lectura de .docx: encabezados de página, párrafos, tablas y cuadros de texto en orden."""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass

from lxml import etree

from cv_parser.errors import CorruptFile
from cv_parser.lines import DocumentText, Line, normalize_text

MAX_UNCOMPRESSED = 100 * 1024 * 1024

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


P, TBL, TR, TC, SDT, SDT_CONTENT = w("p"), w("tbl"), w("tr"), w("tc"), w("sdt"), w("sdtContent")
RUN, T, TAB, BR, CR, TXBX = w("r"), w("t"), w("tab"), w("br"), w("cr"), w("txbxContent")
SKIP = {f"{{{MC}}}Fallback", w("del"), w("instrText"), w("delText"), w("pPr"), w("rPr"), w("sectPr")}
FALSE_VALUES = {"0", "false", "off"}

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True)


@dataclass
class _State:
    lines: list[Line]
    styles: dict[str, tuple[bool | None, float | None]]
    gap: bool = True


def extract_docx(data: bytes) -> DocumentText:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
                raise CorruptFile("too_large")
            body = _xml(z, "word/document.xml")
            styles = _styles(z)
            headers = [_xml(z, name) for name in _header_parts(z, body)]
    except CorruptFile:
        raise
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError, ValueError, OSError, EOFError) as exc:
        raise CorruptFile(type(exc).__name__) from None

    state = _State(lines=[], styles=styles)
    for header in headers:
        _walk(header, state)
    header_count = len(state.lines)
    seen: set[str] = set()
    unique: list[Line] = []
    for line in state.lines:  # varias partes de encabezado suelen repetir el mismo texto
        if line.text not in seen:
            seen.add(line.text)
            unique.append(line)
    state.lines = unique if header_count else []
    state.gap = True
    body_el = body.find(w("body"))
    if body_el is not None:
        _walk(body_el, state)
    return DocumentText(lines=state.lines, pages=None, columns=1)


def _xml(z: zipfile.ZipFile, name: str) -> etree._Element:
    return etree.fromstring(z.read(name), _PARSER)


def _header_parts(z: zipfile.ZipFile, document: etree._Element) -> list[str]:
    try:
        rels = _xml(z, "word/_rels/document.xml.rels")
    except KeyError:
        return []
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(f"{{{PR}}}Relationship")}
    names: list[str] = []
    for ref in document.iter(w("headerReference")):
        target = targets.get(ref.get(f"{{{R}}}id"))
        if not target:
            continue
        name = posixpath.normpath(posixpath.join("word", target)) if not target.startswith("/") else target[1:]
        if name not in names and name in z.namelist():
            names.append(name)
    return names


def _styles(z: zipfile.ZipFile) -> dict[str, tuple[bool | None, float | None]]:
    try:
        root = _xml(z, "word/styles.xml")
    except KeyError:
        return {}
    raw: dict[str, tuple[str | None, bool | None, float | None]] = {}
    for style in root.iter(w("style")):
        rpr = style.find(w("rPr"))
        based = style.find(w("basedOn"))
        raw[style.get(w("styleId"), "")] = (
            based.get(w("val")) if based is not None else None,
            _bold(rpr),
            _size(rpr),
        )
    resolved: dict[str, tuple[bool | None, float | None]] = {}
    for sid in raw:
        bold, size, current, hops = None, None, sid, 0
        while current in raw and hops < 20:
            parent, b, s = raw[current]
            bold = b if bold is None else bold
            size = s if size is None else size
            current, hops = parent, hops + 1
        resolved[sid] = (bold, size)
    return resolved


def _bold(rpr) -> bool | None:
    if rpr is None:
        return None
    b = rpr.find(w("b"))
    if b is None:
        return None
    return (b.get(w("val")) or "true").lower() not in FALSE_VALUES


def _size(rpr) -> float | None:
    if rpr is None:
        return None
    sz = rpr.find(w("sz"))
    try:
        return int(sz.get(w("val"))) / 2 if sz is not None else None
    except (TypeError, ValueError):
        return None


def _walk(container, state: _State) -> None:
    for child in container:
        tag = child.tag
        if tag == P:
            _paragraph(child, state)
        elif tag == TBL:
            for row in child.findall(TR):
                state.gap = True
                for cell in row.findall(TC):
                    _walk(cell, state)
            state.gap = True
        elif tag == SDT:
            content = child.find(SDT_CONTENT)
            if content is not None:
                _walk(content, state)
        elif tag not in SKIP and isinstance(tag, str):
            _walk(child, state)


def _paragraph(p, state: _State) -> None:
    ppr = p.find(w("pPr"))
    style_id = None
    if ppr is not None and ppr.find(w("pStyle")) is not None:
        style_id = ppr.find(w("pStyle")).get(w("val"))
    p_bold, p_size = state.styles.get(style_id or "", (None, None))
    if style_id is None:
        p_bold, p_size = state.styles.get("Normal", (None, None))

    segments: list[list[tuple[str, bool, float]]] = [[]]
    boxes: list = []

    def collect(node, fmt: tuple[bool, float]) -> None:
        for el in node:
            tag = el.tag
            if not isinstance(tag, str) or tag in SKIP:
                continue
            if tag == RUN:
                rpr = el.find(w("rPr"))
                b = _bold(rpr)
                s = _size(rpr)
                collect(el, (b if b is not None else bool(p_bold), s if s is not None else (p_size or 0.0)))
            elif tag == T:
                segments[-1].append((el.text or "", fmt[0], fmt[1]))
            elif tag == TAB:
                segments[-1].append((" ", fmt[0], fmt[1]))
            elif tag in (BR, CR):
                segments.append([])
            elif tag == TXBX:
                boxes.append(el)
            else:
                collect(el, fmt)

    collect(p, (bool(p_bold), p_size or 0.0))
    emitted = False
    for segment in segments:
        text = normalize_text("".join(t for t, _, _ in segment))
        if not text:
            continue
        chars = sum(len(t.strip()) for t, _, _ in segment) or 1
        bold_chars = sum(len(t.strip()) for t, b, _ in segment if b)
        size = max((s for _, _, s in segment), default=0.0)
        state.lines.append(Line(text=text, size=size, bold=bold_chars * 2 > chars, gap_before=state.gap))
        state.gap = False
        emitted = True
    for box in boxes:
        state.gap = True
        _walk(box, state)
        emitted = True
    if not emitted:
        state.gap = True
