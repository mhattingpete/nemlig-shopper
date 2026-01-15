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
        },
        {
            "id": 1002,
            "name": "Hvedemel",
            "price": 12.95,
            "unit_size": "1 kg",
            "brand": "Valsemøllen",
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
        assert "Found 2 products" in result.output
        assert "Økologiske Æg" in result.output
        assert "35.95 DKK" in result.output

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
        assert "RECIPE: Test Recipe" in result.output
        assert "Servings: 4" in result.output
        assert "2 eggs" in result.output
        assert "200g flour" in result.output

    def test_parse_with_scale(self, runner, sample_recipe):
        """Parse with scale should show scaled ingredients."""
        with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
            result = runner.invoke(cli, ["parse", "https://example.com/recipe", "--scale", "2"])

        assert result.exit_code == 0
        assert "Scaling" in result.output
        assert "Scaled Ingredients" in result.output

    def test_parse_with_servings(self, runner, sample_recipe):
        """Parse with target servings should show scaled ingredients."""
        with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
            result = runner.invoke(cli, ["parse", "https://example.com/recipe", "--servings", "8"])

        assert result.exit_code == 0
        assert "Scaling" in result.output

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
                result = runner.invoke(cli, ["add", "https://example.com/recipe"])

        assert result.exit_code == 1
        assert "Please log in" in result.output

    def test_add_with_credentials(self, runner, mock_api_logged_in, sample_recipe):
        """Add should work with valid credentials."""
        mock_api_logged_in.add_multiple_to_cart.return_value = {
            "success": [1001, 1002],
            "failed": [],
        }

        mock_matches = [
            MagicMock(
                matched=True,
                ingredient_name="eggs",
                product_name="Æg",
                price=35.95,
                quantity=1,
                is_dietary_safe=True,
                dietary_warnings=[],
                excluded_count=0,
                alternatives=[],
                to_dict=lambda: {},
            ),
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
                with patch("nemlig_shopper.cli.match_ingredients", return_value=mock_matches):
                    with patch(
                        "nemlig_shopper.cli.prepare_cart_items",
                        return_value=[{"product_id": 1001, "quantity": 1}],
                    ):
                        result = runner.invoke(cli, ["add", "https://example.com/recipe", "--yes"])

        assert result.exit_code == 0
        assert "Added 2 products to cart" in result.output

    def test_add_with_dietary_filters(self, runner, mock_api_logged_in, sample_recipe):
        """Add with dietary filters should pass them to matcher."""
        mock_api_logged_in.add_multiple_to_cart.return_value = {
            "success": [1001],
            "failed": [],
        }

        mock_matches = [
            MagicMock(
                matched=True,
                ingredient_name="milk",
                product_name="Laktosefri Mælk",
                price=18.95,
                quantity=1,
                is_dietary_safe=True,
                dietary_warnings=[],
                excluded_count=2,
                alternatives=[],
                to_dict=lambda: {},
            ),
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
                with patch(
                    "nemlig_shopper.cli.match_ingredients", return_value=mock_matches
                ) as mock_match:
                    with patch(
                        "nemlig_shopper.cli.prepare_cart_items",
                        return_value=[{"product_id": 1001, "quantity": 1}],
                    ):
                        result = runner.invoke(
                            cli,
                            [
                                "add",
                                "https://example.com/recipe",
                                "--lactose-free",
                                "--gluten-free",
                                "--yes",
                            ],
                        )

        # Verify dietary filters were passed
        call_kwargs = mock_match.call_args[1]
        assert "lactose" in call_kwargs["allergies"]
        assert "gluten" in call_kwargs["allergies"]
        assert "Dietary filters" in result.output

    def test_add_cancelled_by_user(self, runner, mock_api_logged_in, sample_recipe):
        """Add should respect user cancellation."""
        mock_matches = [
            MagicMock(
                matched=True,
                ingredient_name="eggs",
                product_name="Æg",
                price=35.95,
                quantity=1,
                is_dietary_safe=True,
                dietary_warnings=[],
                excluded_count=0,
                alternatives=[],
            ),
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
                with patch("nemlig_shopper.cli.match_ingredients", return_value=mock_matches):
                    with patch("nemlig_shopper.cli.get_unmatched_ingredients", return_value=[]):
                        # Simulate user saying 'n' to confirmation
                        result = runner.invoke(
                            cli, ["add", "https://example.com/recipe"], input="n\n"
                        )

        assert "Cancelled" in result.output


# ============================================================================
# Favorites Command Tests
# ============================================================================


class TestFavoritesCommands:
    """Tests for favorites subcommands."""

    def test_favorites_list_empty(self, runner):
        """Favorites list with no favorites should show message."""
        with patch("nemlig_shopper.cli.list_favorites", return_value=[]):
            result = runner.invoke(cli, ["favorites", "list"])

        assert result.exit_code == 0
        assert "No favorites saved" in result.output

    def test_favorites_list_with_items(self, runner):
        """Favorites list should display saved favorites."""
        favorites = [
            {
                "name": "breakfast",
                "title": "Pancakes",
                "ingredient_count": 5,
                "servings": 4,
                "has_product_matches": True,
            },
            {
                "name": "dinner",
                "title": "Pasta Bolognese",
                "ingredient_count": 8,
                "servings": 6,
                "has_product_matches": False,
            },
        ]

        with patch("nemlig_shopper.cli.list_favorites", return_value=favorites):
            result = runner.invoke(cli, ["favorites", "list"])

        assert result.exit_code == 0
        assert "breakfast" in result.output
        assert "Pancakes" in result.output
        assert "dinner" in result.output
        assert "Pasta Bolognese" in result.output

    def test_favorites_show(self, runner, sample_recipe):
        """Favorites show should display recipe details."""
        favorite_data = {
            "product_matches": [
                {"ingredient_name": "eggs", "product_name": "Æg", "matched": True},
            ],
            "saved_at": "2026-01-15T10:00:00",
        }

        with patch("nemlig_shopper.cli.get_favorite_recipe", return_value=sample_recipe):
            with patch("nemlig_shopper.cli.get_favorite", return_value=favorite_data):
                result = runner.invoke(cli, ["favorites", "show", "breakfast"])

        assert result.exit_code == 0
        assert "Test Recipe" in result.output
        assert "eggs" in result.output

    def test_favorites_save(self, runner, sample_recipe):
        """Favorites save should save a new favorite."""
        with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
            with patch("nemlig_shopper.cli.save_favorite") as mock_save:
                result = runner.invoke(
                    cli, ["favorites", "save", "myrecipe", "https://example.com/recipe"]
                )

        assert result.exit_code == 0
        assert "Saved" in result.output
        mock_save.assert_called_once()

    def test_favorites_delete_confirmed(self, runner):
        """Favorites delete with confirmation should delete."""
        with patch("nemlig_shopper.cli.delete_favorite") as mock_delete:
            result = runner.invoke(cli, ["favorites", "delete", "myrecipe", "--yes"])

        assert result.exit_code == 0
        assert "Deleted" in result.output
        mock_delete.assert_called_once_with("myrecipe")

    def test_favorites_delete_cancelled(self, runner):
        """Favorites delete without confirmation should cancel."""
        with patch("nemlig_shopper.cli.delete_favorite") as mock_delete:
            result = runner.invoke(cli, ["favorites", "delete", "myrecipe"], input="n\n")

        assert "Cancelled" in result.output
        mock_delete.assert_not_called()


# ============================================================================
# Preferences Command Tests
# ============================================================================


class TestPreferencesCommands:
    """Tests for preferences subcommands."""

    def test_preferences_status(self, runner):
        """Preferences status should display count and last sync."""
        with patch("nemlig_shopper.cli.get_preference_count", return_value=42):
            with patch("nemlig_shopper.cli.get_last_sync_time", return_value="2026-01-15 10:00"):
                result = runner.invoke(cli, ["preferences", "status"])

        assert result.exit_code == 0
        assert "Products tracked: 42" in result.output
        assert "Last synced: 2026-01-15 10:00" in result.output

    def test_preferences_status_never_synced(self, runner):
        """Preferences status with no sync should suggest syncing."""
        with patch("nemlig_shopper.cli.get_preference_count", return_value=0):
            with patch("nemlig_shopper.cli.get_last_sync_time", return_value=None):
                result = runner.invoke(cli, ["preferences", "status"])

        assert result.exit_code == 0
        assert "Last synced: Never" in result.output
        assert "nemlig preferences sync" in result.output

    def test_preferences_sync(self, runner, mock_api_logged_in):
        """Preferences sync should fetch from order history."""
        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            with patch(
                "nemlig_shopper.cli.sync_preferences_from_orders", return_value=50
            ) as mock_sync:
                result = runner.invoke(cli, ["preferences", "sync", "--orders", "5"])

        assert result.exit_code == 0
        assert "Synced 50 products" in result.output
        mock_sync.assert_called_once_with(mock_api_logged_in, 5)

    def test_preferences_clear_confirmed(self, runner):
        """Preferences clear with --yes should clear."""
        with patch("nemlig_shopper.cli.clear_preferences") as mock_clear:
            result = runner.invoke(cli, ["preferences", "clear", "--yes"])

        assert result.exit_code == 0
        assert "Preferences cleared" in result.output
        mock_clear.assert_called_once()

    def test_preferences_clear_cancelled(self, runner):
        """Preferences clear without confirmation should cancel."""
        with patch("nemlig_shopper.cli.clear_preferences") as mock_clear:
            result = runner.invoke(cli, ["preferences", "clear"], input="n\n")

        assert "Cancelled" in result.output
        mock_clear.assert_not_called()


# ============================================================================
# Prices Command Tests
# ============================================================================


class TestPricesCommands:
    """Tests for prices subcommands."""

    def test_prices_status(self, runner):
        """Prices status should display tracking info."""
        mock_tracker = MagicMock()
        mock_tracker.get_tracked_count.return_value = 25
        mock_tracker.get_price_count.return_value = 150

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "status"])

        assert result.exit_code == 0
        assert "Products tracked: 25" in result.output
        assert "Price records: 150" in result.output

    def test_prices_track(self, runner, mock_api, sample_products):
        """Prices track should record prices for search results."""
        mock_api.search_products.return_value = sample_products

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.record_search_prices", return_value=2):
                result = runner.invoke(cli, ["prices", "track", "æg"])

        assert result.exit_code == 0
        assert "Recorded prices for 2 products" in result.output
        assert "Tracked products" in result.output

    def test_prices_track_no_results(self, runner, mock_api):
        """Prices track with no results should display message."""
        mock_api.search_products.return_value = []

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            result = runner.invoke(cli, ["prices", "track", "nonexistent"])

        assert result.exit_code == 0
        assert "No products found" in result.output

    def test_prices_history(self, runner):
        """Prices history should display price history."""
        mock_tracker = MagicMock()
        mock_tracker.search_products.return_value = [{"id": 1001, "name": "Test Product"}]

        mock_stats = MagicMock()
        mock_stats.current_price = 25.95
        mock_stats.avg_price = 28.50
        mock_stats.min_price = 22.00
        mock_stats.max_price = 32.00
        mock_stats.price_count = 10
        mock_stats.is_on_sale = True
        mock_stats.discount_percent = 8.9

        mock_tracker.get_price_stats.return_value = mock_stats
        mock_tracker.get_price_history.return_value = []

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "history", "test"])

        assert result.exit_code == 0
        assert "Test Product" in result.output
        assert "Current: 25.95 DKK" in result.output
        assert "ON SALE" in result.output

    def test_prices_history_no_data(self, runner):
        """Prices history with no tracked products should suggest tracking."""
        mock_tracker = MagicMock()
        mock_tracker.search_products.return_value = []

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "history", "unknown"])

        assert result.exit_code == 0
        assert "No tracked products found" in result.output
        assert "nemlig prices track" in result.output

    def test_prices_alerts(self, runner):
        """Prices alerts should display products on sale."""
        mock_tracker = MagicMock()

        mock_alert = MagicMock()
        mock_alert.product_name = "Discount Product"
        mock_alert.current_price = 19.95
        mock_alert.avg_price = 25.00
        mock_alert.discount_percent = 20.2
        mock_alert.is_lowest = True

        mock_tracker.get_price_alerts.return_value = [mock_alert]

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "alerts"])

        assert result.exit_code == 0
        assert "PRICE ALERTS" in result.output
        assert "Discount Product" in result.output
        assert "20.2% off" in result.output
        assert "LOWEST" in result.output

    def test_prices_alerts_none(self, runner):
        """Prices alerts with no sales should display message."""
        mock_tracker = MagicMock()
        mock_tracker.get_price_alerts.return_value = []

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "alerts"])

        assert result.exit_code == 0
        assert "No products found with" in result.output

    def test_prices_clear_all(self, runner):
        """Prices clear should clear all data when confirmed."""
        mock_tracker = MagicMock()

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "clear", "--yes"])

        assert result.exit_code == 0
        assert "All price data cleared" in result.output
        mock_tracker.clear_all.assert_called_once()

    def test_prices_clear_old_only(self, runner):
        """Prices clear --old-only should only clear old records."""
        mock_tracker = MagicMock()
        mock_tracker.clear_old_prices.return_value = 50

        with patch("nemlig_shopper.cli.get_tracker", return_value=mock_tracker):
            result = runner.invoke(cli, ["prices", "clear", "--old-only", "--yes"])

        assert result.exit_code == 0
        assert "Removed 50 old price records" in result.output
        mock_tracker.clear_old_prices.assert_called_once_with(days=90)


# ============================================================================
# Plan Command Tests
# ============================================================================


class TestPlanCommand:
    """Tests for the plan command."""

    def test_plan_requires_urls(self, runner, mock_api_logged_in):
        """Plan should require at least one URL."""
        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            result = runner.invoke(cli, ["plan"])

        assert result.exit_code == 1
        assert "No recipe URLs provided" in result.output

    def test_plan_with_urls(self, runner, mock_api_logged_in, sample_recipe):
        """Plan should process multiple recipe URLs."""
        mock_api_logged_in.add_multiple_to_cart.return_value = {
            "success": [1001, 1002],
            "failed": [],
        }

        mock_plan = MagicMock()
        mock_plan.recipe_count = 2
        mock_plan.ingredient_count = 5
        mock_plan.recipes = [sample_recipe, sample_recipe]
        mock_plan.consolidated_ingredients = []

        mock_matches = []

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api_logged_in):
            with patch("nemlig_shopper.cli.create_meal_plan", return_value=mock_plan):
                with patch("nemlig_shopper.cli.match_ingredients", return_value=mock_matches):
                    with patch("nemlig_shopper.cli.prepare_cart_items", return_value=[]):
                        result = runner.invoke(
                            cli,
                            [
                                "plan",
                                "https://example.com/recipe1",
                                "https://example.com/recipe2",
                                "--yes",
                            ],
                        )

        assert result.exit_code == 0
        assert "MEAL PLAN (2 recipes)" in result.output


# ============================================================================
# Export Command Tests
# ============================================================================


class TestExportCommand:
    """Tests for the export command."""

    def test_export_to_json(self, runner, mock_api, sample_recipe, tmp_path):
        """Export should create JSON file."""
        output_file = tmp_path / "shopping.json"

        mock_matches = []

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
                with patch("nemlig_shopper.cli.match_ingredients", return_value=mock_matches):
                    with patch(
                        "nemlig_shopper.cli.export_shopping_list", return_value="json"
                    ) as mock_export:
                        result = runner.invoke(
                            cli, ["export", "https://example.com/recipe", str(output_file)]
                        )

        assert result.exit_code == 0
        assert "Exported" in result.output
        assert "json format" in result.output
        mock_export.assert_called_once()

    def test_export_with_scale(self, runner, mock_api, sample_recipe, tmp_path):
        """Export with scale should scale the recipe."""
        output_file = tmp_path / "shopping.md"

        mock_matches = []

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.parse_recipe_url", return_value=sample_recipe):
                with patch("nemlig_shopper.cli.match_ingredients", return_value=mock_matches):
                    with patch("nemlig_shopper.cli.export_shopping_list", return_value="md"):
                        result = runner.invoke(
                            cli,
                            [
                                "export",
                                "https://example.com/recipe",
                                str(output_file),
                                "--scale",
                                "2",
                            ],
                        )

        assert result.exit_code == 0
        assert "Scaling: 2" in result.output


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
