"""CLI entry point for Nemlig Shopper."""

import click

from .api import NemligAPI, NemligAPIError
from .config import PANTRY_FILE, clear_credentials, get_credentials, save_credentials
from .export import export_shopping_list
from .favorites import (
    FavoritesError,
    delete_favorite,
    get_favorite,
    get_favorite_product_ids,
    get_favorite_recipe,
    list_favorites,
    save_favorite,
    update_favorite_matches,
)
from .matcher import (
    ProductMatch,
    calculate_total_cost,
    get_unmatched_ingredients,
    is_ambiguous_term,
    match_ingredient,
    match_ingredients,
    prepare_cart_items,
)
from .pantry import (
    DEFAULT_PANTRY_ITEMS,
    add_to_pantry,
    clear_pantry,
    filter_pantry_items,
    identify_pantry_items,
    load_pantry_config,
    remove_from_pantry,
)
from .pantry_tui import interactive_pantry_check, simple_pantry_prompt
from .planner import (
    MealPlan,
    consolidate_ingredients,
    create_meal_plan,
    load_urls_from_file,
)
from .preferences import (
    PreferencesError,
    clear_preferences,
    get_last_sync_time,
    get_preference_count,
    sync_preferences_from_orders,
)
from .price_tracker import get_tracker, record_search_prices
from .recipe_parser import Recipe, parse_recipe_text, parse_recipe_url
from .scaler import ScaledIngredient, format_scale_info, scale_recipe
from .tui import interactive_review

# Shared API instance
_api: NemligAPI | None = None


def get_api() -> NemligAPI:
    """Get or create the API instance."""
    global _api
    if _api is None:
        _api = NemligAPI()
    return _api


def ensure_logged_in(api: NemligAPI) -> bool:
    """Ensure user is logged in, prompting for credentials if needed."""
    if api.is_logged_in():
        return True

    username, password = get_credentials()

    if not username or not password:
        click.echo("No credentials found. Please log in first with: nemlig login")
        return False

    try:
        api.login(username, password)
        return True
    except NemligAPIError as e:
        click.echo(f"Login failed: {e}", err=True)
        return False


def display_matches(matches: list[ProductMatch], show_alternatives: bool = False) -> None:
    """Display product matches in a formatted way."""
    click.echo()
    click.echo("=" * 60)
    click.echo("MATCHED PRODUCTS")
    click.echo("=" * 60)

    matched_count = 0
    unmatched_count = 0
    dietary_warnings_count = 0

    for i, match in enumerate(matches, 1):
        if match.matched:
            matched_count += 1
            price_str = f"{match.price:.2f} DKK" if match.price else "N/A"
            click.echo(f"\n{i}. {match.ingredient_name}")
            click.echo(f"   → {match.product_name} (x{match.quantity})")
            click.echo(f"   Price: {price_str}")

            # Show dietary warnings
            if not match.is_dietary_safe and match.dietary_warnings:
                dietary_warnings_count += 1
                for warning in match.dietary_warnings:
                    click.echo(f"   ⚠️  {warning}")

            # Show how many products were filtered
            if match.excluded_count > 0:
                click.echo(f"   ({match.excluded_count} products excluded due to dietary filters)")

            if show_alternatives and match.alternatives:
                click.echo("   Alternatives:")
                for j, alt in enumerate(match.alternatives):
                    alt_name = alt.get("name", "Unknown")
                    alt_price = alt.get("price")
                    price_info = f" - {alt_price:.2f} DKK" if alt_price else ""
                    click.echo(f"     {j + 1}. {alt_name}{price_info}")
        else:
            unmatched_count += 1
            click.echo(f"\n{i}. {match.ingredient_name}")
            click.echo(f"   ✗ No match found (searched: '{match.search_query}')")

    click.echo()
    click.echo("-" * 60)
    click.echo(f"Matched: {matched_count} | Unmatched: {unmatched_count}")
    if dietary_warnings_count > 0:
        click.echo(f"⚠️  Dietary warnings: {dietary_warnings_count}")

    total = calculate_total_cost(matches)
    click.echo(f"Estimated total: {total:.2f} DKK")
    click.echo("-" * 60)


def display_recipe(recipe: Recipe, scaled_info: str | None = None) -> None:
    """Display a parsed recipe."""
    click.echo()
    click.echo("=" * 60)
    click.echo(f"RECIPE: {recipe.title}")
    click.echo("=" * 60)

    if recipe.source_url:
        click.echo(f"Source: {recipe.source_url}")
    if recipe.servings:
        click.echo(f"Servings: {recipe.servings}")
    if scaled_info:
        click.echo(f"Scaling: {scaled_info}")

    click.echo("\nIngredients:")
    for i, ing in enumerate(recipe.ingredients, 1):
        click.echo(f"  {i}. {ing.original}")

    click.echo()


# ============================================================================
# Main CLI Group
# ============================================================================


@click.group()
@click.version_option(version="1.0.0", prog_name="nemlig-shopper")
def cli():
    """Nemlig.com Recipe-to-Cart CLI Tool.

    Parse recipes from URLs or text, match ingredients to Nemlig.com products,
    and add them to your cart.
    """
    pass


# ============================================================================
# Authentication Commands
# ============================================================================


@cli.command()
@click.option("--username", "-u", prompt="Email", help="Nemlig.com email")
@click.option("--password", "-p", prompt="Password", hide_input=True, help="Password")
@click.option("--save/--no-save", default=True, help="Save credentials locally")
def login(username: str, password: str, save: bool):
    """Log in to Nemlig.com."""
    api = get_api()

    try:
        api.login(username, password)
        click.echo("✓ Login successful!")

        if save:
            save_credentials(username, password)
            click.echo("✓ Credentials saved")
    except NemligAPIError as e:
        click.echo(f"✗ Login failed: {e}", err=True)
        raise SystemExit(1) from None


@cli.command()
def logout():
    """Clear saved credentials."""
    clear_credentials()
    click.echo("✓ Credentials cleared")


# ============================================================================
# Recipe Parsing Commands
# ============================================================================


@cli.command("parse")
@click.argument("url")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier (e.g., 2 for double)")
@click.option("--servings", "-S", type=int, help="Scale to target servings")
def parse_url(url: str, scale: float | None, servings: int | None):
    """Parse a recipe from a URL."""
    try:
        click.echo(f"Parsing recipe from: {url}")
        recipe = parse_recipe_url(url)

        # Apply scaling if requested
        if scale or servings:
            scaled_ings, factor, new_servings = scale_recipe(
                recipe, target_servings=servings, multiplier=scale
            )
            scale_info = format_scale_info(factor, recipe.servings, new_servings)

            # Update recipe with scaled values for display
            display_recipe(recipe, scale_info)

            click.echo("Scaled Ingredients:")
            for i, ing in enumerate(scaled_ings, 1):
                click.echo(f"  {i}. {ing}")
        else:
            display_recipe(recipe)

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Failed to parse recipe: {e}", err=True)
        raise SystemExit(1) from None


@cli.command("parse-text")
@click.option("--title", "-t", prompt="Recipe title", help="Name for the recipe")
@click.option("--servings", "-S", type=int, help="Number of servings")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier")
def parse_text_cmd(title: str, servings: int | None, scale: float | None):
    """Parse ingredients from text input."""
    click.echo("Enter ingredients (one per line, empty line to finish):")

    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)

    if not lines:
        click.echo("No ingredients entered.", err=True)
        raise SystemExit(1)

    ingredients_text = "\n".join(lines)
    recipe = parse_recipe_text(title, ingredients_text, servings)

    # Apply scaling if requested
    if scale:
        scaled_ings, factor, new_servings = scale_recipe(recipe, multiplier=scale)
        scale_info = format_scale_info(factor, recipe.servings, new_servings)
        display_recipe(recipe, scale_info)

        click.echo("Scaled Ingredients:")
        for i, ing in enumerate(scaled_ings, 1):
            click.echo(f"  {i}. {ing}")
    else:
        display_recipe(recipe)


# ============================================================================
# Search & Cart Commands
# ============================================================================


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=5, help="Maximum results to show")
def search(query: str, limit: int):
    """Search for products on Nemlig.com."""
    api = get_api()

    try:
        click.echo(f"Searching for: {query}")
        products = api.search_products(query, limit=limit)

        if not products:
            click.echo("No products found.")
            return

        click.echo(f"\nFound {len(products)} products:\n")
        for i, product in enumerate(products, 1):
            name = product.get("name", "Unknown")
            price = product.get("price")
            unit = product.get("unit_size", "")
            price_str = f"{price:.2f} DKK" if price else "N/A"
            click.echo(f"{i}. {name}")
            click.echo(f"   {unit} - {price_str}")
            click.echo()

    except NemligAPIError as e:
        click.echo(f"✗ Search failed: {e}", err=True)
        raise SystemExit(1) from None


@cli.command()
def cart():
    """View current shopping cart contents."""
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    try:
        cart_data = api.get_cart()

        items = cart_data.get("Lines", [])
        total = cart_data.get("TotalProductsPrice", 0)
        item_count = cart_data.get("NumberOfProducts", 0)
        delivery = cart_data.get("DeliveryPrice", 0)
        delivery_time = cart_data.get("FormattedDeliveryTime", "")

        if not items:
            click.echo("Your cart is empty.")
            click.echo("\nUse 'nemlig add <recipe-url>' to add items.")
            return

        click.echo()
        click.echo("SHOPPING CART")
        click.echo("=" * 60)

        for item in items:
            name = item.get("ProductName", "Unknown")
            qty = item.get("Quantity", 1)
            price = item.get("Total", item.get("Price", 0))
            click.echo(f"  {qty}x {name} - {price:.2f} DKK")

        click.echo("-" * 60)
        click.echo(f"Products: {item_count}")
        click.echo(f"Subtotal: {total:.2f} DKK")
        click.echo(f"Delivery: {delivery:.2f} DKK")
        click.echo(f"Total: {total + delivery:.2f} DKK")
        if delivery_time:
            click.echo(f"\nDelivery: {delivery_time}")
        click.echo()
        click.echo("View online: https://www.nemlig.com/LeveringsInfo")

    except NemligAPIError as e:
        click.echo(f"✗ Failed to get cart: {e}", err=True)
        raise SystemExit(1) from None


@cli.command("add")
@click.argument("url")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier")
@click.option("--servings", "-S", type=int, help="Scale to target servings")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheaper products")
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
@click.option("--interactive", "-i", is_flag=True, help="Interactive review with TUI")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--save-as", help="Save as favorite with this name")
@click.option("--skip-pantry-check", is_flag=True, help="Skip pantry item check")
@click.option("--remember-pantry", is_flag=True, help="Remember excluded items as pantry")
def add_to_cart(
    url: str,
    scale: float | None,
    servings: int | None,
    organic: bool,
    budget: bool,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
    interactive: bool,
    yes: bool,
    save_as: str | None,
    skip_pantry_check: bool,
    remember_pantry: bool,
):
    """Parse a recipe and add matched products to cart."""
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    try:
        # Parse recipe
        click.echo(f"Parsing recipe from: {url}")
        recipe = parse_recipe_url(url)

        # Scale if requested
        scaled_ings, factor, new_servings = scale_recipe(
            recipe, target_servings=servings, multiplier=scale
        )

        if factor != 1.0:
            scale_info = format_scale_info(factor, recipe.servings, new_servings)
            click.echo(f"Scaling: {scale_info}")

        # Pantry check: identify and optionally exclude common household items
        if not skip_pantry_check:
            # Convert scaled ingredients to consolidated format for pantry check
            from .planner import ConsolidatedIngredient

            consolidated_for_pantry = [
                ConsolidatedIngredient(
                    name=ing.name,
                    total_quantity=ing.scaled_quantity,
                    unit=ing.unit,
                    sources=[recipe.title],
                )
                for ing in scaled_ings
            ]

            pantry_config = load_pantry_config(PANTRY_FILE)
            pantry_candidates, other_ings = identify_pantry_items(
                consolidated_for_pantry, pantry_config
            )

            # Build index map: consolidated ingredient -> original scaled_ings index
            pantry_candidate_indices = {
                id(c): i for i, c in enumerate(consolidated_for_pantry) if c in pantry_candidates
            }

            if pantry_candidates:
                click.echo(f"\nFound {len(pantry_candidates)} potential pantry items.")

                # Use TUI if interactive, otherwise simple prompt
                if interactive:
                    pantry_result = interactive_pantry_check(
                        pantry_candidates, f"Pantry Check - {recipe.title}"
                    )
                else:
                    pantry_result = simple_pantry_prompt(pantry_candidates)

                if not pantry_result.confirmed:
                    click.echo("Cancelled.")
                    return

                if pantry_result.excluded_items:
                    click.echo(
                        f"Excluding {len(pantry_result.excluded_items)} pantry items from shopping list."
                    )

                    # Remember pantry items if requested
                    if remember_pantry and pantry_result.excluded_items:
                        add_to_pantry(pantry_result.excluded_items, PANTRY_FILE)
                        click.echo("✓ Saved excluded items to your pantry")

                    # Filter out excluded items using indices for precision
                    excluded_names_lower = {name.lower() for name in pantry_result.excluded_items}
                    excluded_indices = {
                        pantry_candidate_indices[id(c)]
                        for c in pantry_candidates
                        if c.name.lower() in excluded_names_lower
                    }
                    scaled_ings = [
                        ing for i, ing in enumerate(scaled_ings) if i not in excluded_indices
                    ]

        # Show preference mode
        if organic:
            click.echo("Mode: Preferring organic products")
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Match ingredients to products
        click.echo("Matching ingredients to products...")
        matches = match_ingredients(
            api,
            scaled_ings,
            prefer_organic=organic,
            prefer_budget=budget,
            allergies=allergies if allergies else None,
            dietary=dietary if dietary else None,
        )

        # Interactive mode: use TUI for review
        if interactive:
            review_result = interactive_review(matches, recipe.title)
            if not review_result.confirmed:
                click.echo("Cancelled.")
                return
            matches = review_result.matches
        else:
            display_matches(matches, show_alternatives=True)

            # Check for unmatched
            unmatched = get_unmatched_ingredients(matches)
            if unmatched:
                click.echo(f"\n⚠ {len(unmatched)} ingredients could not be matched:")
                for name in unmatched:
                    click.echo(f"  - {name}")

            # Confirm
            if not yes:
                if not click.confirm("\nAdd matched products to cart?"):
                    click.echo("Cancelled.")
                    return

        # Add to cart
        cart_items = prepare_cart_items(matches)
        result = api.add_multiple_to_cart(cart_items)

        success_count = len(result["success"])
        fail_count = len(result["failed"])

        click.echo(f"\n✓ Added {success_count} products to cart")
        if fail_count:
            click.echo(f"✗ Failed to add {fail_count} products")

        # Save as favorite if requested
        if save_as:
            match_dicts = [m.to_dict() for m in matches]
            save_favorite(save_as, recipe, match_dicts, overwrite=True)
            click.echo(f"✓ Saved as favorite: {save_as}")

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Meal Planning Commands
# ============================================================================


def parse_shopping_text(text: str) -> tuple[list[str], list[tuple[str, str | None]]]:
    """
    Parse shopping text to extract URLs and manual items with meal context.

    Args:
        text: Multi-line text with recipe URLs and/or ingredient items

    Returns:
        Tuple of (urls, items_with_context) where items_with_context is
        list of (item_name, meal_context) tuples. The meal_context is
        derived from section headers like "Mexicanske pandekager:".
    """
    import re

    urls = []
    items: list[tuple[str, str | None]] = []

    # Current meal context (from section headers)
    current_meal_context: str | None = None
    # Track if we've seen a URL recently (to reset context after URL sections)
    seen_url_in_section = False

    # Patterns for headers to skip (but extract meal context from)
    weekdays = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
    # Date patterns like "5-6 jan", "d. 5", "januar", etc.
    date_pattern = re.compile(
        r"\b\d{1,2}[-/]?\d{0,2}\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)", re.I
    )
    date_pattern2 = re.compile(r"\bd\.\s*\d{1,2}", re.I)

    for line in text.split("\n"):
        line = line.strip()
        # Empty lines after URL sections reset context
        # (staple items like Mælk, Brød typically come after empty line)
        if not line:
            if seen_url_in_section:
                current_meal_context = None
                seen_url_in_section = False
            continue

        line_lower = line.lower()

        # Check if it's a URL
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
            seen_url_in_section = True
            continue

        # Skip lines that contain weekday names (likely date headers)
        # These indicate a new section, reset context
        if any(day in line_lower for day in weekdays):
            current_meal_context = None
            continue

        # Skip lines with date patterns - also reset context
        if date_pattern.search(line) or date_pattern2.search(line):
            current_meal_context = None
            continue

        # Check for meal section headers (lines ending with colon that aren't dates)
        # These provide meal context for subsequent items
        if line.endswith(":"):
            # Extract meal context from header (remove colon)
            header = line[:-1].strip()
            # Skip generic headers like "Andet:"
            if header.lower() not in {"andet", "other", "diverse", "ekstra"}:
                current_meal_context = header.lower()
            else:
                current_meal_context = None
            continue

        # Skip recipe title lines (common patterns) but note they might set context
        if any(phrase in line_lower for phrase in ["one pot", "opskrift", "fra opskrift"]):
            # Could extract meal name from these lines too
            continue

        # It's a manual item - associate with current meal context
        items.append((line, current_meal_context))

    return urls, items


def display_meal_plan(plan: MealPlan) -> None:
    """Display a meal plan with consolidated ingredients."""
    click.echo()
    click.echo("=" * 60)
    click.echo(f"MEAL PLAN ({plan.recipe_count} recipes)")
    click.echo("=" * 60)

    click.echo("\nRecipes:")
    for i, recipe in enumerate(plan.recipes, 1):
        servings_str = f" ({recipe.servings} servings)" if recipe.servings else ""
        click.echo(f"  {i}. {recipe.title}{servings_str}")

    click.echo(f"\nConsolidated Ingredients ({plan.ingredient_count} items):")
    for ing in plan.consolidated_ingredients:
        sources_str = f" [{', '.join(ing.sources)}]" if len(ing.sources) > 1 else ""
        click.echo(f"  • {ing}{sources_str}")

    click.echo()


@cli.command("plan")
@click.argument("urls", nargs=-1)
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Load URLs from file")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheaper products")
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
@click.option("--interactive", "-i", is_flag=True, help="Interactive review with TUI")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--skip-pantry-check", is_flag=True, help="Skip pantry item check")
@click.option("--remember-pantry", is_flag=True, help="Remember excluded items as pantry")
def plan_meals(
    urls: tuple[str, ...],
    file_path: str | None,
    organic: bool,
    budget: bool,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
    interactive: bool,
    yes: bool,
    skip_pantry_check: bool,
    remember_pantry: bool,
):
    """Plan meals from multiple recipe URLs.

    Parses all recipes, consolidates duplicate ingredients, and adds
    everything to your cart.

    Examples:

        nemlig plan https://recipe1.com https://recipe2.com

        nemlig plan --file recipes.txt --organic

        nemlig plan url1 url2 --budget --yes

        nemlig plan url1 --lactose-free --vegan
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    # Collect URLs from arguments and file
    all_urls = list(urls)
    if file_path:
        try:
            file_urls = load_urls_from_file(file_path)
            all_urls.extend(file_urls)
        except FileNotFoundError:
            click.echo(f"✗ File not found: {file_path}", err=True)
            raise SystemExit(1) from None

    if not all_urls:
        click.echo("✗ No recipe URLs provided. Use arguments or --file.", err=True)
        raise SystemExit(1)

    try:
        # Create meal plan
        click.echo(f"Parsing {len(all_urls)} recipes...")
        plan = create_meal_plan(all_urls)

        display_meal_plan(plan)

        # Pantry check: identify and optionally exclude common household items
        consolidated_to_match = plan.consolidated_ingredients
        if not skip_pantry_check:
            pantry_config = load_pantry_config(PANTRY_FILE)
            pantry_candidates, other_ings = identify_pantry_items(
                consolidated_to_match, pantry_config
            )

            if pantry_candidates:
                click.echo(f"\nFound {len(pantry_candidates)} potential pantry items.")

                # Use TUI if interactive, otherwise simple prompt
                if interactive:
                    pantry_result = interactive_pantry_check(
                        pantry_candidates, "Pantry Check - Meal Plan"
                    )
                else:
                    pantry_result = simple_pantry_prompt(pantry_candidates)

                if not pantry_result.confirmed:
                    click.echo("Cancelled.")
                    return

                if pantry_result.excluded_items:
                    click.echo(
                        f"Excluding {len(pantry_result.excluded_items)} pantry items from shopping list."
                    )

                    # Remember pantry items if requested
                    if remember_pantry and pantry_result.excluded_items:
                        add_to_pantry(pantry_result.excluded_items, PANTRY_FILE)
                        click.echo("✓ Saved excluded items to your pantry")

                    # Filter out excluded items
                    consolidated_to_match = filter_pantry_items(
                        consolidated_to_match, pantry_result.excluded_items
                    )

        # Show preference mode
        if organic:
            click.echo("Mode: Preferring organic products")
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Convert consolidated ingredients to ScaledIngredient-like objects for matching
        click.echo("Matching ingredients to products...")
        from .recipe_parser import Ingredient
        from .scaler import ScaledIngredient

        # Create ScaledIngredient objects from consolidated ingredients
        scaled_ings = []
        for cons in consolidated_to_match:
            # Create a minimal Ingredient for the ScaledIngredient wrapper
            orig = Ingredient(
                original=str(cons),
                name=cons.name,
                quantity=cons.total_quantity,
                unit=cons.unit,
            )
            scaled = ScaledIngredient(
                original=orig,
                scaled_quantity=cons.total_quantity,
                scale_factor=1.0,
            )
            scaled_ings.append(scaled)

        matches = match_ingredients(
            api,
            scaled_ings,
            prefer_organic=organic,
            prefer_budget=budget,
            allergies=allergies if allergies else None,
            dietary=dietary if dietary else None,
        )

        # Interactive mode: use TUI for review
        if interactive:
            review_result = interactive_review(matches, f"Meal Plan ({plan.recipe_count} recipes)")
            if not review_result.confirmed:
                click.echo("Cancelled.")
                return
            matches = review_result.matches
        else:
            display_matches(matches, show_alternatives=True)

            # Check for unmatched
            unmatched = get_unmatched_ingredients(matches)
            if unmatched:
                click.echo(f"\n⚠ {len(unmatched)} ingredients could not be matched:")
                for name in unmatched:
                    click.echo(f"  - {name}")

            # Confirm
            if not yes:
                if not click.confirm("\nAdd matched products to cart?"):
                    click.echo("Cancelled.")
                    return

        # Add to cart
        cart_items = prepare_cart_items(matches)
        result = api.add_multiple_to_cart(cart_items)

        success_count = len(result["success"])
        fail_count = len(result["failed"])

        click.echo(f"\n✓ Added {success_count} products to cart")
        if fail_count:
            click.echo(f"✗ Failed to add {fail_count} products")

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1) from None


@cli.command("shop")
@click.option("--text", "-t", "input_text", help="Shopping list as inline text")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Load from file")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic (within 15kr of cheapest)")
@click.option("--no-organic", is_flag=True, help="Never prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheapest products")
@click.option(
    "--organic-threshold",
    type=float,
    default=15.0,
    help="Max extra cost for organic (default 15 DKK)",
)
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
@click.option("--interactive", "-i", is_flag=True, help="Interactive review with TUI")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--skip-pantry-check", is_flag=True, help="Skip pantry item check")
@click.option("--skip-ambiguous-check", is_flag=True, help="Skip prompts for ambiguous items")
@click.option("--remember-pantry", is_flag=True, help="Remember excluded items as pantry")
@click.option("--dry-run", is_flag=True, help="Show what would be added without adding to cart")
def shop(
    input_text: str | None,
    file_path: str | None,
    organic: bool,
    no_organic: bool,
    budget: bool,
    organic_threshold: float,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
    interactive: bool,
    yes: bool,
    skip_pantry_check: bool,
    skip_ambiguous_check: bool,
    remember_pantry: bool,
    dry_run: bool,
):
    """Shop from inline text containing recipes and items.

    Parses recipe URLs and manual items from text, consolidates ingredients,
    and adds everything to your cart.

    The text can contain:
    - Recipe URLs (any line starting with http:// or https://)
    - Manual items (ingredient names like "mælk", "brød", "2x æg")
    - Headers/dates are automatically skipped

    Examples:

        nemlig shop --text "mælk, brød, æg"

        nemlig shop --text "https://recipe.com/pasta
        mælk
        brød
        2x æg"

        nemlig shop -t "$(cat shopping-list.txt)" --organic

        echo "mælk, brød" | nemlig shop --text -
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    # Get input text from option, file, or stdin
    if input_text == "-":
        # Read from stdin
        import sys

        input_text = sys.stdin.read()
    elif file_path:
        with open(file_path) as f:
            input_text = f.read()
    elif not input_text:
        click.echo("✗ No input provided. Use --text or --file.", err=True)
        raise SystemExit(1)

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    try:
        # Parse input to extract URLs and manual items
        # Handle comma-separated items
        if "," in input_text and "\n" not in input_text:
            input_text = input_text.replace(",", "\n")

        urls, items_with_context = parse_shopping_text(input_text)

        click.echo(f"Found {len(urls)} recipe URL(s) and {len(items_with_context)} manual item(s)")

        # Parse recipes if any URLs
        # Store (ScaledIngredient, source, meal_context) tuples
        all_ingredients: list[tuple[ScaledIngredient, str, str | None]] = []
        recipes: list[Recipe] = []

        if urls:
            click.echo(f"\nParsing {len(urls)} recipes...")
            for url in urls:
                try:
                    recipe = parse_recipe_url(url)
                    recipes.append(recipe)
                    click.echo(f"  ✓ {recipe.title}")

                    # Derive meal context from recipe title
                    recipe_context = recipe.title.lower() if recipe.title else None

                    # Scale ingredients (1x by default)
                    scaled_ings, _, _ = scale_recipe(recipe)
                    for ing in scaled_ings:
                        all_ingredients.append((ing, recipe.title, recipe_context))
                except Exception as e:
                    click.echo(f"  ✗ Failed to parse {url}: {e}", err=True)

        # Parse manual items with their meal context
        if items_with_context:
            click.echo("\nManual items:")
            from .recipe_parser import parse_ingredient_text

            for item, meal_context in items_with_context:
                ingredient = parse_ingredient_text(item)
                scaled = ScaledIngredient(
                    original=ingredient,
                    scaled_quantity=ingredient.quantity,
                    scale_factor=1.0,
                )
                all_ingredients.append((scaled, "Manual item", meal_context))
                context_str = f" [{meal_context}]" if meal_context else ""
                click.echo(f"  • {ingredient.name}{context_str}")

        if not all_ingredients:
            click.echo("✗ No ingredients to shop for.", err=True)
            raise SystemExit(1)

        # Build meal context mapping before consolidation
        # Maps ingredient name (lowercase) -> meal context
        ingredient_context_map: dict[str, str | None] = {}
        for ing, _source, meal_context in all_ingredients:
            name_lower = ing.name.lower()
            # Keep the first/most specific context for each ingredient
            if name_lower not in ingredient_context_map and meal_context:
                ingredient_context_map[name_lower] = meal_context

        # Consolidate ingredients (convert to old format for consolidate_ingredients)
        ingredients_for_consolidation = [(ing, source) for ing, source, _ in all_ingredients]
        consolidated = consolidate_ingredients(ingredients_for_consolidation)
        click.echo(f"\nConsolidated to {len(consolidated)} unique ingredients")

        # Pantry check
        consolidated_to_match = consolidated
        if not skip_pantry_check:
            pantry_config = load_pantry_config(PANTRY_FILE)
            pantry_candidates, other_ings = identify_pantry_items(consolidated, pantry_config)

            if pantry_candidates:
                click.echo(f"\nFound {len(pantry_candidates)} potential pantry items.")

                # Use TUI if interactive, otherwise simple prompt
                if interactive:
                    pantry_result = interactive_pantry_check(pantry_candidates, "Pantry Check")
                else:
                    pantry_result = simple_pantry_prompt(pantry_candidates)

                if not pantry_result.confirmed:
                    click.echo("Cancelled.")
                    return

                if pantry_result.excluded_items:
                    click.echo(
                        f"Excluding {len(pantry_result.excluded_items)} pantry items from shopping list."
                    )

                    # Remember pantry items if requested
                    if remember_pantry and pantry_result.excluded_items:
                        add_to_pantry(pantry_result.excluded_items, PANTRY_FILE)
                        click.echo("✓ Saved excluded items to your pantry")

                    # Filter out excluded items
                    consolidated_to_match = filter_pantry_items(
                        consolidated, pantry_result.excluded_items
                    )

        # Handle ambiguous terms - prompt user to specify or skip
        if not skip_ambiguous_check and not yes:
            ambiguous_items = [c for c in consolidated_to_match if is_ambiguous_term(c.name)]
            if ambiguous_items:
                click.echo(
                    f"\n⚠ Found {len(ambiguous_items)} ambiguous item(s) that need clarification:"
                )
                items_to_skip = []
                items_to_replace = {}

                for item in ambiguous_items:
                    click.echo(f"\n  '{item.name}' is ambiguous.")
                    click.echo("  Options:")
                    click.echo("    1. Skip this item")
                    click.echo("    2. Specify what you want (e.g., 'æbler' instead of 'frugt')")
                    click.echo("    3. Keep as-is (search will be generic)")

                    choice = click.prompt(
                        "  Choice", type=click.Choice(["1", "2", "3"]), default="3"
                    )

                    if choice == "1":
                        items_to_skip.append(item.name.lower())
                    elif choice == "2":
                        replacement = click.prompt("  What should we search for instead")
                        if replacement:
                            items_to_replace[item.name.lower()] = replacement

                # Apply skips and replacements
                if items_to_skip or items_to_replace:
                    filtered_consolidated = []
                    for cons in consolidated_to_match:
                        name_lower = cons.name.lower()
                        if name_lower in items_to_skip:
                            click.echo(f"  Skipping: {cons.name}")
                            continue
                        if name_lower in items_to_replace:
                            # Create a new ConsolidatedIngredient with the replacement name
                            from .planner import ConsolidatedIngredient

                            cons = ConsolidatedIngredient(
                                name=items_to_replace[name_lower],
                                total_quantity=cons.total_quantity,
                                unit=cons.unit,
                                sources=cons.sources,
                            )
                            click.echo(f"  Replaced: {name_lower} → {cons.name}")
                        filtered_consolidated.append(cons)
                    consolidated_to_match = filtered_consolidated

        # Determine organic preference mode
        # Default: smart organic (prefer organic if price diff < threshold)
        # --organic: always prefer organic
        # --no-organic: never prefer organic
        # --budget: prefer cheapest (no organic preference)
        use_smart_organic = not no_organic and not budget
        use_prefer_organic = organic and not budget

        # Show preference mode
        if use_prefer_organic:
            click.echo("Mode: Always preferring organic products")
        elif use_smart_organic:
            click.echo(
                f"Mode: Smart organic (prefer if within {organic_threshold:.0f} DKK of cheapest)"
            )
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Match each ingredient with its meal context
        click.echo("\nMatching ingredients to products...")

        matches = []
        for cons in consolidated_to_match:
            # Look up meal context for this ingredient
            meal_context = ingredient_context_map.get(cons.name.lower())

            match = match_ingredient(
                api,
                cons.name,
                cons.total_quantity,
                cons.unit,
                prefer_organic=use_prefer_organic,
                prefer_budget=budget,
                smart_organic=use_smart_organic,
                organic_price_threshold=organic_threshold,
                meal_context=meal_context,
                allergies=allergies if allergies else None,
                dietary=dietary if dietary else None,
            )
            matches.append(match)

        # Interactive mode: use TUI for review
        if interactive:
            title = f"Shopping ({len(recipes)} recipes)" if recipes else "Shopping"
            review_result = interactive_review(matches, title)
            if not review_result.confirmed:
                click.echo("Cancelled.")
                return
            matches = review_result.matches
        else:
            display_matches(matches, show_alternatives=True)

            # Check for unmatched
            unmatched = get_unmatched_ingredients(matches)
            if unmatched:
                click.echo(f"\n⚠ {len(unmatched)} ingredients could not be matched:")
                for name in unmatched:
                    click.echo(f"  - {name}")

        # Dry run: just show what would be added
        if dry_run:
            click.echo("\n--- DRY RUN ---")
            click.echo("The following products would be added to cart:")
            total = calculate_total_cost(matches)
            matched_count = sum(1 for m in matches if m.matched)
            click.echo(f"Products: {matched_count}")
            click.echo(f"Estimated total: {total:.2f} DKK")
            click.echo("\nRun without --dry-run to add to cart.")
            return

        # Confirm
        if not yes:
            if not click.confirm("\nAdd matched products to cart?"):
                click.echo("Cancelled.")
                return

        # Add to cart
        cart_items = prepare_cart_items(matches)
        result = api.add_multiple_to_cart(cart_items)

        success_count = len(result["success"])
        fail_count = len(result["failed"])

        click.echo(f"\n✓ Added {success_count} products to cart")
        if fail_count:
            click.echo(f"✗ Failed to add {fail_count} products")

        # Show cart link
        click.echo("\nView cart: https://www.nemlig.com/LeveringsInfo")

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Export Commands
# ============================================================================


@cli.command("export")
@click.argument("url")
@click.argument("output", type=click.Path())
@click.option("--format", "-f", type=click.Choice(["json", "md", "pdf"]), help="Output format")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheaper products")
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
@click.option("--alternatives", "-a", is_flag=True, help="Include alternative products")
def export_list(
    url: str,
    output: str,
    format: str | None,
    scale: float | None,
    organic: bool,
    budget: bool,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
    alternatives: bool,
):
    """Export a recipe's shopping list to a file.

    Parses a recipe, matches products, and exports to JSON, Markdown, or PDF.

    Examples:

        nemlig export https://recipe.com shopping-list.md

        nemlig export https://recipe.com list.json --alternatives

        nemlig export https://recipe.com list.pdf --organic --scale 2

        nemlig export https://recipe.com list.md --lactose-free
    """
    api = get_api()

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    try:
        # Parse recipe
        click.echo(f"Parsing recipe from: {url}")
        recipe = parse_recipe_url(url)

        # Scale if requested
        scaled_ings, factor, _ = scale_recipe(recipe, multiplier=scale)

        if factor != 1.0:
            click.echo(f"Scaling: {factor}x")

        # Show preference mode
        if organic:
            click.echo("Mode: Preferring organic products")
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Match ingredients
        click.echo("Matching ingredients to products...")
        matches = match_ingredients(
            api,
            scaled_ings,
            prefer_organic=organic,
            prefer_budget=budget,
            allergies=allergies if allergies else None,
            dietary=dietary if dietary else None,
        )

        # Export
        used_format = export_shopping_list(
            matches,
            output,
            recipe_title=recipe.title,
            format=format,
            include_alternatives=alternatives,
        )

        click.echo(f"✓ Exported to {output} ({used_format} format)")

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Favorites Commands
# ============================================================================


@cli.group()
def favorites():
    """Manage saved recipe favorites."""
    pass


@favorites.command("list")
def favorites_list():
    """List all saved favorites."""
    favs = list_favorites()

    if not favs:
        click.echo("No favorites saved yet.")
        click.echo("Use 'nemlig favorites save <name>' after parsing a recipe.")
        return

    click.echo()
    click.echo("SAVED FAVORITES")
    click.echo("=" * 60)

    for fav in favs:
        name = fav["name"]
        title = fav["title"]
        count = fav["ingredient_count"]
        servings = fav.get("servings")
        has_matches = "✓" if fav["has_product_matches"] else "✗"

        servings_str = f" ({servings} servings)" if servings else ""
        click.echo(f"\n  {name}")
        click.echo(f"    {title}{servings_str}")
        click.echo(f"    {count} ingredients | Products matched: {has_matches}")

    click.echo()


@favorites.command("show")
@click.argument("name")
def favorites_show(name: str):
    """Show details of a saved favorite."""
    try:
        recipe = get_favorite_recipe(name)
        favorite = get_favorite(name)

        display_recipe(recipe)

        if favorite.get("product_matches"):
            click.echo("Saved Product Matches:")
            for match in favorite["product_matches"]:
                if match.get("matched"):
                    click.echo(f"  • {match['ingredient_name']} → {match['product_name']}")
                else:
                    click.echo(f"  • {match['ingredient_name']} → (no match)")

        click.echo(f"\nSaved: {favorite.get('saved_at', 'Unknown')}")

    except FavoritesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None


@favorites.command("save")
@click.argument("name")
@click.argument("url")
@click.option("--overwrite", is_flag=True, help="Overwrite if exists")
def favorites_save(name: str, url: str, overwrite: bool):
    """Save a recipe URL as a favorite."""
    try:
        click.echo(f"Parsing recipe from: {url}")
        recipe = parse_recipe_url(url)

        save_favorite(name, recipe, overwrite=overwrite)
        click.echo(f"✓ Saved '{recipe.title}' as favorite: {name}")

    except FavoritesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Failed: {e}", err=True)
        raise SystemExit(1) from None


@favorites.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def favorites_delete(name: str, yes: bool):
    """Delete a saved favorite."""
    try:
        if not yes:
            if not click.confirm(f"Delete favorite '{name}'?"):
                click.echo("Cancelled.")
                return

        delete_favorite(name)
        click.echo(f"✓ Deleted favorite: {name}")

    except FavoritesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None


@favorites.command("order")
@click.argument("name")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier")
@click.option("--servings", "-S", type=int, help="Scale to target servings")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheaper products")
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--rematch", is_flag=True, help="Re-match products instead of using saved matches")
def favorites_order(
    name: str,
    scale: float | None,
    servings: int | None,
    organic: bool,
    budget: bool,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
    yes: bool,
    rematch: bool,
):
    """Order a favorite recipe to cart."""
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    try:
        recipe = get_favorite_recipe(name)
        favorite = get_favorite(name)

        click.echo(f"Ordering: {recipe.title}")

        # Scale recipe
        scaled_ings, factor, new_servings = scale_recipe(
            recipe, target_servings=servings, multiplier=scale
        )

        if factor != 1.0:
            scale_info = format_scale_info(factor, recipe.servings, new_servings)
            click.echo(f"Scaling: {scale_info}")

        # Show preference mode
        if organic:
            click.echo("Mode: Preferring organic products")
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Use saved matches or re-match
        # Force rematch if organic/budget/dietary preferences are set
        force_rematch = rematch or organic or budget or allergies or dietary
        if not force_rematch and favorite.get("product_matches") and factor == 1.0:
            # Use saved product IDs (quick re-order)
            click.echo("Using saved product matches...")
            cart_items = get_favorite_product_ids(name)
        else:
            # Re-match products (needed for scaling, preferences, or if no saved matches)
            click.echo("Matching ingredients to products...")
            matches = match_ingredients(
                api,
                scaled_ings,
                prefer_organic=organic,
                prefer_budget=budget,
                allergies=allergies if allergies else None,
                dietary=dietary if dietary else None,
            )
            display_matches(matches)

            cart_items = prepare_cart_items(matches)

            # Update saved matches
            match_dicts = [m.to_dict() for m in matches]
            update_favorite_matches(name, match_dicts)

        if not cart_items:
            click.echo("No products to add.")
            return

        # Confirm
        if not yes:
            if not click.confirm(f"\nAdd {len(cart_items)} products to cart?"):
                click.echo("Cancelled.")
                return

        # Add to cart
        result = api.add_multiple_to_cart(cart_items)

        success_count = len(result["success"])
        fail_count = len(result["failed"])

        click.echo(f"\n✓ Added {success_count} products to cart")
        if fail_count:
            click.echo(f"✗ Failed to add {fail_count} products")

    except FavoritesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except NemligAPIError as e:
        click.echo(f"✗ API error: {e}", err=True)
        raise SystemExit(1) from None


@favorites.command("update")
@click.argument("name")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic products")
@click.option("--budget", "-b", is_flag=True, help="Prefer cheaper products")
@click.option("--lactose-free", is_flag=True, help="Filter for lactose-free products")
@click.option("--gluten-free", is_flag=True, help="Filter for gluten-free products")
@click.option("--vegan", is_flag=True, help="Filter for vegan products")
def favorites_update(
    name: str,
    organic: bool,
    budget: bool,
    lactose_free: bool,
    gluten_free: bool,
    vegan: bool,
):
    """Re-match products for a saved favorite."""
    api = get_api()

    # Build dietary filter lists
    allergies: list[str] = []
    dietary: list[str] = []
    if lactose_free:
        allergies.append("lactose")
    if gluten_free:
        allergies.append("gluten")
    if vegan:
        dietary.append("vegan")

    try:
        recipe = get_favorite_recipe(name)

        click.echo(f"Re-matching products for: {recipe.title}")

        # Show preference mode
        if organic:
            click.echo("Mode: Preferring organic products")
        if budget:
            click.echo("Mode: Preferring budget-friendly products")
        if allergies or dietary:
            filters = allergies + dietary
            click.echo(f"Dietary filters: {', '.join(filters)}")

        # Scale with factor 1.0 (no scaling)
        scaled_ings, _, _ = scale_recipe(recipe)

        # Match products
        matches = match_ingredients(
            api,
            scaled_ings,
            prefer_organic=organic,
            prefer_budget=budget,
            allergies=allergies if allergies else None,
            dietary=dietary if dietary else None,
        )
        display_matches(matches)

        # Save matches
        match_dicts = [m.to_dict() for m in matches]
        update_favorite_matches(name, match_dicts)

        click.echo(f"✓ Updated product matches for: {name}")

    except FavoritesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except NemligAPIError as e:
        click.echo(f"✗ API error: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Preferences Commands
# ============================================================================


@cli.group()
def preferences():
    """Manage product preferences from order history."""
    pass


@preferences.command("sync")
@click.option("--orders", "-n", default=10, help="Number of recent orders to fetch")
def preferences_sync(orders: int):
    """Sync preferences from your Nemlig.com order history.

    This fetches products from your recent orders and uses them
    to improve ingredient matching. Products you've bought before
    will be preferred over similar alternatives.
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    try:
        click.echo(f"Syncing preferences from last {orders} orders...")
        count = sync_preferences_from_orders(api, orders)
        click.echo(f"✓ Synced {count} products from order history")

    except PreferencesError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except NemligAPIError as e:
        click.echo(f"✗ API error: {e}", err=True)
        raise SystemExit(1) from None


@preferences.command("status")
def preferences_status():
    """Show current preferences status."""
    count = get_preference_count()
    last_sync = get_last_sync_time()

    click.echo()
    click.echo("PREFERENCES STATUS")
    click.echo("=" * 40)
    click.echo(f"  Products tracked: {count}")
    click.echo(f"  Last synced: {last_sync or 'Never'}")
    click.echo()

    if count == 0:
        click.echo("Run 'nemlig preferences sync' to import your order history.")


@preferences.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def preferences_clear(yes: bool):
    """Clear all stored preferences."""
    if not yes:
        if not click.confirm("Clear all preferences?"):
            click.echo("Cancelled.")
            return

    clear_preferences()
    click.echo("✓ Preferences cleared")


# ============================================================================
# Pantry Commands
# ============================================================================


@cli.group()
def pantry():
    """Manage your pantry items (ingredients you always have at home).

    Pantry items are common household staples like salt, pepper, olive oil,
    and sugar. When parsing recipes, you'll be prompted to exclude items
    you already have at home.
    """
    pass


@pantry.command("list")
def pantry_list():
    """List your saved pantry items."""
    config = load_pantry_config(PANTRY_FILE)

    # Get all active items
    all_items = config.all_pantry_items

    click.echo()
    click.echo("YOUR PANTRY")
    click.echo("=" * 50)

    if config.user_items:
        click.echo("\n📦 Custom items (added by you):")
        for item in sorted(config.user_items):
            click.echo(f"  • {item}")

    default_active = DEFAULT_PANTRY_ITEMS - config.excluded_defaults
    if default_active:
        click.echo(f"\n📋 Default items ({len(default_active)} active):")
        # Show first 10 defaults
        sorted_defaults = sorted(default_active)
        for item in sorted_defaults[:10]:
            click.echo(f"  • {item}")
        if len(sorted_defaults) > 10:
            click.echo(f"  ... and {len(sorted_defaults) - 10} more")
            click.echo("  (use 'nemlig pantry defaults' to see all)")

    if config.excluded_defaults:
        click.echo(f"\n🚫 Excluded defaults ({len(config.excluded_defaults)}):")
        for item in sorted(config.excluded_defaults):
            click.echo(f"  • {item}")

    click.echo()
    click.echo(f"Total active pantry items: {len(all_items)}")
    click.echo()


@pantry.command("add")
@click.argument("items", nargs=-1, required=True)
def pantry_add(items: tuple[str, ...]):
    """Add items to your pantry.

    Examples:

        nemlig pantry add "fish sauce"

        nemlig pantry add "sesame oil" "rice vinegar" "mirin"
    """
    add_to_pantry(list(items), PANTRY_FILE)
    click.echo(f"✓ Added {len(items)} item(s) to pantry:")
    for item in items:
        click.echo(f"  • {item}")


@pantry.command("remove")
@click.argument("items", nargs=-1, required=True)
def pantry_remove(items: tuple[str, ...]):
    """Remove items from your pantry.

    If the item is a default pantry item, it will be excluded
    from the defaults. Otherwise, it's removed from your custom items.

    Examples:

        nemlig pantry remove "eggs"

        nemlig pantry remove "salt" "pepper"
    """
    remove_from_pantry(list(items), PANTRY_FILE)
    click.echo(f"✓ Removed {len(items)} item(s) from pantry:")
    for item in items:
        click.echo(f"  • {item}")


@pantry.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def pantry_clear(yes: bool):
    """Clear all pantry customizations.

    This resets your pantry to the default items, removing
    any custom items you've added and any exclusions.
    """
    if not yes:
        if not click.confirm("Reset pantry to defaults?"):
            click.echo("Cancelled.")
            return

    clear_pantry(PANTRY_FILE)
    click.echo("✓ Pantry reset to defaults")


@pantry.command("defaults")
def pantry_defaults():
    """Show default pantry items.

    Lists all the built-in pantry items that are automatically
    recognized as common household staples.
    """
    click.echo()
    click.echo("DEFAULT PANTRY ITEMS")
    click.echo("=" * 50)
    click.echo(f"({len(DEFAULT_PANTRY_ITEMS)} items)")
    click.echo()

    # Show items sorted alphabetically
    for item in sorted(DEFAULT_PANTRY_ITEMS):
        click.echo(f"  • {item}")

    click.echo()


# ============================================================================
# Price Tracking Commands
# ============================================================================


@cli.group()
def prices():
    """Track and analyze product prices over time."""
    pass


@prices.command("track")
@click.argument("query")
@click.option("--limit", "-l", default=10, help="Number of products to track")
def prices_track(query: str, limit: int):
    """Track prices for products matching a search query.

    This searches for products and records their current prices
    to build price history for future analysis.

    Examples:

        nemlig prices track "mælk"

        nemlig prices track "pasta" --limit 20
    """
    api = get_api()

    try:
        click.echo(f"Searching for: {query}")
        products = api.search_products(query, limit=limit)

        if not products:
            click.echo("No products found.")
            return

        count = record_search_prices(products)
        click.echo(f"✓ Recorded prices for {count} products")

        # Show what was tracked
        click.echo("\nTracked products:")
        for product in products[:10]:
            name = product.get("name", "Unknown")[:40]
            price = product.get("price")
            price_str = f"{price:.2f} DKK" if price else "N/A"
            click.echo(f"  • {name} - {price_str}")

        if len(products) > 10:
            click.echo(f"  ... and {len(products) - 10} more")

    except NemligAPIError as e:
        click.echo(f"✗ Search failed: {e}", err=True)
        raise SystemExit(1) from None


@prices.command("history")
@click.argument("query")
@click.option("--days", "-d", default=30, help="Number of days to look back")
def prices_history(query: str, days: int):
    """Show price history for a product.

    Search by product name to see how prices have changed over time.

    Examples:

        nemlig prices history "minimælk"

        nemlig prices history "hakket oksekød" --days 60
    """
    tracker = get_tracker()

    # First try to find matching products
    products = tracker.search_products(query, limit=5)

    if not products:
        click.echo(f"No tracked products found matching '{query}'")
        click.echo("Use 'nemlig prices track <query>' to start tracking prices.")
        return

    # Show history for each matching product
    for product in products:
        product_id = product["id"]
        product_name = product["name"]

        click.echo()
        click.echo(f"📊 {product_name}")
        click.echo("-" * 50)

        # Get stats
        stats = tracker.get_price_stats(product_id)
        if stats:
            click.echo(f"  Current: {stats.current_price:.2f} DKK")
            click.echo(f"  Average: {stats.avg_price:.2f} DKK")
            click.echo(f"  Min: {stats.min_price:.2f} DKK | Max: {stats.max_price:.2f} DKK")
            click.echo(f"  Records: {stats.price_count}")

            if stats.is_on_sale:
                click.echo(f"  🏷️  ON SALE: {stats.discount_percent:.1f}% below average!")

        # Get recent history
        history = tracker.get_price_history(product_id=product_id, days=days)
        if history:
            click.echo("\n  Recent prices:")
            for record in history[:5]:
                date_str = record.recorded_at.strftime("%Y-%m-%d %H:%M")
                click.echo(f"    {date_str}: {record.price:.2f} DKK")


@prices.command("alerts")
@click.option("--min-discount", "-m", default=5.0, help="Minimum discount percentage")
def prices_alerts(min_discount: float):
    """Show products currently on sale.

    Lists products where the current price is significantly
    below the historical average.

    Examples:

        nemlig prices alerts

        nemlig prices alerts --min-discount 10
    """
    tracker = get_tracker()

    alerts = tracker.get_price_alerts(min_discount=min_discount)

    if not alerts:
        click.echo(f"No products found with {min_discount}%+ discount.")
        click.echo("Track more prices with 'nemlig prices track <query>'")
        return

    click.echo()
    click.echo(f"🏷️  PRICE ALERTS ({len(alerts)} products on sale)")
    click.echo("=" * 60)

    for alert in alerts:
        lowest = "🔥 LOWEST!" if alert.is_lowest else ""
        click.echo(f"\n  {alert.product_name[:45]}")
        click.echo(f"    Now: {alert.current_price:.2f} DKK (avg: {alert.avg_price:.2f} DKK)")
        click.echo(f"    💰 {alert.discount_percent:.1f}% off {lowest}")

    click.echo()


@prices.command("status")
def prices_status():
    """Show price tracking status."""
    tracker = get_tracker()

    product_count = tracker.get_tracked_count()
    price_count = tracker.get_price_count()

    click.echo()
    click.echo("PRICE TRACKING STATUS")
    click.echo("=" * 40)
    click.echo(f"  Products tracked: {product_count}")
    click.echo(f"  Price records: {price_count}")
    click.echo()

    if product_count == 0:
        click.echo("Start tracking prices with: nemlig prices track <query>")


@prices.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--old-only", is_flag=True, help="Only clear records older than 90 days")
def prices_clear(yes: bool, old_only: bool):
    """Clear price tracking data."""
    tracker = get_tracker()

    if old_only:
        if not yes:
            if not click.confirm("Remove price records older than 90 days?"):
                click.echo("Cancelled.")
                return
        count = tracker.clear_old_prices(days=90)
        click.echo(f"✓ Removed {count} old price records")
    else:
        if not yes:
            if not click.confirm("Clear ALL price tracking data?"):
                click.echo("Cancelled.")
                return
        tracker.clear_all()
        click.echo("✓ All price data cleared")


# ============================================================================
# Delivery Slot Commands
# ============================================================================


@cli.command("slots")
@click.option("--days", "-d", default=8, help="Number of days to show slots for")
@click.option("--available-only", "-a", is_flag=True, help="Only show available slots")
def show_slots(days: int, available_only: bool):
    """Show available delivery time slots.

    Lists upcoming delivery windows with prices and availability.

    Examples:

        nemlig slots

        nemlig slots --days 14 --available-only
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    try:
        click.echo(f"Fetching delivery slots for next {days} days...")
        slots = api.get_delivery_slots(days=days)

        if not slots:
            click.echo("No delivery slots found.")
            return

        if available_only:
            slots = [s for s in slots if s["is_available"]]

        if not slots:
            click.echo("No available slots found.")
            return

        click.echo()
        click.echo("AVAILABLE DELIVERY SLOTS")
        click.echo("=" * 60)

        current_date = None
        for slot in slots:
            date = slot["date"]
            if date != current_date:
                current_date = date
                click.echo(f"\n📅 {date}")
                click.echo("-" * 40)

            start = slot.get("start_hour")
            end = slot.get("end_hour")
            price = slot.get("delivery_price")
            slot_id = slot.get("id")

            # Skip slots with missing critical data
            if start is None or end is None or slot_id is None:
                click.echo(
                    "  ⚠ Skipping malformed slot (missing start_hour, end_hour, or id)", err=True
                )
                continue

            available = "✓" if slot.get("is_available") else "✗"
            free = " (FREE)" if slot.get("is_free") else ""

            price_str = f"{price:.2f} DKK{free}" if price is not None else "Free"
            click.echo(
                f"  {available} {start:02d}:00-{end:02d}:00  |  {price_str}  |  ID: {slot_id}"
            )

        click.echo()
        click.echo("Use 'nemlig select-slot <ID>' to reserve a slot.")

    except NemligAPIError as e:
        click.echo(f"✗ Failed to get slots: {e}", err=True)
        raise SystemExit(1) from None


@cli.command("select-slot")
@click.argument("slot_id", type=int)
def select_slot(slot_id: int):
    """Select a delivery time slot.

    Reserves the specified delivery slot. The slot ID can be found
    by running 'nemlig slots'.

    Examples:

        nemlig select-slot 2161377
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    try:
        click.echo(f"Selecting slot {slot_id}...")
        result = api.select_delivery_slot(slot_id)

        if result["is_reserved"]:
            minutes = result["minutes_reserved"]
            click.echo(f"✓ Slot reserved for {minutes} minutes")
            click.echo(f"  Timeslot: {result['timeslot_utc']}")
        else:
            click.echo("✗ Failed to reserve slot. It may no longer be available.")
            raise SystemExit(1)

    except NemligAPIError as e:
        click.echo(f"✗ Failed to select slot: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Entry Point
# ============================================================================


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
