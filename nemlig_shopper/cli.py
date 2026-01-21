"""CLI entry point for Nemlig Shopper."""

import click

from .api import NemligAPI, NemligAPIError
from .config import PANTRY_FILE, clear_credentials, get_credentials, save_credentials
from .export import export_shopping_list
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
    load_pantry,
    remove_from_pantry,
)
from .pantry_tui import interactive_pantry_check, simple_pantry_prompt
from .planner import consolidate_ingredients
from .preferences import (
    PreferencesError,
    clear_preferences,
    get_last_sync_time,
    get_preference_count,
    sync_preferences_from_orders,
)
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
@click.argument("url", required=False)
@click.option("--text", "-t", "input_text", help="Parse ingredients from text instead of URL")
@click.option("--title", help="Recipe title (for text input)")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier (e.g., 2 for double)")
@click.option("--servings", "-S", type=int, help="Scale to target servings")
def parse_recipe_cmd(
    url: str | None,
    input_text: str | None,
    title: str | None,
    scale: float | None,
    servings: int | None,
):
    """Parse a recipe from URL or text (without adding to cart).

    Examples:

    \b
        nemlig parse https://recipe.com/pasta
        nemlig parse --text "2 eggs, 100g flour, 1 cup milk"
        nemlig parse --text "eggs, flour" --title "Pancakes"
        nemlig parse https://recipe.com/pasta --scale 2
    """
    if not url and not input_text:
        click.echo("✗ Provide a URL or use --text for manual input.", err=True)
        raise SystemExit(1)

    if url and input_text:
        click.echo("✗ Provide either URL or --text, not both.", err=True)
        raise SystemExit(1)

    try:
        if url:
            click.echo(f"Parsing recipe from: {url}")
            recipe = parse_recipe_url(url)
        else:
            assert input_text is not None  # Validated above
            # Handle comma-separated input
            if "," in input_text and "\n" not in input_text:
                input_text = input_text.replace(",", "\n")
            recipe = parse_recipe_text(title or "Manual Recipe", input_text, servings)

        # Apply scaling if requested
        if scale or servings:
            scaled_ings, factor, new_servings = scale_recipe(
                recipe, target_servings=servings, multiplier=scale
            )
            scale_info = format_scale_info(factor, recipe.servings, new_servings)
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
        click.echo("View online: https://www.nemlig.com/basket")

    except NemligAPIError as e:
        click.echo(f"✗ Failed to get cart: {e}", err=True)
        raise SystemExit(1) from None


@cli.command("add")
@click.argument("urls", nargs=-1)
@click.option("--text", "-t", "input_text", help="Shopping list as inline text (URLs and/or items)")
@click.option("--file", "-f", "file_path", type=click.Path(exists=True), help="Load from file")
@click.option("--scale", "-s", type=float, help="Scale recipe by multiplier (single URL only)")
@click.option("--servings", "-S", type=int, help="Scale to target servings (single URL only)")
@click.option("--organic", "-o", is_flag=True, help="Prefer organic (within threshold of cheapest)")
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
@click.option("--remember-pantry", is_flag=True, help="Remember excluded items as pantry")
@click.option("--skip-ambiguous-check", is_flag=True, help="Skip prompts for ambiguous items")
@click.option("--dry-run", is_flag=True, help="Show what would be added without adding to cart")
def add_to_cart(
    urls: tuple[str, ...],
    input_text: str | None,
    file_path: str | None,
    scale: float | None,
    servings: int | None,
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
    remember_pantry: bool,
    skip_ambiguous_check: bool,
    dry_run: bool,
):
    """Parse recipes and/or items and add matched products to cart.

    Accepts recipe URLs, manual items, or both. Ingredients are consolidated
    when multiple sources are provided.

    Examples:

    \b
        # Single recipe
        nemlig add https://recipe.com/pasta

    \b
        # Multiple recipes (ingredients consolidated)
        nemlig add https://recipe1.com https://recipe2.com

    \b
        # Manual items
        nemlig add --text "mælk, brød, æg"

    \b
        # Mixed input (recipe + manual items)
        nemlig add --text "https://recipe.com
        mælk
        brød"

    \b
        # From file
        nemlig add --file shopping-list.txt

    \b
        # Scale a single recipe
        nemlig add https://recipe.com --scale 2
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

    # Collect all URLs and manual items
    all_urls: list[str] = list(urls)
    manual_items: list[tuple[str, str | None]] = []  # (item, meal_context)

    # Parse --text or --file input
    if input_text == "-":
        import sys

        input_text = sys.stdin.read()
    elif file_path:
        with open(file_path) as f:
            input_text = f.read()

    if input_text:
        # Handle comma-separated items
        if "," in input_text and "\n" not in input_text:
            input_text = input_text.replace(",", "\n")
        text_urls, text_items = parse_shopping_text(input_text)
        all_urls.extend(text_urls)
        manual_items.extend(text_items)

    # Validate input
    if not all_urls and not manual_items:
        click.echo("✗ No input provided. Use URLs, --text, or --file.", err=True)
        raise SystemExit(1)

    # Validate scaling (only for single URL, no manual items)
    if (scale or servings) and (len(all_urls) != 1 or manual_items):
        click.echo("✗ --scale/--servings only works with a single recipe URL.", err=True)
        raise SystemExit(1)

    try:
        # Store (ScaledIngredient, source, meal_context) tuples
        all_ingredients: list[tuple[ScaledIngredient, str, str | None]] = []
        recipes: list[Recipe] = []

        # Parse recipes from URLs
        if all_urls:
            click.echo(f"Parsing {len(all_urls)} recipe(s)...")
            for url in all_urls:
                try:
                    recipe = parse_recipe_url(url)
                    recipes.append(recipe)
                    click.echo(f"  ✓ {recipe.title}")

                    # Derive meal context from recipe title
                    recipe_context = recipe.title.lower() if recipe.title else None

                    # Scale ingredients
                    scaled_ings, factor, new_servings = scale_recipe(
                        recipe, target_servings=servings, multiplier=scale
                    )

                    if factor != 1.0:
                        scale_info = format_scale_info(factor, recipe.servings, new_servings)
                        click.echo(f"    Scaling: {scale_info}")

                    for ing in scaled_ings:
                        all_ingredients.append((ing, recipe.title, recipe_context))
                except Exception as e:
                    click.echo(f"  ✗ Failed to parse {url}: {e}", err=True)

        # Parse manual items
        if manual_items:
            click.echo(f"\nManual items ({len(manual_items)}):")
            from .recipe_parser import parse_ingredient_text

            for item, meal_context in manual_items:
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
            click.echo("✗ No ingredients to add.", err=True)
            raise SystemExit(1)

        # Build meal context mapping before consolidation
        ingredient_context_map: dict[str, str | None] = {}
        for ing, _source, meal_context in all_ingredients:
            name_lower = ing.name.lower()
            if name_lower not in ingredient_context_map and meal_context:
                ingredient_context_map[name_lower] = meal_context

        # Consolidate ingredients
        ingredients_for_consolidation = [(ing, source) for ing, source, _ in all_ingredients]
        consolidated = consolidate_ingredients(ingredients_for_consolidation)

        if len(all_urls) > 1 or manual_items:
            click.echo(f"\nConsolidated to {len(consolidated)} unique ingredients")

        # Pantry check
        consolidated_to_match = consolidated
        if not skip_pantry_check:
            pantry_items = load_pantry(PANTRY_FILE)
            pantry_candidates, _ = identify_pantry_items(consolidated, pantry_items)

            if pantry_candidates:
                click.echo(f"\nFound {len(pantry_candidates)} potential pantry items.")

                if interactive:
                    title = recipes[0].title if len(recipes) == 1 else "Shopping List"
                    pantry_result = interactive_pantry_check(
                        pantry_candidates, f"Pantry Check - {title}"
                    )
                else:
                    pantry_result = simple_pantry_prompt(pantry_candidates)

                if not pantry_result.confirmed:
                    click.echo("Cancelled.")
                    return

                if pantry_result.excluded_items:
                    click.echo(f"Excluding {len(pantry_result.excluded_items)} pantry items.")
                    if remember_pantry:
                        add_to_pantry(pantry_result.excluded_items, PANTRY_FILE)
                        click.echo("✓ Saved excluded items to your pantry")

                    consolidated_to_match = filter_pantry_items(
                        consolidated, pantry_result.excluded_items
                    )

        # Handle ambiguous terms
        if not skip_ambiguous_check and not yes:
            ambiguous_items = [c for c in consolidated_to_match if is_ambiguous_term(c.name)]
            if ambiguous_items:
                click.echo(f"\n⚠ Found {len(ambiguous_items)} ambiguous item(s):")
                items_to_skip = []
                items_to_replace = {}

                for item in ambiguous_items:
                    click.echo(f"\n  '{item.name}' is ambiguous.")
                    click.echo("  Options: 1=Skip, 2=Specify replacement, 3=Keep as-is")
                    choice = click.prompt(
                        "  Choice", type=click.Choice(["1", "2", "3"]), default="3"
                    )

                    if choice == "1":
                        items_to_skip.append(item.name.lower())
                    elif choice == "2":
                        replacement = click.prompt("  Search for instead")
                        if replacement:
                            items_to_replace[item.name.lower()] = replacement

                if items_to_skip or items_to_replace:
                    from .planner import ConsolidatedIngredient

                    filtered = []
                    for cons in consolidated_to_match:
                        name_lower = cons.name.lower()
                        if name_lower in items_to_skip:
                            continue
                        if name_lower in items_to_replace:
                            cons = ConsolidatedIngredient(
                                name=items_to_replace[name_lower],
                                total_quantity=cons.total_quantity,
                                unit=cons.unit,
                                sources=cons.sources,
                            )
                        filtered.append(cons)
                    consolidated_to_match = filtered

        # Determine preference mode
        # Default: auto_preference (budget for most items, smart-organic for produce)
        # Explicit flags override auto mode
        use_auto_preference = not organic and not budget and not no_organic
        use_prefer_organic = organic and not budget
        use_smart_organic = False  # Only used when explicitly set or via auto
        use_prefer_budget = budget

        # Show preference mode
        if use_prefer_organic:
            click.echo("\nMode: Always preferring organic products")
        elif use_auto_preference:
            click.echo(
                f"\nMode: Auto (budget for most, smart organic for produce within {organic_threshold:.0f} DKK)"
            )
        elif use_prefer_budget:
            click.echo("\nMode: Preferring budget-friendly products")
        elif no_organic:
            click.echo("\nMode: Budget (organic preference disabled)")
            use_prefer_budget = True
        if allergies or dietary:
            click.echo(f"Dietary filters: {', '.join(allergies + dietary)}")

        # Match ingredients to products
        click.echo("\nMatching ingredients to products...")
        matches = []
        for cons in consolidated_to_match:
            meal_context = ingredient_context_map.get(cons.name.lower())
            match = match_ingredient(
                api,
                cons.name,
                cons.total_quantity,
                cons.unit,
                prefer_organic=use_prefer_organic,
                prefer_budget=use_prefer_budget,
                smart_organic=use_smart_organic,
                organic_price_threshold=organic_threshold,
                meal_context=meal_context,
                allergies=allergies if allergies else None,
                dietary=dietary if dietary else None,
                auto_preference=use_auto_preference,
            )
            matches.append(match)

        # Review matches
        if interactive:
            title = recipes[0].title if len(recipes) == 1 else f"Shopping ({len(recipes)} recipes)"
            review_result = interactive_review(matches, title)
            if not review_result.confirmed:
                click.echo("Cancelled.")
                return
            matches = review_result.matches
        else:
            display_matches(matches, show_alternatives=True)

            unmatched = get_unmatched_ingredients(matches)
            if unmatched:
                click.echo(f"\n⚠ {len(unmatched)} ingredients could not be matched:")
                for name in unmatched:
                    click.echo(f"  - {name}")

        # Dry run - just show what would be added
        if dry_run:
            click.echo("\n--- DRY RUN ---")
            total = calculate_total_cost(matches)
            matched_count = sum(1 for m in matches if m.matched)
            click.echo(f"Would add {matched_count} products, estimated {total:.2f} DKK")
            click.echo("Run without --dry-run to add to cart.")
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

        click.echo("\nView cart: https://www.nemlig.com/basket")

    except ImportError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Helper Functions
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
    """List your pantry items.

    Edit the pantry file directly at ~/.nemlig-shopper/pantry.txt
    """
    items = load_pantry(PANTRY_FILE)

    click.echo()
    click.echo("YOUR PANTRY")
    click.echo("=" * 50)

    if items:
        for item in sorted(items):
            click.echo(f"  {item}")
    else:
        click.echo("  (empty)")

    click.echo()
    click.echo(f"Total: {len(items)} items")
    click.echo(f"File: {PANTRY_FILE}")
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
