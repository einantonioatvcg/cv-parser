"""Conversión de .doc, RTF y HTML a .docx con LibreOffice sin interfaz."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from lxml import etree, html as lxml_html

from cv_parser.errors import ConversionTimeout, CorruptFile

SUFFIXES = {"doc": ".doc", "rtf": ".rtf", "html": ".html"}
# Filtro explícito: sin él LibreOffice abre cualquier basura como texto plano.
INPUT_FILTERS = {
    "doc": ["MS Word 97", "MS Word 95"],
    "rtf": ["Rich Text Format"],
    "html": ["HTML (StarWriter)"],
}


_DROP_TAGS = {"script", "style", "link", "img", "image", "iframe", "frame", "frameset", "object", "embed",
              "applet", "base", "video", "audio", "source", "track", "picture", "svg", "math", "input", "form",
              "meta", "noscript", "portal", "canvas"}
_URL_ATTRIBUTES = {"src", "href", "background", "srcset", "poster", "data", "lowsrc", "dynsrc", "longdesc",
                   "action", "formaction", "cite", "codebase", "classid", "archive", "usemap", "profile",
                   "manifest", "icon", "xlink:href"}


def sanitize_html(data: bytes) -> bytes:
    """Quita todo lo que haría a LibreOffice descargar algo: imágenes, hojas de estilo, marcos, estilos con url()."""
    try:
        root = lxml_html.document_fromstring(data)
    except (etree.ParserError, ValueError) as exc:
        raise CorruptFile(type(exc).__name__) from None
    for el in list(root.iter()):
        if not isinstance(el.tag, str):  # comentarios e instrucciones de proceso
            if el.getparent() is not None:
                el.getparent().remove(el)
            continue
        if el.tag.lower().split("}")[-1] in _DROP_TAGS and el.getparent() is not None:
            el.drop_tree()
            continue
        for attr in list(el.attrib):
            name = attr.lower().split("}")[-1]
            if name in _URL_ATTRIBUTES or name.startswith("on") or "url" in el.attrib[attr].lower():
                del el.attrib[attr]
    head = root.find("head")
    if head is None:
        head = etree.Element("head")
        root.insert(0, head)
    head.insert(0, etree.fromstring('<meta charset="utf-8"/>'))
    return lxml_html.tostring(root, encoding="utf-8", doctype="<!DOCTYPE html>")


def convert_to_docx(data: bytes, source_format: str, timeout: int = 60) -> bytes:
    if source_format not in SUFFIXES:
        raise ValueError(f"formato no convertible: {source_format}")
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if binary is None:
        raise RuntimeError("LibreOffice no está instalado")
    with tempfile.TemporaryDirectory(prefix="cvp-", ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / f"entrada{SUFFIXES[source_format]}"
        source.write_bytes(sanitize_html(data) if source_format == "html" else data)
        out_dir = tmp_path / "salida"
        output = out_dir / "entrada.docx"
        for input_filter in INPUT_FILTERS[source_format]:
            command = [binary, "--headless", "--norestore", "--nolockcheck", "--nodefault", "--nologo",
                       f"-env:UserInstallation=file://{tmp_path}/perfil", f"--infilter={input_filter}",
                       "--convert-to", "docx:MS Word 2007 XML", "--outdir", str(out_dir), str(source)]
            try:
                result = subprocess.run(command, capture_output=True, timeout=timeout, check=False,
                                        env={**os.environ, "HOME": str(tmp_path)}, start_new_session=True)
            except subprocess.TimeoutExpired:
                _kill_processes_using(str(tmp_path))
                raise ConversionTimeout() from None
            if result.returncode == 0 and output.is_file() and output.stat().st_size > 0:
                break
        else:
            raise CorruptFile("conversion_failed")
        return output.read_bytes()


def _kill_processes_using(marker: str) -> None:
    """LibreOffice deja procesos hijos; se matan los que usan el perfil temporal de esta petición."""
    proc = Path("/proc")
    if not proc.is_dir():
        return
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if marker in (entry / "cmdline").read_bytes().decode(errors="ignore"):
                os.kill(int(entry.name), signal.SIGKILL)
        except (OSError, ValueError):
            continue
