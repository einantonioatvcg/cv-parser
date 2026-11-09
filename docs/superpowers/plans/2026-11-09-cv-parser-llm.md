# cv-parser: capa opcional de LLM — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sacar el máximo de Python primero y usar un LLM opcional (Anthropic y Gemini; OpenAI después) solo para lo que Python no resuelva con seguridad, validado por Python, y medir si se llega a 90 % correctos con máximo 5 % incorrectos.

**Architecture:** Python sigue leyendo el archivo, ordenando columnas, dividiendo secciones y sacando contacto, título y resumen. Con `CV_PARSER_LLM_PROVIDER` distinto de `none`, el texto del CV sin datos de contacto ni identificadores va al proveedor con un esquema JSON. Lo que devuelve pasa por una validación que vacía o descarta lo que no esté en el texto o no tenga forma válida. Si el LLM falla, quedan las reglas.

**Tech Stack:** Python 3.12, FastAPI, SDKs oficiales `anthropic`, `openai` y `google-genai`, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-11-09-cv-parser-design.md`, sección "Capa opcional con LLM" y "Medición con LLM".

## Global Constraints

- Todo local: cero `git push`. Rama `local/cv-parser`. Python corre en Docker: `docker compose run --rm api <comando>`.
- Decidido por el usuario el 2026-11-09: el esfuerzo principal es Python. El LLM complementa, no reemplaza.
- `CV_PARSER_LLM_PROVIDER` vale `none` por defecto. Con `none`, cero llamadas de red (la prueba `test_no_abre_conexiones` sigue pasando).
- Variables nuevas: `CV_PARSER_LLM_PROVIDER` (`none|anthropic|openai|gemini`), `CV_PARSER_LLM_MODEL` (obligatorio si hay proveedor), `CV_PARSER_LLM_TIMEOUT` (`30`), `CV_PARSER_LLM_MODE` (`low_confidence` por defecto, o `always`) y `CV_PARSER_LLM_THRESHOLD` (`0.75`, confianza de sección por debajo de la cual se consulta al LLM). Claves: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, leídas de `.env` (ignorado por git y Docker).
- Al LLM nunca van correos, teléfonos, CURP, RFC, NSS ni el nombre del archivo.
- Logs: solo proveedor, modelo, tokens, duración y clase de error. Nunca texto del CV, del prompt ni de la respuesta. Nunca claves.
- Contrato `/v1`: solo se agregan `meta.extraction` y los avisos `llm_unavailable` y `llm_rejected`.
- Nada de ningún consumidor en `src/` ni en el contrato. Fixtures y tests con datos inventados (`.invalid`).
- Un campo vacío es mejor que uno incorrecto, también para lo que devuelve el LLM.
- Cada commit termina con la línea de atribución de la sesión.

## Review Focus

- Respuesta del LLM con un puesto, empresa o escuela que no está en el texto del CV: se vacía el campo, aviso `llm_rejected`. Test en Task 2.
- Respuesta con JSON inválido, truncado o sin las claves esperadas: se usan las reglas, aviso `llm_unavailable`, `status` `partial`. Test en Task 4.
- Correo, teléfono con formatos mexicanos (`(33) 1234-5678`, `+52 33 1234 5678`), CURP, RFC y NSS en cualquier parte del texto: no llegan al proveedor. Test en Task 1.
- Clave ausente con proveedor configurado: el servicio arranca, cada petición usa reglas con `llm_unavailable` y el log no muestra la clave. Test en Task 3.
- Fechas inventadas o al revés en la respuesta (`2099`, fin antes que inicio, mes 13): se vacían. Test en Task 2.

---

### Task 0: Más esfuerzo en Python y confianza que distinga

Antes de cualquier código de LLM. Se trabaja solo con los 29 CVs de afinado; de la reserva no se mira el detalle.

**Files:**
- Modify: `src/cv_parser/entries.py`, `src/cv_parser/sections.py`, `src/cv_parser/header.py` y los que el patrón pida; `eval/run_eval.py` (reporte de calibración)
- Create: `tests/test_afinado_r4.py` y siguientes, `tests/test_confidence.py`

**Interfaces:**
- Produces: la confianza de cada entrada y de cada sección predice si está bien: el reporte agrega, por rango de confianza (`<0.5`, `0.5–0.75`, `≥0.75`), el % de campos correctos e incorrectos de esas entradas.

- [ ] **Step 1:** Rondas 4 en adelante con el mismo método de las rondas 1–3 (diagnóstico por campo, test inventado que falla, corrección, suite, medición). Parar cuando una ronda mejore menos de 2 puntos de correctos en afinado, o después de la ronda 7.
- [ ] **Step 2: Test que falla para la confianza**

```python
def test_confianza_baja_por_senales_de_duda():
    # entrada armada por línea sin señal de empresa ni de puesto, y con texto sobrante
    dudosa = parse_experience(to_lines("Ventas\nZona Norte\nCentro\n2018 - 2019"), None)[0]
    clara = parse_experience(to_lines("Cajera\nTienda Azul S.A. de C.V.\n2018 - 2019"), None)[0]
    assert dudosa.confidence < 0.75 <= clara.confidence
```

- [ ] **Step 3:** Confianza por entrada a partir de señales, no solo de campos presentes: fecha de rango completo, señal de empresa o institución, palabra de puesto o nivel detectado, sin candidatos sobrantes, sin descripción mezclada con títulos. Sección = promedio de sus entradas; sin entradas con texto en la sección = 0.
- [ ] **Step 4:** Verificar en afinado que el grupo `≥0.75` tiene como máximo 10 % de incorrectos. Si no, ajustar señales y repetir.
- [ ] **Step 5:** Commit por ronda: `fix: ronda N de afinado (...)`. Al terminar, `git tag reglas-v2`.

### Task 1: Configuración y redacción del texto

**Files:**
- Modify: `src/cv_parser/config.py`, `docker-compose.yml` (`env_file: [{path: .env, required: false}]`), `README.md` (variables nuevas)
- Create: `src/cv_parser/llm/__init__.py`, `src/cv_parser/llm/redact.py`, `tests/test_llm_redact.py`, `tests/test_llm_config.py`

**Interfaces:**
- Produces: `Settings.llm_provider: str = "none"`, `Settings.llm_model: str | None = None`, `Settings.llm_timeout: int = 30`; `redact(text: str) -> str`.

- [ ] **Step 1: Tests que fallan**

```python
def test_settings_llm_desde_entorno(monkeypatch):
    monkeypatch.setenv("CV_PARSER_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("CV_PARSER_LLM_MODEL", "claude-haiku-5-5")
    s = Settings.from_env()
    assert (s.llm_provider, s.llm_model, s.llm_timeout) == ("anthropic", "claude-haiku-5-5", 30)
    assert Settings().llm_provider == "none"

def test_proveedor_desconocido_falla(monkeypatch):
    monkeypatch.setenv("CV_PARSER_LLM_PROVIDER", "otro")
    with pytest.raises(ValueError):
        Settings.from_env()

@pytest.mark.parametrize("sucio", [
    "ana.perez@ejemplo.invalid", "(33) 1234-5678", "+52 33 1234 5678", "Cel. 3312345678",
    "CURP: PEPA900101MJCRRN09", "RFC: PEPA900101AB1", "NSS: 12345678901",
])
def test_redacta(sucio):
    salida = redact(f"Ana Pérez\n{sucio}\nCajera 2018 - 2019")
    assert sucio.split()[-1] not in salida and "Cajera 2018 - 2019" in salida and "Ana Pérez" in salida
```

- [ ] **Step 2:** `docker compose run --rm api pytest tests/test_llm_redact.py tests/test_llm_config.py -v` → FAIL por módulo inexistente.
- [ ] **Step 3:** Implementar. `redact` reemplaza cada dato por `[dato]`, usando `header.EMAIL`, `header.find_phone` sobre tramos de dígitos y regex de CURP (`[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d`), RFC (`[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}`) y NSS (11 dígitos). Los rangos de fechas (`2018 - 2019`) no se tocan.
- [ ] **Step 4:** Mismo comando → PASS; suite completa → PASS.
- [ ] **Step 5:** Commit `feat: configura LLM opcional y redacta datos personales`.

### Task 2: Esquema y validación de la respuesta

**Files:**
- Create: `src/cv_parser/llm/schema.py`, `src/cv_parser/llm/validate.py`, `tests/test_llm_validate.py`

**Interfaces:**
- Consumes: `Education`, `Experience`, `YearMonth`, `ParseWarning` (models), `fold` (lines), `MIN_YEAR` (dates).
- Produces: `RESPONSE_SCHEMA: dict` (JSON Schema con `education` y `experience`, mismos campos que el contrato sin `confidence`, `additionalProperties: false`); `validate_response(raw: dict, source_text: str, today: date | None = None) -> tuple[list[Education], list[Experience], list[ParseWarning]]`.

- [ ] **Step 1: Tests que fallan**

```python
TEXTO = "Cajera\nTienda Azul, Zapopan, Jalisco\nMarzo 2018 - Febrero 2021\nLicenciatura en Derecho\nUniversidad Azul\n2010 - 2014"

def test_entrada_valida_pasa_con_confianza():
    edu, exp, avisos = validate_response({"experience": [empleo()], "education": [estudio()]}, TEXTO, HOY)
    assert exp[0].position == "Cajera" and exp[0].confidence == pytest.approx(1.0) and avisos == []

def test_texto_que_no_esta_en_el_cv_se_vacia():
    _, exp, avisos = validate_response({"experience": [empleo(company="Grupo Inventado")], "education": []}, TEXTO, HOY)
    assert exp[0].company is None and [a.code for a in avisos] == ["llm_rejected"]
    assert (avisos[0].section, avisos[0].index) == ("experience", 0)

def test_tolera_mayusculas_y_acentos():
    _, exp, _ = validate_response({"experience": [empleo(position="CAJERA", city="zapopán")], "education": []}, TEXTO, HOY)
    assert exp[0].position == "CAJERA" and exp[0].city == "zapopán"

@pytest.mark.parametrize("inicio,fin", [({"year": 2099, "month": 1}, None), ({"year": 2021, "month": 1}, {"year": 2018, "month": 1}),
                                        ({"year": 2018, "month": 13}, None)])
def test_fechas_invalidas_se_vacian(inicio, fin):
    _, exp, _ = validate_response({"experience": [empleo(start=inicio, end=fin)], "education": []}, TEXTO, HOY)
    assert exp[0].start is None and exp[0].end is None

def test_nivel_y_pais_fuera_de_catalogo():
    edu, _, _ = validate_response({"experience": [], "education": [estudio(level="kinder", country_code="XX")]}, TEXTO, HOY)
    assert edu[0].level is None and edu[0].country_code is None

def test_entrada_sin_datos_clave_se_descarta():
    _, exp, avisos = validate_response({"experience": [empleo(position="Nada", company="Tampoco", start=None, end=None)], "education": []}, TEXTO, HOY)
    assert exp == [] and avisos[0].code == "llm_rejected"

def test_actual_quita_fin():
    _, exp, _ = validate_response({"experience": [empleo(is_current=True, end={"year": 2021, "month": 2})], "education": []}, TEXTO, HOY)
    assert exp[0].is_current and exp[0].end is None
```

`empleo()` y `estudio()` son helpers del test que arman un dict válido sobre `TEXTO`, con campos sustituibles por argumento; `HOY = date(2026, 11, 9)`.

- [ ] **Step 2:** `docker compose run --rm api pytest tests/test_llm_validate.py -v` → FAIL.
- [ ] **Step 3:** Implementar. Un texto "aparece" si `fold(valor)` sin puntuación está contenido en `fold(source_text)` sin puntuación, o si su `SequenceMatcher` contra la mejor ventana del mismo largo da ≥ 0.9. `description` no se compara (puede unir renglones). `country_code` se valida contra los códigos de `places.COUNTRIES`. Confianza: 0.4 con fecha válida + 0.3 por cada dato clave válido (puesto y empresa, o nivel e institución). Se descarta una entrada sin ningún dato clave válido ni fecha válida.
- [ ] **Step 4:** Mismo comando → PASS; suite → PASS.
- [ ] **Step 5:** Commit `feat: valida la respuesta del LLM contra el texto del CV`.

### Task 3: Clientes por proveedor

**Files:**
- Modify: `pyproject.toml` (dependencias `anthropic`, `openai`, `google-genai`), `Dockerfile` (rebuild)
- Create: `src/cv_parser/llm/prompt.py`, `src/cv_parser/llm/clients.py`, `tests/test_llm_clients.py`

**Interfaces:**
- Consumes: `Settings`, `RESPONSE_SCHEMA`.
- Produces: `class LLMError(Exception)`; `@dataclass LLMResult(data: dict, input_tokens: int, output_tokens: int)`; `class LLMClient(Protocol): provider: str; model: str; def extract(self, text: str) -> LLMResult`; `make_client(settings: Settings) -> LLMClient | None` (`None` con `none`); `SYSTEM_PROMPT: str`.

- [ ] **Step 1: Tests que fallan** (sin red: el SDK se sustituye por un objeto falso)

```python
def test_none_no_crea_cliente():
    assert make_client(Settings()) is None

def test_sin_modelo_falla():
    with pytest.raises(ValueError):
        make_client(Settings(llm_provider="anthropic"))

def test_sin_clave_falla_al_usar_y_no_la_muestra(monkeypatch, caplog):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cliente = make_client(Settings(llm_provider="anthropic", llm_model="claude-haiku-5-5"))
    with pytest.raises(LLMError):
        cliente.extract("texto")

@pytest.mark.parametrize("proveedor", ["anthropic", "openai", "gemini"])
def test_adaptadores_devuelven_json_y_tokens(proveedor, monkeypatch):
    cliente = cliente_con_sdk_falso(proveedor, respuesta='{"education": [], "experience": []}', tokens=(100, 20))
    r = cliente.extract("texto")
    assert r.data == {"education": [], "experience": []} and (r.input_tokens, r.output_tokens) == (100, 20)

@pytest.mark.parametrize("proveedor", ["anthropic", "openai", "gemini"])
def test_json_invalido_es_llmerror(proveedor):
    with pytest.raises(LLMError):
        cliente_con_sdk_falso(proveedor, respuesta='{"education": [', tokens=(1, 1)).extract("texto")
```

- [ ] **Step 2:** `docker compose build && docker compose run --rm api pytest tests/test_llm_clients.py -v` → FAIL.
- [ ] **Step 3:** Implementar un adaptador por proveedor con su SDK oficial y salida JSON con esquema:
  - Anthropic: `messages.create` con `output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}, "effort": "low"}`, `max_tokens=8000`; revisar `stop_reason` (`refusal` y `max_tokens` son `LLMError`). Confirmar la forma exacta en la skill `claude-api` antes de escribir.
  - OpenAI: Responses o Chat Completions con `response_format` tipo `json_schema` estricto.
  - Gemini: `google-genai` con `response_mime_type="application/json"` y `response_schema`.
  - Cada SDK con `timeout=settings.llm_timeout` y sin reintentos propios más allá de los del SDK (máximo 1). Cualquier excepción del SDK se convierte en `LLMError(<clase>)`, sin texto.
  - `SYSTEM_PROMPT` en `prompt.py`: las reglas de la guía de respuestas esperadas (`scratchpad/expected-guide.md`, sección "Campos"), en español, sin datos de CVs. Se cachea donde el proveedor lo permita.
- [ ] **Step 4:** Mismo comando → PASS; suite → PASS.
- [ ] **Step 5:** Commit `feat: clientes de LLM para Anthropic, OpenAI y Gemini`.

### Task 4: Integración en el pipeline y la API

**Files:**
- Modify: `src/cv_parser/models.py` (`Meta.extraction: dict[str, str]`), `src/cv_parser/pipeline.py`, `src/cv_parser/api.py`
- Create: `tests/test_pipeline_llm.py`

**Interfaces:**
- Consumes: `make_client`, `LLMClient`, `LLMError`, `redact`, `validate_response`.
- Produces: `parse_document(data, *, convert_timeout=60, today=None, llm: LLMClient | None = None, llm_mode: str = "low_confidence", llm_threshold: float = 0.75) -> ParseResult`; `create_app` crea el cliente una vez con `make_client(settings)` y lo pasa en cada petición.

- [ ] **Step 1: Tests que fallan** (con un `ClienteFalso` que devuelve un dict fijo, falla o cuenta llamadas)

```python
def test_sin_llm_igual_que_antes():
    r = parse_document(read("es_parrafos.docx"))
    assert r.meta.extraction == {"experience": "rules", "education": "rules"}

def test_llm_reemplaza_empleos_y_estudios():
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(respuesta_valida_es()))
    assert r.meta.extraction == {"experience": "llm", "education": "llm"}
    assert sin_confianza(r.extracted.model_dump()) == load_json("expected_es.json")

def test_llm_recibe_texto_sin_contacto():
    falso = ClienteFalso(respuesta_valida_es())
    parse_document(read("es_parrafos.docx"), llm=falso)
    assert "maria.lopez@ejemplo.invalid" not in falso.texto and "1234" not in falso.texto.split("Tel")[-1][:20]

@pytest.mark.parametrize("falla", [LLMError("timeout"), {"educacion": []}, {"education": "x", "experience": []}])
def test_falla_del_llm_deja_reglas(falla, caplog):
    r = parse_document(read("es_parrafos.docx"), llm=ClienteFalso(falla))
    assert r.status == "partial" and "llm_unavailable" in codigos(r)
    assert r.meta.extraction == {"experience": "rules", "education": "rules"}
    assert "Administrativa" not in caplog.text

def test_modo_baja_confianza_no_llama_si_las_reglas_bastan():
    falso = ClienteFalso(respuesta_valida_es())
    r = parse_document(read("es_parrafos.docx"), llm=falso, llm_mode="low_confidence", llm_threshold=0.75)
    assert falso.llamadas == 0 and r.meta.extraction == {"experience": "rules", "education": "rules"}

def test_ilegible_no_llama_al_llm():
    falso = ClienteFalso(respuesta_valida_es())
    parse_document(read("es_escaneado.pdf"), llm=falso)
    assert falso.llamadas == 0

def test_api_usa_el_cliente_configurado(monkeypatch):
    monkeypatch.setattr(api, "make_client", lambda settings: ClienteFalso(respuesta_valida_es()))
    body = TestClient(create_app(Settings(llm_provider="anthropic", llm_model="x"))).post("/v1/parse", files={"file": ("a.docx", read("es_parrafos.docx"))}).json()
    assert body["meta"]["extraction"]["experience"] == "llm"
```

- [ ] **Step 2:** `docker compose run --rm api pytest tests/test_pipeline_llm.py -v` → FAIL.
- [ ] **Step 3:** Implementar. Con `llm` y modo `low_confidence`, solo se consulta si la confianza de `experience` o `education` de las reglas es menor que `CV_PARSER_LLM_THRESHOLD` o si la sección existe y no dio entradas; se reemplaza solo esa sección. Con modo `always`, siempre. Se llama `llm.extract(redact(texto_en_orden))`; `validate_response` arma las listas; su confianza alimenta `Confidence` como hoy. Se registra en log `provider model input_tokens output_tokens duration_ms` o la clase de error. Respuesta sin `education`/`experience` como listas es `LLMError`.
- [ ] **Step 4:** Mismo comando y suite completa → PASS (incluye `test_contract.py` y `test_no_abre_conexiones`).
- [ ] **Step 5:** Commit `feat: integra el LLM opcional en el pipeline`.

### Task 5: Medición con LLM

**Files:**
- Modify: `eval/run_eval.py`, `tests/test_eval_cli.py`

**Interfaces:**
- Consumes: `make_client`, `Settings`, `parse_document(..., llm=...)`.
- Produces: opciones `--provider P --model M` (por defecto sin LLM), `--split all` (los 41, marcado como optimista), y `--open-reserve` que, con LLM, se puede abrir una sola vez por par proveedor/modelo (`split.json["llm_reserve_opened"]`). El reporte agrega `provider`, `model`, `mode`, el % de CVs y de secciones que fueron al LLM, tokens totales y costo estimado con la tabla de precios de `eval/prices.py`.

- [ ] **Step 1: Tests que fallan** (con un cliente falso inyectado por `monkeypatch` sobre `run_eval.make_client`)

```python
def test_reporte_con_llm_registra_proveedor_y_tokens(muestra, monkeypatch, capsys): ...
    # --init, luego --split tuning --provider anthropic --model m: el JSON trae provider "anthropic", model "m" y tokens > 0
def test_reserva_llm_una_vez_por_modelo(muestra, monkeypatch): ...
    # --open-reserve --provider anthropic --model a: 0; repetir: 2; con --model b: 0
def test_split_all_marca_optimista(muestra, monkeypatch): ...
    # --split all: el JSON trae "optimistic": true y cuenta los CVs de ambos grupos
```

Los tres llevan esas comprobaciones como asserts y verifican que la consola y `reportes/` no contienen "Maria".

- [ ] **Step 2:** `docker compose run --rm api pytest tests/test_eval_cli.py -v` → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Mismo comando y suite → PASS.
- [ ] **Step 5:** Commit `feat: medicion con LLM por proveedor y modelo`.

### Task 6: Medir con la muestra

Depende de las claves en `.env`. Sin clave de un proveedor, se mide solo con los que haya.

- [ ] **Step 1:** Ronda base en afinado con `claude-haiku-5-5`, `claude-sonnet-5-5`, `gemini-3.1-flash-lite` y `gemini-2.5-flash`, en modo `low_confidence` y `always`:
  `docker compose run --rm -v <muestra>:/muestra api python eval/run_eval.py --sample-dir /muestra --split tuning --provider anthropic --model claude-haiku-5-5` (y `claude-sonnet-5-5`). Expected: reporte con cifras y costo.
- [ ] **Step 2:** Hasta 3 rondas de afinado del prompt y la validación, solo con los 29 de afinado. Por cada patrón, primero un test con datos inventados; `git diff --cached` antes de cada commit para confirmar que no entra nada de la muestra.
- [ ] **Step 3:** Congelar: `git tag llm-congelado`. Abrir la reserva una vez con las reglas v2 sin LLM y una vez por proveedor/modelo/modo elegido (`--open-reserve --provider ... --model ...`), y correr `--split all`.
- [ ] **Step 4:** Reportar al usuario: cifras de reserva por sección, proveedor y modelo; costo real por CV y proyección a 1,000 y 2,000 CVs al día; patrones que fallan; recomendación.
- [ ] **Step 5:** Recordar al usuario borrar `.env` y rotar las claves usadas en la prueba.

### Task 7: Nombre, título y resumen también con el LLM

**Files:**
- Modify: `src/cv_parser/llm/schema.py`, `src/cv_parser/llm/prompt.py`, `src/cv_parser/llm/validate.py`, `src/cv_parser/pipeline.py`, `src/cv_parser/models.py` (descripción de `extraction`)
- Create: `tests/test_llm_header.py`

**Interfaces:**
- Produces: `RESPONSE_SCHEMA` agrega `name`, `headline`, `summary` (cadena o null). `validate_header(raw: dict, source_text: str) -> tuple[dict[str, str | None], list[ParseWarning]]`. `meta.extraction` agrega `contact`, `headline` y `summary` con `rules` o `llm`.

- [ ] **Step 1: Tests que fallan**
  - nombre, título y resumen que están en el texto pasan; los que no, se vacían con `llm_rejected` (`section` = `contact`, `headline` o `summary`);
  - con el LLM, `extracted.contact.name`, `headline` y `summary` salen del LLM cuando son válidos y de las reglas cuando el LLM da null o algo inválido; correo y teléfono siempre de las reglas;
  - `meta.extraction` dice de dónde salió cada uno.
- [ ] **Step 2:** correr y ver que fallan.
- [ ] **Step 3:** implementar. El resumen se valida por renglones y oraciones contenidas en el texto, como la descripción.
- [ ] **Step 4:** suite completa; medir afinado con Haiku y Sonnet.
- [ ] **Step 5:** commit `feat: el LLM tambien arma nombre, titulo y resumen`.

### Task 8: Repo listo para el equipo

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-11-09-cv-parser-design.md`, planes en `docs/superpowers/plans/`, `.gitignore`, `.dockerignore`, `tests/test_contract.py`
- Create: `AGENTS.md`, `CLAUDE.local.md` (ignorado por git), `docs/integracion.md`, `docs/costos-y-comparativas.md`, `docs/medicion.md`, `tests/conftest.py`

- [ ] **Step 1: Test que falla:** ni el código, ni la documentación, ni el contrato mencionan a un consumidor (nombres de consumidores y rutas locales).
- [ ] **Step 2:** documentación genérica: qué es, cómo se instala como módulo en cualquier sistema (contenedor o servicio HTTP), contrato y errores con ejemplos, configuración, LLM opcional, costos y comparativas medidos, cómo medir, instrucciones para agentes (`AGENTS.md`, que `CLAUDE.md` importa). Las reglas locales del usuario pasan a `CLAUDE.local.md`, ignorado por git.
- [ ] **Step 3:** endurecer lo que la revisión dejó como menor y afecta a quien implemente: `.env*` en `.dockerignore` y `.gitignore`; `tests/conftest.py` borra claves y variables `CV_PARSER_LLM_*` en las pruebas.
- [ ] **Step 4:** suite completa y test de referencias en verde.
- [ ] **Step 5:** commit `docs: documentacion para implementar el servicio`.
