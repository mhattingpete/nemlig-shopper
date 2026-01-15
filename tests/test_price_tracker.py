"""Tests for price tracking functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

from nemlig_shopper.price_tracker import (
    PriceAlert,
    PriceRecord,
    PriceStats,
    PriceTracker,
)


def make_product(
    product_id: int,
    name: str,
    price: float,
    category: str = "Mejeri",
    unit_size: str = "1L",
    unit_price: float | None = None,
) -> dict:
    """Create a product dict for testing."""
    return {
        "id": product_id,
        "name": name,
        "price": price,
        "category": category,
        "unit_size": unit_size,
        "unit_price_calc": unit_price or price,
    }


class TestPriceTracker:
    """Tests for PriceTracker class."""

    def test_record_price(self):
        """Test recording a single price."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            product = make_product(123, "Test Milk", 15.00)
            tracker.record_price(product)

            assert tracker.get_tracked_count() == 1
            assert tracker.get_price_count() == 1

            tracker.close()

    def test_record_multiple_prices(self):
        """Test recording multiple prices."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            products = [
                make_product(1, "Milk", 15.00),
                make_product(2, "Cheese", 35.00),
                make_product(3, "Butter", 25.00),
            ]

            count = tracker.record_prices(products)

            assert count == 3
            assert tracker.get_tracked_count() == 3
            assert tracker.get_price_count() == 3

            tracker.close()

    def test_record_price_updates_product(self):
        """Test that recording prices updates product info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Record first price
            product1 = make_product(123, "Old Name", 15.00)
            tracker.record_price(product1)

            # Record updated price with new name
            product2 = make_product(123, "New Name", 16.00)
            tracker.record_price(product2)

            # Should still be 1 product, but 2 price records
            assert tracker.get_tracked_count() == 1
            assert tracker.get_price_count() == 2

            # Search should find new name
            found = tracker.search_products("New Name")
            assert len(found) == 1
            assert found[0]["name"] == "New Name"

            tracker.close()

    def test_skip_product_without_id(self):
        """Test that products without IDs are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            product = {"name": "No ID Product", "price": 10.00}
            tracker.record_price(product)

            assert tracker.get_tracked_count() == 0

            tracker.close()

    def test_skip_product_without_price(self):
        """Test that products without prices are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            product = {"id": 123, "name": "No Price Product"}
            tracker.record_price(product)

            assert tracker.get_tracked_count() == 0

            tracker.close()


class TestPriceHistory:
    """Tests for price history retrieval."""

    def test_get_history_by_id(self):
        """Test getting price history by product ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Record multiple prices
            for price in [15.00, 16.00, 14.50]:
                tracker.record_price(make_product(123, "Test Milk", price))

            history = tracker.get_price_history(product_id=123)

            assert len(history) == 3
            # Newest first
            assert history[0].price == 14.50
            assert history[1].price == 16.00
            assert history[2].price == 15.00

            tracker.close()

    def test_get_history_by_name(self):
        """Test getting price history by product name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            tracker.record_price(make_product(123, "Arla Minimælk 1L", 15.00))
            tracker.record_price(make_product(123, "Arla Minimælk 1L", 16.00))

            history = tracker.get_price_history(product_name="Minimælk")

            assert len(history) == 2

            tracker.close()

    def test_history_respects_days_limit(self):
        """Test that history respects the days parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Record a price
            tracker.record_price(make_product(123, "Test", 15.00))

            # Get history with very short window
            history = tracker.get_price_history(product_id=123, days=0)

            # Should find nothing with 0 days
            assert len(history) == 0

            tracker.close()


class TestPriceStats:
    """Tests for price statistics."""

    def test_get_stats(self):
        """Test getting price statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Record prices: 10, 15, 20 -> avg=15, min=10, max=20
            for price in [10.00, 15.00, 20.00]:
                tracker.record_price(make_product(123, "Test Product", price))

            stats = tracker.get_price_stats(123)

            assert stats is not None
            assert stats.product_id == 123
            assert stats.product_name == "Test Product"
            assert stats.current_price == 20.00  # Last recorded
            assert stats.min_price == 10.00
            assert stats.max_price == 20.00
            assert stats.avg_price == 15.00
            assert stats.price_count == 3

            tracker.close()

    def test_stats_not_found(self):
        """Test stats for non-existent product."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            stats = tracker.get_price_stats(999)

            assert stats is None

            tracker.close()

    def test_is_on_sale(self):
        """Test the is_on_sale property."""
        # On sale: current < avg * 0.95
        stats = PriceStats(
            product_id=1,
            product_name="Test",
            current_price=9.00,
            min_price=8.00,
            max_price=12.00,
            avg_price=10.00,
            price_count=5,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

        assert stats.is_on_sale is True

    def test_not_on_sale(self):
        """Test is_on_sale when price is normal."""
        stats = PriceStats(
            product_id=1,
            product_name="Test",
            current_price=10.00,
            min_price=8.00,
            max_price=12.00,
            avg_price=10.00,
            price_count=5,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

        assert stats.is_on_sale is False

    def test_discount_percent(self):
        """Test discount percentage calculation."""
        stats = PriceStats(
            product_id=1,
            product_name="Test",
            current_price=8.00,
            min_price=8.00,
            max_price=12.00,
            avg_price=10.00,
            price_count=5,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

        # (10 - 8) / 10 * 100 = 20%
        assert stats.discount_percent == 20.0


class TestPriceAlerts:
    """Tests for price alerts functionality."""

    def test_get_alerts(self):
        """Test getting price alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Product with price drop: avg=(20+15)/2=17.5, discount=(17.5-15)/17.5=14.3%
            tracker.record_price(make_product(1, "On Sale", 20.00))
            tracker.record_price(make_product(1, "On Sale", 15.00))

            # Product with stable price - no discount
            tracker.record_price(make_product(2, "Stable", 10.00))
            tracker.record_price(make_product(2, "Stable", 10.00))

            alerts = tracker.get_price_alerts(min_discount=10.0)

            assert len(alerts) == 1
            assert alerts[0].product_name == "On Sale"
            assert alerts[0].discount_percent > 14  # ~14.3%

            tracker.close()

    def test_alerts_sorted_by_discount(self):
        """Test that alerts are sorted by discount percentage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # 10% discount
            tracker.record_price(make_product(1, "Small Sale", 100.00))
            tracker.record_price(make_product(1, "Small Sale", 90.00))

            # 30% discount
            tracker.record_price(make_product(2, "Big Sale", 100.00))
            tracker.record_price(make_product(2, "Big Sale", 70.00))

            alerts = tracker.get_price_alerts(min_discount=5.0)

            assert len(alerts) == 2
            assert alerts[0].product_name == "Big Sale"  # Bigger discount first
            assert alerts[1].product_name == "Small Sale"

            tracker.close()

    def test_is_lowest_flag(self):
        """Test the is_lowest flag on alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            # Record prices where current is the lowest
            tracker.record_price(make_product(1, "Lowest Ever", 20.00))
            tracker.record_price(make_product(1, "Lowest Ever", 15.00))
            tracker.record_price(make_product(1, "Lowest Ever", 10.00))  # New low!

            alerts = tracker.get_price_alerts(min_discount=5.0)

            assert len(alerts) == 1
            assert alerts[0].is_lowest is True

            tracker.close()


class TestSearchProducts:
    """Tests for product search."""

    def test_search_by_name(self):
        """Test searching products by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            tracker.record_price(make_product(1, "Arla Minimælk 1L", 15.00))
            tracker.record_price(make_product(2, "Arla Letmælk 1L", 14.00))
            tracker.record_price(make_product(3, "Lurpak Butter", 30.00))

            # Search for "mælk"
            results = tracker.search_products("mælk")

            assert len(results) == 2
            names = [r["name"] for r in results]
            assert "Arla Minimælk 1L" in names
            assert "Arla Letmælk 1L" in names

            tracker.close()

    def test_search_respects_limit(self):
        """Test that search respects the limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            for i in range(10):
                tracker.record_price(make_product(i, f"Product {i}", 10.00))

            results = tracker.search_products("Product", limit=3)

            assert len(results) == 3

            tracker.close()


class TestClearData:
    """Tests for clearing data."""

    def test_clear_all(self):
        """Test clearing all data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            tracker = PriceTracker(db_path)

            tracker.record_price(make_product(1, "Test", 10.00))
            tracker.record_price(make_product(2, "Test 2", 20.00))

            assert tracker.get_tracked_count() == 2

            tracker.clear_all()

            assert tracker.get_tracked_count() == 0
            assert tracker.get_price_count() == 0

            tracker.close()


class TestPriceRecord:
    """Tests for PriceRecord dataclass."""

    def test_from_row(self):
        """Test creating PriceRecord from database row."""

        # Create a mock row (dict-like)
        class MockRow:
            def __getitem__(self, key):
                data = {
                    "product_id": 123,
                    "product_name": "Test",
                    "price": 15.00,
                    "unit_price": 1.50,
                    "recorded_at": "2024-01-15T10:30:00",
                }
                return data[key]

        record = PriceRecord.from_row(MockRow())

        assert record.product_id == 123
        assert record.product_name == "Test"
        assert record.price == 15.00
        assert record.unit_price == 1.50
        assert record.recorded_at == datetime(2024, 1, 15, 10, 30, 0)


class TestPriceAlert:
    """Tests for PriceAlert dataclass."""

    def test_alert_properties(self):
        alert = PriceAlert(
            product_id=1,
            product_name="Sale Item",
            current_price=8.00,
            avg_price=10.00,
            min_price=8.00,
            discount_percent=20.0,
            is_lowest=True,
        )

        assert alert.product_name == "Sale Item"
        assert alert.discount_percent == 20.0
        assert alert.is_lowest is True
