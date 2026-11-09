# cv-parser

Microservicio que recibe un CV y devuelve JSON estructurado: contacto, título, resumen, estudios y empleos.

- **Formatos:** PDF (una o dos columnas), `.docx` y `.doc`. También acepta RTF y HTML guardados como `.doc`.
- **Idiomas:** español e inglés, incluidos los CVs que mezclan ambos.
- **Integración:** se instala como módulo adicional en cualquier sistema que necesite leer CVs. Los consumidores solo conocen su contrato HTTP.
- **Estado:** no guarda nada de lo que procesa.

| Modo | Qué hace | Calidad medida* | Costo por CV |
|---|---|---|---|
| Solo reglas (por defecto) | Todo local, sin ninguna llamada de red | 35–52 % correctos, ~16 % incorrectos | $0 |
| Reglas + LLM (recomendado) | Python lee, divide, redacta y valida; un LLM arma estudios, empleos y encabezado | 88–91 % correctos, ~5 % incorrectos | ~$0.0016 con Claude Haiku 5.5 |

\* Medido con 43 CVs reales en español. Detalle, metodología y comparación de proveedores en [docs/costos-y-comparativas.md](docs/costos-y-comparativas.md).

## Inicio rápido

```sh
docker compose build
docker compose up -d
curl http://127.0.0.1:8010/health
curl -F file=@mi-cv.pdf http://127.0.0.1:8010/v1/parse
```

El contrato completo está en `GET /openapi.json`. La guía para integrarlo en otro sistema está en [docs/integracion.md](docs/integracion.md): ejemplos de petición y respuesta, errores, avisos, cómo usar la confianza y la lista para pasar a producción.

## Configuración

Todo se configura con variables de entorno. Para el uso local se pueden poner en un archivo `.env`, que git y Docker ignoran.

| Variable | Por defecto | Uso |
|---|---|---|
| `CV_PARSER_CORS_ORIGINS` | vacío (sin CORS) | Orígenes permitidos, separados por coma |
| `CV_PARSER_MAX_BYTES` | `10485760` | Tamaño máximo del archivo (10 MB) |
| `CV_PARSER_API_KEY` | vacío (sin clave) | Si tiene valor, `/v1/*` exige la cabecera `X-API-Key` igual a ese valor |
| `CV_PARSER_CONVERT_TIMEOUT` | `60` | Segundos máximos por conversión con LibreOffice |
| `CV_PARSER_LLM_PROVIDER` | `none` | `none`, `anthropic`, `openai` o `gemini` |
| `CV_PARSER_LLM_MODEL` | vacío | Modelo del proveedor, p. ej. `claude-haiku-5-5`. Obligatorio si hay proveedor |
| `CV_PARSER_LLM_MODE` | `low_confidence` | `always` consulta al LLM en cada CV (recomendado); `low_confidence`, solo si la confianza de las reglas es baja |
| `CV_PARSER_LLM_THRESHOLD` | `0.75` | Umbral de confianza para `low_confidence` |
| `CV_PARSER_LLM_TIMEOUT` | `30` | Segundos por intento de llamada al LLM (Anthropic y OpenAI reintentan una vez) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` | vacío | Clave del proveedor elegido |

Configuración recomendada, según la medición:

```sh
CV_PARSER_LLM_PROVIDER=anthropic
CV_PARSER_LLM_MODEL=claude-haiku-5-5
CV_PARSER_LLM_MODE=always
ANTHROPIC_API_KEY=...
```

## Privacidad

- **Sin LLM:** ni el servicio ni sus dependencias hacen llamadas externas.
- **Con LLM:** al proveedor solo va el texto del CV, ya sin correos, teléfonos, CURP, RFC ni NSS, y nunca el nombre del archivo. El correo y el teléfono de la respuesta siempre salen de las reglas locales.
- **Validación:** todo lo que devuelve el LLM se compara con el texto del CV. Un puesto, empresa, escuela, fecha o renglón que no esté escrito se vacía y se reporta con el aviso `llm_rejected`.
- **Logs:** solo formato, estado, duración, proveedor, modelo, tokens y la clase de un error. Nunca texto del CV.
- **Almacenamiento:** el servicio no guarda los archivos ni los resultados.

## Pruebas

```sh
docker compose run --rm api pytest
```

Los fixtures de `tests/fixtures/` son inventados. Se regeneran con `docker compose run --rm api python tests/fixtures/build_fixtures.py`. Las pruebas no llaman a ningún proveedor: `tests/conftest.py` borra las claves del entorno.

## Medición

`eval/run_eval.py` mide la calidad con una muestra de CVs propia, guardada fuera del repo: sorteo de una reserva, puntaje por campo, costo por proveedor y calibración de la confianza. Cómo hacerlo, incluida la guía para escribir las respuestas esperadas: [docs/medicion.md](docs/medicion.md).

## Para agentes de código

Instrucciones, reglas que no se rompen y mapa del código: [AGENTS.md](AGENTS.md).

## Estructura

```
src/cv_parser/      servicio (API, pipeline, extractores, reglas, capa de LLM)
eval/               medición con una muestra local
tests/              pruebas y fixtures inventados
docs/               integración, costos y comparativas, medición, diseño y planes
```
