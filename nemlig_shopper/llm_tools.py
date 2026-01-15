"""LLM-friendly composable tools for grocery shopping orchestration.

This module provides ~25 stateless functions that an LLM can compose
to orchestrate the grocery shopping workflow. Each function has clear
inputs/outputs and can be called independently.

Tool Categories:
- Recipe tools: Parse and scale recipes
- Consolidation tools: Combine ingredients from multiple recipes
- Matching tools: Find products for ingredients
- Preference tools: Check dietary/allergy safety
- Package tools: Optimize package selection
- Cart tools: Add products to cart

Example LLM workflow:
    1. result = consolidate_shopping_list(urls, items)
    2. matches = match_shopping_list(result["consolidated"], allergies=["nuts"])
    3. if matches["warnings"]: review and adjust
    4. cart_result = add_matches_to_cart(matches["matches"])
"""

from typing import Any

from .api import NemligAPI, NemligAPIError
from .matcher import (
    ProductMatch,
    match_ingredient,
    translate_ingredient,
)
from .planner import (
    ConsolidatedIngredient,
    consolidate_ingredients,
    parse_recipes,
)
from .preference_engine import (
    check_allergy_safety,
    check_dietary_compatibility,
    filter_products_by_allergies,
    filter_products_by_dietary,
    get_safe_alternative_query,
)
from .recipe_parser import (
    Ingredient,
    Recipe,
    parse_ingredient_text,
    parse_recipe_text,
    parse_recipe_url,
)
from .scaler import ScaledIngredient, scale_recipe
from .units import calculate_packages_needed, parse_unit_size

# Module-level API instance (lazy initialization)
_api: NemligAPI | None = None


def _get_api() -> NemligAPI:
    """Get or create the API instance."""
    global _api
    if _api is None:
        _api = NemligAPI()
    return _api


def set_api(api: NemligAPI) -> None:
    """Set the API instance (useful for testing with mocks)."""
    global _api
    _api = api


# =============================================================================
# RECIPE TOOLS
# =============================================================================


def parse_recipe(url: str) -> dict[str, Any]:
    """
    Parse a recipe from a URL.

    Args:
        url: URL to a recipe page (supports many recipe websites)

    Returns:
        Recipe data as dict:
        {
            "title": str,
            "servings": int | None,
            "source_url": str,
            "ingredients": [
                {"name": str, "quantity": float | None, "unit": str | None, "original": str}
            ]
        }
    """
    recipe = parse_recipe_url(url)
    return _recipe_to_dict(recipe)


def parse_recipe_from_text(
    title: str,
    ingredients_text: str,
    servings: int | None = None,
) -> dict[str, Any]:
    """
    Parse a recipe from plain text ingredients.

    Args:
        title: Name for the recipe
        ingredients_text: Newline-separated ingredient list
        servings: Number of servings (optional)

    Returns:
        Recipe data as dict (same format as parse_recipe)
    """
    recipe = parse_recipe_text(title, ingredients_text, servings)
    return _recipe_to_dict(recipe)


def scale_recipe_by_factor(
    recipe: dict[str, Any],
    multiplier: float,
) -> dict[str, Any]:
    """
    Scale a recipe by a multiplier.

    Args:
        recipe: Recipe dict from parse_recipe()
        multiplier: Scale factor (e.g., 2.0 for double)

    Returns:
        Scaled recipe dict with adjusted quantities
    """
    recipe_obj = _dict_to_recipe(recipe)
    scaled_ings, factor, new_servings = scale_recipe(recipe_obj, multiplier=multiplier)

    return {
        "title": recipe_obj.title,
        "servings": new_servings,
        "source_url": recipe_obj.source_url,
        "scale_factor": factor,
        "ingredients": [_scaled_ingredient_to_dict(ing) for ing in scaled_ings],
    }


def scale_recipe_to_servings(
    recipe: dict[str, Any],
    target_servings: int,
) -> dict[str, Any]:
    """
    Scale a recipe to a target number of servings.

    Args:
        recipe: Recipe dict from parse_recipe()
        target_servings: Desired number of servings

    Returns:
        Scaled recipe dict with adjusted quantities
    """
    recipe_obj = _dict_to_recipe(recipe)
    scaled_ings, factor, new_servings = scale_recipe(recipe_obj, target_servings=target_servings)

    return {
        "title": recipe_obj.title,
        "servings": new_servings,
        "source_url": recipe_obj.source_url,
        "scale_factor": factor,
        "ingredients": [_scaled_ingredient_to_dict(ing) for ing in scaled_ings],
    }


def parse_manual_items(items: list[str]) -> list[dict[str, Any]]:
    """
    Parse additional items not from recipes.

    Args:
        items: List of item strings (e.g., ["2kg potatoes", "milk", "6 eggs"])

    Returns:
        List of ingredient dicts with parsed quantities
    """
    result = []
    for item in items:
        ingredient = parse_ingredient_text(item)
        result.append(_ingredient_to_dict(ingredient))
    return result


# =============================================================================
# CONSOLIDATION TOOLS
# =============================================================================


def consolidate_shopping_list(
    recipe_urls: list[str],
    additional_items: list[str] | None = None,
    scale_factors: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Main entry point: Parse recipes and consolidate ingredients.

    This is the primary function for starting a shopping session. It:
    1. Parses all recipe URLs
    2. Scales recipes as specified
    3. Consolidates duplicate ingredients (summing quantities)
    4. Adds any additional manual items

    Args:
        recipe_urls: List of recipe page URLs
        additional_items: Extra items not in recipes (e.g., ["bread", "milk"])
        scale_factors: URL -> scale factor mapping (e.g., {"url1": 2.0} for double)

    Returns:
        {
            "recipes": [{"title": str, "servings": int, "url": str}],
            "consolidated": [
                {
                    "name": str,
                    "quantity": float | None,
                    "unit": str | None,
                    "sources": [str]
                }
            ],
            "total_ingredients": int,
            "total_recipes": int
        }
    """
    # Parse and scale recipes
    if recipe_urls:
        recipes, all_ingredients = parse_recipes(recipe_urls, scale_factors)
        consolidated = consolidate_ingredients(all_ingredients)
    else:
        recipes = []
        consolidated = []

    # Add manual items
    if additional_items:
        for item in additional_items:
            ingredient = parse_ingredient_text(item)
            # Create a ConsolidatedIngredient for manual items
            consolidated.append(
                ConsolidatedIngredient(
                    name=ingredient.name,
                    total_quantity=ingredient.quantity,
                    unit=ingredient.unit,
                    sources=["Manual item"],
                )
            )

    return {
        "recipes": [
            {"title": r.title, "servings": r.servings, "url": r.source_url} for r in recipes
        ],
        "consolidated": [_consolidated_to_dict(c) for c in consolidated],
        "total_ingredients": len(consolidated),
        "total_recipes": len(recipes),
    }


def merge_ingredient_lists(
    list1: list[dict[str, Any]],
    list2: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge two ingredient lists, consolidating duplicates.

    Args:
        list1: First ingredient list
        list2: Second ingredient list

    Returns:
        Merged and consolidated ingredient list
    """
    # Convert back to ScaledIngredient for consolidation
    all_ings: list[tuple[ScaledIngredient, str]] = []

    for ing in list1 + list2:
        scaled = ScaledIngredient(
            original=Ingredient(
                original=ing.get("original", ing.get("name", "")),
                name=ing.get("name", ""),
                quantity=ing.get("quantity"),
                unit=ing.get("unit"),
                notes=None,
            ),
            scaled_quantity=ing.get("quantity"),
            scale_factor=1.0,
        )
        sources = ing.get("sources", ["Unknown"])
        source = sources[0] if sources else "Unknown"
        all_ings.append((scaled, source))

    consolidated = consolidate_ingredients(all_ings)
    return [_consolidated_to_dict(c) for c in consolidated]


# =============================================================================
# MATCHING TOOLS
# =============================================================================


def match_shopping_list(
    consolidated: list[dict[str, Any]],
    prefer_organic: bool = False,
    prefer_budget: bool = False,
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> dict[str, Any]:
    """
    Match consolidated ingredients to Nemlig products.

    This function finds products for each ingredient, applies preference
    scoring, and checks for allergy/dietary safety.

    Args:
        consolidated: List of consolidated ingredients from consolidate_shopping_list()
        prefer_organic: Boost organic products in scoring
        prefer_budget: Boost cheaper products in scoring
        allergies: List of allergies to check (e.g., ["nuts", "lactose"])
        dietary: List of dietary restrictions (e.g., ["vegetarian", "vegan"])

    Returns:
        {
            "matches": [
                {
                    "ingredient": str,
                    "product": {...} | None,
                    "quantity": int,
                    "matched": bool,
                    "alternatives": [...],
                    "safety": {"is_safe": bool, "warnings": [...]},
                    "coverage": {"needed": str, "provides": str, "extra": str}
                }
            ],
            "unmatched": [str],
            "warnings": [str],
            "estimated_total": float
        }
    """
    api = _get_api()
    matches: list[dict[str, Any]] = []
    warnings: list[str] = []

    for item in consolidated:
        name = item.get("name", "")
        quantity = item.get("quantity")
        unit = item.get("unit")

        # Match the ingredient
        match = match_ingredient(
            api,
            name,
            quantity,
            unit,
            max_alternatives=3,
            prefer_organic=prefer_organic,
            prefer_budget=prefer_budget,
        )

        match_dict = _match_to_dict(match, item)

        # Check allergy safety
        if match.product and allergies:
            safety = check_allergy_safety(match.product, allergies)
            match_dict["safety"] = safety.to_dict()
            if not safety.is_safe:
                warnings.append(
                    f"'{name}' matched to '{match.product_name}' contains allergens: "
                    f"{', '.join(safety.allergens_found)}"
                )

        # Check dietary compatibility
        if match.product and dietary:
            compat = check_dietary_compatibility(match.product, dietary)
            if not compat.is_compatible:
                match_dict["dietary_warning"] = compat.to_dict()
                warnings.append(
                    f"'{name}' matched to '{match.product_name}' may not be compatible: "
                    f"{', '.join(compat.conflicts)}"
                )

        matches.append(match_dict)

    # Calculate totals
    unmatched = [m["ingredient"] for m in matches if not m["matched"]]
    total = sum(
        (m["product"]["price"] or 0) * m["quantity"]
        for m in matches
        if m["matched"] and m["product"]
    )

    return {
        "matches": matches,
        "unmatched": unmatched,
        "warnings": warnings,
        "estimated_total": round(total, 2),
    }


def search_products(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search for products on Nemlig.com.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of product dicts with name, price, unit_size, etc.
    """
    api = _get_api()
    try:
        products = api.search_products(query, limit=limit)
        return products
    except NemligAPIError:
        return []


def search_alternatives(
    ingredient_name: str,
    custom_query: str | None = None,
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Search for alternative products for an ingredient.

    Args:
        ingredient_name: The ingredient to find alternatives for
        custom_query: Custom search query (uses ingredient name if not provided)
        allergies: Filter out products with these allergens
        dietary: Filter out products incompatible with these restrictions

    Returns:
        List of products with safety annotations
    """
    api = _get_api()

    # Determine search query
    if custom_query:
        query = custom_query
    else:
        # Try to find a safe alternative query if there are restrictions
        safe_query = get_safe_alternative_query(ingredient_name, allergies, dietary)
        query = safe_query or ingredient_name

        # Also try Danish translation
        danish = translate_ingredient(ingredient_name)
        if danish and not custom_query:
            query = danish

    try:
        products = api.search_products(query, limit=10)
    except NemligAPIError:
        return []

    # Filter by allergies/dietary if specified
    if allergies:
        products, _unsafe = filter_products_by_allergies(products, allergies)

    if dietary:
        products, _incompatible = filter_products_by_dietary(products, dietary)

    # Annotate with safety info
    result = []
    for product in products:
        p = product.copy()
        if allergies:
            p["allergy_check"] = check_allergy_safety(product, allergies).to_dict()
        if dietary:
            p["dietary_check"] = check_dietary_compatibility(product, dietary).to_dict()
        result.append(p)

    return result


def select_alternative_product(
    matches: list[dict[str, Any]],
    ingredient_name: str,
    alternative_index: int,
) -> list[dict[str, Any]]:
    """
    Select an alternative product for an ingredient.

    Args:
        matches: List of match dicts from match_shopping_list()
        ingredient_name: Name of ingredient to change
        alternative_index: Index of alternative to select (0-based)

    Returns:
        Updated matches list with alternative selected
    """
    result = []
    for match in matches:
        if match["ingredient"].lower() == ingredient_name.lower():
            alternatives = match.get("alternatives", [])
            if alternative_index < len(alternatives):
                # Swap current product with alternative
                old_product = match.get("product")
                new_product = alternatives[alternative_index]

                new_alts = [old_product] if old_product else []
                new_alts.extend(alt for i, alt in enumerate(alternatives) if i != alternative_index)

                match = match.copy()
                match["product"] = new_product
                match["alternatives"] = new_alts
                match["matched"] = True

        result.append(match)

    return result


def exclude_ingredient(
    matches: list[dict[str, Any]],
    ingredient_name: str,
) -> list[dict[str, Any]]:
    """
    Exclude an ingredient from the shopping list.

    Args:
        matches: List of match dicts
        ingredient_name: Name of ingredient to exclude

    Returns:
        Updated matches list with ingredient removed
    """
    return [m for m in matches if m["ingredient"].lower() != ingredient_name.lower()]


# =============================================================================
# PREFERENCE TOOLS
# =============================================================================


def check_product_allergies(
    product: dict[str, Any],
    allergens: list[str],
) -> dict[str, Any]:
    """
    Check if a product is safe for specific allergies.

    Args:
        product: Product dict
        allergens: List of allergy types (e.g., ["nuts", "gluten", "dairy"])

    Returns:
        {
            "is_safe": bool,
            "allergens_found": [str],
            "warnings": [str],
            "product_name": str
        }
    """
    result = check_allergy_safety(product, allergens)
    return result.to_dict()


def check_product_dietary(
    product: dict[str, Any],
    dietary_restrictions: list[str],
) -> dict[str, Any]:
    """
    Check if a product is compatible with dietary restrictions.

    Args:
        product: Product dict
        dietary_restrictions: List of restrictions (e.g., ["vegetarian", "vegan"])

    Returns:
        {
            "is_compatible": bool,
            "conflicts": [str],
            "warnings": [str],
            "product_name": str
        }
    """
    result = check_dietary_compatibility(product, dietary_restrictions)
    return result.to_dict()


def filter_safe_products(
    products: list[dict[str, Any]],
    allergies: list[str] | None = None,
    dietary: list[str] | None = None,
) -> dict[str, Any]:
    """
    Filter products to only include safe ones.

    Args:
        products: List of product dicts
        allergies: Allergies to check
        dietary: Dietary restrictions to check

    Returns:
        {
            "safe": [product dicts],
            "unsafe": [product dicts with warnings],
            "safe_count": int,
            "unsafe_count": int
        }
    """
    safe = products
    unsafe: list[dict[str, Any]] = []

    if allergies:
        safe, unsafe_allergy = filter_products_by_allergies(safe, allergies)
        unsafe.extend(unsafe_allergy)

    if dietary:
        safe, unsafe_dietary = filter_products_by_dietary(safe, dietary)
        unsafe.extend(unsafe_dietary)

    return {
        "safe": safe,
        "unsafe": unsafe,
        "safe_count": len(safe),
        "unsafe_count": len(unsafe),
    }


# =============================================================================
# PACKAGE OPTIMIZATION TOOLS
# =============================================================================


def optimize_package_selection(
    needed_quantity: float,
    needed_unit: str | None,
    available_products: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Find the optimal product package to minimize items while covering need.

    This helps avoid over-buying. For example:
    - Need 3 onions → options: 3 individual (3 items) vs 1 bag of 5 (1 item)
    - Optimizer picks: 1 bag (fewer items, acceptable waste)

    Args:
        needed_quantity: Amount needed
        needed_unit: Unit of needed amount (e.g., "stk", "g", "ml")
        available_products: List of product options

    Returns:
        {
            "product": {...},
            "packages_to_buy": int,
            "coverage": str,
            "waste": str,
            "waste_percentage": float,
            "score": float
        }
    """
    if not available_products:
        return {"product": None, "packages_to_buy": 0, "error": "No products available"}

    candidates = []

    for product in available_products:
        unit_size = product.get("unit_size")
        parsed = parse_unit_size(unit_size)

        if parsed is None:
            # Can't parse unit size, default to 1 package
            candidates.append(
                {
                    "product": product,
                    "packages": 1,
                    "coverage": unit_size or "1 stk",
                    "waste": "unknown",
                    "waste_pct": 0.0,
                    "score": -100,  # Low score for unparseable
                }
            )
            continue

        # Calculate packages needed
        packages = calculate_packages_needed(needed_quantity, needed_unit, unit_size)
        if packages == 0:
            packages = 1  # Fallback

        # Calculate coverage and waste
        total_coverage = packages * parsed.value
        waste = total_coverage - (needed_quantity or 0)
        waste_pct = waste / total_coverage if total_coverage > 0 else 0

        # Score: prefer fewer packages, less waste, lower price
        price = product.get("price", 0) or 0
        score = (
            -packages * 10  # Fewer packages = better
            - waste_pct * 5  # Less waste = better
            - (price * packages) / 100  # Lower total = better
        )

        # Bonus if product is in stock
        if product.get("available", True):
            score += 20

        candidates.append(
            {
                "product": product,
                "packages": packages,
                "coverage": f"{total_coverage:.0f} {parsed.unit}",
                "waste": f"{waste:.0f} {parsed.unit}" if waste > 0 else "0",
                "waste_pct": round(waste_pct, 2),
                "score": score,
            }
        )

    # Sort by score (highest first)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    return {
        "product": best["product"],
        "packages_to_buy": best["packages"],
        "coverage": best["coverage"],
        "waste": best["waste"],
        "waste_percentage": best["waste_pct"],
        "score": best["score"],
    }


def calculate_package_coverage(
    product: dict[str, Any],
    needed_quantity: float,
    needed_unit: str | None,
) -> dict[str, Any]:
    """
    Calculate how well a product covers a needed quantity.

    Args:
        product: Product dict
        needed_quantity: Amount needed
        needed_unit: Unit of needed amount

    Returns:
        {
            "packages_needed": int,
            "total_coverage": str,
            "extra": str,
            "covers_need": bool
        }
    """
    unit_size = product.get("unit_size")
    packages = calculate_packages_needed(needed_quantity, needed_unit, unit_size)

    parsed = parse_unit_size(unit_size)
    if parsed:
        total = packages * parsed.value
        extra = total - (needed_quantity or 0)
        return {
            "packages_needed": packages,
            "total_coverage": f"{total:.0f} {parsed.unit}",
            "extra": f"{extra:.0f} {parsed.unit}" if extra > 0 else "0",
            "covers_need": total >= (needed_quantity or 0),
        }

    return {
        "packages_needed": packages,
        "total_coverage": f"{packages} x {unit_size or 'unknown'}",
        "extra": "unknown",
        "covers_need": True,
    }


# =============================================================================
# CART TOOLS
# =============================================================================


def add_matches_to_cart(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Add all matched products to the Nemlig cart.

    Args:
        matches: List of match dicts from match_shopping_list()

    Returns:
        {
            "success_count": int,
            "failed_count": int,
            "failed": [{"ingredient": str, "error": str}],
            "cart_total": float | None
        }
    """
    api = _get_api()
    items = []

    for match in matches:
        if match.get("matched") and match.get("product"):
            product_id = match["product"].get("id")
            quantity = match.get("quantity", 1)
            if product_id:
                items.append({"product_id": product_id, "quantity": quantity})

    if not items:
        return {
            "success_count": 0,
            "failed_count": 0,
            "failed": [],
            "cart_total": None,
        }

    try:
        result = api.add_multiple_to_cart(items)
        success_count = len(result.get("success", []))
        failed = result.get("failed", [])

        # Map failed items back to ingredients
        failed_items = []
        for failure in failed:
            product_id = failure.get("product_id")
            # Find the ingredient name for this product
            for match in matches:
                if match.get("product", {}).get("id") == product_id:
                    failed_items.append(
                        {
                            "ingredient": match["ingredient"],
                            "product": match["product"].get("name"),
                            "error": failure.get("error", "Unknown error"),
                        }
                    )
                    break

        # Get cart total
        try:
            cart = api.get_cart()
            cart_total = cart.get("total")
        except NemligAPIError:
            cart_total = None

        return {
            "success_count": success_count,
            "failed_count": len(failed),
            "failed": failed_items,
            "cart_total": cart_total,
        }
    except NemligAPIError as e:
        return {
            "success_count": 0,
            "failed_count": len(items),
            "failed": [{"ingredient": "all", "error": str(e)}],
            "cart_total": None,
        }


def get_cart_contents() -> dict[str, Any]:
    """
    Get current cart contents and total.

    Returns:
        Cart data including items and total
    """
    api = _get_api()
    try:
        return api.get_cart()
    except NemligAPIError as e:
        return {"error": str(e)}


def get_shopping_summary(matches: list[dict[str, Any]]) -> str:
    """
    Get a human-readable summary of the shopping list.

    Args:
        matches: List of match dicts

    Returns:
        Formatted markdown summary
    """
    lines = ["## Shopping List Summary\n"]

    # Group by matched status
    matched = [m for m in matches if m.get("matched")]
    unmatched = [m for m in matches if not m.get("matched")]

    if matched:
        lines.append("### Matched Products\n")
        lines.append("| Ingredient | Product | Qty | Price | Notes |")
        lines.append("|------------|---------|-----|-------|-------|")

        for m in matched:
            ingredient = m["ingredient"]
            product = m.get("product", {})
            name = product.get("name", "Unknown")[:30]
            qty = m.get("quantity", 1)
            price = product.get("price", 0)
            price_str = f"{price:.2f} kr" if price else "N/A"

            # Collect notes
            notes = []
            if m.get("safety", {}).get("is_safe") is False:
                notes.append("Allergy warning")
            if m.get("dietary_warning"):
                notes.append("Dietary warning")
            coverage = m.get("coverage", {})
            if coverage.get("extra") and coverage["extra"] != "0":
                notes.append(f"+{coverage['extra']}")

            notes_str = ", ".join(notes) if notes else ""
            lines.append(f"| {ingredient} | {name} | {qty} | {price_str} | {notes_str} |")

    if unmatched:
        lines.append("\n### Unmatched (manual action needed)")
        for m in unmatched:
            lines.append(f"- {m['ingredient']}")

    # Total
    total = sum(
        (m["product"]["price"] or 0) * m["quantity"]
        for m in matches
        if m.get("matched") and m.get("product")
    )
    lines.append(f"\n**Estimated Total:** {total:.2f} kr")
    lines.append(f"**Items:** {len(matched)} matched, {len(unmatched)} unmatched")

    return "\n".join(lines)


# =============================================================================
# UTILITY FUNCTIONS (Internal)
# =============================================================================


def _recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    """Convert Recipe to dict."""
    return {
        "title": recipe.title,
        "servings": recipe.servings,
        "source_url": recipe.source_url,
        "ingredients": [_ingredient_to_dict(ing) for ing in recipe.ingredients],
    }


def _ingredient_to_dict(ingredient: Ingredient) -> dict[str, Any]:
    """Convert Ingredient to dict."""
    return {
        "name": ingredient.name,
        "quantity": ingredient.quantity,
        "unit": ingredient.unit,
        "original": ingredient.original,
        "notes": ingredient.notes,
    }


def _scaled_ingredient_to_dict(ingredient: ScaledIngredient) -> dict[str, Any]:
    """Convert ScaledIngredient to dict."""
    return {
        "name": ingredient.name,
        "quantity": ingredient.scaled_quantity,
        "unit": ingredient.unit,
        "scale_factor": ingredient.scale_factor,
        "original": ingredient.original.original,
    }


def _consolidated_to_dict(consolidated: ConsolidatedIngredient) -> dict[str, Any]:
    """Convert ConsolidatedIngredient to dict."""
    return {
        "name": consolidated.name,
        "quantity": consolidated.total_quantity,
        "unit": consolidated.unit,
        "sources": consolidated.sources,
    }


def _match_to_dict(match: ProductMatch, consolidated: dict[str, Any]) -> dict[str, Any]:
    """Convert ProductMatch to dict with additional info."""
    result = {
        "ingredient": match.ingredient_name,
        "product": match.product,
        "quantity": match.quantity,
        "matched": match.matched,
        "search_query": match.search_query,
        "alternatives": match.alternatives,
        "safety": {"is_safe": True, "warnings": []},  # Default, updated if checks run
    }

    # Add coverage info
    if match.product:
        unit_size = match.product.get("unit_size")
        needed_qty = consolidated.get("quantity")
        needed_unit = consolidated.get("unit")

        parsed = parse_unit_size(unit_size)
        if parsed and needed_qty:
            total = match.quantity * parsed.value
            extra = total - needed_qty
            result["coverage"] = {
                "needed": f"{needed_qty} {needed_unit or 'stk'}",
                "provides": f"{total:.0f} {parsed.unit}",
                "extra": f"{extra:.0f} {parsed.unit}" if extra > 0 else "0",
            }

    return result


def _dict_to_recipe(data: dict[str, Any]) -> Recipe:
    """Convert dict back to Recipe."""
    ingredients = [
        Ingredient(
            original=ing.get("original", ing.get("name", "")),
            name=ing.get("name", ""),
            quantity=ing.get("quantity"),
            unit=ing.get("unit"),
            notes=ing.get("notes"),
        )
        for ing in data.get("ingredients", [])
    ]

    return Recipe(
        title=data.get("title", ""),
        ingredients=ingredients,
        servings=data.get("servings"),
        source_url=data.get("source_url"),
    )
