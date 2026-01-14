"""Nemlig.com API client for authentication, search, and cart operations."""

import uuid
from typing import Any

import requests

from .config import API_BASE_URL


class NemligAPIError(Exception):
    """Exception raised for Nemlig API errors."""

    pass


# External search gateway for autocomplete/quick search
SEARCH_GATEWAY_URL = "https://webapi.prod.knl.nemlig.it/searchgateway/api"


class NemligAPI:
    """Client for interacting with Nemlig.com's API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                "Referer": "https://www.nemlig.com/",
                "version": "11.201.0",
                "platform": "web",
                "device-size": "desktop",
            }
        )
        self._logged_in = False
        self._access_token: str | None = None
        self._user_id: str | None = None
        self._combined_timestamp: str | None = None
        self._timeslot: str = "2026011409-60-600"  # Default timeslot
        self._timeslot_id: str = "2161377"  # Default timeslot ID
        self._correlation_id: str | None = None

    def _get_token(self) -> str | None:
        """Get JWT access token from Nemlig.com."""
        url = f"{API_BASE_URL}/Token"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("access_token")
        except requests.RequestException:
            return None

    def _get_app_settings(self) -> dict[str, Any]:
        """Get app settings including timestamps."""
        url = f"{API_BASE_URL}/v2/AppSettings/Website"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    def _get_current_user(self) -> dict[str, Any]:
        """Get current user info."""
        url = f"{API_BASE_URL}/user/GetCurrentUser"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            # API might return a string or dict depending on auth state
            if isinstance(data, dict):
                return data
            return {}
        except requests.RequestException:
            return {}

    def _get_timeslot(self) -> tuple[str, str]:
        """Get current delivery timeslot and ID from Order/DeliverySpot."""
        url = f"{API_BASE_URL}/Order/DeliverySpot"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                timeslot_utc = data.get("TimeslotUtc", self._timeslot)
                timeslot_id = str(data.get("TimeslotId", self._timeslot_id))
                return timeslot_utc, timeslot_id
        except requests.RequestException:
            pass
        return self._timeslot, self._timeslot_id

    def _refresh_session_data(self) -> None:
        """Refresh token, timestamps, and user info."""
        # Get JWT token
        self._access_token = self._get_token()

        # Add Authorization header to session for all subsequent requests
        if self._access_token:
            self.session.headers.update({"Authorization": f"Bearer {self._access_token}"})

        # Get app settings for timestamps
        settings = self._get_app_settings()
        self._combined_timestamp = settings.get(
            "CombinedProductsAndSitecoreTimestamp", "AAAAAAAA-YFA_17hS"
        )
        self._correlation_id = settings.get("SitecorePublishedStamp", "YFA_17hS")

        # Get user ID if logged in - it's in DebitorId field
        user_data = self._get_current_user()
        if isinstance(user_data, dict):
            # Try DebitorId first (main user ID), then Id as fallback
            debitor_id = user_data.get("DebitorId") or user_data.get("Id")
            if debitor_id:
                self._user_id = str(debitor_id)

        # Get timeslot and timeslot ID
        self._timeslot, self._timeslot_id = self._get_timeslot()

    def _build_products_url(self, endpoint: str) -> str:
        """Build the products API URL with timestamps and user ID."""
        user_id = self._user_id or "0"
        return f"{API_BASE_URL}/{self._combined_timestamp}/{self._timeslot}/1/{user_id}/{endpoint}"

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with Nemlig.com.

        Args:
            username: Nemlig.com email/username
            password: Account password

        Returns:
            True if login successful

        Raises:
            NemligAPIError: If login fails
        """
        url = f"{API_BASE_URL}/login"
        payload = {"Username": username, "Password": password}

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            if data.get("IsLoggedIn") or response.status_code == 200:
                self._logged_in = True
                # Refresh session data after login to get user ID and tokens
                self._refresh_session_data()
                return True
            else:
                raise NemligAPIError("Login failed: Invalid credentials")

        except requests.RequestException as e:
            raise NemligAPIError(f"Login failed: {e}") from e

    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self._logged_in

    def search_products(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for products on Nemlig.com.

        Args:
            query: Search term
            limit: Maximum number of results

        Returns:
            List of product dictionaries with id, name, price, unit, etc.
        """
        # Ensure we have session data
        if not self._combined_timestamp:
            self._refresh_session_data()

        # Try the search gateway (primary method)
        products = self._search_via_gateway(query, limit)
        if products:
            return products

        # Fallback: Try fetching from first matching category via quick search
        if self._access_token:
            categories = self._get_search_categories(query)
            if categories:
                # Try to get products from the first matching category
                for cat in categories[:3]:
                    cat_url = cat.get("Url", "")
                    if cat_url:
                        products = self.get_products_by_category(cat_url, limit)
                        if products:
                            return products

        return []

    def _get_correlation_headers(self) -> dict[str, str]:
        """Generate headers with a unique X-Correlation-Id for each request."""
        return {"X-Correlation-Id": str(uuid.uuid4())}

    def _get_gateway_headers(self) -> dict[str, str]:
        """Generate headers for search gateway requests.

        Note: We explicitly exclude Content-Type for GET requests to the search gateway,
        as it causes a 400 error when present.
        """
        headers = {
            "X-Correlation-Id": str(uuid.uuid4()),
            "Origin": "https://www.nemlig.com",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.nemlig.com/",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _search_via_gateway(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Search products using the search gateway API."""
        # Ensure we have required data for the gateway
        if not self._access_token or not self._combined_timestamp:
            self._refresh_session_data()
            if not self._access_token:
                return []

        url = f"{SEARCH_GATEWAY_URL}/search"
        params = {
            "query": query,
            "take": limit,
            "skip": 0,
            "recipeCount": 0,
            "timestamp": self._combined_timestamp,
            "timeslotUtc": self._timeslot,
            "deliveryZoneId": 1,
            "includeFavorites": self._user_id or "0",
            "TimeSlotId": self._timeslot_id,
        }

        try:
            # Use requests.get directly to avoid session's Content-Type header
            # which causes 400 errors on the search gateway
            response = requests.get(url, params=params, headers=self._get_gateway_headers())
            response.raise_for_status()

            data = response.json()
            # The search gateway returns Products as a dict with nested Products list
            products_data = data.get("Products", {})
            if isinstance(products_data, dict):
                products_list = products_data.get("Products", [])
            else:
                products_list = products_data if isinstance(products_data, list) else []
            return self._parse_products(products_list, limit)

        except requests.RequestException:
            return []

    def _get_search_categories(self, query: str) -> list[dict[str, Any]]:
        """Get category suggestions from the quick search gateway."""
        url = f"{SEARCH_GATEWAY_URL}/quick"
        params = {"query": query, "correlationId": self._correlation_id or ""}
        headers = self._get_gateway_headers()

        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("Categories", [])
        except requests.RequestException:
            return []

    def get_search_suggestions(self, query: str) -> dict[str, Any]:
        """
        Get search suggestions and categories for a query.

        Args:
            query: Search term

        Returns:
            Dict with 'suggestions' (list of strings) and 'categories' (list of dicts)
        """
        if not self._access_token:
            self._refresh_session_data()

        url = f"{SEARCH_GATEWAY_URL}/quick"
        params = {"query": query, "correlationId": self._correlation_id or ""}
        headers = self._get_gateway_headers()

        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return {
                "suggestions": data.get("Suggestions", []),
                "categories": data.get("Categories", []),
            }
        except requests.RequestException:
            return {"suggestions": [], "categories": []}

    def _parse_products(self, products_data: list[dict], limit: int) -> list[dict[str, Any]]:
        """Parse product data from API response into standardized format."""
        products = []

        for item in products_data[:limit]:
            # Extract availability info
            availability = item.get("Availability", {})
            is_available = availability.get("IsDeliveryAvailable", True) and availability.get(
                "IsAvailableInStock", True
            )

            products.append(
                {
                    "id": item.get("Id"),
                    "name": item.get("Name"),
                    "price": item.get("Price"),
                    "unit": item.get("UnitPrice", ""),
                    "unit_price_calc": item.get("UnitPriceCalc"),
                    "unit_size": item.get("Description", ""),
                    "brand": item.get("Brand", ""),
                    "category": item.get("Category", ""),
                    "subcategory": item.get("SubCategory", ""),
                    "image_url": item.get("PrimaryImage", ""),
                    "available": is_available,
                    "labels": item.get("Labels", []),
                }
            )

        return products

    def get_products_by_category(self, category_url: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get products from a specific category.

        Args:
            category_url: The category URL path (e.g., "/dagligvarer/mejeri/maelk-floede/minimaelk")
            limit: Maximum number of results

        Returns:
            List of product dictionaries
        """
        # Ensure we have session data
        if not self._combined_timestamp:
            self._refresh_session_data()

        # First, get the category page to find the productGroupId
        page_url = f"https://www.nemlig.com{category_url}"
        params = {"GetAsJson": "1"}

        try:
            response = self.session.get(page_url, params=params)
            response.raise_for_status()

            data = response.json()
            # Look for product group ID in the page content
            content = data.get("content", [])
            for item in content:
                if item.get("ProductGroupId"):
                    return self._get_products_by_group_id(item["ProductGroupId"], limit)

        except requests.RequestException:
            pass

        return []

    def _get_products_by_group_id(self, group_id: str, limit: int) -> list[dict[str, Any]]:
        """Get products by product group ID."""
        url = self._build_products_url("Products/GetByProductGroupId")
        params = {"productGroupId": group_id, "sortorder": "default", "take": limit}

        try:
            response = self.session.get(url, params=params, headers=self._get_correlation_headers())
            response.raise_for_status()

            data = response.json()
            return self._parse_products(data.get("Products", []), limit)

        except requests.RequestException:
            return []

    def add_to_cart(self, product_id: int | str, quantity: int = 1) -> bool:
        """
        Add a product to the shopping cart.

        Args:
            product_id: The Nemlig product ID
            quantity: Number of items to add

        Returns:
            True if successful

        Raises:
            NemligAPIError: If adding fails or not logged in
        """
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to add items to cart")

        url = f"{API_BASE_URL}/basket/AddToBasket"
        payload = {"ProductId": int(product_id), "Quantity": quantity}

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            raise NemligAPIError(f"Failed to add to cart: {e}") from e

    def add_multiple_to_cart(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Add multiple products to cart.

        Args:
            items: List of dicts with 'product_id' and 'quantity' keys

        Returns:
            Dict with 'success' list and 'failed' list
        """
        results: dict[str, list] = {"success": [], "failed": []}

        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)

            if product_id is None:
                results["failed"].append({"product_id": None, "error": "Missing product_id"})
                continue

            try:
                self.add_to_cart(product_id, quantity)
                results["success"].append(product_id)
            except NemligAPIError as e:
                results["failed"].append({"product_id": product_id, "error": str(e)})

        return results

    def get_cart(self) -> dict[str, Any]:
        """
        Get current cart contents.

        Returns:
            Cart data including items and total
        """
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to view cart")

        url = f"{API_BASE_URL}/basket/GetBasket"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            raise NemligAPIError(f"Failed to get cart: {e}") from e

    def clear_cart(self) -> bool:
        """Clear all items from cart."""
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to clear cart")

        url = f"{API_BASE_URL}/basket/ClearBasket"

        try:
            response = self.session.post(url)
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            raise NemligAPIError(f"Failed to clear cart: {e}") from e

    def get_order_history(self, skip: int = 0, take: int = 10) -> list[dict[str, Any]]:
        """
        Get list of previous orders.

        Args:
            skip: Number of orders to skip (for pagination)
            take: Number of orders to retrieve

        Returns:
            List of order summaries with Id, OrderNumber, OrderDate, Total, etc.

        Raises:
            NemligAPIError: If not logged in or request fails
        """
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to view order history")

        url = f"{API_BASE_URL}/order/GetBasicOrderHistory"
        params = {"skip": skip, "take": take}

        try:
            response = self.session.get(url, params=params, headers=self._get_correlation_headers())
            response.raise_for_status()
            data = response.json()
            return data.get("Orders", [])

        except requests.RequestException as e:
            raise NemligAPIError(f"Failed to get order history: {e}") from e

    def get_order_details(self, order_id: int) -> list[dict[str, Any]]:
        """
        Get detailed product lines for a specific order.

        Args:
            order_id: The order Id (not OrderNumber)

        Returns:
            List of order lines with ProductNumber, ProductName, Quantity, etc.

        Raises:
            NemligAPIError: If not logged in or request fails
        """
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to view order details")

        url = f"{API_BASE_URL}/v2/order/GetOrderHistory/{order_id}"

        try:
            response = self.session.get(url, headers=self._get_correlation_headers())
            response.raise_for_status()
            data = response.json()
            # Filter to only product lines (not deposits, recipes, etc.)
            lines = data.get("Lines", [])
            return [line for line in lines if line.get("IsProductLine", False)]

        except requests.RequestException as e:
            raise NemligAPIError(f"Failed to get order details: {e}") from e

    def get_previous_order_products(self, num_orders: int = 5) -> list[dict[str, Any]]:
        """
        Get all unique products from recent orders.

        Args:
            num_orders: Number of recent orders to fetch products from

        Returns:
            List of unique products with ProductNumber, ProductName, GroupName, etc.
            Products are deduplicated by ProductNumber, with most recent occurrence kept.
        """
        if not self._logged_in:
            raise NemligAPIError("Must be logged in to get previous order products")

        orders = self.get_order_history(skip=0, take=num_orders)

        # Collect products from all orders, keeping most recent occurrence
        products_by_id: dict[str, dict[str, Any]] = {}

        for order in orders:
            order_id = order.get("Id")
            if not order_id:
                continue

            try:
                lines = self.get_order_details(order_id)
                for line in lines:
                    product_num = line.get("ProductNumber")
                    if product_num and product_num not in products_by_id:
                        products_by_id[product_num] = {
                            "product_id": product_num,
                            "name": line.get("ProductName", ""),
                            "category": line.get("GroupName", ""),
                            "main_category": line.get("MainGroupName", ""),
                            "description": line.get("Description", ""),
                        }
            except NemligAPIError:
                # Skip orders we can't fetch
                continue

        return list(products_by_id.values())
