import json
import shutil

from eval import run_eval
from tests.helpers import FIXTURES


# I9: las cifras de una columna usan la etiqueta humana del expected, no la detección del parser.
def test_etiqueta_manual_de_columnas(tmp_path, capsys):
    (tmp_path / "originales").mkdir()
    shutil.copy(FIXTURES / "es_dos_columnas.pdf", tmp_path / "originales" / "a.pdf")
    run_eval.main(["--sample-dir", str(tmp_path), "--init"])
    split = json.loads((tmp_path / "split.json").read_text())
    (i,) = split["assignments"]
    split["assignments"][i] = "tuning"
    (tmp_path / "split.json").write_text(json.dumps(split))
    esperado = json.loads((FIXTURES / "expected_es.json").read_text())
    esperado["_meta"] = {"format": "pdf", "language": "es", "columns": 1}
    (tmp_path / "expected" / f"{i}.expected.json").write_text(json.dumps(esperado))
    run_eval.main(["--sample-dir", str(tmp_path), "--split", "tuning"])
    (reporte,) = [p for p in (tmp_path / "reportes").iterdir() if p.suffix == ".json"]
    datos = json.loads(reporte.read_text())
    assert datos["one_column"]["correct"] > 0 and set(datos["by_columns"]) == {"1"}
