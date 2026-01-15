"""Meal planning: parse multiple recipes and consolidate ingredients."""

from dataclasses import dataclass, field

from .recipe_parser import Recipe, parse_recipe_url
from .scaler import ScaledIngredient, scale_recipe
from .units import get_unit_type, normalize_to_base


@dataclass
class ConsolidatedIngredient:
    """An ingredient consolidated from multiple recipes."""

    name: str
    total_quantity: float | None
    unit: str | None
    sources: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = []
        if self.total_quantity is not None:
            qty = self.total_quantity
            if qty == int(qty):
                parts.append(str(int(qty)))
            else:
                parts.append(f"{qty:.2f}".rstrip("0").rstrip("."))
        if self.unit:
            parts.append(self.unit)
        parts.append(self.name)
        return " ".join(parts)


@dataclass
class MealPlan:
    """A meal plan containing multiple recipes."""

    recipes: list[Recipe]
    consolidated_ingredients: list[ConsolidatedIngredient]
    scale_factors: dict[str, float] = field(default_factory=dict)

    @property
    def recipe_count(self) -> int:
        return len(self.recipes)

    @property
    def ingredient_count(self) -> int:
        return len(self.consolidated_ingredients)


def normalize_ingredient_name(name: str) -> str:
    """
    Normalize ingredient name for grouping.

    Handles plurals, common variations, etc.
    """
    name = name.lower().strip()

    # Common plural → singular mappings
    plural_mappings = {
        "onions": "onion",
        "tomatoes": "tomato",
        "potatoes": "potato",
        "carrots": "carrot",
        "eggs": "egg",
        "cloves": "clove",
        "lemons": "lemon",
        "limes": "lime",
        "apples": "apple",
        "oranges": "orange",
        "bananas": "banana",
        "mushrooms": "mushroom",
        "peppers": "pepper",
        "shallots": "shallot",
        "løg": "løg",
        "æg": "æg",
        "gulerødder": "gulerod",
        "kartofler": "kartoffel",
        "tomater": "tomat",
        "citroner": "citron",
        "æbler": "æble",
    }

    for plural, singular in plural_mappings.items():
        if name == plural:
            return singular

    return name


def can_consolidate(unit1: str | None, unit2: str | None) -> bool:
    """Check if two units can be consolidated (same type)."""
    type1 = get_unit_type(unit1)
    type2 = get_unit_type(unit2)

    # Both unknown - can consolidate if both have no unit
    if type1 == "unknown" and type2 == "unknown":
        return unit1 == unit2

    # Same type can be consolidated
    return type1 == type2 and type1 != "unknown"


def consolidate_ingredients(
    scaled_ingredients: list[tuple[ScaledIngredient, str]],
) -> list[ConsolidatedIngredient]:
    """
    Consolidate ingredients from multiple recipes.

    Groups by normalized name and sums quantities where units are compatible.

    Args:
        scaled_ingredients: List of (ScaledIngredient, recipe_title) tuples

    Returns:
        List of consolidated ingredients
    """
    # Group by normalized name
    groups: dict[str, list[tuple[ScaledIngredient, str]]] = {}

    for ingredient, source in scaled_ingredients:
        key = normalize_ingredient_name(ingredient.name)
        if key not in groups:
            groups[key] = []
        groups[key].append((ingredient, source))

    consolidated: list[ConsolidatedIngredient] = []

    for _normalized_name, items in groups.items():
        # Try to consolidate all items in the group
        # Split into sub-groups by unit type
        unit_groups: dict[str, list[tuple[ScaledIngredient, str]]] = {}

        for ingredient, source in items:
            unit_type = get_unit_type(ingredient.unit)
            if unit_type not in unit_groups:
                unit_groups[unit_type] = []
            unit_groups[unit_type].append((ingredient, source))

        # Consolidate each unit type group
        for unit_type, unit_items in unit_groups.items():
            if unit_type == "unknown":
                # For unknown units, group by exact unit match
                exact_unit_groups: dict[str | None, list[tuple[ScaledIngredient, str]]] = {}
                for ing, src in unit_items:
                    u = ing.unit
                    if u not in exact_unit_groups:
                        exact_unit_groups[u] = []
                    exact_unit_groups[u].append((ing, src))

                for unit, exact_items in exact_unit_groups.items():
                    total_qty, sources = _sum_quantities(exact_items, unit)
                    # Use original name from first item
                    original_name = exact_items[0][0].name
                    consolidated.append(
                        ConsolidatedIngredient(
                            name=original_name,
                            total_quantity=total_qty,
                            unit=unit,
                            sources=sources,
                        )
                    )
            else:
                # For known units, normalize and sum
                total_qty, sources = _sum_quantities_normalized(unit_items, unit_type)
                # Use original name from first item
                original_name = unit_items[0][0].name
                # Determine best unit for display
                display_unit = _get_display_unit(total_qty, unit_type)
                display_qty = _convert_to_display_unit(total_qty, unit_type, display_unit)

                consolidated.append(
                    ConsolidatedIngredient(
                        name=original_name,
                        total_quantity=display_qty,
                        unit=display_unit,
                        sources=sources,
                    )
                )

    return consolidated


def _sum_quantities(
    items: list[tuple[ScaledIngredient, str]], unit: str | None
) -> tuple[float | None, list[str]]:
    """Sum quantities for items with the same unit."""
    total = 0.0
    sources = []
    has_quantity = False

    for ingredient, source in items:
        if ingredient.scaled_quantity is not None:
            total += ingredient.scaled_quantity
            has_quantity = True
        if source not in sources:
            sources.append(source)

    return (total if has_quantity else None), sources


def _sum_quantities_normalized(
    items: list[tuple[ScaledIngredient, str]], unit_type: str
) -> tuple[float | None, list[str]]:
    """Sum quantities after normalizing to base units."""
    total = 0.0
    sources = []
    has_quantity = False

    for ingredient, source in items:
        if ingredient.scaled_quantity is not None and ingredient.unit:
            # Normalize to base unit
            normalized, _, _ = normalize_to_base(ingredient.scaled_quantity, ingredient.unit)
            total += normalized
            has_quantity = True
        elif ingredient.scaled_quantity is not None:
            total += ingredient.scaled_quantity
            has_quantity = True

        if source not in sources:
            sources.append(source)

    return (total if has_quantity else None), sources


def _get_display_unit(quantity: float | None, unit_type: str) -> str:
    """Determine the best unit for displaying a quantity."""
    if quantity is None:
        if unit_type == "weight":
            return "g"
        elif unit_type == "volume":
            return "ml"
        return "stk"

    if unit_type == "weight":
        # Use kg for >= 1000g
        if quantity >= 1000:
            return "kg"
        return "g"
    elif unit_type == "volume":
        # Use L for >= 1000ml
        if quantity >= 1000:
            return "l"
        # Use dl for >= 100ml
        elif quantity >= 100:
            return "dl"
        return "ml"
    elif unit_type == "count":
        return "stk"

    return "stk"


def _convert_to_display_unit(
    quantity: float | None, unit_type: str, display_unit: str
) -> float | None:
    """Convert a base unit quantity to the display unit."""
    if quantity is None:
        return None

    if unit_type == "weight":
        if display_unit == "kg":
            return quantity / 1000
        return quantity  # Already in grams
    elif unit_type == "volume":
        if display_unit == "l":
            return quantity / 1000
        elif display_unit == "dl":
            return quantity / 100
        return quantity  # Already in ml

    return quantity


def parse_recipes(
    urls: list[str],
    scale_factors: dict[str, float] | None = None,
) -> tuple[list[Recipe], list[tuple[ScaledIngredient, str]]]:
    """
    Parse multiple recipes and collect all scaled ingredients.

    Args:
        urls: List of recipe URLs to parse
        scale_factors: Optional dict of URL -> scale factor

    Returns:
        Tuple of (recipes, [(scaled_ingredient, recipe_title), ...])
    """
    recipes: list[Recipe] = []
    all_ingredients: list[tuple[ScaledIngredient, str]] = []
    scale_factors = scale_factors or {}

    for url in urls:
        recipe = parse_recipe_url(url)
        recipes.append(recipe)

        # Get scale factor for this recipe
        factor = scale_factors.get(url, 1.0)

        # Scale ingredients
        scaled_ings, _, _ = scale_recipe(recipe, multiplier=factor)

        # Add to collection with source
        for ing in scaled_ings:
            all_ingredients.append((ing, recipe.title))

    return recipes, all_ingredients


def create_meal_plan(
    urls: list[str],
    scale_factors: dict[str, float] | None = None,
) -> MealPlan:
    """
    Create a meal plan from multiple recipe URLs.

    Args:
        urls: List of recipe URLs
        scale_factors: Optional dict of URL -> scale factor

    Returns:
        MealPlan with consolidated ingredients
    """
    recipes, all_ingredients = parse_recipes(urls, scale_factors)
    consolidated = consolidate_ingredients(all_ingredients)

    return MealPlan(
        recipes=recipes,
        consolidated_ingredients=consolidated,
        scale_factors=scale_factors or {},
    )


def load_urls_from_file(filepath: str) -> list[str]:
    """
    Load recipe URLs from a text file.

    Args:
        filepath: Path to file with one URL per line

    Returns:
        List of URLs
    """
    urls = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                urls.append(line)
    return urls
