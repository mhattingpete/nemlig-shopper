"""Tests for the config module."""

import json
import stat

import pytest


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / ".nemlig-shopper"
    config_dir.mkdir(parents=True, exist_ok=True)

    credentials_file = config_dir / "credentials.json"

    monkeypatch.setattr("nemlig_shopper.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("nemlig_shopper.config.CREDENTIALS_FILE", credentials_file)

    return credentials_file


@pytest.fixture
def clear_env_credentials(monkeypatch):
    """Clear any environment credentials."""
    monkeypatch.delenv("NEMLIG_USERNAME", raising=False)
    monkeypatch.delenv("NEMLIG_PASSWORD", raising=False)


# ============================================================================
# Get Credentials Tests
# ============================================================================


class TestGetCredentials:
    """Tests for get_credentials function."""

    def test_get_from_environment(self, temp_config_dir, monkeypatch):
        """Should return credentials from environment variables."""
        monkeypatch.setenv("NEMLIG_USERNAME", "env_user@example.com")
        monkeypatch.setenv("NEMLIG_PASSWORD", "env_password123")

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username == "env_user@example.com"
        assert password == "env_password123"

    def test_get_from_file(self, temp_config_dir, clear_env_credentials):
        """Should return credentials from file when env vars not set."""
        # Create credentials file
        with open(temp_config_dir, "w") as f:
            json.dump({"username": "file_user@example.com", "password": "file_pass"}, f)

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username == "file_user@example.com"
        assert password == "file_pass"

    def test_env_takes_precedence_over_file(self, temp_config_dir, monkeypatch):
        """Environment variables should take precedence over file."""
        # Set both env vars and file
        monkeypatch.setenv("NEMLIG_USERNAME", "env_user@example.com")
        monkeypatch.setenv("NEMLIG_PASSWORD", "env_password")

        with open(temp_config_dir, "w") as f:
            json.dump({"username": "file_user@example.com", "password": "file_pass"}, f)

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username == "env_user@example.com"
        assert password == "env_password"

    def test_returns_none_when_no_credentials(self, temp_config_dir, clear_env_credentials):
        """Should return None, None when no credentials available."""
        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username is None
        assert password is None

    def test_returns_none_for_partial_env(self, temp_config_dir, monkeypatch):
        """Should return None when only username is in env (no password)."""
        monkeypatch.setenv("NEMLIG_USERNAME", "user@example.com")
        monkeypatch.delenv("NEMLIG_PASSWORD", raising=False)

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        # Falls through to file, which doesn't exist
        assert username is None
        assert password is None

    def test_handles_corrupt_credentials_file(self, temp_config_dir, clear_env_credentials):
        """Should handle corrupt credentials file gracefully."""
        with open(temp_config_dir, "w") as f:
            f.write("{ invalid json }")

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username is None
        assert password is None

    def test_handles_missing_fields_in_file(self, temp_config_dir, clear_env_credentials):
        """Should handle missing fields in credentials file."""
        with open(temp_config_dir, "w") as f:
            json.dump({"username": "only_username"}, f)

        from nemlig_shopper.config import get_credentials

        username, password = get_credentials()

        assert username == "only_username"
        assert password is None


# ============================================================================
# Save Credentials Tests
# ============================================================================


class TestSaveCredentials:
    """Tests for save_credentials function."""

    def test_save_creates_file(self, temp_config_dir):
        """Should create credentials file with correct data."""
        from nemlig_shopper.config import save_credentials

        save_credentials("test@example.com", "mypassword123")

        assert temp_config_dir.exists()
        with open(temp_config_dir) as f:
            data = json.load(f)

        assert data["username"] == "test@example.com"
        assert data["password"] == "mypassword123"

    def test_save_sets_restrictive_permissions(self, temp_config_dir):
        """Should set file permissions to 600 (owner read/write only)."""
        from nemlig_shopper.config import save_credentials

        save_credentials("test@example.com", "password")

        # Check permissions
        mode = temp_config_dir.stat().st_mode
        assert stat.S_IMODE(mode) == 0o600

    def test_save_overwrites_existing(self, temp_config_dir):
        """Should overwrite existing credentials."""
        from nemlig_shopper.config import save_credentials

        # Save initial credentials
        save_credentials("old@example.com", "oldpass")

        # Overwrite with new
        save_credentials("new@example.com", "newpass")

        with open(temp_config_dir) as f:
            data = json.load(f)

        assert data["username"] == "new@example.com"
        assert data["password"] == "newpass"

    def test_save_handles_special_characters(self, temp_config_dir, clear_env_credentials):
        """Should handle special characters in credentials."""
        from nemlig_shopper.config import get_credentials, save_credentials

        # Password with special characters
        special_pass = "p@$$w0rd!#%&*()"

        save_credentials("user@example.com", special_pass)

        username, password = get_credentials()

        assert password == special_pass

    def test_save_handles_unicode(self, temp_config_dir):
        """Should handle unicode in credentials."""
        from nemlig_shopper.config import save_credentials

        save_credentials("brugër@example.com", "løsenord")

        with open(temp_config_dir) as f:
            data = json.load(f)

        assert data["username"] == "brugër@example.com"
        assert data["password"] == "løsenord"


# ============================================================================
# Clear Credentials Tests
# ============================================================================


class TestClearCredentials:
    """Tests for clear_credentials function."""

    def test_clear_removes_file(self, temp_config_dir):
        """Should remove the credentials file."""
        from nemlig_shopper.config import clear_credentials, save_credentials

        # Create credentials first
        save_credentials("test@example.com", "password")
        assert temp_config_dir.exists()

        # Clear them
        clear_credentials()

        assert not temp_config_dir.exists()

    def test_clear_when_no_file_exists(self, temp_config_dir):
        """Should handle clearing when no file exists."""
        from nemlig_shopper.config import clear_credentials

        assert not temp_config_dir.exists()

        # Should not raise
        clear_credentials()

        assert not temp_config_dir.exists()

    def test_clear_then_get_returns_none(self, temp_config_dir, clear_env_credentials):
        """After clearing, get_credentials should return None."""
        from nemlig_shopper.config import clear_credentials, get_credentials, save_credentials

        save_credentials("test@example.com", "password")
        clear_credentials()

        username, password = get_credentials()

        assert username is None
        assert password is None


# ============================================================================
# Integration Tests
# ============================================================================


class TestCredentialsIntegration:
    """Integration tests for credential management."""

    def test_save_and_get_roundtrip(self, temp_config_dir, clear_env_credentials):
        """Credentials should survive save/get cycle."""
        from nemlig_shopper.config import get_credentials, save_credentials

        save_credentials("roundtrip@example.com", "roundtrip_pass")

        username, password = get_credentials()

        assert username == "roundtrip@example.com"
        assert password == "roundtrip_pass"

    def test_multiple_save_clear_cycles(self, temp_config_dir, clear_env_credentials):
        """Should handle multiple save/clear cycles."""
        from nemlig_shopper.config import clear_credentials, get_credentials, save_credentials

        for i in range(3):
            save_credentials(f"user{i}@example.com", f"pass{i}")
            username, password = get_credentials()
            assert username == f"user{i}@example.com"

            clear_credentials()
            username, password = get_credentials()
            assert username is None
