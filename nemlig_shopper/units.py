"""Unit parsing and conversion utilities for package quantity calculations."""

import math
import re
from dataclasses import dataclass
from typing import Literal

UnitType = Literal["weight", "volume", "count", "unknown"]


@dataclass
class ParsedUnit:
    """Parsed unit size from product description."""

    value: float
    unit: str
    unit_type: UnitType
    original: str


# Unit conversions to base units (grams for weight, milliliters for volume, pieces for count)
UNIT_INFO: dict[str, tuple[float, str, UnitType]] = {
    # Weight -> grams
    "g": (1.0, "g", "weight"),
    "gram": (1.0, "g", "weight"),
    "gr": (1.0, "g", "weight"),
    "kg": (1000.0, "g", "weight"),
    "kilo": (1000.0, "g", "weight"),
    # Volume -> milliliters
    "ml": (1.0, "ml", "volume"),
    "cl": (10.0, "ml", "volume"),
    "dl": (100.0, "ml", "volume"),
    "l": (1000.0, "ml", "volume"),
    "liter": (1000.0, "ml", "volume"),
    "litre": (1000.0, "ml", "volume"),
    # Count -> pieces
    "stk": (1.0, "stk", "count"),
    "styk": (1.0, "stk", "count"),
    "pk": (1.0, "pk", "count"),
    "pakke": (1.0, "pk", "count"),
    "pack": (1.0, "pk", "count"),
    "piece": (1.0, "stk", "count"),
    "pieces": (1.0, "stk", "count"),
    "pcs": (1.0, "stk", "count"),
    # Danish specific
    "fed": (1.0, "stk", "count"),  # cloves (garlic)
    "bundt": (1.0, "stk", "count"),  # bunch
    "håndfuld": (1.0, "stk", "count"),  # handful
}

# Recipe unit aliases (maps recipe units to standard units)
RECIPE_UNIT_ALIASES: dict[str, str] = {
    "cups": "cup",
    "cup": "cup",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsp": "tbsp",
    "tbs": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsk": "tsp",
    "tsp": "tsp",
    "spsk": "tbsp",
}


def get_unit_type(unit: str | None) -> UnitType:
    """Get the type of a unit (weight, volume, count, or unknown)."""
    if unit is None:
        return "unknown"

    unit_lower = unit.lower().strip()

    # Check direct match
    if unit_lower in UNIT_INFO:
        return UNIT_INFO[unit_lower][2]

    # Check aliases
    if unit_lower in RECIPE_UNIT_ALIASES:
        return "volume"  # Most recipe units are volume

    return "unknown"


def normalize_to_base(value: float, unit: str) -> tuple[float, str, UnitType]:
    """
    Convert a value to base units (g, ml, or stk).

    Args:
        value: The numeric value
        unit: The unit string

    Returns:
        Tuple of (converted_value, base_unit, unit_type)
    """
    unit_lower = unit.lower().strip()

    if unit_lower in UNIT_INFO:
        multiplier, base_unit, unit_type = UNIT_INFO[unit_lower]
        return value * multiplier, base_unit, unit_type

    # Unknown unit - return as-is
    return value, unit, "unknown"


def parse_unit_size(unit_size: str | None) -> ParsedUnit | None:
    """
    Parse a product unit size string.

    Examples:
        "500g" -> ParsedUnit(500, "g", "weight", "500g")
        "1L" -> ParsedUnit(1000, "ml", "volume", "1L")
        "6 stk" -> ParsedUnit(6, "stk", "count", "6 stk")
        "ca. 400g" -> ParsedUnit(400, "g", "weight", "ca. 400g")
        "1 kg" -> ParsedUnit(1000, "g", "weight", "1 kg")

    Returns:
        ParsedUnit or None if parsing fails
    """
    if not unit_size:
        return None

    original = unit_size.strip()
    text = original.lower()

    # Remove common prefixes
    text = re.sub(r"^(ca\.?|cirka|approximately|approx\.?|~)\s*", "", text)

    # Pattern: number (with optional decimal) followed by unit
    # Handles: "500g", "1.5kg", "1,5 l", "6 stk", "500 g"
    pattern = r"(\d+(?:[.,]\d+)?)\s*([a-zæøå]+)"
    match = re.search(pattern, text)

    if not match:
        return None

    # Parse the number (handle both . and , as decimal)
    num_str = match.group(1).replace(",", ".")
    try:
        value = float(num_str)
    except ValueError:
        return None

    unit = match.group(2)

    # Normalize to base units
    normalized_value, base_unit, unit_type = normalize_to_base(value, unit)

    return ParsedUnit(
        value=normalized_value,
        unit=base_unit,
        unit_type=unit_type,
        original=original,
    )


def can_convert(from_unit: str | None, to_unit: str | None) -> bool:
    """
    Check if two units can be converted (same type).

    Args:
        from_unit: Source unit
        to_unit: Target unit

    Returns:
        True if units are compatible for conversion
    """
    from_type = get_unit_type(from_unit)
    to_type = get_unit_type(to_unit)

    # Unknown types can't be converted
    if from_type == "unknown" or to_type == "unknown":
        return False

    return from_type == to_type


def calculate_packages_needed(
    needed_quantity: float | None,
    needed_unit: str | None,
    package_size: str | None,
) -> int:
    """
    Calculate number of packages needed to fulfill an ingredient requirement.

    Args:
        needed_quantity: Amount needed (e.g., 750)
        needed_unit: Unit of needed amount (e.g., "g")
        package_size: Product unit_size string (e.g., "500g")

    Returns:
        Number of packages to buy (minimum 1), or 0 if calculation not possible
    """
    if needed_quantity is None or needed_quantity <= 0:
        return 1

    # Parse the package size
    parsed_package = parse_unit_size(package_size)
    if parsed_package is None:
        return 0  # Signal to use fallback

    # Normalize the needed quantity to base units
    if needed_unit:
        needed_base, _, needed_type = normalize_to_base(needed_quantity, needed_unit)
    else:
        # No unit specified - assume it's already in the right unit or countable
        needed_base = needed_quantity
        needed_type = "unknown"

    # Check if units are compatible
    if needed_type != "unknown" and parsed_package.unit_type != "unknown":
        if needed_type != parsed_package.unit_type:
            # Incompatible units (e.g., grams vs liters)
            return 0  # Signal to use fallback

    # Calculate packages needed
    if parsed_package.value <= 0:
        return 1

    packages = math.ceil(needed_base / parsed_package.value)
    return max(1, packages)


def format_quantity_explanation(
    needed_quantity: float | None,
    needed_unit: str | None,
    package_size: str | None,
    packages_needed: int,
) -> str:
    """
    Format a human-readable explanation of the quantity calculation.

    Args:
        needed_quantity: Amount needed
        needed_unit: Unit of needed amount
        package_size: Product unit_size string
        packages_needed: Calculated number of packages

    Returns:
        Explanation string (e.g., "Need 750g, package is 500g → 2 packages")
    """
    if needed_quantity is None:
        return f"{packages_needed} package(s)"

    qty_str = (
        f"{needed_quantity:.0f}"
        if needed_quantity == int(needed_quantity)
        else f"{needed_quantity:.1f}"
    )
    unit_str = f" {needed_unit}" if needed_unit else ""

    if package_size:
        return f"Need {qty_str}{unit_str}, package is {package_size} → {packages_needed}"

    return f"Need {qty_str}{unit_str} → {packages_needed} package(s)"
