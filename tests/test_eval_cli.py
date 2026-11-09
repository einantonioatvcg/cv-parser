import json
import shutil

import pytest

from eval import run_eval
from tests.helpers import FIXTURES


@pytest.fixture
def muestra(tmp_path):
    originales = tmp_path / "originales"
    originales.mkdir()
    shutil.copy(FIXTURES / "es_una_columna.pdf", originales / "Maria Lopez CV.pdf")
    shutil.copy(FIXTURES / "es_parrafos.docx", originales / "Maria Lopez CV.docx")
    shutil.copy(FIXTURES / "es_escaneado.pdf", originales / "Maria escaneado.pdf")
    return tmp_path


def todo_el_texto(carpeta) -> str:
    return "\n".join(p.read_text(errors="ignore") for p in carpeta.rglob("*") if p.is_file())


def test_cli_sin_nombres_y_reserva_unica(muestra, capsys):
    # --init crea split.json e ids.json; la consola no contiene "Maria"
    assert run_eval.main(["--sample-dir", str(muestra), "--init"]) == 0
    salida = capsys.readouterr()
    assert (muestra / "split.json").exists() and (muestra / "ids.json").exists()
    assert "Maria" not in salida.out + salida.err
    split = json.loads((muestra / "split.json").read_text())
    ids = sorted(split["assignments"])
    assert len(ids) == 3 and all(len(i) == 12 for i in ids)

    # --init no reasigna un split existente
    assert run_eval.main(["--sample-dir", str(muestra), "--init", "--seed", "99"]) == 0
    assert json.loads((muestra / "split.json").read_text())["assignments"] == split["assignments"]
    capsys.readouterr()

    esperado = (FIXTURES / "expected_es.json").read_text()
    (muestra / "expected").mkdir(exist_ok=True)
    for i in ids:
        (muestra / "expected" / f"{i}.expected.json").write_text(esperado)

    # --split tuning escribe reportes/ sin "Maria"
    assert run_eval.main(["--sample-dir", str(muestra), "--split", "tuning"]) == 0
    salida = capsys.readouterr()
    reportes = list((muestra / "reportes").iterdir())
    assert reportes and "Maria" not in salida.out + salida.err
    assert "Maria" not in "\n".join(p.read_text() for p in reportes)

    # --open-reserve funciona una vez; la segunda sale con código 2
    assert run_eval.main(["--sample-dir", str(muestra), "--open-reserve"]) == 0
    salida = capsys.readouterr()
    assert "Maria" not in salida.out + salida.err
    assert run_eval.main(["--sample-dir", str(muestra), "--open-reserve"]) == 2


def test_reporte_separa_ilegibles(muestra, capsys):
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    split = json.loads((muestra / "split.json").read_text())
    for i in split["assignments"]:
        split["assignments"][i] = "tuning"
    (muestra / "split.json").write_text(json.dumps(split))
    run_eval.main(["--sample-dir", str(muestra), "--split", "tuning"])
    (reporte,) = [p for p in (muestra / "reportes").iterdir() if p.suffix == ".json"]
    datos = json.loads(reporte.read_text())
    assert len(datos["unreadable"]) == 1 and len(datos["missing_expected"]) == 2
    assert {"by_format", "by_language", "by_columns", "by_section", "overall", "one_column", "verdict"} <= set(datos)


from cv_parser.llm.clients import LLMResult


class _ClienteFalso:
    def __init__(self, provider, model):
        self.provider, self.model = provider, model

    def extract(self, text):
        return LLMResult({"education": [], "experience": []}, 1000, 200)


def _con_llm_falso(monkeypatch):
    monkeypatch.setattr(run_eval, "make_client", lambda settings: _ClienteFalso(settings.llm_provider, settings.llm_model))


def _ultimo_json(muestra):
    return json.loads(max((muestra / "reportes").glob("*.json"), key=lambda p: p.stat().st_mtime).read_text())


def test_reporte_con_llm_registra_proveedor_y_tokens(muestra, monkeypatch, capsys):
    _con_llm_falso(monkeypatch)
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    assert run_eval.main(["--sample-dir", str(muestra), "--split", "tuning", "--provider", "anthropic",
                          "--model", "claude-haiku-5-5", "--mode", "always"]) == 0
    datos = _ultimo_json(muestra)
    assert (datos["provider"], datos["model"], datos["mode"]) == ("anthropic", "claude-haiku-5-5", "always")
    assert datos["llm"]["calls"] >= 1 and datos["llm"]["input_tokens"] >= 1000 and datos["llm"]["cost_usd"] > 0
    salida = capsys.readouterr()
    assert "Maria" not in salida.out + salida.err


def test_reserva_llm_una_vez_por_configuracion(muestra, monkeypatch):
    _con_llm_falso(monkeypatch)
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    base = ["--sample-dir", str(muestra), "--open-reserve", "--provider", "anthropic", "--mode", "always"]
    assert run_eval.main(base + ["--model", "a"]) == 0
    assert run_eval.main(base + ["--model", "a"]) == 2
    assert run_eval.main(base + ["--model", "b"]) == 0
    assert run_eval.main(["--sample-dir", str(muestra), "--open-reserve"]) == 0
    assert run_eval.main(["--sample-dir", str(muestra), "--open-reserve", "--name", "reglas-v2"]) == 0
    assert run_eval.main(["--sample-dir", str(muestra), "--open-reserve", "--name", "reglas-v2"]) == 2


def test_split_all_marca_optimista(muestra, monkeypatch):
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    assert run_eval.main(["--sample-dir", str(muestra), "--split", "all"]) == 0
    datos = _ultimo_json(muestra)
    assert datos["optimistic"] is True and datos["split"] == "all"
    assert len(datos["cvs"]) + len(datos["unreadable"]) + len(datos["missing_expected"]) == 3


class _ClienteQueFalla(_ClienteFalso):
    def extract(self, text):
        from cv_parser.llm.clients import LLMError
        raise LLMError("missing_api_key")


def test_no_abre_reserva_si_el_llm_falla(muestra, monkeypatch):
    monkeypatch.setattr(run_eval, "make_client", lambda settings: _ClienteQueFalla(settings.llm_provider, settings.llm_model))
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    base = ["--sample-dir", str(muestra), "--open-reserve", "--provider", "anthropic", "--model", "x", "--mode", "always"]
    assert run_eval.main(base) == 3
    split = json.loads((muestra / "split.json").read_text())
    assert "anthropic/x/always" not in split.get("reserve_openings", {})


def test_reporte_cuenta_fallas_del_llm(muestra, monkeypatch):
    monkeypatch.setattr(run_eval, "make_client", lambda settings: _ClienteQueFalla(settings.llm_provider, settings.llm_model))
    run_eval.main(["--sample-dir", str(muestra), "--init"])
    run_eval.main(["--sample-dir", str(muestra), "--split", "all", "--provider", "anthropic", "--model", "x", "--mode", "always"])
    assert _ultimo_json(muestra)["llm"]["failures"] >= 1
