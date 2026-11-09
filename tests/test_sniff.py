import io
import zipfile

import pytest

from cv_parser.sniff import detect_format
from tests.helpers import FIXTURES


def zip_sin_document_xml() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hola.txt", "no es un documento")
    return buf.getvalue()


@pytest.mark.parametrize("name,fmt", [
    ("es_una_columna.pdf", "pdf"), ("es_parrafos.docx", "docx"), ("es_real.doc", "doc"),
    ("es_rtf_renombrado.doc", "rtf"), ("es_html_renombrado.doc", "html"),
    ("es_docx_renombrado.doc", "docx"), ("danado.docx", "docx"),
])
def test_detecta_por_contenido(name, fmt):
    assert detect_format((FIXTURES / name).read_bytes()) == fmt


@pytest.mark.parametrize("data", [b"", b"MZ\x90\x00", zip_sin_document_xml()])
def test_no_soportado(data):
    assert detect_format(data) is None


@pytest.mark.parametrize("data,fmt", [
    (b"\xef\xbb\xbf<!DOCTYPE html><html><body>x</body></html>", "html"),
    (b"  <HTML><body>x</body></HTML>", "html"),
    (b"basura previa %PDF-1.7\n", "pdf"),
])
def test_variantes(data, fmt):
    assert detect_format(data) == fmt
