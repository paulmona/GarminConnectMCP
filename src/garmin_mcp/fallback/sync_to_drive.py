"""Fallback sync: pull Garmin data to JSON files and upload to Google Drive."""

import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from garmin_mcp.garmin_client import GarminClient
from garmin_mcp.tools.activities import get_recent_activities
from garmin_mcp.tools.health import get_hrv_trend, get_sleep_history
from garmin_mcp.tools.training import get_training_status

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")


def pull_garmin_data(client: GarminClient) -> dict[str, object]:
    """Pull data from Garmin Connect and return as dict of filename -> data."""
    api = client.api
    files: dict[str, object] = {}

    logger.info("Pulling recent activities (30 days)")
    today = date.today()
    start_30d = (today - timedelta(days=30)).isoformat()
    try:
        from garmin_mcp.tools.activities import get_activities_in_range
        files["activities_30d.json"] = get_activities_in_range(
            api, start_30d, today.isoformat()
        )
    except Exception:
        logger.exception("Failed to pull activities")
        files["activities_30d.json"] = []

    logger.info("Pulling HRV trend (90 days)")
    try:
        files["hrv_90d.json"] = get_hrv_trend(api, days=90)
    except Exception:
        logger.exception("Failed to pull HRV")
        files["hrv_90d.json"] = {}

    logger.info("Pulling sleep history (90 days)")
    try:
        files["sleep_90d.json"] = get_sleep_history(api, days=90)
    except Exception:
        logger.exception("Failed to pull sleep")
        files["sleep_90d.json"] = []

    logger.info("Pulling training status")
    try:
        files["training_status.json"] = get_training_status(api)
    except Exception:
        logger.exception("Failed to pull training status")
        files["training_status.json"] = {}

    return files


def write_local(files: dict[str, object]) -> Path:
    """Write data files to local output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, data in files.items():
        path = OUTPUT_DIR / filename
        with open(path, "w") as f:
            json.dump(data, f, default=str, indent=2)
        logger.info("Wrote %s", path)
    return OUTPUT_DIR


def upload_to_drive(
    folder_id: str,
    service_account_json: str,
    files: dict[str, object],
) -> None:
    """Upload JSON files to a Google Drive folder."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload
    except ImportError:
        raise RuntimeError(
            "google-api-python-client and google-auth are required. "
            "Install with: uv pip install garmin-mcp[gdrive]"
        )

    creds = service_account.Credentials.from_service_account_file(
        service_account_json,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=creds)

    # List existing files in the folder to find ones to overwrite
    existing = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name)",
        )
        .execute()
        .get("files", [])
    )
    existing_map = {f["name"]: f["id"] for f in existing}

    for filename, data in files.items():
        content = json.dumps(data, default=str, indent=2).encode()
        media = MediaInMemoryUpload(content, mimetype="application/json")

        if filename in existing_map:
            # Update existing file
            service.files().update(
                fileId=existing_map[filename],
                media_body=media,
            ).execute()
            logger.info("Updated %s in Drive", filename)
        else:
            # Create new file
            metadata = {"name": filename, "parents": [folder_id]}
            service.files().create(
                body=metadata,
                media_body=media,
            ).execute()
            logger.info("Created %s in Drive", filename)


def main() -> None:
    """Run the full sync pipeline."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    client = GarminClient()
    files = pull_garmin_data(client)
    write_local(files)

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if folder_id and sa_json:
        logger.info("Uploading to Google Drive folder %s", folder_id)
        upload_to_drive(folder_id, sa_json, files)
        logger.info("Drive sync complete")
    else:
        logger.info(
            "GOOGLE_DRIVE_FOLDER_ID or GOOGLE_SERVICE_ACCOUNT_JSON not set, "
            "skipping Drive upload. Files saved locally in output/"
        )


if __name__ == "__main__":
    main()
