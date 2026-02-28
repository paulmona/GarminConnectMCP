# Claude Desktop Setup

## Prerequisites

1. Clone the repo and install dependencies:
   ```bash
   cd GarminClaudeSync
   cp .env.example .env
   # Fill in GARMIN_EMAIL and GARMIN_PASSWORD in .env
   uv sync
   ```

2. Verify the server starts:
   ```bash
   uv run garmin-mcp
   ```

## Claude Desktop Configuration

Add the following to your `claude_desktop_config.json`:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "garmin": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/GarminClaudeSync",
        "garmin-mcp"
      ],
      "env": {
        "GARMIN_EMAIL": "your-email@example.com",
        "GARMIN_PASSWORD": "your-garmin-password"
      }
    }
  }
}
```

Replace `/absolute/path/to/GarminClaudeSync` with the actual path to your cloned repo.

## SSE Mode (Remote)

To run as an HTTP server instead of stdio:

```bash
MCP_MODE=sse uv run garmin-mcp
```

## Available Tools

Once connected, Claude will have access to these tools:

- **get_recent_activities** - Recent activities with distance, duration, HR, pace
- **get_activity_detail** - Full detail for a single activity with lap splits and HR zones
- **get_activities_in_range** - Activities between two dates
- **get_hrv_trend** - Heart Rate Variability trend with rolling average
- **get_sleep_history** - Sleep data with stages and scores
- **get_body_battery** - Body Battery daily levels
- **get_resting_hr_trend** - Resting heart rate trend
- **get_training_status** - Training status, VO2 max, readiness score
- **get_race_predictions** - Predicted race finish times
- **get_weekly_summary** - Composite weekly training summary
