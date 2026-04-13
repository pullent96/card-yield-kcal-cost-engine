"""Backward-compatible calculator helpers (used by original CLI)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CardMetrics:
    total_cost: float
    total_kcal: float
    cost_per_serving: float
    kcal_per_serving: float


def calculate_card_metrics(card) -> CardMetrics:  # type: ignore[return]
    """Calculate totals for a RecipeCard-like object.

    Accepts any object with:
      - servings: int
      - ingredients: list of objects with ingredient_cost and ingredient_kcal
        *or* the new IngredientLine objects (returns zero-values in that case).
    """
    total_cost = 0.0
    total_kcal = 0.0

    for ing in getattr(card, "ingredients", []):
        total_cost += getattr(ing, "ingredient_cost", 0.0)
        total_kcal += getattr(ing, "ingredient_kcal", 0.0)

    servings = max(getattr(card, "servings", 1), 1)
    return CardMetrics(
        total_cost=round(total_cost, 2),
        total_kcal=round(total_kcal, 1),
        cost_per_serving=round(total_cost / servings, 2),
        kcal_per_serving=round(total_kcal / servings, 1),
    )
