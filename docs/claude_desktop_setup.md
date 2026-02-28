# Claude Desktop Setup

## Prerequisites

1. Clone the repo and install dependencies:
   ```bash
   cd GarminClaudeSync
   uv sync
   ```

2. Complete first-time setup (see below).

3. Verify the server starts:
   ```bash
   uv run garmin-mcp
   ```

## First-Time Setup

Before using the MCP server, you need to configure your Garmin credentials:

1. Start the web UI:
   ```bash
   uv run garmin-web
   ```

2. Visit [http://localhost:8585](http://localhost:8585) in your browser.

3. Enter your Garmin Connect email and password on the setup screen. Your
   credentials are verified against Garmin's servers before being saved.

4. Once credentials are saved, configure Claude Desktop (see below).

Credentials are stored locally in `config/garmin_auth.json` with owner-only
file permissions. This file is gitignored and should never be committed or
placed in the Claude Desktop config file.

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
      ]
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
- **get_recovery_snapshot** - All key recovery metrics in one call
