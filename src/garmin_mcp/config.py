"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    garmin_email: str
    garmin_password: str
    session_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        email = os.environ.get("GARMIN_EMAIL", "")
        password = os.environ.get("GARMIN_PASSWORD", "")
        session_dir = Path(
            os.environ.get("GARMIN_SESSION_DIR", ".session")
        ).resolve()
        if not email or not password:
            raise ValueError(
                "GARMIN_EMAIL and GARMIN_PASSWORD must be set in environment"
            )
        return cls(
            garmin_email=email,
            garmin_password=password,
            session_dir=session_dir,
        )
