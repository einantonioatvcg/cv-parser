from cv_parser.dates import detect_language


def test_idioma():
    assert detect_language("EXPERIENCIA LABORAL Marzo 2021 Actualidad") == "es"
    assert detect_language("WORK EXPERIENCE March 2021 Present") == "en"
    assert detect_language("EXPERIENCIA LABORAL Marzo EDUCATION Bachelor Present") == "mixed"


def test_idioma_minoritario_bajo_umbral():
    texto = "Experiencia laboral en la empresa con clientes de la ciudad y atención del público. Grupo Comercial del Bajío. Excel"
    assert detect_language(texto + " Office") == "es"
