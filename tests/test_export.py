"""Tests for shopping list export functionality."""

import json
import tempfile
from pathlib import Path

from nemlig_shopper.export import (
    export_shopping_list,
    export_to_json,
    export_to_markdown,
)
from nemlig_shopper.matcher import ProductMatch


def make_product_match(
    ingredient: str,
    product_name: str | None = None,
    price: float | None = None,
    quantity: int = 1,
    matched: bool = True,
) -> ProductMatch:
    """Create a ProductMatch for testing."""
    if matched and product_name:
        product = {
            "id": 123,
            "name": product_name,
            "price": price,
            "unit_size": "500g",
        }
    else:
        product = None

    return ProductMatch(
        ingredient_name=ingredient,
        product=product,
        quantity=quantity,
        matched=matched,
        search_query=ingredient,
        alternatives=[],
    )


class TestExportToJson:
    """Tests for JSON export."""

    def test_basic_export(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00),
            make_product_match("sugar", "Sukker", 12.00),
        ]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            export_to_json(matches, filepath)

            with open(filepath) as f:
                data = json.load(f)

            assert "exported_at" in data
            assert len(data["items"]) == 2
            assert data["summary"]["total_items"] == 2
            assert data["summary"]["matched"] == 2
            assert data["summary"]["unmatched"] == 0
        finally:
            Path(filepath).unlink()

    def test_with_recipe_title(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            export_to_json(matches, filepath, recipe_title="Test Recipe")

            with open(filepath) as f:
                data = json.load(f)

            assert data["recipe_title"] == "Test Recipe"
        finally:
            Path(filepath).unlink()

    def test_unmatched_item(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00),
            make_product_match("rare_spice", matched=False),
        ]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            export_to_json(matches, filepath)

            with open(filepath) as f:
                data = json.load(f)

            assert data["summary"]["matched"] == 1
            assert data["summary"]["unmatched"] == 1
        finally:
            Path(filepath).unlink()

    def test_total_calculation(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00, quantity=2),
            make_product_match("sugar", "Sukker", 10.00, quantity=1),
        ]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            export_to_json(matches, filepath)

            with open(filepath) as f:
                data = json.load(f)

            # 15*2 + 10*1 = 40
            assert data["summary"]["estimated_total"] == 40.00
        finally:
            Path(filepath).unlink()


class TestExportToMarkdown:
    """Tests for Markdown export."""

    def test_basic_export(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00),
            make_product_match("sugar", "Sukker", 12.00),
        ]

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            filepath = f.name

        try:
            export_to_markdown(matches, filepath)

            content = Path(filepath).read_text()

            assert "# Shopping List" in content
            assert "flour" in content
            assert "Hvede Mel" in content
            assert "sugar" in content
            assert "Sukker" in content
        finally:
            Path(filepath).unlink()

    def test_with_recipe_title(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            filepath = f.name

        try:
            export_to_markdown(matches, filepath, recipe_title="My Recipe")

            content = Path(filepath).read_text()

            assert "# My Recipe" in content
        finally:
            Path(filepath).unlink()

    def test_unmatched_section(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00),
            make_product_match("rare_spice", matched=False),
        ]

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            filepath = f.name

        try:
            export_to_markdown(matches, filepath)

            content = Path(filepath).read_text()

            assert "## Unmatched Items" in content
            assert "rare_spice" in content
        finally:
            Path(filepath).unlink()

    def test_checkbox_format(self):
        matches = [
            make_product_match("flour", "Hvede Mel", 15.00),
            make_product_match("rare_spice", matched=False),
        ]

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            filepath = f.name

        try:
            export_to_markdown(matches, filepath)

            content = Path(filepath).read_text()

            # Matched items have [x]
            assert "[x] **flour**" in content
            # Unmatched items have [ ]
            assert "[ ] **rare_spice**" in content
        finally:
            Path(filepath).unlink()


class TestExportShoppingList:
    """Tests for the main export function."""

    def test_auto_detect_json(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name

        try:
            used_format = export_shopping_list(matches, filepath)
            assert used_format == "json"

            with open(filepath) as f:
                data = json.load(f)
            assert "items" in data
        finally:
            Path(filepath).unlink()

    def test_auto_detect_markdown(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            filepath = f.name

        try:
            used_format = export_shopping_list(matches, filepath)
            assert used_format == "md"

            content = Path(filepath).read_text()
            assert "# Shopping List" in content
        finally:
            Path(filepath).unlink()

    def test_explicit_format_override(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            filepath = f.name

        try:
            # Force JSON format even with .txt extension
            used_format = export_shopping_list(matches, filepath, format="json")
            assert used_format == "json"

            with open(filepath) as f:
                data = json.load(f)
            assert "items" in data
        finally:
            Path(filepath).unlink()

    def test_unsupported_format(self):
        matches = [make_product_match("flour", "Hvede Mel", 15.00)]

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            filepath = f.name

        try:
            import pytest

            with pytest.raises(ValueError, match="Unsupported format"):
                export_shopping_list(matches, filepath, format="xyz")
        finally:
            Path(filepath).unlink()
