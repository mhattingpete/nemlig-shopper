"""Price tracking and history with SQLite storage."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def get_db_path() -> Path:
    """Get the path to the price database."""
    db_dir = Path.home() / ".nemlig-shopper"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "prices.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            unit_size TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            price REAL NOT NULL,
            unit_price REAL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_prices_product_id ON prices(product_id);
        CREATE INDEX IF NOT EXISTS idx_prices_recorded_at ON prices(recorded_at);
        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
    """)
    conn.commit()


@dataclass
class PriceRecord:
    """A single price record for a product."""

    product_id: int
    product_name: str
    price: float
    unit_price: float | None
    recorded_at: datetime

    @classmethod
    def from_row(cls, row: Any) -> "PriceRecord":
        """Create from a sqlite3.Row or dict-like object."""
        return cls(
            product_id=row["product_id"],
            product_name=row["product_name"],
            price=row["price"],
            unit_price=row["unit_price"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )


@dataclass
class PriceStats:
    """Statistics for a product's price history."""

    product_id: int
    product_name: str
    current_price: float
    min_price: float
    max_price: float
    avg_price: float
    price_count: int
    first_seen: datetime
    last_seen: datetime

    @property
    def is_on_sale(self) -> bool:
        """Check if current price is below average."""
        return self.current_price < self.avg_price * 0.95  # 5% threshold

    @property
    def discount_percent(self) -> float:
        """Calculate discount percentage from average."""
        if self.avg_price == 0:
            return 0.0
        return ((self.avg_price - self.current_price) / self.avg_price) * 100


@dataclass
class PriceAlert:
    """An alert for a product on sale."""

    product_id: int
    product_name: str
    current_price: float
    avg_price: float
    min_price: float
    discount_percent: float
    is_lowest: bool


class PriceTracker:
    """Track product prices over time."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_db_path()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = get_connection(self.db_path)
            init_db(self._conn)
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def record_price(self, product: dict[str, Any]) -> None:
        """
        Record a price for a product.

        Args:
            product: Product dict from API with id, name, price, etc.
        """
        product_id = product.get("id")
        if not product_id:
            return

        name = product.get("name", "Unknown")
        category = product.get("category", "")
        unit_size = product.get("unit_size", "")
        price = product.get("price")
        unit_price = product.get("unit_price_calc") or product.get("unit_price")

        if price is None:
            return

        now = datetime.now().isoformat()

        # Upsert product
        self.conn.execute(
            """
            INSERT INTO products (id, name, category, unit_size, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                unit_size = excluded.unit_size,
                last_seen = excluded.last_seen
            """,
            (product_id, name, category, unit_size, now, now),
        )

        # Insert price record
        self.conn.execute(
            """
            INSERT INTO prices (product_id, price, unit_price, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, price, unit_price, now),
        )

        self.conn.commit()

    def record_prices(self, products: list[dict[str, Any]]) -> int:
        """
        Record prices for multiple products.

        Args:
            products: List of product dicts from API

        Returns:
            Number of prices recorded
        """
        count = 0
        for product in products:
            if product.get("id") and product.get("price"):
                self.record_price(product)
                count += 1
        return count

    def get_price_history(
        self,
        product_id: int | None = None,
        product_name: str | None = None,
        days: int = 30,
    ) -> list[PriceRecord]:
        """
        Get price history for a product.

        Args:
            product_id: Product ID (preferred)
            product_name: Product name (fuzzy search if no ID)
            days: Number of days to look back

        Returns:
            List of price records, newest first
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        if product_id:
            rows = self.conn.execute(
                """
                SELECT p.product_id, pr.name as product_name, p.price, p.unit_price, p.recorded_at
                FROM prices p
                JOIN products pr ON p.product_id = pr.id
                WHERE p.product_id = ? AND p.recorded_at >= ?
                ORDER BY p.recorded_at DESC
                """,
                (product_id, cutoff),
            ).fetchall()
        elif product_name:
            # Fuzzy search by name
            rows = self.conn.execute(
                """
                SELECT p.product_id, pr.name as product_name, p.price, p.unit_price, p.recorded_at
                FROM prices p
                JOIN products pr ON p.product_id = pr.id
                WHERE pr.name LIKE ? AND p.recorded_at >= ?
                ORDER BY p.recorded_at DESC
                """,
                (f"%{product_name}%", cutoff),
            ).fetchall()
        else:
            return []

        return [PriceRecord.from_row(row) for row in rows]

    def get_price_stats(self, product_id: int) -> PriceStats | None:
        """
        Get price statistics for a product.

        Args:
            product_id: Product ID

        Returns:
            PriceStats or None if no data
        """
        row = self.conn.execute(
            """
            SELECT
                pr.id as product_id,
                pr.name as product_name,
                (SELECT price FROM prices WHERE product_id = pr.id ORDER BY recorded_at DESC LIMIT 1) as current_price,
                MIN(p.price) as min_price,
                MAX(p.price) as max_price,
                AVG(p.price) as avg_price,
                COUNT(p.id) as price_count,
                pr.first_seen,
                pr.last_seen
            FROM products pr
            JOIN prices p ON pr.id = p.product_id
            WHERE pr.id = ?
            GROUP BY pr.id
            """,
            (product_id,),
        ).fetchone()

        if not row:
            return None

        return PriceStats(
            product_id=row["product_id"],
            product_name=row["product_name"],
            current_price=row["current_price"],
            min_price=row["min_price"],
            max_price=row["max_price"],
            avg_price=row["avg_price"],
            price_count=row["price_count"],
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
        )

    def search_products(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Search tracked products by name.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of product dicts with id, name, category
        """
        rows = self.conn.execute(
            """
            SELECT id, name, category, unit_size, first_seen, last_seen
            FROM products
            WHERE name LIKE ?
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()

        return [dict(row) for row in rows]

    def get_price_alerts(self, min_discount: float = 5.0) -> list[PriceAlert]:
        """
        Get products that are currently on sale.

        Args:
            min_discount: Minimum discount percentage to include

        Returns:
            List of PriceAlert for products on sale
        """
        # Get products with significant price drops
        rows = self.conn.execute(
            """
            SELECT
                pr.id as product_id,
                pr.name as product_name,
                (SELECT price FROM prices WHERE product_id = pr.id ORDER BY recorded_at DESC LIMIT 1) as current_price,
                MIN(p.price) as min_price,
                AVG(p.price) as avg_price
            FROM products pr
            JOIN prices p ON pr.id = p.product_id
            GROUP BY pr.id
            HAVING COUNT(p.id) >= 2  -- Need at least 2 price points
            """,
        ).fetchall()

        alerts = []
        for row in rows:
            current = row["current_price"]
            avg = row["avg_price"]
            min_price = row["min_price"]

            if avg > 0:
                discount = ((avg - current) / avg) * 100
                if discount >= min_discount:
                    alerts.append(
                        PriceAlert(
                            product_id=row["product_id"],
                            product_name=row["product_name"],
                            current_price=current,
                            avg_price=avg,
                            min_price=min_price,
                            discount_percent=discount,
                            is_lowest=current <= min_price,
                        )
                    )

        # Sort by discount percentage
        alerts.sort(key=lambda a: a.discount_percent, reverse=True)
        return alerts

    def get_tracked_count(self) -> int:
        """Get the number of tracked products."""
        row = self.conn.execute("SELECT COUNT(*) as count FROM products").fetchone()
        return row["count"] if row else 0

    def get_price_count(self) -> int:
        """Get the total number of price records."""
        row = self.conn.execute("SELECT COUNT(*) as count FROM prices").fetchone()
        return row["count"] if row else 0

    def clear_old_prices(self, days: int = 90) -> int:
        """
        Remove price records older than specified days.

        Args:
            days: Remove records older than this many days

        Returns:
            Number of records removed
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self.conn.execute(
            "DELETE FROM prices WHERE recorded_at < ?",
            (cutoff,),
        )
        self.conn.commit()
        return cursor.rowcount

    def clear_all(self) -> None:
        """Clear all price data."""
        self.conn.execute("DELETE FROM prices")
        self.conn.execute("DELETE FROM products")
        self.conn.commit()


# Module-level tracker instance
_tracker: PriceTracker | None = None


def get_tracker() -> PriceTracker:
    """Get or create the global price tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PriceTracker()
    return _tracker


def record_search_prices(products: list[dict[str, Any]]) -> int:
    """
    Record prices from a search result.

    Call this after API searches to build price history.

    Args:
        products: List of product dicts from search

    Returns:
        Number of prices recorded
    """
    return get_tracker().record_prices(products)
