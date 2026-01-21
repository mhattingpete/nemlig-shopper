"""Recipe URL and text parsing module."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

try:
    from recipe_scrapers import scrape_me
    from recipe_scrapers._exceptions import WebsiteNotImplementedError

    SCRAPERS_AVAILABLE = True
except ImportError:
    SCRAPERS_AVAILABLE = False
    scrape_me = None  # type: ignore[assignment]
    WebsiteNotImplementedError = Exception  # type: ignore[misc,assignment]

try:
    import httpx
    from bs4 import BeautifulSoup

    WEB_SCRAPING_AVAILABLE = True
except ImportError:
    WEB_SCRAPING_AVAILABLE = False


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


def _extract_json_ld_recipe(soup: "BeautifulSoup") -> dict[str, Any] | None:
    """Extract recipe data from JSON-LD script tags."""
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")

            # Handle both single object and array formats
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        return item
            elif data.get("@type") == "Recipe":
                return data
            elif "@graph" in data:
                for item in data["@graph"]:
                    if item.get("@type") == "Recipe":
                        return item
        except (json.JSONDecodeError, TypeError):
            continue

    return None


def _extract_nuxt3_payload(soup: "BeautifulSoup") -> list[Ingredient] | None:
    """Extract ingredients from Nuxt 3 __NUXT_DATA__ payload.

    Nuxt 3 stores data as a JSON array where objects use numeric indices
    as references to other array elements. This function resolves those
    references to extract ingredient data.
    """
    import json

    nuxt_script = soup.find("script", id="__NUXT_DATA__")
    if not nuxt_script or not nuxt_script.string:
        return None

    try:
        data = json.loads(nuxt_script.string)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list):
        return None

    def resolve(idx: int | str | dict | list) -> Any:
        """Resolve a Nuxt 3 payload reference."""
        if isinstance(idx, int) and 0 <= idx < len(data):
            val = data[idx]
            if isinstance(val, dict):
                return {k: resolve(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [resolve(item) for item in val]
            return val
        elif isinstance(idx, dict):
            return {k: resolve(v) for k, v in idx.items()}
        elif isinstance(idx, list):
            return [resolve(item) for item in idx]
        return idx

    # Find ingredient objects (dicts with 'ingredient' key pointing to an index)
    ingredients: list[Ingredient] = []
    seen_names: set[str] = set()

    for item in data:
        if isinstance(item, dict) and "ingredient" in item and "amountOfContent" in item:
            try:
                name = resolve(item["ingredient"])
                amount = resolve(item.get("amountOfContent"))
                unit = resolve(item.get("unitOfContent"))

                if isinstance(name, str) and name and name.lower() not in seen_names:
                    seen_names.add(name.lower())

                    # Build original string
                    parts = []
                    if amount and amount != 0:
                        parts.append(str(amount))
                    if unit:
                        parts.append(str(unit))
                    parts.append(name)
                    original = " ".join(parts)

                    ingredients.append(
                        Ingredient(
                            original=original,
                            name=name,
                            quantity=float(amount) if amount else None,
                            unit=str(unit) if unit else None,
                        )
                    )
            except (TypeError, ValueError, IndexError):
                continue

    return ingredients if ingredients else None


def _extract_nuxt_data(soup: "BeautifulSoup") -> dict[str, Any] | None:
    """Extract recipe data from Nuxt.js __NUXT_DATA__ or similar."""
    import json

    # Look for Nuxt data script
    for script in soup.find_all("script"):
        script_text = script.string or ""
        if "__NUXT__" in script_text or "window.__NUXT__" in script_text:
            # Try to extract JSON from the script
            match = re.search(r"window\.__NUXT__\s*=\s*({.+?});?\s*$", script_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

    # Look for embedded JSON with recipe data
    for script in soup.find_all("script"):
        script_text = script.string or ""
        if "ingredientGroups" in script_text or "recipeIngredient" in script_text:
            # Try to find JSON object containing recipe
            try:
                # Find JSON-like structures
                for match in re.finditer(r'\{[^{}]*"ingredientGroups"[^{}]*\}', script_text):
                    data = json.loads(match.group(0))
                    if "ingredientGroups" in data:
                        return data
            except (json.JSONDecodeError, TypeError):
                pass

    return None


def _scrape_recipe_fallback(url: str) -> Recipe:
    """
    Fallback scraper for websites not supported by recipe-scrapers.

    Uses BeautifulSoup to extract recipe data from HTML.
    Supports JSON-LD, microdata, and common HTML patterns.
    """
    if not WEB_SCRAPING_AVAILABLE:
        raise ImportError(
            "httpx and beautifulsoup4 are required for fallback scraping. "
            "Install with: pip install httpx beautifulsoup4"
        )

    # Fetch the page
    response = httpx.get(url, follow_redirects=True, timeout=30.0)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try to extract from JSON-LD first (most reliable)
    json_ld = _extract_json_ld_recipe(soup)
    if json_ld:
        title = json_ld.get("name", "Unknown Recipe")

        # Parse servings
        servings = None
        recipe_yield = json_ld.get("recipeYield")
        if recipe_yield:
            if isinstance(recipe_yield, list):
                recipe_yield = recipe_yield[0]
            match = re.search(r"(\d+)", str(recipe_yield))
            if match:
                servings = int(match.group(1))

        # Parse ingredients
        raw_ingredients = json_ld.get("recipeIngredient", [])
        if isinstance(raw_ingredients, str):
            raw_ingredients = [raw_ingredients]

        ingredients = [parse_ingredient_text(ing) for ing in raw_ingredients]

        return Recipe(title=title, ingredients=ingredients, servings=servings, source_url=url)

    # Try Nuxt 3 payload extraction (sites like Rema1000)
    nuxt3_ingredients = _extract_nuxt3_payload(soup)
    if nuxt3_ingredients:
        # Extract title from page
        title = None
        for selector in ["h1", ".recipe-title", ".entry-title", "[itemprop='name']"]:
            elem = soup.select_one(selector)
            if elem and elem.get_text(strip=True):
                title = elem.get_text(strip=True)
                break
        if not title:
            title = "Unknown Recipe"

        # Try to find servings
        servings = None
        for text in soup.stripped_strings:
            if any(word in text.lower() for word in ["personer", "servings", "portioner"]):
                match = re.search(r"(\d+)", text)
                if match:
                    servings = int(match.group(1))
                    break

        return Recipe(title=title, ingredients=nuxt3_ingredients, servings=servings, source_url=url)

    # Extract title - try various common patterns
    title = None
    for selector in ["h1", ".recipe-title", ".entry-title", "[itemprop='name']"]:
        elem = soup.select_one(selector)
        if elem and elem.get_text(strip=True):
            title = elem.get_text(strip=True)
            break
    if not title:
        title = "Unknown Recipe"

    # Extract servings
    servings = None
    for selector in [
        "[itemprop='recipeYield']",
        ".servings",
        ".yield",
        ".recipe-servings",
    ]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            match = re.search(r"(\d+)", text)
            if match:
                servings = int(match.group(1))
                break

    # Also try to find servings in text patterns
    if not servings:
        for text in soup.stripped_strings:
            if any(word in text.lower() for word in ["personer", "servings", "portioner"]):
                match = re.search(r"(\d+)", text)
                if match:
                    servings = int(match.group(1))
                    break

    # Extract ingredients - try various common patterns
    raw_ingredients: list[str] = []

    # Method 1: Schema.org markup (microdata)
    for elem in soup.select("[itemprop='recipeIngredient'], [itemprop='ingredients']"):
        text = elem.get_text(strip=True)
        if text:
            raw_ingredients.append(text)

    # Method 2: Common ingredient list classes
    if not raw_ingredients:
        for selector in [
            ".ingredients li",
            ".recipe-ingredients li",
            ".ingredient-list li",
            ".wprm-recipe-ingredient",
            "[class*='ingredient'] li",
        ]:
            elems = soup.select(selector)
            if elems:
                for elem in elems:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 2:
                        raw_ingredients.append(text)
                break

    # Method 3: Look for lists after "Ingredienser" heading
    if not raw_ingredients:
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            heading_text = heading.get_text(strip=True).lower()
            if "ingrediens" in heading_text or "ingredient" in heading_text:
                # Find the next list
                next_elem = heading.find_next(["ul", "ol"])
                if next_elem:
                    for li in next_elem.find_all("li"):
                        text = li.get_text(strip=True)
                        if text:
                            raw_ingredients.append(text)
                break

    # Filter out section headers and recipe names
    filtered_ingredients = []
    skip_patterns = ["tilbehør", "dressing", "sauce", "marinade", "topping"]
    for ing in raw_ingredients:
        ing_lower = ing.lower().strip()
        # Skip if it looks like a section header (single word, no numbers)
        if not any(c.isdigit() for c in ing) and ing_lower in skip_patterns:
            continue
        # Skip if it's the recipe title
        if title and ing_lower == title.lower():
            continue
        filtered_ingredients.append(ing)

    # Parse ingredients
    ingredients = [parse_ingredient_text(ing) for ing in filtered_ingredients]

    return Recipe(title=title, ingredients=ingredients, servings=servings, source_url=url)


def parse_recipe_url(url: str) -> Recipe:
    """
    Parse a recipe from a URL using recipe-scrapers.

    Falls back to custom scraping for unsupported websites.

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

    try:
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

        return Recipe(
            title=scraper.title(), ingredients=ingredients, servings=servings, source_url=url
        )

    except WebsiteNotImplementedError:
        # Fall back to custom scraping for unsupported sites
        return _scrape_recipe_fallback(url)


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
