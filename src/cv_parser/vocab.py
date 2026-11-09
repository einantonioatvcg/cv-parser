"""Diccionarios en español e inglés. Las claves están plegadas con `lines.fold`."""

from __future__ import annotations

_HEADINGS_BY_SECTION = {
    "experience": [
        "experiencia", "experiencia laboral", "experiencia profesional", "experiencia de trabajo",
        "experiencias laborales", "experiencia laboral y profesional", "experiencia profesional y laboral",
        "experiencia laboral relevante", "experiencias", "experiencia laboral informal", "historial laboral", "historia laboral", "trayectoria laboral",
        "trayectoria profesional", "empleos", "empleos anteriores", "antecedentes laborales", "work experience",
        "experience", "professional experience", "employment history", "work history", "employment",
        "career history", "relevant experience", "professional background",
    ],
    "education": [
        "educacion", "formacion", "formacion academica", "formacion profesional", "estudios", "estudios realizados",
        "escolaridad", "preparacion academica", "grado de estudios", "grado maximo de estudios", "nivel de estudios",
        "formacion y estudios", "educacion y formacion", "formacion complementaria", "antecedentes academicos",
        "education", "academic background", "academic formation", "educational background", "academic history",
        "education and training",
    ],
    "summary": [
        "perfil", "perfil profesional", "perfil laboral", "resumen", "resumen profesional", "objetivo",
        "objetivo profesional", "objetivo laboral", "acerca de mi", "sobre mi", "presentacion", "summary",
        "professional summary", "profile", "professional profile", "objective", "career objective", "about me",
    ],
    "skills": [
        "habilidades", "competencias", "aptitudes", "conocimientos", "habilidades tecnicas", "habilidades blandas",
        "conocimientos tecnicos", "herramientas", "habilidades y competencias", "skills", "technical skills",
        "soft skills", "competencies", "abilities", "tools", "skills and abilities",
    ],
    "languages": ["idiomas", "idioma", "lenguas", "languages", "language"],
    "certifications": [
        "certificaciones", "cursos", "cursos y certificaciones", "capacitacion", "cursos y talleres", "diplomados",
        "certificaciones y cursos", "certifications", "courses", "training", "licenses and certifications",
        "certificates",
    ],
    "projects": ["proyectos", "projects"],
    "personal": [
        "datos personales", "informacion personal", "datos generales", "personal information", "personal details",
        "personal data", "contacto", "contact", "informacion de contacto", "contact information", "datos de contacto",
        "datos del solicitante", "datos de identificacion", "datos generales del solicitante",
    ],
    "references": [
        "referencias", "referencias personales", "referencias laborales", "referencias profesionales", "references",
        "personal references", "professional references", "recomendaciones", "referencias vecinales", "referencia laboral", "referencia personal",
    ],
    "other": [
        "intereses", "pasatiempos", "hobbies", "interests", "voluntariado", "volunteer", "volunteering",
        "volunteer experience", "awards", "premios", "reconocimientos", "publicaciones", "publications", "otros", "other", "informacion adicional", "additional information", "otros antecedentes",
    ],
}

HEADINGS: dict[str, str] = {text: key for key, texts in _HEADINGS_BY_SECTION.items() for text in texts}

MONTHS: dict[str, int] = {
    "enero": 1, "ene": 1, "january": 1, "jan": 1,
    "febrero": 2, "feb": 2, "february": 2,
    "marzo": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6, "june": 6,
    "julio": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "septiembre": 9, "setiembre": 9, "sept": 9, "sep": 9, "set": 9, "september": 9,
    "octubre": 10, "oct": 10, "october": 10,
    "noviembre": 11, "nov": 11, "november": 11,
    "diciembre": 12, "dic": 12, "december": 12, "dec": 12,
}

CURRENT_WORDS: list[str] = [
    "a la fecha", "la fecha", "actualidad", "actualmente", "actual", "presente", "hoy", "en curso", "cursando",
    "vigente", "present", "current", "currently", "now", "today", "to date", "ongoing", "in progress",
]

PERSONAL_PREFIXES: list[str] = [
    "fecha de nacimiento", "fecha nacimiento", "f. de nacimiento", "nacimiento", "nacido", "nacida",
    "lugar de nacimiento", "edad", "date of birth", "birth date", "birthdate", "birthday", "born", "dob",
    "curp", "rfc", "nss", "imss", "estado civil", "marital status", "nacionalidad", "nationality",
    "tel", "telefono", "cel", "celular", "movil", "phone", "mobile", "whatsapp", "email", "e-mail", "correo",
    "direccion", "domicilio", "address", "c.p", "cp ", "codigo postal", "zip", "licencia", "pasaporte", "passport",
    "sexo", "genero", "gender",
]

SPANISH_WORDS = frozenset(
    "experiencia laboral profesional formacion academica educacion estudios habilidades idiomas perfil resumen "
    "objetivo actualidad actual presente referencias datos personales de del la las el los en y con para por una "
    "un al como sus mis empresa trabajo puesto licenciatura universidad bachillerato preparatoria secundaria "
    "maestria ingenieria enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
    "diciembre manejo atencion clientes ventas responsable funciones logros".split()
)
ENGLISH_WORDS = frozenset(
    "experience work professional education skills languages profile summary objective present current "
    "references personal the and of with for in to at on as by an my company job position bachelor master "
    "university school high degree january february march april june july august september october november "
    "december management customer sales responsible duties achievements".split()
)
