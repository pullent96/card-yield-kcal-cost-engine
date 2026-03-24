"""Tests for the backward-compatible calculator module."""
import pytest

from card_engine.calculator import calculate_card_metrics, CardMetrics


class _FakeIngredient:
    def __init__(self, cost: float, kcal: float):
        self.ingredient_cost = cost
        self.ingredient_kcal = kcal


class _FakeCard:
    def __init__(self, servings: int, ingredients):
        self.servings = servings
        self.ingredients = ingredients


class TestCalculateCardMetrics:
    def test_basic(self):
        card = _FakeCard(
            servings=4,
            ingredients=[
                _FakeIngredient(cost=2.00, kcal=200.0),
                _FakeIngredient(cost=1.50, kcal=150.0),
            ],
        )
        result = calculate_card_metrics(card)
        assert result.total_cost == pytest.approx(3.50, rel=0.001)
        assert result.total_kcal == pytest.approx(350.0, rel=0.001)
        assert result.cost_per_serving == pytest.approx(0.88, rel=0.001)
        assert result.kcal_per_serving == pytest.approx(87.5, rel=0.001)

    def test_single_serving(self):
        card = _FakeCard(
            servings=1,
            ingredients=[_FakeIngredient(cost=5.00, kcal=500.0)],
        )
        result = calculate_card_metrics(card)
        assert result.cost_per_serving == 5.00
        assert result.kcal_per_serving == 500.0

    def test_zero_ingredients(self):
        card = _FakeCard(servings=4, ingredients=[])
        result = calculate_card_metrics(card)
        assert result.total_cost == 0.0
        assert result.total_kcal == 0.0

    def test_returns_card_metrics(self):
        card = _FakeCard(servings=2, ingredients=[_FakeIngredient(2.0, 100.0)])
        result = calculate_card_metrics(card)
        assert isinstance(result, CardMetrics)
