"""Recipe scaling and quantity math logic."""

import math
from dataclasses import dataclass

from .recipe_parser import Ingredient, Recipe


@dataclass
class ScaledIngredient:
    """An ingredient with scaled quantity."""

    original: Ingredient
    scaled_quantity: float | None
    scale_factor: float

    @property
    def name(self) -> str:
        return self.original.name

    @property
    def unit(self) -> str | None:
        return self.original.unit

    def __str__(self) -> str:
        parts = []
        if self.scaled_quantity is not None:
            # Format quantity nicely
            qty = self.scaled_quantity
            if qty == int(qty):
                parts.append(str(int(qty)))
            else:
                parts.append(f"{qty:.2f}".rstrip("0").rstrip("."))
        if self.unit:
            parts.append(self.unit)
        parts.append(self.name)
        if self.original.notes:
            parts.append(f"({self.original.notes})")
        return " ".join(parts)


def calculate_scale_factor(
    original_servings: int | None,
    target_servings: int | None = None,
    multiplier: float | None = None,
) -> float:
    """
    Calculate the scaling factor for a recipe.

    Args:
        original_servings: Original recipe serving size
        target_servings: Desired serving size
        multiplier: Direct multiplier (e.g., 2.0 for double)

    Returns:
        Scale factor to multiply quantities by

    Raises:
        ValueError: If neither target_servings nor multiplier provided,
                   or if target_servings given without original_servings
    """
    if multiplier is not None:
        return multiplier

    if target_servings is not None:
        if original_servings is None:
            raise ValueError(
                "Cannot scale by servings: original serving size unknown. "
                "Use --scale multiplier instead, or specify original servings."
            )
        return target_servings / original_servings

    # Default: no scaling
    return 1.0


def scale_quantity(quantity: float | None, scale_factor: float) -> float | None:
    """
    Scale a quantity by the given factor.

    Args:
        quantity: Original quantity (can be None)
        scale_factor: Factor to multiply by

    Returns:
        Scaled quantity, or None if input was None
    """
    if quantity is None:
        return None
    return quantity * scale_factor


def round_to_practical(quantity: float, unit: str | None = None) -> float:
    """
    Round a quantity to a practical cooking measurement.

    Args:
        quantity: The scaled quantity
        unit: The unit of measurement (affects rounding logic)

    Returns:
        Rounded quantity
    """
    if quantity <= 0:
        return quantity

    # For countable items, round up to whole numbers
    countable_units = {
        "piece",
        "pieces",
        "pcs",
        "stk",
        "styk",
        "clove",
        "cloves",
        "fed",
        "can",
        "cans",
        "package",
        "packages",
        "pkg",
        "bottle",
        "bottles",
        "head",
        "heads",
        "slice",
        "slices",
        "bunch",
        "bunches",
        "bag",
        "bags",
        "stalk",
        "stalks",
        "sprig",
        "sprigs",
    }

    if unit and unit.lower() in countable_units:
        return math.ceil(quantity)

    # For small quantities, keep more precision
    if quantity < 1:
        # Round to nearest quarter
        return round(quantity * 4) / 4

    # For medium quantities, round to nearest half
    if quantity < 10:
        return round(quantity * 2) / 2

    # For larger quantities, round to whole numbers
    return round(quantity)


def scale_ingredient(
    ingredient: Ingredient, scale_factor: float, round_practical: bool = True
) -> ScaledIngredient:
    """
    Scale a single ingredient.

    Args:
        ingredient: The ingredient to scale
        scale_factor: Factor to multiply quantity by
        round_practical: Whether to round to practical measurements

    Returns:
        ScaledIngredient with new quantity
    """
    scaled_qty = scale_quantity(ingredient.quantity, scale_factor)

    if round_practical and scaled_qty is not None:
        scaled_qty = round_to_practical(scaled_qty, ingredient.unit)

    return ScaledIngredient(
        original=ingredient, scaled_quantity=scaled_qty, scale_factor=scale_factor
    )


def scale_recipe(
    recipe: Recipe,
    target_servings: int | None = None,
    multiplier: float | None = None,
    round_practical: bool = True,
) -> tuple[list[ScaledIngredient], float, int | None]:
    """
    Scale all ingredients in a recipe.

    Args:
        recipe: The recipe to scale
        target_servings: Desired serving size
        multiplier: Direct multiplier (overrides target_servings)
        round_practical: Whether to round to practical measurements

    Returns:
        Tuple of (scaled_ingredients, scale_factor, new_servings)
    """
    scale_factor = calculate_scale_factor(recipe.servings, target_servings, multiplier)

    scaled_ingredients = [
        scale_ingredient(ing, scale_factor, round_practical) for ing in recipe.ingredients
    ]

    # Calculate new servings
    new_servings = None
    if recipe.servings is not None:
        new_servings = round(recipe.servings * scale_factor)
    elif target_servings is not None:
        new_servings = target_servings

    return scaled_ingredients, scale_factor, new_servings


def calculate_product_quantity(
    scaled_quantity: float | None, product_unit_size: str | None = None
) -> int:
    """
    Calculate how many product units to buy for a scaled ingredient.

    Args:
        scaled_quantity: The scaled ingredient quantity needed
        product_unit_size: The product's unit size (e.g., "500g", "1L")

    Returns:
        Number of product units to purchase (minimum 1)
    """
    if scaled_quantity is None:
        return 1

    # For now, simple ceiling - could be enhanced to parse product_unit_size
    # and calculate based on actual package sizes
    return max(1, math.ceil(scaled_quantity))


def format_scale_info(
    scale_factor: float, original_servings: int | None, new_servings: int | None
) -> str:
    """
    Format scaling information for display.

    Args:
        scale_factor: The scaling factor used
        original_servings: Original serving size
        new_servings: New serving size after scaling

    Returns:
        Human-readable scaling description
    """
    if scale_factor == 1.0:
        if original_servings:
            return f"Original recipe ({original_servings} servings)"
        return "Original recipe"

    if scale_factor == 2.0:
        desc = "Doubled"
    elif scale_factor == 0.5:
        desc = "Halved"
    elif scale_factor == 3.0:
        desc = "Tripled"
    else:
        desc = f"Scaled {scale_factor:.2g}x"

    if original_servings and new_servings:
        return f"{desc} ({original_servings} → {new_servings} servings)"
    elif new_servings:
        return f"{desc} ({new_servings} servings)"

    return desc
