# Instrucciones para agentes

Este archivo es para agentes de código (Claude Code, Codex, Cursor y similares) y para personas que trabajen en el repo. `CLAUDE.md` lo importa.

## Qué es

`cv-parser` es un microservicio HTTP sin estado que recibe un CV (PDF, `.docx` o `.doc`, en español o inglés) y devuelve JSON estructurado: contacto, título, resumen, estudios y empleos. Está pensado para instalarse como módulo adicional en cualquier sistema que necesite leer CVs. Ningún consumidor aparece en el código ni en el contrato.

- Contrato: `GET /openapi.json`, versión `/v1`. Integración: `docs/integracion.md`.
- Diseño: `docs/superpowers/specs/2026-11-09-cv-parser-design.md`.
- Costos y calidad medidos: `docs/costos-y-comparativas.md`.
- Cómo medir con una muestra propia: `docs/medicion.md`.

## Reglas que no se rompen

1. **Un campo vacío es mejor que uno incorrecto.** Nunca inventes mes, país, nivel, empresa ni entradas. Toda regla nueva necesita un test que demuestre que no inventa.
2. **Sin datos de CVs reales en el repo.** Ni en tests, fixtures, logs, mensajes de commit ni documentación. Los fixtures se generan con `tests/fixtures/build_fixtures.py`, con datos inventados y correos `.invalid`. Si afinas con CVs reales, escribe el test con otro texto que reproduzca el mismo patrón.
3. **Logs sin contenido.** Los logs llevan solo formato, estado, duración, proveedor, modelo, tokens y la clase de una excepción. Nunca texto del CV, nombre de archivo, prompt, respuesta del LLM ni claves.
4. **Genérico.** Ni el código, ni el contrato, ni la documentación llevan nombres, catálogos o reglas de un consumidor. `tests/test_contract.py` lo verifica.
5. **Contrato estable.** En `/v1` solo se agregan campos y códigos de aviso. Quitar un campo o cambiar su significado exige `/v2`.
6. **El LLM es opcional y está apagado por defecto** (`CV_PARSER_LLM_PROVIDER=none`). Sin LLM no hay ninguna llamada de red. Con LLM:
   - al proveedor solo va el texto redactado por `llm/redact.py`, sin correos, teléfonos, CURP, RFC ni NSS;
   - todo lo que devuelve pasa por `llm/validate.py`, y lo que no está escrito en el CV se vacía.
7. **Claves solo en `.env`.** Está en `.gitignore` y `.dockerignore`. Nunca en el código, los tests ni los logs.

## Comandos

Python corre siempre dentro del contenedor:

```sh
docker compose build                           # tras cambiar dependencias
docker compose run --rm api pytest             # suite completa (debe quedar en verde)
docker compose run --rm api pytest tests/test_entries.py -v
docker compose up -d                           # servicio en http://127.0.0.1:8010
docker compose run --rm api python tests/fixtures/build_fixtures.py   # regenera fixtures
```

`tests/conftest.py` borra las claves y las variables `CV_PARSER_LLM_*` en cada prueba: ningún test llama a un proveedor real.

## Mapa del código

| Archivo | Qué hace |
|---|---|
| `src/cv_parser/api.py` | FastAPI: `/health`, `/v1/parse`, errores `{"error": "<codigo>"}` |
| `src/cv_parser/pipeline.py` | Orquesta: formato, extracción, secciones, encabezado, entradas, LLM opcional, confianza y estado |
| `src/cv_parser/sniff.py` | Detecta el formato por contenido, no por extensión |
| `src/cv_parser/extract/` | PDF con orden de lectura por columnas, `.docx` (párrafos, tablas, cuadros de texto, encabezados de página), conversión de `.doc`, RTF y HTML con LibreOffice |
| `src/cv_parser/lines.py` | `Line`, normalización de texto, unión de renglones partidos |
| `src/cv_parser/sections.py` | Encabezados de sección (diccionario en `vocab.py`, variantes y errores de dedo) |
| `src/cv_parser/header.py` | Nombre, título, correo y teléfono |
| `src/cv_parser/entries.py` | Separa empleos y estudios usando las fechas como ancla; confianza por señales |
| `src/cv_parser/dates.py`, `levels.py`, `places.py` | Fechas, nivel de estudios, ciudad y país |
| `src/cv_parser/llm/` | `redact.py`, `schema.py`, `prompt.py`, `clients.py` (Anthropic, OpenAI, Gemini), `validate.py` |
| `src/cv_parser/models.py` | Modelos Pydantic del contrato |
| `eval/` | Medición con una muestra local: `run_eval.py`, `score.py`, `split.py`, `prices.py` |

## Cómo trabajar

- **Prueba primero.** Escribe el test que reproduce el caso, míralo fallar, corrige, y corre la suite completa.
- **Afinar reglas** con una muestra real sigue el ciclo de `docs/medicion.md`: diagnóstico por campo, test con datos inventados, corrección y medición. Nunca afines con la reserva.
- **Cambiar el prompt o la validación del LLM:** mide en el grupo de afinado con al menos dos modelos antes de dar el cambio por bueno. Los LLM no responden igual cada vez, así que repite una corrida si la diferencia es menor a un punto.
- **Dependencias nuevas:** en `pyproject.toml` y `docker compose build`. Evita las que hagan llamadas de red al importarse.
- **Antes de cada commit:** `git diff --cached`, para confirmar que no entra texto de un CV real ni una clave.
