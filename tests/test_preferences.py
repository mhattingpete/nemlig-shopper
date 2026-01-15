"""Tests for the preferences module."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from nemlig_shopper.preferences import (
    PreferencesError,
    clear_preferences,
    find_preferred_by_name,
    get_last_sync_time,
    get_preference_count,
    get_preferred_products,
    is_preferred_product,
    sync_preferences_from_orders,
)


@pytest.fixture
def temp_preferences_file(tmp_path, monkeypatch):
    """Create a temporary preferences file for testing."""
    preferences_file = tmp_path / "preferences.json"
    monkeypatch.setattr("nemlig_shopper.preferences.PREFERENCES_FILE", preferences_file)
    return preferences_file


@pytest.fixture
def populated_preferences(temp_preferences_file):
    """Create a preferences file with sample data."""
    preferences_data = {
        "products": {
            "1001": {
                "name": "Økologisk Sødmælk 1L",
                "category": "Mælk",
                "main_category": "Mejeri",
                "synced_at": "2026-01-10T10:00:00",
            },
            "1002": {
                "name": "Rugbrød",
                "category": "Brød",
                "main_category": "Bageri",
                "synced_at": "2026-01-10T10:00:00",
            },
            "1003": {
                "name": "Økologiske Æg 10 stk",
                "category": "Æg",
                "main_category": "Mejeri",
                "synced_at": "2026-01-10T10:00:00",
            },
        },
        "synced_at": "2026-01-10T10:00:00",
    }
    with open(temp_preferences_file, "w", encoding="utf-8") as f:
        json.dump(preferences_data, f)
    return temp_preferences_file


@pytest.fixture
def mock_api():
    """Create a mock API that returns order products."""
    api = MagicMock()
    api.get_previous_order_products.return_value = [
        {
            "product_id": "2001",
            "name": "Havregryn",
            "category": "Morgenmad",
            "main_category": "Kolonial",
        },
        {
            "product_id": "2002",
            "name": "Smør",
            "category": "Smør & Margarine",
            "main_category": "Mejeri",
        },
    ]
    return api


# ============================================================================
# Get Preferred Products Tests
# ============================================================================


class TestGetPreferredProducts:
    """Tests for get_preferred_products function."""

    def test_get_products_when_no_file(self, temp_preferences_file):
        """Should return empty dict when no preferences file."""
        result = get_preferred_products()
        assert result == {}

    def test_get_products_returns_all(self, populated_preferences):
        """Should return all stored products."""
        result = get_preferred_products()

        assert len(result) == 3
        assert "1001" in result
        assert "1002" in result
        assert "1003" in result
        assert result["1001"]["name"] == "Økologisk Sødmælk 1L"

    def test_get_products_empty_file(self, temp_preferences_file):
        """Should return empty dict for empty preferences."""
        with open(temp_preferences_file, "w") as f:
            json.dump({"products": {}, "synced_at": None}, f)

        result = get_preferred_products()
        assert result == {}


# ============================================================================
# Is Preferred Product Tests
# ============================================================================


class TestIsPreferredProduct:
    """Tests for is_preferred_product function."""

    def test_returns_true_for_existing(self, populated_preferences):
        """Should return True for products in preferences."""
        assert is_preferred_product("1001") is True
        assert is_preferred_product("1002") is True

    def test_returns_false_for_nonexistent(self, populated_preferences):
        """Should return False for products not in preferences."""
        assert is_preferred_product("9999") is False

    def test_handles_int_product_id(self, populated_preferences):
        """Should handle integer product IDs."""
        assert is_preferred_product(1001) is True
        assert is_preferred_product(9999) is False

    def test_returns_false_when_no_file(self, temp_preferences_file):
        """Should return False when no preferences file."""
        assert is_preferred_product("anything") is False


# ============================================================================
# Find Preferred By Name Tests
# ============================================================================


class TestFindPreferredByName:
    """Tests for find_preferred_by_name function."""

    def test_find_exact_match(self, populated_preferences):
        """Should find products with exact name match."""
        result = find_preferred_by_name("Rugbrød")

        assert len(result) == 1
        assert result[0]["product_id"] == "1002"
        assert result[0]["name"] == "Rugbrød"

    def test_find_partial_match(self, populated_preferences):
        """Should find products with partial name match."""
        result = find_preferred_by_name("mælk")

        assert len(result) == 1
        assert result[0]["product_id"] == "1001"

    def test_find_case_insensitive(self, populated_preferences):
        """Should match case-insensitively."""
        result = find_preferred_by_name("RUGBRØD")

        assert len(result) == 1
        assert result[0]["name"] == "Rugbrød"

    def test_find_multiple_matches(self, populated_preferences):
        """Should return all matching products."""
        result = find_preferred_by_name("Økologisk")

        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "Økologisk Sødmælk 1L" in names
        assert "Økologiske Æg 10 stk" in names

    def test_find_no_matches(self, populated_preferences):
        """Should return empty list when no matches."""
        result = find_preferred_by_name("nonexistent")
        assert result == []

    def test_find_when_no_file(self, temp_preferences_file):
        """Should return empty list when no preferences file."""
        result = find_preferred_by_name("anything")
        assert result == []

    def test_find_includes_product_id(self, populated_preferences):
        """Result should include product_id field."""
        result = find_preferred_by_name("Rugbrød")

        assert "product_id" in result[0]
        assert result[0]["product_id"] == "1002"


# ============================================================================
# Sync Preferences From Orders Tests
# ============================================================================


class TestSyncPreferencesFromOrders:
    """Tests for sync_preferences_from_orders function."""

    def test_sync_creates_preferences(self, temp_preferences_file, mock_api):
        """Should create preferences from order products."""
        count = sync_preferences_from_orders(mock_api, num_orders=5)

        assert count == 2
        mock_api.get_previous_order_products.assert_called_once_with(5)

        # Verify data was saved
        products = get_preferred_products()
        assert "2001" in products
        assert "2002" in products
        assert products["2001"]["name"] == "Havregryn"

    def test_sync_updates_existing(self, populated_preferences, mock_api):
        """Should add new products while keeping existing."""
        # Initially 3 products
        assert get_preference_count() == 3

        sync_preferences_from_orders(mock_api)

        # Should now have 5 products (3 existing + 2 new)
        assert get_preference_count() == 5

    def test_sync_updates_synced_at(self, temp_preferences_file, mock_api):
        """Should update the synced_at timestamp."""
        before = get_last_sync_time()
        assert before is None

        sync_preferences_from_orders(mock_api)

        after = get_last_sync_time()
        assert after is not None
        # Should be a recent timestamp
        sync_time = datetime.fromisoformat(after)
        assert (datetime.now() - sync_time).total_seconds() < 5

    def test_sync_handles_api_error(self, temp_preferences_file):
        """Should raise PreferencesError on API failure."""
        mock_api = MagicMock()
        mock_api.get_previous_order_products.side_effect = Exception("API error")

        with pytest.raises(PreferencesError) as exc_info:
            sync_preferences_from_orders(mock_api)

        assert "Failed to fetch order history" in str(exc_info.value)

    def test_sync_skips_products_without_id(self, temp_preferences_file):
        """Should skip products without product_id."""
        mock_api = MagicMock()
        mock_api.get_previous_order_products.return_value = [
            {"product_id": "1001", "name": "Valid Product"},
            {"name": "No ID Product"},  # Missing product_id
            {"product_id": None, "name": "Null ID"},  # None product_id
        ]

        sync_preferences_from_orders(mock_api)

        products = get_preferred_products()
        assert len(products) == 1
        assert "1001" in products


# ============================================================================
# Get Last Sync Time Tests
# ============================================================================


class TestGetLastSyncTime:
    """Tests for get_last_sync_time function."""

    def test_returns_timestamp(self, populated_preferences):
        """Should return the synced_at timestamp."""
        result = get_last_sync_time()
        assert result == "2026-01-10T10:00:00"

    def test_returns_none_when_never_synced(self, temp_preferences_file):
        """Should return None when preferences don't exist."""
        result = get_last_sync_time()
        assert result is None

    def test_returns_none_when_synced_at_null(self, temp_preferences_file):
        """Should return None when synced_at is null."""
        with open(temp_preferences_file, "w") as f:
            json.dump({"products": {}, "synced_at": None}, f)

        result = get_last_sync_time()
        assert result is None


# ============================================================================
# Clear Preferences Tests
# ============================================================================


class TestClearPreferences:
    """Tests for clear_preferences function."""

    def test_clear_removes_products(self, populated_preferences):
        """Should remove all products."""
        assert get_preference_count() == 3

        clear_preferences()

        assert get_preference_count() == 0

    def test_clear_resets_sync_time(self, populated_preferences):
        """Should reset synced_at to None."""
        assert get_last_sync_time() is not None

        clear_preferences()

        assert get_last_sync_time() is None

    def test_clear_when_no_file(self, temp_preferences_file):
        """Should handle clearing when no file exists."""
        clear_preferences()

        assert get_preference_count() == 0


# ============================================================================
# Get Preference Count Tests
# ============================================================================


class TestGetPreferenceCount:
    """Tests for get_preference_count function."""

    def test_returns_count(self, populated_preferences):
        """Should return correct product count."""
        assert get_preference_count() == 3

    def test_returns_zero_when_empty(self, temp_preferences_file):
        """Should return 0 when no preferences."""
        assert get_preference_count() == 0

    def test_returns_zero_after_clear(self, populated_preferences):
        """Should return 0 after clearing."""
        clear_preferences()
        assert get_preference_count() == 0


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestPreferencesErrorHandling:
    """Tests for error handling in preferences module."""

    def test_load_corrupt_json_raises_error(self, temp_preferences_file):
        """Should raise PreferencesError for corrupt JSON."""
        with open(temp_preferences_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(PreferencesError) as exc_info:
            get_preferred_products()

        assert "Failed to load" in str(exc_info.value)

    def test_save_to_readonly_raises_error(self, temp_preferences_file, mock_api):
        """Should raise PreferencesError when file is not writable."""
        # Create a valid file first
        with open(temp_preferences_file, "w") as f:
            json.dump({"products": {}, "synced_at": None}, f)

        # Make it read-only
        temp_preferences_file.chmod(0o444)

        try:
            with pytest.raises(PreferencesError) as exc_info:
                sync_preferences_from_orders(mock_api)

            assert "Failed to save" in str(exc_info.value)
        finally:
            temp_preferences_file.chmod(0o644)


# ============================================================================
# Data Integrity Tests
# ============================================================================


class TestDataIntegrity:
    """Tests for data integrity in preferences module."""

    def test_unicode_names_preserved(self, temp_preferences_file, mock_api):
        """Should preserve unicode characters in product names."""
        mock_api.get_previous_order_products.return_value = [
            {
                "product_id": "1001",
                "name": "Rødgrød med fløde",
                "category": "Dessert",
                "main_category": "Kolonial",
            }
        ]

        sync_preferences_from_orders(mock_api)

        products = get_preferred_products()
        assert products["1001"]["name"] == "Rødgrød med fløde"

    def test_sync_preserves_existing_products(self, populated_preferences, mock_api):
        """Sync should preserve existing products when adding new ones."""
        # Get original products
        original = get_preferred_products()
        assert "1001" in original

        # Sync new products
        sync_preferences_from_orders(mock_api)

        # Original products should still be there
        products = get_preferred_products()
        assert "1001" in products
        assert products["1001"]["name"] == "Økologisk Sødmælk 1L"

        # New products should be added
        assert "2001" in products

    def test_multiple_syncs_accumulate(self, temp_preferences_file):
        """Multiple syncs should accumulate products."""
        # First sync
        mock_api1 = MagicMock()
        mock_api1.get_previous_order_products.return_value = [
            {"product_id": "1", "name": "Product 1"}
        ]
        sync_preferences_from_orders(mock_api1)
        assert get_preference_count() == 1

        # Second sync with different products
        mock_api2 = MagicMock()
        mock_api2.get_previous_order_products.return_value = [
            {"product_id": "2", "name": "Product 2"}
        ]
        sync_preferences_from_orders(mock_api2)
        assert get_preference_count() == 2

        # Both should be present
        products = get_preferred_products()
        assert "1" in products
        assert "2" in products
