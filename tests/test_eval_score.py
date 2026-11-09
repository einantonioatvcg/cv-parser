from eval.score import Counts, score, score_cv, verdict


def test_reglas_de_campo():
    assert score({"city": "Guadalajara"}, {"city": "GUADALAJÁRA"}) == Counts(1, 0, 0)
    assert score({"city": "Guadalajara"}, {"city": None}) == Counts(0, 1, 0)
    assert score({"city": "Guadalajara"}, {"city": "Monterrey"}) == Counts(0, 0, 1)
    assert score({"city": None}, {"city": "Monterrey"}) == Counts(0, 0, 1)
    assert score({"city": None}, {"city": None}) == Counts(0, 0, 0)


def test_fecha_cuenta_anio_y_mes_por_separado():
    assert score({"start": {"year": 2021, "month": 3}}, {"start": {"year": 2021, "month": None}}) == Counts(1, 1, 0)
    assert score({"start": {"year": 2021, "month": 3}}, {"start": None}) == Counts(0, 2, 0)


def test_booleanos():
    assert score({"is_current": True}, {"is_current": False}) == Counts(0, 1, 0)
    assert score({"is_current": False}, {"is_current": True}) == Counts(0, 0, 1)
    assert score({"is_current": False}, {"is_current": False}) == Counts(0, 0, 0)


def test_exactos_y_confianza_ignorada():
    assert score({"country_code": "MX"}, {"country_code": "mx"}) == Counts(0, 0, 1)
    assert score({"level": "university"}, {"level": "university"}) == Counts(1, 0, 0)
    assert score({"city": "X"}, {"city": "X", "confidence": 0.3}) == Counts(1, 0, 0)


def test_descripcion_tolera_mas():
    esperado = {"description": "Gestión de agenda y viajes de la dirección general"}
    assert score(esperado, {"description": "Gestion de agenda y viajes de direccion general."}) == Counts(1, 0, 0)


def empleo(puesto, empresa, anio):
    return {"position": puesto, "company": empresa, "city": None, "country_code": "MX",
            "start": {"year": anio, "month": None}, "end": None, "is_current": False, "description": None}


def cv(empleos):
    return {"contact": {"name": "Ana", "email": None, "phone": None}, "headline": None, "summary": None,
            "education": [], "experience": empleos}


def test_empareja_por_parecido_y_cuenta_faltantes_e_inventadas():
    a, b = empleo("Cajera", "Tienda Azul", 2018), empleo("Mesera", "Café Sol", 2016)
    # lista invertida: todo correcto
    r = score_cv(cv([a, b]), cv([b, a]))
    assert r["experience"] == Counts(8, 0, 0)
    # entrada esperada ausente: sus campos con valor cuentan como vacíos
    r = score_cv(cv([a, b]), cv([a]))
    assert r["experience"] == Counts(4, 4, 0)
    # entrada de más: sus campos con valor cuentan como incorrectos
    r = score_cv(cv([a]), cv([a, b]))
    assert r["experience"] == Counts(4, 0, 4)
    assert r["contact"] == Counts(1, 0, 0) and set(r) == {"contact", "headline", "summary", "education", "experience"}


def test_veredicto():
    assert verdict(Counts(80, 15, 5), Counts(80, 15, 5)) is True
    assert verdict(Counts(79, 16, 5), Counts(80, 15, 5)) is False
    assert verdict(Counts(90, 5, 5), Counts(84, 10, 6)) is False
    assert verdict(Counts(0, 0, 0), Counts(0, 0, 0)) is False


def test_suma():
    assert Counts(1, 2, 3) + Counts(1, 1, 1) == Counts(2, 3, 4) and Counts(1, 2, 3).total == 6
