"""Garmin Connect client with session caching."""

import logging

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from .config import Settings

logger = logging.getLogger(__name__)


class GarminClient:
    """Wrapper around garminconnect.Garmin with automatic session persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings.from_env()
        self._client: Garmin | None = None

    @property
    def api(self) -> Garmin:
        """Return an authenticated Garmin instance, creating one if needed."""
        if self._client is None:
            self._client = self._authenticate()
        return self._client

    def _authenticate(self) -> Garmin:
        """Authenticate with Garmin Connect, using cached tokens if available."""
        client = Garmin(
            email=self._settings.garmin_email,
            password=self._settings.garmin_password,
        )
        token_dir = self._settings.session_dir
        token_dir.mkdir(parents=True, exist_ok=True)
        token_path = str(token_dir / "tokens")

        try:
            client.login(tokenstore=token_path)
            logger.info("Authenticated with Garmin Connect")
            self._save_tokens(client, token_path)
            return client
        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
        ):
            logger.warning(
                "Initial auth failed, attempting fresh login"
            )

        # Retry with fresh credentials (no tokenstore)
        try:
            client.login()
            logger.info("Fresh login succeeded")
            self._save_tokens(client, token_path)
            return client
        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
        ) as exc:
            raise GarminConnectAuthenticationError(
                "Failed to authenticate with Garmin Connect after retry"
            ) from exc

    @staticmethod
    def _save_tokens(client: Garmin, token_path: str) -> None:
        """Persist garth tokens to disk."""
        try:
            client.garth.dump(token_path)
            logger.debug("Tokens saved to %s", token_path)
        except Exception:
            logger.warning("Failed to save tokens", exc_info=True)
