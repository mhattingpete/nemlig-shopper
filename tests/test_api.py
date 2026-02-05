"""Tests for the NemligAPI client."""

import httpx
import pytest

from nemlig_shopper.api import NemligAPIError
from nemlig_shopper.config import API_BASE_URL

# Search gateway URL used by the API
SEARCH_GATEWAY_URL = "https://webapi.prod.knl.nemlig.it/searchgateway/api"


class TestApiInitialization:
    """Tests for API client initialization."""

    def test_creates_session_with_required_headers(self, api_client):
        """Client should initialize with proper HTTP headers."""
        headers = api_client.client.headers
        assert headers["Content-Type"] == "application/json"
        assert headers["User-Agent"].startswith("Mozilla/5.0")
        assert headers["platform"] == "web"
        assert headers["device-size"] == "desktop"

    def test_starts_logged_out(self, api_client):
        """Client should start in logged-out state."""
        assert not api_client.is_logged_in()
        assert api_client._access_token is None
        assert api_client._user_id is None


class TestAuthentication:
    """Tests for login/logout functionality."""

    def test_login_success(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Successful login should set logged_in state and refresh session."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response,
            status_code=200,
        )

        result = api_client.login("test@example.com", "password123")

        assert result is True
        assert api_client.is_logged_in()
        assert api_client._access_token == "test-jwt-token-12345"
        assert api_client._user_id == "67890"

    def test_login_invalid_credentials(self, mock_httpx, api_client):
        """Login with invalid credentials should raise NemligAPIError."""
        # Nemlig API returns 400 with ErrorCode for invalid credentials
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json={
                "Data": None,
                "ErrorCode": 4,
                "ErrorMessage": "E-mail og/eller password er ikke gyldig",
            },
            status_code=400,
        )

        with pytest.raises(NemligAPIError) as exc_info:
            api_client.login("wrong@example.com", "wrongpassword")

        assert "400" in str(exc_info.value) or "Client Error" in str(exc_info.value)
        assert not api_client.is_logged_in()

    def test_login_network_error(self, mock_httpx, api_client):
        """Login with network error should raise NemligAPIError."""
        mock_httpx.post(f"{API_BASE_URL}/login").mock(
            side_effect=httpx.ConnectError("Network unreachable")
        )

        with pytest.raises(NemligAPIError) as exc_info:
            api_client.login("test@example.com", "password123")

        assert "Login failed" in str(exc_info.value)

    def test_login_http_error(self, mock_httpx, api_client):
        """Login with HTTP error should raise NemligAPIError."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json={"error": "Service unavailable"},
            status_code=503,
        )

        with pytest.raises(NemligAPIError):
            api_client.login("test@example.com", "password123")


class TestSessionRefresh:
    """Tests for session data refresh functionality."""

    def test_refresh_session_gets_token(
        self,
        mock_httpx,
        api_client,
        mock_token_response,
        mock_app_settings_response,
        mock_user_response,
        mock_timeslot_response,
    ):
        """Session refresh should fetch and store JWT token."""
        mock_httpx.get(f"{API_BASE_URL}/Token").respond(json=mock_token_response, status_code=200)
        mock_httpx.get(f"{API_BASE_URL}/v2/AppSettings/Website").respond(
            json=mock_app_settings_response, status_code=200
        )
        mock_httpx.get(f"{API_BASE_URL}/user/GetCurrentUser").respond(
            json=mock_user_response, status_code=200
        )
        mock_httpx.get(f"{API_BASE_URL}/Order/DeliverySpot").respond(
            json=mock_timeslot_response, status_code=200
        )

        api_client._refresh_session_data()

        assert api_client._access_token == "test-jwt-token-12345"
        assert api_client._combined_timestamp == "TEST-TIMESTAMP-123"
        assert api_client._user_id == "67890"
        assert api_client._timeslot == "2026011509-60-600"

    def test_refresh_session_handles_token_failure(
        self,
        mock_httpx,
        api_client,
        mock_app_settings_response,
        mock_user_response,
        mock_timeslot_response,
    ):
        """Session refresh should handle token fetch failure gracefully."""
        mock_httpx.get(f"{API_BASE_URL}/Token").mock(side_effect=httpx.ConnectError("timeout"))
        mock_httpx.get(f"{API_BASE_URL}/v2/AppSettings/Website").respond(
            json=mock_app_settings_response, status_code=200
        )
        mock_httpx.get(f"{API_BASE_URL}/user/GetCurrentUser").respond(
            json=mock_user_response, status_code=200
        )
        mock_httpx.get(f"{API_BASE_URL}/Order/DeliverySpot").respond(
            json=mock_timeslot_response, status_code=200
        )

        api_client._refresh_session_data()

        assert api_client._access_token is None
        # Other data should still be fetched
        assert api_client._combined_timestamp == "TEST-TIMESTAMP-123"

    def test_refresh_session_uses_fallback_values(self, mock_httpx, api_client):
        """Session refresh should use fallback values when API fails."""
        # All requests fail
        mock_httpx.get(f"{API_BASE_URL}/Token").mock(side_effect=httpx.ConnectError("timeout"))
        mock_httpx.get(f"{API_BASE_URL}/v2/AppSettings/Website").mock(
            side_effect=httpx.ConnectError("timeout")
        )
        mock_httpx.get(f"{API_BASE_URL}/user/GetCurrentUser").mock(
            side_effect=httpx.ConnectError("timeout")
        )
        mock_httpx.get(f"{API_BASE_URL}/Order/DeliverySpot").mock(
            side_effect=httpx.ConnectError("timeout")
        )

        api_client._refresh_session_data()

        # Should use default fallback values
        assert api_client._combined_timestamp == "AAAAAAAA-YFA_17hS"
        # Timeslot is generated dynamically (tomorrow at 15:00)
        assert api_client._timeslot.endswith("15-60-240")


class TestProductSearch:
    """Tests for product search functionality."""

    def test_search_products_via_gateway(
        self, mock_httpx, api_client, mock_search_response, setup_session_mocks
    ):
        """Search should return products from the search gateway."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").respond(
            json=mock_search_response, status_code=200
        )

        products = api_client.search_products("mælk", limit=10)

        assert len(products) == 1
        assert products[0]["name"] == "Økologisk Sødmælk"
        assert products[0]["price"] == 15.95
        assert products[0]["brand"] == "Arla"

    def test_search_products_parses_availability(self, mock_httpx, api_client, setup_session_mocks):
        """Search should correctly parse product availability."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").respond(
            json={
                "Products": {
                    "Products": [
                        {
                            "Id": 1,
                            "Name": "Available Product",
                            "Price": 10.0,
                            "Availability": {
                                "IsDeliveryAvailable": True,
                                "IsAvailableInStock": True,
                            },
                        },
                        {
                            "Id": 2,
                            "Name": "Out of Stock",
                            "Price": 20.0,
                            "Availability": {
                                "IsDeliveryAvailable": True,
                                "IsAvailableInStock": False,
                            },
                        },
                    ]
                }
            },
            status_code=200,
        )

        products = api_client.search_products("test", limit=10)

        assert products[0]["available"] is True
        assert products[1]["available"] is False

    def test_search_products_returns_empty_on_gateway_failure(
        self, mock_httpx, api_client, setup_session_mocks
    ):
        """Search should return empty list when gateway fails."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").mock(
            side_effect=httpx.ConnectError("Gateway timeout")
        )
        # Also mock the quick search fallback
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/quick").respond(
            json={"Categories": [], "Suggestions": []}, status_code=200
        )

        products = api_client.search_products("mælk", limit=10)

        assert products == []

    def test_search_products_respects_limit(self, mock_httpx, api_client, setup_session_mocks):
        """Search should respect the limit parameter."""
        many_products = [
            {"Id": i, "Name": f"Product {i}", "Price": 10.0, "Availability": {}} for i in range(20)
        ]
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").respond(
            json={"Products": {"Products": many_products}}, status_code=200
        )

        products = api_client.search_products("test", limit=5)

        assert len(products) == 5

    def test_search_products_triggers_session_refresh(
        self, mock_httpx, api_client, mock_search_response, setup_session_mocks
    ):
        """Search should refresh session data if not already available."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").respond(
            json=mock_search_response, status_code=200
        )

        # No session data yet
        assert api_client._combined_timestamp is None

        api_client.search_products("mælk")

        # Session should have been refreshed
        assert api_client._combined_timestamp is not None


class TestSearchSuggestions:
    """Tests for search suggestions functionality."""

    def test_get_search_suggestions(self, mock_httpx, api_client, setup_session_mocks):
        """Should return suggestions and categories."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/quick").respond(
            json={
                "Suggestions": ["mælk", "mælkesnitte", "mælkebøtte"],
                "Categories": [
                    {"Name": "Mælk & Fløde", "Url": "/mejeri/maelk"},
                    {"Name": "Plantemælk", "Url": "/mejeri/plantemælk"},
                ],
            },
            status_code=200,
        )

        result = api_client.get_search_suggestions("mælk")

        assert "mælk" in result["suggestions"]
        assert len(result["categories"]) == 2
        assert result["categories"][0]["Name"] == "Mælk & Fløde"

    def test_get_search_suggestions_handles_failure(
        self, mock_httpx, api_client, setup_session_mocks
    ):
        """Should return empty results on failure."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/quick").mock(
            side_effect=httpx.ConnectError("timeout")
        )

        result = api_client.get_search_suggestions("mælk")

        assert result == {"suggestions": [], "categories": []}


class TestCartOperations:
    """Tests for shopping cart functionality."""

    def test_add_to_cart_requires_login(self, api_client):
        """Adding to cart without login should raise error."""
        with pytest.raises(NemligAPIError) as exc_info:
            api_client.add_to_cart(100001, quantity=1)

        assert "Must be logged in" in str(exc_info.value)

    def test_add_to_cart_success(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Successfully adding to cart should return True."""
        # Login first
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        # Add to cart
        mock_httpx.post(f"{API_BASE_URL}/basket/AddToBasket").respond(
            json={"Success": True}, status_code=200
        )

        result = api_client.add_to_cart(100001, quantity=2)

        assert result is True

    def test_add_to_cart_network_error(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Network error when adding to cart should raise NemligAPIError."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        mock_httpx.post(f"{API_BASE_URL}/basket/AddToBasket").mock(
            side_effect=httpx.ConnectError("timeout")
        )

        with pytest.raises(NemligAPIError) as exc_info:
            api_client.add_to_cart(100001)

        assert "Failed to add to cart" in str(exc_info.value)

    def test_add_multiple_to_cart(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Adding multiple items should track success and failures."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        # Use side_effect with a list to sequence multiple responses
        mock_httpx.post(f"{API_BASE_URL}/basket/AddToBasket").mock(
            side_effect=[
                httpx.Response(200, json={"Success": True}),
                httpx.ConnectError("timeout"),
            ]
        )

        items = [
            {"product_id": 100001, "quantity": 1},
            {"product_id": 100002, "quantity": 2},
        ]
        result = api_client.add_multiple_to_cart(items)

        assert 100001 in result["success"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["product_id"] == 100002

    def test_add_multiple_to_cart_missing_product_id(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Items without product_id should be recorded as failed."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        items = [{"quantity": 1}]  # Missing product_id
        result = api_client.add_multiple_to_cart(items)

        assert len(result["failed"]) == 1
        assert "Missing product_id" in result["failed"][0]["error"]

    def test_get_cart_requires_login(self, api_client):
        """Getting cart without login should raise error."""
        with pytest.raises(NemligAPIError) as exc_info:
            api_client.get_cart()

        assert "Must be logged in" in str(exc_info.value)

    def test_get_cart_success(
        self,
        mock_httpx,
        api_client,
        mock_login_success_response,
        mock_cart_response,
        setup_session_mocks,
    ):
        """Getting cart should return cart contents."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        mock_httpx.get(f"{API_BASE_URL}/basket/GetBasket").respond(
            json=mock_cart_response, status_code=200
        )

        cart = api_client.get_cart()

        assert cart["Total"] == 31.90
        assert len(cart["Items"]) == 1
        assert cart["Items"][0]["ProductName"] == "Økologisk Sødmælk"

    def test_clear_cart_requires_login(self, api_client):
        """Clearing cart without login should raise error."""
        with pytest.raises(NemligAPIError) as exc_info:
            api_client.clear_cart()

        assert "Must be logged in" in str(exc_info.value)

    def test_clear_cart_success(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """Clearing cart should return True on success."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        mock_httpx.post(f"{API_BASE_URL}/basket/ClearBasket").respond(
            json={"Success": True}, status_code=200
        )

        result = api_client.clear_cart()

        assert result is True


class TestProductParsing:
    """Tests for product data parsing."""

    def test_parse_products_extracts_all_fields(self, api_client, mock_product):
        """Product parsing should extract all expected fields."""
        result = api_client._parse_products([mock_product], limit=10)

        product = result[0]
        assert product["id"] == 100001
        assert product["name"] == "Økologisk Sødmælk"
        assert product["price"] == 15.95
        assert product["unit"] == "15,95 kr./l"
        assert product["brand"] == "Arla"
        assert product["category"] == "Mejeri"
        assert product["subcategory"] == "Mælk"
        assert product["available"] is True
        assert "Økologisk" in product["labels"]

    def test_parse_products_handles_missing_fields(self, api_client):
        """Product parsing should handle missing optional fields."""
        minimal_product = {"Id": 1, "Name": "Test", "Price": 10.0}

        result = api_client._parse_products([minimal_product], limit=10)

        product = result[0]
        assert product["id"] == 1
        assert product["name"] == "Test"
        assert product["brand"] == ""
        assert product["category"] == ""
        assert product["labels"] == []

    def test_parse_products_handles_unavailable(self, api_client):
        """Product parsing should correctly identify unavailable products."""
        unavailable = {
            "Id": 1,
            "Name": "Out of Stock",
            "Price": 10.0,
            "Availability": {"IsDeliveryAvailable": False, "IsAvailableInStock": True},
        }

        result = api_client._parse_products([unavailable], limit=10)

        assert result[0]["available"] is False


class TestErrorHandling:
    """Tests for error handling across the API."""

    def test_http_500_error_on_login(self, mock_httpx, api_client):
        """Server error during login should raise NemligAPIError."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json={"error": "Internal server error"}, status_code=500
        )

        with pytest.raises(NemligAPIError):
            api_client.login("test@example.com", "password")

    def test_timeout_on_search(self, mock_httpx, api_client, setup_session_mocks):
        """Timeout during search should return empty list."""
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/search").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        mock_httpx.get(f"{SEARCH_GATEWAY_URL}/quick").respond(
            json={"Categories": []}, status_code=200
        )

        result = api_client.search_products("test")

        assert result == []

    def test_malformed_json_on_token(self, mock_httpx, api_client):
        """Malformed JSON response should be handled gracefully."""
        mock_httpx.get(f"{API_BASE_URL}/Token").respond(content=b"not json", status_code=200)
        mock_httpx.get(f"{API_BASE_URL}/v2/AppSettings/Website").respond(json={}, status_code=200)
        mock_httpx.get(f"{API_BASE_URL}/user/GetCurrentUser").respond(json={}, status_code=200)
        mock_httpx.get(f"{API_BASE_URL}/Order/DeliverySpot").respond(json={}, status_code=200)

        # Should not raise, just return None for token
        api_client._refresh_session_data()
        assert api_client._access_token is None

    def test_cart_operations_handle_http_errors(
        self, mock_httpx, api_client, mock_login_success_response, setup_session_mocks
    ):
        """HTTP errors on cart operations should raise NemligAPIError."""
        mock_httpx.post(f"{API_BASE_URL}/login").respond(
            json=mock_login_success_response, status_code=200
        )
        api_client.login("test@example.com", "password")

        mock_httpx.get(f"{API_BASE_URL}/basket/GetBasket").respond(
            json={"error": "Service unavailable"}, status_code=503
        )

        with pytest.raises(NemligAPIError) as exc_info:
            api_client.get_cart()

        assert "Failed to get cart" in str(exc_info.value)
