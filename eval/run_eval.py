"""Corre la muestra local de CVs y escribe reportes sin nombres de archivo.

Uso (dentro del contenedor):
  python eval/run_eval.py --sample-dir /muestra --init
  python eval/run_eval.py --sample-dir /muestra --split tuning
  python eval/run_eval.py --sample-dir /muestra --open-reserve
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cv_parser import __version__  # noqa: E402
from cv_parser.config import Settings  # noqa: E402
from cv_parser.llm.clients import make_client  # noqa: E402
from cv_parser.pipeline import parse_document  # noqa: E402
from eval.prices import cost_usd  # noqa: E402
from cv_parser.sniff import detect_format  # noqa: E402
from eval.score import SECTIONS, Counts, score_cv, score_entries_by_actual, verdict  # noqa: E402
from eval.split import SampleItem, assign_split  # noqa: E402

DEFAULT_SEED = 20261109


def file_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _originals(sample: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    folder = sample / "originales"
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.is_file():
                found.setdefault(file_id(path.read_bytes()), path)
    return found


class _Counting:
    """Envuelve al cliente de LLM para contar llamadas y tokens."""

    def __init__(self, inner) -> None:
        self.inner, self.provider, self.model = inner, inner.provider, inner.model
        self.calls = self.input_tokens = self.output_tokens = 0

    failures = 0

    def extract(self, text: str):
        try:
            result = self.inner.extract(text)
        except Exception:
            self.failures += 1
            raise
        self.calls += 1
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        return result


def _parse(data: bytes, llm=None, mode: str = "low_confidence", threshold: float = 0.75):
    try:
        return parse_document(data, llm=llm, llm_mode=mode, llm_threshold=threshold), None
    except Exception as exc:  # noqa: BLE001 - se reporta solo la clase
        return None, type(exc).__name__


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_init(sample: Path, seed: int) -> int:
    files = _originals(sample)
    ids_path = sample / "ids.json"
    ids = json.loads(ids_path.read_text()) if ids_path.exists() else {}
    ids.update({i: p.name for i, p in files.items()})
    _write_json(ids_path, ids)

    split_path = sample / "split.json"
    if split_path.exists():
        split = json.loads(split_path.read_text())
        new = [i for i in files if i not in split["assignments"]]
        print(f"split.json ya existe; no se reasigna. CVs sin asignar: {len(new)}")
    else:
        items: dict[str, dict] = {}
        for i, path in files.items():
            result, error = _parse(path.read_bytes())
            if result is not None:
                items[i] = {"format": result.meta.format, "language": result.meta.language,
                            "columns": result.meta.columns, "status": result.status}
            else:
                fmt = detect_format(path.read_bytes())
                items[i] = {"format": {"rtf": "doc", "html": "doc"}.get(fmt or "", fmt or "unknown"),
                            "language": "unknown", "columns": 1, "status": f"error:{error}"}
        labels_path = sample / "labels.json"   # etiquetas humanas opcionales: {id: {format, language, columns}}
        if labels_path.exists():
            for i, label in json.loads(labels_path.read_text()).items():
                if i in items:
                    items[i].update({k: v for k, v in label.items() if k in ("format", "language", "columns")})
        assignments = assign_split(
            [SampleItem(i, v["format"], v["language"], v["columns"]) for i, v in items.items()], seed)
        split = {"seed": seed, "assignments": assignments, "items": items, "reserve_opened": False}
        _write_json(split_path, split)
    (sample / "expected").mkdir(exist_ok=True)
    (sample / "reportes").mkdir(exist_ok=True)

    groups: Counter = Counter()
    for i, kind in split["assignments"].items():
        meta = split["items"].get(i, {})
        groups[(kind, meta.get("format"), meta.get("language"), meta.get("columns"))] += 1
    print(f"CVs: {len(split['assignments'])}")
    for (kind, fmt, lang, cols), n in sorted(groups.items(), key=str):
        print(f"  {kind:8} formato={fmt} idioma={lang} columnas={cols}: {n}")
    reserve = [split["items"].get(i, {}) for i, k in split["assignments"].items() if k == "reserve"]
    for label, present in (("doc", any(m.get("format") == "doc" for m in reserve)),
                           ("inglés", any(m.get("language") in ("en", "mixed") for m in reserve)),
                           ("varias columnas", any((m.get("columns") or 1) > 1 for m in reserve))):
        if not present:
            print(f"  aviso: la reserva no tiene {label}; ese caso solo queda probado con fixtures")
    return 0


def _run(sample: Path, kind: str, llm_args: dict | None = None) -> dict:
    split = json.loads((sample / "split.json").read_text())
    files = _originals(sample)
    ids = sorted(i for i, k in split["assignments"].items() if kind == "all" or k == kind)
    llm_args = llm_args or {}
    client = None
    if llm_args.get("provider"):
        client = _Counting(make_client(Settings(llm_provider=llm_args["provider"], llm_model=llm_args["model"],
                                                llm_timeout=llm_args.get("timeout", 60))))
    mode, threshold = llm_args.get("mode", "low_confidence"), llm_args.get("threshold", 0.75)
    report = {"split": kind, "optimistic": kind == "all",
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "parser_version": __version__, "provider": llm_args.get("provider"), "model": llm_args.get("model"),
              "mode": mode if client else None, "cvs": [], "unreadable": [], "missing_expected": [],
              "missing_file": [], "errors": []}
    llm_sections = 0
    by: dict[str, dict[str, Counts]] = defaultdict(lambda: defaultdict(Counts))
    overall = Counts()
    one_column = Counts()
    for i in ids:
        path = files.get(i)
        if path is None:
            report["missing_file"].append(i)
            continue
        result, error = _parse(path.read_bytes(), client, mode, threshold)
        if result is None:
            report["errors"].append({"id": i, "error": error})
            continue
        llm_sections += sum(1 for v in result.meta.extraction.values() if v == "llm")
        if result.status == "unreadable":
            report["unreadable"].append(i)
            continue
        expected_path = sample / "expected" / f"{i}.expected.json"
        if not expected_path.exists():
            report["missing_expected"].append(i)
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        sections = score_cv(expected, result.extracted.model_dump())
        total = sum(sections.values(), Counts())
        overall += total
        # La etiqueta humana del expected manda sobre lo que detectó el parser.
        label = expected.get("_meta") or {}
        fmt = label.get("format") or result.meta.format
        language = label.get("language") or result.meta.language
        columns = int(label.get("columns") or result.meta.columns)
        if columns == 1:
            one_column += total
        by["by_format"][fmt] += total
        by["by_language"][language] += total
        by["by_columns"][str(columns)] += total
        for name, counts in sections.items():
            by["by_section"][name] += counts
        actual = result.extracted.model_dump()
        for section in ("experience", "education"):
            produced = actual[section]
            for entry, counts in zip(produced, score_entries_by_actual(expected.get(section) or [], produced)):
                by["by_confidence"][_bucket(entry["confidence"])] += counts
        report["cvs"].append({"id": i, "format": fmt, "language": language, "columns": columns,
                              "label": "manual" if label else "parser", "status": result.status, "totals": total.as_dict(),
                              "sections": {k: v.as_dict() for k, v in sections.items()}})
    for key in ("by_format", "by_language", "by_columns", "by_section", "by_confidence"):
        report[key] = {k: v.as_dict() for k, v in sorted(by[key].items())}
    if client is not None:
        measured = len(report["cvs"]) + len(report["missing_expected"])
        report["llm"] = {
            "calls": client.calls, "failures": client.failures, "input_tokens": client.input_tokens, "output_tokens": client.output_tokens,
            "sections_to_llm": llm_sections, "pct_cvs_to_llm": round(100 * client.calls / measured, 1) if measured else 0,
            "cost_usd": cost_usd(client.model, client.input_tokens, client.output_tokens),
        }
    report["overall"] = overall.as_dict()
    report["one_column"] = one_column.as_dict()
    report["verdict"] = verdict(one_column, overall)
    return report


def _bucket(confidence: float) -> str:
    return "<0.5" if confidence < 0.5 else ("0.5-0.75" if confidence < 0.75 else ">=0.75")


def _markdown(report: dict) -> str:
    lines = [f"# Medición `{report['split']}`", "", f"- Generado: {report['generated_at']}",
             f"- Versión del parser: {report['parser_version']}",
             f"- CVs medidos: {len(report['cvs'])}; ilegibles: {len(report['unreadable'])}; "
             f"sin respuesta esperada: {len(report['missing_expected'])}; errores: {len(report['errors'])}",
             f"- Una columna: {report['one_column']['pct_correct']} % correctos",
             f"- Toda la muestra: {report['overall']['pct_correct']} % correctos, "
             f"{report['overall']['pct_incorrect']} % incorrectos",
             f"- Veredicto (80 % correctos a una columna, máximo 5 % incorrectos): "
             f"{'se logra' if report['verdict'] else 'no se logra'}", ""]
    for key, title in (("by_format", "Formato"), ("by_language", "Idioma"), ("by_columns", "Columnas"),
                       ("by_section", "Sección"), ("by_confidence", "Confianza de la entrada")):
        lines += [f"## {title}", "", "| Grupo | Correctos | Vacíos | Incorrectos | % correctos | % incorrectos |",
                  "|---|---|---|---|---|---|"]
        for group, c in report[key].items():
            lines.append(f"| {group} | {c['correct']} | {c['empty']} | {c['incorrect']} | {c['pct_correct']} | {c['pct_incorrect']} |")
        lines.append("")
    lines += ["## Por CV", "", "| ID | Formato | Idioma | Columnas | % correctos | % incorrectos |", "|---|---|---|---|---|---|"]
    for cv in report["cvs"]:
        t = cv["totals"]
        lines.append(f"| {cv['id']} | {cv['format']} | {cv['language']} | {cv['columns']} | {t['pct_correct']} | {t['pct_incorrect']} |")
    if report["unreadable"]:
        lines += ["", "Ilegibles: " + ", ".join(report["unreadable"])]
    if report["errors"]:
        lines += ["", "Errores: " + ", ".join(f"{e['id']} ({e['error']})" for e in report["errors"])]
    return "\n".join(lines) + "\n"


def cmd_report(sample: Path, kind: str, llm_args: dict | None = None) -> int:
    report = _run(sample, kind, llm_args)
    folder = sample / "reportes"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _write_json(folder / f"{kind}-{stamp}.json", report)
    (folder / f"{kind}-{stamp}.md").write_text(_markdown(report), encoding="utf-8")
    o, one = report["overall"], report["one_column"]
    print(f"{kind}: {len(report['cvs'])} CVs medidos, {len(report['unreadable'])} ilegibles, "
          f"{len(report['missing_expected'])} sin respuesta esperada, {len(report['errors'])} con error")
    print(f"una columna: {one['pct_correct']} % correctos; toda la muestra: {o['pct_correct']} % correctos, "
          f"{o['pct_incorrect']} % incorrectos; veredicto: {'se logra' if report['verdict'] else 'no se logra'}")
    for section, c in report["by_section"].items():
        print(f"  {section}: {c['pct_correct']} % correctos, {c['pct_incorrect']} % incorrectos")
    if report.get("llm"):
        l = report["llm"]
        print(f"LLM {report['provider']}/{report['model']} modo {report['mode']}: {l['calls']} llamadas "
              f"({l['pct_cvs_to_llm']} % de CVs), {l['input_tokens']} tokens de entrada, {l['output_tokens']} de salida, "
              f"costo estimado {l['cost_usd']} USD")
    print(f"reporte: reportes/{kind}-{stamp}.md")
    return 0


def _config_name(llm_args: dict, name: str | None) -> str:
    if name:
        return name
    if llm_args.get("provider"):
        return f"{llm_args['provider']}/{llm_args['model']}/{llm_args.get('mode', 'low_confidence')}"
    return "rules"


def _llm_works(llm_args: dict) -> bool:
    """Prueba previa con un fixture inventado, para no gastar la reserva con una clave o un modelo equivocados."""
    from cv_parser.extract.docx import extract_docx
    from cv_parser.llm.clients import LLMError

    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "es_parrafos.docx"
    text = "\n".join(l.text for l in extract_docx(fixture.read_bytes()).lines)
    client = make_client(Settings(llm_provider=llm_args["provider"], llm_model=llm_args["model"], llm_timeout=60))
    try:
        client.extract(text)
    except LLMError:
        return False
    return True


def cmd_open_reserve(sample: Path, llm_args: dict | None = None, name: str | None = None) -> int:
    """La reserva se abre una sola vez por configuración (reglas o proveedor/modelo/modo)."""
    llm_args = llm_args or {}
    split_path = sample / "split.json"
    split = json.loads(split_path.read_text())
    config = _config_name(llm_args, name)
    if "reserve_openings" not in split:
        # Formato anterior: una sola bandera, que correspondía a las reglas.
        split["reserve_openings"] = {"rules": split.get("reserve_opened_at")} if split.get("reserve_opened") else {}
    opened = split["reserve_openings"]
    if config in opened:
        print(f"La reserva ya se abrió para '{config}'; no se vuelve a medir.", file=sys.stderr)
        return 2
    if llm_args.get("provider") and not _llm_works(llm_args):
        print("El LLM no respondió con un CV inventado; la reserva no se abre.", file=sys.stderr)
        return 3
    opened[config] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    split["reserve_opened"] = True
    _write_json(split_path, split)
    return cmd_report(sample, "reserve", llm_args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Medición del parser con la muestra local de CVs")
    parser.add_argument("--sample-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--split", choices=["tuning", "all"])
    mode.add_argument("--open-reserve", action="store_true")
    parser.add_argument("--provider", choices=["anthropic", "openai", "gemini"])
    parser.add_argument("--model")
    parser.add_argument("--mode", choices=["low_confidence", "always"], default="low_confidence")
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--name", help="nombre de la configuración al abrir la reserva (p. ej. reglas-v2)")
    args = parser.parse_args(argv)
    llm_args = {"provider": args.provider, "model": args.model, "mode": args.mode, "threshold": args.threshold}
    if args.provider and not args.model:
        parser.error("--model es obligatorio con --provider")
    sample: Path = args.sample_dir
    if args.init:
        return cmd_init(sample, args.seed)
    if not (sample / "split.json").exists():
        print("Falta split.json; corre primero --init.", file=sys.stderr)
        return 1
    if args.open_reserve:
        return cmd_open_reserve(sample, llm_args, args.name)
    return cmd_report(sample, args.split, llm_args)


if __name__ == "__main__":
    sys.exit(main())
