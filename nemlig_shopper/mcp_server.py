"""MCP server exposing Nemlig.com shopping as tools for Claude clients.

Cart-only: it searches, parses recipes, and fills the basket, but never places an
order. Run via `nemlig-mcp` (stdio) and wire into a client's MCP config.
"""

import functools

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from .api import NemligAPI, NemligAPIError
from .cli import get_api
from .config import get_credentials
from .recipe_parser import parse_recipe_text, parse_recipe_url

# mask_error_details hides unexpected internals; the _tool decorator turns expected
# Nemlig/runtime errors into clean ToolErrors so Claude never sees a traceback.
mcp = FastMCP(name="nemlig-shopper", mask_error_details=True)

PICKER_URI = "ui://nemlig/picker.html"


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


def _tool(fn=None, *, app=None):
    """Register an MCP tool, converting Nemlig/runtime errors into clean ToolErrors.

    Use bare `@_tool` or `@_tool(app=AppConfig(...))` to attach an MCP Apps UI.
    """

    def decorate(target):
        @functools.wraps(target)
        def wrapper(*args, **kwargs):
            try:
                return target(*args, **kwargs)
            except ToolError:
                raise
            except NemligAPIError as e:
                raise ToolError(str(e)) from None
            except Exception as e:
                raise ToolError(f"{target.__name__} failed: {e}") from None

        return mcp.tool(wrapper, app=app) if app is not None else mcp.tool(wrapper)

    return decorate(fn) if fn is not None else decorate


def _search(query: str, limit: int) -> list[Product]:
    raw = get_api().search_products(query, limit=limit)
    return _rank([Product.from_api(d) for d in raw], query)


@_tool
def search_products(query: str, limit: int = 8) -> list[Product]:
    """Search Nemlig.com for grocery products. Use Danish search terms for best results
    (e.g. 'mælk', 'hakket oksekød'). Returns ranked candidates tagged 'cheapest',
    'recommended', and/or 'organic' so you can present clear choices to the user."""
    return _search(query, limit)


@_tool(app=AppConfig(resource_uri=PICKER_URI))
def pick_products(query: str, limit: int = 8) -> list[Product]:
    """Show the user an interactive picker to choose a product among candidates.

    Prefer this over search_products when you want the user to choose — several options
    are reasonable, or you're unsure which they'd prefer. Clients that render MCP Apps show
    clickable cards (each 'Add' button adds that product); other clients fall back to the
    same candidate list for conversational picking."""
    return _search(query, limit)


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


# Interactive product-picker widget (MCP Apps). Rendered by `pick_products`; clients that
# can't render it fall back to the tool's structured list. Loads the ext-apps bridge from
# unpkg (allowed via the resource CSP) and calls `add_to_cart` on click.
_PICKER_HTML = """<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8" />
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 12px; color: #1a1a1a; }
  .grid { display: grid; gap: 10px; }
  .card { border: 1px solid #e3e3e3; border-radius: 10px; padding: 12px; display: flex; gap: 12px; justify-content: space-between; align-items: center; }
  .info { min-width: 0; }
  .name { font-weight: 600; }
  .meta { color: #666; font-size: 13px; margin-top: 2px; }
  .badges { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
  .badge { font-size: 11px; padding: 2px 7px; border-radius: 999px; background: #eef; color: #335; }
  .badge.cheapest { background: #e6f6ea; color: #1c6b34; }
  .badge.recommended { background: #fff2da; color: #8a5b00; }
  .badge.organic { background: #e9f7e1; color: #2c6e1f; }
  .right { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; }
  .price { font-weight: 700; white-space: nowrap; }
  button { padding: 8px 14px; border: 0; border-radius: 8px; background: #0a7d33; color: #fff; font-weight: 600; cursor: pointer; }
  button:disabled { background: #9bbfa6; cursor: default; }
  .empty { color: #777; padding: 16px; }
</style>
</head>
<body>
  <div id="root"><div class="empty">Henter varer…</div></div>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";

    const root = document.getElementById("root");
    const app = new App({ name: "Nemlig Picker", version: "1.0.0" });
    const kr = (v) => (typeof v === "number" ? v.toFixed(2).replace(".", ",") + " kr." : "");

    function productsFrom(content) {
      const text = (content || []).find((c) => c.type === "text");
      if (!text) return [];
      let data;
      try { data = JSON.parse(text.text); } catch { return []; }
      if (Array.isArray(data)) return data;
      return data.result || data.items || [];
    }

    function render(products) {
      if (!products.length) { root.innerHTML = '<div class="empty">Ingen varer fundet.</div>'; return; }
      const grid = document.createElement("div");
      grid.className = "grid";
      for (const p of products) {
        const card = document.createElement("div");
        card.className = "card";
        const tags = (p.tags || []).map((t) => `<span class="badge ${t}">${t}</span>`).join("");
        const unit = p.unit_price ? ` · ${kr(p.unit_price)}/enhed` : "";
        const size = p.unit_size ? ` · ${p.unit_size}` : "";
        card.innerHTML =
          `<div class="info">
             <div class="name"></div>
             <div class="meta"></div>
             <div class="badges">${tags}</div>
           </div>
           <div class="right"><div class="price">${kr(p.price)}</div></div>`;
        card.querySelector(".name").textContent = p.name ?? "Ukendt vare";
        card.querySelector(".meta").textContent = `${p.brand ?? ""}${size}${unit}`;
        const btn = document.createElement("button");
        btn.textContent = "Tilføj";
        btn.disabled = !p.available || p.id == null;
        btn.onclick = async () => {
          btn.disabled = true; btn.textContent = "Tilføjer…";
          try {
            await app.callServerTool({ name: "add_to_cart", arguments: { product_id: p.id, quantity: 1 } });
            btn.textContent = "Tilføjet ✓";
          } catch {
            btn.textContent = "Fejl"; btn.disabled = false;
          }
        };
        card.querySelector(".right").appendChild(btn);
        grid.appendChild(card);
      }
      root.replaceChildren(grid);
    }

    app.ontoolresult = ({ content }) => render(productsFrom(content));
    await app.connect();
  </script>
</body>
</html>"""


@mcp.resource(
    PICKER_URI,
    app=AppConfig(csp=ResourceCSP(resource_domains=["https://unpkg.com"])),
)
def _picker_widget() -> str:
    """Interactive product-picker UI (MCP Apps), rendered by `pick_products`."""
    return _PICKER_HTML


def main():
    """Entry point for the `nemlig-mcp` stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
