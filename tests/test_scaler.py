"""Unit tests for the scaler module."""

import pytest

from nemlig_shopper.recipe_parser import Ingredient, Recipe
from nemlig_shopper.scaler import (
    ScaledIngredient,
    calculate_product_quantity,
    calculate_scale_factor,
    format_scale_info,
    round_to_practical,
    scale_ingredient,
    scale_quantity,
    scale_recipe,
)


class TestCalculateScaleFactor:
    """Tests for calculate_scale_factor function."""

    def test_multiplier_overrides_all(self):
        factor = calculate_scale_factor(original_servings=4, target_servings=8, multiplier=3.0)
        assert factor == 3.0

    def test_target_servings_with_original(self):
        factor = calculate_scale_factor(original_servings=4, target_servings=8)
        assert factor == 2.0

    def test_target_servings_half(self):
        factor = calculate_scale_factor(original_servings=8, target_servings=4)
        assert factor == 0.5

    def test_target_servings_without_original_raises(self):
        with pytest.raises(ValueError, match="original serving size unknown"):
            calculate_scale_factor(original_servings=None, target_servings=8)

    def test_no_scaling_returns_one(self):
        factor = calculate_scale_factor(original_servings=4)
        assert factor == 1.0

    def test_no_scaling_with_none_servings(self):
        factor = calculate_scale_factor(original_servings=None)
        assert factor == 1.0


class TestScaleQuantity:
    """Tests for scale_quantity function."""

    def test_double(self):
        result = scale_quantity(2.0, 2.0)
        assert result == 4.0

    def test_half(self):
        result = scale_quantity(2.0, 0.5)
        assert result == 1.0

    def test_none_quantity(self):
        result = scale_quantity(None, 2.0)
        assert result is None

    def test_zero_scale(self):
        result = scale_quantity(5.0, 0)
        assert result == 0.0

    def test_fractional_scale(self):
        result = scale_quantity(3.0, 1.5)
        assert result == 4.5


class TestRoundToPractical:
    """Tests for round_to_practical function."""

    def test_countable_rounds_up(self):
        # Pieces should round up
        result = round_to_practical(2.3, "pieces")
        assert result == 3

    def test_countable_cloves(self):
        result = round_to_practical(1.5, "cloves")
        assert result == 2

    def test_countable_cans(self):
        result = round_to_practical(1.1, "cans")
        assert result == 2

    def test_small_quantity_rounds_to_quarter(self):
        # 0.3 should round to 0.25
        result = round_to_practical(0.3, "cups")
        assert result == 0.25

    def test_small_quantity_half(self):
        result = round_to_practical(0.45, "cups")
        assert result == 0.5

    def test_medium_quantity_rounds_to_half(self):
        # 2.3 should round to 2.5
        result = round_to_practical(2.3, "cups")
        assert result == 2.5

    def test_medium_quantity_whole(self):
        result = round_to_practical(2.8, "cups")
        assert result == 3.0

    def test_large_quantity_rounds_to_whole(self):
        result = round_to_practical(15.3, "g")
        assert result == 15

    def test_zero_quantity(self):
        result = round_to_practical(0, "cups")
        assert result == 0

    def test_no_unit_uses_default_rounding(self):
        result = round_to_practical(2.3, None)
        assert result == 2.5


class TestScaleIngredient:
    """Tests for scale_ingredient function."""

    def test_double_ingredient(self):
        ing = Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups")
        scaled = scale_ingredient(ing, 2.0)
        assert scaled.scaled_quantity == 4.0
        assert scaled.name == "flour"
        assert scaled.unit == "cups"
        assert scaled.scale_factor == 2.0

    def test_half_ingredient(self):
        ing = Ingredient(original="4 tbsp butter", name="butter", quantity=4.0, unit="tbsp")
        scaled = scale_ingredient(ing, 0.5)
        assert scaled.scaled_quantity == 2.0

    def test_ingredient_no_quantity(self):
        ing = Ingredient(original="salt to taste", name="salt")
        scaled = scale_ingredient(ing, 2.0)
        assert scaled.scaled_quantity is None

    def test_ingredient_with_practical_rounding(self):
        ing = Ingredient(original="3 pieces chicken", name="chicken", quantity=3.0, unit="pieces")
        # 3 * 1.5 = 4.5, should round up to 5 for pieces
        scaled = scale_ingredient(ing, 1.5, round_practical=True)
        assert scaled.scaled_quantity == 5

    def test_ingredient_without_practical_rounding(self):
        ing = Ingredient(original="3 pieces chicken", name="chicken", quantity=3.0, unit="pieces")
        scaled = scale_ingredient(ing, 1.5, round_practical=False)
        assert scaled.scaled_quantity == 4.5

    def test_original_ingredient_preserved(self):
        ing = Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups")
        scaled = scale_ingredient(ing, 2.0)
        assert scaled.original is ing


class TestScaledIngredientStr:
    """Tests for ScaledIngredient __str__ method."""

    def test_str_whole_number(self):
        ing = Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups")
        scaled = ScaledIngredient(original=ing, scaled_quantity=4.0, scale_factor=2.0)
        assert str(scaled) == "4 cups flour"

    def test_str_decimal(self):
        ing = Ingredient(original="1 cup sugar", name="sugar", quantity=1.0, unit="cup")
        scaled = ScaledIngredient(original=ing, scaled_quantity=1.5, scale_factor=1.5)
        assert str(scaled) == "1.5 cup sugar"

    def test_str_with_notes(self):
        ing = Ingredient(
            original="1 cup butter (softened)",
            name="butter",
            quantity=1.0,
            unit="cup",
            notes="softened",
        )
        scaled = ScaledIngredient(original=ing, scaled_quantity=2.0, scale_factor=2.0)
        assert str(scaled) == "2 cup butter (softened)"

    def test_str_none_quantity(self):
        ing = Ingredient(original="salt", name="salt")
        scaled = ScaledIngredient(original=ing, scaled_quantity=None, scale_factor=1.0)
        assert str(scaled) == "salt"


class TestScaleRecipe:
    """Tests for scale_recipe function."""

    def test_double_recipe(self):
        recipe = Recipe(
            title="Test",
            servings=4,
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups"),
                Ingredient(original="1 cup sugar", name="sugar", quantity=1.0, unit="cup"),
            ],
        )
        scaled_ings, factor, new_servings = scale_recipe(recipe, multiplier=2.0)

        assert factor == 2.0
        assert new_servings == 8
        assert len(scaled_ings) == 2
        assert scaled_ings[0].scaled_quantity == 4.0
        assert scaled_ings[1].scaled_quantity == 2.0

    def test_scale_by_servings(self):
        recipe = Recipe(
            title="Test",
            servings=4,
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups"),
            ],
        )
        scaled_ings, factor, new_servings = scale_recipe(recipe, target_servings=8)

        assert factor == 2.0
        assert new_servings == 8
        assert scaled_ings[0].scaled_quantity == 4.0

    def test_scale_recipe_no_servings(self):
        recipe = Recipe(
            title="Test",
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups"),
            ],
        )
        scaled_ings, factor, new_servings = scale_recipe(recipe, multiplier=3.0)

        assert factor == 3.0
        assert new_servings is None
        assert scaled_ings[0].scaled_quantity == 6.0

    def test_no_scaling(self):
        recipe = Recipe(
            title="Test",
            servings=4,
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups"),
            ],
        )
        scaled_ings, factor, new_servings = scale_recipe(recipe)

        assert factor == 1.0
        assert new_servings == 4
        assert scaled_ings[0].scaled_quantity == 2.0


class TestCalculateProductQuantity:
    """Tests for calculate_product_quantity function."""

    def test_round_up(self):
        result = calculate_product_quantity(2.3)
        assert result == 3

    def test_whole_number(self):
        result = calculate_product_quantity(2.0)
        assert result == 2

    def test_none_returns_one(self):
        result = calculate_product_quantity(None)
        assert result == 1

    def test_minimum_one(self):
        result = calculate_product_quantity(0.1)
        assert result == 1

    def test_zero_returns_one(self):
        result = calculate_product_quantity(0)
        assert result == 1


class TestFormatScaleInfo:
    """Tests for format_scale_info function."""

    def test_no_scaling(self):
        result = format_scale_info(1.0, 4, 4)
        assert result == "Original recipe (4 servings)"

    def test_no_scaling_no_servings(self):
        result = format_scale_info(1.0, None, None)
        assert result == "Original recipe"

    def test_doubled(self):
        result = format_scale_info(2.0, 4, 8)
        assert result == "Doubled (4 → 8 servings)"

    def test_halved(self):
        result = format_scale_info(0.5, 8, 4)
        assert result == "Halved (8 → 4 servings)"

    def test_tripled(self):
        result = format_scale_info(3.0, 2, 6)
        assert result == "Tripled (2 → 6 servings)"

    def test_custom_scale(self):
        result = format_scale_info(1.5, 4, 6)
        assert result == "Scaled 1.5x (4 → 6 servings)"

    def test_scaled_no_original_servings(self):
        result = format_scale_info(2.0, None, 8)
        assert result == "Doubled (8 servings)"

    def test_scaled_no_servings(self):
        result = format_scale_info(2.0, None, None)
        assert result == "Doubled"
