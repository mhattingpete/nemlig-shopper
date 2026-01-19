"""Tests for the preference_engine module."""

from nemlig_shopper.preference_engine import (
    ALLERGY_KEYWORDS,
    DIETARY_RESTRICTION_KEYWORDS,
    DIETARY_SAFE_INDICATORS,
    check_allergy_safety,
    check_dietary_compatibility,
    get_safe_alternative_query,
)


class TestCheckAllergySafety:
    """Tests for check_allergy_safety function."""

    def test_safe_product_no_allergens(self):
        """Product without allergens should be safe."""
        product = {"name": "Æbler 1kg", "description": "Danske æbler"}
        result = check_allergy_safety(product, ["nuts", "dairy"])

        assert result.is_safe
        assert result.allergens_found == []

    def test_unsafe_product_contains_nuts(self):
        """Product with nuts should be flagged."""
        product = {"name": "Nøddemix 200g", "description": "Blanding af mandler og cashew"}
        result = check_allergy_safety(product, ["nuts"])

        assert not result.is_safe
        assert len(result.allergens_found) > 0
        assert any("nuts" in af.lower() for af in result.allergens_found)

    def test_unsafe_product_contains_dairy(self):
        """Product with dairy should be flagged."""
        product = {"name": "Mælk 1L", "category": "Mejeri"}
        result = check_allergy_safety(product, ["dairy"])

        assert not result.is_safe
        assert len(result.allergens_found) > 0

    def test_unsafe_product_contains_gluten(self):
        """Product with gluten should be flagged."""
        product = {"name": "Hvedemel 1kg", "description": "Fint hvedemel"}
        result = check_allergy_safety(product, ["gluten"])

        assert not result.is_safe
        assert any("gluten" in af.lower() for af in result.allergens_found)

    def test_multiple_allergens_detected(self):
        """Multiple allergens should all be detected."""
        product = {
            "name": "Nøddesmør",
            "description": "Smør med mælk og mandler",
        }
        result = check_allergy_safety(product, ["nuts", "dairy"])

        assert not result.is_safe
        # Should find both
        found_types = " ".join(result.allergens_found).lower()
        assert "nuts" in found_types or "mandel" in found_types
        assert "dairy" in found_types or "mælk" in found_types

    def test_case_insensitive_matching(self):
        """Allergen matching should be case insensitive."""
        product = {"name": "MÆLK", "description": "FLØDE"}
        result = check_allergy_safety(product, ["dairy"])

        assert not result.is_safe

    def test_shellfish_detection(self):
        """Shellfish allergens should be detected."""
        product = {"name": "Rejer 200g", "description": "Nordiske rejer"}
        result = check_allergy_safety(product, ["shellfish"])

        assert not result.is_safe

    def test_eggs_detection(self):
        """Egg allergens should be detected."""
        product = {"name": "Frilandsæg 10 stk", "category": "Mejeri"}
        result = check_allergy_safety(product, ["eggs"])

        assert not result.is_safe

    def test_soy_detection(self):
        """Soy allergens should be detected."""
        product = {"name": "Sojasauce 250ml", "description": "Japansk soja"}
        result = check_allergy_safety(product, ["soy"])

        assert not result.is_safe

    def test_may_contain_warning(self):
        """'May contain' style warnings should be detected."""
        product = {
            "name": "Chokolade",
            "description": "Kan indeholde spor af nødder",
        }
        result = check_allergy_safety(product, ["nuts"])

        # Even if no direct allergen, should have warning
        assert len(result.warnings) > 0 or not result.is_safe

    def test_to_dict_serialization(self):
        """Result should serialize to dict correctly."""
        product = {"name": "Mælk 1L"}
        result = check_allergy_safety(product, ["dairy"])

        result_dict = result.to_dict()
        assert "is_safe" in result_dict
        assert "allergens_found" in result_dict
        assert "warnings" in result_dict
        assert "product_name" in result_dict


class TestCheckDietaryCompatibility:
    """Tests for check_dietary_compatibility function."""

    def test_vegetable_is_vegetarian(self):
        """Vegetables should be vegetarian compatible."""
        product = {"name": "Gulerødder 1kg", "category": "Grønt"}
        result = check_dietary_compatibility(product, ["vegetarian"])

        assert result.is_compatible
        assert result.conflicts == []

    def test_meat_is_not_vegetarian(self):
        """Meat products should not be vegetarian."""
        product = {"name": "Hakket oksekød 500g", "category": "Kød"}
        result = check_dietary_compatibility(product, ["vegetarian"])

        assert not result.is_compatible
        assert len(result.conflicts) > 0

    def test_chicken_is_not_vegetarian(self):
        """Chicken should not be vegetarian."""
        product = {"name": "Kyllingebryst 400g"}
        result = check_dietary_compatibility(product, ["vegetarian"])

        assert not result.is_compatible

    def test_fish_is_not_vegetarian(self):
        """Fish should not be vegetarian."""
        product = {"name": "Laks 200g"}
        result = check_dietary_compatibility(product, ["vegetarian"])

        assert not result.is_compatible

    def test_fish_is_pescatarian(self):
        """Fish should be pescatarian compatible."""
        product = {"name": "Laks 200g"}
        result = check_dietary_compatibility(product, ["pescatarian"])

        # Pescatarian allows fish
        assert result.is_compatible

    def test_dairy_is_not_vegan(self):
        """Dairy should not be vegan."""
        product = {"name": "Mælk 1L", "category": "Mejeri"}
        result = check_dietary_compatibility(product, ["vegan"])

        assert not result.is_compatible

    def test_eggs_are_not_vegan(self):
        """Eggs should not be vegan."""
        product = {"name": "Økologiske æg"}
        result = check_dietary_compatibility(product, ["vegan"])

        assert not result.is_compatible

    def test_plant_based_is_vegan(self):
        """Products labeled plant-based should be vegan."""
        product = {"name": "Plantebaseret mælk", "description": "Vegansk alternativ"}
        result = check_dietary_compatibility(product, ["vegan"])

        # Should recognize vegan label
        assert result.is_compatible

    def test_product_with_vegan_label(self):
        """Products with vegan label should be recognized."""
        product = {"name": "Naturli' Vegansk Smør"}
        result = check_dietary_compatibility(product, ["vegan"])

        assert result.is_compatible

    def test_multiple_dietary_restrictions(self):
        """Multiple restrictions should all be checked."""
        product = {"name": "Kylling"}
        result = check_dietary_compatibility(product, ["vegetarian", "vegan"])

        assert not result.is_compatible

    def test_to_dict_serialization(self):
        """Result should serialize to dict correctly."""
        product = {"name": "Oksekød"}
        result = check_dietary_compatibility(product, ["vegetarian"])

        result_dict = result.to_dict()
        assert "is_compatible" in result_dict
        assert "conflicts" in result_dict
        assert "warnings" in result_dict


class TestGetSafeAlternativeQuery:
    """Tests for get_safe_alternative_query function."""

    def test_lactose_allergy_adds_laktosefri(self):
        """Lactose allergy should suggest lactose-free query."""
        query = get_safe_alternative_query("milk", allergens=["lactose"])

        assert query is not None
        assert "laktosefri" in query.lower()

    def test_gluten_allergy_adds_glutenfri(self):
        """Gluten allergy should suggest gluten-free query."""
        query = get_safe_alternative_query("bread", allergens=["gluten"])

        assert query is not None
        assert "glutenfri" in query.lower()

    def test_vegan_diet_adds_vegansk(self):
        """Vegan diet should suggest vegan query."""
        query = get_safe_alternative_query("butter", dietary_restrictions=["vegan"])

        assert query is not None
        assert "vegansk" in query.lower()

    def test_no_restrictions_returns_none(self):
        """No restrictions should return None."""
        query = get_safe_alternative_query("apples")

        assert query is None


class TestAllergyKeywords:
    """Tests to verify allergy keyword coverage."""

    def test_all_allergen_types_have_keywords(self):
        """All documented allergen types should have keywords."""
        expected_types = [
            "nuts",
            "gluten",
            "dairy",
            "lactose",
            "shellfish",
            "fish",
            "eggs",
            "soy",
            "sesame",
            "celery",
            "mustard",
        ]
        for allergen_type in expected_types:
            assert allergen_type in ALLERGY_KEYWORDS
            assert len(ALLERGY_KEYWORDS[allergen_type]) > 0

    def test_keywords_include_danish(self):
        """Keywords should include Danish terms."""
        # Check a few known Danish terms
        assert "mælk" in ALLERGY_KEYWORDS["dairy"]
        assert "æg" in ALLERGY_KEYWORDS["eggs"]
        assert "rejer" in ALLERGY_KEYWORDS["shellfish"]
        assert "hvede" in ALLERGY_KEYWORDS["gluten"]


class TestDietaryKeywords:
    """Tests to verify dietary keyword coverage."""

    def test_all_dietary_types_have_keywords(self):
        """All documented dietary types should have keywords."""
        expected_types = ["vegetarian", "vegan", "pescatarian"]
        for dietary_type in expected_types:
            assert dietary_type in DIETARY_RESTRICTION_KEYWORDS
            assert len(DIETARY_RESTRICTION_KEYWORDS[dietary_type]) > 0

    def test_safe_indicators_exist(self):
        """Safe indicators should exist for common diets."""
        assert "vegetarian" in DIETARY_SAFE_INDICATORS
        assert "vegan" in DIETARY_SAFE_INDICATORS
        assert "gluten-free" in DIETARY_SAFE_INDICATORS
        assert "lactose-free" in DIETARY_SAFE_INDICATORS
