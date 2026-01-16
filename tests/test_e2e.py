"""End-to-end integration tests.

These tests verify the full flow from recipe URL to product matching.
Note: Cart operations are not tested to avoid modifying real cart state.
"""

import pytest

from nemlig_shopper.recipe_parser import parse_recipe_url


@pytest.fixture
def authenticated_api():
    """Create an authenticated NemligAPI instance."""
    from nemlig_shopper.api import NemligAPI
    from nemlig_shopper.config import get_credentials

    api = NemligAPI()
    creds = get_credentials()
    if creds:
        email, password = creds
        if email and password:
            api.login(email, password)
    return api


class TestRecipeParsing:
    """Test parsing recipes from real URLs."""

    @pytest.mark.integration
    def test_parse_valdemarsro_recipe(self):
        """Test parsing a real recipe from Valdemarsro."""
        url = "https://www.valdemarsro.dk/one-pot-vegetar-pasta-med-tomatfloedesauce/"
        recipe = parse_recipe_url(url)

        assert recipe.title is not None
        assert "pasta" in recipe.title.lower() or "one pot" in recipe.title.lower()
        assert recipe.servings == 4
        assert len(recipe.ingredients) >= 10

        # Check some expected ingredients are present
        ingredient_names = [ing.name.lower() for ing in recipe.ingredients]
        all_text = " ".join(ingredient_names)

        assert "pasta" in all_text
        assert "tomat" in all_text
        assert "basilikum" in all_text
        assert "løg" in all_text or "log" in all_text

    @pytest.mark.integration
    def test_parse_recipe_quantities(self):
        """Test that quantities are correctly parsed from recipe."""
        url = "https://www.valdemarsro.dk/one-pot-vegetar-pasta-med-tomatfloedesauce/"
        recipe = parse_recipe_url(url)

        # Find the pasta ingredient (should be 400g)
        pasta_ing = next((ing for ing in recipe.ingredients if "pasta" in ing.name.lower()), None)
        assert pasta_ing is not None
        assert pasta_ing.quantity == 400

        # Find hakkede tomater (should be 800g)
        tomato_ing = next(
            (ing for ing in recipe.ingredients if "hakkede tomater" in ing.name.lower()), None
        )
        assert tomato_ing is not None
        assert tomato_ing.quantity == 800


class TestIngredientMatching:
    """Test ingredient to product matching (no cart operations)."""

    @pytest.mark.integration
    def test_match_common_ingredients(self, authenticated_api):
        """Test that common Danish ingredients can be matched."""
        from nemlig_shopper.matcher import match_ingredient

        # Test common ingredients - should find matches
        test_ingredients = ["pasta", "løg", "mælk", "smør", "æg"]

        for ingredient in test_ingredients:
            match = match_ingredient(authenticated_api, ingredient)
            assert match.matched, f"Failed to match: {ingredient}"
            assert match.product is not None
            assert match.product.get("name") is not None

    @pytest.mark.integration
    def test_translation_works(self, authenticated_api):
        """Test that English ingredients are translated to Danish."""
        from nemlig_shopper.matcher import match_ingredient

        # English ingredients should be translated and matched
        match = match_ingredient(authenticated_api, "milk")
        assert match.matched
        assert match.product is not None
        # Should find Danish milk product
        assert "mælk" in match.product.get("name", "").lower() or match.search_query == "mælk"


class TestFullPipeline:
    """Test the full recipe-to-matches pipeline."""

    @pytest.mark.integration
    def test_recipe_to_matches_pipeline(self, authenticated_api):
        """Test parsing a recipe and matching all ingredients."""
        from nemlig_shopper.matcher import match_ingredients
        from nemlig_shopper.recipe_parser import parse_recipe_url
        from nemlig_shopper.scaler import scale_recipe

        url = "https://www.valdemarsro.dk/one-pot-vegetar-pasta-med-tomatfloedesauce/"

        # Parse recipe
        recipe = parse_recipe_url(url)
        assert len(recipe.ingredients) > 0

        # Scale (1x, no change)
        scaled_ingredients, factor, _ = scale_recipe(recipe)
        assert factor == 1.0
        assert len(scaled_ingredients) == len(recipe.ingredients)

        # Match to products
        matches = match_ingredients(authenticated_api, scaled_ingredients)

        assert len(matches) == len(recipe.ingredients)

        # At least 80% should match
        matched_count = sum(1 for m in matches if m.matched)
        match_rate = matched_count / len(matches)
        assert match_rate >= 0.8, f"Match rate too low: {match_rate:.0%}"

        # All matched products should have valid data
        for match in matches:
            if match.matched:
                assert match.product_id is not None
                assert match.product_name != "No match found"
