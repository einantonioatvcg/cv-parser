import io
import zipfile

import pytest

from cv_parser.errors import CorruptFile
from cv_parser.extract.docx import extract_docx
from tests.helpers import read


def docx_que_descomprime_mas_de_100_mb() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:document/>")
        z.writestr("word/relleno.bin", b"\0" * (101 * 1024 * 1024))
    return buf.getvalue()


def test_docx_tablas_cuadros_y_encabezado():
    textos = [l.text for l in extract_docx(read("es_tablas_cuadros.docx")).lines]
    assert textos[0] == "María Fernanda López Hernández"
    assert textos.count("Recepcionista") == 1               # tabla
    assert textos.count("Universidad de Guadalajara") == 1  # cuadro de texto, sin duplicar el Fallback


def test_docx_orden_y_formato():
    doc = extract_docx(read("es_tablas_cuadros.docx"))
    assert doc.pages is None and doc.columns == 1
    lines = doc.lines
    textos = [l.text for l in lines]
    assert textos.index("EXPERIENCIA LABORAL") < textos.index("Recepcionista") < textos.index("FORMACIÓN ACADÉMICA")
    assert textos.index("FORMACIÓN ACADÉMICA") < textos.index("Universidad de Guadalajara") < textos.index("HABILIDADES")
    por_texto = {l.text: l for l in lines}
    assert por_texto["EXPERIENCIA LABORAL"].bold and por_texto["EXPERIENCIA LABORAL"].gap_before
    assert por_texto["Enero 2018 - Febrero 2021"].gap_before   # cada fila de tabla abre bloque
    assert por_texto["Bachillerato General"].gap_before        # párrafo vacío dentro del cuadro


def test_docx_parrafos():
    textos = [l.text for l in extract_docx(read("es_parrafos.docx")).lines]
    assert textos[:2] == ["María Fernanda López Hernández", "Asistente Administrativa"]
    assert "- Gestión de agenda y viajes de la dirección general" in textos
    assert "" not in textos


def test_docx_vacio_y_danado():
    assert extract_docx(read("sin_texto.docx")).lines == []
    with pytest.raises(CorruptFile):
        extract_docx(read("danado.docx"))


def test_docx_bomba_zip():
    with pytest.raises(CorruptFile):
        extract_docx(docx_que_descomprime_mas_de_100_mb())


def test_docx_xml_invalido():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document><sin cerrar")
    with pytest.raises(CorruptFile):
        extract_docx(buf.getvalue())
