"""Tests for the recipe text parser."""
import pytest
from card_engine.parser import parse_recipe_text, _slugify, _ingredient_key


CHILLI_TEXT = """\
TITLE: Chilli Con Carne

BASE:
- 500g beef mince
- 2 onions
- 3 cloves garlic
- 400g tin chopped tomatoes
- 1 tbsp chilli powder

METHOD:
1. Brown the beef mince.
2. Add onions and garlic, cook 5 mins.
3. Add tomatoes and spices, simmer 30 mins.

NOTES:
- Serve with rice or bread.
"""


class TestSlugify:
    def test_basic(self):
        assert _slugify("Chilli Con Carne") == "chilli-con-carne"

    def test_special_chars(self):
        assert _slugify("Café au lait!") == "cafe-au-lait"

    def test_numbers(self):
        assert _slugify("Recipe 123") == "recipe-123"


class TestIngredientKey:
    def test_simple(self):
        assert _ingredient_key("beef mince") == "beef_mince"

    def test_with_numbers(self):
        key = _ingredient_key("kidney beans")
        assert key == "kidney_beans"


class TestParseRecipeText:
    def test_title_extracted(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        assert recipe.title == "Chilli Con Carne"

    def test_slug(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        assert recipe.slug == "chilli-con-carne"

    def test_ingredient_count(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        assert len(recipe.ingredients) == 5

    def test_ingredient_quantity_and_unit(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        mince = next(i for i in recipe.ingredients if "mince" in i.name)
        assert mince.quantity == 500.0
        assert mince.unit == "g"

    def test_ingredient_tbsp(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        chilli = next(i for i in recipe.ingredients if "chilli" in i.name)
        assert chilli.quantity == 1.0
        assert chilli.unit == "tbsp"

    def test_method_steps_count(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        assert len(recipe.method) == 3

    def test_method_step_no_numbering(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        # Step numbers should be stripped
        assert not recipe.method[0].startswith("1.")

    def test_notes_extracted(self):
        recipe = parse_recipe_text(CHILLI_TEXT)
        assert len(recipe.notes) == 1

    def test_implicit_title(self):
        """First non-blank line becomes title when no TITLE: prefix."""
        text = "My Recipe\n\nBASE:\n- 200g flour\n\nMETHOD:\n1. Mix.\n"
        recipe = parse_recipe_text(text)
        assert recipe.title == "My Recipe"

    def test_empty_sections(self):
        text = "TITLE: Empty\n\nBASE:\n\nMETHOD:\n"
        recipe = parse_recipe_text(text)
        assert recipe.title == "Empty"
        assert recipe.ingredients == []
        assert recipe.method == []

    def test_fraction_quantity(self):
        text = "TITLE: Test\n\nBASE:\n- 1/2 tsp salt\n\nMETHOD:\n1. Mix.\n"
        recipe = parse_recipe_text(text)
        assert len(recipe.ingredients) == 1
        assert abs(recipe.ingredients[0].quantity - 0.5) < 0.001
        assert recipe.ingredients[0].unit == "tsp"
