# CLAUDE.md — homarr-mcp

## Project Overview

MCP server for managing Homarr dashboards via the tRPC API. Built on FastMCP with httpx.

- **Package**: `homarr-mcp`
- **Python**: >= 3.12
- **Registry**: `ghcr.io/tetra-2023/homarr-mcp`

## Architecture

```
src/
  server.py         — MCP tool definitions (18 tools via @mcp.tool())
  homarr_client.py  — HomarrClient: async tRPC client (httpx-based)
  config.py         — Pydantic settings (HOMARR_URL, HOMARR_API_KEY)
```

- `server.py` registers tools grouped by resource: boards, apps, groups, users.
- `homarr_client.py` handles tRPC wire format: GET for queries, POST for mutations, `ApiKey` header.
- No session management — single global client instance, stateless API key auth.

## Homarr tRPC API

- Queries: `GET /api/trpc/{procedure}?input={"json":{...}}`
- Mutations: `POST /api/trpc/{procedure}` with body `{"json":{...}}`
- Response: `{"result":{"data":{"json": <actual_data>}}}`
- Auth: `ApiKey` header with `<id>.<token>` format

## Development Setup

```bash
uv sync --all-extras --dev
cp .env.example .env  # Configure HOMARR_URL, HOMARR_API_KEY
```

## Running

```bash
uv run python src/server.py                    # stdio (default)
uv run python src/server.py --streamable-http  # HTTP transport
```

Environment variables: `HOMARR_URL`, `HOMARR_API_KEY`, `HOMARR_TRANSPORT`, `MCP_HOST`, `MCP_PORT`.

## Testing

```bash
uv run pytest tests/test_server.py -v
```

## Code Conventions

- **Linter/formatter**: ruff (line-length=100, target py312, rules: E, F, W, I)
- **Commit messages**: Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- **Tool pattern**: `@mcp.tool()` → get client → call client method → filter response
- **Response filtering**: `verbosity` parameter (minimal/standard/full) via `RESPONSE_FIELDS` dict
- **Security**: Never log API keys. Use `SecretStr` for credentials.
