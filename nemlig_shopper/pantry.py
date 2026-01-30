"""Pantry management: identify and filter common household items.

The pantry is a simple text file (~/.nemlig-shopper/pantry.txt) with one item per line.
Edit it directly or use the CLI commands to manage your pantry.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .planner import ConsolidatedIngredient

# Default pantry items - minimal set (only absolute basics)
# These are used to initialize the pantry file if it doesn't exist
DEFAULT_PANTRY_ITEMS: set[str] = {
    # Water
    "water",
    "vand",
    # Oil
    "oil",
    "olie",
    "olive oil",
    "olivenolie",
    # Salt & pepper
    "salt",
    "pepper",
    "peber",
    "black pepper",
    "sort peber",
}


def _normalize(name: str) -> str:
    """Normalize item name for matching."""
    return name.lower().strip()


def load_pantry(pantry_file: Path) -> set[str]:
    """Load pantry items from text file.

    If the file doesn't exist, creates it with default items.
    """
    if not pantry_file.exists():
        save_pantry(DEFAULT_PANTRY_ITEMS, pantry_file)
        return DEFAULT_PANTRY_ITEMS.copy()

    try:
        text = pantry_file.read_text()
        items = {_normalize(line) for line in text.splitlines() if line.strip()}
        return items
    except OSError:
        return DEFAULT_PANTRY_ITEMS.copy()


def save_pantry(items: set[str], pantry_file: Path) -> None:
    """Save pantry items to text file."""
    pantry_file.parent.mkdir(parents=True, exist_ok=True)
    pantry_file.write_text("\n".join(sorted(items)) + "\n")


def add_to_pantry(items: list[str], pantry_file: Path) -> set[str]:
    """Add items to the pantry file."""
    current = load_pantry(pantry_file)
    for item in items:
        current.add(_normalize(item))
    save_pantry(current, pantry_file)
    return current


def remove_from_pantry(items: list[str], pantry_file: Path) -> set[str]:
    """Remove items from the pantry file."""
    current = load_pantry(pantry_file)
    for item in items:
        current.discard(_normalize(item))
    save_pantry(current, pantry_file)
    return current


def clear_pantry(pantry_file: Path) -> None:
    """Reset pantry to default items."""
    save_pantry(DEFAULT_PANTRY_ITEMS, pantry_file)


def get_default_pantry_items() -> list[str]:
    """Get sorted list of default pantry items."""
    return sorted(DEFAULT_PANTRY_ITEMS)


def _is_pantry_item(ingredient_name: str, pantry_items: set[str]) -> bool:
    """Check if an ingredient matches any pantry item.

    Uses word boundary matching to avoid false positives like
    "salt" matching "havsalt" (sea salt) in "knækbrød havsalt".
    """

    normalized = _normalize(ingredient_name)
    words = normalized.split()

    # Exact match
    if normalized in pantry_items:
        return True

    # Check if any multi-word pantry item is contained in the ingredient name
    # e.g., "olive oil" matches "extra virgin olive oil"
    for item in pantry_items:
        item_lower = item.lower()
        if " " in item_lower:
            # Multi-word items: allow substring matching
            if item_lower in normalized or normalized in item_lower:
                return True

    # Check individual words for common items like "salt", "pepper"
    # Must match as a complete word, not as part of a compound word
    single_word_pantry = {p.lower() for p in pantry_items if " " not in p}
    for word in words:
        # Exact word match only (not substring of compound words)
        if word in single_word_pantry:
            return True

    return False


def identify_pantry_items(
    ingredients: list[ConsolidatedIngredient],
    pantry_items: set[str] | None = None,
) -> tuple[list[ConsolidatedIngredient], list[ConsolidatedIngredient]]:
    """Split ingredients into pantry candidates and other items.

    Args:
        ingredients: List of consolidated ingredients
        pantry_items: Set of pantry item names (uses defaults if None)

    Returns:
        Tuple of (pantry_candidates, other_ingredients)
    """
    if pantry_items is None:
        pantry_items = DEFAULT_PANTRY_ITEMS

    pantry_candidates: list[ConsolidatedIngredient] = []
    other_ingredients: list[ConsolidatedIngredient] = []

    for ingredient in ingredients:
        if _is_pantry_item(ingredient.name, pantry_items):
            pantry_candidates.append(ingredient)
        else:
            other_ingredients.append(ingredient)

    return pantry_candidates, other_ingredients


def filter_pantry_items(
    ingredients: list[ConsolidatedIngredient],
    items_to_exclude: list[str],
) -> list[ConsolidatedIngredient]:
    """Remove specified items from ingredient list.

    Args:
        ingredients: List of consolidated ingredients
        items_to_exclude: Names of items to exclude (case-insensitive)

    Returns:
        Filtered list with excluded items removed
    """
    if not items_to_exclude:
        return ingredients

    exclude_normalized = {_normalize(name) for name in items_to_exclude if name is not None}

    return [ing for ing in ingredients if _normalize(ing.name) not in exclude_normalized]
