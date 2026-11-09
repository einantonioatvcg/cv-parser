"""Detección del formato por contenido, sin mirar la extensión."""

from __future__ import annotations

import io
import zipfile
from typing import Literal

Format = Literal["pdf", "docx", "doc", "rtf", "html"]

OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")


def _text_head(data: bytes) -> str:
    head = data[:1024]
    for bom in BOMS:
        if head.startswith(bom):
            head = head[len(bom):]
            break
    # UTF-16 sin BOM o con BOM: quitar bytes nulos basta para buscar las etiquetas.
    return head.replace(b"\x00", b"").decode("latin-1").lstrip().lower()


def detect_format(data: bytes) -> Format | None:
    if not data:
        return None
    if data.startswith(OLE_SIGNATURE):
        return "doc"
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return "docx" if "word/document.xml" in z.namelist() else None
        except zipfile.BadZipFile:
            # Un ZIP ilegible se trata como docx para que la extracción lo reporte dañado.
            return "docx"
    if b"%PDF" in data[:1024]:
        return "pdf"
    head = _text_head(data)
    if head.startswith("{\\rtf"):
        return "rtf"
    if head.startswith("<!doctype html") or head.startswith("<html") or (
        head.startswith("<?xml") and "<html" in head
    ):
        return "html"
    return None
