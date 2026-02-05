"""CLI entry point for Nemlig Shopper."""

import click

from .api import NemligAPI, NemligAPIError
from .config import clear_credentials, get_credentials, save_credentials
from .recipe_parser import parse_recipe_text, parse_recipe_url

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


# ============================================================================
# Main CLI Group
# ============================================================================


@click.group()
@click.version_option(version="1.0.0", prog_name="nemlig-shopper")
def cli():
    """Nemlig.com Recipe-to-Cart CLI Tool.

    Parse recipes from URLs, search products, and add them to your cart.
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
# Recipe Parsing Command
# ============================================================================


@cli.command("parse")
@click.argument("url", required=False)
@click.option("--text", "-t", "input_text", help="Parse ingredients from text instead of URL")
@click.option("--title", help="Recipe title (for text input)")
@click.option("--servings", "-S", type=int, help="Servings (for text input)")
def parse_recipe_cmd(
    url: str | None,
    input_text: str | None,
    title: str | None,
    servings: int | None,
):
    """Parse a recipe from URL or text and display ingredients.

    Examples:

    \b
        nemlig parse https://valdemarsro.dk/lasagne/
        nemlig parse --text "2 eggs, 100g flour, 1 cup milk"
        nemlig parse --text "eggs, flour" --title "Pancakes"
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
            assert input_text is not None
            # Handle comma-separated input
            if "," in input_text and "\n" not in input_text:
                input_text = input_text.replace(",", "\n")
            recipe = parse_recipe_text(title or "Manual Recipe", input_text, servings)

        # Display recipe
        click.echo()
        servings_str = f" ({recipe.servings} servings)" if recipe.servings else ""
        click.echo(f"Recipe: {recipe.title}{servings_str}")
        click.echo()
        click.echo("Ingredients:")
        for ing in recipe.ingredients:
            # Format: quantity unit name
            qty_str = ""
            if ing.quantity:
                qty_str = f"{ing.quantity:g}" if ing.quantity % 1 == 0 else f"{ing.quantity:.2f}"
            unit_str = f" {ing.unit}" if ing.unit else ""
            qty_unit = f"{qty_str}{unit_str}".ljust(8) if qty_str else "".ljust(8)
            click.echo(f"  {qty_unit} {ing.name}")

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
@click.option("--limit", "-l", default=10, help="Maximum results to show")
def search(query: str, limit: int):
    """Search for products on Nemlig.com.

    Examples:

    \b
        nemlig search mælk
        nemlig search "hakket oksekød" --limit 5
    """
    api = get_api()

    try:
        click.echo(f"Searching for: {query}")
        products = api.search_products(query, limit=limit)

        if not products:
            click.echo("No products found.")
            return

        click.echo()
        click.echo(f"{'ID':<8} {'Name':<28} {'Price':<8} {'Size':<10} Status")
        click.echo("-" * 6 + "   " + "-" * 28 + "  " + "-" * 6 + "   " + "-" * 8 + "   " + "-" * 10)

        for product in products:
            pid = str(product.get("id", ""))[:8]
            name = (product.get("name", "Unknown") or "Unknown")[:28]
            price = product.get("price")
            price_str = f"{price:.2f}" if price else "N/A"
            unit_size = (product.get("unit_size", "") or "")[:10]
            available = "✓ In Stock" if product.get("available", True) else "✗ Sold Out"

            click.echo(f"{pid:<8} {name:<28}  {price_str:<6}   {unit_size:<8}   {available}")

            # Second line with brand, category, and labels
            brand = product.get("brand", "")
            category = product.get("category", "")
            labels_list = []

            # Build label tags
            if product.get("is_refrigerated"):
                labels_list.append("Køl")
            if product.get("is_frozen"):
                labels_list.append("Frost")
            if product.get("is_organic"):
                labels_list.append("Øko")
            if product.get("is_dairy"):
                labels_list.append("Dairy")
            if product.get("is_lactose_free"):
                labels_list.append("Laktosefri")
            if product.get("is_gluten_free"):
                labels_list.append("Glutenfri")
            if product.get("is_vegan"):
                labels_list.append("Vegan")
            if product.get("is_on_discount"):
                labels_list.append("Tilbud")

            labels_str = " ".join(f"[{lbl}]" for lbl in labels_list)
            details = " | ".join(filter(None, [brand, category]))
            if labels_str:
                details = f"{details} | {labels_str}" if details else labels_str

            if details:
                click.echo(f"         {details}")

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
            click.echo("\nUse 'nemlig add <product_id>' to add items.")
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
@click.argument("product_id", type=int)
@click.option("--quantity", "-q", default=1, help="Quantity to add (default: 1)")
def add_to_cart(product_id: int, quantity: int):
    """Add a product to your cart by ID.

    Find product IDs using 'nemlig search <query>'.

    Examples:

    \b
        nemlig add 701015
        nemlig add 103368 --quantity 2
    """
    api = get_api()

    if not ensure_logged_in(api):
        raise SystemExit(1)

    try:
        api.add_to_cart(product_id, quantity)
        click.echo(f"✓ Added {quantity}x product {product_id} to cart")
        click.echo("\nView cart: https://www.nemlig.com/basket")

    except NemligAPIError as e:
        click.echo(f"✗ Failed to add to cart: {e}", err=True)
        raise SystemExit(1) from None


# ============================================================================
# Entry Point
# ============================================================================


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
