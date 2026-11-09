"""Casos de la revisión final: cada uno reproduce un dato inventado o una llamada externa."""

import http.server
import json
import threading
from pathlib import Path

import pytest
from fpdf import FPDF

from cv_parser.dates import find_date_range
from cv_parser.entries import parse_education, parse_experience
from cv_parser.extract.pdf import extract_pdf
from cv_parser.header import parse_header
from cv_parser.pipeline import parse_document
from cv_parser.places import find_place
from cv_parser.sections import split_sections
from tests.helpers import to_lines

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def pdf_fechas_a_la_derecha() -> bytes:
    pdf = FPDF(format="A4")
    pdf.add_font("Lib", "", FONT)
    pdf.add_page()
    pdf.set_font("Lib", "", 10)
    pdf.cell(180, 6, "Rosa Inventada Pérez", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.cell(180, 6, "EXPERIENCIA LABORAL", new_x="LMARGIN", new_y="NEXT")
    for puesto, fechas in [("Cajera", "Jun 2016 - Dic 2017"), ("Mesera", "Ene 2018 - Feb 2019"),
                           ("Recepcionista", "Mar 2019 - Abr 2020"), ("Vendedora", "May 2020 - Jun 2021"),
                           ("Asistente", "Jul 2021 - Actualidad")]:
        pdf.ln(4)
        pdf.cell(130, 6, puesto)
        pdf.cell(50, 6, fechas, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(180, 6, "Tienda Azul", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.cell(180, 6, "ESTUDIOS", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(130, 6, "Bachillerato General")
    pdf.cell(50, 6, "2010 - 2013", align="R", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


# C1
def test_fechas_alineadas_a_la_derecha_no_son_columna():
    data = pdf_fechas_a_la_derecha()
    assert extract_pdf(data).columns == 1
    r = parse_document(data)
    assert len(r.extracted.experience) == 5 and all(e.start for e in r.extracted.experience)
    assert len(r.extracted.education) == 1


# C2
@pytest.mark.parametrize("texto", [
    "• Fecha de nacimiento: mayo de 1990", "Fecha de nac.: mayo 1990", "Nac.: mayo de 1990",
    "Lugar y fecha de nacimiento: Puebla, 12 de mayo de 1990", "Nací en mayo de 1990",
    "D.O.B.: May 12, 1990", "Age: 34 (May 1990)", "- CURP: LOHM900512 2019",
])
def test_datos_personales_nunca_son_fecha(texto):
    assert find_date_range(texto) is None


def test_universidad_nacional_si_tiene_fecha():
    assert find_date_range("Universidad Nacional, 2010 - 2014") is not None


# C3
def test_html_no_hace_llamadas_externas():
    pedidos = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pedidos.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        html = (f'<!DOCTYPE html><html><head><link rel="stylesheet" href="http://127.0.0.1:{port}/a.css">'
                f'<style>@import url("http://127.0.0.1:{port}/b.css"); body {{ background: url(http://127.0.0.1:{port}/c.png) }}</style>'
                f'</head><body background="http://127.0.0.1:{port}/d.png"><img src="http://127.0.0.1:{port}/foto.png">'
                f'<p>Rosa Pérez</p><p>EXPERIENCIA</p><p>Cajera</p><p>Tienda Azul</p><p>2018 - 2019</p></body></html>')
        r = parse_document(html.encode())
    finally:
        server.shutdown()
    assert pedidos == []
    assert r.extracted.experience[0].position == "Cajera"


# I1
def test_estudios_sin_fecha_tras_una_linea_fechada():
    texto = ("Ingeniería Industrial – Instituto Tecnológico de Morelia (2008-2013)\n"
             "Bachillerato – CBTIS 52\nPrimaria – Escuela Benito Juárez")
    salida = parse_education(to_lines(texto), None)
    assert [(e.level, e.institution) for e in salida] == [
        ("university", "Instituto Tecnológico de Morelia"), ("high_school", "CBTIS 52"),
        ("elementary", "Escuela Benito Juárez")]
    assert salida[1].start is None and salida[2].start is None


def test_empleo_sin_fecha_al_final_sin_renglon_en_blanco():
    salida = parse_experience(to_lines("Cajera\nTienda Azul\n2018 - 2019\nMesero\nRestaurante Azul"), None)
    assert [(e.position, e.company) for e in salida] == [("Cajera", "Tienda Azul"), ("Mesero", "Restaurante Azul")]


# I2
def test_vineta_con_anio_no_es_ancla():
    salida = parse_experience(to_lines("Cajera\nTienda Azul\n2018 - 2021\n- Reconocimiento 2020\n- Manejo de caja"), None)
    assert len(salida) == 1 and salida[0].description == "Reconocimiento 2020\nManejo de caja"


def test_anio_suelto_con_texto_no_es_ancla():
    salida = parse_experience(to_lines("Cajera\nTienda Azul\n2018 - 2021\nCurso de Excel 2019"), None)
    assert len(salida) == 1


# I3
def test_subetiquetas_no_cambian_de_seccion():
    s = split_sections(to_lines("EXPERIENCIA\nCajera\nTienda Azul\n2019 - 2021\nActividades:\n- Cobro en caja\n"
                                "Logros\n- Mejor vendedora\nMesera\nRestaurante Sol\n2016 - 2018"))
    salida = parse_experience(s.parts["experience"], None)
    assert [e.position for e in salida] == ["Cajera", "Mesera"]
    assert salida[0].description == "Cobro en caja\nMejor vendedora"


def test_puesto_con_nombre_de_seccion():
    s = split_sections(to_lines("EXPERIENCIA\nCapacitación\nGrupo Azul S.A.\n2019 - 2021"))
    assert s.order == ["experience"] and len(parse_experience(s.parts["experience"], None)) == 1


# I4
def test_encabezado_desconocido_no_se_une_a_la_seccion_anterior():
    s = split_sections(to_lines("EXPERIENCIA\nCajera\nTienda Azul\n2018 - 2019\n\nRECOMENDACIONES\n"
                                "Lic. Juan Pérez, Gerente, Tienda Azul\n2015 - 2018"))
    assert len(parse_experience(s.parts["experience"], None)) == 1


@pytest.mark.parametrize("texto,clave", [
    ("FORMACIÓN ACADÉMICA Y COMPLEMENTARIA", "education"), ("Experiencia Laboral Relevante", "experience"),
    ("EXPERIENCIA PROFESIONAL Y LABORAL", "experience"), ("Educación y Formación", "education"),
    ("Certificaciones y cursos", "certifications"), ("Historia laboral", "experience"),
    ("Grado máximo de estudios", "education"), ("Work Experience & Internships", "experience"),
])
def test_encabezados_compuestos(texto, clave):
    assert clave in split_sections(to_lines(f"Nombre\n{texto}\nContenido")).parts


def test_datos_del_solicitante_no_son_empleo():
    texto = ("EXPERIENCIA\nCajera\nTienda Azul\n2018 - 2019\n\nDATOS DEL SOLICITANTE\n"
             "Lugar y fecha de nacimiento: Puebla, 12 de mayo de 1990\nF. Nac.: mayo 1990\nHijos: 2")
    s = split_sections(to_lines(texto))
    assert len(parse_experience(s.parts["experience"], None)) == 1


# I5
def test_linea_de_lugar_no_roba_descripcion():
    texto = "Cajera\nOxxo\nZapopan, Jalisco\n2018 - 2019\nCobro en caja\nMesero\nLa Casa del Taco\n2016 - 2018"
    salida = parse_experience(to_lines(texto), None)
    assert [(e.position, e.company) for e in salida] == [("Cajera", "Oxxo"), ("Mesero", "La Casa del Taco")]


# I6
@pytest.mark.parametrize("texto,pais", [("Córdoba, Veracruz", "MX"), ("San José, Chihuahua", "MX")])
def test_estado_gana_a_ciudad_homonima(texto, pais):
    assert find_place(texto).country_code == pais


# I7
def test_titulo_no_es_dato_personal():
    contacto, titulo = parse_header(to_lines("Ana López Martínez\nEdad: 34 años\nana@ejemplo.invalid"))
    assert titulo is None


def test_rotulo_curriculum_en_el_nombre():
    contacto, _ = parse_header(to_lines("Curriculum Vitae de Ana López\nana@ejemplo.invalid"))
    assert contacto.name == "Ana López"


# I8
def test_identificadores_no_son_telefono():
    r = parse_document_from_lines("Ana López\nDATOS PERSONALES\nNSS: 12345678901\nCelular: 33 1234 5678\n"
                                  "EXPERIENCIA\nCajera\nTienda Azul\n2018 - 2019")
    assert r.extracted.contact.phone == "3312345678"


def test_identificador_en_encabezado_no_es_telefono():
    contacto, _ = parse_header(to_lines("Ana López\nINE: 1234567890123\nFolio 0012345678"))
    assert contacto.phone is None


# I10
def test_lugar_de_nacimiento_no_es_pais_por_defecto():
    r = parse_document_from_lines("Ana López\nDATOS PERSONALES\nLugar de nacimiento: Bogotá, Colombia\n"
                                  "Domicilio: Av. Vallarta 1234, Zapopan, Jalisco\nEXPERIENCIA\nCajera\nTienda Azul\n2018 - 2019")
    assert r.extracted.experience[0].country_code == "MX"


# I11
def test_orden_empresa_puesto_se_reutiliza():
    texto = "Globex Corporation\nMarketing Manager\n2018 - 2022\n\nHooli\nProduct Analyst\n2016 - 2018"
    salida = parse_experience(to_lines(texto), None)
    assert [(e.position, e.company) for e in salida] == [("Marketing Manager", "Globex Corporation"), ("Product Analyst", "Hooli")]


def parse_document_from_lines(texto: str):
    import io

    from docx import Document

    doc = Document()
    for renglon in texto.split("\n"):
        doc.add_paragraph(renglon)
    buf = io.BytesIO()
    doc.save(buf)
    return parse_document(buf.getvalue())
