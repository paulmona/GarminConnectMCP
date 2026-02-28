"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path


class CredentialsNotConfiguredError(Exception):
    """Raised when Garmin credentials have not been configured yet."""


@dataclass(frozen=True)
class Settings:
    garmin_email: str
    garmin_password: str
    session_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        email = os.environ.get("GARMIN_EMAIL", "").strip()
        password = os.environ.get("GARMIN_PASSWORD", "").strip()
        if not email or not password:
            raise CredentialsNotConfiguredError(
                "GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set."
            )
        session_dir = Path(
            os.environ.get("GARMIN_SESSION_DIR", "config/.session")
        ).resolve()
        return cls(
            garmin_email=email,
            garmin_password=password,
            session_dir=session_dir,
        )
