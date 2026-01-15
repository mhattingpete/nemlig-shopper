"""Tests for the llm_tools module."""

from nemlig_shopper.llm_tools import (
    calculate_package_coverage,
    exclude_ingredient,
    get_shopping_summary,
    merge_ingredient_lists,
    optimize_package_selection,
    parse_manual_items,
    parse_recipe_from_text,
    select_alternative_product,
)


class TestParseManualItems:
    """Tests for parse_manual_items function."""

    def test_parse_simple_items(self):
        """Should parse simple item strings."""
        items = ["milk", "bread", "eggs"]
        result = parse_manual_items(items)

        assert len(result) == 3
        assert result[0]["name"] == "milk"
        assert result[1]["name"] == "bread"
        assert result[2]["name"] == "eggs"

    def test_parse_items_with_quantities(self):
        """Should parse items with quantities."""
        items = ["2kg potatoes", "500g flour", "3 eggs"]
        result = parse_manual_items(items)

        assert len(result) == 3
        assert result[0]["quantity"] == 2
        assert result[0]["unit"] == "kg"
        assert result[0]["name"] == "potatoes"

        assert result[1]["quantity"] == 500
        assert result[1]["unit"] == "g"

    def test_parse_items_with_units(self):
        """Should parse items with various units."""
        items = ["1L milk", "250ml cream", "6 stk eggs"]
        result = parse_manual_items(items)

        assert result[0]["unit"] == "l"
        assert result[1]["unit"] == "ml"
        assert result[2]["unit"] == "stk"

    def test_parse_empty_list(self):
        """Empty list should return empty result."""
        result = parse_manual_items([])
        assert result == []


class TestParseRecipeFromText:
    """Tests for parse_recipe_from_text function."""

    def test_parse_simple_recipe(self):
        """Should parse a simple recipe from text."""
        ingredients = """
        2 eggs
        100g flour
        1 cup milk
        """
        result = parse_recipe_from_text("Pancakes", ingredients, servings=4)

        assert result["title"] == "Pancakes"
        assert result["servings"] == 4
        assert len(result["ingredients"]) == 3

    def test_parse_without_servings(self):
        """Should parse recipe without servings."""
        ingredients = "2 eggs\n100g flour"
        result = parse_recipe_from_text("Test Recipe", ingredients)

        assert result["title"] == "Test Recipe"
        assert result["servings"] is None
        assert len(result["ingredients"]) == 2


class TestMergeIngredientLists:
    """Tests for merge_ingredient_lists function."""

    def test_merge_consolidates_same_ingredient(self):
        """Same ingredients should be consolidated."""
        list1 = [{"name": "onion", "quantity": 1, "unit": "stk", "sources": ["Recipe A"]}]
        list2 = [{"name": "onion", "quantity": 2, "unit": "stk", "sources": ["Recipe B"]}]

        result = merge_ingredient_lists(list1, list2)

        # Should have one consolidated onion entry
        assert len(result) == 1
        assert result[0]["name"] == "onion"
        assert result[0]["quantity"] == 3

    def test_merge_keeps_different_ingredients(self):
        """Different ingredients should remain separate."""
        list1 = [{"name": "onion", "quantity": 1, "unit": "stk", "sources": ["A"]}]
        list2 = [{"name": "carrot", "quantity": 2, "unit": "stk", "sources": ["B"]}]

        result = merge_ingredient_lists(list1, list2)

        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "onion" in names
        assert "carrot" in names

    def test_merge_handles_different_units(self):
        """Ingredients with incompatible units stay separate."""
        list1 = [{"name": "tomato", "quantity": 500, "unit": "g", "sources": ["A"]}]
        list2 = [{"name": "tomato", "quantity": 3, "unit": "stk", "sources": ["B"]}]

        result = merge_ingredient_lists(list1, list2)

        # Different unit types should stay separate
        assert len(result) == 2

    def test_merge_empty_lists(self):
        """Merging empty lists should return empty."""
        result = merge_ingredient_lists([], [])
        assert result == []


class TestOptimizePackageSelection:
    """Tests for optimize_package_selection function."""

    def test_single_product_selection(self):
        """Should select the only available product."""
        products = [{"name": "Onions 5pc", "unit_size": "5 stk", "price": 15}]
        result = optimize_package_selection(3, "stk", products)

        assert result["product"] is not None
        assert result["packages_to_buy"] == 1

    def test_prefer_fewer_packages(self):
        """Should prefer larger packages when it means fewer items."""
        products = [
            {"name": "Onion single", "unit_size": "1 stk", "price": 5},
            {"name": "Onions bag", "unit_size": "5 stk", "price": 15},
        ]
        result = optimize_package_selection(3, "stk", products)

        # Should prefer the bag (1 package) over 3 singles
        assert result["product"]["name"] == "Onions bag"
        assert result["packages_to_buy"] == 1

    def test_calculates_waste(self):
        """Should calculate waste correctly."""
        products = [{"name": "Onions 5pc", "unit_size": "5 stk", "price": 15}]
        result = optimize_package_selection(3, "stk", products)

        # Need 3, get 5, waste is 2
        assert "2" in result["waste"]

    def test_weight_based_calculation(self):
        """Should handle weight-based calculations."""
        products = [{"name": "Flour 1kg", "unit_size": "1 kg", "price": 20}]
        result = optimize_package_selection(750, "g", products)

        # 750g needed, 1kg package = 1 package
        assert result["packages_to_buy"] == 1

    def test_multiple_packages_needed(self):
        """Should calculate when multiple packages needed."""
        products = [{"name": "Milk 1L", "unit_size": "1 l", "price": 12}]
        result = optimize_package_selection(2500, "ml", products)

        # 2500ml needed, 1L packages = 3 packages
        assert result["packages_to_buy"] == 3

    def test_empty_product_list(self):
        """Should handle empty product list gracefully."""
        result = optimize_package_selection(3, "stk", [])

        assert result["product"] is None
        assert "error" in result


class TestCalculatePackageCoverage:
    """Tests for calculate_package_coverage function."""

    def test_exact_coverage(self):
        """Should calculate exact coverage."""
        product = {"unit_size": "500g", "price": 10}
        result = calculate_package_coverage(product, 500, "g")

        assert result["packages_needed"] == 1
        assert result["covers_need"]
        assert "0" in str(result["extra"])

    def test_partial_coverage_needs_extra(self):
        """Should round up when partial coverage."""
        product = {"unit_size": "500g", "price": 10}
        result = calculate_package_coverage(product, 750, "g")

        assert result["packages_needed"] == 2
        assert result["covers_need"]

    def test_count_based_coverage(self):
        """Should handle count-based products."""
        product = {"unit_size": "6 stk", "price": 15}
        result = calculate_package_coverage(product, 10, "stk")

        assert result["packages_needed"] == 2  # 12 >= 10


class TestSelectAlternativeProduct:
    """Tests for select_alternative_product function."""

    def test_select_first_alternative(self):
        """Should swap product with first alternative."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"id": 1, "name": "Regular Milk"},
                "quantity": 1,
                "matched": True,
                "alternatives": [
                    {"id": 2, "name": "Organic Milk"},
                    {"id": 3, "name": "Low-fat Milk"},
                ],
            }
        ]

        result = select_alternative_product(matches, "milk", 0)

        assert result[0]["product"]["name"] == "Organic Milk"
        assert len(result[0]["alternatives"]) == 2
        assert any(a["name"] == "Regular Milk" for a in result[0]["alternatives"])

    def test_select_second_alternative(self):
        """Should swap product with second alternative."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"id": 1, "name": "Regular Milk"},
                "quantity": 1,
                "matched": True,
                "alternatives": [
                    {"id": 2, "name": "Organic Milk"},
                    {"id": 3, "name": "Low-fat Milk"},
                ],
            }
        ]

        result = select_alternative_product(matches, "milk", 1)

        assert result[0]["product"]["name"] == "Low-fat Milk"

    def test_invalid_index_returns_unchanged(self):
        """Invalid alternative index should return unchanged."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"id": 1, "name": "Regular Milk"},
                "quantity": 1,
                "matched": True,
                "alternatives": [{"id": 2, "name": "Organic Milk"}],
            }
        ]

        result = select_alternative_product(matches, "milk", 5)

        assert result[0]["product"]["name"] == "Regular Milk"

    def test_case_insensitive_ingredient_match(self):
        """Ingredient matching should be case insensitive."""
        matches = [
            {
                "ingredient": "Milk",
                "product": {"id": 1, "name": "Regular"},
                "matched": True,
                "alternatives": [{"id": 2, "name": "Organic"}],
            }
        ]

        result = select_alternative_product(matches, "milk", 0)

        assert result[0]["product"]["name"] == "Organic"


class TestExcludeIngredient:
    """Tests for exclude_ingredient function."""

    def test_exclude_removes_ingredient(self):
        """Should remove the specified ingredient."""
        matches = [
            {"ingredient": "milk", "product": {}, "matched": True},
            {"ingredient": "bread", "product": {}, "matched": True},
            {"ingredient": "eggs", "product": {}, "matched": True},
        ]

        result = exclude_ingredient(matches, "bread")

        assert len(result) == 2
        assert not any(m["ingredient"] == "bread" for m in result)

    def test_exclude_case_insensitive(self):
        """Exclusion should be case insensitive."""
        matches = [
            {"ingredient": "Milk", "product": {}, "matched": True},
            {"ingredient": "Bread", "product": {}, "matched": True},
        ]

        result = exclude_ingredient(matches, "milk")

        assert len(result) == 1
        assert result[0]["ingredient"] == "Bread"

    def test_exclude_nonexistent_unchanged(self):
        """Excluding nonexistent ingredient should return unchanged."""
        matches = [
            {"ingredient": "milk", "product": {}, "matched": True},
        ]

        result = exclude_ingredient(matches, "bread")

        assert len(result) == 1


class TestGetShoppingSummary:
    """Tests for get_shopping_summary function."""

    def test_summary_includes_matched(self):
        """Summary should include matched products."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"name": "Minimælk 1L", "price": 12.50},
                "quantity": 2,
                "matched": True,
            }
        ]

        summary = get_shopping_summary(matches)

        assert "milk" in summary.lower()
        assert "Minimælk" in summary
        assert "2" in summary

    def test_summary_includes_unmatched(self):
        """Summary should list unmatched items."""
        matches = [
            {
                "ingredient": "exotic spice",
                "product": None,
                "matched": False,
            }
        ]

        summary = get_shopping_summary(matches)

        assert "unmatched" in summary.lower()
        assert "exotic spice" in summary

    def test_summary_includes_total(self):
        """Summary should include total price."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"name": "Milk", "price": 10.00},
                "quantity": 2,
                "matched": True,
            },
            {
                "ingredient": "bread",
                "product": {"name": "Bread", "price": 15.00},
                "quantity": 1,
                "matched": True,
            },
        ]

        summary = get_shopping_summary(matches)

        # Total should be 10*2 + 15*1 = 35
        assert "35" in summary

    def test_summary_notes_warnings(self):
        """Summary should include warning notes."""
        matches = [
            {
                "ingredient": "milk",
                "product": {"name": "Milk", "price": 10.00},
                "quantity": 1,
                "matched": True,
                "safety": {"is_safe": False, "warnings": ["Contains lactose"]},
            }
        ]

        summary = get_shopping_summary(matches)

        assert "warning" in summary.lower()

    def test_summary_markdown_format(self):
        """Summary should be valid markdown."""
        matches = [
            {
                "ingredient": "test",
                "product": {"name": "Test", "price": 10},
                "quantity": 1,
                "matched": True,
            }
        ]

        summary = get_shopping_summary(matches)

        assert "##" in summary  # Has headers
        assert "|" in summary  # Has table


class TestConsolidateShoppingListIntegration:
    """Integration tests for consolidate_shopping_list (requires no API)."""

    def test_consolidate_manual_items_only(self):
        """Should work with only manual items."""
        from nemlig_shopper.llm_tools import consolidate_shopping_list

        result = consolidate_shopping_list(
            recipe_urls=[],
            additional_items=["2kg potatoes", "1L milk", "6 eggs"],
        )

        assert result["total_recipes"] == 0
        assert result["total_ingredients"] == 3
        assert len(result["consolidated"]) == 3

    def test_consolidate_empty_input(self):
        """Should handle empty input gracefully."""
        from nemlig_shopper.llm_tools import consolidate_shopping_list

        result = consolidate_shopping_list(recipe_urls=[], additional_items=[])

        assert result["total_recipes"] == 0
        assert result["total_ingredients"] == 0
        assert result["consolidated"] == []
