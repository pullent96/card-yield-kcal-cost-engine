"""Yield engine: compute portions and total yield from evidence URLs or heuristics."""
from __future__ import annotations

import re
import statistics

from card_engine.models import IngredientLine, YieldResult
from card_engine.providers.base import extract_from_url

_DEFAULT_PORTIONS = 10

_PORTIONS_RE = re.compile(
    r"(?:serves?|portions?|makes?)\s*[:\-]?\s*(\d+)",
    re.IGNORECASE,
)
_YIELD_RE = re.compile(
    r"(?:yield|total yield|makes?)\s*[:\-]?\s*([\d.]+)\s*(g|kg|ml|l)\b",
    re.IGNORECASE,
)


def _parse_portions_from_html(html: str) -> int | None:
    """Best-effort search for a portions count in HTML text."""
    m = _PORTIONS_RE.search(html)
    if m:
        return int(m.group(1))
    return None


def _parse_yield_g_from_html(html: str) -> float | None:
    """Best-effort extraction of total yield from HTML."""
    m = _YIELD_RE.search(html)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    multipliers = {"kg": 1000.0, "g": 1.0, "l": 1000.0, "ml": 1.0}
    return val * multipliers.get(unit, 1.0)


def _estimate_yield_from_ingredients(ingredients: list[IngredientLine]) -> float | None:
    """Rough heuristic: sum all g/ml/kg/l quantities."""
    to_g = {"g": 1.0, "ml": 1.0, "kg": 1000.0, "l": 1000.0}
    total = 0.0
    found = False
    for ing in ingredients:
        if ing.unit in to_g and ing.quantity:
            total += ing.quantity * to_g[ing.unit]
            found = True
    return total if found else None


def run_yield_engine(
    ingredients: list[IngredientLine],
    urls: list[str],
    fetch_fn=None,
) -> YieldResult:
    """
    Compute yield result from evidence URLs with ingredient heuristic fallback.

    :param ingredients: parsed ingredient lines (used for weight heuristic)
    :param urls: list of yield evidence URLs
    :param fetch_fn: optional HTTP fetch override (for testing)
    :return: YieldResult
    """
    portions_list: list[int] = []
    yield_list: list[float] = []
    valid_urls: list[str] = []

    fetcher = fetch_fn or (lambda u: __import__("requests").get(
        u, timeout=15, headers={"User-Agent": "RecipeEngine/1.0"}
    ).text)

    for url in urls:
        try:
            html = fetcher(url)
            p = _parse_portions_from_html(html)
            if p:
                portions_list.append(p)
            y = _parse_yield_g_from_html(html)
            if y:
                yield_list.append(y)
            valid_urls.append(url)
        except Exception:
            pass

    portions = (
        int(statistics.median(portions_list)) if portions_list else _DEFAULT_PORTIONS
    )
    if yield_list:
        total_yield_g: float | None = statistics.median(yield_list)
    else:
        total_yield_g = _estimate_yield_from_ingredients(ingredients)

    return YieldResult(
        portions=portions,
        total_yield_g=total_yield_g,
        source_urls=valid_urls,
    )
