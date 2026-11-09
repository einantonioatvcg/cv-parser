import pytest

from cv_parser.errors import CorruptFile
from cv_parser.extract.pdf import extract_pdf
from tests.helpers import read


def test_pdf_una_columna():
    doc = extract_pdf(read("es_una_columna.pdf"))
    assert doc.columns == 1 and doc.pages == 1
    assert "Asistente Administrativa" in [l.text for l in doc.lines]


def test_pdf_formato_de_linea():
    lines = extract_pdf(read("es_una_columna.pdf")).lines
    por_texto = {l.text: l for l in lines}
    assert por_texto["EXPERIENCIA LABORAL"].bold and por_texto["EXPERIENCIA LABORAL"].gap_before
    assert not por_texto["Marzo 2021 - Actualidad"].bold
    assert not por_texto["Marzo 2021 - Actualidad"].gap_before
    assert por_texto["Recepcionista"].gap_before


def test_pdf_dos_columnas_no_mezcla():
    doc = extract_pdf(read("es_dos_columnas.pdf"))
    textos = [l.text for l in doc.lines]
    assert doc.columns == 2
    assert not any("HABILIDADES" in t and "EXPERIENCIA" in t for t in textos)
    assert textos.index("EXPERIENCIA LABORAL") < textos.index("Recepcionista") < textos.index("FORMACIÓN ACADÉMICA")
    assert textos[0] == "María Fernanda López Hernández"


def test_pdf_escaneado_sin_lineas():
    assert extract_pdf(read("es_escaneado.pdf")).lines == []


@pytest.mark.parametrize("name", ["danado.pdf", "protegido.pdf"])
def test_pdf_ilegible(name):
    with pytest.raises(CorruptFile):
        extract_pdf(read(name))
