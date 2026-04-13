import unittest
from card_engine.calculator import half_split_mean, calculate_card_metrics
from card_engine.models import Ingredient, RecipeCard


class TestHalfSplitMean(unittest.TestCase):

    def test_even_values(self):
        values = [1.0, 2.0, 3.0, 4.0]
        low, high = half_split_mean(values)
        self.assertAlmostEqual(low, 1.5)
        self.assertAlmostEqual(high, 3.5)

    def test_odd_values(self):
        values = [1.0, 2.0, 3.0]
        low, high = half_split_mean(values)
        self.assertAlmostEqual(low, 1.5)
        self.assertAlmostEqual(high, 2.5)

    def test_single_value(self):
        values = [5.0]
        low, high = half_split_mean(values)
        self.assertAlmostEqual(low, 5.0)
        self.assertAlmostEqual(high, 5.0)

    def test_empty_values(self):
        low, high = half_split_mean([])
        self.assertAlmostEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.0)


class TestCalculateCardMetrics(unittest.TestCase):

    def test_basic_calculation(self):
        card = RecipeCard(
            name="Test Recipe",
            servings=4,
            ingredients=[
                Ingredient(
                    name="Chicken",
                    quantity_raw=1.0,
                    unit="kg",
                    yield_fraction=0.8,
                    cost_per_raw_unit=8.0,
                    kcal_per_edible_unit=200.0,
                ),
                Ingredient(
                    name="Rice",
                    quantity_raw=0.5,
                    unit="kg",
                    yield_fraction=1.0,
                    cost_per_raw_unit=2.0,
                    kcal_per_edible_unit=360.0,
                ),
            ],
        )
        result = calculate_card_metrics(card)
        self.assertAlmostEqual(result["total_cost"], 9.0)
        self.assertAlmostEqual(result["total_kcal"], 340.0)
        self.assertAlmostEqual(result["cost_per_serving"], 2.25)
        self.assertAlmostEqual(result["kcal_per_serving"], 85.0)
        self.assertEqual(len(result["ingredient_details"]), 2)

    def test_zero_yield(self):
        card = RecipeCard(
            name="Zero Yield",
            servings=2,
            ingredients=[
                Ingredient(
                    name="Peeled Veg",
                    quantity_raw=1.0,
                    unit="kg",
                    yield_fraction=0.0,
                    cost_per_raw_unit=3.0,
                    kcal_per_edible_unit=100.0,
                ),
            ],
        )
        result = calculate_card_metrics(card)
        self.assertAlmostEqual(result["total_kcal"], 0.0)
        self.assertAlmostEqual(result["total_cost"], 3.0)
