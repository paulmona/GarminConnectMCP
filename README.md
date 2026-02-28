# Garmin MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives Claude real-time access to your Garmin Connect data for training analysis.

Ask Claude questions like *"How was my recovery this week?"*, *"Am I ready for a hard session today?"*, or *"Show me my HRV trend over the last month"* — and it will pull live data from your Garmin account to answer.

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
| `get_weight_trend` | Daily weights with min/max/average/change summary |
| `get_body_composition` | Body fat %, muscle mass, bone mass, visceral fat, metabolic age (requires Garmin smart scale) |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A Garmin Connect account
- Claude Desktop

## Installation

```bash
git clone https://github.com/paulmona/GarminConnectMCP.git
cd GarminConnectMCP
uv sync
```

## Claude Desktop Configuration

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
        "/absolute/path/to/GarminConnectMCP",
        "garmin-mcp"
      ],
      "env": {
        "GARMIN_EMAIL": "your@email.com",
        "GARMIN_PASSWORD": "yourpassword"
      }
    }
  }
}
```

Use the full path to `uv` (find it with `which uv`). Quit and relaunch Claude Desktop — a hammer icon will appear in the chat bar confirming the 13 tools are loaded.

## Project Structure

```
src/garmin_mcp/
├── server.py          # MCP server — 13 tool definitions
├── garmin_client.py   # Garmin auth with session caching and auto re-auth
├── config.py          # Settings loader (reads GARMIN_EMAIL / GARMIN_PASSWORD)
├── tools/
│   ├── activities.py  # Activity tools
│   ├── health.py      # HRV, sleep, body battery, resting HR tools
│   ├── training.py    # Training status, race predictions, weekly summary, recovery snapshot
│   └── body.py        # Weight trend and body composition tools

config/                # Runtime data — gitignored
└── .session/          # Garmin OAuth token cache (chmod 700)
```

## Security

Credentials are passed via environment variables in the Claude Desktop config and are never stored on disk or committed to git. OAuth session tokens are cached locally in `config/.session/` with owner-only permissions. See [SECURITY.md](SECURITY.md) for the full security model.

## Running Tests

```bash
uv run pytest
```

## License

MIT
