"""Shared fixtures for nemlig-shopper tests."""

import pytest
import respx

from nemlig_shopper.api import NemligAPI
from nemlig_shopper.config import API_BASE_URL

# Search gateway URL used by the API
SEARCH_GATEWAY_URL = "https://webapi.prod.knl.nemlig.it/searchgateway/api"


@pytest.fixture
def mock_httpx():
    """Activate respx mock for HTTP requests."""
    with respx.mock(assert_all_called=False) as respx_mock:
        yield respx_mock


@pytest.fixture
def api_client():
    """Create a fresh NemligAPI client instance."""
    return NemligAPI()


@pytest.fixture
def mock_token_response():
    """Standard token response data."""
    return {"access_token": "test-jwt-token-12345"}


@pytest.fixture
def mock_app_settings_response():
    """Standard app settings response data."""
    return {
        "CombinedProductsAndSitecoreTimestamp": "TEST-TIMESTAMP-123",
        "SitecorePublishedStamp": "TEST-CORRELATION-ID",
    }


@pytest.fixture
def mock_user_response():
    """Standard logged-in user response data."""
    return {
        "Id": 12345,
        "DebitorId": 67890,
        "Email": "test@example.com",
        "FirstName": "Test",
        "LastName": "User",
    }


@pytest.fixture
def mock_timeslot_response():
    """Standard timeslot response data."""
    return {
        "TimeslotUtc": "2026011509-60-600",
        "TimeslotId": 2161500,
    }


@pytest.fixture
def mock_login_success_response():
    """Standard successful login response."""
    # Nemlig API returns RedirectUrl on successful login (not IsLoggedIn)
    return {
        "RedirectUrl": "/",
        "MergeSuccessful": True,
        "ZipCodeDiffers": False,
        "DeliveryZoneId": 1,
    }


@pytest.fixture
def mock_product():
    """Single product data as returned by the API."""
    return {
        "Id": 100001,
        "Name": "Økologisk Sødmælk",
        "Price": 15.95,
        "UnitPrice": "15,95 kr./l",
        "UnitPriceCalc": 15.95,
        "Description": "1 liter",
        "Brand": "Arla",
        "Category": "Mejeri",
        "SubCategory": "Mælk",
        "PrimaryImage": "https://example.com/milk.jpg",
        "Labels": ["Økologisk"],
        "Availability": {
            "IsDeliveryAvailable": True,
            "IsAvailableInStock": True,
        },
    }


@pytest.fixture
def mock_search_response(mock_product):
    """Standard search gateway response with products."""
    return {
        "Products": {
            "Products": [mock_product],
            "TotalCount": 1,
        },
        "Categories": [],
        "Recipes": [],
    }


@pytest.fixture
def mock_cart_response():
    """Standard cart response."""
    return {
        "Items": [
            {
                "ProductId": 100001,
                "ProductName": "Økologisk Sødmælk",
                "Quantity": 2,
                "Price": 15.95,
                "TotalPrice": 31.90,
            }
        ],
        "Total": 31.90,
        "ItemCount": 2,
    }


@pytest.fixture
def setup_session_mocks(
    mock_httpx,
    mock_token_response,
    mock_app_settings_response,
    mock_user_response,
    mock_timeslot_response,
):
    """Set up all mocks needed for session initialization."""
    mock_httpx.get(f"{API_BASE_URL}/Token").respond(json=mock_token_response)
    mock_httpx.get(f"{API_BASE_URL}/v2/AppSettings/Website").respond(
        json=mock_app_settings_response
    )
    mock_httpx.get(f"{API_BASE_URL}/user/GetCurrentUser").respond(json=mock_user_response)
    mock_httpx.get(f"{API_BASE_URL}/Order/DeliverySpot").respond(json=mock_timeslot_response)
    return mock_httpx
