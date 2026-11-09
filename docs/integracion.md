# Integración

Cómo usar `cv-parser` desde otro sistema. El servicio no conoce a sus consumidores: cada sistema lo llama por HTTP y traduce la respuesta a su propio modelo de datos.

## Despliegue

El servicio es una imagen Docker sin estado. Escucha en el puerto `8010` y se configura por variables de entorno (ver `README.md`).

```yaml
# docker-compose del sistema consumidor (ejemplo)
services:
  cv-parser:
    build: ./cv-parser            # o una imagen publicada en tu registro
    command: uvicorn cv_parser.api:app --host 0.0.0.0 --port 8010 --app-dir src
    environment:
      CV_PARSER_API_KEY: ${CV_PARSER_API_KEY}
      CV_PARSER_LLM_PROVIDER: anthropic
      CV_PARSER_LLM_MODEL: claude-haiku-5-5
      CV_PARSER_LLM_MODE: always
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    expose: ["8010"]              # solo en la red interna; no lo publiques a internet
```

El `docker-compose.yml` de este repo es para desarrollo: monta el código, usa `--reload` y abre CORS a `http://localhost:3000`. En producción usa la imagen con su `CMD` por defecto.

- **Salud:** `GET /health` responde `{"status": "healthy", "version": "0.1.0"}`. Úsalo como health check del orquestador; la imagen no trae `curl`, así que usa la comprobación HTTP del orquestador o `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health')"`.
- **Concurrencia:** cada petición ocupa un hilo mientras se convierte el archivo y se espera al LLM. Para volumen, corre varias réplicas o agrega `--workers N` al comando de `uvicorn`.
- **Imagen:** hoy instala también las dependencias de desarrollo (`.[dev]`: pytest y generadores de fixtures). Para producción, cambia `pip install -e ".[dev]"` por `pip install .` en el `Dockerfile`.

## Petición

`POST /v1/parse`, `multipart/form-data`, con el archivo en el campo `file`. Si hay clave configurada, envía la cabecera `X-API-Key`.

```sh
curl -H "X-API-Key: $CV_PARSER_API_KEY" -F file=@cv.pdf http://cv-parser:8010/v1/parse
```

```python
import httpx

with open("cv.pdf", "rb") as f:
    r = httpx.post("http://cv-parser:8010/v1/parse", files={"file": ("cv.pdf", f)},
                   headers={"X-API-Key": API_KEY}, timeout=90)
data = r.json()
```

```javascript
const form = new FormData();
form.append("file", archivo);   // File o Blob
const r = await fetch("http://cv-parser:8010/v1/parse", { method: "POST", body: form, headers: { "X-API-Key": apiKey } });
const data = await r.json();
```

Un CV tarda de menos de un segundo, con solo reglas y un PDF o `.docx`, a varios segundos con LLM o con un `.doc` que pasa por LibreOffice. En el peor caso se suman la conversión (hasta `CV_PARSER_CONVERT_TIMEOUT`, 60 s, y en `.doc` hasta dos intentos) y el LLM (hasta `CV_PARSER_LLM_TIMEOUT`, 30 s, por intento). Usa un tiempo límite de cliente de 180 segundos, o baja esas variables.

## Respuesta `200`

```json
{
  "status": "ok",
  "meta": {
    "format": "pdf", "language": "es", "pages": 2, "columns": 1,
    "sections": ["summary", "experience", "education"],
    "duration_ms": 2400, "parser_version": "0.1.0",
    "extraction": {"experience": "llm", "education": "llm", "contact": "llm", "headline": "rules", "summary": "llm"}
  },
  "warnings": [],
  "confidence": {"summary": 0.9, "education": 1.0, "experience": 1.0, "overall": 1.0},
  "extracted": {
    "contact": {"name": "María Fernanda López Hernández", "email": "maria.lopez@ejemplo.invalid", "phone": "3312345678"},
    "headline": "Asistente Administrativa",
    "summary": "Asistente administrativa con 6 años de experiencia en atención a clientes, facturación y manejo de agenda.",
    "education": [{
      "level": "university", "level_text": "Licenciatura en Administración de Empresas", "is_technical": false,
      "area_text": "Administración de Empresas", "institution": "Universidad de Guadalajara",
      "city": "Guadalajara", "country_code": "MX",
      "start": {"year": 2013, "month": 8}, "end": {"year": 2017, "month": 6}, "is_current": false, "confidence": 1.0
    }],
    "experience": [{
      "position": "Asistente Administrativa", "company": "Grupo Comercial del Bajío S.A. de C.V.",
      "city": "Guadalajara", "country_code": "MX",
      "start": {"year": 2021, "month": 3}, "end": null, "is_current": true,
      "description": "Gestión de agenda y viajes de la dirección general\nFacturación electrónica y conciliación bancaria",
      "confidence": 1.0
    }]
  }
}
```

Los datos del ejemplo son inventados.

### Campos

- **`status`:**
  - `ok`: el CV se leyó y se encontró estructura.
  - `partial`: el resultado es incompleto. Puede ser que no haya secciones reconocibles, que no haya estudios ni empleos, que la confianza sea baja o que el LLM haya fallado.
  - `unreadable`: el CV no tiene texto, por ejemplo un PDF escaneado o un documento vacío.
- **`meta.sections`:** las secciones reconocidas, en orden de aparición. Sirve para distinguir "no tiene experiencia" de "no se pudo leer".
- **`meta.extraction`:** de dónde salió cada parte, `rules` o `llm`.
- **`level`:** uno de `elementary`, `middle_school`, `high_school`, `university`, `master`, `doctorate`, o `null`. Una carrera técnica es `high_school` y un técnico superior es `university`, ambos con `is_technical`.
- **Fechas:** `{year, month}`. `month` es `null` si el CV no lo dice. `is_current` indica que el empleo o estudio sigue en curso, y entonces `end` es `null`.
- **`country_code`:** ISO 3166-1 alfa-2. Si la entrada no dice país, se hereda del domicilio del CV; si no hay indicio, es `null`.
- **`confidence`:** de 0 a 1 por entrada y por sección.
- **Campos vacíos:** son intencionales. El servicio prefiere dejar un campo vacío a inventar un valor.

### Avisos (`warnings`)

| `code` | Significado |
|---|---|
| `scanned_pdf` | El PDF no tiene capa de texto (requiere OCR, fuera de alcance) |
| `empty_document` | El documento no tiene texto |
| `no_sections` | No se reconoció ningún encabezado de sección |
| `llm_unavailable` | El LLM falló o tardó; se entregó el resultado de las reglas |
| `llm_rejected` | Se descartó algo que el LLM devolvió y no estaba en el CV; `section` dice en qué parte |

Ignora los campos y códigos de aviso que no conozcas: en `/v1` se pueden agregar sin aviso.

## Errores

Todos devuelven `{"error": "<codigo>"}`. Nunca incluyen contenido del CV.

| HTTP | `error` | Cuándo |
|---|---|---|
| 400 | `missing_file` | Falta el campo `file` o viene vacío |
| 401 | `unauthorized` | Hay clave configurada y `X-API-Key` falta o no coincide |
| 413 | `file_too_large` | Supera `CV_PARSER_MAX_BYTES` |
| 415 | `unsupported_format` | No es PDF, `.docx`, `.doc`, RTF ni HTML |
| 422 | `corrupt_file` | El archivo está dañado o protegido con contraseña |
| 500 | `conversion_timeout` | LibreOffice superó `CV_PARSER_CONVERT_TIMEOUT` |
| 500 | `internal_error` | Error interno |

## Uso recomendado en el sistema consumidor

1. **Prellena, no decidas.** Muestra lo extraído en un formulario que la persona confirma o corrige. Guarda en tu base lo confirmado, no la respuesta cruda.
2. **Usa la confianza.** Marca para revisión las entradas con `confidence` menor a 0.75. Con el LLM encendido, aun así conviene que una persona confirme.
3. **Traduce en tu lado.** Los catálogos propios (niveles, áreas, países, ciudades) se mapean en el sistema consumidor, a partir de `level`, `level_text`, `area_text`, `city` y `country_code`. El servicio no conoce catálogos de nadie.
4. **No reintentes en bucle.** Ante `422` o `415`, pide otro archivo. Ante `500`, reintenta una vez.

## Antes de producción

El servicio se midió como prueba local. Antes de exponerlo a usuarios reales:

- **Red:** solo en la red interna, con `CV_PARSER_API_KEY` puesta; si un navegador lo llama, limita CORS a tus dominios.
- **Aislamiento:** LibreOffice procesa archivos no confiables. Pon límites de CPU y memoria al contenedor, procesos sin root (la imagen ya corre como usuario 1000) y, de ser posible, el convertidor en un contenedor sin red.
- **Tamaño:** el servidor recibe el archivo completo antes de comparar su tamaño con `CV_PARSER_MAX_BYTES`. Pon también un límite en el proxy de entrada.
- **LLM:**
  - revisa el contrato de tratamiento de datos del proveedor elegido;
  - define si los CVs de producción pueden salir a ese proveedor;
  - vigila el gasto: el reporte de medición da tokens y costo por CV.
- **Datos que todavía no se redactan:** los números de credencial del INE y los correos escritos de forma ofuscada ("ana (at) correo"). Si tu caso lo exige, agrégalos a `llm/redact.py` con su test.
- **Monitoreo:** los logs traen `status`, `duration_ms` y, con LLM, proveedor, modelo y tokens. No traen datos personales.
