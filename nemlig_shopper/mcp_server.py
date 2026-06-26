"""MCP server exposing Nemlig.com shopping as tools for Claude clients.

Cart-only: it searches, parses recipes, and fills the basket, but never places an
order. Run via `nemlig-mcp` (stdio) and wire into a client's MCP config.
"""

import functools

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from .api import NemligAPI, NemligAPIError
from .cli import get_api
from .config import get_credentials
from .recipe_parser import parse_recipe_text, parse_recipe_url

# mask_error_details hides unexpected internals; the _tool decorator turns expected
# Nemlig/runtime errors into clean ToolErrors so Claude never sees a traceback.
mcp = FastMCP(name="nemlig-shopper", mask_error_details=True)


class Product(BaseModel):
    """A Nemlig product candidate, tagged to help the user choose."""

    id: int | str | None
    name: str | None
    price: float | None
    unit_price: float | None  # price per kg/l/etc., for comparing value
    unit_size: str | None
    brand: str | None
    available: bool
    is_organic: bool
    is_frozen: bool
    is_on_discount: bool
    image_url: str | None
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict) -> "Product":
        return cls(
            id=d.get("id"),
            name=d.get("name"),
            price=d.get("price"),
            unit_price=d.get("unit_price_calc"),
            unit_size=d.get("unit_size") or None,
            brand=d.get("brand") or None,
            available=bool(d.get("available", True)),
            is_organic=bool(d.get("is_organic", False)),
            is_frozen=bool(d.get("is_frozen", False)),
            is_on_discount=bool(d.get("is_on_discount", False)),
            image_url=d.get("image_url") or None,
        )


def _rank(products: list[Product], query: str) -> list[Product]:
    """Tag candidates 'cheapest' / 'recommended' / 'organic' for easy picking."""
    available = [p for p in products if p.available]
    if available:
        cheapest = min(available, key=lambda p: p.price if p.price is not None else float("inf"))
        cheapest.tags.append("cheapest")
        kw = query.split()[0].lower() if query.split() else ""
        for p in available:
            if not p.is_frozen and (not kw or (p.name and kw in p.name.lower())):
                p.tags.append("recommended")
                break
    for p in products:
        if p.is_organic:
            p.tags.append("organic")
    return products


def _login_or_error() -> NemligAPI:
    """Return a logged-in client, or raise a clean ToolError (never a traceback)."""
    api = get_api()
    if api.is_logged_in():
        return api
    username, password = get_credentials()
    if not username or not password:
        raise ToolError(
            "No Nemlig credentials configured. Set NEMLIG_USERNAME and NEMLIG_PASSWORD, "
            "or run `nemlig login` once."
        )
    try:
        api.login(username, password)
    except NemligAPIError as e:
        raise ToolError(f"Nemlig login failed: {e}") from None
    return api


def _tool(fn):
    """Register an MCP tool, converting Nemlig/runtime errors into clean ToolErrors."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except NemligAPIError as e:
            raise ToolError(str(e)) from None
        except Exception as e:
            raise ToolError(f"{fn.__name__} failed: {e}") from None

    return mcp.tool(wrapper)


@_tool
def search_products(query: str, limit: int = 8) -> list[Product]:
    """Search Nemlig.com for grocery products. Use Danish search terms for best results
    (e.g. 'mælk', 'hakket oksekød'). Returns ranked candidates tagged 'cheapest',
    'recommended', and/or 'organic' so you can present clear choices to the user."""
    raw = get_api().search_products(query, limit=limit)
    return _rank([Product.from_api(d) for d in raw], query)


@_tool
def parse_recipe(url_or_text: str) -> dict:
    """Parse a recipe from a URL or a free-text ingredient list into title + ingredients
    (each with quantity/unit/name). Use this to expand recipe lines from a shopping list,
    then call search_products for each ingredient."""
    text = url_or_text.strip()
    if text.lower().startswith(("http://", "https://")):
        recipe = parse_recipe_url(text)
    else:
        recipe = parse_recipe_text("Recipe", text, None)
    return recipe.to_dict()


@_tool
def add_to_cart(product_id: int, quantity: int = 1) -> str:
    """Add `quantity` of a Nemlig product (numeric id from search_products) to the basket."""
    if quantity < 1:
        raise ToolError("quantity must be at least 1")
    _login_or_error().add_to_cart(product_id, quantity)
    return f"Added {quantity}× product {product_id} to the basket."


@_tool
def view_cart() -> dict:
    """Show the current Nemlig basket: line items (name, quantity, line total) and totals."""
    cart = _login_or_error().get_cart()
    lines = cart.get("Lines", []) or []
    return {
        "items": [
            {
                "name": line.get("ProductName"),
                "quantity": line.get("Quantity"),
                "total": line.get("Total"),
            }
            for line in lines
        ],
        "products_price": cart.get("TotalProductsPrice"),
        "delivery_price": cart.get("DeliveryPrice"),
        "number_of_products": cart.get("NumberOfProducts"),
        "delivery_time": cart.get("FormattedDeliveryTime"),
    }


@_tool
def clear_cart() -> str:
    """Remove all items from the Nemlig basket."""
    _login_or_error().clear_cart()
    return "Basket cleared."


def main():
    """Entry point for the `nemlig-mcp` stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
