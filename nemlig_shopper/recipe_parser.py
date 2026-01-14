"""Recipe URL and text parsing module."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

try:
    from recipe_scrapers import scrape_me

    SCRAPERS_AVAILABLE = True
except ImportError:
    SCRAPERS_AVAILABLE = False
    scrape_me = None  # type: ignore[assignment]


@dataclass
class Ingredient:
    """Represents a parsed ingredient."""

    original: str  # Original text
    name: str  # Extracted ingredient name
    quantity: float | None = None
    unit: str | None = None
    notes: str | None = None  # e.g., "finely chopped"

    def __str__(self) -> str:
        parts = []
        if self.quantity:
            parts.append(str(self.quantity))
        if self.unit:
            parts.append(self.unit)
        parts.append(self.name)
        if self.notes:
            parts.append(f"({self.notes})")
        return " ".join(parts)


@dataclass
class Recipe:
    """Represents a parsed recipe."""

    title: str
    ingredients: list[Ingredient] = field(default_factory=list)
    servings: int | None = None
    source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert recipe to dictionary for serialization."""
        return {
            "title": self.title,
            "servings": self.servings,
            "source_url": self.source_url,
            "ingredients": [
                {
                    "original": ing.original,
                    "name": ing.name,
                    "quantity": ing.quantity,
                    "unit": ing.unit,
                    "notes": ing.notes,
                }
                for ing in self.ingredients
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recipe":
        """Create recipe from dictionary."""
        ingredients = [
            Ingredient(
                original=ing["original"],
                name=ing["name"],
                quantity=ing.get("quantity"),
                unit=ing.get("unit"),
                notes=ing.get("notes"),
            )
            for ing in data.get("ingredients", [])
        ]
        return cls(
            title=data["title"],
            servings=data.get("servings"),
            source_url=data.get("source_url"),
            ingredients=ingredients,
        )


# Common units for parsing
UNITS = {
    # Volume
    "cup",
    "cups",
    "c",
    "tablespoon",
    "tablespoons",
    "tbsp",
    "tbs",
    "tb",
    "teaspoon",
    "teaspoons",
    "tsp",
    "ts",
    "ml",
    "milliliter",
    "milliliters",
    "l",
    "liter",
    "liters",
    "litre",
    "litres",
    "dl",
    "deciliter",
    "deciliters",
    "fl oz",
    "fluid ounce",
    "fluid ounces",
    # Weight
    "g",
    "gram",
    "grams",
    "kg",
    "kilogram",
    "kilograms",
    "oz",
    "ounce",
    "ounces",
    "lb",
    "lbs",
    "pound",
    "pounds",
    # Count
    "piece",
    "pieces",
    "pcs",
    "clove",
    "cloves",
    "slice",
    "slices",
    "bunch",
    "bunches",
    "can",
    "cans",
    "package",
    "packages",
    "pkg",
    "bag",
    "bags",
    "bottle",
    "bottles",
    "head",
    "heads",
    "stalk",
    "stalks",
    "sprig",
    "sprigs",
    # Danish units
    "stk",
    "styk",
    "spsk",
    "spiseskefuld",
    "tsk",
    "teskefuld",
    "fed",
}

# Fraction to decimal mapping
FRACTIONS = {
    "½": 0.5,
    "⅓": 0.333,
    "⅔": 0.667,
    "¼": 0.25,
    "¾": 0.75,
    "⅕": 0.2,
    "⅖": 0.4,
    "⅗": 0.6,
    "⅘": 0.8,
    "⅙": 0.167,
    "⅚": 0.833,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
    "1/2": 0.5,
    "1/3": 0.333,
    "2/3": 0.667,
    "1/4": 0.25,
    "3/4": 0.75,
    "1/8": 0.125,
}


def parse_quantity(text: str) -> tuple[float | None, str]:
    """
    Parse quantity from the beginning of an ingredient string.

    Handles both period (.) and comma (,) as decimal separators
    to support both English and Danish/European number formats.

    Returns:
        Tuple of (quantity, remaining_text)
    """
    text = text.strip()

    # Check for unicode fractions first
    for frac, value in FRACTIONS.items():
        if text.startswith(frac):
            remaining = text[len(frac) :].strip()
            # Check for mixed number (e.g., "1½")
            return value, remaining

    # Match patterns like "1", "1.5", "1,5" (Danish), "1 1/2", "1-2" (range)
    # Note: [\.,] matches both period and comma as decimal separator
    pattern = r"^(\d+(?:[\.,]\d+)?(?:\s*[-–]\s*\d+(?:[\.,]\d+)?)?(?:\s+\d+/\d+)?|\d+/\d+)"
    match = re.match(pattern, text)

    if match:
        qty_str = match.group(1)
        remaining = text[match.end() :].strip()

        # Normalize decimal separator (Danish uses comma)
        qty_str_normalized = qty_str.replace(",", ".")

        # Handle ranges (take the higher value)
        if "-" in qty_str_normalized or "–" in qty_str_normalized:
            parts = re.split(r"[-–]", qty_str_normalized)
            try:
                return float(parts[-1].strip()), remaining
            except ValueError:
                pass

        # Handle mixed numbers like "1 1/2"
        if " " in qty_str_normalized and "/" in qty_str_normalized:
            parts = qty_str_normalized.split()
            try:
                whole = float(parts[0])
                frac_parts = parts[1].split("/")
                frac = float(frac_parts[0]) / float(frac_parts[1])
                return whole + frac, remaining
            except (ValueError, IndexError, ZeroDivisionError):
                pass

        # Handle simple fractions like "1/2"
        if "/" in qty_str_normalized:
            try:
                parts = qty_str_normalized.split("/")
                return float(parts[0]) / float(parts[1]), remaining
            except (ValueError, ZeroDivisionError):
                pass

        # Simple number
        try:
            return float(qty_str_normalized), remaining
        except ValueError:
            pass

    return None, text


def parse_unit(text: str) -> tuple[str | None, str]:
    """
    Parse unit from the beginning of text.

    Returns:
        Tuple of (unit, remaining_text)
    """
    text = text.strip()
    words = text.split()

    if not words:
        return None, text

    # Check for two-word units first (e.g., "fl oz", "fluid ounce")
    if len(words) >= 2:
        two_word = f"{words[0]} {words[1]}".lower()
        if two_word in UNITS:
            return two_word, " ".join(words[2:])

    # Check single word
    first_word = words[0].lower().rstrip(",.")
    if first_word in UNITS:
        return first_word, " ".join(words[1:])

    return None, text


def parse_ingredient_text(text: str) -> Ingredient:
    """
    Parse a single ingredient line into structured data.

    Args:
        text: Raw ingredient text (e.g., "2 cups flour, sifted")

    Returns:
        Ingredient object with parsed data
    """
    original = text.strip()

    # Parse quantity
    quantity, remaining = parse_quantity(original)

    # Parse unit
    unit, remaining = parse_unit(remaining)

    # Extract notes (usually in parentheses or after comma)
    notes = None
    name = remaining

    # Check for parenthetical notes
    paren_match = re.search(r"\(([^)]+)\)", remaining)
    if paren_match:
        notes = paren_match.group(1)
        name = remaining[: paren_match.start()] + remaining[paren_match.end() :]

    # Check for comma-separated notes
    if "," in name:
        parts = name.split(",", 1)
        name = parts[0].strip()
        note_part = parts[1].strip()
        if notes:
            notes = f"{notes}, {note_part}"
        else:
            notes = note_part

    # Clean up name
    name = name.strip().rstrip(",.")
    name = re.sub(r"\s+", " ", name)  # Normalize whitespace

    return Ingredient(original=original, name=name, quantity=quantity, unit=unit, notes=notes)


def parse_ingredients_text(text: str) -> list[Ingredient]:
    """
    Parse multiple ingredients from text (one per line).

    Args:
        text: Multi-line text with ingredients

    Returns:
        List of Ingredient objects
    """
    ingredients = []

    for line in text.strip().split("\n"):
        line = line.strip()
        # Skip empty lines and headers
        if not line or line.lower().startswith(("ingredients", "for the", "---")):
            continue
        # Skip bullet points and numbers at start
        line = re.sub(r"^[\-\*•]\s*", "", line)
        line = re.sub(r"^\d+\.\s*", "", line)

        if line:
            ingredients.append(parse_ingredient_text(line))

    return ingredients


def parse_recipe_url(url: str) -> Recipe:
    """
    Parse a recipe from a URL using recipe-scrapers.

    Args:
        url: URL to a recipe page

    Returns:
        Recipe object with parsed data

    Raises:
        ImportError: If recipe-scrapers is not installed
        Exception: If scraping fails
    """
    if not SCRAPERS_AVAILABLE or scrape_me is None:
        raise ImportError(
            "recipe-scrapers package is required for URL parsing. "
            "Install with: pip install recipe-scrapers"
        )

    scraper = scrape_me(url)

    # Parse ingredients
    raw_ingredients = scraper.ingredients()
    ingredients = [parse_ingredient_text(ing) for ing in raw_ingredients]

    # Parse servings
    servings = None
    try:
        servings_str = scraper.yields()
        if servings_str:
            # Extract number from string like "4 servings"
            match = re.search(r"(\d+)", servings_str)
            if match:
                servings = int(match.group(1))
    except Exception:
        pass

    return Recipe(title=scraper.title(), ingredients=ingredients, servings=servings, source_url=url)


def parse_recipe_text(title: str, ingredients_text: str, servings: int | None = None) -> Recipe:
    """
    Create a recipe from manual text input.

    Args:
        title: Recipe name
        ingredients_text: Multi-line ingredient list
        servings: Optional serving size

    Returns:
        Recipe object
    """
    ingredients = parse_ingredients_text(ingredients_text)

    return Recipe(title=title, ingredients=ingredients, servings=servings, source_url=None)
