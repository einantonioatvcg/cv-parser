import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from cv_parser.api import create_app
from cv_parser.config import Settings


def test_openapi_publica_contrato():
    spec = TestClient(create_app(Settings())).get("/openapi.json").json()
    assert "/v1/parse" in spec["paths"]
    assert {"status", "meta", "warnings", "confidence", "extracted"} <= set(spec["components"]["schemas"]["ParseResult"]["properties"])
    respuestas = spec["paths"]["/v1/parse"]["post"]["responses"]
    assert {"200", "400", "401", "413", "415", "422", "500"} <= set(respuestas)


# Términos de consumidores conocidos, como hash para no escribirlos aquí. Rutas locales de Linux, macOS o Windows.
FORBIDDEN_HASHES = {
    "917538ec59fa94960927914082aec51bd4ca4ab1e7cba2df7f88215725a713f6",
    "a4963c49961afb237b424cf89f69899c335dd77ec4681e9402c0040cd05b17c0",
    "d786578f5a9359c5953a8ffe8b2caaa8ab9f964e1ca7314e8bb53a3bf6315fa9",
    "f31dd822e7fcc0ff5738e5a2fdf3063251821a2189351b143f11b8968c97a59c",
}
LOCAL_PATH = re.compile(r"/home/[a-z]|/Users/[A-Za-z]|[A-Z]:\\\\Users", re.I)


def mentions_consumer(text: str) -> bool:
    """Busca palabras sueltas y frases de hasta 3 palabras cuyo hash esté en la lista."""
    import hashlib
    import unicodedata

    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
    words = re.findall(r"[a-z0-9]+", folded)
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            if hashlib.sha256(phrase.encode()).hexdigest() in FORBIDDEN_HASHES:
                return True
    return False


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".cfg", ""}
SKIP_DIRS = {".git", ".superpowers", "__pycache__", ".pytest_cache", "fixtures"}
SKIP_FILES = {"CLAUDE.local.md", ".env"}


def _repo_text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS) and path.name not in SKIP_FILES:
            if path.suffix in TEXT_SUFFIXES and not path.name.endswith(".egg-info"):
                yield path


def test_repo_sin_referencias_a_consumidores_ni_rutas_locales():
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in _repo_text_files()
            for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
            if mentions_consumer(line) or LOCAL_PATH.search(line)]
    assert hits == []


def test_sin_referencias_a_consumidores():
    texto = "\n".join(p.read_text() for p in Path("src").rglob("*.py"))
    texto += json.dumps(TestClient(create_app(Settings())).get("/openapi.json").json())
    assert not mentions_consumer(texto)
