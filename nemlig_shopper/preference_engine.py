"""Dietary preference and allergy safety checking for product matching.

This module provides functions to check if products are safe for users
with specific dietary restrictions or allergies. It uses keyword matching
against product names and descriptions in both Danish and English.
"""

from dataclasses import dataclass, field
from typing import Any

# Allergy keywords in Danish and English
# Maps allergy type to list of keywords that indicate the allergen
ALLERGY_KEYWORDS: dict[str, list[str]] = {
    "nuts": [
        "nød",
        "nødder",
        "mandel",
        "mandler",
        "hasselnød",
        "hasselnødder",
        "valnød",
        "valnødder",
        "cashew",
        "pistacie",
        "peanut",
        "peanuts",
        "jordnød",
        "jordnødder",
        "peanøl",  # peanut oil
        "mandelolie",  # almond oil
        "nut",
        "almond",
        "walnut",
        "hazelnut",
        "pecan",
        "macadamia",
    ],
    "gluten": [
        "hvede",
        "rug",
        "byg",
        "havre",  # oats (often cross-contaminated)
        "gluten",
        "wheat",
        "rye",
        "barley",
        "oat",
        "seitan",
        "bulgur",
        "couscous",
        "semolina",
        "semulje",
    ],
    "dairy": [
        "mælk",
        "fløde",
        "ost",
        "smør",
        "yoghurt",
        "skyr",
        "creme fraiche",
        "cremefraiche",
        "mascarpone",
        "ricotta",
        "mozzarella",
        "parmesan",
        "feta",
        "milk",
        "cream",
        "cheese",
        "butter",
        "yogurt",
        "whey",
        "casein",
        "valle",
        "kasein",
    ],
    "lactose": [
        "laktose",
        "mælk",
        "fløde",
        "lactose",
        "milk",
        "cream",
        # Note: many dairy products can be lactose-free, but we flag them for review
    ],
    "shellfish": [
        "rejer",
        "reje",
        "hummer",
        "krabbe",
        "krabber",
        "musling",
        "muslinger",
        "østers",
        "shrimp",
        "prawn",
        "prawns",
        "lobster",
        "crab",
        "mussel",
        "mussels",
        "oyster",
        "scallop",
        "clam",
        "crayfish",
    ],
    "fish": [
        "fisk",
        "laks",
        "torsk",
        "tun",
        "makrel",
        "sild",
        "ål",
        "rødspætte",
        "fish",
        "salmon",
        "cod",
        "tuna",
        "mackerel",
        "herring",
        "anchovy",
        "ansjovs",
        "sardine",
        "sardin",
    ],
    "eggs": [
        "æg",
        "æggehvide",
        "æggeblomme",
        "egg",
        "eggs",
        "albumin",
        "mayonnaise",
        "mayo",
    ],
    "soy": [
        "soja",
        "soy",
        "tofu",
        "edamame",
        "miso",
        "tempeh",
        "sojasauce",
        "soy sauce",
    ],
    "sesame": [
        "sesam",
        "sesame",
        "tahini",
    ],
    "celery": [
        "selleri",
        "celery",
        "celeriac",
        "knoldselleri",
    ],
    "mustard": [
        "sennep",
        "mustard",
    ],
}

# Dietary restriction keywords
# Maps dietary type to keywords that indicate a product DOES contain restricted items
DIETARY_RESTRICTION_KEYWORDS: dict[str, list[str]] = {
    "vegetarian": [
        # Meat keywords - products with these are NOT vegetarian
        "kød",
        "oksekød",
        "svinekød",
        "kylling",
        "kalkun",
        "and",
        "gås",
        "lam",
        "vildt",
        "bacon",
        "skinke",
        "pølse",
        "leverpostej",
        "paté",
        "meat",
        "beef",
        "pork",
        "chicken",
        "turkey",
        "duck",
        "lamb",
        "ham",
        "sausage",
        "salami",
        "pepperoni",
        "fisk",
        "fish",
        "rejer",
        "shrimp",
        "laks",
        "salmon",
        "gelatin",  # Often animal-derived
        "gelatine",
    ],
    "vegan": [
        # All vegetarian restrictions plus dairy/eggs/honey
        "kød",
        "oksekød",
        "svinekød",
        "kylling",
        "bacon",
        "skinke",
        "pølse",
        "meat",
        "beef",
        "pork",
        "chicken",
        "fisk",
        "fish",
        "mælk",
        "milk",
        "fløde",
        "cream",
        "ost",
        "cheese",
        "smør",
        "butter",
        "æg",
        "egg",
        "honning",
        "honey",
        "yoghurt",
        "yogurt",
        "skyr",
        "gelatin",
    ],
    "pescatarian": [
        # Meat but NOT fish
        "kød",
        "oksekød",
        "svinekød",
        "kylling",
        "bacon",
        "skinke",
        "pølse",
        "meat",
        "beef",
        "pork",
        "chicken",
        "turkey",
        "ham",
        "sausage",
    ],
}

# Positive indicators that a product IS safe for a dietary restriction
DIETARY_SAFE_INDICATORS: dict[str, list[str]] = {
    "vegetarian": ["vegetar", "vegetarian", "veggie", "plantebaseret", "plant-based"],
    "vegan": ["vegan", "vegansk", "plantebaseret", "plant-based"],
    "gluten-free": ["glutenfri", "gluten-free", "gluten free"],
    "lactose-free": ["laktosefri", "lactose-free", "lactose free"],
}


@dataclass
class SafetyCheckResult:
    """Result of checking a product for allergen/dietary safety."""

    is_safe: bool
    allergens_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    product_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_safe": self.is_safe,
            "allergens_found": self.allergens_found,
            "warnings": self.warnings,
            "product_name": self.product_name,
        }


@dataclass
class DietaryCheckResult:
    """Result of checking a product for dietary compatibility."""

    is_compatible: bool
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    product_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_compatible": self.is_compatible,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "product_name": self.product_name,
        }


def _get_product_text(product: dict[str, Any]) -> str:
    """Extract searchable text from a product dict."""
    parts = [
        product.get("name", ""),
        product.get("description", ""),
        product.get("category", ""),
        product.get("subcategory", ""),
    ]
    return " ".join(str(p).lower() for p in parts if p)


def check_allergy_safety(
    product: dict[str, Any],
    allergens: list[str],
) -> SafetyCheckResult:
    """
    Check if a product is safe for users with specific allergies.

    Args:
        product: Product dict from Nemlig API
        allergens: List of allergy types to check (e.g., ["nuts", "dairy"])
                  Valid types: nuts, gluten, dairy, lactose, shellfish, fish,
                              eggs, soy, sesame, celery, mustard

    Returns:
        SafetyCheckResult with is_safe flag and any allergens found
    """
    product_text = _get_product_text(product)
    product_name = product.get("name", "Unknown")
    found_allergens: list[str] = []
    warnings: list[str] = []

    for allergen in allergens:
        allergen_lower = allergen.lower().strip()

        # Get keywords for this allergen type
        keywords = ALLERGY_KEYWORDS.get(allergen_lower, [allergen_lower])

        # Check if any keyword is in the product text
        for keyword in keywords:
            if keyword in product_text:
                found_allergens.append(f"{allergen}: '{keyword}'")
                break

    # Check for "may contain" style warnings (common in Danish)
    may_contain_patterns = [
        "kan indeholde",
        "spor af",
        "produceret i",
        "may contain",
        "traces of",
    ]
    for pattern in may_contain_patterns:
        if pattern in product_text:
            warnings.append(f"Product may contain allergen traces ('{pattern}' found)")
            break

    return SafetyCheckResult(
        is_safe=len(found_allergens) == 0,
        allergens_found=found_allergens,
        warnings=warnings,
        product_name=product_name,
    )


def check_dietary_compatibility(
    product: dict[str, Any],
    dietary_restrictions: list[str],
) -> DietaryCheckResult:
    """
    Check if a product is compatible with dietary restrictions.

    Args:
        product: Product dict from Nemlig API
        dietary_restrictions: List of dietary types (e.g., ["vegetarian", "vegan"])
                             Valid types: vegetarian, vegan, pescatarian

    Returns:
        DietaryCheckResult with is_compatible flag and any conflicts found
    """
    product_text = _get_product_text(product)
    product_name = product.get("name", "Unknown")
    conflicts: list[str] = []
    warnings: list[str] = []

    for restriction in dietary_restrictions:
        restriction_lower = restriction.lower().strip()

        # First check for positive indicators (e.g., "vegan" label)
        safe_indicators = DIETARY_SAFE_INDICATORS.get(restriction_lower, [])
        is_marked_safe = any(indicator in product_text for indicator in safe_indicators)

        if is_marked_safe:
            continue  # Product is explicitly marked as compatible

        # Check for restriction keywords (things that make it incompatible)
        restriction_keywords = DIETARY_RESTRICTION_KEYWORDS.get(restriction_lower, [])

        for keyword in restriction_keywords:
            if keyword in product_text:
                conflicts.append(f"{restriction}: contains '{keyword}'")
                break

    # Add warning if no clear indicators either way
    if not conflicts:
        any_safe_indicator = any(
            indicator in product_text
            for indicators in DIETARY_SAFE_INDICATORS.values()
            for indicator in indicators
        )
        if not any_safe_indicator:
            warnings.append("No dietary labels found - verify manually")

    return DietaryCheckResult(
        is_compatible=len(conflicts) == 0,
        conflicts=conflicts,
        warnings=warnings,
        product_name=product_name,
    )


def get_safe_alternative_query(
    ingredient_name: str,
    allergens: list[str] | None = None,
    dietary_restrictions: list[str] | None = None,
) -> str | None:
    """
    Generate a search query for finding a safe alternative product.

    Args:
        ingredient_name: The original ingredient name
        allergens: List of allergies to avoid
        dietary_restrictions: List of dietary restrictions

    Returns:
        Modified search query, or None if no modification needed
    """
    modifiers = []

    if allergens:
        for allergen in allergens:
            allergen_lower = allergen.lower()
            # Map allergens to product search modifiers
            if allergen_lower in ("lactose", "dairy"):
                modifiers.append("laktosefri")
            elif allergen_lower == "gluten":
                modifiers.append("glutenfri")

    if dietary_restrictions:
        for restriction in dietary_restrictions:
            restriction_lower = restriction.lower()
            if restriction_lower == "vegan":
                modifiers.append("vegansk")
            elif restriction_lower == "vegetarian":
                modifiers.append("vegetar")

    if modifiers:
        return f"{modifiers[0]} {ingredient_name}"

    return None
