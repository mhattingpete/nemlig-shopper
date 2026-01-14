"""Favorites storage and retrieval logic."""

import json
from datetime import datetime
from typing import Any

from .config import FAVORITES_FILE
from .recipe_parser import Recipe


class FavoritesError(Exception):
    """Exception raised for favorites-related errors."""

    pass


def _load_favorites() -> dict[str, Any]:
    """Load favorites from disk."""
    if not FAVORITES_FILE.exists():
        return {}

    try:
        with open(FAVORITES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise FavoritesError(f"Failed to load favorites: {e}") from e


def _save_favorites(favorites: dict[str, Any]) -> None:
    """Save favorites to disk."""
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, indent=2, ensure_ascii=False)
    except OSError as e:
        raise FavoritesError(f"Failed to save favorites: {e}") from e


def list_favorites() -> list[dict[str, Any]]:
    """
    List all saved favorites.

    Returns:
        List of favorite summaries with name, title, ingredient count, etc.
    """
    favorites = _load_favorites()

    result = []
    for name, data in favorites.items():
        result.append(
            {
                "name": name,
                "title": data.get("recipe", {}).get("title", "Unknown"),
                "ingredient_count": len(data.get("recipe", {}).get("ingredients", [])),
                "servings": data.get("recipe", {}).get("servings"),
                "source_url": data.get("recipe", {}).get("source_url"),
                "saved_at": data.get("saved_at"),
                "has_product_matches": bool(data.get("product_matches")),
            }
        )

    return sorted(result, key=lambda x: x["name"])


def get_favorite(name: str) -> dict[str, Any]:
    """
    Get a specific favorite by name.

    Args:
        name: The favorite's name/alias

    Returns:
        Full favorite data including recipe and product matches

    Raises:
        FavoritesError: If favorite not found
    """
    favorites = _load_favorites()

    if name not in favorites:
        raise FavoritesError(f"Favorite '{name}' not found")

    return favorites[name]


def get_favorite_recipe(name: str) -> Recipe:
    """
    Get the recipe from a favorite.

    Args:
        name: The favorite's name/alias

    Returns:
        Recipe object

    Raises:
        FavoritesError: If favorite not found
    """
    favorite = get_favorite(name)
    recipe_data = favorite.get("recipe", {})
    return Recipe.from_dict(recipe_data)


def save_favorite(
    name: str,
    recipe: Recipe,
    product_matches: list[dict[str, Any]] | None = None,
    overwrite: bool = False,
) -> None:
    """
    Save a recipe as a favorite.

    Args:
        name: Name/alias for the favorite
        recipe: The recipe to save
        product_matches: Optional list of matched products
        overwrite: Whether to overwrite if name exists

    Raises:
        FavoritesError: If name exists and overwrite is False
    """
    favorites = _load_favorites()

    if name in favorites and not overwrite:
        raise FavoritesError(f"Favorite '{name}' already exists. Use --overwrite to replace.")

    favorites[name] = {
        "recipe": recipe.to_dict(),
        "product_matches": product_matches or [],
        "saved_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    _save_favorites(favorites)


def update_favorite_matches(name: str, product_matches: list[dict[str, Any]]) -> None:
    """
    Update the product matches for a favorite.

    Args:
        name: The favorite's name
        product_matches: New product matches

    Raises:
        FavoritesError: If favorite not found
    """
    favorites = _load_favorites()

    if name not in favorites:
        raise FavoritesError(f"Favorite '{name}' not found")

    favorites[name]["product_matches"] = product_matches
    favorites[name]["updated_at"] = datetime.now().isoformat()

    _save_favorites(favorites)


def delete_favorite(name: str) -> None:
    """
    Delete a favorite.

    Args:
        name: The favorite's name

    Raises:
        FavoritesError: If favorite not found
    """
    favorites = _load_favorites()

    if name not in favorites:
        raise FavoritesError(f"Favorite '{name}' not found")

    del favorites[name]
    _save_favorites(favorites)


def rename_favorite(old_name: str, new_name: str) -> None:
    """
    Rename a favorite.

    Args:
        old_name: Current name
        new_name: New name

    Raises:
        FavoritesError: If old name not found or new name exists
    """
    favorites = _load_favorites()

    if old_name not in favorites:
        raise FavoritesError(f"Favorite '{old_name}' not found")

    if new_name in favorites:
        raise FavoritesError(f"Favorite '{new_name}' already exists")

    favorites[new_name] = favorites.pop(old_name)
    favorites[new_name]["updated_at"] = datetime.now().isoformat()

    _save_favorites(favorites)


def favorite_exists(name: str) -> bool:
    """Check if a favorite with the given name exists."""
    favorites = _load_favorites()
    return name in favorites


def get_favorite_product_ids(name: str) -> list[dict[str, Any]]:
    """
    Get product IDs and quantities from a saved favorite.

    Args:
        name: The favorite's name

    Returns:
        List of dicts with product_id and quantity

    Raises:
        FavoritesError: If favorite not found or has no matches
    """
    favorite = get_favorite(name)
    matches = favorite.get("product_matches", [])

    if not matches:
        raise FavoritesError(
            f"Favorite '{name}' has no saved product matches. "
            "Run 'nemlig favorites update <name>' to match products."
        )

    return [
        {"product_id": m["product_id"], "quantity": m.get("quantity", 1)}
        for m in matches
        if m.get("matched") and m.get("product_id")
    ]
