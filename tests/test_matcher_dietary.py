"""Tests for dietary filtering in the matcher module."""

from nemlig_shopper.matcher import (
    ProductMatch,
    filter_by_dietary_requirements,
)


class TestFilterByDietaryRequirements:
    """Tests for filter_by_dietary_requirements function."""

    def test_no_filters_returns_all(self):
        """Without filters, all products should be returned."""
        products = [
            {"name": "Mælk 1L", "id": 1},
            {"name": "Brød", "id": 2},
            {"name": "Æg 6 stk", "id": 3},
        ]
        safe, excluded = filter_by_dietary_requirements(products)

        assert len(safe) == 3
        assert len(excluded) == 0

    def test_lactose_filter_excludes_dairy(self):
        """Lactose filter should exclude dairy products."""
        products = [
            {"name": "Mælk 1L", "id": 1},
            {"name": "Brød", "id": 2},
            {"name": "Fløde", "id": 3},
            {"name": "Æbler", "id": 4},
        ]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["lactose"])

        # Mælk and Fløde contain lactose keywords
        assert len(excluded) >= 2
        safe_names = [p["name"] for p in safe]
        assert "Brød" in safe_names
        assert "Æbler" in safe_names

    def test_gluten_filter_excludes_wheat(self):
        """Gluten filter should exclude wheat products."""
        products = [
            {"name": "Hvedemel 1kg", "id": 1},
            {"name": "Rugbrød", "id": 2},
            {"name": "Ris", "id": 3},
            {"name": "Kartofler", "id": 4},
        ]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["gluten"])

        # Hvedemel and Rugbrød contain gluten keywords
        assert len(excluded) >= 2
        safe_names = [p["name"] for p in safe]
        assert "Ris" in safe_names
        assert "Kartofler" in safe_names

    def test_vegan_filter_excludes_animal_products(self):
        """Vegan filter should exclude animal products."""
        products = [
            {"name": "Kyllingebryst", "id": 1},
            {"name": "Æg 6 stk", "id": 2},
            {"name": "Ost", "id": 3},
            {"name": "Gulerødder", "id": 4},
            {"name": "Kartofler", "id": 5},
        ]
        safe, excluded = filter_by_dietary_requirements(products, dietary=["vegan"])

        # Kyllingebryst, Æg, Ost are not vegan
        assert len(excluded) >= 3
        safe_names = [p["name"] for p in safe]
        assert "Gulerødder" in safe_names
        assert "Kartofler" in safe_names

    def test_vegetarian_filter_excludes_meat(self):
        """Vegetarian filter should exclude meat products."""
        products = [
            {"name": "Oksekød 500g", "id": 1},
            {"name": "Bacon", "id": 2},
            {"name": "Æg 6 stk", "id": 3},
            {"name": "Ost", "id": 4},
            {"name": "Tomater", "id": 5},
        ]
        safe, excluded = filter_by_dietary_requirements(products, dietary=["vegetarian"])

        # Oksekød and Bacon are meat
        assert len(excluded) >= 2
        safe_names = [p["name"] for p in safe]
        # Eggs and cheese are vegetarian
        assert "Æg 6 stk" in safe_names
        assert "Ost" in safe_names
        assert "Tomater" in safe_names

    def test_multiple_allergies_combined(self):
        """Multiple allergies should all be checked."""
        products = [
            {"name": "Mælk 1L", "id": 1},
            {"name": "Hvedemel", "id": 2},
            {"name": "Nøddesmør", "id": 3},
            {"name": "Ris", "id": 4},
        ]
        safe, excluded = filter_by_dietary_requirements(
            products, allergies=["lactose", "gluten", "nuts"]
        )

        # All except Ris should be excluded
        assert len(safe) == 1
        assert safe[0]["name"] == "Ris"

    def test_excluded_products_have_reasons(self):
        """Excluded products should be annotated with exclusion reasons."""
        products = [{"name": "Mælk 1L", "id": 1}]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["lactose"])

        assert len(excluded) == 1
        assert "_excluded_reasons" in excluded[0]
        assert len(excluded[0]["_excluded_reasons"]) > 0

    def test_empty_product_list(self):
        """Empty product list should return empty results."""
        safe, excluded = filter_by_dietary_requirements([], allergies=["lactose"])

        assert safe == []
        assert excluded == []

    def test_vegan_labeled_product_passes_vegan_filter(self):
        """Products labeled vegan should pass vegan filter."""
        products = [
            {"name": "Vegansk Smør", "description": "Plantebaseret alternativ", "id": 1},
            {"name": "Mælk", "id": 2},
        ]
        safe, excluded = filter_by_dietary_requirements(products, dietary=["vegan"])

        # Vegansk Smør should be recognized as vegan-safe
        safe_names = [p["name"] for p in safe]
        assert "Vegansk Smør" in safe_names


class TestProductMatchDietaryFields:
    """Tests for dietary fields in ProductMatch dataclass."""

    def test_default_is_dietary_safe(self):
        """By default, is_dietary_safe should be True."""
        match = ProductMatch(
            ingredient_name="test",
            product={"id": 1, "name": "Test"},
            quantity=1,
            matched=True,
            search_query="test",
            alternatives=[],
        )

        assert match.is_dietary_safe is True
        assert match.dietary_warnings is None
        assert match.excluded_count == 0

    def test_dietary_warnings_stored(self):
        """Dietary warnings should be stored when set."""
        match = ProductMatch(
            ingredient_name="milk",
            product={"id": 1, "name": "Mælk"},
            quantity=1,
            matched=True,
            search_query="mælk",
            alternatives=[],
            is_dietary_safe=False,
            dietary_warnings=["No lactose-safe products found for 'milk'"],
            excluded_count=5,
        )

        assert match.is_dietary_safe is False
        assert match.dietary_warnings is not None
        assert len(match.dietary_warnings) == 1
        assert "lactose" in match.dietary_warnings[0]
        assert match.excluded_count == 5

    def test_to_dict_does_not_include_dietary_fields(self):
        """to_dict should work without breaking (dietary fields are optional)."""
        match = ProductMatch(
            ingredient_name="test",
            product={"id": 1, "name": "Test"},
            quantity=1,
            matched=True,
            search_query="test",
            alternatives=[],
            is_dietary_safe=False,
            dietary_warnings=["warning"],
        )

        result = match.to_dict()
        # to_dict() returns basic match info, dietary fields are for display only
        assert "ingredient_name" in result
        assert "product_name" in result


class TestDietaryFilterIntegration:
    """Integration tests for dietary filtering in matching flow."""

    def test_filter_dairy_products(self):
        """Dairy products should be filtered with lactose allergy."""
        products = [
            {"name": "Letmælk 1L", "id": 1, "price": 10},
            {"name": "Laktosefri Mælk", "id": 2, "price": 15},
            {"name": "Havregrød", "id": 3, "price": 20},
        ]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["lactose"])

        # Letmælk contains mælk (dairy keyword)
        excluded_names = [p["name"] for p in excluded]
        assert "Letmælk 1L" in excluded_names

        # Laktosefri may still be flagged because it contains "mælk"
        # This is expected behavior - keyword matching is conservative

    def test_filter_nut_products(self):
        """Nut products should be filtered with nuts allergy."""
        products = [
            {"name": "Mandler 200g", "id": 1},
            {"name": "Hasselnødder", "id": 2},
            {"name": "Solsikkekerner", "id": 3},
        ]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["nuts"])

        # Mandler and Hasselnødder are nuts
        assert len(excluded) >= 2
        safe_names = [p["name"] for p in safe]
        assert "Solsikkekerner" in safe_names

    def test_filter_shellfish_products(self):
        """Shellfish products should be filtered with shellfish allergy."""
        products = [
            {"name": "Rejer 200g", "id": 1},
            {"name": "Hummer", "id": 2},
            {"name": "Laks", "id": 3},  # Fish, not shellfish
        ]
        safe, excluded = filter_by_dietary_requirements(products, allergies=["shellfish"])

        # Rejer and Hummer are shellfish
        assert len(excluded) >= 2
        # Laks is fish, not shellfish - should be safe
        safe_names = [p["name"] for p in safe]
        assert "Laks" in safe_names
