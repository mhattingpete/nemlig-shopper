"""Tests for TUI module."""

from nemlig_shopper.matcher import ProductMatch, select_alternative
from nemlig_shopper.tui import ReviewResult, ReviewScreen


def make_match(
    name: str,
    product_name: str | None = None,
    price: float | None = None,
    alternatives: list[dict] | None = None,
) -> ProductMatch:
    """Create a ProductMatch for testing."""
    if product_name:
        product = {
            "id": 123,
            "name": product_name,
            "price": price,
            "available": True,
        }
        matched = True
    else:
        product = None
        matched = False

    return ProductMatch(
        ingredient_name=name,
        product=product,
        quantity=1,
        matched=matched,
        search_query=name,
        alternatives=alternatives or [],
    )


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_confirmed_result(self):
        matches = [make_match("onion", "Løg")]
        result = ReviewResult(confirmed=True, matches=matches)

        assert result.confirmed is True
        assert len(result.matches) == 1
        assert result.matches[0].ingredient_name == "onion"

    def test_cancelled_result(self):
        matches = [make_match("onion", "Løg")]
        result = ReviewResult(confirmed=False, matches=matches)

        assert result.confirmed is False
        assert len(result.matches) == 1


class TestReviewScreen:
    """Tests for ReviewScreen app."""

    def test_screen_initialization(self):
        matches = [
            make_match("onion", "Løg", 10.0),
            make_match("garlic", "Hvidløg", 15.0),
        ]

        app = ReviewScreen(matches, "Test Recipe")

        assert len(app.matches) == 2
        assert app.recipe_title == "Test Recipe"

    def test_screen_copies_matches(self):
        """Ensure the screen makes a copy of matches."""
        matches = [make_match("onion", "Løg", 10.0)]
        app = ReviewScreen(matches, "Test")

        # Modify original - should not affect app
        matches.append(make_match("garlic", "Hvidløg"))

        assert len(app.matches) == 1

    def test_default_title(self):
        app = ReviewScreen([], None)
        assert app.recipe_title == "Shopping List"

    def test_get_summary_all_matched(self):
        matches = [
            make_match("onion", "Løg", 10.0),
            make_match("garlic", "Hvidløg", 15.0),
        ]
        app = ReviewScreen(matches, "Test")

        summary = app._get_summary()

        assert "Items: 2" in summary
        assert "Matched: 2" in summary
        assert "Unmatched: 0" in summary
        assert "Total: 25.00 DKK" in summary

    def test_get_summary_with_unmatched(self):
        matches = [
            make_match("onion", "Løg", 10.0),
            make_match("rare_spice"),  # Unmatched
        ]
        app = ReviewScreen(matches, "Test")

        summary = app._get_summary()

        assert "Items: 2" in summary
        assert "Matched: 1" in summary
        assert "Unmatched: 1" in summary
        assert "Total: 10.00 DKK" in summary

    def test_get_summary_with_quantities(self):
        match = make_match("onion", "Løg", 10.0)
        match.quantity = 3
        app = ReviewScreen([match], "Test")

        summary = app._get_summary()

        # 10.0 * 3 = 30.0
        assert "Total: 30.00 DKK" in summary


class TestSelectAlternative:
    """Tests for select_alternative function (used by TUI)."""

    def test_select_first_alternative(self):
        alt1 = {"id": 456, "name": "Alt Product 1", "price": 12.0}
        alt2 = {"id": 789, "name": "Alt Product 2", "price": 14.0}
        match = make_match("onion", "Original", 10.0, alternatives=[alt1, alt2])

        new_match = select_alternative(match, 0)

        assert new_match.product_name == "Alt Product 1"
        assert new_match.price == 12.0
        # Original should now be in alternatives
        assert len(new_match.alternatives) == 2
        assert new_match.alternatives[0]["name"] == "Original"

    def test_select_second_alternative(self):
        alt1 = {"id": 456, "name": "Alt 1", "price": 12.0}
        alt2 = {"id": 789, "name": "Alt 2", "price": 14.0}
        match = make_match("onion", "Original", 10.0, alternatives=[alt1, alt2])

        new_match = select_alternative(match, 1)

        assert new_match.product_name == "Alt 2"
        assert new_match.price == 14.0

    def test_select_invalid_index(self):
        alt1 = {"id": 456, "name": "Alt 1", "price": 12.0}
        match = make_match("onion", "Original", 10.0, alternatives=[alt1])

        # Index out of range - should return same match
        new_match = select_alternative(match, 5)

        assert new_match.product_name == "Original"

    def test_select_no_alternatives(self):
        match = make_match("onion", "Original", 10.0, alternatives=[])

        # No alternatives - should return same match
        new_match = select_alternative(match, 0)

        assert new_match.product_name == "Original"


class TestReviewScreenIntegration:
    """Integration tests for ReviewScreen (without actually running the app)."""

    def test_matches_can_be_modified(self):
        """Test that matches can be swapped via select_alternative."""
        alt = {"id": 456, "name": "Alternative", "price": 8.0}
        matches = [make_match("onion", "Original", 10.0, alternatives=[alt])]

        app = ReviewScreen(matches, "Test")

        # Simulate selecting alternative
        app.matches[0] = select_alternative(app.matches[0], 0)

        assert app.matches[0].product_name == "Alternative"
        assert app.matches[0].price == 8.0

    def test_multiple_swaps(self):
        """Test multiple alternative swaps."""
        alt1 = {"id": 456, "name": "Alt 1", "price": 8.0}
        alt2 = {"id": 789, "name": "Alt 2", "price": 6.0}
        matches = [make_match("onion", "Original", 10.0, alternatives=[alt1, alt2])]

        app = ReviewScreen(matches, "Test")

        # First swap
        app.matches[0] = select_alternative(app.matches[0], 0)
        assert app.matches[0].product_name == "Alt 1"

        # Second swap (Original is now at index 0 in alternatives)
        app.matches[0] = select_alternative(app.matches[0], 0)
        assert app.matches[0].product_name == "Original"
