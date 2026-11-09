"""Quita del texto lo que nunca debe salir hacia un proveedor de LLM."""

from __future__ import annotations

import re

from cv_parser.header import EMAIL, find_phone

SEP = r"[\s-]?"
CURP = re.compile(rf"\b[A-Z]{{4}}{SEP}\d{{6}}{SEP}[HM][A-Z]{{5}}{SEP}[A-Z0-9]\d\b", re.I)
RFC = re.compile(rf"\b[A-ZÑ&]{{3,4}}{SEP}\d{{6}}(?:{SEP}[A-Z0-9]{{3}})?\b")
NSS = re.compile(r"(?<!\d)\d{11}(?!\d)")
LABELED_ID = re.compile(r"\b((?i:rfc|curp|nss|imss|ine|clave de elector|no\. de seguro social))\b\.?[ \t]*[:#.]?[ \t]*"
                        r"((?:[A-Z0-9Ñ&]+[ \t-]?){1,5})")
LABELED_PHONE = re.compile(r"\b(tel[eé]fonos?|tel|cel|celular|m[oó]vil|casa|whatsapp|fijo|oficina|phone|mobile)\b"
                           r"\.?\s*:?\s*(\+?\(?\d[\d\s().-]{5,24}\d\)?)", re.I)
PHONE_RUN = re.compile(r"\+?\(?\d[\d\s().-]{8,20}\d\)?")


def _labeled_id(m: re.Match) -> str:
    return f"{m.group(1)}: [dato] " if sum(c.isdigit() for c in m.group(2)) >= 6 else m.group(0)


def _labeled_phone(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(2))
    return f"{m.group(1)}: [telefono]" + ("\n" if m.group(2).endswith("\n") else "") if len(digits) >= 7 else m.group(0)


def redact(text: str) -> str:
    """Reemplaza correos, teléfonos, CURP, RFC y NSS por marcas. Las fechas y el resto del texto no cambian."""
    text = EMAIL.sub("[correo]", text)
    text = LABELED_ID.sub(_labeled_id, text)
    text = CURP.sub("[curp]", text)
    text = RFC.sub("[rfc]", text)
    text = NSS.sub("[nss]", text)
    # Teléfonos rotulados, aunque tengan menos de 10 dígitos o sigan en el renglón siguiente.
    text = LABELED_PHONE.sub(_labeled_phone, text)
    lines = [PHONE_RUN.sub(lambda m: "[telefono]" if find_phone(m.group(0)) else m.group(0), l) for l in text.split("\n")]
    return "\n".join(lines)
