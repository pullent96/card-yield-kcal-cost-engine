"""Kcal engine: compute ingredient calorie totals from nutrition evidence URLs."""
from __future__ import annotations

import statistics
from typing import Optional

from card_engine.models import IngredientLine, KcalResult, Range
from card_engine.providers.base import ProviderResult, extract_from_url


def _total_kcal(
    ingredient: IngredientLine,
    result: ProviderResult,
) -> Optional[float]:
    """Calculate total kcal for the quantity used."""
    if result.kcal_per_100g is None:
        return None
    qty = ingredient.quantity or 0.0
    unit = ingredient.unit or "g"
    to_g = {"g": 1.0, "ml": 1.0, "kg": 1000.0, "l": 1000.0}
    multiplier = to_g.get(unit, 1.0)
    qty_g = qty * multiplier
    return result.kcal_per_100g * (qty_g / 100.0)


def _aggregate_range(values: list[float]) -> Range:
    if not values:
        return Range(low=0.0, mid=0.0, high=0.0)
    return Range(
        low=min(values),
        mid=statistics.median(values),
        high=max(values),
    )


def run_kcal_engine(
    ingredients: list[IngredientLine],
    evidence: dict[str, list[str]],
    fetch_fn=None,
) -> list[KcalResult]:
    """
    Enrich each ingredient with kcal data.

    :param ingredients: list of parsed ingredient lines
    :param evidence: mapping of ingredient_key -> list of nutrition/product URLs
    :param fetch_fn: optional HTTP fetch override (for testing)
    :return: list of KcalResult
    """
    results = []
    for ing in ingredients:
        urls = evidence.get(ing.key, [])
        kcal_totals: list[float] = []
        valid_urls: list[str] = []
        for url in urls:
            try:
                pr = extract_from_url(url, fetch_fn=fetch_fn)
                kcal = _total_kcal(ing, pr)
                if kcal is not None:
                    kcal_totals.append(kcal)
                    valid_urls.append(url)
            except Exception:
                pass

        if not kcal_totals:
            continue

        rng = _aggregate_range(kcal_totals)
        results.append(
            KcalResult(
                ingredient_key=ing.key,
                total_kcal_mid=rng.mid,
                range=rng,
                source_urls=valid_urls,
            )
        )
    return results
