"""Sorteo de la reserva por grupos de formato, idioma y columnas."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class SampleItem:
    id: str
    format: str
    language: str
    columns: int


def assign_split(items: list[SampleItem], seed: int) -> dict[str, str]:
    """Una tercera parte va a `reserve`, tomando de un grupo a la vez, empezando por los más pequeños."""
    size = round(len(items) / 3)
    groups: dict[tuple, list[str]] = defaultdict(list)
    for item in sorted(items, key=lambda i: i.id):
        groups[(item.format, item.language, item.columns)].append(item.id)
    rng = random.Random(seed)
    ordered = []
    for key in sorted(groups, key=lambda k: (len(groups[k]), str(k))):
        ids = groups[key][:]
        rng.shuffle(ids)
        ordered.append(ids)
    reserve: list[str] = []
    while len(reserve) < size:
        for ids in ordered:
            if ids and len(reserve) < size:
                reserve.append(ids.pop(0))
    chosen = set(reserve)
    return {item.id: ("reserve" if item.id in chosen else "tuning") for item in items}
