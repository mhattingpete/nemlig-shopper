"""Tests for the favorites persistence module."""

import json

import pytest

from nemlig_shopper.favorites import (
    FavoritesError,
    delete_favorite,
    favorite_exists,
    get_favorite,
    get_favorite_product_ids,
    get_favorite_recipe,
    list_favorites,
    rename_favorite,
    save_favorite,
    update_favorite_matches,
)
from nemlig_shopper.recipe_parser import Ingredient, Recipe


@pytest.fixture
def temp_favorites_file(tmp_path, monkeypatch):
    """Create a temporary favorites file for testing."""
    favorites_file = tmp_path / "favorites.json"
    monkeypatch.setattr("nemlig_shopper.favorites.FAVORITES_FILE", favorites_file)
    return favorites_file


@pytest.fixture
def sample_recipe():
    """Create a sample recipe for testing."""
    return Recipe(
        title="Test Pancakes",
        ingredients=[
            Ingredient(original="2 eggs", name="eggs", quantity=2.0, unit=""),
            Ingredient(original="200g flour", name="flour", quantity=200.0, unit="g"),
            Ingredient(original="3 dl milk", name="milk", quantity=3.0, unit="dl"),
        ],
        servings=4,
        source_url="https://example.com/pancakes",
    )


@pytest.fixture
def sample_matches():
    """Create sample product matches for testing."""
    return [
        {
            "ingredient_name": "eggs",
            "product_id": 1001,
            "product_name": "Økologiske Æg 10 stk",
            "quantity": 1,
            "price": 35.95,
            "matched": True,
        },
        {
            "ingredient_name": "flour",
            "product_id": 1002,
            "product_name": "Hvedemel 1kg",
            "quantity": 1,
            "price": 12.95,
            "matched": True,
        },
        {
            "ingredient_name": "milk",
            "product_id": None,
            "product_name": None,
            "quantity": 0,
            "matched": False,
        },
    ]


@pytest.fixture
def populated_favorites(temp_favorites_file, sample_recipe, sample_matches):
    """Create a favorites file with some data."""
    favorites_data = {
        "breakfast": {
            "recipe": sample_recipe.to_dict(),
            "product_matches": sample_matches,
            "saved_at": "2026-01-10T10:00:00",
            "updated_at": "2026-01-10T10:00:00",
        },
        "dinner": {
            "recipe": {
                "title": "Pasta Bolognese",
                "ingredients": [
                    {"original": "500g pasta", "name": "pasta", "quantity": 500.0, "unit": "g"}
                ],
                "servings": 6,
                "source_url": "https://example.com/pasta",
            },
            "product_matches": [],
            "saved_at": "2026-01-11T18:00:00",
            "updated_at": "2026-01-11T18:00:00",
        },
    }
    with open(temp_favorites_file, "w", encoding="utf-8") as f:
        json.dump(favorites_data, f)
    return temp_favorites_file


# ============================================================================
# List Favorites Tests
# ============================================================================


class TestListFavorites:
    """Tests for list_favorites function."""

    def test_list_empty_when_no_file(self, temp_favorites_file):
        """Should return empty list when no favorites file exists."""
        result = list_favorites()
        assert result == []

    def test_list_empty_when_empty_file(self, temp_favorites_file):
        """Should return empty list when favorites file is empty."""
        with open(temp_favorites_file, "w") as f:
            json.dump({}, f)

        result = list_favorites()
        assert result == []

    def test_list_returns_summaries(self, populated_favorites):
        """Should return summary info for each favorite."""
        result = list_favorites()

        assert len(result) == 2

        # Results should be sorted by name
        assert result[0]["name"] == "breakfast"
        assert result[1]["name"] == "dinner"

        # Check breakfast summary
        breakfast = result[0]
        assert breakfast["title"] == "Test Pancakes"
        assert breakfast["ingredient_count"] == 3
        assert breakfast["servings"] == 4
        assert breakfast["has_product_matches"] is True
        assert breakfast["source_url"] == "https://example.com/pancakes"

        # Check dinner summary
        dinner = result[1]
        assert dinner["title"] == "Pasta Bolognese"
        assert dinner["ingredient_count"] == 1
        assert dinner["has_product_matches"] is False

    def test_list_handles_missing_fields(self, temp_favorites_file):
        """Should handle favorites with missing optional fields."""
        favorites_data = {
            "minimal": {
                "recipe": {"title": "Minimal Recipe", "ingredients": []},
                "product_matches": None,
                "saved_at": None,
            }
        }
        with open(temp_favorites_file, "w") as f:
            json.dump(favorites_data, f)

        result = list_favorites()

        assert len(result) == 1
        assert result[0]["title"] == "Minimal Recipe"
        assert result[0]["ingredient_count"] == 0
        assert result[0]["has_product_matches"] is False


# ============================================================================
# Get Favorite Tests
# ============================================================================


class TestGetFavorite:
    """Tests for get_favorite function."""

    def test_get_existing_favorite(self, populated_favorites):
        """Should return full favorite data."""
        result = get_favorite("breakfast")

        assert "recipe" in result
        assert result["recipe"]["title"] == "Test Pancakes"
        assert "product_matches" in result
        assert len(result["product_matches"]) == 3

    def test_get_nonexistent_raises_error(self, populated_favorites):
        """Should raise FavoritesError for unknown favorite."""
        with pytest.raises(FavoritesError) as exc_info:
            get_favorite("nonexistent")

        assert "not found" in str(exc_info.value)

    def test_get_from_empty_file_raises_error(self, temp_favorites_file):
        """Should raise FavoritesError when file is empty."""
        with open(temp_favorites_file, "w") as f:
            json.dump({}, f)

        with pytest.raises(FavoritesError) as exc_info:
            get_favorite("anything")

        assert "not found" in str(exc_info.value)


# ============================================================================
# Get Favorite Recipe Tests
# ============================================================================


class TestGetFavoriteRecipe:
    """Tests for get_favorite_recipe function."""

    def test_get_recipe_returns_recipe_object(self, populated_favorites):
        """Should return a Recipe object."""
        recipe = get_favorite_recipe("breakfast")

        assert isinstance(recipe, Recipe)
        assert recipe.title == "Test Pancakes"
        assert len(recipe.ingredients) == 3
        assert recipe.servings == 4

    def test_get_recipe_nonexistent_raises_error(self, populated_favorites):
        """Should raise FavoritesError for unknown favorite."""
        with pytest.raises(FavoritesError):
            get_favorite_recipe("nonexistent")


# ============================================================================
# Save Favorite Tests
# ============================================================================


class TestSaveFavorite:
    """Tests for save_favorite function."""

    def test_save_new_favorite(self, temp_favorites_file, sample_recipe):
        """Should save a new favorite to disk."""
        save_favorite("new_recipe", sample_recipe)

        # Verify it was saved
        with open(temp_favorites_file) as f:
            data = json.load(f)

        assert "new_recipe" in data
        assert data["new_recipe"]["recipe"]["title"] == "Test Pancakes"
        assert "saved_at" in data["new_recipe"]
        assert "updated_at" in data["new_recipe"]

    def test_save_with_product_matches(self, temp_favorites_file, sample_recipe, sample_matches):
        """Should save favorite with product matches."""
        save_favorite("with_matches", sample_recipe, product_matches=sample_matches)

        with open(temp_favorites_file) as f:
            data = json.load(f)

        assert len(data["with_matches"]["product_matches"]) == 3

    def test_save_duplicate_raises_error(self, populated_favorites, sample_recipe):
        """Should raise error when saving duplicate without overwrite."""
        with pytest.raises(FavoritesError) as exc_info:
            save_favorite("breakfast", sample_recipe)

        assert "already exists" in str(exc_info.value)

    def test_save_duplicate_with_overwrite(self, populated_favorites, sample_recipe):
        """Should overwrite when overwrite=True."""
        new_recipe = Recipe(
            title="New Breakfast",
            ingredients=[],
            servings=2,
        )

        save_favorite("breakfast", new_recipe, overwrite=True)

        result = get_favorite("breakfast")
        assert result["recipe"]["title"] == "New Breakfast"

    def test_save_creates_file_if_missing(self, temp_favorites_file, sample_recipe):
        """Should create favorites file if it doesn't exist."""
        assert not temp_favorites_file.exists()

        save_favorite("first", sample_recipe)

        assert temp_favorites_file.exists()

    def test_save_preserves_existing_favorites(self, populated_favorites, sample_recipe):
        """Should not overwrite other favorites when saving new one."""
        new_recipe = Recipe(title="Lunch", ingredients=[], servings=2)

        save_favorite("lunch", new_recipe)

        result = list_favorites()
        names = [f["name"] for f in result]
        assert "breakfast" in names
        assert "dinner" in names
        assert "lunch" in names


# ============================================================================
# Update Favorite Matches Tests
# ============================================================================


class TestUpdateFavoriteMatches:
    """Tests for update_favorite_matches function."""

    def test_update_matches(self, populated_favorites):
        """Should update product matches for existing favorite."""
        new_matches = [{"ingredient_name": "eggs", "product_id": 9999, "matched": True}]

        update_favorite_matches("breakfast", new_matches)

        result = get_favorite("breakfast")
        assert len(result["product_matches"]) == 1
        assert result["product_matches"][0]["product_id"] == 9999

    def test_update_sets_updated_at(self, populated_favorites):
        """Should update the updated_at timestamp."""
        original = get_favorite("breakfast")
        original_updated = original["updated_at"]

        update_favorite_matches("breakfast", [])

        result = get_favorite("breakfast")
        assert result["updated_at"] != original_updated

    def test_update_nonexistent_raises_error(self, populated_favorites):
        """Should raise error for unknown favorite."""
        with pytest.raises(FavoritesError) as exc_info:
            update_favorite_matches("nonexistent", [])

        assert "not found" in str(exc_info.value)


# ============================================================================
# Delete Favorite Tests
# ============================================================================


class TestDeleteFavorite:
    """Tests for delete_favorite function."""

    def test_delete_existing(self, populated_favorites):
        """Should delete an existing favorite."""
        assert favorite_exists("breakfast")

        delete_favorite("breakfast")

        assert not favorite_exists("breakfast")

    def test_delete_preserves_others(self, populated_favorites):
        """Should not affect other favorites."""
        delete_favorite("breakfast")

        assert favorite_exists("dinner")

    def test_delete_nonexistent_raises_error(self, populated_favorites):
        """Should raise error for unknown favorite."""
        with pytest.raises(FavoritesError) as exc_info:
            delete_favorite("nonexistent")

        assert "not found" in str(exc_info.value)


# ============================================================================
# Rename Favorite Tests
# ============================================================================


class TestRenameFavorite:
    """Tests for rename_favorite function."""

    def test_rename_success(self, populated_favorites):
        """Should rename a favorite."""
        rename_favorite("breakfast", "morning_meal")

        assert not favorite_exists("breakfast")
        assert favorite_exists("morning_meal")

        # Data should be preserved
        result = get_favorite("morning_meal")
        assert result["recipe"]["title"] == "Test Pancakes"

    def test_rename_updates_timestamp(self, populated_favorites):
        """Should update the updated_at timestamp."""
        original = get_favorite("breakfast")
        original_updated = original["updated_at"]

        rename_favorite("breakfast", "morning_meal")

        result = get_favorite("morning_meal")
        assert result["updated_at"] != original_updated

    def test_rename_nonexistent_raises_error(self, populated_favorites):
        """Should raise error for unknown source name."""
        with pytest.raises(FavoritesError) as exc_info:
            rename_favorite("nonexistent", "new_name")

        assert "not found" in str(exc_info.value)

    def test_rename_to_existing_raises_error(self, populated_favorites):
        """Should raise error when target name already exists."""
        with pytest.raises(FavoritesError) as exc_info:
            rename_favorite("breakfast", "dinner")

        assert "already exists" in str(exc_info.value)


# ============================================================================
# Favorite Exists Tests
# ============================================================================


class TestFavoriteExists:
    """Tests for favorite_exists function."""

    def test_exists_returns_true(self, populated_favorites):
        """Should return True for existing favorite."""
        assert favorite_exists("breakfast") is True

    def test_exists_returns_false(self, populated_favorites):
        """Should return False for nonexistent favorite."""
        assert favorite_exists("nonexistent") is False

    def test_exists_empty_file(self, temp_favorites_file):
        """Should return False when no favorites file."""
        assert favorite_exists("anything") is False


# ============================================================================
# Get Favorite Product IDs Tests
# ============================================================================


class TestGetFavoriteProductIds:
    """Tests for get_favorite_product_ids function."""

    def test_get_product_ids(self, populated_favorites):
        """Should return product IDs for matched products only."""
        result = get_favorite_product_ids("breakfast")

        # Should only include matched products with product_id
        assert len(result) == 2
        assert {"product_id": 1001, "quantity": 1} in result
        assert {"product_id": 1002, "quantity": 1} in result

    def test_get_product_ids_no_matches_raises_error(self, populated_favorites):
        """Should raise error when favorite has no matches."""
        with pytest.raises(FavoritesError) as exc_info:
            get_favorite_product_ids("dinner")

        assert "no saved product matches" in str(exc_info.value)

    def test_get_product_ids_nonexistent_raises_error(self, populated_favorites):
        """Should raise error for unknown favorite."""
        with pytest.raises(FavoritesError):
            get_favorite_product_ids("nonexistent")

    def test_get_product_ids_filters_unmatched(self, temp_favorites_file, sample_recipe):
        """Should filter out products where matched=False."""
        matches = [
            {"ingredient_name": "a", "product_id": 100, "matched": True, "quantity": 2},
            {"ingredient_name": "b", "product_id": 200, "matched": False, "quantity": 1},
            {"ingredient_name": "c", "product_id": None, "matched": True, "quantity": 1},
        ]

        save_favorite("test", sample_recipe, product_matches=matches)

        result = get_favorite_product_ids("test")

        # Only product_id=100 should be included (matched=True and has product_id)
        assert len(result) == 1
        assert result[0]["product_id"] == 100
        assert result[0]["quantity"] == 2


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in favorites module."""

    def test_load_corrupt_json_raises_error(self, temp_favorites_file):
        """Should raise FavoritesError for corrupt JSON."""
        with open(temp_favorites_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(FavoritesError) as exc_info:
            list_favorites()

        assert "Failed to load" in str(exc_info.value)

    def test_load_invalid_json_type_raises_error(self, temp_favorites_file):
        """Should raise FavoritesError when JSON is not a dict."""
        with open(temp_favorites_file, "w") as f:
            json.dump(["not", "a", "dict"], f)

        # This will cause issues when trying to iterate
        with pytest.raises((FavoritesError, AttributeError, TypeError)):
            list_favorites()

    def test_save_to_readonly_raises_error(self, temp_favorites_file, sample_recipe, monkeypatch):
        """Should raise FavoritesError when file is not writable."""
        # Create a valid JSON file first
        with open(temp_favorites_file, "w") as f:
            json.dump({}, f)

        # Make it read-only
        temp_favorites_file.chmod(0o444)

        try:
            with pytest.raises(FavoritesError) as exc_info:
                save_favorite("test", sample_recipe)

            assert "Failed to save" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            temp_favorites_file.chmod(0o644)


# ============================================================================
# Data Integrity Tests
# ============================================================================


class TestDataIntegrity:
    """Tests for data integrity across save/load cycles."""

    def test_roundtrip_preserves_recipe_data(self, temp_favorites_file, sample_recipe):
        """Recipe data should survive save/load cycle."""
        save_favorite("roundtrip", sample_recipe)

        loaded = get_favorite_recipe("roundtrip")

        assert loaded.title == sample_recipe.title
        assert loaded.servings == sample_recipe.servings
        assert loaded.source_url == sample_recipe.source_url
        assert len(loaded.ingredients) == len(sample_recipe.ingredients)

        for orig, loaded_ing in zip(sample_recipe.ingredients, loaded.ingredients, strict=False):
            assert loaded_ing.name == orig.name
            assert loaded_ing.quantity == orig.quantity
            assert loaded_ing.unit == orig.unit

    def test_roundtrip_preserves_product_matches(
        self, temp_favorites_file, sample_recipe, sample_matches
    ):
        """Product matches should survive save/load cycle."""
        save_favorite("roundtrip", sample_recipe, product_matches=sample_matches)

        loaded = get_favorite("roundtrip")

        assert len(loaded["product_matches"]) == len(sample_matches)
        for orig, loaded_match in zip(sample_matches, loaded["product_matches"], strict=False):
            assert loaded_match["ingredient_name"] == orig["ingredient_name"]
            assert loaded_match["product_id"] == orig["product_id"]
            assert loaded_match["matched"] == orig["matched"]

    def test_unicode_names_preserved(self, temp_favorites_file, sample_recipe):
        """Unicode characters in names should be preserved."""
        # Recipe with Danish characters
        danish_recipe = Recipe(
            title="Rødgrød med fløde",
            ingredients=[
                Ingredient(original="500g jordbær", name="jordbær", quantity=500.0, unit="g"),
            ],
            servings=4,
        )

        save_favorite("dansk_dessert", danish_recipe)

        loaded = get_favorite_recipe("dansk_dessert")

        assert loaded.title == "Rødgrød med fløde"
        assert loaded.ingredients[0].name == "jordbær"

    def test_multiple_operations_consistent(self, temp_favorites_file, sample_recipe):
        """Multiple operations should maintain consistency."""
        # Save multiple favorites
        for i in range(5):
            recipe = Recipe(title=f"Recipe {i}", ingredients=[], servings=i + 1)
            save_favorite(f"recipe_{i}", recipe)

        # Delete some
        delete_favorite("recipe_1")
        delete_favorite("recipe_3")

        # Update one
        update_favorite_matches(
            "recipe_2", [{"ingredient_name": "test", "matched": True, "product_id": 123}]
        )

        # Rename one
        rename_favorite("recipe_4", "renamed_4")

        # Verify state
        favorites = list_favorites()
        names = [f["name"] for f in favorites]

        assert len(names) == 3
        assert "recipe_0" in names
        assert "recipe_2" in names
        assert "renamed_4" in names
        assert "recipe_1" not in names
        assert "recipe_3" not in names
        assert "recipe_4" not in names
