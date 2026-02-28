FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies (cached layer — only rebuilds when deps change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Session token cache lives here; mount a volume to persist across restarts
RUN mkdir -p config/.session

# SSE transport — clients connect to http://<host>:8000/sse
EXPOSE 8000

ENV MCP_MODE=sse

CMD ["uv", "run", "garmin-mcp"]
