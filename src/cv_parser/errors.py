"""Errores del procesamiento de documentos."""


class CorruptFile(Exception):
    """El archivo está dañado, protegido con contraseña o no se pudo leer."""


class ConversionTimeout(Exception):
    """La conversión con LibreOffice superó el tiempo límite."""


class UnsupportedFormat(Exception):
    """El contenido no es PDF, docx, doc, RTF ni HTML."""
