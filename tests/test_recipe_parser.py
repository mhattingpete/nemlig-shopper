"""Unit tests for the recipe_parser module."""

from nemlig_shopper.recipe_parser import (
    Ingredient,
    Recipe,
    parse_ingredient_text,
    parse_ingredients_text,
    parse_quantity,
    parse_recipe_text,
    parse_unit,
)


class TestParseQuantity:
    """Tests for parse_quantity function."""

    def test_simple_integer(self):
        qty, remaining = parse_quantity("2 cups flour")
        assert qty == 2.0
        assert remaining == "cups flour"

    def test_decimal_number(self):
        qty, remaining = parse_quantity("1.5 cups sugar")
        assert qty == 1.5
        assert remaining == "cups sugar"

    def test_fraction(self):
        qty, remaining = parse_quantity("1/2 cup milk")
        assert qty == 0.5
        assert remaining == "cup milk"

    def test_mixed_number(self):
        qty, remaining = parse_quantity("1 1/2 cups flour")
        assert qty == 1.5
        assert remaining == "cups flour"

    def test_unicode_fraction_half(self):
        qty, remaining = parse_quantity("½ cup butter")
        assert qty == 0.5
        assert remaining == "cup butter"

    def test_unicode_fraction_quarter(self):
        qty, remaining = parse_quantity("¼ tsp salt")
        assert qty == 0.25
        assert remaining == "tsp salt"

    def test_unicode_fraction_three_quarters(self):
        qty, remaining = parse_quantity("¾ cup cream")
        assert qty == 0.75
        assert remaining == "cup cream"

    def test_range_takes_higher_value(self):
        qty, remaining = parse_quantity("2-3 cloves garlic")
        assert qty == 3.0
        assert remaining == "cloves garlic"

    def test_no_quantity(self):
        qty, remaining = parse_quantity("salt to taste")
        assert qty is None
        assert remaining == "salt to taste"

    def test_empty_string(self):
        qty, remaining = parse_quantity("")
        assert qty is None
        assert remaining == ""

    def test_danish_decimal_comma(self):
        """Test Danish format with comma as decimal separator."""
        qty, remaining = parse_quantity("0,50 tsk rosmarin")
        assert qty == 0.5
        assert remaining == "tsk rosmarin"

    def test_danish_decimal_comma_larger(self):
        """Test Danish format with larger decimal number."""
        qty, remaining = parse_quantity("1,5 dl fløde")
        assert qty == 1.5
        assert remaining == "dl fløde"


class TestParseUnit:
    """Tests for parse_unit function."""

    def test_cup(self):
        unit, remaining = parse_unit("cup flour")
        assert unit == "cup"
        assert remaining == "flour"

    def test_cups_plural(self):
        unit, remaining = parse_unit("cups flour")
        assert unit == "cups"
        assert remaining == "flour"

    def test_tablespoon(self):
        unit, remaining = parse_unit("tbsp olive oil")
        assert unit == "tbsp"
        assert remaining == "olive oil"

    def test_teaspoon(self):
        unit, remaining = parse_unit("tsp salt")
        assert unit == "tsp"
        assert remaining == "salt"

    def test_grams(self):
        unit, remaining = parse_unit("g butter")
        assert unit == "g"
        assert remaining == "butter"

    def test_kilograms(self):
        unit, remaining = parse_unit("kg potatoes")
        assert unit == "kg"
        assert remaining == "potatoes"

    def test_milliliters(self):
        unit, remaining = parse_unit("ml water")
        assert unit == "ml"
        assert remaining == "water"

    def test_two_word_unit_fluid_ounce(self):
        unit, remaining = parse_unit("fl oz cream")
        assert unit == "fl oz"
        assert remaining == "cream"

    def test_danish_unit_stk(self):
        unit, remaining = parse_unit("stk æbler")
        assert unit == "stk"
        assert remaining == "æbler"

    def test_no_unit(self):
        unit, remaining = parse_unit("eggs")
        assert unit is None
        assert remaining == "eggs"

    def test_unit_with_comma(self):
        unit, remaining = parse_unit("cups, flour")
        assert unit == "cups"
        assert remaining == "flour"


class TestParseIngredientText:
    """Tests for parse_ingredient_text function."""

    def test_simple_ingredient(self):
        ing = parse_ingredient_text("2 cups flour")
        assert ing.quantity == 2.0
        assert ing.unit == "cups"
        assert ing.name == "flour"
        assert ing.notes is None

    def test_ingredient_with_notes_parentheses(self):
        ing = parse_ingredient_text("1 cup butter (softened)")
        assert ing.quantity == 1.0
        assert ing.unit == "cup"
        assert ing.name == "butter"
        assert ing.notes == "softened"

    def test_ingredient_with_notes_comma(self):
        ing = parse_ingredient_text("2 cups flour, sifted")
        assert ing.quantity == 2.0
        assert ing.unit == "cups"
        assert ing.name == "flour"
        assert ing.notes == "sifted"

    def test_ingredient_no_quantity(self):
        ing = parse_ingredient_text("salt to taste")
        assert ing.quantity is None
        assert ing.unit is None
        assert ing.name == "salt to taste"

    def test_ingredient_no_unit(self):
        ing = parse_ingredient_text("3 eggs")
        assert ing.quantity == 3.0
        assert ing.unit is None
        assert ing.name == "eggs"

    def test_original_preserved(self):
        original = "2 cups all-purpose flour, sifted"
        ing = parse_ingredient_text(original)
        assert ing.original == original

    def test_complex_ingredient(self):
        ing = parse_ingredient_text("1 1/2 cups heavy cream (cold)")
        assert ing.quantity == 1.5
        assert ing.unit == "cups"
        assert ing.name == "heavy cream"
        assert ing.notes == "cold"

    def test_fraction_ingredient(self):
        ing = parse_ingredient_text("½ tsp vanilla extract")
        assert ing.quantity == 0.5
        assert ing.unit == "tsp"
        assert ing.name == "vanilla extract"


class TestParseIngredientsText:
    """Tests for parse_ingredients_text function."""

    def test_multiple_ingredients(self):
        text = """2 cups flour
1 cup sugar
3 eggs"""
        ingredients = parse_ingredients_text(text)
        assert len(ingredients) == 3
        assert ingredients[0].name == "flour"
        assert ingredients[1].name == "sugar"
        assert ingredients[2].name == "eggs"

    def test_skips_empty_lines(self):
        text = """2 cups flour

1 cup sugar"""
        ingredients = parse_ingredients_text(text)
        assert len(ingredients) == 2

    def test_skips_headers(self):
        text = """Ingredients:
2 cups flour
1 cup sugar"""
        ingredients = parse_ingredients_text(text)
        assert len(ingredients) == 2
        assert ingredients[0].name == "flour"

    def test_handles_bullet_points(self):
        text = """- 2 cups flour
* 1 cup sugar
• 3 eggs"""
        ingredients = parse_ingredients_text(text)
        assert len(ingredients) == 3
        assert ingredients[0].quantity == 2.0
        assert ingredients[1].quantity == 1.0
        assert ingredients[2].quantity == 3.0

    def test_handles_numbered_list(self):
        text = """1. 2 cups flour
2. 1 cup sugar
3. 3 eggs"""
        ingredients = parse_ingredients_text(text)
        assert len(ingredients) == 3


class TestIngredient:
    """Tests for Ingredient dataclass."""

    def test_str_with_all_fields(self):
        ing = Ingredient(
            original="2 cups flour, sifted", name="flour", quantity=2.0, unit="cups", notes="sifted"
        )
        assert str(ing) == "2.0 cups flour (sifted)"

    def test_str_without_notes(self):
        ing = Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups")
        assert str(ing) == "2.0 cups flour"

    def test_str_without_unit(self):
        ing = Ingredient(original="3 eggs", name="eggs", quantity=3.0)
        assert str(ing) == "3.0 eggs"


class TestRecipe:
    """Tests for Recipe dataclass."""

    def test_to_dict(self):
        recipe = Recipe(
            title="Test Recipe",
            servings=4,
            source_url="https://example.com",
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups")
            ],
        )
        d = recipe.to_dict()
        assert d["title"] == "Test Recipe"
        assert d["servings"] == 4
        assert d["source_url"] == "https://example.com"
        assert len(d["ingredients"]) == 1
        assert d["ingredients"][0]["name"] == "flour"

    def test_from_dict(self):
        data = {
            "title": "Test Recipe",
            "servings": 4,
            "source_url": "https://example.com",
            "ingredients": [
                {"original": "2 cups flour", "name": "flour", "quantity": 2.0, "unit": "cups"}
            ],
        }
        recipe = Recipe.from_dict(data)
        assert recipe.title == "Test Recipe"
        assert recipe.servings == 4
        assert len(recipe.ingredients) == 1
        assert recipe.ingredients[0].quantity == 2.0

    def test_round_trip_serialization(self):
        original = Recipe(
            title="Chocolate Cake",
            servings=8,
            ingredients=[
                Ingredient(original="2 cups flour", name="flour", quantity=2.0, unit="cups"),
                Ingredient(original="1 cup sugar", name="sugar", quantity=1.0, unit="cup"),
            ],
        )
        restored = Recipe.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.servings == original.servings
        assert len(restored.ingredients) == len(original.ingredients)


class TestParseRecipeText:
    """Tests for parse_recipe_text function."""

    def test_basic_recipe(self):
        ingredients = """2 cups flour
1 cup sugar
3 eggs"""
        recipe = parse_recipe_text("My Cake", ingredients, servings=4)
        assert recipe.title == "My Cake"
        assert recipe.servings == 4
        assert len(recipe.ingredients) == 3
        assert recipe.source_url is None

    def test_recipe_without_servings(self):
        ingredients = "2 cups flour"
        recipe = parse_recipe_text("Simple Recipe", ingredients)
        assert recipe.servings is None
