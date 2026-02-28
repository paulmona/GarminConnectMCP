"""JSON-backed configuration store for runtime-editable settings."""

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "garmin": {
        "email": "",
        "password": "",
    },
    "hr_zones": [
        {"name": "Z1", "min_bpm": 99, "max_bpm": 119},
        {"name": "Z2", "min_bpm": 119, "max_bpm": 139},
        {"name": "Z3", "min_bpm": 139, "max_bpm": 158},
        {"name": "Z4", "min_bpm": 158, "max_bpm": 178},
        {"name": "Z5", "min_bpm": 178, "max_bpm": 198},
    ],
    "sync_schedule": {
        "interval_minutes": 60,
    },
    "data_export": {
        "activities": True,
        "hrv": True,
        "sleep": True,
        "body_battery": True,
        "training_status": True,
    },
    "status": {
        "last_sync": None,
        "last_error": None,
    },
}


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load config from JSON file, returning defaults if file is missing."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy


def save_config(config: dict[str, Any], path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Save config dict to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
