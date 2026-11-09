"""Separación de empleos y estudios usando los rangos de fechas como ancla."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from cv_parser.dates import PERSONAL_RE, DateRange, find_date_range, find_date_span
from cv_parser.header import TITLE_WORDS
from cv_parser.levels import detect_level
from cv_parser.lines import Line, fold, fold_map, join_wrapped, normalize_text
from cv_parser.models import Education, Experience
from cv_parser.places import Place, is_place_line, split_place

# Viñetas: símbolos (incluidos los de fuentes de símbolos en el área de uso privado), guion pegado,
# "o " y listas numeradas a mano.
BULLET = re.compile(
    r"^\s*(?:\d{1,2}[.)-]\s+|o\s+(?=\w)|[\uE000-\uF8FF\-•·*▪●◦‣➢➤►✓✔→–—❖◆◇■□➔⇒✗✘♦]+\s*)"
)
_LABEL_WORDS = r"(?:funciones|actividades|tareas|responsabilidades|logros|duties|responsibilities|achievements|tasks)"
_LABEL_TAIL = r"(?:\s+(?:o|y|y/o|e|and|realizadas|principales|desempenadas|a cargo|" + _LABEL_WORDS + r"))*"
LABEL = re.compile(r"^\W*(?:principales\s+)?" + _LABEL_WORDS + _LABEL_TAIL + r"\s*:?\s*$")
LABEL_PREFIX = re.compile(r"^(?:principales\s+)?" + _LABEL_WORDS + _LABEL_TAIL.replace("a cargo", "a cargo") + r"\s*:\s*", re.I)
PHONE_FRAGMENT = re.compile(r"\s*(?:\b(?:tel|tel[eé]fono|cel|celular|phone)\b\.?\s*:?\s*)?\(?\+?\d[\d\s().\-–]{6,}\d\)?", re.I)
PAGE_FOOTER = re.compile(r"^(?:pagina|page|hoja)\s*\d+(?:\s*(?:de|of)\s*\d+)?$")
DATE_LEFTOVER = re.compile(r"^(?:de|desde|from|periodo|period|fecha|dates?)\s*:?\s*$|^[\s|,;:()\[\]/·•–—-]*$", re.I)
COMPANY = re.compile(
    r"(?<![a-z])(s\.? ?a\.?(?: de c\.? ?v\.?)?|s\.? de r\.? ?l\.?(?: de c\.? ?v\.?)?|s\.? ?c\.|s\.? ?a\.? ?p\.? ?i\.?|"
    r"inc|llc|ltd|ltda|corp|corporation|corporativo|company|co\.|gmbh|grupo|group|hospital|clinica|clinic|"
    r"farmacia|pharmacy|tienda|store|restaurante|restaurant|hotel|banco|bank|despacho|consultores|consulting|"
    r"servicios|services|industrias|industries|comercializadora|distribuidora|constructora|laboratorio|"
    r"laboratorios|gobierno|secretaria|ayuntamiento|municipio|universidad|colegio|escuela|instituto)s?(?![a-z])"
)
INSTITUTION = re.compile(
    r"(?<![a-z])(universidad|university|univ\.|instituto|institute|colegio|college|escuela|school of|"
    r"tecnologico|technological|politecnico|polytechnic|academia|academy|centro de estudios|centro universitario|"
    r"preparatoria|prepa|conalep|cbtis|cetis|cecyt|cobach|unam|ipn|itesm|iteso|uag|udg|uanl|univa|uvm|unitec|"
    r"tec de monterrey|facultad|faculty)(?![a-z])"
)
INLINE_SPLIT = re.compile(r"\s*[|•·]\s*|\s+[-–—]\s+|\s+@\s+|,\s+")
MAX_SHORT_WORDS = 11
FIELD = re.compile(r"^\s*([^\W\d_][\w./ ]{1,30}?)\s*:\s*(.*)$")
FIELD_ROLES = {
    "position": {"puesto", "cargo", "cargo ocupado", "puesto desempenado", "position", "job title", "rol", "puesto ocupado"},
    "company": {"empresa", "compania", "company", "employer", "razon social", "negocio", "lugar de trabajo"},
    "institution": {"escuela", "institucion", "universidad", "plantel", "centro educativo", "school", "institution",
                    "nombre de la escuela", "nombre y tipo del centro", "colegio", "centro de estudios"},
    "level": {"carrera", "grado", "titulo", "nivel", "adquirido", "estudios", "degree", "grado obtenido",
              "calificacion obtenida", "nivel academico", "nivel de estudios", "titulo obtenido"},
    "place": {"lugar", "direccion", "ubicacion", "domicilio", "ciudad", "localidad"},
    "drop": {"jefe inmediato", "jefe directo", "telefono", "tel", "motivo de salida", "motivo de separacion",
             "sueldo", "salario", "documento recibido", "docuemnto recibido", "periodo", "duracion", "proyecto",
             "horario", "referencia", "supervisor", "contacto", "fechas", "fecha"},
}
COURSE = re.compile(r"(?<![a-z])(curso|taller|diplomado|especialidad de|capacitacion|licencia|practicas|"
                    r"servicio social|certificad|mencion|seminario|congreso|ponencia|residencia)")
ACTION_START = re.compile(
    r"^(?:manejo|atencion|control|apoyo|apoyar|realizar|realizacion|realice|elaboracion|elaborar|elabore|"
    r"supervision|supervisar|captura|capturar|cobranza|gestion|revision|revisar|registro|archivo|limpieza|"
    r"acomodo|atender|atendi|entrega|entregar|promover|promocion|brindar|trato|generacion|tramites?|"
    r"inventarios?|arqueo|apertura|cierre|asesoria|asesorar|seguimiento|recorte|motivo|contrato por|"
    r"se\s|hacia|hice|trabaje|labore|encargad[oa] de|responsable de|experiencia en|experiencia de|"
    r"check list|aplicacion|implementacion|desarrollo de|coordinacion de|preparacion|recepcion de|curse|estudie)(?![a-z])"
)
DURATION = re.compile(r"^\(?\s*\d+\s*(?:anos?|meses|mes|dias?|semanas?)(?:\s*(?:y\s*)?\d+\s*(?:anos?|meses|mes|dias?|semanas?))*\s*\.?\s*\)?$")
SCHOOL_START = {"primaria", "secundaria", "preparatoria", "bachillerato"}


def _field(text: str) -> tuple[str | None, str]:
    """"PUESTO: Cajera" -> ("position", "Cajera"). Un rótulo desconocido deja la línea igual."""
    m = FIELD.match(text)
    if not m:
        return None, text
    label = fold(m.group(1)).strip(" .")
    for role, labels in FIELD_ROLES.items():
        if label in labels:
            return role, m.group(2).strip()
    return None, text


@dataclass
class _Item:
    line: Line
    date: DateRange | None = None
    pieces: list[str] = field(default_factory=list)   # texto que acompaña a la fecha en su línea
    kind: str = "short"                                # short, desc, date


@dataclass
class _Block:
    before: list[_Item] = field(default_factory=list)
    date_item: _Item | None = None
    after: list[_Item] = field(default_factory=list)


def _is_bullet(text: str) -> bool:
    return bool(BULLET.match(text))


def _strip_bullet(text: str) -> str:
    return BULLET.sub("", text, count=1).strip()


def _split_date(line: Line, today: date | None) -> _Item | None:
    text = BULLET.sub("", normalize_text(line.text), count=1)
    found = find_date_span(text, today)
    if found is not None:
        rng, a, b = found
        rest = [text[:a], text[b:]]
        bare_year = rng.end is None and not rng.is_current and rng.start.month is None
        separated = text[:a].rstrip().endswith(tuple("|,;(-–—")) or text[b:].lstrip().startswith(tuple("|,;)-–—"))
        if bare_year and "".join(rest).strip() and not separated and a > 0:
            return None   # "Curso de Excel 2019"; en cambio "2003 PREPARATORIA" sí es fecha
    else:
        # Fecha suelta en un trozo separado por coma o barra: "Bachelor of Arts, University of Texas, 2015".
        pieces = [p for p in re.split(r"\s*[|;]\s*|,\s*", text) if p.strip()]
        rng = None
        rest = []
        for piece in pieces:
            hit = find_date_span(piece, today) if rng is None else None
            if hit and DATE_LEFTOVER.match(piece[:hit[1]] + piece[hit[2]:]):
                rng = hit[0]
            else:
                rest.append(piece)
        if rng is None:
            return None
        rest = [", ".join(rest)]
    pieces = []
    for chunk in rest:
        chunk = re.sub(r"^\s*(?:de|desde|from|periodo|period)\s*:?\s*$", "", chunk.strip(), flags=re.I)
        chunk = re.sub(r"\s*(?:de|del|desde|from)$", "", chunk.strip(" |,;:()[]-–—·•"), flags=re.I)
        chunk = chunk.strip(" |,;:()[]-–—·•")
        if chunk and not DATE_LEFTOVER.match(chunk):
            pieces.extend(p for p in re.split(r"\s*[|•·]\s*", chunk) if p.strip())
    return _Item(line=line, date=rng, pieces=pieces, kind="date")


def _classify(line: Line) -> str:
    text = line.text
    if _is_bullet(text):
        return "desc"
    folded = fold(text)
    if LABEL.match(folded):
        return "label"
    if COMPANY.search(folded) or INSTITUTION.search(folded) or is_place_line(text) or detect_level(text):
        return "short"
    words = len(text.split())
    if words <= MAX_SHORT_WORDS and split_place(text)[1] is not None:
        return "short"  # "Refrescos Azules - Los Mochis, Sin.": termina en lugar, es encabezado de la entrada
    if ACTION_START.match(folded):
        return "desc"   # "Manejo de caja", "Se terminó la obra": funciones, aunque no lleven viñeta
    if words <= 8 and (line.bold or TITLE_WORDS.search(folded)):
        return "short"  # título de puesto aunque empiece con minúscula
    if text[:1].islower() or words > MAX_SHORT_WORDS or (words >= 5 and text.rstrip().endswith(".")):
        return "desc"
    return "short"


def _bold_titles(lines: list[Line], today: date | None) -> bool:
    """La sección distingue títulos en negrita de renglones normales (y no todo es negrita)."""
    plain = [l for l in lines if not _is_bullet(l.text) and find_date_range(l.text, today) is None]
    bold = sum(1 for l in plain if l.bold)
    return bold >= 2 and len(plain) - bold >= 2


def _items(lines: list[Line], today: date | None) -> list[_Item]:
    items = []
    bold_titles = _bold_titles(lines, today)
    after_date = False
    for line in join_wrapped(lines, _is_bullet, lambda t: find_date_range(t, today) is not None):
        folded = fold(line.text)
        if PAGE_FOOTER.match(folded) or (":" in folded and PERSONAL_RE.search(folded)):
            continue   # pie de página o dato personal ("Edad: 31 años"): nunca es parte de una entrada
        item = _split_date(line, today)
        if item is not None and _is_bullet(line.text) and item.date.end is None and not item.date.is_current:
            item = None   # "- Reconocimiento 2020" es una función, no una fecha de la entrada
        if item is None:
            item = _Item(line=line, kind=_classify(line))
            if bold_titles and item.kind == "short":
                if line.bold:
                    after_date = False
                elif after_date and not _signal(line.text) and not is_place_line(line.text):
                    item.kind = "desc"   # tras la fecha, un renglón sin negrita ni señal es una función
        else:
            after_date = True
        if item.kind != "label":
            items.append(item)
    return items


def _gap_blocks(items: list[_Item]) -> list[list[_Item]]:
    blocks: list[list[_Item]] = []
    for item in items:
        if not blocks or item.line.gap_before:
            blocks.append([])
        blocks[-1].append(item)
    return blocks


def _split_between(between: list[_Item], k_before: int) -> int:
    """Índice donde empiezan las líneas de la entrada siguiente en el tramo entre dos fechas."""
    for i in range(len(between) - 1, 0, -1):
        if between[i].line.gap_before and all(it.kind == "short" for it in between[i:]):
            return i
    if between and between[0].line.gap_before and all(it.kind == "short" for it in between):
        return 0
    i = len(between)
    taken = 0
    while i > 0 and between[i - 1].kind == "short":
        is_place = is_place_line(between[i - 1].line.text)
        if not is_place and taken >= max(k_before, 1):
            break
        taken += 0 if is_place else 1
        i -= 1
    while i < len(between) and is_place_line(between[i].line.text):
        i += 1   # un lugar al inicio del tramo pertenece a la entrada anterior
    return i


def _segment(items: list[_Item]) -> list[_Block]:
    anchors = [i for i, it in enumerate(items) if it.kind == "date"]
    if not anchors:
        return [_Block(before=b) for b in _gap_blocks(items)]

    blocks: list[_Block] = []
    first = anchors[0]
    head = items[:first]
    head_blocks = _gap_blocks(head)
    # Bloques separados por renglón en blanco antes de la primera fecha son entradas sin fecha;
    # el último bloque son las líneas iniciales de la primera entrada.
    if items[first].line.gap_before and head:
        undated, lead = head_blocks, []
    else:
        undated, lead = head_blocks[:-1], (head_blocks[-1] if head_blocks else [])
    blocks += [_Block(before=b) for b in undated]
    lead = [it for it in lead if it.kind == "short"] if lead else []
    date_first = not lead
    k_before = len([it for it in lead if not is_place_line(it.line.text)])

    for n, anchor in enumerate(anchors):
        block = _Block(before=lead, date_item=items[anchor])
        nxt = anchors[n + 1] if n + 1 < len(anchors) else None
        if nxt is not None:
            between = items[anchor + 1:nxt]
            cut = len(between) if date_first else _split_between(between, k_before)
            block.after = between[:cut]
            lead = between[cut:]
        else:
            tail = items[anchor + 1:]
            extra: list[list[_Item]] = []
            if not date_first:
                cut = _split_between(tail, 0) if any(it.line.gap_before for it in tail[1:]) else len(tail)
                if cut < len(tail) and tail[cut].line.gap_before:
                    extra = _gap_blocks(tail[cut:])
                    tail = tail[:cut]
            block.after = tail
            blocks.append(block)
            blocks += [_Block(before=b) for b in extra]
            break
        blocks.append(block)
    return blocks


def _signal(text: str) -> bool:
    folded = fold(text)
    return bool(COMPANY.search(folded) or INSTITUTION.search(folded) or detect_level(text))


def _weight(text: str) -> int:
    """Cuántos datos clave aporta una línea: "Bachillerato – CBTIS 52" aporta dos."""
    if is_place_line(text):
        return 0
    return 2 if len([p for p in INLINE_SPLIT.split(split_place(text)[0], maxsplit=1) if p.strip()]) == 2 else 1


def _resplit(block: _Block) -> list[_Block]:
    if block.date_item is not None:
        have = sum(_weight(it.line.text) for it in block.before if it.kind == "short")
        pieces = block.date_item.pieces
        have += 2 if len(pieces) >= 2 else (_weight(pieces[0]) if pieces else 0)
        stream, head = block.after, block
        head.after = []
        target = head.after
    else:
        have, stream, head = 0, block.before, block
        head.before = []
        target = head.before
    out = [head]
    for i, it in enumerate(stream):
        if it.kind == "short" and have >= 2 and not is_place_line(it.line.text):
            run = []
            for nxt in stream[i:]:
                if nxt.kind != "short":
                    break
                run.append(nxt)
            if any(_signal(r.line.text) for r in run[:2]):
                new = _Block()
                out.append(new)
                target, have = new.before, 0
        target.append(it)
        if it.kind == "short":
            have += _weight(it.line.text)
    return out


@dataclass
class _Parts:
    candidates: list[str]
    roles: list[str | None]
    description: list[str]
    place: Place | None
    date: DateRange | None


def _blocks(lines: list[Line], today: date | None) -> list[_Block]:
    return [part for block in _segment(_items(lines, today)) for part in _resplit(block)]


def _parts(block: _Block) -> _Parts:
    texts: list[str] = []
    description: list[str] = []
    items = block.before + ([block.date_item] if block.date_item else []) + block.after
    for it in items:
        if it.kind == "date":
            texts.extend(it.pieces)
        elif it.kind == "short" and not description:
            texts.append(it.line.text)
        else:
            text = LABEL_PREFIX.sub("", _strip_bullet(it.line.text))
            if not text:
                continue
            if description and not _is_bullet(it.line.text) and it.kind == "desc" and text[:1].islower():
                description[-1] += " " + text
            else:
                description.append(text)
    place = None
    candidates: list[str] = []
    roles: list[str | None] = []
    for text in texts:
        role, text = _field(text)
        if role == "drop" or DURATION.match(fold(text).strip()):
            continue
        text = PHONE_FRAGMENT.sub("", text).strip(" ,;|-–")
        if not text:
            continue
        rest, found = split_place(text)
        if found is not None and place is None:
            place = found
        if role == "place":
            continue
        if found is None:
            rest = text
        if rest and re.search(r"[^\W\d_]{2}", rest) and not LABEL.match(fold(rest).strip(" :")):
            candidates.append(rest)
            roles.append(role)
    return _Parts(candidates, roles, description, place, block.date_item.date if block.date_item else None)


def _mostly_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


def _split_position_at_company(candidates: list[str]) -> list[str]:
    """ "SUBGERENTE DE SUCURSAL en BANCO AZUL SA": un "en" en minúsculas entre texto en mayúsculas separa puesto y empresa."""
    if len(candidates) == 1:
        m = re.search(r"\s+en\s+", candidates[0])
        if m and _mostly_upper(candidates[0][:m.start()]) and _mostly_upper(candidates[0][m.end():]):
            return [candidates[0][:m.start()].strip(), candidates[0][m.end():].strip()]
    return candidates


def _split_at_company_word(candidates: list[str]) -> list[str]:
    """"AUXILIAR DE SUCURSAL BANCO DEL SOL": parte antes de la palabra de empresa si lo anterior es un puesto."""
    if len(candidates) != 1:
        return candidates
    text = candidates[0]
    folded, index = fold_map(text)
    m = COMPANY.search(folded)
    if not m or m.start() == 0:
        return candidates
    cut = index[m.start()]
    head = text[:cut]
    abbrev = re.search(r"(?:\b[^\W\d_]{1,2}\.\s*)+$", head)   # "H. AYUNTAMIENTO"
    if abbrev:
        cut, head = abbrev.start(), head[:abbrev.start()]
    if not head.strip() or not TITLE_WORDS.search(fold(head)) or head.rstrip().endswith((" de", " del", " DE", " DEL")):
        return candidates
    tail = text[cut:]
    # Solo en mayúsculas o con razón social ("BANCO DEL SOL", "Sol S.A."): "Analista Servicios Financieros" no se parte.
    if not (_mostly_upper(text) and len(tail.split()) >= 2) and not re.search(r"s\.?\s?a\.?|s\.?\s?c\.|inc\b|llc\b", fold(tail)):
        return candidates
    return [head.strip(" ,-–"), text[cut:].strip()]


def _split_single(candidates: list[str]) -> list[str]:
    if len(candidates) == 1:
        pieces = [p for p in INLINE_SPLIT.split(candidates[0], maxsplit=1) if p.strip()]
        if len(pieces) == 2:
            return pieces
    return candidates


def _location(parts: _Parts, fallback: Place | None) -> tuple[str | None, str | None]:
    if parts.place is not None:
        return parts.place.city, parts.place.country_code
    return None, fallback.country_code if fallback else None


def _too_long(*values: str | None) -> bool:
    """Un dato clave de más de 8 palabras o 70 caracteres suele traer una función pegada."""
    return any(v and (len(v.split()) > 8 or len(v) > 70) for v in values)


def _date_points(rng: DateRange | None) -> float:
    if rng is None:
        return 0.0
    return 0.3 if (rng.end is not None or rng.is_current) else 0.15


def _experience_confidence(rng, position, company, leftovers, roles) -> float:
    """Señales: rango de fechas completo, empresa con señal de empresa, puesto con palabra de puesto, sin sobrantes."""
    labelled = set(r for r in roles if r)
    score = _date_points(rng)
    if company:
        score += 0.25 if (COMPANY.search(fold(company)) or "company" in labelled) else 0.15
    if position:
        score += 0.25 if (TITLE_WORDS.search(fold(position)) or "position" in labelled) else 0.15
    if leftovers:
        score -= 0.15
    elif position and company:
        score += 0.1
    if _too_long(position, company):
        score -= 0.3
    return round(min(max(score, 0.0), 1.0), 2)


def _education_confidence(rng, match, institution, leftovers) -> float:
    """Señales: fecha, nivel reconocido, institución con señal de escuela, sin sobrantes."""
    score = 0.3 if rng else 0.0   # en estudios una sola fecha (la de término) basta
    if match:
        score += 0.3
    if institution:
        score += 0.25 if INSTITUTION.search(fold(institution)) else 0.15
    if leftovers:
        score -= 0.15
    elif match and institution:
        score += 0.1
    if _too_long(institution, match.level_text if match else None):
        score -= 0.3
    return round(min(max(score, 0.0), 1.0), 2)


def parse_experience(lines: list[Line], fallback: Place | None, today: date | None = None) -> list[Experience]:
    entries: list[Experience] = []
    company_first: bool | None = None
    for block in _blocks(lines, today):
        parts = _parts(block)
        if "position" in parts.roles or "company" in parts.roles:
            by_role = {r: c for c, r in zip(parts.candidates, parts.roles) if r}
            others = [c for c, r in zip(parts.candidates, parts.roles) if not r]
            position = by_role.get("position") or (others.pop(0) if others and "position" not in by_role else None)
            company = by_role.get("company") or (others.pop(0) if others and "company" not in by_role else None)
            city, country = _location(parts, fallback)
            rng = parts.date
            description = "\n".join(others + parts.description) or None
            confidence = _experience_confidence(rng, position, company, others, parts.roles)
            entries.append(Experience(
                position=position, company=company, city=city, country_code=country,
                start=rng.start if rng else None, end=rng.end if rng else None,
                is_current=rng.is_current if rng else False, description=description,
                confidence=round(confidence, 2),
            ))
            continue
        candidates = _split_single(_split_at_company_word(_split_position_at_company(parts.candidates)))
        if not candidates and parts.date is None:
            continue
        # Una sola línea con señal de empresa y sin palabra de puesto: es la empresa.
        only_company = (len(candidates) == 1 and bool(COMPANY.search(fold(candidates[0])))
                        and not TITLE_WORDS.search(fold(candidates[0])))
        company_idx = [i for i, c in enumerate(candidates) if COMPANY.search(fold(c))]
        title_idx = [i for i, c in enumerate(candidates[:2]) if TITLE_WORDS.search(fold(c))]
        if len(company_idx) != 1 and len(title_idx) == 1 and len(candidates) > 1:
            other = 1 - title_idx[0]
            company_idx = [other] if other < len(candidates) else company_idx
        if only_company:
            position, company, extra = None, candidates[0], []
        elif len(company_idx) == 1 and len(candidates) > 1:
            company = candidates[company_idx[0]]
            others = [c for i, c in enumerate(candidates) if i != company_idx[0]]
            position = others[0]
            extra = others[1:]
            if company_first is None:
                company_first = company_idx[0] == 0
        elif company_first and len(candidates) > 1:
            company, position, extra = candidates[0], candidates[1], candidates[2:]
        else:
            position = candidates[0] if candidates else None
            company = candidates[1] if len(candidates) > 1 else None
            extra = candidates[2:]
        city, country = _location(parts, fallback)
        rng = parts.date
        description = "\n".join(extra + parts.description) or None
        confidence = _experience_confidence(rng, position, company, extra, parts.roles)
        entries.append(Experience(
            position=position, company=company, city=city, country_code=country,
            start=rng.start if rng else None, end=rng.end if rng else None,
            is_current=rng.is_current if rng else False, description=description,
            confidence=round(confidence, 2),
        ))
    return entries


def parse_education(lines: list[Line], fallback: Place | None, today: date | None = None) -> list[Education]:
    entries: list[Education] = []
    for block in _blocks(lines, today):
        parts = _parts(block)
        roles = parts.roles if len(parts.candidates) > 1 or any(parts.roles) else [None]
        candidates = parts.candidates if any(roles) else _split_single(parts.candidates)
        if len(roles) != len(candidates):
            roles = [None] * len(candidates)
        if not candidates:
            continue   # solo una fecha: no hay estudio que reportar
        levels = [detect_level(c) for c in candidates]
        if not any(levels) and any(COURSE.search(fold(c)) for c in candidates):
            continue   # cursos, licencias y prácticas no son estudios formales
        if not any(levels) and not any(INSTITUTION.search(fold(c)) for c in candidates) and "level" not in roles:
            continue
        is_inst = [bool(INSTITUTION.search(fold(c))) or r == "institution" for c, r in zip(candidates, roles)]
        level_idx = next((i for i, r in enumerate(roles) if r == "level"), None)
        if level_idx is None:
            level_idx = next((i for i, m in enumerate(levels) if m and not is_inst[i]), None)
        if level_idx is None:
            level_idx = next((i for i, m in enumerate(levels) if m), None)
        inst_idx = next((i for i, flag in enumerate(is_inst) if flag and i != level_idx), None)
        if inst_idx is None and level_idx is not None and is_inst[level_idx]:
            inst_idx = level_idx
        if inst_idx is None:
            inst_idx = next((i for i in range(len(candidates)) if i != level_idx), None)
        match = levels[level_idx] if level_idx is not None else None
        level_text = match.level_text if match else None
        if match and ACTION_START.match(fold(candidates[level_idx])):
            level_text = None   # "Curse la primaria": el nivel vale, el texto es prosa y no es el nombre del grado
        if match is None:
            level_text = next((c for i, c in enumerate(candidates) if i != inst_idx), None)
        institution = candidates[inst_idx] if inst_idx is not None else None
        if match and inst_idx == level_idx:
            institution = match.level_text
        if match and institution is None and level_idx is not None:
            # "Secundaria ESTIC No. 45": nivel seguido del nombre de la escuela en siglas, número o comillas.
            head, _, rest = candidates[level_idx].partition(" ")
            first = rest.split()[0] if rest.split() else ""
            if fold(head) in SCHOOL_START and ((first.isupper() and len(first) >= 3) or first[:1] in "#“\"" or first == "No."):
                level_text, institution = head, rest.strip()

        rng = parts.date
        start, end, current = (rng.start, rng.end, rng.is_current) if rng else (None, None, False)
        if rng and rng.end is None and not rng.is_current:
            start, end = None, rng.start   # una sola fecha en estudios es la de término
        city, country = _location(parts, fallback)
        leftovers = [c for i, c in enumerate(candidates) if i not in (level_idx, inst_idx)]
        confidence = _education_confidence(rng, match, institution, leftovers)
        entries.append(Education(
            level=match.level if match else None, level_text=level_text,
            is_technical=match.is_technical if match else False, area_text=match.area_text if match else None,
            institution=institution, city=city, country_code=country, start=start, end=end,
            is_current=current, confidence=round(confidence, 2),
        ))
    return entries
