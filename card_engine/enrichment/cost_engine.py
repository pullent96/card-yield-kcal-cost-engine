"""Cost engine: compute ingredient used-cost from retailer evidence URLs."""
from __future__ import annotations

import statistics
from typing import Optional

from card_engine.models import CostResult, IngredientLine, Range
from card_engine.providers.base import ProviderResult, extract_from_url


def _used_cost(
    ingredient: IngredientLine,
    result: ProviderResult,
) -> Optional[float]:
    """Calculate cost of the quantity used from a provider result."""
    if result.cost_per_100g is None:
        return None
    qty = ingredient.quantity or 0.0
    unit = ingredient.unit or "g"
    # Convert ingredient quantity to grams/ml
    to_g = {"g": 1.0, "ml": 1.0, "kg": 1000.0, "l": 1000.0}
    multiplier = to_g.get(unit, 1.0)
    qty_g = qty * multiplier
    return result.cost_per_100g * (qty_g / 100.0)


def _aggregate_range(values: list[float]) -> Range:
    """Return low/mid/high from a list of cost values."""
    if not values:
        return Range(low=0.0, mid=0.0, high=0.0)
    return Range(
        low=min(values),
        mid=statistics.median(values),
        high=max(values),
    )


def run_cost_engine(
    ingredients: list[IngredientLine],
    evidence: dict[str, list[str]],
    fetch_fn=None,
) -> list[CostResult]:
    """
    Enrich each ingredient with cost data.

    :param ingredients: list of parsed ingredient lines
    :param evidence: mapping of ingredient_key -> list of retailer URLs
    :param fetch_fn: optional HTTP fetch override (for testing)
    :return: list of CostResult
    """
    results = []
    for ing in ingredients:
        urls = evidence.get(ing.key, [])
        used_costs: list[float] = []
        valid_urls: list[str] = []
        for url in urls:
            try:
                pr = extract_from_url(url, fetch_fn=fetch_fn)
                cost = _used_cost(ing, pr)
                if cost is not None:
                    used_costs.append(cost)
                    valid_urls.append(url)
            except Exception:
                pass  # skip failed URLs gracefully

        if not used_costs:
            continue

        rng = _aggregate_range(used_costs)
        results.append(
            CostResult(
                ingredient_key=ing.key,
                used_cost_mid=rng.mid,
                range=rng,
                source_urls=valid_urls,
            )
        )
    return results
