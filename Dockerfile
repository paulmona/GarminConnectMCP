FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies (cached layer — only rebuilds when deps change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Non-root user for runtime — session tokens are owned by this user,
# so 0700 permissions in garmin_client.py are meaningful.
RUN groupadd --gid 1000 mcp && \
    useradd --uid 1000 --gid mcp --create-home mcp

# Session token cache lives here; mount a volume to persist across restarts
RUN mkdir -p config/.session && chown -R mcp:mcp config/

USER mcp

# SSE transport — clients connect to http://<host>:8000/sse
EXPOSE 8000

ENV MCP_MODE=sse

LABEL org.opencontainers.image.title="Garmin Connect MCP Server" \
      org.opencontainers.image.description="MCP server exposing Garmin Connect data (HRV, sleep, activities, recovery) to Claude AI" \
      org.opencontainers.image.source="https://github.com/paulmon/GarminConnectMCP" \
      org.opencontainers.image.licenses="MIT" \
      net.unraid.docker.icon="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/garmin-connect.png" \
      net.unraid.docker.webui="http://[IP]:[PORT:8000]/mcp"

CMD ["uv", "run", "garmin-mcp"]
