"""User preferences based on order history."""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .config import PREFERENCES_FILE

if TYPE_CHECKING:
    from .api import NemligAPI


class PreferencesError(Exception):
    """Exception raised for preferences-related errors."""

    pass


def _load_preferences() -> dict[str, Any]:
    """Load preferences from disk."""
    if not PREFERENCES_FILE.exists():
        return {"products": {}, "synced_at": None}

    try:
        with open(PREFERENCES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise PreferencesError(f"Failed to load preferences: {e}") from e


def _save_preferences(preferences: dict[str, Any]) -> None:
    """Save preferences to disk."""
    try:
        with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=2, ensure_ascii=False)
    except OSError as e:
        raise PreferencesError(f"Failed to save preferences: {e}") from e


def sync_preferences_from_orders(api: "NemligAPI", num_orders: int = 10) -> int:
    """
    Sync preferences from recent order history.

    Fetches products from the user's recent orders and stores them
    as preferred products for better ingredient matching.

    Args:
        api: Logged-in NemligAPI instance
        num_orders: Number of recent orders to fetch

    Returns:
        Number of unique products synced

    Raises:
        PreferencesError: If sync fails
    """
    try:
        products = api.get_previous_order_products(num_orders)
    except Exception as e:
        raise PreferencesError(f"Failed to fetch order history: {e}") from e

    preferences = _load_preferences()

    # Update products, keeping existing data but refreshing with new
    for product in products:
        product_id = product.get("product_id")
        if product_id:
            preferences["products"][product_id] = {
                "name": product.get("name", ""),
                "category": product.get("category", ""),
                "main_category": product.get("main_category", ""),
                "synced_at": datetime.now().isoformat(),
            }

    preferences["synced_at"] = datetime.now().isoformat()
    _save_preferences(preferences)

    return len(products)


def get_preferred_products() -> dict[str, dict[str, Any]]:
    """
    Get all preferred products.

    Returns:
        Dict mapping product_id to product info
    """
    preferences = _load_preferences()
    return preferences.get("products", {})


def is_preferred_product(product_id: str | int) -> bool:
    """
    Check if a product is in the user's preferences.

    Args:
        product_id: Product ID to check

    Returns:
        True if product has been purchased before
    """
    preferences = _load_preferences()
    return str(product_id) in preferences.get("products", {})


def find_preferred_by_name(name: str) -> list[dict[str, Any]]:
    """
    Find preferred products matching a name.

    Args:
        name: Ingredient/product name to search for

    Returns:
        List of matching preferred products with their IDs
    """
    preferences = _load_preferences()
    products = preferences.get("products", {})
    name_lower = name.lower()

    matches = []
    for product_id, info in products.items():
        product_name = info.get("name", "").lower()
        if name_lower in product_name or product_name in name_lower:
            matches.append({"product_id": product_id, **info})

    return matches


def get_last_sync_time() -> str | None:
    """Get the timestamp of the last preference sync."""
    preferences = _load_preferences()
    return preferences.get("synced_at")


def clear_preferences() -> None:
    """Clear all stored preferences."""
    _save_preferences({"products": {}, "synced_at": None})


def get_preference_count() -> int:
    """Get the number of stored preferred products."""
    preferences = _load_preferences()
    return len(preferences.get("products", {}))
