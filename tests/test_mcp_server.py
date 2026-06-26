"""Tests for the MCP server tools (in-memory FastMCP client + respx mocks)."""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from nemlig_shopper.api import SEARCH_GATEWAY_URL
from nemlig_shopper.mcp_server import Product, _rank, mcp


def _make_product(
    id: int | str = 1,
    name: str = "vare",
    price: float = 10.0,
    available: bool = True,
    is_organic: bool = False,
    is_frozen: bool = False,
) -> Product:
    return Product(
        id=id,
        name=name,
        price=price,
        unit_price=None,
        unit_size=None,
        brand=None,
        available=available,
        is_organic=is_organic,
        is_frozen=is_frozen,
        is_on_discount=False,
        image_url=None,
    )


@pytest.fixture(autouse=True)
def reset_api_singleton(monkeypatch):
    """Each test gets a fresh NemligAPI (the server shares cli's singleton)."""
    import nemlig_shopper.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_api", None)


def _call(name: str, args: dict):
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, args)

    return asyncio.run(go())


def _tool_names() -> set[str]:
    async def go():
        async with Client(mcp) as client:
            return {t.name for t in await client.list_tools()}

    return asyncio.run(go())


# ============================================================================
# Product model
# ============================================================================


class TestProductModel:
    def test_from_api_maps_fields(self):
        product = Product.from_api(
            {
                "id": 100001,
                "name": "Økologisk Sødmælk",
                "price": 15.95,
                "unit_price_calc": 15.95,
                "unit_size": "1 liter",
                "brand": "Arla",
                "available": True,
                "is_organic": True,
            }
        )
        assert product.id == 100001
        assert product.unit_price == 15.95
        assert product.is_organic is True
        assert product.tags == []

    def test_from_api_tolerates_missing(self):
        product = Product.from_api({})
        assert product.name is None
        assert product.available is True  # defaults to available


# ============================================================================
# Tool surface (cart-only: no checkout)
# ============================================================================


class TestToolSurface:
    def test_expected_tools_present(self):
        names = _tool_names()
        assert {
            "search_products",
            "parse_recipe",
            "add_to_cart",
            "view_cart",
            "clear_cart",
        } <= names

    def test_no_checkout_tool(self):
        names = _tool_names()
        assert not any(
            kw in n.lower() for n in names for kw in ("checkout", "order", "pay", "purchase")
        )


# ============================================================================
# search_products ranking
# ============================================================================


class TestSearchProducts:
    def test_returns_ranked_tagged_products(self, setup_session_mocks, mock_search_response):
        setup_session_mocks.get(f"{SEARCH_GATEWAY_URL}/search").respond(json=mock_search_response)

        result = _call("search_products", {"query": "mælk", "limit": 5})
        # FastMCP wraps a list return under {"result": [...]} in structured content.
        products = result.structured_content["result"]

        assert products
        milk = next(p for p in products if p["name"] == "Økologisk Sødmælk")
        assert "organic" in milk["tags"]
        assert "cheapest" in milk["tags"]
        assert "recommended" in milk["tags"]


# ============================================================================
# Picker widget (MCP Apps) — headless: registration + fallback only
# ============================================================================


class TestPickerWidget:
    def test_pick_products_tool_present(self):
        assert "pick_products" in _tool_names()

    def test_pick_products_returns_fallback_list(self, setup_session_mocks, mock_search_response):
        setup_session_mocks.get(f"{SEARCH_GATEWAY_URL}/search").respond(json=mock_search_response)
        result = _call("pick_products", {"query": "mælk", "limit": 5})
        products = result.structured_content["result"]
        assert any(p["name"] == "Økologisk Sødmælk" for p in products)

    def test_picker_resource_is_interactive_html(self):
        async def go():
            async with Client(mcp) as client:
                return await client.read_resource("ui://nemlig/picker.html")

        contents = asyncio.run(go())
        html = contents[0].text
        assert "<!DOCTYPE html>" in html
        assert "add_to_cart" in html  # the widget calls back into the cart tool
        assert "ext-apps" in html  # uses the MCP Apps host bridge

    def test_pick_and_search_return_same_data(self, setup_session_mocks, mock_search_response):
        # Both delegate to _search; this guards against future divergence.
        setup_session_mocks.get(f"{SEARCH_GATEWAY_URL}/search").respond(json=mock_search_response)
        search = _call("search_products", {"query": "mælk", "limit": 5})
        setup_session_mocks.get(f"{SEARCH_GATEWAY_URL}/search").respond(json=mock_search_response)
        pick = _call("pick_products", {"query": "mælk", "limit": 5})
        assert search.structured_content == pick.structured_content


# ============================================================================
# _rank tagging (pure function — no HTTP)
# ============================================================================


class TestRank:
    def test_cheapest_is_lowest_priced_available(self):
        pricey = _make_product(id=1, name="dyr mælk", price=20.0)
        cheap = _make_product(id=2, name="billig mælk", price=12.5)
        _rank([pricey, cheap], "mælk")
        assert "cheapest" in cheap.tags
        assert "cheapest" not in pricey.tags

    def test_recommended_skips_frozen(self):
        frozen = _make_product(id=1, name="frossen mælk", is_frozen=True)
        fresh = _make_product(id=2, name="frisk mælk", is_frozen=False)
        _rank([frozen, fresh], "mælk")
        assert "recommended" in fresh.tags
        assert "recommended" not in frozen.tags

    def test_organic_tagged(self):
        eco = _make_product(name="øko mælk", is_organic=True)
        _rank([eco], "mælk")
        assert "organic" in eco.tags

    def test_unavailable_gets_no_cheapest(self):
        out = _make_product(available=False, is_organic=True)
        _rank([out], "mælk")
        assert "cheapest" not in out.tags
        assert "organic" in out.tags  # organic still tagged regardless of stock

    def test_empty_list(self):
        assert _rank([], "mælk") == []


# ============================================================================
# Graceful auth failure (never a traceback)
# ============================================================================


class TestAuthFailure:
    def test_view_cart_without_credentials_raises_clean_error(self, monkeypatch, tmp_path):
        monkeypatch.delenv("NEMLIG_USERNAME", raising=False)
        monkeypatch.delenv("NEMLIG_PASSWORD", raising=False)
        monkeypatch.setattr("nemlig_shopper.config.CREDENTIALS_FILE", tmp_path / "missing.json")

        with pytest.raises(ToolError) as exc:
            _call("view_cart", {})
        assert "credentials" in str(exc.value).lower()
