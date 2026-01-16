"""Tests for the pantry module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nemlig_shopper.pantry import (
    DEFAULT_PANTRY_ITEMS,
    PantryConfig,
    add_to_pantry,
    clear_pantry,
    filter_pantry_items,
    get_default_pantry_items,
    identify_pantry_items,
    load_pantry_config,
    remove_from_pantry,
    save_pantry_config,
)
from nemlig_shopper.planner import ConsolidatedIngredient


@pytest.fixture
def temp_pantry_file(tmp_path) -> Path:
    """Create a temporary pantry file."""
    return tmp_path / "pantry.json"


@pytest.fixture
def sample_ingredients() -> list[ConsolidatedIngredient]:
    """Create sample ingredients for testing."""
    return [
        ConsolidatedIngredient(name="salt", total_quantity=1.0, unit="tsp", sources=["Recipe 1"]),
        ConsolidatedIngredient(
            name="olive oil", total_quantity=2.0, unit="tbsp", sources=["Recipe 1"]
        ),
        ConsolidatedIngredient(
            name="chicken breast", total_quantity=500.0, unit="g", sources=["Recipe 1"]
        ),
        ConsolidatedIngredient(
            name="tomatoes", total_quantity=4.0, unit="stk", sources=["Recipe 1"]
        ),
        ConsolidatedIngredient(name="pepper", total_quantity=0.5, unit="tsp", sources=["Recipe 1"]),
        ConsolidatedIngredient(name="sugar", total_quantity=100.0, unit="g", sources=["Recipe 2"]),
    ]


# =============================================================================
# PantryConfig Tests
# =============================================================================


class TestPantryConfig:
    """Tests for PantryConfig dataclass."""

    def test_default_config(self):
        """Default config should have empty user items and exclusions."""
        config = PantryConfig()
        assert config.user_items == set()
        assert config.excluded_defaults == set()
        assert config.updated_at is None

    def test_all_pantry_items_default(self):
        """Default pantry items should equal DEFAULT_PANTRY_ITEMS."""
        config = PantryConfig()
        assert config.all_pantry_items == DEFAULT_PANTRY_ITEMS

    def test_all_pantry_items_with_user_items(self):
        """User items should be added to the active set."""
        config = PantryConfig(user_items={"fish sauce", "sesame oil"})
        items = config.all_pantry_items
        assert "fish sauce" in items
        assert "sesame oil" in items
        assert "salt" in items  # Default item still there

    def test_all_pantry_items_with_exclusions(self):
        """Excluded defaults should be removed from the active set."""
        config = PantryConfig(excluded_defaults={"salt", "pepper"})
        items = config.all_pantry_items
        assert "salt" not in items
        assert "pepper" not in items
        assert "sugar" in items  # Other defaults still there

    def test_to_dict_and_from_dict_roundtrip(self):
        """Config should survive serialization roundtrip."""
        config = PantryConfig(
            user_items={"fish sauce", "mirin"},
            excluded_defaults={"eggs"},
        )
        data = config.to_dict()
        restored = PantryConfig.from_dict(data)

        assert restored.user_items == config.user_items
        assert restored.excluded_defaults == config.excluded_defaults


# =============================================================================
# Persistence Tests
# =============================================================================


class TestPersistence:
    """Tests for loading and saving pantry config."""

    def test_load_nonexistent_file(self, temp_pantry_file):
        """Loading nonexistent file should return default config."""
        config = load_pantry_config(temp_pantry_file)
        assert config.user_items == set()
        assert config.excluded_defaults == set()

    def test_save_and_load_roundtrip(self, temp_pantry_file):
        """Config should survive save/load roundtrip."""
        config = PantryConfig(
            user_items={"fish sauce", "rice vinegar"},
            excluded_defaults={"eggs"},
        )
        save_pantry_config(config, temp_pantry_file)

        loaded = load_pantry_config(temp_pantry_file)
        assert loaded.user_items == config.user_items
        assert loaded.excluded_defaults == config.excluded_defaults
        assert loaded.updated_at is not None

    def test_load_corrupted_file(self, temp_pantry_file):
        """Loading corrupted file should return default config."""
        temp_pantry_file.write_text("not valid json {{{")
        config = load_pantry_config(temp_pantry_file)
        assert config.user_items == set()


# =============================================================================
# Identification Tests
# =============================================================================


class TestIdentifyPantryItems:
    """Tests for identifying pantry items in ingredient lists."""

    def test_identifies_salt(self, sample_ingredients):
        """Salt should be identified as a pantry item."""
        pantry, other = identify_pantry_items(sample_ingredients)
        pantry_names = {p.name for p in pantry}
        assert "salt" in pantry_names

    def test_identifies_olive_oil(self, sample_ingredients):
        """Olive oil should be identified as a pantry item."""
        pantry, other = identify_pantry_items(sample_ingredients)
        pantry_names = {p.name for p in pantry}
        assert "olive oil" in pantry_names

    def test_identifies_danish_terms(self):
        """Danish pantry items like 'smør' should be identified."""
        ingredients = [
            ConsolidatedIngredient(name="smør", total_quantity=50.0, unit="g", sources=["Test"]),
            ConsolidatedIngredient(
                name="hvedemel", total_quantity=200.0, unit="g", sources=["Test"]
            ),
        ]
        pantry, other = identify_pantry_items(ingredients)
        pantry_names = {p.name for p in pantry}
        assert "smør" in pantry_names
        assert "hvedemel" in pantry_names

    def test_fresh_produce_not_pantry(self, sample_ingredients):
        """Fresh items like tomatoes should not be pantry items."""
        pantry, other = identify_pantry_items(sample_ingredients)
        other_names = {p.name for p in other}
        assert "tomatoes" in other_names
        assert "chicken breast" in other_names

    def test_splits_ingredients_correctly(self, sample_ingredients):
        """Should correctly split into pantry and other categories."""
        pantry, other = identify_pantry_items(sample_ingredients)

        # Pantry: salt, olive oil, pepper, sugar
        assert len(pantry) == 4

        # Other: chicken breast, tomatoes
        assert len(other) == 2

    def test_uses_custom_config(self, sample_ingredients):
        """Should use custom pantry config if provided."""
        # Config that excludes salt but adds tomatoes
        config = PantryConfig(
            user_items={"tomatoes"},
            excluded_defaults={"salt"},
        )
        pantry, other = identify_pantry_items(sample_ingredients, config)
        pantry_names = {p.name for p in pantry}

        assert "tomatoes" in pantry_names  # Added by user
        assert "salt" not in pantry_names  # Excluded by user


# =============================================================================
# Filter Tests
# =============================================================================


class TestFilterPantryItems:
    """Tests for filtering pantry items from ingredient lists."""

    def test_removes_excluded_items(self, sample_ingredients):
        """Excluded items should be removed from list."""
        filtered = filter_pantry_items(sample_ingredients, ["salt", "pepper"])
        names = {i.name for i in filtered}
        assert "salt" not in names
        assert "pepper" not in names

    def test_preserves_non_excluded(self, sample_ingredients):
        """Non-excluded items should remain."""
        filtered = filter_pantry_items(sample_ingredients, ["salt"])
        names = {i.name for i in filtered}
        assert "olive oil" in names
        assert "chicken breast" in names
        assert "tomatoes" in names

    def test_case_insensitive(self, sample_ingredients):
        """Filtering should be case-insensitive."""
        filtered = filter_pantry_items(sample_ingredients, ["SALT", "Olive Oil"])
        names = {i.name for i in filtered}
        assert "salt" not in names
        assert "olive oil" not in names

    def test_empty_exclude_list(self, sample_ingredients):
        """Empty exclude list should return all items."""
        filtered = filter_pantry_items(sample_ingredients, [])
        assert len(filtered) == len(sample_ingredients)


# =============================================================================
# Add/Remove Tests
# =============================================================================


class TestAddRemove:
    """Tests for adding and removing pantry items."""

    def test_add_to_empty_pantry(self, temp_pantry_file):
        """Adding items to empty pantry should work."""
        config = add_to_pantry(["fish sauce", "mirin"], temp_pantry_file)
        assert "fish sauce" in config.user_items
        assert "mirin" in config.user_items

    def test_add_removes_from_excluded(self, temp_pantry_file):
        """Adding a previously excluded default should remove from exclusions."""
        # First exclude salt
        remove_from_pantry(["salt"], temp_pantry_file)
        config = load_pantry_config(temp_pantry_file)
        assert "salt" in config.excluded_defaults

        # Now add salt back
        config = add_to_pantry(["salt"], temp_pantry_file)
        assert "salt" not in config.excluded_defaults

    def test_remove_user_item(self, temp_pantry_file):
        """Removing a user item should remove it from user_items."""
        add_to_pantry(["fish sauce"], temp_pantry_file)
        config = remove_from_pantry(["fish sauce"], temp_pantry_file)
        assert "fish sauce" not in config.user_items

    def test_remove_default_item(self, temp_pantry_file):
        """Removing a default item should add it to excluded_defaults."""
        config = remove_from_pantry(["salt"], temp_pantry_file)
        assert "salt" in config.excluded_defaults

    def test_clear_pantry(self, temp_pantry_file):
        """Clear should reset to defaults."""
        add_to_pantry(["fish sauce"], temp_pantry_file)
        remove_from_pantry(["salt"], temp_pantry_file)

        clear_pantry(temp_pantry_file)
        config = load_pantry_config(temp_pantry_file)

        assert config.user_items == set()
        assert config.excluded_defaults == set()


# =============================================================================
# Default Items Tests
# =============================================================================


class TestDefaultItems:
    """Tests for default pantry items."""

    def test_get_default_items(self):
        """Should return sorted list of defaults."""
        items = get_default_pantry_items()
        assert isinstance(items, list)
        assert items == sorted(items)

    def test_includes_common_items(self):
        """Default list should include common pantry staples."""
        items = set(get_default_pantry_items())
        # English
        assert "salt" in items
        assert "pepper" in items
        assert "sugar" in items
        assert "olive oil" in items
        assert "butter" in items
        # Danish
        assert "smør" in items
        assert "peber" in items
        assert "sukker" in items

    def test_not_too_large(self):
        """Default list should be reasonable size."""
        items = get_default_pantry_items()
        # Should have common items but not be excessive
        assert 50 <= len(items) <= 150


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestCLIIntegration:
    """Tests for CLI pantry commands."""

    def test_pantry_list_command(self):
        """Pantry list command should work."""
        from click.testing import CliRunner

        from nemlig_shopper.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["pantry", "list"])
        assert result.exit_code == 0
        assert "YOUR PANTRY" in result.output

    def test_pantry_defaults_command(self):
        """Pantry defaults command should show default items."""
        from click.testing import CliRunner

        from nemlig_shopper.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["pantry", "defaults"])
        assert result.exit_code == 0
        assert "DEFAULT PANTRY ITEMS" in result.output
        assert "salt" in result.output

    def test_pantry_add_and_remove(self, temp_pantry_file):
        """Add and remove commands should work."""
        from click.testing import CliRunner

        from nemlig_shopper.cli import cli

        runner = CliRunner()

        # Patch PANTRY_FILE to use temp file
        with patch("nemlig_shopper.cli.PANTRY_FILE", temp_pantry_file):
            # Add item
            result = runner.invoke(cli, ["pantry", "add", "test item"])
            assert result.exit_code == 0
            assert "Added" in result.output

            # Remove item
            result = runner.invoke(cli, ["pantry", "remove", "test item"])
            assert result.exit_code == 0
            assert "Removed" in result.output

    def test_pantry_clear(self, temp_pantry_file):
        """Clear command should reset pantry."""
        from click.testing import CliRunner

        from nemlig_shopper.cli import cli

        runner = CliRunner()

        with patch("nemlig_shopper.cli.PANTRY_FILE", temp_pantry_file):
            result = runner.invoke(cli, ["pantry", "clear", "--yes"])
            assert result.exit_code == 0
            assert "reset to defaults" in result.output


# =============================================================================
# LLM Tools Tests
# =============================================================================


class TestLLMTools:
    """Tests for LLM tool functions."""

    def test_identify_pantry_items_tool(self, sample_ingredients):
        """LLM tool should identify pantry items from dicts."""
        from nemlig_shopper import llm_tools

        # Convert to dict format
        consolidated = [
            {"name": i.name, "quantity": i.total_quantity, "unit": i.unit, "sources": i.sources}
            for i in sample_ingredients
        ]

        result = llm_tools.identify_pantry_items(consolidated)

        assert "pantry_candidates" in result
        assert "other_ingredients" in result
        assert result["total_candidates"] > 0
        assert result["total_other"] > 0

    def test_exclude_pantry_items_tool(self, sample_ingredients):
        """LLM tool should exclude specified items."""
        from nemlig_shopper import llm_tools

        consolidated = [
            {"name": i.name, "quantity": i.total_quantity, "unit": i.unit, "sources": i.sources}
            for i in sample_ingredients
        ]

        result = llm_tools.exclude_pantry_items(consolidated, ["salt", "pepper"])

        names = {item["name"] for item in result}
        assert "salt" not in names
        assert "pepper" not in names
        assert "chicken breast" in names

    def test_get_user_pantry_tool(self, temp_pantry_file):
        """LLM tool should return pantry config."""
        from nemlig_shopper import llm_tools

        with patch("nemlig_shopper.llm_tools.PANTRY_FILE", temp_pantry_file):
            result = llm_tools.get_user_pantry()

        assert "user_items" in result
        assert "all_active_items" in result
        assert result["default_count"] == len(DEFAULT_PANTRY_ITEMS)

    def test_get_default_pantry_items_tool(self):
        """LLM tool should return default items."""
        from nemlig_shopper import llm_tools

        result = llm_tools.get_default_pantry_items()

        assert "items" in result
        assert "count" in result
        assert result["count"] == len(DEFAULT_PANTRY_ITEMS)
        assert "salt" in result["items"]
