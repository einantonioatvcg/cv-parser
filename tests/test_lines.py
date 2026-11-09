import pytest

from cv_parser.lines import Line, normalize_text


def test_normaliza():
    assert normalize_text("Oﬁcina  Central") == "Oficina Central"
    assert normalize_text("Administración") == "Administración"


@pytest.mark.parametrize("sucio,limpio", [
    ("Asistente Administrativa", "Asistente Administrativa"),   # espacio duro
    ("Administración", "Administración"),                      # acento separado
    ("  Ca­jera ​ ", "Cajera"),                            # guion suave y ancho cero
    ("Tel:\t33 1234 5678", "Tel: 33 1234 5678"),
])
def test_normaliza_variantes(sucio, limpio):
    assert normalize_text(sucio) == limpio


def test_line_congelada():
    line = Line("Hola")
    assert (line.page, line.size, line.bold, line.gap_before) == (1, 0.0, False, False)
    with pytest.raises(Exception):
        line.text = "otro"
