# GarminClaudeSync

MCP server that exposes Garmin Connect data to Claude for Hyrox training analysis.

## Setup

```bash
cp .env.example .env
# Fill in your Garmin credentials in .env
uv sync
```

## Usage

```bash
uv run python -m garmin_mcp
```
