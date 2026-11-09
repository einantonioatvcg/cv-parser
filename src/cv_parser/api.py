"""Aplicación HTTP. Nunca registra el contenido ni el nombre del archivo."""

from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI, File, Header, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cv_parser import __version__
from cv_parser.config import Settings
from cv_parser.errors import ConversionTimeout, CorruptFile, UnsupportedFormat
from cv_parser.llm.clients import make_client
from cv_parser.models import ParseResult
from cv_parser.pipeline import parse_document

log = logging.getLogger("cv_parser.api")


class ErrorBody(BaseModel):
    error: str


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


ERROR_RESPONSES = {
    400: {"model": ErrorBody, "description": "Falta el archivo o viene vacío (missing_file)"},
    401: {"model": ErrorBody, "description": "Clave configurada y cabecera X-API-Key ausente o distinta (unauthorized)"},
    413: {"model": ErrorBody, "description": "Supera CV_PARSER_MAX_BYTES (file_too_large)"},
    415: {"model": ErrorBody, "description": "Formato no soportado (unsupported_format)"},
    422: {"model": ErrorBody, "description": "Archivo dañado o protegido con contraseña (corrupt_file)"},
    500: {"model": ErrorBody, "description": "Error interno (internal_error, conversion_timeout)"},
}


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="cv-parser",
        version=__version__,
        description="Convierte un CV en PDF, docx o doc (español o inglés) en JSON estructurado. "
                    "Los consumidores deben ignorar campos y códigos de aviso que no conozcan.",
    )
    llm = make_client(settings)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.exception_handler(RequestValidationError)
    def invalid_request(request, exc):  # noqa: ARG001
        return _error(400, "missing_file")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "version": __version__}

    @app.post("/v1/parse", response_model=ParseResult, responses=ERROR_RESPONSES)
    def parse(
        file: UploadFile | None = File(None),
        x_api_key: str | None = Header(None),
    ):
        if settings.api_key and not hmac.compare_digest((x_api_key or "").encode(), settings.api_key.encode()):
            return _error(401, "unauthorized")
        if file is None:
            return _error(400, "missing_file")
        data = file.file.read(settings.max_bytes + 1)
        if not data:
            return _error(400, "missing_file")
        if len(data) > settings.max_bytes:
            return _error(413, "file_too_large")
        try:
            return parse_document(data, convert_timeout=settings.convert_timeout, llm=llm,
                                  llm_mode=settings.llm_mode, llm_threshold=settings.llm_threshold)
        except UnsupportedFormat:
            return _error(415, "unsupported_format")
        except CorruptFile:
            return _error(422, "corrupt_file")
        except ConversionTimeout:
            log.warning("conversion timeout")
            return _error(500, "conversion_timeout")
        except Exception as exc:  # noqa: BLE001 - nunca se devuelve ni registra el contenido
            log.error("internal error: %s", type(exc).__name__)
            return _error(500, "internal_error")

    return app


app = create_app(Settings.from_env())
