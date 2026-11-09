import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from cv_parser.errors import ConversionTimeout, CorruptFile
from cv_parser.extract.convert import convert_to_docx
from cv_parser.extract.docx import extract_docx
from tests.helpers import read


def lanza_timeout_expired(*args, **kwargs):
    raise subprocess.TimeoutExpired(cmd="soffice", timeout=1)


@pytest.mark.parametrize("name,fmt", [("es_real.doc", "doc"), ("es_rtf_renombrado.doc", "rtf"), ("es_html_renombrado.doc", "html")])
def test_convierte_y_lee(name, fmt):
    textos = [l.text for l in extract_docx(convert_to_docx(read(name), fmt)).lines]
    assert "Asistente Administrativa" in textos and "Recepcionista" in textos


def test_conversiones_simultaneas():
    with ThreadPoolExecutor(2) as pool:
        salidas = list(pool.map(lambda _: convert_to_docx(read("es_real.doc"), "doc"), range(2)))
    assert all(salidas)


def test_ole_invalido_limpia_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with pytest.raises(CorruptFile):
        convert_to_docx(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1basura", "doc")
    assert list(tmp_path.iterdir()) == []


def test_timeout_limpia_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(subprocess, "run", lanza_timeout_expired)
    with pytest.raises(ConversionTimeout):
        convert_to_docx(read("es_real.doc"), "doc")
    assert list(tmp_path.iterdir()) == []


def test_formato_no_convertible():
    with pytest.raises(ValueError):
        convert_to_docx(b"x", "pdf")
