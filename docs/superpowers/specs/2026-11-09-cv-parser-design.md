# cv-parser: microservicio de parseo de CV

Fecha: 2026-11-09. Estado: aprobado por el usuario. Actualizado el 2026-11-09 con la capa opcional de LLM (ver "Capa opcional con LLM").

Microservicio genérico que se conecta a cualquier sistema sin dependencias directas. Cada sistema consumidor construye su propio adaptador; este documento cubre solo el microservicio.

## Intención

Un servicio propio recibe un CV y devuelve JSON estructurado sin mandar datos a terceros. Cualquier sistema puede usarlo conociendo solo su contrato HTTP.

El primer uso previsto es prellenar el registro de candidatos en un portal de empleo. Por ahora es una prueba local: medir si Python lo logra antes de integrarlo a algún flujo.

Se hace local para ahorrar tokens y no enviar datos personales fuera. La medición del 2026-11-09 mostró que las reglas no alcanzan (37 % correctos y 15 % incorrectos en la reserva), y el usuario decidió agregar un LLM opcional para empleos, estudios, nombre, título y resumen.

## Objetivos

1. Leer PDF, `.docx` y `.doc`. Los tres son obligatorios.
2. Entender CVs en español e inglés, incluidos los mixtos.
3. Devolver un JSON genérico, estable, documentado en OpenAPI y versionado en `/v1`.
4. Configurarse por variables de entorno y correr como imagen Docker sin estado.
5. Medir la calidad con una muestra de CVs y saber si Python lo logra.

## Fuera de alcance

- Reglas de cualquier consumidor: catálogos, IDs y validaciones de formularios.
- Guardar CVs o resultados.
- OCR: un PDF escaneado se reporta como ilegible.
- LLM como requisito: el servicio funciona completo sin él. El LLM es opcional y está apagado por defecto.
- Cola, modo asíncrono, varios clientes o usuarios. Si el volumen lo pide, se agregan sin romper `/v1`.
- Desplegar a QA o producción.
- CVs de producción de un consumidor.

## Lo que no debe pasar

- **Inventar datos.** Un campo vacío es mejor que uno incorrecto. Si el CV solo trae el año, el mes queda vacío. Si no hay indicios de país, el país queda vacío.
- **Sacar datos personales del equipo sin permiso.** Con el LLM apagado, ni el servicio ni sus dependencias hacen llamadas externas. Con el LLM encendido, solo sale el texto del CV sin correo, teléfono ni identificadores (CURP, RFC, NSS), y solo al proveedor configurado.
- **Dejar datos personales en logs, repos o reportes compartidos.** Los logs no llevan texto del CV ni nombre de archivo.
- **Depender de un consumidor.** Nada de un consumidor en el código, los nombres o el contrato.
- **Romper el contrato sin cambiar de versión.**

## Decidido por el usuario

- Microservicio independiente, en un proyecto aparte, que se conecte a lo que sea sin dependencias directas.
- Lógica propia desde cero, en inglés y español. El usuario sigue abierto a una librería mejor; ninguna de las revisadas cumple (ver "Librerías revisadas").
- 2026-11-09: LLM opcional para empleos y estudios, intercambiable entre Anthropic, OpenAI y Gemini por variables de entorno. Para las pruebas se pueden enviar a cualquiera de los tres los CVs de la muestra, que es controlada. Meta: al menos 90 % de campos correctos y como máximo 5 % incorrectos.
- Soporte obligatorio de `.doc` y `.docx`.
- Muestra inicial: unos 15 CVs del usuario. Claude puede leer los que el usuario ponga en la carpeta de muestra, sabiendo que su contenido se envía a Anthropic. Eso no cubre CVs de producción.
- Todo local: ramas locales, nada se sube al repo remoto ni a QA. Proceso de superpowers.
- "Python lo logra" con al menos 80 % de campos correctos en CVs de una columna y como máximo 5 % incorrectos en toda la muestra.

## Decisiones del autor del diseño

- **Repo:** propio, independiente de cualquier consumidor.
- **Stack:** Python 3.12, FastAPI, `pdfplumber`, `python-docx` y LibreOffice sin interfaz.
- **Ejecución:** Docker, con el puerto `127.0.0.1:8010` del equipo.
- **`.doc`:** se convierte a `.docx` con LibreOffice y sigue el mismo camino. La imagen crece varios cientos de MB; se acepta para la prueba.
- **Datos de contacto:** nombre, correo y teléfono salen en `extracted`, para comprobar que el CV se leyó bien.
- **Pruebas:** usan CVs inventados; ningún dato real entra al repo.

## Contrato

### Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `CV_PARSER_CORS_ORIGINS` | vacío, sin CORS | Orígenes permitidos, separados por coma. El `docker-compose.yml` local pone `http://localhost:3000` |
| `CV_PARSER_MAX_BYTES` | `10485760` (10 MB) | Tamaño máximo del archivo |
| `CV_PARSER_API_KEY` | vacío, sin clave | Si tiene valor, `/v1/*` exige la cabecera `X-API-Key` igual a ese valor; `/health` sigue abierto |
| `CV_PARSER_CONVERT_TIMEOUT` | `60` | Segundos máximos por conversión con LibreOffice |
| `CV_PARSER_LLM_PROVIDER` | `none` | `none`, `anthropic`, `openai` o `gemini` |
| `CV_PARSER_LLM_MODEL` | vacío | Modelo del proveedor, p. ej. `claude-haiku-5-5`. Obligatorio si el proveedor no es `none` |
| `CV_PARSER_LLM_TIMEOUT` | `30` | Segundos máximos por llamada al LLM |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` | vacío | Clave del proveedor elegido; nunca va en el repo ni en logs |

### Rutas

- `GET /health` devuelve `{"status": "healthy", "version": "0.1.0"}`.
- `GET /openapi.json` publica el contrato para generar tipos en cualquier lenguaje.
- `POST /v1/parse` recibe `multipart/form-data` con el campo `file`.

| Código | Cuándo |
|---|---|
| `200` | Se procesó, aunque el resultado sea parcial o ilegible; ver `status` |
| `400` | Falta el archivo o viene vacío |
| `401` | Hay clave configurada y la cabecera falta o no coincide |
| `413` | Supera `CV_PARSER_MAX_BYTES` |
| `415` | Formato no soportado |
| `422` | Archivo dañado o protegido con contraseña |
| `500` | Error interno, sin contenido del CV en la respuesta |

Los errores devuelven `{"error": "<codigo>"}`.

Respuesta `200`:

```json
{
  "status": "ok | partial | unreadable",
  "meta": {
    "format": "pdf | docx | doc",
    "language": "es | en | mixed",
    "pages": 2,
    "columns": 1,
    "sections": ["summary", "experience", "education"],
    "duration_ms": 320,
    "parser_version": "0.1.0"
  },
  "warnings": [{ "code": "no_sections", "section": null, "index": null }],
  "confidence": { "summary": 0.9, "education": 0.7, "experience": 0.6, "overall": 0.7 },
  "extracted": {
    "contact": { "name": null, "email": null, "phone": null },
    "headline": null,
    "summary": null,
    "education": [{
      "level": "university",
      "level_text": "Licenciatura en Administración",
      "is_technical": false,
      "area_text": "Administración",
      "institution": "Universidad de Guadalajara",
      "city": "Guadalajara",
      "country_code": "MX",
      "start": { "year": 2013, "month": 8 },
      "end": { "year": 2017, "month": 6 },
      "is_current": false,
      "confidence": 0.8
    }],
    "experience": [{
      "position": "Asistente Administrativa",
      "company": "Grupo Comercial del Bajío",
      "city": "Guadalajara",
      "country_code": "MX",
      "start": { "year": 2021, "month": 3 },
      "end": null,
      "is_current": true,
      "description": "Gestión de agenda",
      "confidence": 0.8
    }]
  }
}
```

- **`level`:** uno de `elementary`, `middle_school`, `high_school`, `university`, `master`, `doctorate`. Una carrera técnica es `high_school` y un técnico superior es `university`, ambos con `is_technical`.
- **`country_code`:** ISO 3166-1 alfa-2. Si la entrada no trae país, hereda el del encabezado del CV; nunca usa un valor fijo.
- **`meta.sections`:** secciones reconocidas en orden de aparición. Permite al consumidor distinguir "no tiene experiencia" de "no se pudo leer".
- **`warnings.code`:** `scanned_pdf`, `empty_document`, `no_sections`, `llm_unavailable` (el LLM falló o tardó y quedó el resultado de las reglas) y `llm_rejected` (se descartó algo que el LLM devolvió y no pasó la validación; `section` e `index` dicen qué).
- **`meta.extraction`:** campo agregado: `{"experience", "education", "contact", "headline", "summary"}`, cada uno `rules` o `llm`. Dice cómo se obtuvo cada parte; correo y teléfono siempre salen de las reglas.
- **Cambios compatibles en `/v1`:** se pueden agregar campos y códigos de aviso. Los consumidores deben ignorar los que no conozcan. Quitar o cambiar el significado de un campo exige `/v2`.

### Cómo se procesa

1. **Detectar el formato por su contenido, no por la extensión.** Muchos `.doc` en realidad son RTF, HTML o `.docx` renombrados. RTF y HTML también se convierten con LibreOffice.
2. **Sacar líneas con su formato.** En PDF hay que reconstruir el orden de lectura con coordenadas, porque la lectura directa mezcla las columnas. En `.docx` hay que recorrer párrafos, tablas, cuadros de texto y encabezados de página, porque muchas plantillas ponen ahí el contenido.
3. **Detectar lo ilegible.** Un PDF casi sin texto se reporta como `unreadable` con el aviso `scanned_pdf`.
4. **Dividir en secciones** con un diccionario único de encabezados en ambos idiomas, sin distinguir mayúsculas ni acentos, y aceptando variantes como `E X P E R I E N C I A`. Los datos personales y las referencias son secciones propias y nunca se vuelven empleos ni estudios.
5. **Separar empleos y estudios,** usando los rangos de fechas como ancla. Es la parte más difícil y de la que depende casi toda la precisión.
6. **Interpretar** fechas (`03/2021`, `Marzo 2021`, `a la fecha`, `Present`), nivel de estudios, ciudad y país.
7. **Calcular confianza** por entrada y por sección.

Los conversores corren con un directorio temporal por petición, un tiempo límite y limpieza al terminar, aunque falle. El contenedor corre sin privilegios de root.

## Capa opcional con LLM

Decidida por el usuario el 2026-11-09, después de medir que las reglas no alcanzan.

- **Qué hace cada parte.** Python lee el archivo, ordena columnas, divide secciones, saca correo y teléfono, y da su propia versión de todo lo demás. El LLM arma `experience`, `education`, el nombre, el título y el resumen; si lo que devuelve no es válido, queda la versión de Python.
- **Qué se envía.** El texto completo del CV en orden de lectura, sin correos, teléfonos ni identificadores (CURP, RFC, NSS). No se envía el nombre del archivo.
- **Proveedor intercambiable.** Una interfaz común con un adaptador por proveedor (Anthropic, OpenAI, Gemini). Todos piden la misma salida JSON con esquema. Cambiar de proveedor no cambia el contrato.
- **Validación en Python, para que el LLM tampoco invente.** Cada entrada que devuelve pasa por:
  - fechas válidas con las mismas reglas de `dates.py` (años de 1950 al año siguiente, inicio antes que fin);
  - `level` dentro de los seis valores y `country_code` dentro de ISO 3166-1;
  - `position`, `company`, `institution`, `level_text` y `city` deben aparecer en el texto del CV, sin distinguir mayúsculas ni acentos;
  - un campo que no pasa se vacía; una entrada sin ningún dato clave válido se descarta, con aviso `llm_rejected`.
- **Si falla el LLM.** Error, tiempo agotado o respuesta inválida dejan el resultado de las reglas, con aviso `llm_unavailable` y `status` `partial`.
- **Logs.** Solo proveedor, modelo, tokens, duración y clase de error. Nunca texto del CV ni del prompt.
- **Costo estimado.** Unos 2,000 tokens de entrada y 1,200 de salida por CV. Con Claude Haiku 5.5 son unos $0.0008 por CV; con Claude Sonnet 5.5, unos $0.016.

## Medición

### Muestra

- Los CVs van en una carpeta fuera del repo, con permisos 700 y fuera de cualquier repo. Sus reportes también se quedan ahí.
- La copia se borra al terminar la prueba, previa confirmación del usuario.
- `eval/run_eval.py` corre la muestra y genera un reporte en esa carpeta. Identifica cada CV con un ID derivado de un hash, para que los nombres de archivo no terminen en consola ni en el reporte.

### Respuesta esperada

- **Quién la escribe:** cada CV tiene un `<id>.expected.json` con la misma forma que `extracted`, sin los campos de confianza. Claude lo escribe leyendo el CV, no a partir de la salida del parser, para no dar por bueno un error. El usuario revisa una parte. Un CV sin ese archivo no entra en las cifras.
- **Reserva:** una tercera parte de la muestra, unos 5 CVs, no se usa para afinar. Las cifras de "Python lo logra" salen de esa reserva, porque medir sobre los CVs ya afinados daría un resultado optimista.
  - **Cómo se elige:** por sorteo dentro de cada grupo de formato, idioma y columnas, para que no quede sin `.doc` o inglés si la muestra los tiene. Lo que la muestra no cubra solo se prueba con CVs inventados, y el reporte lo dice.
  - **Cuándo se abre:** al alcanzar las metas con los CVs de afinado o después de tres rondas, lo que ocurra primero. Una ronda es correr la medición, revisar los errores y corregir. Se abre una sola vez.

Se mide sobre `extracted`. Las entradas de estudios y empleos se emparejan por mayor parecido, no por orden. Cada campo queda así:

- **Correcto:** coincide con lo esperado. Los textos se comparan sin mayúsculas ni acentos, con tolerancia a diferencias menores.
- **Vacío:** se esperaba un valor y no salió. Una entrada esperada que no se encontró cuenta todos sus campos como vacíos.
- **Incorrecto:** salió un valor distinto, o salió un valor donde no se esperaba ninguno. Una entrada inventada cuenta todos sus campos como incorrectos.
- **No cuenta:** un campo que se esperaba vacío y salió vacío. Si contara como correcto, inflaría el porcentaje.

Los CVs ilegibles no entran en los porcentajes y se reportan aparte. El reporte separa los resultados por formato, idioma, columnas y sección.

### Qué significa "Python lo logra"

- Al menos 80 % de campos correctos en CVs de una columna.
- Como máximo 5 % de campos incorrectos en toda la muestra. Pesa más que los vacíos, porque un dato equivocado puede pasar inadvertido.

Con 5 CVs en reserva es una señal y no una estadística firme. Si no se alcanza, se revisa con el usuario si conviene seguir afinando o conectar OpenAI solo para las secciones de baja confianza.

### Resultado con reglas (2026-11-09)

Muestra de 43 CVs reales en español (30 PDF y 13 `.docx`, sin `.doc` ni inglés); 29 de afinado y 14 de reserva. Tras tres rondas, la reserva dio 31.5 % correctos en CVs de una columna y 15.1 % incorrectos en total. No se logra.

### Medición con LLM

- **Meta:** al menos 90 % de campos correctos y como máximo 5 % incorrectos en toda la muestra.
- **Misma muestra.** No hay más CVs. El prompt y la validación se afinan solo con los 29 CVs de afinado. De la reserva solo se conocen cifras agregadas; su detalle no se ha revisado.
- **Reserva.** Con el prompt, el modelo y la validación congelados, la reserva se mide una sola vez por proveedor y modelo. Esa es la cifra principal. La de los 41 CVs juntos se reporta aparte como optimista.
- **Sesgo conocido.** Las respuestas esperadas las escribió Claude. Antes de comparar proveedores, el usuario revisa al menos 5, sobre todo de la reserva.

## Pruebas automáticas

- `pytest` dentro del contenedor, con CVs inventados guardados en el repo y su respuesta esperada.
- **Formatos que deben cubrir,** en español e inglés: PDF a una y dos columnas, `.docx` con párrafos, `.docx` con tablas y cuadros de texto, y `.doc` real.
- **Casos especiales:** `.doc` que en realidad es RTF o HTML, PDF escaneado, archivo dañado y archivo protegido.
- **Pruebas unitarias por tabla** para fechas, encabezados, niveles y lugares.
- **Contrato:** `/openapi.json` publica `/v1/parse`, y ni el código ni el contrato mencionan a un consumidor.
- **Configuración:** CORS, clave y límite de tamaño se prueban por variable de entorno.
- Los CVs reales nunca entran al repo; `.gitignore` y una revisión antes de cada commit lo refuerzan.

## Librerías revisadas

| Repo | Por qué no se usa |
|---|---|
| `wespiper/pyresume` | Sin soporte de español; con un CV inventado dio resultados incorrectos y un parche de encabezados y meses no bastó. MIT, se puede consultar |
| `OmkarPathak/ResumeParser` | Es un ATS Django con LLM de 1 GB y solo 153 líneas aprovechables |
| `sanketsarwade/Resume-Parser-using-Python` | Dos notebooks con 237 líneas, sin licencia, solo PDF, sin experiencia ni fechas |
| `xitanggg/open-resume` | Solo PDF en inglés a una columna, según su propio código. AGPL: se puede aprender del enfoque de puntuar líneas por sus rasgos, sin copiar código |

La búsqueda en GitHub fue breve y no exhaustiva.

## Lo que queda a quien lo construya

- Estructura interna de módulos y nombres.
- Algoritmo de columnas y fórmula de confianza.
- Contenido de diccionarios y listas de lugares.
- Umbrales de comparación de texto.
- Orden de construcción, siempre que `.doc` quede cubierto antes de medir.

## Antes de pasar de la prueba

No se resuelve ahora, pero bloquea cualquier despliegue: dónde vive el servicio, si basta la clave por cabecera, costo de la imagen con LibreOffice y aislamiento de los conversores frente a archivos maliciosos.
