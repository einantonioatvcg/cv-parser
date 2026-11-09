"""Datos de contacto y título del encabezado del CV."""

from __future__ import annotations

import re

from cv_parser.levels import detect_level
from cv_parser.lines import Line, fold, join_wrapped
from cv_parser.models import Contact
from cv_parser.places import is_place_line

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
PHONE = re.compile(r"(?<![\w])(\+?\d[\d\s().-]{8,20}\d)(?![\w])")
URL = re.compile(r"(https?://|www\.|linkedin\.com|github\.com)", re.I)
LABELS = re.compile(
    r"^(curriculum vitae|curriculum|curriculo|cv|hoja de vida|resume|resumen curricular|solicitud de empleo)$"
)
ADDRESS_WORDS = re.compile(
    r"(?<![a-z])(calle|av|avenida|blvd|boulevard|col|colonia|fracc|fraccionamiento|c\.?p|no|num|street|st|ave|apt|suite)(?![a-z])"
)
CONTACT_WORDS = re.compile(r"^(tel|telefono|cel|celular|movil|phone|mobile|whatsapp|email|e-mail|correo|linkedin)")
MAX_HEADLINE_WORDS = 8
# Palabras de puesto u oficio: un título solo se acepta si trae una (o un grado de estudios).
TITLE_WORDS = re.compile(
    r"(?<![a-z])(asistente|auxiliar|gerente|subgerente|jefe|jefa|coordinador|coordinadora|director|directora|"
    r"supervisor|supervisora|ingenier[oa]|licenciad[oa]|contador|contadora|tecnic[oa]|analista|ejecutiv[oa]|"
    r"vendedor|vendedora|cajer[oa]|administrador|administradora|desarrollador|desarrolladora|programador|"
    r"programadora|disenador|disenadora|enfermer[oa]|maestr[oa]|profesor|profesora|docente|operador|operadora|"
    r"recepcionista|secretari[oa]|abogad[oa]|arquitect[oa]|medic[oa]|psicolog[oa]|chofer|conductor|"
    r"almacenista|capturista|promotor|promotora|mesero|mesera|cocinero|cocinera|ayudante|consultor|consultora|"
    r"especialista|representante|agente|asesor|asesora|mecanico|electricista|soldador|pasante|egresad[oa]|"
    r"manager|assistant|engineer|developer|analyst|designer|accountant|consultant|specialist|technician|"
    r"coordinator|supervisor|director|officer|representative|driver|nurse|teacher|cashier|receptionist)(?![a-z])"
)
NOT_NAME_WORDS = re.compile(
    r"(?<![a-z])(datos|curriculum|antecedentes|informacion|identificacion|perfil|objetivo|experiencia|"
    r"educacion|formacion|puesto|empresa|direccion|domicilio|telefono|correo)(?![a-z])"
)
ID_LABELS = re.compile(r"(?<![a-z])(nss|imss|ine|curp|rfc|folio|cedula|isbn|issn|clave|pasaporte|passport|"
                       r"licencia|cuenta|clabe|tarjeta|id|no\. de empleado|matricula)(?![a-z])")
PHONE_LABELS = re.compile(r"(?<![a-z])(tel|telefono|cel|celular|movil|phone|mobile|whatsapp|contacto)(?![a-z])")
FIELD_LABEL = re.compile(r"^[^\W\d_]+(?:[ .][^\W\d_]+){0,2}\.?\s*:")
NAME_PREFIX = re.compile(r"^(curr[ií]cul(?:um|o)(?: vitae)?|cv|hoja de vida|resum[eé])\s*(?:de|of|:|-)?\s+", re.I)


def find_email(text: str) -> str | None:
    m = EMAIL.search(text)
    return m.group(0).rstrip(".") if m else None


def find_phone(text: str) -> str | None:
    if ID_LABELS.search(fold(text)):
        return None
    for m in PHONE.finditer(text):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if 10 <= len(digits) <= 15 and not re.search(r"(19|20)\d{2}\s*-\s*(19|20)\d{2}", raw):
            return ("+" if raw.startswith("+") else "") + digits
    return None


def is_contact_line(text: str) -> bool:
    folded = fold(text)
    return bool(EMAIL.search(text) or find_phone(text) or URL.search(text) or CONTACT_WORDS.match(folded))


def is_address_line(text: str) -> bool:
    folded = fold(text)
    return "#" in text or bool(ADDRESS_WORDS.search(folded) and re.search(r"\d", text))


def looks_like_name(text: str) -> bool:
    words = text.split()
    if not (2 <= len(words) <= 6) or re.search(r"[\d@#|/:•]", text) or text.rstrip().endswith("."):
        return False
    if not all(w[0].isalpha() for w in words):
        return False
    folded = fold(text)
    if not text[0].isupper() or NOT_NAME_WORDS.search(folded) or TITLE_WORDS.search(folded) or detect_level(text):
        return False
    return True


def _is_title(text: str) -> bool:
    if len(text.split()) > MAX_HEADLINE_WORDS or re.search(r"\d|@|:", text) or FIELD_LABEL.match(text):
        return False
    return bool(TITLE_WORDS.search(fold(text)) or detect_level(text))


def parse_header(header: list[Line]) -> tuple[Contact, str | None]:
    """Devuelve el contacto y el título (la primera línea tras el nombre que no sea contacto, dirección ni lugar)."""
    contact = Contact(phone=best_phone(header))
    for line in header:
        contact.email = contact.email or find_email(line.text)

    candidates = [
        Line(text=NAME_PREFIX.sub("", line.text), size=line.size, bold=line.bold, gap_before=line.gap_before)
        for line in join_wrapped(header)
        if not is_contact_line(line.text) and not LABELS.match(fold(line.text).strip(" :."))
    ]
    names = [i for i, line in enumerate(candidates) if looks_like_name(line.text)]
    if not names:
        return contact, None
    biggest = max(candidates[i].size for i in names)
    # Si el formato distingue una línea más grande, esa es el nombre; si no, la primera.
    name_index = next(i for i in names if candidates[i].size == biggest)
    contact.name = candidates[name_index].text

    # Título: solo la línea pegada al nombre (después o antes) que parezca puesto o grado.
    headline = None
    for j in (name_index + 1, name_index - 1):
        if 0 <= j < len(candidates) and _is_title(candidates[j].text):
            headline = candidates[j].text.strip(" |-–")
            break
    return contact, headline


def best_phone(lines: list[Line]) -> str | None:
    """Prefiere un teléfono en una línea rotulada como teléfono; nunca uno rotulado como identificador."""
    labelled = [l for l in lines if PHONE_LABELS.search(fold(l.text))]
    for line in labelled + [l for l in lines if l not in labelled]:
        phone = find_phone(line.text)
        if phone:
            return phone
    return None
