# Garmin MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives Claude real-time access to your Garmin Connect data for training analysis.

Ask Claude questions like *"How was my recovery this week?"*, *"Am I ready for a hard session today?"*, or *"Show me my HRV trend over the last month"* — and it will pull live data from your Garmin account to answer.

## Features

- **11 tools** covering activities, health metrics, and training status
- **Web UI** for first-time credential setup at `http://localhost:8585`
- **Session caching** — authenticates once, reuses tokens across calls
- **Auto re-auth** — transparently re-authenticates if a session expires mid-conversation
- **Google Drive fallback** for exporting data when a remote MCP connection isn't available

## Available Tools

| Tool | Description |
|------|-------------|
| `get_recent_activities` | Recent activities with distance, duration, HR, and pace |
| `get_activity_detail` | Full detail for a single activity including lap splits and HR zone breakdown |
| `get_activities_in_range` | Activities between two dates, optionally filtered by type |
| `get_hrv_trend` | HRV over recent days with 7-day rolling average |
| `get_sleep_history` | Sleep scores, total duration, and time in each sleep stage |
| `get_body_battery` | Daily Body Battery highs, lows, charged, and drained values |
| `get_resting_hr_trend` | Resting heart rate trend |
| `get_training_status` | VO2 max, training load, readiness score, and recovery time |
| `get_race_predictions` | Predicted finish times for 5K, 10K, half marathon, marathon |
| `get_weekly_summary` | Composite weekly summary: activities, distance, avg sleep, avg RHR |
| `get_recovery_snapshot` | All key recovery metrics in one call — use this first for readiness questions |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A Garmin Connect account
- Claude Desktop (for MCP integration)

## Installation

```bash
git clone https://github.com/yourname/garmin-mcp-server.git
cd garmin-mcp-server
uv sync
```

## Setup

Start the web UI to configure your Garmin credentials:

```bash
uv run garmin-web
```

Open [http://localhost:8585](http://localhost:8585), enter your Garmin Connect email and password, and click **Connect to Garmin**. Your credentials are verified against Garmin's servers before being saved locally to `config/garmin_auth.json` (owner-read-only, gitignored).

## Claude Desktop Integration

Add the following to your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "garmin": {
      "command": "/absolute/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/garmin-mcp-server",
        "garmin-mcp"
      ]
    }
  }
}
```

Use the full path to `uv` (find it with `which uv`). Quit and relaunch Claude Desktop — a hammer icon will appear in the chat bar confirming the tools are loaded.

## Project Structure

```
src/garmin_mcp/
├── server.py          # MCP server — 11 tool definitions
├── garmin_client.py   # Garmin auth with session caching and auto re-auth
├── credentials.py     # Credential storage (config/garmin_auth.json)
├── config.py          # Settings loader
├── tools/
│   ├── activities.py  # Activity tools
│   ├── health.py      # HRV, sleep, body battery, resting HR tools
│   └── training.py    # Training status, race predictions, weekly summary, recovery snapshot
└── web/
    └── app.py         # FastAPI config UI (port 8585)

fallback/
└── sync_to_drive.py   # Google Drive export script (alternative to MCP)

config/                # Runtime data — gitignored
├── garmin_auth.json   # Credentials (chmod 600)
├── config.json        # App settings (HR zones, sync schedule, etc.)
└── .session/          # Garmin OAuth token cache (chmod 700)
```

## Security

Credentials are stored locally in `config/garmin_auth.json` with owner-only file permissions and are never committed to git. The web UI binds to `127.0.0.1` only. See [SECURITY.md](SECURITY.md) for the full security model.

## Running Tests

```bash
uv run pytest
```

116 tests covering tools, credential handling, web UI, and server startup.
