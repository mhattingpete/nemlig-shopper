"""Tests for the show_slots() bug fix where None values would crash CLI formatting."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nemlig_shopper.cli import cli


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestShowSlotsNoneHandling:
    """Test that show_slots handles None values gracefully."""

    def test_handles_none_start_hour(self, runner):
        """Should skip slot with None start_hour and show warning."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": None,  # Bug: None value
                "end_hour": 12,
                "id": 123,
                "delivery_price": 29.0,
                "is_available": True,
                "is_free": False,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "⚠ Skipping malformed slot" in result.output
        assert "missing start_hour, end_hour, or id" in result.output

    def test_handles_none_end_hour(self, runner):
        """Should skip slot with None end_hour and show warning."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 10,
                "end_hour": None,  # Bug: None value
                "id": 123,
                "delivery_price": 29.0,
                "is_available": True,
                "is_free": False,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "⚠ Skipping malformed slot" in result.output

    def test_handles_none_slot_id(self, runner):
        """Should skip slot with None id and show warning."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 10,
                "end_hour": 12,
                "id": None,  # Bug: None value
                "delivery_price": 29.0,
                "is_available": True,
                "is_free": False,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "⚠ Skipping malformed slot" in result.output

    def test_handles_none_price(self, runner):
        """Should display 'Free' when price is None."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 10,
                "end_hour": 12,
                "id": 123,
                "delivery_price": None,  # None price should show as "Free"
                "is_available": True,
                "is_free": False,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "10:00-12:00" in result.output
        assert "Free" in result.output
        assert "ID: 123" in result.output

    def test_handles_missing_keys(self, runner):
        """Should skip slot when dictionary keys are missing entirely."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                # Missing start_hour, end_hour, id keys entirely
                "delivery_price": 29.0,
                "is_available": True,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "⚠ Skipping malformed slot" in result.output

    def test_mixed_valid_and_invalid_slots(self, runner):
        """Should display valid slots and skip invalid ones."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 8,
                "end_hour": 10,
                "id": 100,
                "delivery_price": 0.0,
                "is_available": True,
                "is_free": True,
            },
            {
                "date": "2026-01-15",
                "start_hour": None,  # Invalid
                "end_hour": 12,
                "id": 101,
                "delivery_price": 29.0,
                "is_available": True,
                "is_free": False,
            },
            {
                "date": "2026-01-15",
                "start_hour": 12,
                "end_hour": 14,
                "id": 102,
                "delivery_price": 29.0,
                "is_available": False,
                "is_free": False,
            },
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        # Valid slots should appear
        assert "08:00-10:00" in result.output
        assert "ID: 100" in result.output
        assert "12:00-14:00" in result.output
        assert "ID: 102" in result.output
        # Invalid slot should be skipped with warning
        assert "⚠ Skipping malformed slot" in result.output
        # ID 101 should not appear in slot listing
        assert "ID: 101" not in result.output

    def test_handles_none_is_available(self, runner):
        """Should treat None is_available as False."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 10,
                "end_hour": 12,
                "id": 123,
                "delivery_price": 29.0,
                "is_available": None,  # Should default to False/✗
                "is_free": False,
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "✗" in result.output  # Should show unavailable marker
        assert "10:00-12:00" in result.output

    def test_handles_none_is_free(self, runner):
        """Should handle None is_free without crashing."""
        mock_api = MagicMock()
        mock_api.get_delivery_slots.return_value = [
            {
                "date": "2026-01-15",
                "start_hour": 10,
                "end_hour": 12,
                "id": 123,
                "delivery_price": 0.0,
                "is_available": True,
                "is_free": None,  # Should default to False
            }
        ]

        with patch("nemlig_shopper.cli.get_api", return_value=mock_api):
            with patch("nemlig_shopper.cli.ensure_logged_in", return_value=True):
                result = runner.invoke(cli, ["slots"])

        assert result.exit_code == 0
        assert "10:00-12:00" in result.output
        # Should show "0.00 DKK" without " (FREE)" suffix
        assert "0.00 DKK" in result.output
        assert "(FREE)" not in result.output
