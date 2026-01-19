"""Tests for the pantry module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nemlig_shopper.pantry import (
    DEFAULT_PANTRY_ITEMS,
    add_to_pantry,
    clear_pantry,
    filter_pantry_items,
    get_default_pantry_items,
    identify_pantry_items,
    load_pantry,
    remove_from_pantry,
    save_pantry,
)
from nemlig_shopper.planner import ConsolidatedIngredient


@pytest.fixture
def temp_pantry_file(tmp_path) -> Path:
    """Create a temporary pantry file path."""
    return tmp_path / "pantry.txt"


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
        ConsolidatedIngredient(name="water", total_quantity=500.0, unit="ml", sources=["Recipe 2"]),
    ]


# =============================================================================
# Persistence Tests
# =============================================================================


class TestPersistence:
    """Tests for loading and saving pantry items."""

    def test_load_nonexistent_file_creates_defaults(self, temp_pantry_file):
        """Loading nonexistent file should create it with defaults."""
        items = load_pantry(temp_pantry_file)
        assert items == DEFAULT_PANTRY_ITEMS
        assert temp_pantry_file.exists()

    def test_save_and_load_roundtrip(self, temp_pantry_file):
        """Items should survive save/load roundtrip."""
        items = {"fish sauce", "rice vinegar", "salt"}
        save_pantry(items, temp_pantry_file)

        loaded = load_pantry(temp_pantry_file)
        assert loaded == items

    def test_load_text_file_format(self, temp_pantry_file):
        """Should load items from simple text file (one per line)."""
        temp_pantry_file.write_text("salt\npepper\nolive oil\n")
        items = load_pantry(temp_pantry_file)
        assert items == {"salt", "pepper", "olive oil"}

    def test_load_ignores_empty_lines(self, temp_pantry_file):
        """Should ignore empty lines in the file."""
        temp_pantry_file.write_text("salt\n\npepper\n  \n")
        items = load_pantry(temp_pantry_file)
        assert items == {"salt", "pepper"}

    def test_normalizes_items_on_load(self, temp_pantry_file):
        """Should normalize items (lowercase, strip whitespace)."""
        temp_pantry_file.write_text("  SALT  \n  Olive Oil  \n")
        items = load_pantry(temp_pantry_file)
        assert items == {"salt", "olive oil"}


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
        """Danish pantry items like 'olie' should be identified."""
        ingredients = [
            ConsolidatedIngredient(
                name="olivenolie", total_quantity=50.0, unit="ml", sources=["Test"]
            ),
            ConsolidatedIngredient(name="peber", total_quantity=1.0, unit="tsp", sources=["Test"]),
        ]
        pantry, other = identify_pantry_items(ingredients)
        pantry_names = {p.name for p in pantry}
        assert "olivenolie" in pantry_names
        assert "peber" in pantry_names

    def test_fresh_produce_not_pantry(self, sample_ingredients):
        """Fresh items like tomatoes should not be pantry items."""
        pantry, other = identify_pantry_items(sample_ingredients)
        other_names = {p.name for p in other}
        assert "tomatoes" in other_names
        assert "chicken breast" in other_names

    def test_splits_ingredients_correctly(self, sample_ingredients):
        """Should correctly split into pantry and other categories."""
        pantry, other = identify_pantry_items(sample_ingredients)

        # Pantry: salt, olive oil, pepper, water
        assert len(pantry) == 4

        # Other: chicken breast, tomatoes
        assert len(other) == 2

    def test_uses_custom_items(self, sample_ingredients):
        """Should use custom pantry items set if provided."""
        # Custom set that includes tomatoes but not salt
        custom_items = {"tomatoes", "olive oil"}
        pantry, other = identify_pantry_items(sample_ingredients, custom_items)
        pantry_names = {p.name for p in pantry}

        assert "tomatoes" in pantry_names  # In custom set
        assert "salt" not in pantry_names  # Not in custom set


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
        items = add_to_pantry(["fish sauce", "mirin"], temp_pantry_file)
        assert "fish sauce" in items
        assert "mirin" in items

    def test_add_to_existing_pantry(self, temp_pantry_file):
        """Adding items should preserve existing items."""
        save_pantry({"salt", "pepper"}, temp_pantry_file)
        items = add_to_pantry(["fish sauce"], temp_pantry_file)
        assert "salt" in items
        assert "pepper" in items
        assert "fish sauce" in items

    def test_remove_item(self, temp_pantry_file):
        """Removing an item should remove it from the set."""
        save_pantry({"salt", "pepper", "fish sauce"}, temp_pantry_file)
        items = remove_from_pantry(["fish sauce"], temp_pantry_file)
        assert "fish sauce" not in items
        assert "salt" in items

    def test_remove_nonexistent_item(self, temp_pantry_file):
        """Removing nonexistent item should not raise error."""
        save_pantry({"salt", "pepper"}, temp_pantry_file)
        items = remove_from_pantry(["nonexistent"], temp_pantry_file)
        assert items == {"salt", "pepper"}

    def test_clear_pantry(self, temp_pantry_file):
        """Clear should reset to defaults."""
        save_pantry({"fish sauce", "custom item"}, temp_pantry_file)
        clear_pantry(temp_pantry_file)
        items = load_pantry(temp_pantry_file)
        assert items == DEFAULT_PANTRY_ITEMS


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
        """Default list should include basic pantry staples."""
        items = set(get_default_pantry_items())
        # English
        assert "salt" in items
        assert "pepper" in items
        assert "olive oil" in items
        assert "water" in items
        # Danish
        assert "peber" in items
        assert "vand" in items

    def test_minimal_size(self):
        """Default list should be minimal (user adds more if needed)."""
        items = get_default_pantry_items()
        # Minimal set: water, oil, salt, pepper (both languages)
        assert 5 <= len(items) <= 20


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestCLIIntegration:
    """Tests for CLI pantry commands."""

    def test_pantry_list_command(self, temp_pantry_file):
        """Pantry list command should work."""
        from click.testing import CliRunner

        from nemlig_shopper.cli import cli

        runner = CliRunner()
        with patch("nemlig_shopper.cli.PANTRY_FILE", temp_pantry_file):
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
        """LLM tool should return pantry items."""
        from nemlig_shopper import llm_tools

        with patch("nemlig_shopper.llm_tools.PANTRY_FILE", temp_pantry_file):
            result = llm_tools.get_user_pantry()

        assert "items" in result
        assert "count" in result

    def test_get_default_pantry_items_tool(self):
        """LLM tool should return default items."""
        from nemlig_shopper import llm_tools

        result = llm_tools.get_default_pantry_items()

        assert "items" in result
        assert "count" in result
        assert result["count"] == len(DEFAULT_PANTRY_ITEMS)
        assert "salt" in result["items"]
