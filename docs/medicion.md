# Medición

Cómo medir la calidad del servicio con una muestra de CVs propia, sin que ningún CV entre al repo.

## Reglas

- Los CVs reales viven en una carpeta **fuera del repo**, con permisos `700`. Sus reportes y respuestas esperadas también se quedan ahí.
- La consola y los reportes identifican cada CV por un ID: los primeros 12 caracteres del SHA-256 de su contenido. Nunca muestran el nombre del archivo.
- Si usas un LLM para medir, el texto de esos CVs sale hacia el proveedor. Hazlo solo con CVs que se puedan compartir con él.

## Estructura de la carpeta de muestra

```
<muestra>/
  originales/          los CVs (PDF, .docx, .doc)
  expected/<id>.expected.json   respuesta esperada de cada CV
  reportes/            reportes de cada medición (JSON y Markdown)
  split.json           sorteo afinado/reserva y aperturas de la reserva
  ids.json             relación ID → nombre de archivo (solo en esta carpeta)
  labels.json          opcional: etiquetas humanas {id: {format, language, columns}} para el sorteo
```

## Pasos

```sh
M=/ruta/a/la/muestra    # fuera del repo
docker compose run --rm -v $M:/muestra api python eval/run_eval.py --sample-dir /muestra --init
```

1. **`--init`:** sortea una tercera parte de la muestra como **reserva**, estratificando por formato, idioma y columnas, y el resto queda para **afinar**. Nunca rehace un sorteo existente.
2. **Respuestas esperadas.** Escribe `expected/<id>.expected.json` para los CVs de afinado, leyendo cada CV con la guía de abajo y **sin mirar la salida del servicio**, para no dar por bueno un error. Una persona revisa al menos 5.
3. **Medir el afinado:**

   ```sh
   docker compose run --rm -v $M:/muestra api python eval/run_eval.py --sample-dir /muestra --split tuning
   docker compose run --rm -v $M:/muestra api python eval/run_eval.py --sample-dir /muestra --split tuning \
     --provider anthropic --model claude-haiku-5-5 --mode always
   ```

   El reporte separa por formato, idioma, columnas, sección y rango de confianza. Con LLM agrega llamadas, fallas, tokens y costo estimado.
4. **Afinar en rondas:** diagnóstico por campo, un test con datos inventados que reproduzca cada patrón, la corrección, la suite completa y medir de nuevo. Para cuando una ronda mejore menos de 2 puntos.
5. **Congelar y abrir la reserva.** Etiqueta el commit. Escribe las respuestas esperadas de la reserva y ábrela **una sola vez por configuración**:

   ```sh
   docker compose run --rm -v $M:/muestra api python eval/run_eval.py --sample-dir /muestra --open-reserve --name reglas
   docker compose run --rm -v $M:/muestra api python eval/run_eval.py --sample-dir /muestra --open-reserve \
     --provider anthropic --model claude-haiku-5-5 --mode always
   ```

   Con LLM, antes de abrir la reserva se hace una prueba con un fixture inventado. Si falla (clave o modelo equivocados), la reserva no se abre y el comando sale con código 3. Repetir una configuración ya abierta sale con código 2.
6. **`--split all`** mide toda la muestra. Esa cifra es optimista, porque incluye los CVs con los que se afinó, y el reporte la marca así.

## Puntaje

- **correcto:** coincide, sin mayúsculas, acentos ni puntuación. Se compara con `SequenceMatcher`, con umbral de 0.85, o de 0.7 para `description` y `summary`. `level` y `country_code` se comparan exactos.
- **vacío:** se esperaba un valor y no salió.
- **incorrecto:** salió un valor distinto, o un valor donde no se esperaba ninguno.
- **no cuenta:** se esperaba vacío y salió vacío.
- **Fechas:** año y mes cuentan por separado.
- **Entradas:** se emparejan por parecido de puesto y empresa, o de grado y escuela. Una entrada faltante cuenta sus campos como vacíos, y una inventada, como incorrectos.
- **Veredicto:** al menos 80 % correctos en CVs de una columna y como máximo 5 % incorrectos en total. La meta con LLM es 90 % correctos.

## Guía para escribir las respuestas esperadas

Cada archivo tiene la forma de `extracted`, sin `confidence`, más un `_meta` con la etiqueta humana del CV.

Forma (JSON, UTF-8):

```json
{
  "_meta": {"format": "pdf|docx", "language": "es|en|mixed", "columns": 1},
  "contact": {"name": "...", "email": "...", "phone": "..."},
  "headline": null,
  "summary": null,
  "education": [{"level": "...", "level_text": "...", "is_technical": false, "area_text": null,
                 "institution": "...", "city": null, "country_code": null,
                 "start": {"year": 2010, "month": null}, "end": null, "is_current": false}],
  "experience": [{"position": "...", "company": "...", "city": null, "country_code": null,
                  "start": {"year": 2021, "month": 3}, "end": null, "is_current": true, "description": null}]
}
```

Campos:
- `_meta.format`: el formato del archivo original (`pdf`, `docx` o `doc`). `language`: idioma del CV; `mixed` si mezcla mucho ambos. `columns`: 2 si el diseño visual pone contenido en dos columnas lado a lado (p. ej. barra lateral con datos/habilidades y cuerpo principal); 1 si se lee de arriba a abajo (aunque tenga fechas alineadas a la derecha o tablas).
- `contact.name`: nombre completo tal como aparece. `email` tal cual. `phone`: el teléfono principal del candidato, solo dígitos (conserva `+` si lo escribe con prefijo internacional, p. ej. `+523312345678`); `null` si no hay. Nunca el de una referencia.
- `headline`: el título o puesto que aparece bajo/junto al nombre en el encabezado (p. ej. "Contador Público"). `null` si no hay uno.
- `summary`: el texto de la sección de perfil/resumen/objetivo, uniendo sus renglones con un espacio, tal cual. `null` si no hay esa sección.
- `education`: solo estudios formales (primaria, secundaria, bachillerato/preparatoria, carrera técnica, TSU, licenciatura/ingeniería, maestría, doctorado), en el orden del CV. NO incluyas cursos, diplomados, certificaciones, talleres ni idiomas.
  - `level`: `elementary`, `middle_school`, `high_school`, `university`, `master`, `doctorate`. Carrera técnica/bachillerato técnico/CONALEP = `high_school` con `is_technical: true`; TSU/técnico superior universitario = `university` con `is_technical: true`. Especialidad médica o posgrado no maestría: `null` si no encaja.
  - `level_text`: el texto del grado como está escrito ("Licenciatura en Contaduría Pública"). `area_text`: lo que va después de "en/de/in/of" ("Contaduría Pública"); `null` si no hay área.
  - `institution`: nombre de la escuela tal cual.
- `experience`: empleos (incluye prácticas profesionales/servicio social/voluntariado solo si están en la sección de experiencia), en el orden del CV. NO incluyas referencias.
  - `position` y `company` tal cual. `description`: las viñetas o renglones de funciones/logros de ese empleo, sin el símbolo de viñeta, unidos con `\n` (un renglón partido por el ancho de página se une con espacio). `null` si no hay.
- Fechas (`start`, `end`): `{"year": AAAA, "month": M|null}`. `month` solo si el CV lo escribe. Si dice "actual/presente/a la fecha/en curso": `end: null`, `is_current: true`. En estudios, si solo hay una fecha, va en `end` y `start` es `null`. En empleos, una sola fecha va en `start`. Sin fechas: ambos `null`.
- `city`: solo si la entrada misma la menciona. `country_code` (ISO alfa-2, p. ej. `MX`): el de la entrada si lo menciona (o si su ciudad/estado lo deja claro, p. ej. "Guadalajara, Jalisco" = MX); si la entrada no trae lugar, usa el país del domicilio del encabezado del CV si este lo deja claro; si no hay ningún indicio, `null`.
