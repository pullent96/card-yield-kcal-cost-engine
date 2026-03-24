# Card Yield Kcal Cost Engine

A small Python engine for calculating:

- Total card cost
- Total card calories (kcal)
- Per-serving cost and kcal
- Yield-aware ingredient usage (raw quantity vs edible quantity)

## Quick Start

Requirements: Python 3.10+

Run tests:

python -m unittest discover -s tests -p "test_*.py"

Run CLI example:

python -m card_engine.cli --file examples/sample_card.json

## Data Model

Each ingredient includes:

- name: text label
- quantity_raw: input quantity before trimming/cooking losses
- yield_fraction: edible yield (0 < yield_fraction <= 1)
- cost_per_raw_unit: cost based on raw quantity unit
- kcal_per_edible_unit: kcal based on edible quantity unit

Derived values:

- edible_quantity = quantity_raw * yield_fraction
- ingredient_cost = quantity_raw * cost_per_raw_unit
- ingredient_kcal = edible_quantity * kcal_per_edible_unit

Card totals:

- total_cost = sum(ingredient_cost)
- total_kcal = sum(ingredient_kcal)
- cost_per_serving = total_cost / servings
- kcal_per_serving = total_kcal / servings

## Example JSON

See examples/sample_card.json

## Library Usage

from card_engine.models import Ingredient, RecipeCard
from card_engine.calculator import calculate_card_metrics

card = RecipeCard(
	name="Chicken Rice Bowl",
	servings=4,
	ingredients=[
		Ingredient(
			name="Chicken Thigh",
			quantity_raw=1.2,
			yield_fraction=0.8,
			cost_per_raw_unit=6.5,
			kcal_per_edible_unit=215,
			unit="kg",
		),
		Ingredient(
			name="Rice",
			quantity_raw=0.4,
			yield_fraction=1.0,
			cost_per_raw_unit=2.2,
			kcal_per_edible_unit=360,
			unit="kg",
		),
	],
)

result = calculate_card_metrics(card)
print(result)
