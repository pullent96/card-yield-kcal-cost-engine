"""Tests for the renderer (recipe card assembly)."""
from __future__ import annotations

import pytest

from card_engine.models import (
    CostResult,
    IngredientLine,
    KcalResult,
    Range,
    YieldResult,
)
from card_engine.parser import parse_recipe_text
from card_engine.renderer import recipe_card_to_dict, render_recipe_card

RECIPE_TEXT = """\
TITLE: Pasta Arrabbiata

BASE:
- 400g pasta
- 200g tinned tomatoes
- 2 cloves garlic

METHOD:
1. Cook pasta.
2. Make sauce.
3. Combine.
"""


class TestRenderRecipeCard:
    def _parsed(self):
        return parse_recipe_text(RECIPE_TEXT)

    def _cost_results(self):
        return [
            CostResult("pasta", 1.20, Range(1.00, 1.20, 1.50)),
            CostResult("tinned_tomatoes", 0.45, Range(0.35, 0.45, 0.55)),
        ]

    def _kcal_results(self):
        return [
            KcalResult("pasta", 680.0, Range(660.0, 680.0, 700.0)),
        ]

    def _yield_result(self, portions=4):
        return YieldResult(portions=portions, total_yield_g=600.0)

    def test_title_propagated(self):
        card = render_recipe_card(self._parsed(), self._cost_results(), self._kcal_results(), self._yield_result())
        assert card.title == "Pasta Arrabbiata"

    def test_portions_from_yield(self):
        card = render_recipe_card(self._parsed(), self._cost_results(), self._kcal_results(), self._yield_result(portions=6))
        assert card.portions == 6

    def test_cost_totals(self):
        card = render_recipe_card(self._parsed(), self._cost_results(), self._kcal_results(), self._yield_result())
        assert card.cost_mid == pytest.approx(1.65, rel=0.01)
        assert card.cost_low == pytest.approx(1.35, rel=0.01)
        assert card.cost_high == pytest.approx(2.05, rel=0.01)

    def test_cost_per_portion(self):
        card = render_recipe_card(self._parsed(), self._cost_results(), self._kcal_results(), self._yield_result(portions=4))
        assert card.cost_per_portion_mid == pytest.approx(1.65 / 4, rel=0.01)

    def test_kcal_totals(self):
        card = render_recipe_card(self._parsed(), self._cost_results(), self._kcal_results(), self._yield_result())
        assert card.kcal_mid == pytest.approx(680.0, rel=0.01)

    def test_no_enrichment_gives_zero_totals(self):
        card = render_recipe_card(self._parsed(), [], [], self._yield_result())
        assert card.cost_mid == 0.0
        assert card.kcal_mid == 0.0

    def test_method_propagated(self):
        card = render_recipe_card(self._parsed(), [], [], self._yield_result())
        assert len(card.method) == 3

    def test_ingredients_propagated(self):
        card = render_recipe_card(self._parsed(), [], [], self._yield_result())
        assert len(card.ingredients) == 3


class TestRecipeCardToDict:
    def test_dict_has_required_keys(self):
        parsed = parse_recipe_text(RECIPE_TEXT)
        yield_result = YieldResult(portions=4, total_yield_g=600.0)
        card = render_recipe_card(parsed, [], [], yield_result)
        d = recipe_card_to_dict(card)
        for key in ("title", "slug", "portions", "cost", "kcal", "ingredients", "method"):
            assert key in d

    def test_cost_section_keys(self):
        parsed = parse_recipe_text(RECIPE_TEXT)
        card = render_recipe_card(parsed, [], [], YieldResult(4, 600.0))
        d = recipe_card_to_dict(card)
        assert all(k in d["cost"] for k in ("low", "mid", "high", "per_portion_mid"))

    def test_kcal_section_keys(self):
        parsed = parse_recipe_text(RECIPE_TEXT)
        card = render_recipe_card(parsed, [], [], YieldResult(4, 600.0))
        d = recipe_card_to_dict(card)
        assert all(k in d["kcal"] for k in ("low", "mid", "high", "per_portion_mid"))
