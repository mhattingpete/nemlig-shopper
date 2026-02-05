"""Tests for the CLI module."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nemlig_shopper.api import NemligAPIError
from nemlig_shopper.cli import cli
from nemlig_shopper.recipe_parser import Ingredient, Recipe


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_api():
    """Create a mock API client."""
    api = MagicMock()
    api.is_logged_in.return_value = False
    api._logged_in = False
    return api


@pytest.fixture
def mock_api_logged_in():
    """Create a mock API client that's already logged in."""
    api = MagicMock()
    api.is_logged_in.return_value = True
    api._logged_in = True
    return api


@pytest.fixture
def sample_recipe():
    """Create a sample recipe for testing."""
    return Recipe(
        title="Test Recipe",
        ingredients=[
            Ingredient(original="2 eggs", name="eggs", quantity=2.0, unit=""),
            Ingredient(original="200g flour", name="flour", quantity=200.0, unit="g"),
            Ingredient(original="1 cup milk", name="milk", quantity=1.0, unit="cup"),
        ],
        servings=4,
        source_url="https://example.com/recipe",
    )


@pytest.fixture
def sample_products():
    """Sample product search results."""
    return [
        {
            "id": 1001,
            "name": "Økologiske Æg 10 stk",
            "price": 35.95,
            "unit_size": "10 stk",
            "brand": "Arla",
            "category": "Mejeri",
            "available": True,
            "is_organic": True,
            "is_dairy": True,
            "is_refrigerated": True,
            "is_frozen": False,
            "is_lactose_free": False,
            "is_gluten_free": False,
            "is_vegan": False,
            "is_on_discount": False,
        },
        {
            "id": 1002,
            "name": "Hvedemel",
            "price": 12.95,
            "unit_size": "1 kg",
            "brand": "Valsemøllen",
            "category": "Kolonial",
            "available": True,
            "is_organic": False,
            "is_dairy": False,
            "is_refrigerated": False,
            "is_frozen": False,
            "is_lactose_free": False,
            "is_gluten_free": False,
            "is_vegan": True,
            "is_on_discount": True,
        },
    ]


# ============================================================================
# Main CLI Tests
# ============================================================================


class TestMainCli:
    """Tests for the main CLI group."""

    def test_cli_help(self, runner):
        """CLI should display help information."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Nemlig.com Recipe-to-Cart CLI Tool" in result.output

    def test_cli_version(self, runner):
        """CLI should display version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_shows_commands(self, runner):
        """CLI help should show all available commands."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Verify the 6 expected commands are listed
        assert "login" in result.output
        assert "logout" in result.output
        assert "parse" in result.output
        assert "search" in result.output
        assert "add" in result.output
        assert "cart" in result.output


# ============================================================================
# Authentication Command Tests
# ============================================================================


class TestLoginCommand:
    """Tests for the login command."""

    def test_login_success(self, runner, mock_api):
        """Successful login should save credentials."""
        mock_api.login.return_value = True

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.save_credentials") as mock_save:
                result = runner.invoke(
                    cli, ["login", "-u", "test@example.com", "-p", "password123"]
                )

        assert result.exit_code == 0
        assert "Login successful" in result.output
        assert "Credentials saved" in result.output
        mock_api.login.assert_called_once_with("test@example.com", "password123")
        mock_save.assert_called_once_with("test@example.com", "password123")

    def test_login_no_save(self, runner, mock_api):
        """Login with --no-save should not save credentials."""
        mock_api.login.return_value = True

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.save_credentials") as mock_save:
                result = runner.invoke(
                    cli,
                    ["login", "-u", "test@example.com", "-p", "password123", "--no-save"],
                )

        assert result.exit_code == 0
        assert "Login successful" in result.output
        assert "Credentials saved" not in result.output
        mock_save.assert_not_called()

    def test_login_failure(self, runner, mock_api):
        """Failed login should display error and exit with code 1."""
        mock_api.login.side_effect = NemligAPIError("Invalid credentials")

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["login", "-u", "wrong@example.com", "-p", "wrongpass"])

        assert result.exit_code == 1
        assert "Login failed" in result.output


class TestLogoutCommand:
    """Tests for the logout command."""

    def test_logout_clears_credentials(self, runner):
        """Logout should clear saved credentials."""
        with patch("nemlig_shopper.cli.clear_credentials") as mock_clear:
            result = runner.invoke(cli, ["logout"])

        assert result.exit_code == 0
        assert "Credentials cleared" in result.output
        mock_clear.assert_called_once()


# ============================================================================
# Search Command Tests
# ============================================================================


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_with_results(self, runner, mock_api, sample_products):
        """Search should display found products."""
        mock_api.search_products.return_value = sample_products

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["search", "æg"])

        assert result.exit_code == 0
        assert "Økologiske Æg" in result.output
        assert "35.95" in result.output

    def test_search_no_results(self, runner, mock_api):
        """Search with no results should display message."""
        mock_api.search_products.return_value = []

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["search", "nonexistent"])

        assert result.exit_code == 0
        assert "No products found" in result.output

    def test_search_with_limit(self, runner, mock_api, sample_products):
        """Search should respect limit parameter."""
        mock_api.search_products.return_value = sample_products[:1]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            runner.invoke(cli, ["search", "æg", "--limit", "1"])

        mock_api.search_products.assert_called_once_with("æg", limit=1)

    def test_search_api_error(self, runner, mock_api):
        """Search API error should display error and exit."""
        mock_api.search_products.side_effect = NemligAPIError("API error")

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["search", "test"])

        assert result.exit_code == 1
        assert "Search failed" in result.output

    def test_search_displays_product_labels(self, runner, mock_api, sample_products):
        """Search should display product labels like organic, discount."""
        mock_api.search_products.return_value = sample_products

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["search", "æg"])

        assert result.exit_code == 0
        # First product has organic and dairy labels
        assert "[Øko]" in result.output
        assert "[Dairy]" in result.output
        # Second product has discount
        assert "[Tilbud]" in result.output


# ============================================================================
# Parse Command Tests
# ============================================================================


class TestParseCommand:
    """Tests for the parse command."""

    def test_parse_url_success(self, runner, sample_recipe):
        """Parse should display recipe information."""
        with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
            result = runner.invoke(cli, ["parse", "https://example.com/recipe"])

        assert result.exit_code == 0
        assert "Recipe: Test Recipe" in result.output
        assert "4 servings" in result.output
        assert "eggs" in result.output
        assert "flour" in result.output

    def test_parse_text_input(self, runner):
        """Parse should handle text input."""
        with patch("nemlig_shopper.cli.parse_recipe_text") as mock_parse:
            mock_recipe = Recipe(
                title="Manual Recipe",
                ingredients=[
                    Ingredient(original="eggs", name="eggs", quantity=None, unit=None),
                    Ingredient(original="flour", name="flour", quantity=None, unit=None),
                ],
                servings=None,
                source_url=None,
            )
            mock_parse.return_value = mock_recipe
            result = runner.invoke(cli, ["parse", "--text", "eggs, flour"])

        assert result.exit_code == 0
        assert "eggs" in result.output
        assert "flour" in result.output

    def test_parse_requires_input(self, runner):
        """Parse should require either URL or text input."""
        result = runner.invoke(cli, ["parse"])

        assert result.exit_code == 1
        assert "Provide a URL or use --text" in result.output

    def test_parse_invalid_url(self, runner):
        """Parse with invalid URL should display error."""
        with patch(
            "nemlig_shopper.cli.parse_recipe_url",
            side_effect=Exception("Failed to parse"),
        ):
            result = runner.invoke(cli, ["parse", "https://invalid.com"])

        assert result.exit_code == 1
        assert "Failed to parse" in result.output


# ============================================================================
# Add to Cart Command Tests
# ============================================================================


class TestAddCommand:
    """Tests for the add command."""

    def test_add_requires_login(self, runner, mock_api):
        """Add should require login."""
        mock_api.is_logged_in.return_value = False

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.get_credentials", return_value=(None, None)):
                result = runner.invoke(cli, ["add", "1001"])

        assert result.exit_code == 1
        assert "Please log in" in result.output

    def test_add_product_success(self, runner, mock_api_logged_in):
        """Add should add product to cart."""
        mock_api_logged_in.add_to_cart.return_value = True

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["add", "1001"])

        assert result.exit_code == 0
        assert "Added 1x product 1001 to cart" in result.output
        mock_api_logged_in.add_to_cart.assert_called_once_with(1001, 1)

    def test_add_product_with_quantity(self, runner, mock_api_logged_in):
        """Add should respect quantity parameter."""
        mock_api_logged_in.add_to_cart.return_value = True

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["add", "1001", "--quantity", "3"])

        assert result.exit_code == 0
        assert "Added 3x product 1001 to cart" in result.output
        mock_api_logged_in.add_to_cart.assert_called_once_with(1001, 3)

    def test_add_product_failure(self, runner, mock_api_logged_in):
        """Add should handle API errors."""
        mock_api_logged_in.add_to_cart.side_effect = NemligAPIError("Product not found")

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["add", "9999"])

        assert result.exit_code == 1
        assert "Failed to add to cart" in result.output


# ============================================================================
# Cart Command Tests
# ============================================================================


class TestCartCommand:
    """Tests for the cart command."""

    def test_cart_requires_login(self, runner, mock_api):
        """Cart should require login."""
        mock_api.is_logged_in.return_value = False

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.get_credentials", return_value=(None, None)):
                result = runner.invoke(cli, ["cart"])

        assert result.exit_code == 1
        assert "Please log in" in result.output

    def test_cart_empty(self, runner, mock_api_logged_in):
        """Cart should show empty message when no items."""
        mock_api_logged_in.get_cart.return_value = {
            "Lines": [],
            "TotalProductsPrice": 0,
            "NumberOfProducts": 0,
            "DeliveryPrice": 0,
        }

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["cart"])

        assert result.exit_code == 0
        assert "Your cart is empty" in result.output

    def test_cart_with_items(self, runner, mock_api_logged_in):
        """Cart should display items and totals."""
        mock_api_logged_in.get_cart.return_value = {
            "Lines": [
                {"ProductName": "Økologisk Mælk", "Quantity": 2, "Total": 27.90},
                {"ProductName": "Rugbrød", "Quantity": 1, "Total": 18.95},
            ],
            "TotalProductsPrice": 46.85,
            "NumberOfProducts": 3,
            "DeliveryPrice": 29.00,
            "FormattedDeliveryTime": "Onsdag 10:00-12:00",
        }

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["cart"])

        assert result.exit_code == 0
        assert "SHOPPING CART" in result.output
        assert "Økologisk Mælk" in result.output
        assert "Rugbrød" in result.output
        assert "46.85 DKK" in result.output
        assert "29.00 DKK" in result.output  # Delivery
        assert "Onsdag 10:00-12:00" in result.output


# ============================================================================
# Ensure Logged In Helper Tests
# ============================================================================


class TestEnsureLoggedIn:
    """Tests for the ensure_logged_in helper function."""

    def test_already_logged_in(self, mock_api_logged_in):
        """Should return True if already logged in."""
        from nemlig_shopper.cli import ensure_logged_in

        result = ensure_logged_in(mock_api_logged_in)

        assert result is True
        mock_api_logged_in.login.assert_not_called()

    def test_login_with_saved_credentials(self, mock_api):
        """Should use saved credentials to log in."""
        from nemlig_shopper.cli import ensure_logged_in

        with patch(
            "nemlig_shopper.cli.get_credentials",
            return_value=("user@example.com", "password"),
        ):
            result = ensure_logged_in(mock_api)

        assert result is True
        mock_api.login.assert_called_once_with("user@example.com", "password")

    def test_no_credentials_returns_false(self, mock_api, capsys):
        """Should return False if no credentials available."""
        from nemlig_shopper.cli import ensure_logged_in

        with patch("nemlig_shopper.cli.get_credentials", return_value=(None, None)):
            result = ensure_logged_in(mock_api)

        assert result is False

    def test_login_failure_returns_false(self, mock_api, capsys):
        """Should return False if login fails."""
        from nemlig_shopper.cli import ensure_logged_in

        mock_api.login.side_effect = NemligAPIError("Bad credentials")

        with patch(
            "nemlig_shopper.cli.get_credentials",
            return_value=("user@example.com", "wrongpass"),
        ):
            result = ensure_logged_in(mock_api)

        assert result is False
