"""Configuration and credential management for Nemlig Shopper."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App directories
APP_NAME = "nemlig-shopper"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
PREFERENCES_FILE = CONFIG_DIR / "preferences.json"
PANTRY_FILE = CONFIG_DIR / "pantry.txt"  # Simple text file, one item per line

# Ensure config directory exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# API Configuration
API_BASE_URL = "https://www.nemlig.com/webapi"


def get_credentials() -> tuple[str | None, str | None]:
    """Get Nemlig credentials from environment or config file."""
    username = os.getenv("NEMLIG_USERNAME")
    password = os.getenv("NEMLIG_PASSWORD")

    if username and password:
        return username, password

    # Try reading from credentials file
    if CREDENTIALS_FILE.exists():
        import json

        try:
            with open(CREDENTIALS_FILE) as f:
                creds = json.load(f)
                return creds.get("username"), creds.get("password")
        except (OSError, json.JSONDecodeError):
            pass

    return None, None


def save_credentials(username: str, password: str) -> None:
    """Save credentials to config file."""
    import json

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump({"username": username, "password": password}, f)
    # Set restrictive permissions
    CREDENTIALS_FILE.chmod(0o600)


def clear_credentials() -> None:
    """Remove saved credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
