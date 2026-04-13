from __future__ import annotations

import math
from dataclasses import replace

from card_engine.models import Ingredient, RecipeCard, RecipeParsed


def half_split_mean(values: list[float]) -> tuple[float, float]:
    """
    Sort values ascending. Split in half.
    lower half = first ceil(n/2) items
    upper half = last ceil(n/2) items
    For odd lengths, middle item goes to both halves.
    Returns (low_avg, high_avg).
    """
    if not values:
        return (0.0, 0.0)
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    half = math.ceil(n / 2)
    low_avg = sum(sorted_vals[:half]) / half
    high_avg = sum(sorted_vals[-half:]) / half
    return (low_avg, high_avg)


def calculate_card_metrics(card: RecipeCard) -> dict:
    """
    Returns:
    {
        total_cost: float,
        total_kcal: float,
        cost_per_serving: float,
        kcal_per_serving: float,
        ingredient_details: list[dict],
    }
    """
    ingredient_details = []
    total_cost = 0.0
    total_kcal = 0.0

    for ing in card.ingredients:
        edible_quantity = ing.quantity_raw * ing.yield_fraction
        ingredient_cost = ing.quantity_raw * ing.cost_per_raw_unit
        ingredient_kcal = edible_quantity * ing.kcal_per_edible_unit

        total_cost += ingredient_cost
        total_kcal += ingredient_kcal

        ingredient_details.append({
            "name": ing.name,
            "quantity_raw": ing.quantity_raw,
            "unit": ing.unit,
            "yield_fraction": ing.yield_fraction,
            "edible_quantity": edible_quantity,
            "ingredient_cost": ingredient_cost,
            "ingredient_kcal": ingredient_kcal,
        })

    servings = card.servings if card.servings > 0 else 1
    return {
        "total_cost": total_cost,
        "total_kcal": total_kcal,
        "cost_per_serving": total_cost / servings,
        "kcal_per_serving": total_kcal / servings,
        "ingredient_details": ingredient_details,
    }


def scale_yield(recipe: RecipeParsed, target_portions: int = 10) -> RecipeParsed:
    """
    Scale ingredient amounts in a RecipeParsed to hit target_portions (8-12).
    Since RecipeParsed stores raw text lines, we scale numeric quantities in place.
    """
    import re
    current_yield = None
    search_text = recipe.title + " " + recipe.notes + " " + recipe.total_time
    m = re.search(r"(?:serves?|portions?|yield[s]?)\s*:?\s*(\d+)", search_text, re.IGNORECASE)
    if m:
        current_yield = int(m.group(1))

    if current_yield is None or current_yield == 0:
        return recipe

    scale_factor = target_portions / current_yield

    def scale_line(line: str) -> str:
        def _replace(m):
            val = float(m.group(0))
            scaled = val * scale_factor
            if scaled == int(scaled):
                return str(int(scaled))
            return f"{scaled:.1f}"
        return re.sub(r"\d+(?:\.\d+)?", _replace, line)

    scaled_ingredients = [scale_line(l) for l in recipe.ingredients_raw]
    return replace(recipe, ingredients_raw=scaled_ingredients)
