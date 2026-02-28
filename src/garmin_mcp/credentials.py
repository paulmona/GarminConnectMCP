"""Garmin credentials storage backed by a JSON file in config/."""

import json
import os
import stat
from pathlib import Path

CREDENTIALS_PATH = Path("config/garmin_auth.json")


class CredentialsNotConfiguredError(Exception):
    """Raised when Garmin credentials have not been configured yet."""


def load(path: Path = CREDENTIALS_PATH) -> dict | None:
    """Read garmin_auth.json and return {"email": ..., "password": ...}.

    Returns None if the file is missing or incomplete.
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    if not email or not password:
        return None
    return {"email": email, "password": password}


def save(email: str, password: str, path: Path = CREDENTIALS_PATH) -> None:
    """Write credentials to garmin_auth.json with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"email": email, "password": password}, f, indent=2)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def exists(path: Path = CREDENTIALS_PATH) -> bool:
    """Return True if valid credentials are stored."""
    return load(path) is not None
