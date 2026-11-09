"""Genera los CVs inventados de tests/fixtures/.

Todos los datos son ficticios y los correos usan el dominio reservado .invalid.
Correr dentro del contenedor: docker compose run --rm api python tests/fixtures/build_fixtures.py
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from docx.shared import Pt
from fpdf import FPDF
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
FONT_DIR = Path("/usr/share/fonts/truetype/liberation")

PEOPLE = {
    "es": {
        "name": "María Fernanda López Hernández",
        "headline": "Asistente Administrativa",
        "location": "Guadalajara, Jalisco, México",
        "contact": "Tel: 33 1234 5678 | maria.lopez@ejemplo.invalid",
        "h_summary": "PERFIL PROFESIONAL",
        "h_experience": "EXPERIENCIA LABORAL",
        "h_education": "FORMACIÓN ACADÉMICA",
        "h_skills": "HABILIDADES",
        "h_languages": "IDIOMAS",
        "summary": "Asistente administrativa con 6 años de experiencia en atención a clientes, facturación y manejo de agenda.",
        "jobs": [
            ("Asistente Administrativa", "Grupo Comercial del Bajío S.A. de C.V.", "Guadalajara, Jalisco",
             "Marzo 2021 - Actualidad",
             ["Gestión de agenda y viajes de la dirección general", "Facturación electrónica y conciliación bancaria"]),
            ("Recepcionista", "Clínica San Rafael", "Zapopan, Jalisco", "Enero 2018 - Febrero 2021",
             ["Atención a pacientes y control de citas"]),
        ],
        "studies": [
            ("Licenciatura en Administración de Empresas", "Universidad de Guadalajara", "Guadalajara, Jalisco",
             "Agosto 2013 - Junio 2017"),
            ("Bachillerato General", "Preparatoria 7", "Guadalajara, Jalisco", "2010 - 2013"),
        ],
        "skills": ["Excel avanzado", "Facturación CFDI", "Atención a clientes"],
        "languages": ["Español nativo", "Inglés intermedio"],
    },
    "en": {
        "name": "Mary Lopez",
        "headline": "Administrative Assistant",
        "location": "Guadalajara, Jalisco, Mexico",
        "contact": "Phone: (33) 1234-5678 | mary.lopez@example.invalid",
        "h_summary": "PROFESSIONAL SUMMARY",
        "h_experience": "WORK EXPERIENCE",
        "h_education": "EDUCATION",
        "h_skills": "SKILLS",
        "h_languages": "LANGUAGES",
        "summary": "Administrative assistant with 6 years of experience in customer service, invoicing and calendar management.",
        "jobs": [
            ("Administrative Assistant", "Grupo Comercial del Bajío S.A. de C.V.", "Guadalajara, Jalisco",
             "March 2021 - Present",
             ["Calendar and travel management for the general director", "Electronic invoicing and bank reconciliation"]),
            ("Receptionist", "San Rafael Clinic", "Zapopan, Jalisco", "January 2018 - February 2021",
             ["Patient reception and appointment scheduling"]),
        ],
        "studies": [
            ("Bachelor of Business Administration", "University of Guadalajara", "Guadalajara, Jalisco",
             "August 2013 - June 2017"),
            ("High School Diploma", "Preparatoria 7", "Guadalajara, Jalisco", "2010 - 2013"),
        ],
        "skills": ["Advanced Excel", "Electronic invoicing", "Customer service"],
        "languages": ["Spanish (native)", "English (intermediate)"],
    },
}


# Bloques: (tipo, texto, espacio_antes). Tipos: name, h (encabezado), b (negrita), t (texto), bullet.
def header_blocks(p):
    return [("name", p["name"], False), ("t", p["headline"], False), ("t", p["location"], False), ("t", p["contact"], False)]


def summary_blocks(p):
    return [("h", p["h_summary"], True), ("t", p["summary"], False)]


def experience_blocks(p):
    out = [("h", p["h_experience"], True)]
    for i, (position, company, place, dates, bullets) in enumerate(p["jobs"]):
        out += [("b", position, i > 0), ("t", f"{company}, {place}", False), ("t", dates, False)]
        out += [("bullet", b, False) for b in bullets]
    return out


def education_blocks(p):
    out = [("h", p["h_education"], True)]
    for i, (level, inst, place, dates) in enumerate(p["studies"]):
        out += [("b", level, i > 0), ("t", f"{inst}, {place}", False), ("t", dates, False)]
    return out


def list_blocks(heading, items):
    return [("h", heading, True)] + [("t", s, False) for s in items]


def side_blocks(p):
    return list_blocks(p["h_skills"], p["skills"]) + list_blocks(p["h_languages"], p["languages"])


def main_blocks(p):
    return summary_blocks(p) + experience_blocks(p) + education_blocks(p)


# ---------- PDF ----------

STYLE = {"name": ("B", 18, 9), "h": ("B", 12, 6), "b": ("B", 11, 5.5), "t": ("", 10, 5), "bullet": ("", 10, 5)}


def new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.add_font("Lib", "", str(FONT_DIR / "LiberationSans-Regular.ttf"))
    pdf.add_font("Lib", "B", str(FONT_DIR / "LiberationSans-Bold.ttf"))
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    return pdf


def write_blocks(pdf: FPDF, blocks, x: float, y: float, width: float) -> float:
    for kind, text, gap in blocks:
        if gap:
            y += 8
        style, size, height = STYLE[kind]
        pdf.set_font("Lib", style, size)
        pdf.set_xy(x, y)
        pdf.multi_cell(width, height, ("• " + text) if kind == "bullet" else text, new_x="LEFT", new_y="NEXT")
        y = pdf.get_y()
    return y


def pdf_one_column(p) -> bytes:
    pdf = new_pdf()
    blocks = header_blocks(p) + main_blocks(p) + side_blocks(p)
    write_blocks(pdf, blocks, 15, 15, 180)
    return bytes(pdf.output())


def pdf_two_columns(p) -> bytes:
    pdf = new_pdf()
    y = write_blocks(pdf, header_blocks(p), 15, 15, 180)
    write_blocks(pdf, side_blocks(p), 15, y, 48)
    write_blocks(pdf, main_blocks(p), 80, y, 115)
    return bytes(pdf.output())


def pdf_scanned() -> bytes:
    img = Image.new("L", (1240, 1754), 255)
    draw = ImageDraw.Draw(img)
    for i, text in enumerate(["CV ESCANEADO", "Persona Inventada", "Cajera 2018 - 2020"]):
        draw.text((120, 150 + i * 60), text, fill=0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.image(buf, x=0, y=0, w=210, h=297)
    return bytes(pdf.output())


def pdf_protected(p) -> bytes:
    from fpdf.enums import EncryptionMethod

    pdf = new_pdf()
    pdf.set_encryption(owner_password="dueno-inventado", user_password="secreta",
                       encryption_method=EncryptionMethod.AES_128)
    write_blocks(pdf, header_blocks(p), 15, 15, 180)
    return bytes(pdf.output())


# ---------- DOCX ----------

def add_par(doc, text: str = "", bold: bool = False, size: float | None = None):
    par = doc.add_paragraph()
    if text:
        run = par.add_run(text)
        run.bold = bold
        if size:
            run.font.size = Pt(size)
    return par


def docx_blocks(doc, blocks):
    for kind, text, gap in blocks:
        if gap:
            add_par(doc)
        if kind == "name":
            add_par(doc, text, bold=True, size=16)
        elif kind == "h":
            add_par(doc, text, bold=True, size=12)
        elif kind == "b":
            add_par(doc, text, bold=True)
        elif kind == "bullet":
            add_par(doc, "- " + text)
        else:
            add_par(doc, text)


def to_bytes(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def docx_paragraphs(p) -> bytes:
    doc = Document()
    docx_blocks(doc, header_blocks(p) + main_blocks(p) + side_blocks(p))
    return to_bytes(doc)


NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def textbox_paragraph(lines: list[str]):
    """Párrafo con un cuadro de texto moderno y su Fallback VML con el mismo contenido."""
    content = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{esc(t)}</w:t></w:r></w:p>" if t else "<w:p/>" for t in lines)
    xml = f"""<w:p {NS}><w:r><mc:AlternateContent>
<mc:Choice Requires="wps"><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="5400000" cy="2200000"/><wp:docPr id="10" name="Cuadro de texto 1"/>
<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="5400000" cy="2200000"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></wps:spPr>
<wps:txbx><w:txbxContent>{content}</w:txbxContent></wps:txbx><wps:bodyPr/></wps:wsp>
</a:graphicData></a:graphic></wp:inline></w:drawing></mc:Choice>
<mc:Fallback><w:pict><v:shape style="width:425pt;height:173pt"><v:textbox><w:txbxContent>{content}</w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>
</mc:AlternateContent></w:r></w:p>"""
    return parse_xml(xml)


def docx_tables_textboxes(p) -> bytes:
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = p["name"]
    docx_blocks(doc, header_blocks(p)[1:] + summary_blocks(p))
    add_par(doc)
    add_par(doc, p["h_experience"], bold=True, size=12)
    table = doc.add_table(rows=0, cols=2)
    for position, company, place, dates, bullets in p["jobs"]:
        cells = table.add_row().cells
        cells[0].text = dates
        cells[1].text = position
        cells[1].add_paragraph(f"{company}, {place}")
        for b in bullets:
            cells[1].add_paragraph("• " + b)
    add_par(doc)
    add_par(doc, p["h_education"], bold=True, size=12)
    lines: list[str] = []
    for i, (level, inst, place, dates) in enumerate(p["studies"]):
        lines += ([""] if i else []) + [level, inst, place, dates]
    doc.element.body.insert(len(doc.element.body) - 1, textbox_paragraph(lines))
    docx_blocks(doc, side_blocks(p))
    return to_bytes(doc)


def docx_empty() -> bytes:
    return to_bytes(Document())


def docx_no_headings() -> bytes:
    doc = Document()
    for text in [
        "Rosa Inventada Pérez",
        "Me gusta trabajar con personas y aprendo rápido cosas nuevas.",
        "Trabajé varios años atendiendo una tienda de mi familia y después ayudé en una papelería del barrio.",
        "Busco un empleo de medio tiempo cerca de mi casa.",
    ]:
        add_par(doc, text)
    return to_bytes(doc)


# ---------- conversiones con LibreOffice ----------

def soffice_convert(data: bytes, suffix: str, target: str) -> bytes:
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / f"entrada{suffix}"
        src.write_bytes(data)
        subprocess.run(
            [binary, "--headless", "--norestore", "--nolockcheck", f"-env:UserInstallation=file://{tmp}/perfil",
             "--convert-to", target, "--outdir", str(tmp_path / "salida"), str(src)],
            check=True, capture_output=True, timeout=120,
        )
        (out,) = (tmp_path / "salida").iterdir()
        return out.read_bytes()


def main() -> None:
    files: dict[str, bytes] = {}
    for lang, p in PEOPLE.items():
        files[f"{lang}_una_columna.pdf"] = pdf_one_column(p)
        files[f"{lang}_dos_columnas.pdf"] = pdf_two_columns(p)
        files[f"{lang}_parrafos.docx"] = docx_paragraphs(p)
        files[f"{lang}_tablas_cuadros.docx"] = docx_tables_textboxes(p)
        files[f"{lang}_real.doc"] = soffice_convert(files[f"{lang}_parrafos.docx"], ".docx", "doc:MS Word 97")
    es_docx = files["es_parrafos.docx"]
    files["es_rtf_renombrado.doc"] = soffice_convert(es_docx, ".docx", "rtf")
    files["es_html_renombrado.doc"] = soffice_convert(es_docx, ".docx", "html:HTML (StarWriter)")
    files["es_docx_renombrado.doc"] = es_docx
    files["es_escaneado.pdf"] = pdf_scanned()
    files["danado.pdf"] = files["es_una_columna.pdf"][:400]
    files["danado.docx"] = es_docx[: len(es_docx) // 2]
    files["protegido.pdf"] = pdf_protected(PEOPLE["es"])
    files["sin_texto.docx"] = docx_empty()
    files["es_sin_encabezados.docx"] = docx_no_headings()
    for name, data in files.items():
        (OUT / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")


if __name__ == "__main__":
    main()
