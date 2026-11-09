"""Comparación campo por campo entre la respuesta esperada y la del parser."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

TEXT_THRESHOLD = 0.85
LOOSE_THRESHOLD = 0.7
LOOSE_FIELDS = {"description", "summary"}
EXACT_FIELDS = {"level", "country_code"}
IGNORED_FIELDS = {"confidence"}
MIN_PAIR_SIMILARITY = 0.4
SECTIONS = ("contact", "headline", "summary", "education", "experience")


@dataclass(frozen=True)
class Counts:
    correct: int = 0
    empty: int = 0
    incorrect: int = 0

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.correct + other.correct, self.empty + other.empty, self.incorrect + other.incorrect)

    @property
    def total(self) -> int:
        return self.correct + self.empty + self.incorrect

    def as_dict(self) -> dict:
        t = self.total or 1
        return {"correct": self.correct, "empty": self.empty, "incorrect": self.incorrect,
                "pct_correct": round(100 * self.correct / t, 1), "pct_incorrect": round(100 * self.incorrect / t, 1)}


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def similar(a: str, b: str) -> float:
    a, b = clean(a), clean(b)
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _has_value(value) -> bool:
    return value not in (None, "", False, [], {})


def _field(name: str, expected, actual) -> Counts:
    if isinstance(expected, dict) or isinstance(actual, dict):
        return score(expected if isinstance(expected, dict) else {}, actual if isinstance(actual, dict) else {})
    exp_has, act_has = _has_value(expected), _has_value(actual)
    if not exp_has and not act_has:
        return Counts()
    if exp_has and not act_has:
        return Counts(empty=1)
    if not exp_has:
        return Counts(incorrect=1)
    if isinstance(expected, bool) or isinstance(expected, (int, float)) or name in EXACT_FIELDS:
        return Counts(correct=1) if expected == actual else Counts(incorrect=1)
    threshold = LOOSE_THRESHOLD if name in LOOSE_FIELDS else TEXT_THRESHOLD
    return Counts(correct=1) if similar(expected, actual) >= threshold else Counts(incorrect=1)


def score(expected: dict, actual: dict) -> Counts:
    """Compara dos objetos plano o anidados. Los campos vacíos en ambos lados no cuentan."""
    expected = expected or {}
    actual = actual or {}
    total = Counts()
    for name in sorted(set(expected) | set(actual)):
        if name in IGNORED_FIELDS:
            continue
        total += _field(name, expected.get(name), actual.get(name))
    return total


def _pair_key(entry: dict) -> str:
    if "position" in entry or "company" in entry:
        return f"{entry.get('position') or ''} {entry.get('company') or ''}"
    return f"{entry.get('level_text') or ''} {entry.get('institution') or ''}"


def _pairs(expected: list[dict], actual: list[dict]) -> list[tuple[int, int]]:
    ranked = sorted(
        ((similar(_pair_key(e), _pair_key(a)), i, j) for i, e in enumerate(expected) for j, a in enumerate(actual)),
        reverse=True,
    )
    used_e: set[int] = set()
    used_a: set[int] = set()
    pairs = []
    for sim, i, j in ranked:
        if sim < MIN_PAIR_SIMILARITY or i in used_e or j in used_a:
            continue
        used_e.add(i)
        used_a.add(j)
        pairs.append((i, j))
    return pairs


def score_entries(expected: list[dict], actual: list[dict]) -> Counts:
    pairs = _pairs(expected, actual)
    total = sum((score(expected[i], actual[j]) for i, j in pairs), Counts())
    matched_e = {i for i, _ in pairs}
    matched_a = {j for _, j in pairs}
    total += sum((score(e, {}) for i, e in enumerate(expected) if i not in matched_e), Counts())
    total += sum((score({}, a) for j, a in enumerate(actual) if j not in matched_a), Counts())
    return total


def score_entries_by_actual(expected: list[dict], actual: list[dict]) -> list[Counts]:
    """Puntaje de cada entrada producida, en su orden; una inventada cuenta todos sus campos como incorrectos."""
    by_actual = {j: score(expected[i], actual[j]) for i, j in _pairs(expected, actual)}
    return [by_actual.get(j, score({}, a)) for j, a in enumerate(actual)]


def score_cv(expected: dict, actual: dict) -> dict[str, Counts]:
    return {
        "contact": score(expected.get("contact") or {}, actual.get("contact") or {}),
        "headline": _field("headline", expected.get("headline"), actual.get("headline")),
        "summary": _field("summary", expected.get("summary"), actual.get("summary")),
        "education": score_entries(expected.get("education") or [], actual.get("education") or []),
        "experience": score_entries(expected.get("experience") or [], actual.get("experience") or []),
    }


def verdict(one_column: Counts, overall: Counts) -> bool:
    """Al menos 80 % correctos en CVs de una columna y como máximo 5 % incorrectos en toda la muestra."""
    if one_column.total == 0 or overall.total == 0:
        return False
    return one_column.correct / one_column.total >= 0.8 and overall.incorrect / overall.total <= 0.05
