import pytest

from cv_parser.sections import split_sections
from tests.helpers import to_lines


@pytest.mark.parametrize("texto,clave", [
    ("EXPERIENCIA LABORAL", "experience"), ("Experiencia Profesional:", "experience"),
    ("Work Experience", "experience"), ("E X P E R I E N C I A", "experience"),
    ("Formación Académica", "education"), ("FORMACION ACADEMICA", "education"), ("Escolaridad", "education"),
    ("Education", "education"), ("Perfil Profesional", "summary"), ("Professional Summary", "summary"),
    ("Referencias Personales", "references"), ("Datos Personales", "personal"), ("Idiomas", "languages"),
    # variantes de texto sucio
    ("FORMACIÓN ACADÉMICA", "education"), ("Formación Académica", "education"),
    ("E X P E R I E N C I A   L A B O R A L", "experience"), ("Education & Training", "education"),
])
def test_encabezados(texto, clave):
    assert clave in split_sections(to_lines(f"Nombre\n{texto}\nContenido")).parts


def test_orden_de_aparicion():
    s = split_sections(to_lines("Nombre\nPERFIL\nTexto\nEXPERIENCIA\nCajera\nESTUDIOS\nPrimaria"))
    assert s.order == ["summary", "experience", "education"]
    assert [l.text for l in s.header] == ["Nombre"]
    assert s.found_any is True


def test_oracion_no_es_encabezado():
    s = split_sections(to_lines("Nombre\nAsistente con experiencia laboral en ventas"))
    assert s.found_any is False and s.order == []


def test_referencias_cierran_experiencia():
    s = split_sections(to_lines("EXPERIENCIA\nCajera\nREFERENCIAS PERSONALES\nJuan Pérez 3312345678"))
    assert [l.text for l in s.parts["experience"]] == ["Cajera"]


def test_encabezado_repetido_se_une():
    s = split_sections(to_lines("EXPERIENCIA\nCajera\nIDIOMAS\nInglés\nEXPERIENCIA LABORAL\nMesera"))
    assert [l.text for l in s.parts["experience"]] == ["Cajera", "Mesera"]
    assert s.order == ["experience", "languages"]
