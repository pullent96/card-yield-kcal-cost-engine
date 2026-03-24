"""Render enriched data into a final RecipeCard."""
from __future__ import annotations

from card_engine.models import (
    CostResult,
    KcalResult,
    ParsedRecipe,
    RecipeCard,
    YieldResult,
)


def render_recipe_card(
    parsed: ParsedRecipe,
    cost_results: list[CostResult],
    kcal_results: list[KcalResult],
    yield_result: YieldResult,
) -> RecipeCard:
    """Combine parsed recipe + enrichment results into a RecipeCard."""

    # --- Cost aggregation ---
    total_cost_low = sum(r.range.low for r in cost_results)
    total_cost_mid = sum(r.range.mid for r in cost_results)
    total_cost_high = sum(r.range.high for r in cost_results)

    portions = yield_result.portions or 1
    cost_per_portion = total_cost_mid / portions if portions else 0.0

    # --- Kcal aggregation ---
    total_kcal_low = sum(r.range.low for r in kcal_results)
    total_kcal_mid = sum(r.range.mid for r in kcal_results)
    total_kcal_high = sum(r.range.high for r in kcal_results)

    kcal_per_portion = total_kcal_mid / portions if portions else 0.0

    return RecipeCard(
        title=parsed.title,
        slug=parsed.slug,
        portions=portions,
        total_yield_g=yield_result.total_yield_g,
        cost_low=round(total_cost_low, 2),
        cost_mid=round(total_cost_mid, 2),
        cost_high=round(total_cost_high, 2),
        cost_per_portion_mid=round(cost_per_portion, 2),
        kcal_low=round(total_kcal_low, 1),
        kcal_mid=round(total_kcal_mid, 1),
        kcal_high=round(total_kcal_high, 1),
        kcal_per_portion_mid=round(kcal_per_portion, 1),
        ingredients=parsed.ingredients,
        method=parsed.method,
        notes=parsed.notes,
        cost_breakdown=cost_results,
        kcal_breakdown=kcal_results,
    )


def recipe_card_to_dict(card: RecipeCard) -> dict:
    """Serialise a RecipeCard to a JSON-compatible dict."""
    return {
        "title": card.title,
        "slug": card.slug,
        "portions": card.portions,
        "total_yield_g": card.total_yield_g,
        "cost": {
            "low": card.cost_low,
            "mid": card.cost_mid,
            "high": card.cost_high,
            "per_portion_mid": card.cost_per_portion_mid,
        },
        "kcal": {
            "low": card.kcal_low,
            "mid": card.kcal_mid,
            "high": card.kcal_high,
            "per_portion_mid": card.kcal_per_portion_mid,
        },
        "ingredients": [
            {
                "key": ing.key,
                "name": ing.name,
                "raw_text": ing.raw_text,
                "quantity": ing.quantity,
                "unit": ing.unit,
            }
            for ing in card.ingredients
        ],
        "method": card.method,
        "notes": card.notes,
        "cost_breakdown": [
            {
                "ingredient_key": r.ingredient_key,
                "used_cost_mid": r.used_cost_mid,
                "low": r.range.low,
                "mid": r.range.mid,
                "high": r.range.high,
                "source_urls": r.source_urls,
            }
            for r in card.cost_breakdown
        ],
        "kcal_breakdown": [
            {
                "ingredient_key": r.ingredient_key,
                "total_kcal_mid": r.total_kcal_mid,
                "low": r.range.low,
                "mid": r.range.mid,
                "high": r.range.high,
                "source_urls": r.source_urls,
            }
            for r in card.kcal_breakdown
        ],
    }
