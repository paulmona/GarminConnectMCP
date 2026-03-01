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

---

## Option A — Local (Claude Desktop, stdio)

Best for a single machine. Claude Desktop spawns the server as a local process.

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Garmin Connect account

### Setup

```bash
git clone https://github.com/paulmona/GarminConnectMCP.git
cd GarminConnectMCP
uv sync
```

### Claude Desktop config

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

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

Use the full path to `uv` (find it with `which uv`). Quit and relaunch Claude Desktop — a hammer icon confirms the 13 tools are loaded.

---

## Option B — Docker (SSE, remote-friendly)

Best for running on a home server or NAS so Claude on any device (Desktop, mobile, web) can reach it.

### Requirements

- Docker and Docker Compose
- Garmin Connect account

### Setup

```bash
git clone https://github.com/paulmona/GarminConnectMCP.git
cd GarminConnectMCP
cp .env.example .env
# Edit .env and fill in your Garmin credentials
docker compose up -d
```

Or pull directly from Docker Hub (no clone needed):

```bash
GARMIN_EMAIL=your@email.com GARMIN_PASSWORD=yourpassword \
  docker run -d -p 8000:8000 \
  -e GARMIN_EMAIL -e GARMIN_PASSWORD -e MCP_MODE=sse \
  -v garmin-session:/app/config/.session \
  paulmon/garmin-connect-mcp:latest
```

### Claude Desktop config

```json
{
  "mcpServers": {
    "garmin": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Replace `localhost` with your server's IP or hostname if running remotely.

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GARMIN_EMAIL` | Yes | — | Garmin Connect email |
| `GARMIN_PASSWORD` | Yes | — | Garmin Connect password |
| `MCP_MODE` | No | `stdio` | Set to `sse` for Docker/remote |
| `MCP_API_KEY` | No | — | Bearer token; enables OAuth server. Strongly recommended when exposing over the internet |
| `MCP_TOTP_SECRET` | Yes (when `MCP_API_KEY` set) | — | Base32 TOTP secret for 2FA on OAuth `/authorize`. Required to prevent unauthorized token issuance. Generate with: `python3 -c "import pyotp; print(pyotp.random_base32())"` |
| `MCP_SERVER_URL` | No | `http://localhost:8000` | Public base URL for OAuth issuer/resource metadata |
| `MCP_HOST` | No | `0.0.0.0` | SSE bind address |
| `MCP_PORT` | No | `8000` | SSE port |

---

## Project Structure

```
src/garmin_mcp/
├── server.py          # MCP server — 13 tool definitions
├── garmin_client.py   # Garmin auth with session caching and auto re-auth
├── config.py          # Settings loader (reads env vars)
└── tools/
    ├── activities.py  # Activity tools
    ├── health.py      # HRV, sleep, body battery, resting HR tools
    ├── training.py    # Training status, race predictions, weekly summary, recovery snapshot
    └── body.py        # Weight trend and body composition tools

Dockerfile             # Production image (python3.13-bookworm-slim + uv)
docker-compose.yml     # Compose config with session volume
```

## Security

Credentials are passed via environment variables and never stored on disk or committed to git. OAuth session tokens are cached in `config/.session/` with owner-only permissions (or in a Docker volume). When `MCP_API_KEY` is set, the server enforces Bearer token authentication on all requests and exposes a full OAuth 2.0 PKCE server for claude.ai remote MCP. `MCP_TOTP_SECRET` is **required** in this mode — it gates the `/authorize` endpoint behind a 6-digit authenticator code, preventing unauthorized OAuth token issuance. See [SECURITY.md](SECURITY.md) for the full security model.

## Running Tests

```bash
uv sync --extra dev
uv run pytest
```

## License

MIT
