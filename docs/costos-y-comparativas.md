# Costos y comparativas

Resultados medidos en noviembre de 2026, con el código de este repo. Sirven para elegir la configuración y para estimar el gasto.

## Resumen

- **Solo con reglas** (sin LLM, todo local), el servicio acierta entre 35 y 52 % de los campos y se equivoca en cerca de 16 %. Lee bien los formatos y el contacto, pero los CVs reales tienen demasiados diseños para separar estudios y empleos solo con reglas.
- **Con reglas + LLM**, el servicio acierta entre 88 y 91 % de los campos y se equivoca en cerca de 5 %. Python lee el archivo, divide secciones, quita datos personales y valida; el LLM arma estudios, empleos, nombre, título y resumen.
- **Recomendación: Claude Haiku 5.5 en modo `always`.** En la reserva dio la misma calidad que Claude Sonnet 5.5 por la décima parte del costo: unos **$0.0016 por CV**, es decir **$47–93 al mes con 1,000–2,000 CVs al día**. Si se necesita bajar de 5 % de incorrectos, usa Sonnet 5.5: en el grupo de afinado quedó en 4.5 %, contra 5.7 % de Haiku, por unos $0.018 por CV.

## Cómo se midió

- **Muestra:** 43 CVs reales en español, facilitados para esta prueba: 30 PDF y 13 `.docx`, de diseños muy distintos (una y dos columnas, tablas, barras laterales, plantillas de portales de empleo, texto corrido). Dos son escaneos sin texto y se reportan aparte. La muestra no traía `.doc` ni CVs en inglés: esos casos solo están probados con fixtures inventados.
- **Respuestas esperadas:** para cada CV se escribió a mano el resultado correcto, campo por campo, leyendo el CV y sin ver la salida del servicio (guía en `docs/medicion.md`).
- **Puntaje por campo:**
  - **correcto:** coincide, sin distinguir mayúsculas ni acentos y con tolerancia a diferencias menores;
  - **vacío:** se esperaba un valor y no salió;
  - **incorrecto:** salió un valor distinto, o un valor donde no se esperaba ninguno. Una entrada inventada cuenta todos sus campos como incorrectos;
  - un campo que se esperaba vacío y salió vacío no cuenta.
- **Afinado y reserva:** 29 CVs se usaron para afinar las reglas y el prompt. Los otros 14, la **reserva**, se sortearon al inicio, no se miraron en detalle y se midieron una sola vez por configuración. La cifra honesta es la de la reserva; la de afinado es optimista.
- **Meta fijada:** al menos 90 % correctos y como máximo 5 % incorrectos. Un dato equivocado pesa más que uno vacío, porque puede pasar inadvertido.

## Calidad

### Reserva (CVs que nunca se usaron para afinar)

13 CVs medidos y 1 ilegible. En estas corridas el LLM armaba estudios y empleos; el encabezado todavía salía de las reglas.

| Configuración | Correctos | Incorrectos | Estudios (corr./inc.) | Empleos (corr./inc.) |
|---|---|---|---|---|
| Solo reglas, primera versión | 37.0 % | 15.1 % | 36.5 / 16.7 | 34.1 / 13.9 |
| Solo reglas, versión final | 35.0 % | 15.6 % | 37.2 / 18.6 | 30.1 / 13.5 |
| Reglas + **Claude Haiku 5.5** | **87.7 %** | **5.8 %** | 87.8 / 7.5 | 92.4 / 3.0 |
| Reglas + Claude Sonnet 5.5 | 87.5 % | 6.2 % | 89.0 / 6.2 | 91.3 / 4.5 |
| Reglas + Gemini 2.5 Flash | 84.4 % | 10.7 % | 83.9 / 15.2 | 88.9 / 6.6 |

En esa reserva, lo que más bajaba el promedio era el encabezado, que todavía sacaban las reglas: contacto con 66.7 % correctos y 15.4 % incorrectos, y resumen con 33 % y 33 %. Por eso la versión final también le pasa nombre, título y resumen al LLM.

### Afinado (29 CVs, optimista), versión final

| Configuración | Correctos | Incorrectos | Contacto | Título | Resumen |
|---|---|---|---|---|---|
| Solo reglas | 50.5 % | 15.8 % | 80.5 / 3.7 | 0 / 0 | 50.0 / 16.7 |
| Reglas + Claude Haiku 5.5 | 88.9 % | 5.7 % | 89.0 / 1.2 | 60.0 / 0 | 75.0 / 16.7 |
| Reglas + Claude Sonnet 5.5 | 91.0 % | 4.5 % | 89.0 / 1.2 | 80.0 / 0 | 75.0 / 16.7 |

Antes de pasar nombre, título y resumen al LLM, en este mismo grupo Gemini 2.5 Flash daba 89.0 % y 7.0 %, y Gemini 3.1 Flash-Lite, 84.6 % y 9.6 %.

Dos corridas iguales de Haiku sobre el grupo de afinado variaron menos de medio punto: los LLM no responden exactamente igual cada vez.

### Modo `low_confidence`

Este modo consulta al LLM solo si la confianza de las reglas es baja. Con el umbral de 0.75 igual se consultó en el 93 % de los CVs, porque casi todos tienen alguna sección dudosa, y acertó menos que `always` (81–84 % en afinado). **Usa `always`.**

## Costo

### Tokens y costo medidos por CV

Son los promedios de las corridas de afinado. Incluyen las instrucciones fijas y, en salida, el razonamiento que cada proveedor cobra.

| Modelo | Entrada (tokens) | Salida (tokens) | Precio por 1M (entrada / salida) | Costo por CV |
|---|---|---|---|---|
| Claude Haiku 5.5 | 3,825 | 2,335 | $0.10 / $0.50 | **$0.0016** |
| Gemini 3.1 Flash-Lite | 1,323 | 914 | $0.25 / $1.50 | $0.0017 |
| Gemini 2.5 Flash | 1,410 | 2,725 | $0.30 / $2.50 | $0.0072 |
| Claude Sonnet 5.5 | 3,825 | 1,034 | $2.00 / $10.00 | $0.0180 |

Gemini y Claude cuentan los tokens de forma distinta, así que sus cifras de tokens no son comparables entre sí. Las de costo sí.

### Proyección

| Modelo | 1,000 CV/día | 2,000 CV/día | Al mes (30 días) |
|---|---|---|---|
| Claude Haiku 5.5 | $1.55 | $3.10 | $47 – $93 |
| Gemini 3.1 Flash-Lite | $1.70 | $3.40 | $51 – $102 |
| Gemini 2.5 Flash | $7.20 | $14.50 | $217 – $434 |
| Claude Sonnet 5.5 | $18.00 | $36.00 | $540 – $1,080 |
| GPT-5.4 nano (estimado, sin medir) | ~$3.70 | ~$7.40 | ~$110 – $221 |
| GPT-5.4 mini (estimado, sin medir) | ~$13.40 | ~$26.80 | ~$401 – $803 |

- **Más barato por lotes:** si el resultado no se necesita en el momento, procesar por lotes cuesta 50 % menos en los tres proveedores. Hoy el servicio no lo implementa.
- **Precios usados:**
  - Claude: lista oficial de Anthropic (octubre de 2026).
  - OpenAI y Gemini: sitios de comparación (noviembre de 2026). Confírmalos en las páginas oficiales.
  - Los precios están en `eval/prices.py`; el reporte de medición los usa para calcular el costo.
- **OpenAI:** el adaptador está escrito pero no se ha medido. Su costo es una estimación con los tokens medidos de Haiku (3,825 de entrada y 2,335 de salida por CV); el número real depende de cuánto razone el modelo.

## Qué falta y qué tomar en cuenta

- **La reserva es una señal, no una cifra firme:** tiene 14 CVs. Con más CVs las cifras cambiarán algunos puntos.
- **Las cifras de Claude pueden estar algo favorecidas,** porque las respuestas esperadas las escribió un modelo de Claude, siguiendo la guía de `docs/medicion.md`. Conviene que una persona revise algunas antes de decidir entre proveedores.
- **El encabezado con LLM no se midió en la reserva,** porque ya se había abierto una vez para cada modelo. La cifra de la versión final en la reserva puede ser algo mejor que la de la tabla, ya que el contacto era lo que más fallaba.
- **Más reglas casi no ayudaron:** las rondas extra subieron el afinado de 45.6 % a cerca de 51 % (50.5 % en la medición final), pero la reserva no se movió. El camino para mejorar está en el prompt y la validación del LLM, medidos con más CVs.
- **Lo que más falla con LLM:** estudios con nivel o nombre del grado ambiguos, títulos y resúmenes en CVs sin una sección de perfil clara, y CVs a dos columnas con el contenido mezclado en el texto del PDF.
