"""De bytes a `ParseResult`: formato, extracción, secciones, encabezado y entradas."""

from __future__ import annotations

import logging
import re
import time
from datetime import date

from cv_parser import __version__
from cv_parser.dates import detect_language
from cv_parser.entries import parse_education, parse_experience
from cv_parser.errors import UnsupportedFormat
from cv_parser.extract.convert import convert_to_docx
from cv_parser.extract.docx import extract_docx
from cv_parser.extract.pdf import extract_pdf
from cv_parser.header import best_phone, find_email, is_address_line, looks_like_name, parse_header
from cv_parser.lines import DocumentText, fold
from cv_parser.llm.clients import LLMClient, LLMError
from cv_parser.llm.redact import redact
from cv_parser.llm.validate import validate_header, validate_response
from cv_parser.models import Confidence, Extracted, Meta, ParseResult, ParseWarning
from cv_parser.places import find_place, find_place_loose, is_place_line
from cv_parser.sections import split_sections
from cv_parser.sniff import detect_format

log = logging.getLogger("cv_parser")

MIN_PDF_LETTERS = 30
BIRTH_OR_ORIGIN = re.compile(r"(?<![a-z])(nacimiento|naci|nacid[oa]|nacionalidad|origen|birth|born|nationality)(?![a-z])")
SUMMARY_CONFIDENCE = 0.9
OK_THRESHOLD = 0.6


def _extract(data: bytes, fmt: str, convert_timeout: int) -> DocumentText:
    if fmt == "pdf":
        return extract_pdf(data)
    if fmt == "docx":
        return extract_docx(data)
    return extract_docx(convert_to_docx(data, fmt, timeout=convert_timeout))


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def parse_document(data: bytes, *, convert_timeout: int = 60, today: date | None = None,
                   llm: LLMClient | None = None, llm_mode: str = "low_confidence",
                   llm_threshold: float = 0.75) -> ParseResult:
    started = time.monotonic()
    fmt = detect_format(data)
    if fmt is None:
        raise UnsupportedFormat()
    doc = _extract(data, fmt, convert_timeout)
    public_format = fmt if fmt in ("pdf", "docx") else "doc"
    lines = doc.lines
    if fmt == "pdf" and sum(len(re.findall(r"[^\W\d_]", l.text)) for l in lines) < MIN_PDF_LETTERS:
        lines = []

    def finish(result: ParseResult) -> ParseResult:
        result.meta.duration_ms = int((time.monotonic() - started) * 1000)
        log.info("parse format=%s status=%s duration_ms=%d", public_format, result.status, result.meta.duration_ms)
        return result

    if not lines:
        code = "scanned_pdf" if fmt == "pdf" else "empty_document"
        meta = Meta(format=public_format, language="es", pages=doc.pages, columns=doc.columns,
                    parser_version=__version__)
        return finish(ParseResult(status="unreadable", meta=meta, warnings=[ParseWarning(code=code)]))

    sections = split_sections(lines)
    header = sections.header if sections.found_any else lines
    personal = sections.parts.get("personal", [])
    contact, headline = parse_header(header)
    for line in personal:
        contact.email = contact.email or find_email(line.text)
    contact.phone = contact.phone or best_phone(personal)
    # El país por defecto nunca sale del lugar de nacimiento ni de la nacionalidad.
    # Tampoco del renglón del nombre: "Guerrero" o "Hidalgo" son apellidos comunes, no lugares.
    home = [l for l in header + personal
            if not BIRTH_OR_ORIGIN.search(fold(l.text)) and l.text != contact.name
            and not (looks_like_name(l.text) and not is_place_line(l.text))]
    fallback = next((p for p in (find_place(l.text) for l in home) if p is not None), None)
    if fallback is None:
        # Sin comas, solo en renglones que parecen dirección: "Calle 5 Col. Centro Pachuca Hgo.".
        addresses = [l for l in home if is_address_line(l.text) or re.search(r"\b(c\.?\s?p|col)\b", fold(l.text))]
        fallback = next((p for p in (find_place_loose(l.text) for l in addresses) if p is not None), None)

    summary_lines = sections.parts.get("summary", [])
    summary = " ".join(l.text for l in summary_lines) or None
    experience = parse_experience(sections.parts.get("experience", []), fallback, today)
    education = parse_education(sections.parts.get("education", []), fallback, today)
    extraction = {"experience": "rules", "education": "rules", "contact": "rules", "headline": "rules",
                  "summary": "rules"}
    llm_warnings: list[ParseWarning] = []
    llm_failed = False
    targets = _llm_targets(sections, experience, education, llm, llm_mode, llm_threshold)
    if targets:
        try:
            llm_education, llm_experience, llm_warnings, header_data, header_warnings = _ask_llm(
                llm, lines, today, "\n".join(l.text for l in summary_lines) or None)
        except LLMError:
            llm_failed = True
        else:
            if "experience" in targets:
                experience, extraction["experience"] = llm_experience, "llm"
            if "education" in targets:
                education, extraction["education"] = llm_education, "llm"
            llm_warnings = [w for w in llm_warnings if w.section in targets] + header_warnings
            # Nombre, título y resumen del LLM cuando son válidos; si no, quedan los de las reglas.
            if header_data["name"]:
                contact.name, extraction["contact"] = header_data["name"], "llm"
            if header_data["headline"]:
                headline, extraction["headline"] = header_data["headline"], "llm"
            if header_data["summary"]:
                summary, extraction["summary"] = header_data["summary"], "llm"
            if fallback is not None:
                # Como en las reglas: una entrada sin lugar hereda el país del encabezado del CV.
                for entry in (experience if "experience" in targets else []) + (education if "education" in targets else []):
                    if entry.country_code is None and entry.city is None:
                        entry.country_code = fallback.country_code

    section_scores = [s for s in (_mean([e.confidence for e in education]) if education else None,
                                  _mean([e.confidence for e in experience]) if experience else None) if s is not None]
    confidence = Confidence(
        summary=SUMMARY_CONFIDENCE if summary else 0.0,
        education=_mean([e.confidence for e in education]),
        experience=_mean([e.confidence for e in experience]),
        overall=_mean(section_scores),
    )
    warnings = [] if sections.found_any else [ParseWarning(code="no_sections")]
    if llm_failed:
        warnings.append(ParseWarning(code="llm_unavailable"))
    warnings += llm_warnings
    if (llm_failed or not sections.found_any or not (education or experience)
            or confidence.overall < OK_THRESHOLD):
        status = "partial"
    else:
        status = "ok"
    meta = Meta(
        format=public_format,
        language=detect_language(" ".join(l.text for l in lines)),
        pages=doc.pages,
        columns=doc.columns,
        sections=[s for s in sections.order if s != "other"],
        parser_version=__version__,
        extraction=extraction,
    )
    extracted = Extracted(contact=contact, headline=headline, summary=summary, education=education,
                          experience=experience)
    return finish(ParseResult(status=status, meta=meta, warnings=warnings, confidence=confidence,
                              extracted=extracted))


def _llm_targets(sections, experience, education, llm, mode: str, threshold: float) -> list[str]:
    """Secciones que irán al LLM: todas en modo always; en low_confidence, las dudosas o vacías."""
    if llm is None:
        return []
    if mode == "always" or not sections.found_any:
        return ["experience", "education"]
    targets = []
    for name, entries in (("experience", experience), ("education", education)):
        has_text = bool(sections.parts.get(name))
        if (entries and _mean([e.confidence for e in entries]) < threshold) or (has_text and not entries):
            targets.append(name)
    return targets


def _ask_llm(llm, lines, today: date | None, summary_text: str | None = None):
    started = time.monotonic()
    try:
        result = llm.extract(redact("\n".join(l.text for l in lines)))
        if not isinstance(result.data.get("education"), list) or not isinstance(result.data.get("experience"), list):
            raise LLMError("unexpected_shape")
    except LLMError as exc:
        log.warning("llm provider=%s model=%s error=%s", llm.provider, llm.model, exc)
        raise
    log.info("llm provider=%s model=%s input_tokens=%d output_tokens=%d duration_ms=%d", llm.provider, llm.model,
             result.input_tokens, result.output_tokens, int((time.monotonic() - started) * 1000))
    source = "\n".join(l.text for l in lines)
    education, experience, warnings = validate_response(result.data, source, today)
    header, header_warnings = validate_header(result.data, source, summary_text)
    return education, experience, warnings, header, header_warnings
