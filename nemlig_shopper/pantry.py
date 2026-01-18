"""Pantry management: identify and filter common household items."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .planner import ConsolidatedIngredient

# Default pantry items - minimal set (only absolute basics)
# User can expand via `nemlig pantry add`
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


@dataclass
class PantryConfig:
    """Configuration for pantry items."""

    user_items: set[str] = field(default_factory=set)
    excluded_defaults: set[str] = field(default_factory=set)
    updated_at: datetime | None = None

    @property
    def all_pantry_items(self) -> set[str]:
        """Get all active pantry items (defaults + user, minus excluded)."""
        return (DEFAULT_PANTRY_ITEMS - self.excluded_defaults) | self.user_items

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "version": 1,
            "user_items": sorted(self.user_items),
            "excluded_defaults": sorted(self.excluded_defaults),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PantryConfig:
        """Create from dict."""
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])

        return cls(
            user_items=set(data.get("user_items", [])),
            excluded_defaults=set(data.get("excluded_defaults", [])),
            updated_at=updated_at,
        )


def load_pantry_config(pantry_file: Path) -> PantryConfig:
    """Load pantry configuration from disk."""
    if not pantry_file.exists():
        return PantryConfig()

    try:
        with open(pantry_file) as f:
            data = json.load(f)
        return PantryConfig.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return PantryConfig()


def save_pantry_config(config: PantryConfig, pantry_file: Path) -> None:
    """Save pantry configuration to disk."""
    config.updated_at = datetime.now()
    pantry_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pantry_file, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def _normalize_for_matching(name: str) -> str:
    """Normalize ingredient name for pantry matching."""
    return name.lower().strip()


def _is_pantry_item(ingredient_name: str, pantry_items: set[str]) -> bool:
    """Check if an ingredient matches any pantry item."""
    normalized = _normalize_for_matching(ingredient_name)

    # Exact match
    if normalized in pantry_items:
        return True

    # Check if any pantry item is contained in the ingredient name
    # e.g., "olive oil" matches "extra virgin olive oil"
    for item in pantry_items:
        item_lower = item.lower()
        if item_lower in normalized or normalized in item_lower:
            return True

    # Check individual words for common items like "salt", "pepper"
    words = normalized.split()
    single_word_pantry = {p.lower() for p in pantry_items if " " not in p}
    for word in words:
        if word in single_word_pantry:
            return True

    return False


def identify_pantry_items(
    ingredients: list[ConsolidatedIngredient],
    config: PantryConfig | None = None,
) -> tuple[list[ConsolidatedIngredient], list[ConsolidatedIngredient]]:
    """
    Split ingredients into pantry candidates and other items.

    Args:
        ingredients: List of consolidated ingredients
        config: Optional pantry configuration (uses defaults if None)

    Returns:
        Tuple of (pantry_candidates, other_ingredients)
    """
    if config is None:
        config = PantryConfig()

    pantry_items = config.all_pantry_items
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
    """
    Remove specified items from ingredient list.

    Args:
        ingredients: List of consolidated ingredients
        items_to_exclude: Names of items to exclude (case-insensitive)

    Returns:
        Filtered list with excluded items removed
    """
    if not items_to_exclude:
        return ingredients

    exclude_normalized = {
        _normalize_for_matching(name) for name in items_to_exclude if name is not None
    }

    return [
        ing for ing in ingredients if _normalize_for_matching(ing.name) not in exclude_normalized
    ]


def add_to_pantry(
    items: list[str],
    pantry_file: Path,
) -> PantryConfig:
    """Add items to user's pantry."""
    config = load_pantry_config(pantry_file)
    for item in items:
        normalized = _normalize_for_matching(item)
        config.user_items.add(normalized)
        # Remove from excluded if it was there
        config.excluded_defaults.discard(normalized)
    save_pantry_config(config, pantry_file)
    return config


def remove_from_pantry(
    items: list[str],
    pantry_file: Path,
) -> PantryConfig:
    """Remove items from user's pantry."""
    config = load_pantry_config(pantry_file)
    for item in items:
        normalized = _normalize_for_matching(item)
        # Remove from user items
        config.user_items.discard(normalized)
        # If it's a default item, add to excluded
        if normalized in {p.lower() for p in DEFAULT_PANTRY_ITEMS}:
            config.excluded_defaults.add(normalized)
    save_pantry_config(config, pantry_file)
    return config


def clear_pantry(pantry_file: Path) -> None:
    """Clear all pantry customizations."""
    config = PantryConfig()
    save_pantry_config(config, pantry_file)


def get_default_pantry_items() -> list[str]:
    """Get sorted list of default pantry items."""
    return sorted(DEFAULT_PANTRY_ITEMS)
