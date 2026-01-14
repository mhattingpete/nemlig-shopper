"""CLI entry point for Nemlig Shopper."""

import click

from .api import NemligAPI, NemligAPIError
from .config import clear_credentials, get_credentials, save_credentials
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
from .preferences import (
    PreferencesError,
    clear_preferences,
    get_last_sync_time,
    get_preference_count,
    sync_preferences_from_orders,
)
from .recipe_parser import Recipe, parse_recipe_text, parse_recipe_url
from .scaler import format_scale_info, scale_recipe

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

    for i, match in enumerate(matches, 1):
        if match.matched:
            matched_count += 1
            price_str = f"{match.price:.2f} DKK" if match.price else "N/A"
            click.echo(f"\n{i}. {match.ingredient_name}")
            click.echo(f"   → {match.product_name} (x{match.quantity})")
            click.echo(f"   Price: {price_str}")

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
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--save-as", help="Save as favorite with this name")
def add_to_cart(
    url: str, scale: float | None, servings: int | None, yes: bool, save_as: str | None
):
    """Parse a recipe and add matched products to cart."""
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

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

        # Match ingredients to products
        click.echo("Matching ingredients to products...")
        matches = match_ingredients(api, scaled_ings)

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
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--rematch", is_flag=True, help="Re-match products instead of using saved matches")
def favorites_order(name: str, scale: float | None, servings: int | None, yes: bool, rematch: bool):
    """Order a favorite recipe to cart."""
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

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

        # Use saved matches or re-match
        if not rematch and favorite.get("product_matches") and factor == 1.0:
            # Use saved product IDs (quick re-order)
            click.echo("Using saved product matches...")
            cart_items = get_favorite_product_ids(name)
        else:
            # Re-match products (needed for scaling or if no saved matches)
            click.echo("Matching ingredients to products...")
            matches = match_ingredients(api, scaled_ings)
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
def favorites_update(name: str):
    """Re-match products for a saved favorite."""
    api = get_api()

    try:
        recipe = get_favorite_recipe(name)

        click.echo(f"Re-matching products for: {recipe.title}")

        # Scale with factor 1.0 (no scaling)
        scaled_ings, _, _ = scale_recipe(recipe)

        # Match products
        matches = match_ingredients(api, scaled_ings)
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
# Entry Point
# ============================================================================


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
