"""Tests for meal planning and ingredient consolidation."""

from nemlig_shopper.planner import (
    ConsolidatedIngredient,
    MealPlan,
    can_consolidate,
    consolidate_ingredients,
    normalize_ingredient_name,
)
from nemlig_shopper.recipe_parser import Ingredient
from nemlig_shopper.scaler import ScaledIngredient


def make_scaled_ingredient(
    name: str,
    quantity: float | None = None,
    unit: str | None = None,
) -> ScaledIngredient:
    """Helper to create ScaledIngredient for tests."""
    orig = Ingredient(
        original=f"{quantity or ''} {unit or ''} {name}".strip(),
        name=name,
        quantity=quantity,
        unit=unit,
    )
    return ScaledIngredient(
        original=orig,
        scaled_quantity=quantity,
        scale_factor=1.0,
    )


class TestNormalizeIngredientName:
    """Tests for normalize_ingredient_name function."""

    def test_lowercase(self):
        assert normalize_ingredient_name("Onion") == "onion"
        assert normalize_ingredient_name("GARLIC") == "garlic"

    def test_strips_whitespace(self):
        assert normalize_ingredient_name("  onion  ") == "onion"

    def test_english_plurals(self):
        assert normalize_ingredient_name("onions") == "onion"
        assert normalize_ingredient_name("tomatoes") == "tomato"
        assert normalize_ingredient_name("eggs") == "egg"
        assert normalize_ingredient_name("carrots") == "carrot"

    def test_danish_plurals(self):
        assert normalize_ingredient_name("gulerødder") == "gulerod"
        assert normalize_ingredient_name("kartofler") == "kartoffel"
        assert normalize_ingredient_name("tomater") == "tomat"

    def test_singular_unchanged(self):
        assert normalize_ingredient_name("onion") == "onion"
        assert normalize_ingredient_name("garlic") == "garlic"


class TestCanConsolidate:
    """Tests for can_consolidate function."""

    def test_same_weight_units(self):
        assert can_consolidate("g", "kg") is True
        assert can_consolidate("kg", "g") is True

    def test_same_volume_units(self):
        assert can_consolidate("ml", "l") is True
        assert can_consolidate("dl", "ml") is True

    def test_incompatible_units(self):
        assert can_consolidate("g", "ml") is False
        assert can_consolidate("kg", "l") is False

    def test_unknown_same_unit(self):
        # Same unknown units can be consolidated
        assert can_consolidate("cups", "cups") is True
        assert can_consolidate(None, None) is True

    def test_unknown_different_units(self):
        # Different unknown units cannot be consolidated
        assert can_consolidate("bunch", "sprig") is False  # Both unknown
        assert can_consolidate(None, "stk") is False

    def test_recipe_volume_units_consolidate(self):
        # cups and tbsp are both volume units (recipe aliases)
        assert can_consolidate("cups", "tbsp") is True


class TestConsolidateIngredients:
    """Tests for consolidate_ingredients function."""

    def test_single_ingredient(self):
        items = [(make_scaled_ingredient("onion", 2, "stk"), "Recipe A")]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        assert result[0].name == "onion"
        assert result[0].total_quantity == 2
        assert result[0].unit == "stk"
        assert result[0].sources == ["Recipe A"]

    def test_same_ingredient_same_unit(self):
        items = [
            (make_scaled_ingredient("onion", 2, "stk"), "Recipe A"),
            (make_scaled_ingredient("onion", 1, "stk"), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        assert result[0].name == "onion"
        assert result[0].total_quantity == 3
        assert result[0].sources == ["Recipe A", "Recipe B"]

    def test_same_ingredient_plural_forms(self):
        items = [
            (make_scaled_ingredient("onion", 2, "stk"), "Recipe A"),
            (make_scaled_ingredient("onions", 1, "stk"), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        assert result[0].total_quantity == 3

    def test_weight_unit_consolidation(self):
        items = [
            (make_scaled_ingredient("flour", 500, "g"), "Recipe A"),
            (make_scaled_ingredient("flour", 1, "kg"), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        # 500g + 1000g = 1500g = 1.5kg
        assert result[0].total_quantity == 1.5
        assert result[0].unit == "kg"

    def test_volume_unit_consolidation(self):
        items = [
            (make_scaled_ingredient("milk", 500, "ml"), "Recipe A"),
            (make_scaled_ingredient("milk", 2, "dl"), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        # 500ml + 200ml = 700ml = 7dl
        assert result[0].total_quantity == 7
        assert result[0].unit == "dl"

    def test_incompatible_units_kept_separate(self):
        items = [
            (make_scaled_ingredient("tomato", 500, "g"), "Recipe A"),
            (make_scaled_ingredient("tomato", 2, "stk"), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        # Should have 2 separate entries
        assert len(result) == 2

    def test_different_ingredients_separate(self):
        items = [
            (make_scaled_ingredient("onion", 2, "stk"), "Recipe A"),
            (make_scaled_ingredient("garlic", 3, "stk"), "Recipe A"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"onion", "garlic"}

    def test_no_quantity_ingredients(self):
        items = [
            (make_scaled_ingredient("salt", None, None), "Recipe A"),
            (make_scaled_ingredient("salt", None, None), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        assert len(result) == 1
        assert result[0].name == "salt"
        assert result[0].total_quantity is None
        assert result[0].sources == ["Recipe A", "Recipe B"]

    def test_mixed_quantity_no_quantity(self):
        items = [
            (make_scaled_ingredient("pepper", 1, "tsp"), "Recipe A"),
            (make_scaled_ingredient("pepper", None, None), "Recipe B"),
        ]
        result = consolidate_ingredients(items)

        # Should keep separate - one with quantity, one without
        assert len(result) == 2


class TestConsolidatedIngredientStr:
    """Tests for ConsolidatedIngredient string representation."""

    def test_with_quantity_and_unit(self):
        ing = ConsolidatedIngredient(
            name="flour",
            total_quantity=500,
            unit="g",
            sources=["Recipe A"],
        )
        assert str(ing) == "500 g flour"

    def test_with_decimal_quantity(self):
        ing = ConsolidatedIngredient(
            name="milk",
            total_quantity=1.5,
            unit="l",
            sources=["Recipe A"],
        )
        assert str(ing) == "1.5 l milk"

    def test_without_unit(self):
        ing = ConsolidatedIngredient(
            name="eggs",
            total_quantity=3,
            unit=None,
            sources=["Recipe A"],
        )
        assert str(ing) == "3 eggs"

    def test_without_quantity(self):
        ing = ConsolidatedIngredient(
            name="salt",
            total_quantity=None,
            unit=None,
            sources=["Recipe A"],
        )
        assert str(ing) == "salt"


class TestMealPlan:
    """Tests for MealPlan dataclass."""

    def test_recipe_count(self):
        plan = MealPlan(
            recipes=[],  # Empty for this test
            consolidated_ingredients=[],
        )
        assert plan.recipe_count == 0

    def test_ingredient_count(self):
        plan = MealPlan(
            recipes=[],
            consolidated_ingredients=[
                ConsolidatedIngredient("onion", 2, "stk", ["A"]),
                ConsolidatedIngredient("garlic", 3, "stk", ["A"]),
            ],
        )
        assert plan.ingredient_count == 2
