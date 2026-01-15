"""CLI entry point for Nemlig Shopper."""

import click

from .api import NemligAPI, NemligAPIError
from .config import clear_credentials, get_credentials, save_credentials
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
    match_ingredients,
    prepare_cart_items,
)
from .planner import (
    MealPlan,
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
from .scaler import format_scale_info, scale_recipe
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
        for cons in plan.consolidated_ingredients:
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
