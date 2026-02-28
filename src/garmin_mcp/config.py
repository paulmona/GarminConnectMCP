"""Configuration loaded from credentials file."""

import os
from dataclasses import dataclass
from pathlib import Path

from . import credentials
from .credentials import CredentialsNotConfiguredError


@dataclass(frozen=True)
class Settings:
    garmin_email: str
    garmin_password: str
    session_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        creds = credentials.load()
        if creds is None:
            raise CredentialsNotConfiguredError(
                "Garmin credentials not configured. "
                "Run the web UI to complete setup: uv run garmin-web"
            )
        session_dir = Path(
            os.environ.get("GARMIN_SESSION_DIR", "config/.session")
        ).resolve()
        return cls(
            garmin_email=creds["email"],
            garmin_password=creds["password"],
            session_dir=session_dir,
        )
